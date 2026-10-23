"""Campaign selection through the real service and routes, with a mock Brevo only."""
import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote

import httpx
import pytest

from routers import newsletter, newsletter_admin
from services import newsletter_service, newsletter_audience
from services.newsletter_audience import CampaignPlan, AudienceUnavailable
from services.newsletter_consent import (
    CONFIRMED_KEY, SUPPRESSED_KEY, TOPICS, BREVO_ADD_RETRY_KEY, BREVO_REMOVE_RETRY_KEY,
    BREVO_ADD_UNSETTLED_KEY, LISTMONK_ADD_UNSETTLED_KEY, LISTMONK_REMOVE_RETRY_KEY,
    preference_attributes,
)
from tests.test_newsletter_delivery_sync import (
    MemoryRedis, consent, EMAIL, HTTP_CLIENT, ADD_CONTACT, CONTACT_STATUS, REMOVE_CONTACT,
    application, store,
)

AUTH = {"Authorization": "Bearer synthetic-admin-key"}
SEGMENTS = {
    f"{language}:{frequency}:{topic}": index + 1
    for index, (language, frequency, topic) in enumerate(
        (language, frequency, topic) for language in ("el", "en")
        for frequency in ("monthly", "weekly") for topic in ("all", *sorted(TOPICS))
    )
}


class Provider:
    def __init__(self) -> None:
        self.contacts: dict[str, dict[str, Any]] = {}
        self.campaigns: dict[int, dict[str, Any]] = {}
        self.sent: list[dict[str, Any]] = []
        self.writes: list[httpx.Request] = []
        self.extra: list[dict[str, Any]] = []
        self.fail_send = False
        self.lists = {newsletter_service.LIST_ID: {"id": newsletter_service.LIST_ID, "name": "Enrollment", "folderId": 1}}
        self.deleted = []
        self.delivered = []
        self.next_list_id = 100

    def enroll(self, data: dict[str, Any], **changes: Any) -> None:
        email = data["email"]
        self.contacts[email.casefold()] = {
            "email": email, "emailBlacklisted": False, "listUnsubscribed": [],
            "listIds": [newsletter_service.LIST_ID], "attributes": preference_attributes(data), **changes,
        }

    def request(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path).removeprefix("/v3/")
        body = json.loads(request.content) if request.content else {}
        if request.method != "GET":
            self.writes.append(request)
        if path == "contacts/lists":
            if request.method == "POST":
                self.next_list_id += 1
                list_id = self.next_list_id
                self.lists[list_id] = {"id": list_id, **body}
                return httpx.Response(201, json={"id": list_id})
            offset = int(request.url.params["offset"])
            limit = int(request.url.params["limit"])
            assert 0 < limit <= 50
            return httpx.Response(200, json={"lists": list(self.lists.values())[offset:offset + limit], "count": len(self.lists)})
        if path.startswith("contacts/lists/"):
            list_id = int(path.split("/")[2])
            if request.method == "DELETE":
                self.lists.pop(list_id, None)
                self.deleted.append(list_id)
                for contact in self.contacts.values():
                    contact["listIds"] = [value for value in contact["listIds"] if value != list_id]
                return httpx.Response(204)
            if path.endswith("/contacts/add") or path.endswith("/contacts/remove"):
                assert 0 < len(body["emails"]) <= 150
                for email in body["emails"]:
                    contact = self.contacts[email.casefold()]
                    if path.endswith("/add"):
                        contact["listIds"] = sorted(set(contact["listIds"] + [list_id]))
                    else:
                        contact["listIds"] = [value for value in contact["listIds"] if value != list_id]
                return httpx.Response(201, json={"contacts": {"success": body["emails"], "failure": []}})
            if path.endswith("/contacts"):
                contacts = [contact for contact in [*self.contacts.values(), *self.extra] if list_id in contact["listIds"]]
                offset = int(request.url.params["offset"])
                return httpx.Response(200, json={"contacts": contacts[offset:offset + 500], "count": len(contacts)})
            return httpx.Response(200, json=self.lists[list_id])
        if request.method == "GET" and path.startswith("contacts/"):
            contact = self.contacts.get(path.removeprefix("contacts/").casefold())
            return httpx.Response(200, json=contact) if contact else httpx.Response(404)
        if path == "contacts" and request.method == "POST":
            email = body["email"].casefold()
            contact = self.contacts.setdefault(email, {"email": body["email"], "emailBlacklisted": False,
                                                       "listUnsubscribed": [], "listIds": [], "attributes": {}})
            contact["attributes"].update(body["attributes"])
            contact["listIds"] = list(set(contact["listIds"] + body["listIds"]))
            return httpx.Response(204)
        if path == "emailCampaigns":
            campaign_id = len(self.campaigns) + 1
            self.campaigns[campaign_id] = dict(body)
            return httpx.Response(201, json={"id": campaign_id})
        if path.startswith("emailCampaigns/"):
            campaign_id = int(path.split("/")[1])
            if path.endswith("/sendNow"):
                if self.fail_send:
                    return httpx.Response(500, json={"message": EMAIL + " private-token"})
                campaign = dict(self.campaigns[campaign_id])
                assert set(campaign["recipients"]) == {"listIds"}
                assert newsletter_service.LIST_ID not in campaign["recipients"]["listIds"]
                self.delivered.append({email for email, contact in self.contacts.items()
                                       if set(campaign["recipients"]["listIds"]).intersection(contact["listIds"])})
                self.sent.append(campaign)
                self.campaigns[campaign_id]["status"] = "sent"
                return httpx.Response(204)
            if request.method == "PUT":
                self.campaigns[campaign_id].update(body)
                return httpx.Response(204)
            campaign = dict(self.campaigns[campaign_id])
            if "recipients" in campaign:
                campaign["recipients"] = {({"listIds": "lists", "segmentIds": "segments"}.get(key, key)): value
                                          for key, value in campaign["recipients"].items()}
            return httpx.Response(200, json=campaign)
        raise AssertionError(f"Unexpected mock operation: {request.method}")


