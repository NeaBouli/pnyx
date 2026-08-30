"""Mock-only consent boundaries for GH261's read-only delivery investigation.

These protect existing DOI behavior; they do not assert delivery or suppression
propagation that the current implementation does not provide.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from routers import newsletter, newsletter_admin


@pytest.fixture
def consent_redis(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    store = MagicMock()
    store.get = AsyncMock(return_value=None)
    store.hget = AsyncMock(return_value=None)
    store.hset = AsyncMock()
    store.setex = AsyncMock()
    store.delete = AsyncMock()
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
    raw = json.dumps({"email": "consent@example.org", "frequency": frequency,
                      "language": language, "subscriber_type": "citizens",
                      "topics": {"active_votes": False, "vote_results": True}})
    consent_redis.get.return_value = raw
    result = await newsletter.confirm_subscription("synthetic-token")
    assert result.status_code == 200
    consent_redis.hset.assert_awaited_once_with("newsletter:confirmed", "consent@example.org", raw)
    consent_redis.delete.assert_awaited_once_with("newsletter:pending:synthetic-token")


async def test_expired_confirmation_does_not_activate_any_contact(consent_redis: MagicMock) -> None:
    result = await newsletter.confirm_subscription("expired-synthetic-token")
    assert result.status_code == 410
    consent_redis.hset.assert_not_awaited()
    consent_redis.delete.assert_not_awaited()


async def test_sequential_confirmation_replay_is_rejected(consent_redis: MagicMock) -> None:
    consent_redis.get.side_effect = [json.dumps({"email": "consent@example.org"}), None]
    assert (await newsletter.confirm_subscription("synthetic-token")).status_code == 200
    assert (await newsletter.confirm_subscription("synthetic-token")).status_code == 410
    consent_redis.hset.assert_awaited_once()
    # This is a sequential check, not a claim of atomic concurrent consumption.


async def test_confirmation_write_failure_keeps_pending_token(
    consent_redis: MagicMock,
) -> None:
    consent_redis.get.return_value = json.dumps({"email": "consent@example.org"})
    consent_redis.hset.side_effect = RuntimeError("synthetic storage failure")
    with pytest.raises(RuntimeError, match="synthetic storage failure"):
        await newsletter.confirm_subscription("synthetic-token")
    consent_redis.delete.assert_not_awaited()


async def test_optional_listmonk_failure_does_not_erase_confirmed_consent(
    consent_redis: MagicMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = json.dumps({"email": "consent@example.org", "frequency": "monthly", "language": "el"})
    consent_redis.get.return_value = raw
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "synthetic-test-password")
    mocked = AsyncMock(side_effect=RuntimeError("synthetic Listmonk outage"))
    monkeypatch.setattr(newsletter, "_listmonk_request", mocked)
    assert (await newsletter.confirm_subscription("synthetic-token")).status_code == 200
    consent_redis.hset.assert_awaited_once_with("newsletter:confirmed", "consent@example.org", raw)
    mocked.assert_awaited_once()


async def test_existing_confirmation_does_not_replace_preferences_or_send(
    consent_redis: MagicMock,
) -> None:
    consent_redis.hget.return_value = json.dumps({"frequency": "monthly", "language": "el"})
    result = await newsletter.subscribe(newsletter.SubscribeRequest(email="consent@example.org"))
    assert result["message"] == "Already subscribed."
    consent_redis.setex.assert_not_awaited()
    consent_redis.hset.assert_not_awaited()


@pytest.mark.parametrize("field,value", [("frequency", "daily"), ("language", "xx"),
                                        ("subscriber_type", "unknown")])
async def test_invalid_preferences_never_send_or_store(
    consent_redis: MagicMock, field: str, value: str,
) -> None:
    req = newsletter.SubscribeRequest(email="consent@example.org", **{field: value})
    with pytest.raises(HTTPException) as exc:
        await newsletter.subscribe(req)
    assert exc.value.status_code == 400
    consent_redis.setex.assert_not_awaited()
    consent_redis.hset.assert_not_awaited()


async def test_admin_send_requires_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncMock(side_effect=AssertionError("Unexpected provider call"))
    telegram = AsyncMock(side_effect=AssertionError("Unexpected Telegram call"))
    monkeypatch.setattr(newsletter_admin, "_brevo_request", provider)
    monkeypatch.setattr(newsletter_admin, "tg_send", telegram)
    with pytest.raises(HTTPException) as exc:
        await newsletter_admin.newsletter_send(newsletter_admin.SendRequest(campaign_id=123, confirm=False), _auth=True)
    assert exc.value.status_code == 400
    provider.assert_not_awaited()
    telegram.assert_not_awaited()
