"""Legacy reconfirmation: atomic lifecycle, provider pause and private admin I/O."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

import main
from routers import newsletter, newsletter_admin
from services import newsletter_service
from services.newsletter_consent import (
    CONFIRMED_KEY, SUPPRESSED_KEY, RECONFIRM_KEY, RECONFIRM_SECONDS,
    BREVO_ADD_RETRY_KEY, BREVO_REMOVE_RETRY_KEY, LISTMONK_REMOVE_RETRY_KEY,
    START_RECONFIRM, CLAIM_RECONFIRM_SEND, CONFIRM_RECONFIRM, EXPIRE_RECONFIRM,
    FINISH_RECONFIRM_EXPIRY, reconfirm_token_key, reconfirm_digest_key,
    delivery_eligible, has_doi_evidence,
)
from tests.test_newsletter_delivery_sync import MemoryRedis, consent, EMAIL, HTTP_CLIENT

NOW = datetime(2026, 10, 21, 9, tzinfo=timezone.utc)
TOKEN = "synthetic-reconfirmation-token"
AUTH = {"Authorization": "Bearer synthetic-admin-key"}
ADMIN = "/api/v1/admin/newsletter/reconfirm"


class Clock(datetime):
    value = NOW

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return cls.value if tz else cls.value.replace(tzinfo=None)


class ReconfirmRedis(MemoryRedis):
    def __init__(self) -> None:
        super().__init__()
        self.ttls: dict[str, int] = {}

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        keys, values = args[:numkeys], args[numkeys:]
        if script == START_RECONFIRM:
            confirmed, suppressed, registry, token, old_token = keys
            email, normalized, raw, previous, invitation, ttl = values
            if (normalized in self.hashes[suppressed] or self.hashes[confirmed].get(email) != raw
                    or self.hashes[registry].get(normalized, "") != previous):
                return 0
            self.hashes[confirmed][email] = invitation
            self.hashes[registry][normalized] = invitation
            if old_token != token:
                self.pending.pop(old_token, None)
            self.pending[token] = invitation
            self.ttls[token] = ttl
        elif script == CLAIM_RECONFIRM_SEND:
            confirmed, registry, suppressed = keys
            email, normalized, raw, attempted = values
            if (normalized in self.hashes[suppressed] or self.hashes[confirmed].get(email) != raw
                    or self.hashes[registry].get(normalized) != raw):
                return 0
            self.hashes[confirmed][email] = attempted
            self.hashes[registry][normalized] = attempted
        elif script == CONFIRM_RECONFIRM:
            token, confirmed, registry, suppressed = keys
            invitation, email, normalized, raw, evidence = values
            if (self.pending.get(token) != invitation or normalized in self.hashes[suppressed]
                    or self.hashes[confirmed].get(email) != raw or self.hashes[registry].get(normalized) != raw):
                return 0
            self.hashes[confirmed][email] = evidence
            self.hashes[registry].pop(normalized)
            self.pending.pop(token)
        elif script == EXPIRE_RECONFIRM:
            confirmed, registry, token, addition, brevo_retry, listmonk_retry = keys
            email, normalized, raw, cleanup, configured = values
            if (self.hashes[registry].get(normalized) != raw
                    or self.hashes[confirmed].get(email) not in (None, raw)):
                return 0
            self.hashes[registry][normalized] = cleanup
            self.hashes[confirmed].pop(email, None)
            self.pending.pop(token, None)
            self.hashes[addition].pop(email, None)
            self.hashes[brevo_retry][email] = "1"
            if configured == "1":
                self.hashes[listmonk_retry][email] = "1"
        elif script == FINISH_RECONFIRM_EXPIRY:
            normalized, raw = values
            if self.hashes[keys[0]].get(normalized) != raw:
                return 0
            self.hashes[keys[0]].pop(normalized)
        else:
            return await super().eval(script, numkeys, *args)
        self.mutations.append("eval")
        return 1


def legacy(email: str = EMAIL, **changes: Any) -> dict[str, Any]:
    data = consent(email=email)
    for key in ("consent_schema", "requested_at", "confirmed_at", "confirmation_method"):
        data.pop(key)
    return dict(data, **changes)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> ReconfirmRedis:
    redis = ReconfirmRedis()
    Clock.value = NOW
    monkeypatch.setattr(newsletter, "datetime", Clock)
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=redis))
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    monkeypatch.setattr(newsletter.secrets, "token_urlsafe", lambda _: TOKEN)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")
    monkeypatch.setattr(newsletter_service, "contact_status", AsyncMock(return_value="already_present"))
    monkeypatch.setattr(newsletter_service, "remove_contact", AsyncMock(return_value=True))
    monkeypatch.setattr(newsletter_service, "add_contact", AsyncMock(return_value=True))
    monkeypatch.setattr(newsletter_service, "send_reconfirmation", AsyncMock(return_value=True))
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(side_effect=AssertionError("Unexpected network")))
    redis.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(legacy())
    return redis


async def post(path: str = ADMIN, **params: Any) -> httpx.Response:
    app = FastAPI()
    app.include_router(newsletter.router)
    app.include_router(newsletter_admin.router)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, params=params, headers=AUTH)


async def test_dry_run_only_selects_missing_evidence_and_never_writes(store: ReconfirmRedis) -> None:
    # Valid DOI without topics is held by backfill, but is outside reconfirmation.
    valid = consent(email="valid@example.org", requested_at=(NOW - timedelta(hours=1)).isoformat(),
                    confirmed_at=NOW.isoformat(), topics={topic: False for topic in legacy()["topics"]})
    store.hashes[CONFIRMED_KEY].update({valid["email"]: json.dumps(valid), "bad@example.org": "{}",
                                      "withdrawn@example.org": json.dumps(legacy(email="withdrawn@example.org"))})
    store.hashes[SUPPRESSED_KEY]["withdrawn@example.org"] = "unsubscribed"
    before = dict(store.hashes[CONFIRMED_KEY])
    response = await post()
    assert response.status_code == 200
    assert response.json() == {"selected": 1, "pending": 0, "paused": 0, "sent": 0, "skipped": 3, "failed": 0}
    assert store.hashes[CONFIRMED_KEY] == before
    assert not store.mutations
    newsletter_service.send_reconfirmation.assert_not_awaited()
    newsletter_service.remove_contact.assert_not_awaited()


async def test_apply_pauses_before_sending_once_and_repeats_safely(store: ReconfirmRedis) -> None:
    async def send(email: str, token: str) -> bool:
        newsletter_service.remove_contact.assert_awaited_once_with(EMAIL)
        assert json.loads(store.hashes[CONFIRMED_KEY][EMAIL])["consent_state"] == "reconfirm_pending"
        assert not delivery_eligible(json.loads(store.hashes[CONFIRMED_KEY][EMAIL]), NOW)
        assert TOKEN not in repr(store.hashes) + repr(store.pending)
        return True

    newsletter_service.send_reconfirmation.side_effect = send
    response = await post(dry_run=False)
    assert response.status_code == 200
    assert response.json()["sent"] == response.json()["paused"] == 1
    assert store.ttls[reconfirm_token_key(TOKEN)] == RECONFIRM_SECONDS
    state = json.loads(store.hashes[CONFIRMED_KEY][EMAIL])
    assert state["reconfirm_created_at"] == state["requested_at"] == NOW.isoformat()
    assert state["reconfirm_send_attempted_at"] == NOW.isoformat()
    assert (await post(dry_run=False)).json()["sent"] == 0
    newsletter_service.send_reconfirmation.assert_awaited_once_with(EMAIL, TOKEN)


async def test_concurrent_admin_runs_send_one_invitation(store: ReconfirmRedis) -> None:
    results = await asyncio.gather(*[newsletter.reconfirm_legacy(dry_run=False) for _ in range(12)])
    assert sum(result["sent"] for result in results) == 1
    newsletter_service.send_reconfirmation.assert_awaited_once()


async def test_explicit_resend_rotates_token_without_extending_deadline(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await post(dry_run=False)
    Clock.value = NOW + timedelta(days=8)
    monkeypatch.setattr(newsletter.secrets, "token_urlsafe", lambda _: TOKEN + "-new")
    response = await post(dry_run=False, resend=True)
    assert response.json()["sent"] == 1
    assert reconfirm_token_key(TOKEN) not in store.pending
    assert store.ttls[reconfirm_token_key(TOKEN + "-new")] == 22 * 86400
    assert json.loads(store.hashes[CONFIRMED_KEY][EMAIL])["reconfirm_created_at"] == NOW.isoformat()
    assert (await newsletter.confirm_subscription(TOKEN)).status_code == 410
    assert (await newsletter.confirm_subscription(TOKEN + "-new")).status_code == 200


@pytest.mark.parametrize("suppression", ["local", "provider", "listmonk"])
@pytest.mark.parametrize("dry_run", [True, False])
async def test_suppressed_records_never_receive_an_invitation(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch, suppression: str, dry_run: bool,
) -> None:
    if suppression == "local":
        store.hashes[SUPPRESSED_KEY][EMAIL.casefold()] = "withdrawn"
    elif suppression == "provider":
        newsletter_service.contact_status.return_value = "suppressed"
    else:
        monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
        monkeypatch.setattr(newsletter, "_listmonk_reconfirm_contact", AsyncMock(return_value={
            "id": 7, "email": EMAIL, "status": "blocklisted", "lists": [],
        }))
        monkeypatch.setattr(newsletter, "_remove_listmonk_contact", AsyncMock(return_value=True))
    response = await post(dry_run=dry_run)
    assert response.status_code == 200
    assert response.json()["selected"] == response.json()["sent"] == 0
    newsletter_service.send_reconfirmation.assert_not_awaited()
    if dry_run:
        assert not store.mutations


@pytest.mark.parametrize("failure", ["pause", "smtp"])
async def test_failed_or_ambiguous_provider_work_does_not_automatically_resend(
    store: ReconfirmRedis, failure: str,
) -> None:
    if failure == "pause":
        newsletter_service.remove_contact.return_value = False
    else:
        newsletter_service.send_reconfirmation.return_value = False
    response = await post(dry_run=False)
    assert response.json()["failed"] == 1
    assert EMAIL in store.hashes[CONFIRMED_KEY]
    newsletter_service.remove_contact.return_value = True
    newsletter_service.send_reconfirmation.return_value = True
    await post(dry_run=False)
    assert newsletter_service.send_reconfirmation.await_count == (0 if failure == "pause" else 1)


async def test_withdrawal_during_pause_prevents_send_and_click(store: ReconfirmRedis) -> None:
    async def pause(email: str) -> bool:
        store.hashes[SUPPRESSED_KEY][email.casefold()] = "withdrawn"
        store.hashes[CONFIRMED_KEY].pop(email, None)
        return True

    newsletter_service.remove_contact.side_effect = pause
    assert (await post(dry_run=False)).json()["sent"] == 0
    newsletter_service.send_reconfirmation.assert_not_awaited()
    assert (await newsletter.confirm_subscription(TOKEN)).status_code == 410
    newsletter_service.add_contact.assert_not_awaited()


@pytest.mark.parametrize("days", [0, 12, 29])
@pytest.mark.parametrize("topics", [True, False])
async def test_click_replaces_legacy_with_fresh_doi_and_enrolls_only_with_topics(
    store: ReconfirmRedis, days: int, topics: bool,
) -> None:
    original = legacy(topics={topic: topics for topic in legacy()["topics"]})
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(original)
    await post(dry_run=False)
    Clock.value = NOW + timedelta(days=days)
    assert (await newsletter.confirm_subscription(TOKEN)).status_code == 200
    evidence = json.loads(store.hashes[CONFIRMED_KEY][EMAIL])
    assert evidence["requested_at"] == NOW.isoformat()
    assert evidence["confirmed_at"] == Clock.value.isoformat()
    assert evidence["confirmation_method"] == "double_opt_in"
    assert evidence["confirmation_source"] == "legacy_reconfirmation"
    assert evidence["topics"] == original["topics"]
    assert has_doi_evidence(evidence, Clock.value)
    assert delivery_eligible(evidence, Clock.value) is topics
    assert all(not key.startswith("reconfirm_") for key in evidence)
    assert not store.hashes[RECONFIRM_KEY]
    assert (await newsletter.confirm_subscription(TOKEN)).status_code == 410
    assert newsletter_service.add_contact.await_count == int(topics)


async def test_ordinary_doi_evidence_retains_24_hour_limit() -> None:
    evidence = consent(requested_at=NOW.isoformat(), confirmed_at=(NOW + timedelta(days=2)).isoformat())
    assert not has_doi_evidence(evidence, NOW + timedelta(days=2))


@pytest.mark.parametrize("elapsed,expired", [(30 * 86400 - 1, False), (30 * 86400, True), (31 * 86400, True)])
async def test_expiry_boundary_dry_run_apply_and_idempotency(
    store: ReconfirmRedis, elapsed: int, expired: bool,
) -> None:
    await post(dry_run=False)
    Clock.value = NOW + timedelta(seconds=elapsed)
    mutations = list(store.mutations)
    dry = await post(ADMIN + "/expire")
    assert dry.json() == {"expired": int(expired), "deleted": 0, "pending": int(not expired), "failed": 0}
    assert store.mutations == mutations
    result = await post(ADMIN + "/expire", dry_run=False)
    assert result.json()["deleted"] == int(expired)
    assert (EMAIL not in store.hashes[CONFIRMED_KEY]) is expired
    if expired:
        assert not store.pending and not store.hashes[RECONFIRM_KEY]
        assert (await newsletter.confirm_subscription(TOKEN)).status_code == 410
        assert (await post(ADMIN + "/expire", dry_run=False)).json()["expired"] == 0


async def test_expired_link_cannot_restore_legacy_before_cleanup(store: ReconfirmRedis) -> None:
    await post(dry_run=False)
    Clock.value = NOW + timedelta(days=30)
    assert (await newsletter.confirm_subscription(TOKEN)).status_code == 410
    assert (await post(dry_run=False, resend=True)).json()["sent"] == 0
    newsletter_service.add_contact.assert_not_awaited()


async def test_expiry_keeps_provider_retry_but_deletes_consent_and_token(store: ReconfirmRedis) -> None:
    await post(dry_run=False)
    Clock.value = NOW + timedelta(days=31)
    newsletter_service.remove_contact.return_value = False
    response = await post(ADMIN + "/expire", dry_run=False)
    assert response.json()["failed"] == 1
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    assert not store.pending
    assert EMAIL in store.hashes[BREVO_REMOVE_RETRY_KEY]
    cleanup = json.loads(store.hashes[RECONFIRM_KEY][EMAIL.casefold()])
    assert set(cleanup) == {"email", "consent_state", "reconfirm_created_at"}
    newsletter_service.remove_contact.return_value = True
    assert (await post(ADMIN + "/expire", dry_run=False)).json()["deleted"] == 1
    assert not store.hashes[RECONFIRM_KEY]


async def test_confirmed_record_is_never_expired(store: ReconfirmRedis) -> None:
    await post(dry_run=False)
    await newsletter.confirm_subscription(TOKEN)
    saved = store.hashes[CONFIRMED_KEY][EMAIL]
    Clock.value = NOW + timedelta(days=60)
    assert (await post(ADMIN + "/expire", dry_run=False)).json()["deleted"] == 0
    assert store.hashes[CONFIRMED_KEY][EMAIL] == saved


async def test_listmonk_pause_unlinks_without_blocklisting_or_deleting(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-password")
    contact = {"id": 7, "email": EMAIL, "status": "enabled", "lists": [{"id": 3}]}
    calls = AsyncMock(side_effect=lambda method, *_: {"data": {"results": [contact]}} if method == "GET" else {"data": True})
    monkeypatch.setattr(newsletter, "_listmonk_request", calls)
    assert (await post(dry_run=False)).json()["sent"] == 1
    writes = [call.args for call in calls.await_args_list if call.args[0] != "GET"]
    assert writes == [("PUT", "/api/subscribers/lists", {
        "ids": [7], "action": "remove", "target_list_ids": sorted(newsletter.LIST_IDS.values()),
    })]


async def test_campaign_guard_repairs_pause_and_blocks_provider_failure(store: ReconfirmRedis) -> None:
    await post(dry_run=False)
    newsletter_service.remove_contact.reset_mock()
    assert await newsletter_service.ensure_reconfirmations_paused()
    newsletter_service.remove_contact.assert_awaited_once_with(EMAIL)
    newsletter_service.remove_contact.return_value = False
    assert not await newsletter_service.ensure_reconfirmations_paused()


async def test_backfill_cannot_enroll_pending_reconfirmations(store: ReconfirmRedis) -> None:
    await post(dry_run=False)
    counts = await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True)
    assert counts["held"] == 1
    assert counts["to_add"] == counts["already_present"] == 0
    newsletter_service.add_contact.assert_not_awaited()


@pytest.mark.parametrize("hook", ["before_send", "before_send_transaction"])
def test_sentry_scrubs_reconfirmation_links_and_bearer_tokens(hook: str) -> None:
    event = {
        "request": {"url": f"https://api.ekklesia.gr/api/v1/newsletter/confirm/{TOKEN}"},
        "extra": {"token": TOKEN, "url": f"https://api.ekklesia.gr/api/v1/newsletter/confirm/{TOKEN}",
                  "raw": json.dumps({"email": EMAIL})},
        "exception": {"values": [{"stacktrace": {"frames": [{"vars": {
            "token": TOKEN, "body": f'<a href="https://api.ekklesia.gr/api/v1/newsletter/confirm/{TOKEN}">Confirm</a>',
        }}]}}]},
    }
    result = main._sentry_init_options("https://synthetic@example.org/1")[hook](event, {})
    assert EMAIL not in repr(result) and TOKEN not in repr(result)


async def test_admin_campaign_cannot_send_until_pending_contacts_are_paused(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await post(dry_run=False)
    newsletter_service.remove_contact.return_value = False
    provider = AsyncMock(return_value={"subject": "Fixture"})
    monkeypatch.setattr(newsletter_admin, "_brevo_request", provider)
    app = FastAPI()
    app.include_router(newsletter_admin.router)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/newsletter/send", json={"campaign_id": 123, "confirm": True}, headers=AUTH)
    assert response.status_code == 503
    assert [call.args[0] for call in provider.await_args_list] == ["GET"]


async def test_monthly_campaign_cannot_send_until_pending_contacts_are_paused(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await post(dry_run=False)
    newsletter_service.remove_contact.return_value = False
    db = MagicMock()
    db.scalar = AsyncMock(return_value=0)
    db.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
    provider = AsyncMock(return_value={"id": 123})
    monkeypatch.setattr(newsletter_service, "_brevo_post", provider)
    assert not await newsletter_service.send_monthly_report(db)
    provider.assert_not_awaited()


@pytest.mark.parametrize("path", [ADMIN, ADMIN + "/expire"])
async def test_auth_and_private_validation_errors(store: ReconfirmRedis, path: str) -> None:
    app = FastAPI()
    app.include_router(newsletter_admin.router)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for headers in ({}, {"Authorization": "Bearer invalid-key"}):
            assert (await client.post(path, headers=headers)).status_code == 403
        response = await client.post(path, params={"dry_run": EMAIL + TOKEN}, headers=AUTH)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid newsletter request"}
    assert EMAIL not in response.text and TOKEN not in response.text
    assert not store.mutations


@pytest.mark.parametrize("path", [ADMIN, ADMIN + "/expire"])
async def test_store_failure_returns_fixed_503_without_pii(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, path: str,
) -> None:
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(side_effect=RuntimeError(EMAIL + TOKEN)))
    response = await post(path, dry_run=False)
    assert response.status_code == 503
    assert response.json() == {"detail": "Newsletter reconfirmation unavailable; retry"}
    assert EMAIL not in response.text + caplog.text and TOKEN not in response.text + caplog.text


async def test_transactional_template_is_neutral_and_has_one_link(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncMock(return_value={})
    monkeypatch.setattr(newsletter_service, "_brevo_post", provider)
    assert await newsletter_service.send_reconfirmation(EMAIL, TOKEN)
    endpoint, data = provider.await_args.args
    assert endpoint == "smtp/email"
    assert data["sender"] == newsletter_service.SENDER
    assert data["htmlContent"].count('<a href=') == 1
    assert "30" in data["htmlContent"] and TOKEN in data["htmlContent"]
    for name in ("Brevo", "Listmonk", "Telegram", "GitHub", "Κατεβάστε"):
        assert name not in data["subject"] + data["htmlContent"]


async def test_scheduler_applies_expiry_and_logs_only_counts(
    store: ReconfirmRedis, caplog: pytest.LogCaptureFixture,
) -> None:
    await post(dry_run=False)
    Clock.value = NOW + timedelta(days=31)
    with caplog.at_level(logging.INFO):
        await main.scheduled_newsletter_reconfirm_expiry()
    assert EMAIL not in store.hashes[CONFIRMED_KEY]
    assert "expired=1 deleted=1 pending=0 failed=0" in caplog.text
    assert EMAIL not in caplog.text and TOKEN not in caplog.text


async def test_scheduler_failure_does_not_log_exception_values(
    store: ReconfirmRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(newsletter, "expire_reconfirmations", AsyncMock(side_effect=RuntimeError(EMAIL + TOKEN)))
    outcome = MagicMock()
    monkeypatch.setattr(main, "report_outcome", outcome)
    await main.scheduled_newsletter_reconfirm_expiry()
    outcome.assert_called_once_with("failed")
    assert EMAIL not in caplog.text and TOKEN not in caplog.text