@pytest.fixture
def provider(store: MemoryRedis, monkeypatch: pytest.MonkeyPatch) -> Provider:
    provider = Provider()
    monkeypatch.setenv("BREVO_NEWSLETTER_SEGMENTS", json.dumps(SEGMENTS))
    monkeypatch.setattr(newsletter_service, "BREVO_API_KEY", "synthetic-key")
    monkeypatch.setattr(newsletter_admin, "BREVO_API_KEY", "synthetic-key")
    monkeypatch.setattr(newsletter_service, "add_contact", ADD_CONTACT)
    monkeypatch.setattr(newsletter_service, "contact_status", CONTACT_STATUS)
    monkeypatch.setattr(newsletter_service, "remove_contact", REMOVE_CONTACT)
    monkeypatch.setattr(newsletter_admin, "tg_send", AsyncMock(return_value=False))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: HTTP_CLIENT(
        **{**kwargs, "transport": httpx.MockTransport(provider.request)},
    ))
    return provider


def save(store: MemoryRedis, provider: Provider, data: dict[str, Any], **provider_changes: Any) -> None:
    store.hashes[CONFIRMED_KEY][data["email"]] = json.dumps(data)
    provider.enroll(data, **provider_changes)


def db() -> MagicMock:
    return MagicMock(scalar=AsyncMock(return_value=0), execute=AsyncMock(return_value=MagicMock(all=lambda: [])))


async def admin_send(plan: CampaignPlan) -> dict[str, int]:
    draft = await newsletter_admin.newsletter_create_draft(newsletter_admin.DraftRequest(
        subject="Campaign subject", html_content="<p>Campaign content</p>", **plan.model_dump(),
    ), _auth=True)
    return await newsletter_admin.newsletter_send(newsletter_admin.SendRequest(
        campaign_id=draft["campaign_id"], confirm=True,
    ), _auth=True)


