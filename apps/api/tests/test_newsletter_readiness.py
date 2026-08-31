"""No network, mail, Redis writes or contact mutation in readiness tests."""
import json
import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from routers import newsletter, newsletter_admin
from services.newsletter_consent import (
    TOPICS, classify_contact, confirmation_payload, readiness_summary,
)


NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
EMAIL = "consent+test@example.org"


def consent(**changes: object) -> str:
    data = {"email": EMAIL, "subscriber_type": "citizens", "language": "el", "frequency": "monthly",
            "topics": dict.fromkeys(TOPICS, True), "consent_schema": 2,
            "requested_at": "2026-08-31T10:00:00+00:00", "confirmed_at": "2026-08-31T11:00:00+00:00",
            "confirmation_method": "double_opt_in"}
    return json.dumps({**data, **changes})


def provider(**changes: object) -> dict:
    return {"email": EMAIL, "emailBlacklisted": False, "listIds": [], "listUnsubscribed": [], **changes}


def test_fresh_consent_still_cannot_enter_ungated_campaign_audience() -> None:
    assert classify_contact(EMAIL, consent(), 200, provider(), 2, NOW) == (
        "HOLD", ["campaign_preferences_not_enforced"])
    summary = readiness_summary([classify_contact(EMAIL, consent(), 200, provider(), 2, NOW)], 1, True)
    assert summary["proposed_writes"] == 0
    assert summary["delivery_ready"] is False


@pytest.mark.parametrize("status,reason", [(404, "provider_missing_history"), (429, "provider_lookup_failed"),
                                          (500, "provider_lookup_failed"), (None, "provider_lookup_failed")])
def test_missing_or_failed_provider_state_never_authorizes_create(status: int | None, reason: str) -> None:
    assert classify_contact(EMAIL, consent(), status, None, 2, NOW) == ("HOLD", [reason])


@pytest.mark.parametrize("contact", [provider(emailBlacklisted=True), provider(listUnsubscribed=[2]),
                                    provider(emailBlacklisted=True, listIds=[2])])
def test_suppression_excludes_even_current_list_members(contact: dict) -> None:
    assert classify_contact(EMAIL, consent(), 200, contact, 2, NOW) == ("EXCLUDE", ["provider_suppressed"])


@pytest.mark.parametrize("contact", [None, [], provider(email="other@example.org"), provider(emailBlacklisted=None),
                                    provider(listUnsubscribed=None), provider(listIds=[True]), provider(listIds="2")])
def test_incomplete_state_is_not_inferred(contact: object) -> None:
    assert classify_contact(EMAIL, consent(), 200, contact, 2, NOW) == ("HOLD", ["provider_state_incomplete"])


@pytest.mark.parametrize("change", [{"frequency": "weekly"}, {"language": "en"}, {"subscriber_type": "press"},
                                    {"topics": {**dict.fromkeys(TOPICS, True), "new_proposals": False}}])
def test_preferences_are_not_coerced(change: dict) -> None:
    raw = consent(**change)
    action, reasons = classify_contact(EMAIL, raw, 200, provider(), 2, NOW)
    assert action == "HOLD"
    assert "unsupported_delivery_profile" in reasons
    assert all(json.loads(raw)[key] == value for key, value in change.items())


def test_oneoff_operator_test_is_not_general_consent() -> None:
    assert classify_contact(EMAIL, consent(topics=dict.fromkeys(TOPICS, False)), 200, provider(listIds=[2]), 2, NOW) == (
        "EXCLUDE", ["no_topics_selected"])


@pytest.mark.parametrize("raw", ["not-json", "[]", "null", consent(email="wrong@example.org"),
                                 consent(topics={"active_votes": True}), consent(topics=dict.fromkeys(TOPICS, "true"))])
def test_invalid_records_excluded(raw: str) -> None:
    assert classify_contact(EMAIL, raw, None, None, 2, NOW)[0] == "EXCLUDE"


@pytest.mark.parametrize("change", [{"confirmed_at": None}, {"requested_at": None}, {"consent_schema": 1},
                                    {"confirmation_method": "import"}, {"confirmed_at": "2026-08-31T11:00:00"},
                                    {"confirmed_at": "2026-09-01T11:00:00+00:00"},
                                    {"requested_at": "2026-08-28T11:00:00+00:00"}])
def test_missing_or_impossible_evidence_not_backfilled(change: dict) -> None:
    action, reasons = classify_contact(EMAIL, consent(**change), 404, None, 2, NOW)
    assert action == "HOLD"
    assert "missing_confirmation_evidence" in reasons


