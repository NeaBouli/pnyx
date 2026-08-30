"""Focused mock-only tests for operator Reply-To routing (services/mail_policy).

Covers: mail_policy constant/helper, newsletter subscribe opt-in mail,
newsletter_service.send_transactional, monthly report campaign, admin draft
campaign, and the contact router fallback recipient. No real email, network,
redis or database access; everything is mocked.
"""
import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.mail_policy import OPERATOR_EMAIL, operator_reply_to


def test_operator_email_constant() -> None:
    assert OPERATOR_EMAIL == "kaspartisan@proton.me"


def test_operator_reply_to_object() -> None:
    assert operator_reply_to() == {"email": OPERATOR_EMAIL}


class _FakeResp:
    status_code = 201
    text = "{}"


class _FakeClient:
    """Minimal async-context httpx.AsyncClient stand-in capturing POSTs."""

    def __init__(self, captured: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        self._captured = captured

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def post(self, url: str, headers: Any = None, json: Any = None) -> _FakeResp:
        self._captured["url"] = url
        self._captured["json"] = json
        return _FakeResp()


async def test_subscribe_optin_mail_reply_to() -> None:
    from routers import newsletter

    redis = MagicMock()
    redis.hget = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    posted = {}

    req = newsletter.SubscribeRequest(email="citizen@example.org")
    with patch.object(newsletter, "BREVO_API_KEY", "test-key"), \
         patch.object(newsletter, "_get_redis", AsyncMock(return_value=redis)), \
         patch.object(newsletter.httpx, "AsyncClient",
                      lambda *a, **k: _FakeClient(posted, *a, **k)):
        out = await newsletter.subscribe(req)

    assert out["success"] is True
    assert posted["url"] == "https://api.brevo.com/v3/smtp/email"
    payload = posted["json"]
    assert payload["replyTo"] == {"email": OPERATOR_EMAIL}
    assert payload["sender"] == {"name": "ekklesia Newsletter", "email": "newsletter@ekklesia.gr"}
    assert payload["to"] == [{"email": "citizen@example.org"}]
    # DOI behavior preserved: pending token stored before sending
    redis.setex.assert_awaited_once()
    assert redis.setex.await_args.args[1] == 86400


async def test_send_transactional_reply_to() -> None:
    from services import newsletter_service

    captured = {}

    async def fake_post(endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        captured["endpoint"] = endpoint
        captured["data"] = data
        return {}

    with patch.object(newsletter_service, "_brevo_post", side_effect=fake_post):
        ok = await newsletter_service.send_transactional("user@example.org", "Subject", "<p>hi</p>")

    assert ok is True
    assert captured["endpoint"] == "smtp/email"
    payload = captured["data"]
    assert payload["replyTo"] == {"email": OPERATOR_EMAIL}
    assert payload["sender"] == newsletter_service.SENDER
    assert payload["to"] == [{"email": "user@example.org"}]


async def test_monthly_report_campaign_reply_to() -> None:
    from services import newsletter_service

    scalar_results = iter([1, 2, 3, 4])
    db = MagicMock()
    db.scalar = AsyncMock(side_effect=lambda *a, **k: next(scalar_results))
    empty_result = MagicMock()
    empty_result.all.return_value = []
    db.execute = AsyncMock(return_value=empty_result)

    calls = []

    async def fake_post(endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        calls.append((endpoint, data))
        return {"id": 123} if endpoint == "emailCampaigns" else {}

    with patch.object(newsletter_service, "_brevo_post", side_effect=fake_post):
        ok = await newsletter_service.send_monthly_report(db)

    assert ok is True
    endpoint, payload = calls[0]
    assert endpoint == "emailCampaigns"
    assert payload["replyTo"] == OPERATOR_EMAIL
    assert payload["sender"] == newsletter_service.SENDER
    assert payload["recipients"] == {"listIds": [newsletter_service.LIST_ID]}
    # immediate-send behavior preserved
    assert calls[1][0] == "emailCampaigns/123/sendNow"


async def test_admin_draft_campaign_reply_to() -> None:
    from routers import newsletter_admin

    captured = {}

    async def fake_request(method: str, endpoint: str, data: Any = None) -> dict[str, Any]:
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["data"] = data
        return {"id": 42}

    req = newsletter_admin.DraftRequest(subject="Test Subject", html_content="<p>hello world</p>")
    with patch.object(newsletter_admin, "_brevo_request", side_effect=fake_request):
        result = await newsletter_admin.newsletter_create_draft(req, _auth=True)

    assert result["status"] == "draft"
    assert captured["method"] == "POST"
    assert captured["endpoint"] == "emailCampaigns"
    payload = captured["data"]
    assert payload["replyTo"] == OPERATOR_EMAIL
    assert payload["sender"] == newsletter_admin.SENDER
    assert payload["recipients"] == {"listIds": [newsletter_admin.LIST_ID]}


def test_contact_fallback_recipient_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import routers.contact as contact

    try:
        with monkeypatch.context() as env:
            env.delenv("CONTACT_RECIPIENT", raising=False)
            importlib.reload(contact)
            assert contact.RECIPIENT == OPERATOR_EMAIL
            env.setenv("CONTACT_RECIPIENT", "custom@example.org")
            importlib.reload(contact)
            assert contact.RECIPIENT == "custom@example.org"
    finally:
        importlib.reload(contact)


async def test_contact_payload_recipient_and_user_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    from routers import contact

    monkeypatch.setattr(contact, "RECIPIENT", OPERATOR_EMAIL)
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    posted = {}

    body = contact.NgoContactRequest(
        first_name="Jane", last_name="Doe", email="jane@example.org", consent=True
    )
    with patch.object(contact, "_check_rate_limit", AsyncMock()), \
         patch.object(contact, "ip_reference", return_value="ref"), \
         patch.object(contact.httpx, "AsyncClient",
                      lambda *a, **k: _FakeClient(posted, *a, **k)):
        out = await contact.contact_ngo(body, request=SimpleNamespace())

    assert out["status"] == "ok"
    payload = posted["json"]
    assert payload["to"] == [{"email": OPERATOR_EMAIL, "name": "Ekklesia Admin"}]
    # user replyTo preserved
    assert payload["replyTo"] == {"email": "jane@example.org", "name": "Jane Doe"}
    assert payload["sender"] == {"name": "ekklesia.gr", "email": "noreply@ekklesia.gr"}