async def test_confirmation_syncs_complete_attributes_and_preference_update_preserves_evidence(store, provider):
    original = consent(language="en", frequency="weekly")
    store.pending["newsletter:pending:synthetic"] = json.dumps(original)
    assert (await newsletter.confirm_subscription("synthetic")).status_code == 200
    before = json.loads(store.hashes[CONFIRMED_KEY][EMAIL])
    assert provider.contacts[EMAIL]["attributes"] == preference_attributes(before)
    changed = {topic: topic == "system_news" for topic in TOPICS}
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.put("/api/v1/admin/newsletter/preferences", headers=AUTH, json={
            "email": EMAIL, "language": "el", "frequency": "monthly", "topics": changed,
        })
    assert response.json() == {"updated": 1, "synced": 1, "failed": 0}
    after = json.loads(store.hashes[CONFIRMED_KEY][EMAIL])
    for key in ("consent_schema", "confirmation_method", "requested_at", "confirmed_at"):
        assert after[key] == before[key]
    attributes = provider.contacts[EMAIL]["attributes"]
    assert attributes["NL_WEEKLY"] is False and attributes["NL_MONTHLY"] is True
    assert attributes["NL_ACTIVE_VOTES"] is False and attributes["NL_SYSTEM_NEWS"] is True
    assert attributes == preference_attributes(after)
    assert all("Fixture" not in request.content.decode() for request in provider.writes)
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert not provider.sent


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_send_paths_honor_language_frequency_and_topic_eligibility(store, provider, kind):
    for index, changes in enumerate([
        {"language": "el", "frequency": "monthly"},
        {"language": "en", "frequency": "weekly"},
        {"language": "unknown", "frequency": "weekly"},
        {"language": "en", "frequency": "monthly", "topics": {topic: topic == "system_news" for topic in TOPICS}},
        {"frequency": "invalid"},
        {"topics": dict.fromkeys(TOPICS, False)},
        {"consent_schema": 1},
    ]):
        save(store, provider, consent(f"fixture{index}@example.org", **changes))
    # Provider-only contacts and local/provider withdrawals cannot join a campaign.
    save(store, provider, consent("withdrawn@example.org"))
    store.hashes[SUPPRESSED_KEY]["withdrawn@example.org"] = "unsubscribed"
    provider.contacts["withdrawn@example.org"]["listIds"] = []
    save(store, provider, consent("blacklisted@example.org"), emailBlacklisted=True)
    provider.enroll(consent("provider-only@example.org"), attributes={})
    # Legacy evidence is held locally; its provider membership must not broaden a segment.
    provider.contacts["fixture6@example.org"]["attributes"] = {}
    if kind == "monthly":
        assert await newsletter_service.send_monthly_report(db())
        assert {campaign["tag"] for campaign in provider.sent} == {
            "newsletter:v1:el:monthly:all", "newsletter:v1:en:monthly:all",
        }
        assert "Monthly Report" in provider.sent[1]["htmlContent"]
        assert "/en/bills" in provider.sent[1]["htmlContent"]
    else:
        result = await admin_send(CampaignPlan(language="en", frequency="weekly", topic="active_votes"))
        assert result["selected"] == result["sent"] == 1
        assert len(provider.sent) == 1
    for campaign in provider.sent:
        plan = newsletter_audience.campaign_plan(campaign["tag"])
        selected = await newsletter_audience.select_audience(store, plan)
        expected = {"fixture0@example.org", "fixture2@example.org"} if plan.language == "el" else (
            {"fixture1@example.org", "fixture3@example.org"} if kind == "monthly" else {"fixture1@example.org"})
        assert selected.selected == expected
        assert set(campaign["recipients"]) == {"listIds"}
        assert provider.delivered[provider.sent.index(campaign)] == expected


@pytest.mark.parametrize("language", ["el", "en"])
@pytest.mark.parametrize("frequency", ["weekly", "monthly"])
@pytest.mark.parametrize("topic", [None, *sorted(TOPICS)])
async def test_admin_plan_matrix(store, provider, language, frequency, topic):
    save(store, provider, consent(language=language, frequency=frequency,
                                 topics={name: topic is None or name == topic for name in TOPICS}))
    result = await admin_send(CampaignPlan(language=language, frequency=frequency, topic=topic))
    assert result["selected"] == result["sent"] == 1
    assert provider.delivered == [{EMAIL}]
    assert provider.deleted == provider.sent[0]["recipients"]["listIds"]


