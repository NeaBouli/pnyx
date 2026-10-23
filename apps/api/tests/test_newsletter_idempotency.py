"""Durable campaign retries, including lost provider and Redis acknowledgements."""
import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone

import httpx
import pytest

from routers import newsletter, newsletter_admin
from services import newsletter_service
from services.newsletter_claims import (
    CLAIMS_KEY, WRITE_CLAIM, DispatchClaim, FENCE_FIELD, CAMPAIGN_PREFIX, dispatch_status,
)
from services.newsletter_lock import LOCK_KEY, newsletter_lock
from tests.test_newsletter_audiences import (
    provider, store, seed_campaign, save, consent, dispatch, db, EMAIL,
)
from tests.test_newsletter_delivery_sync import HTTP_CLIENT, application


def claims(store):
    return {key: json.loads(raw) for key, raw in store.hashes[CLAIMS_KEY].items()
            if key != FENCE_FIELD and not key.startswith(CAMPAIGN_PREFIX)}


@pytest.mark.parametrize("failure", ["create", "rejected", "connect"])
async def test_monthly_retry_resumes_only_unsent_language_and_reuses_draft(store, provider, monkeypatch, failure):
    save(store, provider, consent())
    save(store, provider, consent("english@example.org", language="en"))
    original = provider.request
    failed = False
    english_id = None

    def request(req):
        nonlocal failed, english_id
        if req.method == "POST" and req.url.path == "/v3/emailCampaigns":
            payload = json.loads(req.content)
            language = payload["tag"].split(":")[2]
            assert any(key.endswith(":" + language) and value["state"] == "claimed"
                       for key, value in claims(store).items())
            if language == "en" and failure == "create" and not failed:
                failed = True
                return httpx.Response(400)
        if req.url.path.endswith("/sendNow"):
            campaign_id = int(req.url.path.split("/")[-2])
            claim = next(value for value in claims(store).values() if value["campaign_id"] == campaign_id)
            assert claim["state"] == "uncertain"  # Durable before the provider can accept.
            if provider.campaigns[campaign_id]["tag"].split(":")[2] == "en":
                english_id = campaign_id
                if failure != "create" and not failed:
                    failed = True
                    if failure == "connect":
                        raise httpx.ConnectTimeout(EMAIL, request=req)
                    return httpx.Response(400)
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    assert not await newsletter_service.send_monthly_report(db())
    assert provider.delivered == [{EMAIL}]
    states = claims(store)
    assert sorted(value["state"] for value in states.values()) == ["failed", "sent"]
    before_id = english_id
    assert await newsletter_service.send_monthly_report(db())
    assert before_id is None or english_id == before_id
    assert provider.delivered == [{EMAIL}, {"english@example.org"}]
    assert await newsletter_service.send_monthly_report(db())  # Standby scheduler rerun.
    assert len(provider.sent) == len(provider.campaigns) == 2
    assert all(value["state"] == "sent" for value in claims(store).values())


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_successful_campaign_is_durable_across_later_workers(store, provider, kind):
    seed_campaign(store, provider)
    await dispatch(kind)
    mutations = len(provider.writes)
    # The next call obtains a fresh Redis lease, as another scheduler/worker does.
    result = await dispatch(kind)
    assert result is True if kind == "monthly" else result["reason"] == "already_sent"
    assert len(provider.sent) == 1 and len(provider.writes) == mutations


