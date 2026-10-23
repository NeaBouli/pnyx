"""Durable campaign retries, including lost provider and Redis acknowledgements."""
import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from routers import newsletter, newsletter_admin
from services import newsletter_service
from services.newsletter_claims import CLAIMS_KEY, WRITE_CLAIM, DispatchClaim
from services.newsletter_lock import LOCK_KEY, newsletter_lock
from tests.test_newsletter_audiences import (
    provider, store, seed_campaign, save, consent, dispatch, db, EMAIL,
)
from tests.test_newsletter_delivery_sync import HTTP_CLIENT, application


def claims(store):
    return {key: json.loads(raw) for key, raw in store.hashes[CLAIMS_KEY].items()}


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
async def test_uncertain_send_is_reconciled_without_automatic_resend(store, provider, monkeypatch, kind, failure):
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
            assert result["reason"] == ("already_sent" if failure == "lost_ack" else "dispatch_uncertain")
        else:
            assert result is (failure == "lost_ack")
    assert attempts == 1
    assert len(provider.sent) == int(failure == "lost_ack")
    assert any(value["state"] == ("sent" if failure == "lost_ack" else "uncertain")
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
    assert any(value["state"] == "sent" for value in claims(store).values())


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_crash_before_send_resumes_persisted_campaign(store, provider, monkeypatch, kind):
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
    assert len(provider.sent) == 1
    assert any(value["state"] == "sent" and value["campaign_id"] == saved_id for value in claims(store).values())


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