async def test_audience_endpoint_is_admin_read_only_counts_and_current_preferences(store, provider):
    save(store, provider, consent())
    save(store, provider, consent("suppressed@example.org"), emailBlacklisted=True)
    save(store, provider, consent("english@example.org", language="en"))
    baseline = list(store.mutations)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        assert (await client.post("/api/v1/admin/newsletter/audience", json={})).status_code == 403
        response = await client.post("/api/v1/admin/newsletter/audience", headers=AUTH, json={})
    assert response.json() == {"reason": "ready", "selected": 1, "excluded": 2, "failed": 0, "provider": 1}
    assert all(type(value) is int for key, value in response.json().items() if key != "reason")
    assert "@" not in response.text and "token" not in response.text
    assert store.mutations == baseline and not provider.writes


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_provider_lookup_failure_aborts_without_private_errors(store, provider, monkeypatch, caplog, kind):
    save(store, provider, consent())
    monkeypatch.setattr(newsletter_service, "contact_status", AsyncMock(return_value="failed"))
    if kind == "monthly":
        assert not await newsletter_service.send_monthly_report(db())
    else:
        with pytest.raises(newsletter.HTTPException) as caught:
            await admin_send(CampaignPlan())
        assert caught.value.status_code == 503
        assert EMAIL not in str(caught.value.detail)
    assert not provider.sent
    assert EMAIL not in caplog.text


async def test_backfill_updates_existing_members_then_campaign_is_deliverable(store, provider):
    save(store, provider, consent(language="en"), attributes={})
    assert (await newsletter_admin.newsletter_backfill(_auth=True))["to_add"] == 1
    assert not provider.writes
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["to_add"] == 1
    assert provider.contacts[EMAIL]["attributes"]["NL_LANGUAGE"] == "en"
    writes = len(provider.writes)
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["already_present"] == 1
    assert len(provider.writes) == writes
    assert (await admin_send(CampaignPlan(language="en")))["sent"] == 1


@pytest.mark.parametrize("suppressed", [True, False])
async def test_preference_update_cannot_restore_withdrawal_or_missing_doi(store, provider, suppressed):
    save(store, provider, consent(consent_schema=2 if suppressed else 1))
    if suppressed:
        store.hashes[SUPPRESSED_KEY][EMAIL] = "unsubscribed"
    original = store.hashes[CONFIRMED_KEY][EMAIL]
    result = await newsletter_admin.newsletter_preferences(newsletter_admin.PreferencesRequest(
        email=EMAIL, language="en", frequency="monthly", topics=dict.fromkeys(TOPICS, True),
    ), _auth=True)
    assert result == {"updated": 0, "synced": 0, "failed": 1}
    assert store.hashes[CONFIRMED_KEY][EMAIL] == original and not provider.writes


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_withdrawal_after_campaign_write_blocks_dispatch(store, provider, monkeypatch, kind):
    save(store, provider, consent())
    if kind == "monthly":
        original = newsletter_service._brevo_post

        async def withdraw(endpoint, data):
            result = await original(endpoint, data)
            if endpoint == "emailCampaigns":
                await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
            return result

        monkeypatch.setattr(newsletter_service, "_brevo_post", withdraw)
        assert not await newsletter_service.send_monthly_report(db())
    else:
        original = newsletter_admin._brevo_request

        async def withdraw(method, endpoint, data=None):
            result = await original(method, endpoint, data)
            if method == "PUT":
                await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
            return result

        monkeypatch.setattr(newsletter_admin, "_brevo_request", withdraw)
        with pytest.raises(newsletter.HTTPException):
            await admin_send(CampaignPlan())
    assert EMAIL in store.hashes[SUPPRESSED_KEY] and not provider.sent