@pytest.mark.parametrize("kind", ["monthly", "admin"])
@pytest.mark.parametrize("failure", ["lost_ack", "timeout", "server", "cancel"])
async def test_uncertain_send_stays_manual_without_automatic_resend(store, provider, monkeypatch, kind, failure):
    seed_campaign(store, provider)
    original = provider.request
    attempts = 0

    def request(req):
        nonlocal attempts
        if req.url.path.endswith("/sendNow"):
            attempts += 1
            if failure == "lost_ack":
                original(req)
            if failure == "cancel":
                raise asyncio.CancelledError()
            if failure == "server":
                return httpx.Response(503, text=EMAIL + " private-token")
            raise httpx.ReadTimeout(EMAIL + " private-token", request=req)
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await dispatch(kind)
    elif kind == "admin":
        with pytest.raises(newsletter.HTTPException):
            await dispatch(kind)
    else:
        assert not await dispatch(kind)
    assert any(value["state"] == "uncertain" and value["campaign_id"] for value in claims(store).values())
    for _ in range(2):
        result = await dispatch(kind)
        if kind == "admin":
            assert result["reason"] == "dispatch_uncertain"
        else:
            assert result is False
    assert attempts == 1
    assert len(provider.sent) == int(failure == "lost_ack")
    assert any(value["state"] == "uncertain"
               for value in claims(store).values())


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_send_success_then_redis_failure_cannot_duplicate_delivery(store, provider, monkeypatch, kind):
    seed_campaign(store, provider)
    original = store.eval

    async def evaluate(script, numkeys, *args):
        if script == WRITE_CLAIM and json.loads(args[-1])["state"] == "sent":
            raise ConnectionError("private-redis-password")
        return await original(script, numkeys, *args)

    monkeypatch.setattr(store, "eval", evaluate)
    if kind == "admin":
        with pytest.raises(newsletter.HTTPException):
            await dispatch(kind)
    else:
        assert not await dispatch(kind)
    monkeypatch.setattr(store, "eval", original)
    await dispatch(kind)
    assert len(provider.sent) == 1
    assert any(value["state"] == "uncertain" for value in claims(store).values())


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_interrupted_claim_resumes_only_when_explicitly_failed(store, provider, monkeypatch, kind):
    seed_campaign(store, provider)
    original = provider.request

    def request(req):
        if req.method == "GET" and req.url.path.startswith("/v3/emailCampaigns/"):
            if any(value["campaign_id"] for value in claims(store).values()) and any(
                campaign.get("recipients") for campaign in provider.campaigns.values()
            ):
                raise asyncio.CancelledError()
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    with pytest.raises(asyncio.CancelledError):
        await dispatch(kind)
    saved_id = next(value["campaign_id"] for value in claims(store).values() if value["campaign_id"])
    assert not provider.sent
    monkeypatch.setattr(provider, "request", original)
    await dispatch(kind)
    assert len(provider.sent) == int(kind == "admin")
    assert any(value["state"] == ("sent" if kind == "admin" else "claimed")
               and value["campaign_id"] == saved_id for value in claims(store).values())


async def test_claim_fencing_prevents_stale_owner_dispatch(store, provider):
    async with newsletter_lock(store) as lease:
        claim = await DispatchClaim.acquire(lease, "admin:1", 1)
        store.pending[LOCK_KEY] = "replacement-owner"
        with pytest.raises(newsletter_audience_error()) as caught:
            await claim.send(lambda: None, {}, "provider_unavailable")
        assert caught.value.reason == "lock_unavailable"
    assert claims(store)["admin:1"]["state"] == "claimed"
    assert not provider.sent


def newsletter_audience_error():
    from services.newsletter_audience import AudienceUnavailable
    return AudienceUnavailable


async def test_dispatch_status_is_authenticated_counts_only_and_read_only(store, provider, caplog):
    seed_campaign(store, provider)
    await dispatch("admin")
    store.hashes[CLAIMS_KEY]["private-request-id"] = json.dumps({"state": "uncertain", "campaign_id": 999})
    baseline = list(store.mutations)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        assert (await client.get("/api/v1/admin/newsletter/dispatch-status")).status_code == 403
        response = await client.get("/api/v1/admin/newsletter/dispatch-status", headers={
            "Authorization": "Bearer synthetic-admin-key",
        })
    assert response.json() == {"claimed": 0, "sent": 1, "failed": 0, "uncertain": 1}
    assert store.mutations == baseline
    assert all(value not in response.text + caplog.text for value in (EMAIL, "private-request-id", "999"))


async def test_legacy_dispatch_status_counts_shared_uncertainty_once(store):
    store.hashes[CLAIMS_KEY].update({
        "monthly:2026-10:el": json.dumps({"state": "failed", "campaign_id": 999}),
        "admin:999": json.dumps({"state": "uncertain", "campaign_id": 999}),
    })
    before = list(store.mutations)
    assert await dispatch_status(store) == {"claimed": 0, "sent": 0, "failed": 0, "uncertain": 1}
    assert store.mutations == before


