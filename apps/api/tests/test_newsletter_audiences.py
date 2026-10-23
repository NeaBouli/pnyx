"""Campaign selection through the real service and routes, with a mock Brevo only."""
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
        if request.method == "GET" and path.startswith("contacts/"):
            contact = self.contacts.get(path.removeprefix("contacts/").casefold())
            return httpx.Response(200, json=contact) if contact else httpx.Response(404)
        if request.method == "GET" and path == "contacts":
            segment = int(request.url.params["segmentId"])
            key = next(key for key, value in SEGMENTS.items() if value == segment)
            language, frequency, topic = key.split(":")
            contacts = []
            for contact in [*self.contacts.values(), *self.extra]:
                attributes = contact["attributes"]
                if (attributes.get("NL_LANGUAGE") == language and attributes.get(f"NL_{frequency.upper()}") is True
                        and newsletter_service.LIST_ID in contact["listIds"]
                        and any(attributes.get(f"NL_{name.upper()}") is True for name in TOPICS)
                        and (topic == "all" or attributes.get(f"NL_{topic.upper()}") is True)):
                    contacts.append(contact)
            offset = int(request.url.params["offset"])
            return httpx.Response(200, json={"contacts": contacts[offset:offset + 500], "count": len(contacts)})
        if path == "contacts" and request.method == "POST":
            email = body["email"].casefold()
            contact = self.contacts.setdefault(email, {"email": body["email"], "emailBlacklisted": False,
                                                       "listUnsubscribed": [], "listIds": [], "attributes": {}})
            contact["attributes"].update(body["attributes"])
            contact["listIds"] = list(set(contact["listIds"] + body["listIds"]))
            return httpx.Response(204)
        if path.endswith("/contacts/remove"):
            for email in body["emails"]:
                self.contacts[email.casefold()]["listIds"] = []
            return httpx.Response(201, json={"contacts": {"success": body["emails"], "failure": []}})
        if path == "emailCampaigns":
            campaign_id = len(self.campaigns) + 1
            self.campaigns[campaign_id] = dict(body)
            return httpx.Response(201, json={"id": campaign_id})
        if path.startswith("emailCampaigns/"):
            campaign_id = int(path.split("/")[1])
            if path.endswith("/sendNow"):
                if self.fail_send:
                    return httpx.Response(500, json={"message": EMAIL + " private-token"})
                self.sent.append(dict(self.campaigns[campaign_id]))
                return httpx.Response(204)
            if request.method == "PUT":
                self.campaigns[campaign_id].update(body)
                return httpx.Response(204)
            return httpx.Response(200, json=self.campaigns[campaign_id])
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
    assert provider.contacts[EMAIL]["attributes"] == {"FIRSTNAME": "Fixture", **preference_attributes(before)}
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
        assert campaign["recipients"] == {"segmentIds": [SEGMENTS[plan.key]]}


@pytest.mark.parametrize("language", ["el", "en"])
@pytest.mark.parametrize("frequency", ["weekly", "monthly"])
@pytest.mark.parametrize("topic", [None, *sorted(TOPICS)])
async def test_admin_plan_matrix(store, provider, language, frequency, topic):
    save(store, provider, consent(language=language, frequency=frequency,
                                 topics={name: topic is None or name == topic for name in TOPICS}))
    result = await admin_send(CampaignPlan(language=language, frequency=frequency, topic=topic))
    assert result["selected"] == result["sent"] == 1
    assert provider.sent[0]["recipients"] == {"segmentIds": [SEGMENTS[f"{language}:{frequency}:{topic or 'all'}"]]}


async def test_audience_endpoint_is_admin_read_only_counts_and_current_preferences(store, provider):
    save(store, provider, consent())
    save(store, provider, consent("suppressed@example.org"), emailBlacklisted=True)
    save(store, provider, consent("english@example.org", language="en"))
    baseline = list(store.mutations)
    async with HTTP_CLIENT(transport=httpx.ASGITransport(app=application()), base_url="http://test") as client:
        assert (await client.post("/api/v1/admin/newsletter/audience", json={})).status_code == 403
        response = await client.post("/api/v1/admin/newsletter/audience", headers=AUTH, json={})
    assert response.json() == {"selected": 1, "excluded": 2, "failed": 0}
    assert all(type(value) is int for value in response.json().values())
    assert "@" not in response.text and "token" not in response.text
    assert store.mutations == baseline and not provider.writes


@pytest.mark.parametrize("kind", ["monthly", "admin"])
@pytest.mark.parametrize("problem", ["extra_member", "stale_attributes", "suppression_retry", "missing_config", "provider_failure"])
async def test_send_paths_fail_closed_without_private_errors(store, provider, monkeypatch, caplog, kind, problem):
    save(store, provider, consent())
    if problem == "extra_member":
        provider.enroll(consent("unknown@example.org"))
    elif problem == "stale_attributes":
        provider.contacts[EMAIL]["attributes"]["NL_LANGUAGE"] = "en"
    elif problem == "suppression_retry":
        store.hashes[BREVO_REMOVE_RETRY_KEY][EMAIL] = "1"
        monkeypatch.setattr(newsletter_service, "remove_contact", AsyncMock(return_value=False))
    elif problem == "missing_config":
        monkeypatch.delenv("BREVO_NEWSLETTER_SEGMENTS")
    else:
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


async def test_segment_pagination_and_unknown_language(store, provider):
    for index in range(501):
        save(store, provider, consent(f"fixture{index}@example.org", language=None))
    audience = await newsletter_audience.prepare_audience(store, CampaignPlan())
    assert audience.counts == {"selected": 501, "excluded": 0, "failed": 0}


@pytest.mark.parametrize("raw", ["{}", "[]", "null", '{"el:monthly:all":true}', '{"el:monthly:all":0}'])
def test_segment_configuration_is_required_and_strict(monkeypatch, raw):
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
    assert provider.sent[0]["recipients"] == {"segmentIds": [SEGMENTS[CampaignPlan().key]]}


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
    assert audience.counts == {"selected": 0, "excluded": 0, "failed": 3}


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