async def test_provider_error_is_redacted_and_send_failure_is_not_success(store, provider, caplog):
    save(store, provider, consent())
    provider.fail_send = True
    with pytest.raises(newsletter.HTTPException) as caught:
        await admin_send(CampaignPlan())
    assert EMAIL not in str(caught.value.detail) + caplog.text
    assert "private-token" not in str(caught.value.detail) + caplog.text
    assert not await newsletter_service.send_monthly_report(db())


async def test_unknown_language_uses_greek_for_large_audience(store, provider):
    for index in range(501):
        save(store, provider, consent(f"fixture{index}@example.org", language=None))
    audience = await newsletter_audience.prepare_audience(store, CampaignPlan())
    assert audience.counts == {"selected": 501, "excluded": 0, "failed": 0, "provider": 501}


@pytest.mark.parametrize("raw", ["{}", "[]", "null", '{"el:monthly:all":true}', '{"el:monthly:all":0}'])
def test_legacy_segment_parser_remains_strict(monkeypatch, raw):
    monkeypatch.setenv("BREVO_NEWSLETTER_SEGMENTS", raw)
    with pytest.raises(AudienceUnavailable):
        newsletter_audience.campaign_recipients(CampaignPlan())


async def test_preference_change_during_sync_retains_retry_until_current_attributes_match(store, provider, monkeypatch):
    data = consent()
    store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps(data)
    original = newsletter_service._brevo_post

    async def change(endpoint, payload, **kwargs):
        result = await original(endpoint, payload, **kwargs)
        if endpoint == "contacts":
            store.hashes[CONFIRMED_KEY][EMAIL] = json.dumps({**data, "language": "en"})
        return result

    monkeypatch.setattr(newsletter_service, "_brevo_post", change)
    assert not await newsletter._sync_brevo_contact(store, EMAIL)
    assert store.hashes[BREVO_ADD_RETRY_KEY] == {EMAIL: "1"}
    monkeypatch.setattr(newsletter_service, "_brevo_post", original)
    assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["to_add"] == 1
    assert provider.contacts[EMAIL]["attributes"]["NL_LANGUAGE"] == "en"
    assert not store.hashes[BREVO_ADD_RETRY_KEY]


@pytest.mark.parametrize("withdraw", [True, False])
async def test_preference_changes_propagate_withdrawal_and_all_disabled_topics(store, provider, monkeypatch, withdraw):
    save(store, provider, consent())
    if withdraw:
        original = newsletter_service._brevo_post

        async def remove(endpoint, payload, **kwargs):
            result = await original(endpoint, payload, **kwargs)
            if endpoint == "contacts":
                await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
            return result

        monkeypatch.setattr(newsletter_service, "_brevo_post", remove)
    result = await newsletter_admin.newsletter_preferences(newsletter_admin.PreferencesRequest(
        email=EMAIL, language="en", frequency="weekly", topics=dict.fromkeys(TOPICS, withdraw),
    ), _auth=True)
    assert result == {"updated": 1, "synced": int(not withdraw), "failed": int(withdraw)}
    assert newsletter_service.LIST_ID not in provider.contacts[EMAIL]["listIds"]
    assert (EMAIL in store.hashes[SUPPRESSED_KEY]) is withdraw
    assert not provider.sent


async def test_admin_send_rejects_unplanned_draft_and_overwrites_shared_list_recipients(store, provider):
    save(store, provider, consent())
    provider.campaigns[1] = {"recipients": {"listIds": [newsletter_service.LIST_ID]}}
    request = newsletter_admin.SendRequest(campaign_id=1, confirm=True)
    with pytest.raises(newsletter.HTTPException):
        await newsletter_admin.newsletter_send(request, _auth=True)
    assert not provider.sent
    provider.campaigns[1]["tag"] = CampaignPlan().tag
    assert (await newsletter_admin.newsletter_send(request, _auth=True))["sent"] == 1
    assert provider.delivered == [{EMAIL}]
    assert provider.deleted == provider.sent[0]["recipients"]["listIds"]