async def test_new_month_is_a_distinct_dispatch_claim(store, provider, monkeypatch):
    seed_campaign(store, provider)
    assert await dispatch("monthly")
    now = datetime.now(timezone.utc)

    class NextMonth(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(year=now.year + 1) if now.month == 12 else now.replace(month=now.month + 1, day=1)

    monkeypatch.setattr(newsletter_service, "datetime", NextMonth)
    assert await dispatch("monthly")
    assert provider.delivered == [{EMAIL}, {EMAIL}]


async def test_monthly_rejection_then_admin_timeout_blocks_scheduler_retry(store, provider, monkeypatch):
    seed_campaign(store, provider)
    original = provider.request
    attempts = []

    def request(req):
        if req.url.path.endswith("/sendNow"):
            attempts.append(req.url.path)
            if len(attempts) == 1:
                return httpx.Response(400)
            raise httpx.ReadTimeout("lost send acknowledgement", request=req)
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    assert not await dispatch("monthly")
    campaign_id = next(value["campaign_id"] for value in claims(store).values()
                       if value["campaign_id"] is not None)
    req = newsletter_admin.SendRequest(campaign_id=campaign_id, confirm=True)
    with pytest.raises(newsletter.HTTPException):
        await newsletter_admin.newsletter_send(req, _auth=True)
    before = list(provider.writes)
    for _ in range(2):
        assert not await dispatch("monthly")
        assert (await newsletter_admin.newsletter_send(req, _auth=True))["reason"] == "dispatch_uncertain"
    assert len(attempts) == 2
    assert provider.writes == before
    assert not provider.delivered
    assert await dispatch_status(store) == {"claimed": 0, "sent": 0, "failed": 1, "uncertain": 1}


@pytest.mark.parametrize("state", ["claimed", "uncertain", "sent"])
@pytest.mark.parametrize("legacy", [False, True])
async def test_existing_monthly_campaign_claim_blocks_admin_alias(store, provider, state, legacy):
    seed_campaign(store, provider)
    if legacy:
        store.hashes[CLAIMS_KEY]["monthly:2026-10:el"] = json.dumps({"state": state, "campaign_id": 1})
    else:
        async with newsletter_lock(store) as lease:
            claim = await DispatchClaim.acquire(lease, "monthly:2026-10:el", 1)
            if state != "claimed":
                await claim.write(state)
    before = list(provider.writes)
    result = await dispatch("admin")
    assert result["sent"] == 0
    assert result["reason"] == {
        "claimed": "dispatch_claimed", "uncertain": "dispatch_uncertain", "sent": "already_sent",
    }[state]
    assert provider.writes == before
    assert not provider.delivered


@pytest.mark.parametrize("state", ["claimed", "uncertain", "sent"])
@pytest.mark.parametrize("legacy", [False, True])
async def test_existing_admin_campaign_claim_blocks_monthly_retry(store, provider, state, legacy):
    seed_campaign(store, provider)
    month_key = f"monthly:{datetime.now(timezone.utc):%Y-%m}:el"
    async with newsletter_lock(store) as lease:
        monthly = await DispatchClaim.acquire(lease, month_key, 1)
        await monthly.write("failed")
        admin = await DispatchClaim.acquire(lease, "admin:1", 1)
        if state != "claimed":
            await admin.write(state)
    if legacy:
        store.hashes[CLAIMS_KEY].pop(f"{CAMPAIGN_PREFIX}1")
        for key, record in claims(store).items():
            record.pop("fence", None)
            store.hashes[CLAIMS_KEY][key] = json.dumps(record)
    before = list(provider.writes)
    assert await dispatch("monthly") is (state == "sent")
    assert provider.writes == before
    assert not provider.delivered


async def test_reclaimed_failed_campaign_fences_stale_token_under_same_lease(store, provider):
    async with newsletter_lock(store) as lease:
        old = await DispatchClaim.acquire(lease, "admin:1", 1)
        await replace(old).write("failed")
        current = await DispatchClaim.acquire(lease, "admin:1", 1)
        assert current.fence > old.fence
        before = dict(store.hashes[CLAIMS_KEY])
        with pytest.raises(newsletter_audience_error()):
            await old.send(lambda: pytest.fail("stale token reached sendNow"), {}, "provider_unavailable")
        assert store.hashes[CLAIMS_KEY] == before


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_campaign_fence_is_checked_atomically_at_send_gate(store, provider, monkeypatch, kind):
    seed_campaign(store, provider)
    original = store.eval
    replaced = None

    async def evaluate(script, numkeys, *args):
        nonlocal replaced
        if script == WRITE_CLAIM and json.loads(args[-1])["state"] == "uncertain":
            campaign_key = args[5]
            replacement = {**json.loads(store.hashes[CLAIMS_KEY][campaign_key]), "fence": 999}
            replaced = json.dumps(replacement)
            # Only the shared campaign token changes; the lease and logical
            # record still match. The atomic gate must reject this worker.
            store.hashes[CLAIMS_KEY][campaign_key] = replaced
        return await original(script, numkeys, *args)

    monkeypatch.setattr(store, "eval", evaluate)
    if kind == "admin":
        with pytest.raises(newsletter.HTTPException):
            await dispatch(kind)
    else:
        assert not await dispatch(kind)
    assert replaced is not None and replaced in store.hashes[CLAIMS_KEY].values()
    assert not any(req.url.path.endswith("/sendNow") for req in provider.writes)
    assert not provider.delivered


@pytest.mark.parametrize("campaign_id", [0, -1])
def test_send_request_rejects_non_positive_campaign_ids(campaign_id):
    from pydantic import ValidationError
    from routers.newsletter_admin import SendRequest

    with pytest.raises(ValidationError):
        SendRequest(campaign_id=campaign_id)


@pytest.mark.parametrize("campaign_id", [0, -5, True])
def test_claim_acquire_rejects_invalid_campaign_ids_without_writing(campaign_id):
    import asyncio
    from services.newsletter_audience import AudienceUnavailable
    from services.newsletter_claims import DispatchClaim

    class _NoStoreLease:
        store = None  # any write attempt would fail loudly

    with pytest.raises(AudienceUnavailable):
        asyncio.run(DispatchClaim.acquire(_NoStoreLease(), "admin:test", campaign_id))
