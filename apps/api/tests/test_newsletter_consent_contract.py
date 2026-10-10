"""Mock-only consent boundaries for GH261's guarded confirmation flow.

These protect existing DOI behavior; they do not assert delivery or suppression
propagation that the current implementation does not provide.
"""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from routers import newsletter, newsletter_admin
from services.newsletter_consent import CONFIRM_ONCE, classify_contact, readiness_summary


def _request() -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host="203.0.113.10"), headers={})


@pytest.fixture
def consent_redis(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Keep consent tests offline; fail immediately on an unexpected HTTP client."""
    store = MagicMock()
    store.get = AsyncMock(return_value=None)
    store.hget = AsyncMock(return_value=None)
    store.hset = AsyncMock()
    store.setex = AsyncMock()
    store.delete = AsyncMock()
    store.eval = AsyncMock(return_value=1)
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    # Network is forbidden even if a future refactor adds a provider call.
    monkeypatch.setattr(newsletter.httpx, "AsyncClient",
                        MagicMock(side_effect=AssertionError("Unexpected network client")))
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    return store


@pytest.mark.parametrize("frequency,language", [("weekly", "el"), ("monthly", "en")])
async def test_confirmation_preserves_original_preferences(
    consent_redis: MagicMock, frequency: str, language: str,
) -> None:
    """A DOI confirmation retains all choices and timestamps only this click."""
    raw = json.dumps({"email": "consent@example.org", "frequency": frequency,
                      "language": language, "subscriber_type": "citizens",
                      "topics": {"active_votes": False, "vote_results": True}})
    consent_redis.get.return_value = raw
    result = await newsletter.confirm_subscription("synthetic-token")
    assert result.status_code == 200
    args = consent_redis.eval.await_args.args
    assert args[1:6] == (2, "newsletter:pending:synthetic-token", "newsletter:confirmed", raw, "consent@example.org")
    stored = json.loads(args[6])
    assert {key: stored[key] for key in json.loads(raw)} == json.loads(raw)
    assert datetime.fromisoformat(stored["confirmed_at"]).tzinfo is not None
    assert stored["confirmation_method"] == "double_opt_in"
    assert stored["consent_schema"] == 1  # Legacy pending proof is not upgraded.
    assert "requested_at" not in stored
    consent_redis.hset.assert_not_awaited()
    consent_redis.delete.assert_not_awaited()


@pytest.mark.parametrize("frequency,language,topics", [
    ("weekly", "en", {"new_proposals": True, "active_votes": False,
                       "vote_results": True, "system_news": True, "breaking_news": False}),
    ("monthly", "el", {"new_proposals": True, "active_votes": True,
                        "vote_results": True, "system_news": True, "breaking_news": True}),
])
async def test_subscribe_then_confirm_preserves_schema2_without_delivery_permission(
    consent_redis: MagicMock, monkeypatch: pytest.MonkeyPatch,
    frequency: str, language: str, topics: dict[str, bool],
) -> None:
    """Exercise both routers with their real pending payload, using mail mocks only."""
    requested_at = datetime(2026, 8, 31, 10, tzinfo=timezone.utc)
    confirmed_at = datetime(2026, 8, 31, 11, tzinfo=timezone.utc)
    moments = iter((requested_at, confirmed_at))

    class Clock:
        @classmethod
        def now(cls, tz: object) -> datetime:
            assert tz is timezone.utc
            return next(moments)

    monkeypatch.setattr(newsletter, "datetime", Clock)
    monkeypatch.setattr(newsletter.secrets, "token_urlsafe", lambda size: "synthetic-schema2-token")
    monkeypatch.setattr(newsletter, "BREVO_API_KEY", "synthetic-schema2-key")
    mail = AsyncMock()
    mail.__aenter__.return_value = mail
    mail.post.return_value = SimpleNamespace(status_code=201)
    factory = MagicMock(return_value=mail)
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", factory)
    req = newsletter.SubscribeRequest(
        email="schema2@example.org", name="Synthetic", frequency=frequency, language=language,
        **{f"topic_{name}": enabled for name, enabled in topics.items()},
    )

    assert (await newsletter.subscribe(req, _request()))["success"] is True
    consent_redis.setex.assert_awaited_once()
    pending_key, ttl, raw = consent_redis.setex.await_args.args
    assert pending_key == "newsletter:pending:synthetic-schema2-token"
    assert ttl == 86400
    pending = json.loads(raw)
    assert pending == {
        "consent_schema": 2, "requested_at": requested_at.isoformat(),
        "email": "schema2@example.org", "name": "Synthetic", "subscriber_type": "citizens",
        "frequency": frequency, "language": language, "topics": topics,
    }
    assert "confirmed_at" not in pending
    assert consent_redis.eval.await_count == 2  # The real signup rate-limit checks.
    mail.post.assert_awaited_once()
    assert mail.post.await_args.args == ("https://api.brevo.com/v3/smtp/email",)
    payload = mail.post.await_args.kwargs["json"]
    assert payload["to"] == [{"email": "schema2@example.org"}]
    assert "synthetic-schema2-token" in payload["htmlContent"]

    consent_redis.get.return_value = raw
    assert (await newsletter.confirm_subscription("synthetic-schema2-token")).status_code == 200
    assert consent_redis.eval.await_count == 3
    args = consent_redis.eval.await_args.args
    assert args[:6] == (CONFIRM_ONCE, 2, pending_key, "newsletter:confirmed", raw, "schema2@example.org")
    confirmed = json.loads(args[6])
    assert {key: confirmed[key] for key in pending} == pending
    assert confirmed["confirmed_at"] == confirmed_at.isoformat()
    assert confirmed["confirmation_method"] == "double_opt_in"
    decision = classify_contact("schema2@example.org", args[6], 200, {
        "email": "schema2@example.org", "emailBlacklisted": False,
        "listIds": [], "listUnsubscribed": [],
    }, 2, confirmed_at)
    assert decision[0] == "HOLD"
    assert "missing_confirmation_evidence" not in decision[1]
    assert "campaign_preferences_not_enforced" in decision[1]
    assert ("unsupported_delivery_profile" in decision[1]) is (frequency == "weekly")
    summary = readiness_summary([decision], 1, True)
    assert summary["proposed_writes"] == 0
    assert summary["delivery_ready"] is False
    # Confirmation records the click but never sends another message or directly mutates consent.
    factory.assert_called_once_with(timeout=10.0)
    consent_redis.hset.assert_not_awaited()
    consent_redis.delete.assert_not_awaited()


async def test_expired_confirmation_does_not_activate_any_contact(consent_redis: MagicMock) -> None:
    """Missing pending state is a rejection, never reconstructed consent."""
    result = await newsletter.confirm_subscription("expired-synthetic-token")
    assert result.status_code == 410
    consent_redis.hset.assert_not_awaited()
    consent_redis.delete.assert_not_awaited()
    consent_redis.eval.assert_not_awaited()


async def test_sequential_confirmation_replay_is_rejected(consent_redis: MagicMock) -> None:
    """Once absent from pending state, a token cannot confirm again sequentially."""
    consent_redis.get.side_effect = [json.dumps({"email": "consent@example.org"}), None]
    assert (await newsletter.confirm_subscription("synthetic-token")).status_code == 200
    assert (await newsletter.confirm_subscription("synthetic-token")).status_code == 410
    consent_redis.eval.assert_awaited_once()


async def test_confirmation_write_failure_keeps_pending_token(
    consent_redis: MagicMock,
) -> None:
    """A failed consent write must not destroy the subscriber's pending proof."""
    consent_redis.get.return_value = json.dumps({"email": "consent@example.org"})
    consent_redis.eval.side_effect = RuntimeError("synthetic storage failure")
    with pytest.raises(RuntimeError, match="synthetic storage failure"):
        await newsletter.confirm_subscription("synthetic-token")
    consent_redis.delete.assert_not_awaited()


async def test_optional_listmonk_failure_does_not_erase_confirmed_consent(
    consent_redis: MagicMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An optional provider outage cannot discard the local confirmation record."""
    raw = json.dumps({"email": "consent@example.org", "frequency": "monthly", "language": "el"})
    consent_redis.get.return_value = raw
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-test-password")
    mocked = AsyncMock(side_effect=RuntimeError("synthetic Listmonk outage"))
    monkeypatch.setattr(newsletter, "_listmonk_request", mocked)
    assert (await newsletter.confirm_subscription("synthetic-token")).status_code == 200
    consent_redis.eval.assert_awaited_once()
    assert json.loads(consent_redis.eval.await_args.args[6])["email"] == "consent@example.org"
    mocked.assert_awaited_once()


@pytest.mark.parametrize("result,expected_status", [(0, 410), (2, 200)])
async def test_concurrent_replay_or_existing_consent_never_reenrolls(
    consent_redis: MagicMock, monkeypatch: pytest.MonkeyPatch, result: int, expected_status: int,
) -> None:
    consent_redis.get.return_value = json.dumps({"email": "consent@example.org"})
    consent_redis.eval.return_value = result
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-test-password")
    provider = AsyncMock(side_effect=AssertionError("Must not reenroll"))
    monkeypatch.setattr(newsletter, "_listmonk_request", provider)
    response = await newsletter.confirm_subscription("synthetic-token")
    assert response.status_code == expected_status
    if result == 2:
        assert "αμετάβλητες" in response.body.decode()
    provider.assert_not_awaited()


async def test_existing_confirmation_does_not_replace_preferences_or_send(
    consent_redis: MagicMock,
) -> None:
    """Repeating signup is not permission to overwrite an existing opt-in."""
    consent_redis.hget.return_value = json.dumps({"frequency": "monthly", "language": "el"})
    result = await newsletter.subscribe(newsletter.SubscribeRequest(email="consent@example.org"), _request())
    assert result["message"] == "Already subscribed."
    consent_redis.setex.assert_not_awaited()
    consent_redis.hset.assert_not_awaited()


@pytest.mark.parametrize("field,value", [("frequency", "daily"), ("language", "xx"),
                                        ("subscriber_type", "unknown")])
async def test_invalid_preferences_never_send_or_store(
    consent_redis: MagicMock, field: str, value: str,
) -> None:
    """Reject unsupported preference values before any mail or consent mutation."""
    req = newsletter.SubscribeRequest(email="consent@example.org", **{field: value})
    with pytest.raises(HTTPException) as exc:
        await newsletter.subscribe(req, _request())
    assert exc.value.status_code == 400
    consent_redis.setex.assert_not_awaited()
    consent_redis.hset.assert_not_awaited()


async def test_admin_send_requires_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unconfirmed admin request has no Brevo or Telegram side effects."""
    provider = AsyncMock(side_effect=AssertionError("Unexpected provider call"))
    telegram = AsyncMock(side_effect=AssertionError("Unexpected Telegram call"))
    monkeypatch.setattr(newsletter_admin, "_brevo_request", provider)
    monkeypatch.setattr(newsletter_admin, "tg_send", telegram)
    with pytest.raises(HTTPException) as exc:
        await newsletter_admin.newsletter_send(newsletter_admin.SendRequest(campaign_id=123, confirm=False), _auth=True)
    assert exc.value.status_code == 400
    provider.assert_not_awaited()
    telegram.assert_not_awaited()