@pytest.mark.parametrize("path,body", [
    ("audience", {"language": EMAIL}),
    ("audience", {"frequency": "private-token"}),
    ("audience", {"topic": EMAIL}),
    ("preferences", {"email": EMAIL, "language": "el", "frequency": "monthly", "topics": {"active_votes": True}}),
])
async def test_new_admin_validation_is_private_and_precedes_io(store, provider, monkeypatch, caplog, path, body):
    redis = AsyncMock(side_effect=AssertionError("Unexpected store access"))
    monkeypatch.setattr(newsletter, "_get_redis", redis)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        response = await client.request("PUT" if path == "preferences" else "POST",
                                        f"/api/v1/admin/newsletter/{path}", headers=AUTH, json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid newsletter request"}
    assert EMAIL not in response.text + caplog.text
    assert "private-token" not in response.text + caplog.text
    redis.assert_not_awaited()


async def test_audience_excludes_alias_conflicts_and_counts_failed_provider_state(store, provider):
    save(store, provider, consent(EMAIL))
    alias = EMAIL.upper().replace("EXAMPLE.ORG", "example.org")
    store.hashes[CONFIRMED_KEY][alias] = json.dumps(consent(alias, language="en"))
    save(store, provider, consent("stale@example.org"), attributes={})
    audience = await newsletter_audience.select_audience(store, CampaignPlan())
    assert audience.counts == {"selected": 1, "excluded": 0, "failed": 2}


async def test_monthly_english_titles_and_labels_are_localized_and_escaped(store, provider, monkeypatch):
    save(store, provider, consent(language="en"))
    monkeypatch.setattr(newsletter_service, "small_cell_k", lambda: 0)
    database = db()
    rows = [
        [("bill-1", "Ελληνικός τίτλος", "English <title>")],
        [("bill-1", "Ελληνικός τίτλος", None, None)],
        [("bill-1", "Ελληνικός τίτλος", "English <title>", 10, 5, 15)],
    ]
    database.execute.side_effect = [MagicMock(all=lambda value=value: value) for value in rows]
    assert await newsletter_service.send_monthly_report(database)
    content = provider.sent[0]["htmlContent"]
    assert 'lang="en"' in content
    assert "English &lt;title&gt;" in content and "Ελληνικός τίτλος" not in content
    assert all(label in content for label in ("Upcoming Votes", "YES", "NO", "Total", "New bills"))


async def dispatch(kind):
    if kind == "monthly":
        return await newsletter_service.send_monthly_report(db())
    return await newsletter_admin.newsletter_send(
        newsletter_admin.SendRequest(campaign_id=1, confirm=True), _auth=True,
    )


def seed_campaign(store, provider):
    save(store, provider, consent())
    provider.campaigns[1] = {"tag": CampaignPlan().tag}


async def blocked_dispatch(kind, reason):
    if kind == "monthly":
        assert not await dispatch(kind)
    else:
        with pytest.raises(newsletter.HTTPException) as error:
            await dispatch(kind)
        assert error.value.status_code == 503
        assert error.value.detail["reason"] == reason
        return error.value.detail


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_withdrawal_at_final_lease_renewal_blocks_send_even_when_removal_fails(
    store, provider, monkeypatch, caplog, kind,
):
    from services.newsletter_lock import NewsletterLease

    seed_campaign(store, provider)
    monkeypatch.setattr(newsletter_service, "remove_contact", AsyncMock(return_value=False))
    original = NewsletterLease.check
    withdrawn = False

    async def renew(lease):
        nonlocal withdrawn
        await original(lease)
        final_gap = any(request.method == "PUT" or (
            kind == "monthly" and request.url.path == "/v3/emailCampaigns"
        ) for request in provider.writes)
        if final_gap and not withdrawn:
            withdrawn = True
            await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")

    monkeypatch.setattr(NewsletterLease, "check", renew)
    await blocked_dispatch(kind, "audience_mismatch")
    assert withdrawn and EMAIL in store.hashes[SUPPRESSED_KEY]
    assert newsletter_service.LIST_ID in provider.contacts[EMAIL]["listIds"]
    assert not provider.sent
    assert "reason=audience_mismatch" in caplog.text


@pytest.mark.parametrize("kind", ["admin", "monthly"])
@pytest.mark.parametrize("key,value", [
    (BREVO_ADD_RETRY_KEY, "1"),
    (BREVO_ADD_UNSETTLED_KEY, "pending"),
    (BREVO_ADD_UNSETTLED_KEY, "uncertain"),
    (LISTMONK_ADD_UNSETTLED_KEY, "pending"),
    (LISTMONK_ADD_UNSETTLED_KEY, "uncertain"),
    (BREVO_REMOVE_RETRY_KEY, "1"),
    (LISTMONK_REMOVE_RETRY_KEY, "1"),
])
@pytest.mark.parametrize("stage", ["initial", "final"])
async def test_unsettled_enrollment_writes_cannot_expand_campaign_lists(store, provider, monkeypatch, kind, key, value, stage):
    seed_campaign(store, provider)
    # Even an excluded contact's older write can change segment membership later.
    save(store, provider, consent("older-sync@example.org", language="en"))
    if stage == "initial":
        store.hashes[key]["older-sync@example.org"] = value
    else:
        from services.newsletter_lock import NewsletterLease
        original = NewsletterLease.check

        async def renew(lease):
            await original(lease)
            if any(request.method == "PUT" or (
                kind == "monthly" and request.url.path == "/v3/emailCampaigns"
            ) for request in provider.writes):
                store.hashes[key]["older-sync@example.org"] = value

        monkeypatch.setattr(NewsletterLease, "check", renew)
    await dispatch(kind)
    assert provider.delivered[0] == {EMAIL}
    assert store.hashes[key] == {"older-sync@example.org": value}


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_late_attribute_commit_cannot_expand_campaign_list(store, provider, monkeypatch, kind):
    from services.newsletter_lock import NewsletterLease

    seed_campaign(store, provider)
    save(store, provider, consent("older-sync@example.org", language="en"))
    original = NewsletterLease.check

    async def renew(lease):
        await original(lease)
        if any(request.method == "PUT" or (
            kind == "monthly" and request.url.path == "/v3/emailCampaigns"
        ) for request in provider.writes):
            # A historical request commits after the initial one-contact audit.
            provider.contacts["older-sync@example.org"]["attributes"]["NL_LANGUAGE"] = "el"

    monkeypatch.setattr(NewsletterLease, "check", renew)
    await dispatch(kind)
    assert provider.delivered[0] == {EMAIL}



@pytest.mark.parametrize("kind", ["admin", "monthly"])
@pytest.mark.parametrize("operation", ["unsubscribe", "webhook", "brevo", "listmonk", "preferences", "backfill"])
async def test_dispatch_lease_excludes_other_tasks_through_send(store, provider, monkeypatch, kind, operation):
    from services.newsletter_lock import NewsletterLockUnavailable

    seed_campaign(store, provider)
    entered, release = asyncio.Event(), asyncio.Event()
    original = provider.request

    async def request(req):
        if req.url.path.endswith("/sendNow"):
            entered.set()
            await release.wait()
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    task = asyncio.create_task(dispatch(kind))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        writes = len(provider.writes)
        if operation in {"unsubscribe", "webhook"}:
            path = "unsubscribe" if operation == "unsubscribe" else "webhook/brevo"
            token = "synthetic-admin-key" if operation == "unsubscribe" else "synthetic-webhook-token"
            async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
                response = await client.post(f"/api/v1/newsletter/{path}", headers={
                    "Authorization": f"Bearer {token}",
                }, json={"email": EMAIL, "event": "unsubscribe"})
            assert response.status_code == (503 if operation == "unsubscribe" else 429)
        elif operation in {"brevo", "listmonk"}:
            sync = newsletter._sync_brevo_contact if operation == "brevo" else newsletter._sync_listmonk_contact
            with pytest.raises(NewsletterLockUnavailable):
                await sync(store, EMAIL)
        elif operation == "preferences":
            with pytest.raises(newsletter.HTTPException) as error:
                await newsletter_admin.newsletter_preferences(newsletter_admin.PreferencesRequest(
                    email=EMAIL, language="en", frequency="weekly", topics=dict.fromkeys(TOPICS, True),
                ), _auth=True)
            assert error.value.status_code == 503
        else:
            assert (await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True))["failed"] == 1
        assert not store.hashes[SUPPRESSED_KEY]
        assert EMAIL in store.hashes[CONFIRMED_KEY]
        assert len(provider.writes) == writes
    finally:
        release.set()
        await asyncio.wait_for(task, 2)
    assert len(provider.sent) == 1
    # The same withdrawal succeeds once dispatch releases its authorization.
    monkeypatch.setattr(provider, "request", original)
    assert await newsletter._withdraw_subscription(store, EMAIL, "unsubscribed")
    assert EMAIL in store.hashes[SUPPRESSED_KEY]