def test_existing_membership_is_keep_not_approval() -> None:
    action, reasons = classify_contact(EMAIL, consent(confirmed_at=None), 200, provider(listIds=[2, 9]), 2, NOW)
    assert action == "KEEP"
    assert "missing_confirmation_evidence" in reasons
    assert "existing_list_member" in reasons


def test_fresh_confirmation_preserves_request_evidence_and_preferences() -> None:
    original = json.loads(consent())
    original.pop("confirmed_at")
    original.pop("confirmation_method")
    confirmed = json.loads(confirmation_payload(original, NOW))
    assert {key: confirmed[key] for key in original} == original
    assert confirmed["confirmed_at"] == NOW.isoformat()
    assert "confirmed_at" not in original


@pytest.mark.parametrize("failure", ["404", "timeout", "invalid_json", "success"])
async def test_endpoint_get_only_encoded_identity_private_errors_and_aggregate_output(
    monkeypatch: pytest.MonkeyPatch, failure: str, caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="httpx")
    store = MagicMock()
    store.eval_ro = AsyncMock(return_value=[1, EMAIL, consent()])
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter_admin, "BREVO_API_KEY", "synthetic-test-key")
    requests = []

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert b"consent%2Btest%40example.org" in request.url.raw_path
        if failure == "timeout":
            raise httpx.ReadTimeout("private-email@example.org", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text="private-email@example.org")
        return httpx.Response(404, text="private-email@example.org") if failure == "404" else httpx.Response(200, json=provider())

    real_client = httpx.AsyncClient
    monkeypatch.setattr(newsletter_admin.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(transport), **kw))
    result = await newsletter_admin.newsletter_readiness(_auth=True)
    assert result["complete"] is True
    assert result["actions"] == {"KEEP": 0, "HOLD": 1, "EXCLUDE": 0}
    assert result["proposed_writes"] == 0
    assert len(requests) == 1
    assert "@" not in json.dumps(result)
    assert "synthetic-test-key" not in json.dumps(result)
    assert {call[0] for call in store.method_calls} == {"eval_ro"}
    assert "example.org" not in caplog.text
    assert "synthetic-test-key" not in caplog.text


async def test_total_timeout_cancels_reads_without_partial_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MagicMock()
    store.eval_ro = AsyncMock(return_value=[1, EMAIL, consent()])
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter_admin, "BREVO_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(newsletter_admin, "READINESS_TIMEOUT_SECONDS", 0.01)
    cancelled = []

    async def delayed_get(request: httpx.Request) -> httpx.Response:
        try:
            await asyncio.sleep(5)
            return httpx.Response(200, json=provider())
        finally:
            cancelled.append(True)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(newsletter_admin.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(delayed_get), **kw))
    with pytest.raises(HTTPException) as exc:
        await newsletter_admin.newsletter_readiness(_auth=True)
    assert exc.value.status_code == 504
    assert cancelled == [True]


async def test_snapshot_limit_stops_before_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MagicMock()
    store.eval_ro = AsyncMock(return_value=[101])
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter_admin.httpx, "AsyncClient", MagicMock(side_effect=AssertionError("Unexpected provider")))
    result = await newsletter_admin.newsletter_readiness(_auth=True)
    assert result["complete"] is False
    assert result["evaluated_count"] == result["proposed_writes"] == 0


@pytest.mark.parametrize("key,raw,action", [("", consent(), "HOLD"), ("synthetic-key", "invalid-json", "EXCLUDE")])
async def test_invalid_or_unconfigured_records_never_call_provider(
    monkeypatch: pytest.MonkeyPatch, key: str, raw: str, action: str,
) -> None:
    store = MagicMock()
    store.eval_ro = AsyncMock(return_value=[1, EMAIL, raw])
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter_admin, "BREVO_API_KEY", key)

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No provider request permitted")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(newsletter_admin.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(unexpected_request), **kw))
    result = await newsletter_admin.newsletter_readiness(_auth=True)
    assert result["actions"][action] == 1
    assert result["proposed_writes"] == 0


async def test_readiness_requires_existing_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    store = AsyncMock(side_effect=AssertionError("Unauthorized read"))
    monkeypatch.setattr(newsletter, "_get_redis", store)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")
    app = FastAPI()
    app.include_router(newsletter_admin.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            response = await client.get("/api/v1/admin/newsletter/readiness", headers=headers)
            assert response.status_code == 403
    store.assert_not_awaited()
