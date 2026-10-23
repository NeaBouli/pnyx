"""Provider writes that settle after authorization cannot mutate an isolated target."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from routers import newsletter, newsletter_admin
from services import newsletter_audience, newsletter_dispatch, newsletter_service
from services.newsletter_lock import NewsletterLockUnavailable
from services.newsletter_consent import (
    CONFIRMED_KEY, SUPPRESSED_KEY, BREVO_ADD_UNSETTLED_KEY, TOPICS, WITHDRAWAL_PENDING_KEY,
)
from tests.test_newsletter_audiences import (
    provider, store, save, seed_campaign, dispatch, blocked_dispatch, CampaignPlan, consent, EMAIL,
)


@pytest.mark.parametrize("kind", ["admin", "monthly"])
@pytest.mark.parametrize("race", ["withdrawal", "preferences"])
async def test_uncertain_write_commits_after_final_authorization_without_expanding_target(
    store, provider, monkeypatch, kind, race,
):
    seed_campaign(store, provider)
    older = "older-sync@example.org"
    save(store, provider, consent(older, language="en"))
    original = provider.request
    delayed = []

    async def request(req):
        if req.method == "POST" and req.url.path == "/v3/contacts" and race == "preferences":
            delayed.append(req)
            raise httpx.ReadTimeout("private-provider-payload", request=req)
        if req.url.path.endswith("/sendNow") and not delayed == ["committed"]:
            # This executes after the last consent, list and lease checks.
            if race == "withdrawal":
                provider.contacts[older]["listIds"].append(newsletter_service.LIST_ID)
                provider.contacts[older]["attributes"]["NL_LANGUAGE"] = "el"
            else:
                for write in delayed:
                    original(write)
            delayed[:] = ["committed"]
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    if race == "withdrawal":
        # Pre-existing membership + uncertain preference write + successful removal.
        store.hashes[BREVO_ADD_UNSETTLED_KEY][older] = "uncertain"
        assert await newsletter._withdraw_subscription(store, older, "unsubscribed")
        assert older in store.hashes[SUPPRESSED_KEY]
        assert newsletter_service.LIST_ID not in provider.contacts[older]["listIds"]
    else:
        def preference(language):
            return newsletter_admin.PreferencesRequest(
                email=older, language=language, frequency="monthly", topics=consent(older)["topics"],
            )
        assert (await newsletter_admin.newsletter_preferences(preference("el"), _auth=True))["failed"] == 1
        assert (await newsletter_admin.newsletter_preferences(preference("en"), _auth=True))["updated"] == 1
        # Matching current attributes used to incorrectly settle the older Greek update.
        assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["already_present"] == 2
        assert delayed
    await dispatch(kind)
    assert delayed == ["committed"]
    assert provider.delivered[0] == {EMAIL}
    assert older not in provider.delivered[0]
    assert provider.deleted
    assert all(list_id == newsletter_service.LIST_ID for list_id in provider.lists)


@pytest.mark.parametrize("kind", ["admin", "monthly"])
@pytest.mark.parametrize("failure", ["create", "add", "partial_add", "empty_add", "members", "extra", "duplicate", "count", "campaign", "send", "lease"])
async def test_dispatch_failure_aborts_and_deletes_temporary_list(store, provider, monkeypatch, caplog, kind, failure):
    seed_campaign(store, provider)
    caplog.set_level(logging.DEBUG)
    original = provider.request

    def request(req):
        path = req.url.path
        if failure == "create" and req.method == "POST" and path == "/v3/contacts/lists":
            return httpx.Response(503, text=EMAIL + " private-provider-payload")
        if path.endswith("/contacts/add"):
            if failure == "add":
                raise httpx.ReadTimeout(EMAIL, request=req)
            if failure == "partial_add":
                original(req)
                return httpx.Response(201, json={"contacts": {"failure": [EMAIL]}})
            if failure == "empty_add":
                return httpx.Response(201, json={})
            if failure == "lease":
                from services.newsletter_lock import LOCK_KEY
                store.pending[LOCK_KEY] = "another-worker"
        if req.method == "GET" and path.endswith("/contacts") and len(provider.writes) > 1:
            if failure == "members":
                return httpx.Response(502, text=EMAIL)
            if failure in {"extra", "duplicate", "count"}:
                response = original(req).json()
                response["contacts"].append({"email": EMAIL if failure == "duplicate" else "extra@example.org"})
                if failure != "count":
                    response["count"] += 1
                return httpx.Response(200, json=response)
        if failure == "campaign" and path == ("/v3/emailCampaigns/1" if kind == "admin" else "/v3/emailCampaigns") and req.method != "GET":
            return httpx.Response(503, text=EMAIL)
        if failure == "send" and path.endswith("/sendNow"):
            return httpx.Response(503, text=EMAIL)
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    await blocked_dispatch(kind, "lock_unavailable" if failure == "lease" else (
        "audience_mismatch" if failure in {"empty_add", "extra", "duplicate", "count"} else
        "audience_unavailable" if failure == "campaign" and kind == "admin" or failure == "send" and kind == "admin" else "provider_unavailable"
    ))
    assert not provider.sent
    assert len(provider.deleted) == int(failure != "create")
    assert set(provider.lists) == {newsletter_service.LIST_ID}
    assert EMAIL not in caplog.text and "private-provider-payload" not in caplog.text


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_queued_withdrawal_before_send_aborts_and_deletes_target(store, provider, monkeypatch, kind):
    seed_campaign(store, provider)
    original = provider.request
    queued = False

    async def request(req):
        nonlocal queued
        response = original(req)
        if not queued and (req.method == "PUT" or req.method == "POST" and req.url.path == "/v3/emailCampaigns"):
            queued = True
            # A different task cannot acquire the lock, but records durable intent.
            task = asyncio.create_task(newsletter._withdraw_subscription(store, EMAIL, "unsubscribed"))
            with pytest.raises(NewsletterLockUnavailable):
                await task
        return response

    monkeypatch.setattr(provider, "request", request)
    await blocked_dispatch(kind, "audience_mismatch")
    assert queued and store.hashes[WITHDRAWAL_PENDING_KEY] == {EMAIL: "unsubscribed"}
    assert not provider.sent and provider.deleted
    monkeypatch.setattr(provider, "request", original)
    assert await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
    assert not store.hashes[WITHDRAWAL_PENDING_KEY]


@pytest.mark.parametrize("size", [501, 10_000, 10_001])
async def test_batches_pagination_and_contact_bound(store, provider, size):
    for index in range(size):
        save(store, provider, consent(f"fixture{index}@example.org"))
    if size > 10_000:
        provider.campaigns[1] = {"tag": CampaignPlan().tag}
        await blocked_dispatch("admin", "audience_limit_exceeded")
        assert not provider.writes
        return
    provider.campaigns[1] = {"tag": CampaignPlan().tag}
    result = await dispatch("admin")
    assert result["sent"] == size
    assert provider.delivered == [set(store.hashes[CONFIRMED_KEY])]
    batches = [json.loads(req.content)["emails"] for req in provider.writes if req.url.path.endswith("/contacts/add")]
    assert sum(map(len, batches)) == size
    assert max(map(len, batches)) <= 150
    assert provider.deleted


async def test_cleanup_discovers_only_owned_lists_older_than_24h_and_retries(store, provider, monkeypatch, caplog):
    now = int(datetime.now(timezone.utc).timestamp())
    def item(list_id, age, name=None):
        return {"id": list_id, "folderId": 1, "name": name or f"{newsletter_dispatch.TEMP_PREFIX}{now-age}-{uuid4().hex}"}
    provider.lists.update({
        100: item(100, 86401), 101: item(101, 86402), 102: item(102, 86000),
        103: item(103, 100000, "operator-list"), 104: item(104, 100000, "newsletter-tmp-v1-1234567890-invalid"),
    })
    original = provider.request
    def request(req):
        if req.method == "DELETE" and req.url.path.endswith("/101"):
            return httpx.Response(503, text=EMAIL)
        return original(req)
    monkeypatch.setattr(provider, "request", request)
    assert await newsletter_dispatch.cleanup_temporary_campaign_lists() == {"selected": 2, "deleted": 1, "failed": 1}
    assert set(provider.lists) == {newsletter_service.LIST_ID, 101, 102, 103, 104}
    monkeypatch.setattr(provider, "request", original)
    assert await newsletter_dispatch.cleanup_temporary_campaign_lists() == {"selected": 1, "deleted": 1, "failed": 0}
    assert await newsletter_dispatch.cleanup_temporary_campaign_lists() == {"selected": 0, "deleted": 0, "failed": 0}
    assert EMAIL not in caplog.text
    assert not provider.sent


async def test_delete_failure_after_acceptance_does_not_retry_send_and_cleanup_recovers(store, provider, monkeypatch, caplog):
    seed_campaign(store, provider)
    original = provider.request
    def request(req):
        if req.method == "DELETE":
            return httpx.Response(503, text=EMAIL)
        return original(req)
    monkeypatch.setattr(provider, "request", request)
    assert (await dispatch("admin"))["sent"] == 1
    assert len(provider.sent) == 1
    assert "temporary_list_cleanup_failed" in caplog.text and EMAIL not in caplog.text
    for list_id in set(provider.lists) - {newsletter_service.LIST_ID}:
        provider.lists[list_id]["name"] = f"{newsletter_dispatch.TEMP_PREFIX}{int(datetime.now(timezone.utc).timestamp())-86401}-{uuid4().hex}"
    monkeypatch.setattr(provider, "request", original)
    assert (await newsletter_dispatch.cleanup_temporary_campaign_lists())["deleted"] == 1
    assert len(provider.sent) == 1


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_enrollment_lists_and_attributes_do_not_authorize_recipients(store, provider, kind):
    seed_campaign(store, provider)
    # Selected consent remains selected despite stale attributes and no enrollment membership.
    provider.contacts[EMAIL]["attributes"] = {}
    provider.contacts[EMAIL]["listIds"] = []
    provider.enroll(consent("provider-only@example.org"))
    await dispatch(kind)
    assert provider.delivered == [{EMAIL}]
    assert provider.contacts[EMAIL]["listIds"] == []
    assert provider.contacts["provider-only@example.org"]["listIds"] == [newsletter_service.LIST_ID]


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_cancellation_before_send_deletes_list_under_lease(store, provider, monkeypatch, kind):
    from services.newsletter_lock import LOCK_KEY
    seed_campaign(store, provider)
    original = provider.request
    async def request(req):
        if req.url.path.endswith("/contacts/add"):
            raise asyncio.CancelledError()
        if req.method == "DELETE":
            assert LOCK_KEY in store.pending
        return original(req)
    monkeypatch.setattr(provider, "request", request)
    with pytest.raises(asyncio.CancelledError):
        await dispatch(kind)
    assert not provider.sent and provider.deleted
    assert set(provider.lists) == {newsletter_service.LIST_ID}
    assert LOCK_KEY not in store.pending


async def test_creation_timeout_is_discovered_by_cleanup(store, provider, monkeypatch):
    seed_campaign(store, provider)
    original = provider.request
    def request(req):
        if req.method == "POST" and req.url.path == "/v3/contacts/lists":
            original(req)  # Provider commits the list but loses the response.
            raise httpx.ReadTimeout(EMAIL, request=req)
        return original(req)
    monkeypatch.setattr(provider, "request", request)
    await blocked_dispatch("admin", "provider_unavailable")
    assert not provider.sent and not provider.deleted
    assert len(provider.lists) == 2
    monkeypatch.setattr(provider, "request", original)
    assert (await newsletter_dispatch.cleanup_temporary_campaign_lists())["deleted"] == 0
    for list_id in set(provider.lists) - {newsletter_service.LIST_ID}:
        provider.lists[list_id]["name"] = f"{newsletter_dispatch.TEMP_PREFIX}{int(datetime.now(timezone.utc).timestamp())-86401}-{uuid4().hex}"
    assert (await newsletter_dispatch.cleanup_temporary_campaign_lists())["deleted"] == 1


@pytest.mark.parametrize("size", [0, 49, 50, 51, 99, 100, 101, 501])
async def test_cleanup_reads_all_pages_before_deleting(store, provider, monkeypatch, size):
    now = int(datetime.now(timezone.utc).timestamp())
    for list_id in range(1000, 1000 + size):
        provider.lists[list_id] = {"id": list_id, "folderId": 1,
                                  "name": f"{newsletter_dispatch.TEMP_PREFIX}{now-86401}-{uuid4().hex}"}
    original = provider.request
    pages = []

    def request(req):
        if req.method == "GET" and req.url.path == "/v3/contacts/lists":
            assert not provider.deleted  # Deletion must not shift later pages.
            assert int(req.url.params["limit"]) == 50
            pages.append(int(req.url.params["offset"]))
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    assert await newsletter_dispatch.cleanup_temporary_campaign_lists() == {"selected": size, "deleted": size, "failed": 0}
    assert pages == list(range(0, size + 1, 50))  # Includes the enrollment list.
    assert len(set(provider.deleted)) == size
    assert set(provider.lists) == {newsletter_service.LIST_ID}


async def test_cleanup_page_failure_is_reported_and_retry_deletes_every_leftover(store, provider, monkeypatch):
    now = int(datetime.now(timezone.utc).timestamp())
    for list_id in range(1000, 1100):
        provider.lists[list_id] = {"id": list_id, "folderId": 1,
                                  "name": f"{newsletter_dispatch.TEMP_PREFIX}{now-86401}-{uuid4().hex}"}
    original = provider.request

    def request(req):
        if (req.method == "GET" and req.url.path == "/v3/contacts/lists"
                and req.url.params["offset"] == "50"):
            return httpx.Response(503, text=EMAIL + " private-provider-token")
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    with pytest.raises(newsletter_audience.AudienceUnavailable) as caught:
        await newsletter_dispatch.cleanup_temporary_campaign_lists()
    assert caught.value.reason == "provider_unavailable"
    assert EMAIL not in str(caught.value)
    assert not provider.deleted
    monkeypatch.setattr(provider, "request", original)
    assert await newsletter_dispatch.cleanup_temporary_campaign_lists() == {"selected": 100, "deleted": 100, "failed": 0}
    assert set(provider.lists) == {newsletter_service.LIST_ID}


async def test_membership_adds_are_idempotent_and_each_dispatch_uses_new_list(store, provider, monkeypatch):
    seed_campaign(store, provider)
    original = provider.request
    def request(req):
        if req.url.path.endswith("/contacts/add"):
            original(req)  # Simulate replay of an identical batch.
        return original(req)
    monkeypatch.setattr(provider, "request", request)
    for campaign_id in (1, 2):
        provider.campaigns[campaign_id] = {"tag": CampaignPlan().tag}
        assert (await newsletter_admin.newsletter_send(
            newsletter_admin.SendRequest(campaign_id=campaign_id, confirm=True), _auth=True,
        ))["sent"] == 1
    assert provider.delivered == [{EMAIL}, {EMAIL}]
    assert len(set(provider.deleted)) == 2
    names = [json.loads(req.content)["name"] for req in provider.writes
             if req.method == "POST" and req.url.path == "/v3/contacts/lists"]
    assert len(set(names)) == 2
    assert all(newsletter_dispatch.TEMP_NAME.fullmatch(name) for name in names)


@pytest.mark.parametrize("state", ["withdrawn", "expired", "reconfirm_expiring", "unknown", {}])
async def test_consent_with_inactive_or_unknown_state_never_enters_target(store, provider, state):
    seed_campaign(store, provider)
    save(store, provider, consent("inactive@example.org", consent_state=state))
    await dispatch("admin")
    assert provider.delivered == [{EMAIL}]


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_provider_retaining_old_campaign_targets_aborts(store, provider, monkeypatch, kind):
    seed_campaign(store, provider)
    original = provider.request
    def request(req):
        response = original(req)
        if req.method == "GET" and req.url.path.startswith("/v3/emailCampaigns/"):
            campaign = response.json()
            if "recipients" in campaign:
                campaign["recipients"]["segments"] = [98765]
                return httpx.Response(200, json=campaign)
        return response
    monkeypatch.setattr(provider, "request", request)
    await blocked_dispatch(kind, "audience_mismatch")
    assert not provider.sent and provider.deleted