@pytest.mark.parametrize("kind", ["admin", "monthly"])
async def test_inflight_preference_sync_blocks_campaign_and_retains_stale_write_retry(store, provider, monkeypatch, kind):
    from services.newsletter_lock import LOCK_KEY

    seed_campaign(store, provider)
    data = consent("older-sync@example.org")
    store.hashes[CONFIRMED_KEY][data["email"]] = json.dumps(data)
    entered, release = asyncio.Event(), asyncio.Event()
    original = provider.request

    async def request(req):
        if req.method == "POST" and req.url.path == "/v3/contacts":
            entered.set()
            await release.wait()
        return original(req)

    monkeypatch.setattr(provider, "request", request)
    task = asyncio.create_task(newsletter._sync_brevo_contact(store, data["email"]))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert LOCK_KEY in store.pending
        store.hashes[CONFIRMED_KEY][data["email"]] = json.dumps({**data, "language": "en"})
        await blocked_dispatch(kind, "lock_unavailable")
    finally:
        release.set()
        assert not await asyncio.wait_for(task, 2)
    assert store.hashes[BREVO_ADD_RETRY_KEY]
    await dispatch(kind)
    assert provider.delivered[0] == {EMAIL}


@pytest.mark.parametrize("key", ["en:weekly:all", "en:weekly:active_votes", "el:monthly:unknown", "xx:weekly:all", EMAIL])
@pytest.mark.parametrize("value", [0, -1, True, "private-segment", 1.5, None, {}, []])
def test_entire_segment_mapping_rejects_unknown_keys_and_invalid_other_entries(monkeypatch, key, value):
    monkeypatch.setenv("BREVO_NEWSLETTER_SEGMENTS", json.dumps({"el:monthly:all": 1, key: value}))
    with pytest.raises(AudienceUnavailable) as error:
        newsletter_audience.campaign_recipients(CampaignPlan())
    assert error.value.reason == "segments_invalid"


@pytest.mark.parametrize("key", ["el:monthly:unknown", "xx:weekly:all", "el:daily:all", EMAIL])
def test_unknown_segment_key_is_rejected_even_with_valid_id(monkeypatch, key):
    monkeypatch.setenv("BREVO_NEWSLETTER_SEGMENTS", json.dumps({"el:monthly:all": 1, key: 17}))
    with pytest.raises(AudienceUnavailable, match="segments_invalid"):
        newsletter_audience.campaign_recipients(CampaignPlan())


@pytest.mark.parametrize("kind", ["audience", "admin", "monthly"])
@pytest.mark.parametrize("raw", [None, "", "{}", "private-malformed-config", '{"unknown":true}'])
async def test_legacy_segment_config_is_not_required_for_dispatch(store, provider, monkeypatch, caplog, kind, raw):
    seed_campaign(store, provider)
    if raw is None:
        monkeypatch.delenv("BREVO_NEWSLETTER_SEGMENTS")
    else:
        monkeypatch.setenv("BREVO_NEWSLETTER_SEGMENTS", raw)
    if kind == "audience":
        assert (await newsletter_admin.newsletter_audience(CampaignPlan(), _auth=True))["selected"] == 1
        assert not provider.writes
    else:
        await dispatch(kind)
        assert provider.delivered == [{EMAIL}]
    assert EMAIL not in caplog.text and "private-malformed-config" not in caplog.text
