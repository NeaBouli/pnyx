"""CSP on real API responses and the HTML documents served by the API."""

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from httpx import ASGITransport, AsyncClient, Response
import pytest
from starlette.responses import Response as ASGIResponse
from starlette.types import Message, Receive, Scope, Send
import yaml

import main
from routers import newsletter
from security_headers import SecurityHeadersMiddleware
from services.newsletter_consent import RECONFIRM_KEY


STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
TOKEN = "synthetic-confirmation-token"
CONFIRM_PATH = f"/api/v1/newsletter/confirm/{TOKEN}"


def assert_policy(response: Response, policy: str = STRICT_CSP) -> None:
    # get_list checks the wire values rather than a comma-joined header lookup.
    assert response.headers.get_list("content-security-policy") == [policy]
    assert response.headers.get_list("x-content-type-options") == ["nosniff"]


def hash_source(content: str) -> str:
    return "'sha256-" + b64encode(sha256(content.encode()).digest()).decode() + "'"


@pytest.mark.parametrize("path,status,content", [
    ("/health", 200, "ekklesia-api"),
    ("/", 200, "Ekklesia.gr API"),
    ("/api/v1/does-not-exist", 404, "Not Found"),
    ("/robots.txt", 200, "Disallow: /"),
])
async def test_api_response_has_one_strict_policy(path: str, status: int, content: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(path, headers={"Origin": "https://ekklesia.gr"})
    assert response.status_code == status
    assert content in response.text
    assert_policy(response)
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["access-control-allow-origin"] == "https://ekklesia.gr"


@pytest.mark.parametrize("origin,request_headers,status", [
    ("https://ekklesia.gr", "Content-Type, Authorization, X-API-Key", 200),
    ("https://ekklesia.gr", "X-Nullifier", 400),
    ("https://unknown.example", "Content-Type", 400),
])
async def test_preflight_keeps_cors_and_gets_one_policy(
    origin: str, request_headers: str, status: int,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.options("/api/v1/bills", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": request_headers,
        })
    assert response.status_code == status
    assert_policy(response)
    if origin == "https://ekklesia.gr":
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "POST" in response.headers["access-control-allow-methods"]
    else:
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("html", [False, True])
async def test_existing_middleware_and_repeated_headers_produce_one_policy(html: bool) -> None:
    app = FastAPI()
    app.state.limiter = main.limiter
    app.user_middleware = list(main.app.user_middleware)

    @app.get("/repeated-headers")
    async def repeated_headers() -> ASGIResponse:
        response = HTMLResponse("<h1>Document</h1>") if html else JSONResponse({"ok": True})
        response.headers.append("Content-Security-Policy", STRICT_CSP)
        response.headers.append("Content-Security-Policy", "default-src 'self'")
        response.headers.append("X-Content-Type-Options", "nosniff")
        response.headers.append("X-Content-Type-Options", "nosniff")
        return response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/repeated-headers", headers={"Origin": "https://ekklesia.gr"})
    assert response.status_code == 200
    assert_policy(response)
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["access-control-allow-origin"] == "https://ekklesia.gr"
    assert "Document" in response.text if html else response.json() == {"ok": True}


async def test_unhandled_server_error_preserves_default_response_with_security_headers() -> None:
    app = FastAPI()
    app.user_middleware = list(main.app.user_middleware)
    app.state.limiter = main.limiter
    app.exception_handlers = dict(main.app.exception_handlers)

    @app.get("/server-error")
    async def server_error() -> None:
        raise RuntimeError("Synthetic failure")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/server-error")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert response.headers["content-type"].startswith("text/plain")
    assert_policy(response)


@pytest.mark.parametrize("state,status,content", [
    ("confirmed", 200, "Εγγραφή Επιβεβαιώθηκε!"),
    ("already_confirmed", 200, "Η εγγραφή σας ήταν ήδη επιβεβαιωμένη"),
    ("expired", 410, "Link abgelaufen"),
    ("consumed", 410, "Confirmation link expired or already used."),
    ("reconfirmed", 200, "Εγγραφή Επιβεβαιώθηκε!"),
    ("reconfirm_expired", 410, "Confirmation link expired or already used."),
])
async def test_newsletter_html_preserves_content_and_authorizes_only_its_assets(
    monkeypatch: pytest.MonkeyPatch, state: str, status: int, content: str,
) -> None:
    store = MagicMock()
    data = {"email": "confirmation@example.org"}
    raw = json.dumps(data)
    store.get = AsyncMock(return_value=raw)
    store.hget = AsyncMock(return_value=None)
    store.set = AsyncMock(return_value=True)
    result = {"already_confirmed": 2, "consumed": 0}.get(state, 1)
    store.eval = AsyncMock(return_value=result)
    if state == "expired":
        store.get.return_value = None
    if state in {"reconfirmed", "reconfirm_expired"}:
        now = datetime.now(timezone.utc)
        data.update({
            "consent_state": "reconfirm_pending",
            "reconfirm_token_hash": sha256(TOKEN.encode()).hexdigest(),
            "reconfirm_created_at": (now - timedelta(hours=1)).isoformat(),
            "reconfirm_deadline_at": (now + timedelta(hours=1)).isoformat(),
        })
        raw = json.dumps(data)
        store.get.side_effect = [None, raw]

        async def hget(key: str, field: str) -> str | None:
            return raw if key == RECONFIRM_KEY and state == "reconfirmed" else None

        store.hget.side_effect = hget
        monkeypatch.setattr(newsletter, "_reconcile_consent_aliases", AsyncMock())
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter, "_remove_ineligible_contact", AsyncMock())

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(CONFIRM_PATH)
    assert response.status_code == status
    assert response.headers["content-type"].startswith("text/html")
    assert content in response.text
    styles = re.findall(r"<style>(.*?)</style>", response.text, re.S)
    assert len(styles) == 1
    expected = (
        f"{STRICT_CSP}; style-src {hash_source(styles[0])}"
        "; img-src https://ekklesia.gr/pnx.png"
    )
    assert_policy(response, expected)
    assert "<script" not in response.text
    assert "style=" not in response.text
    assert "unsafe-inline" not in expected
    if status == 200:
        assert '<img src="https://ekklesia.gr/pnx.png"' in response.text
        assert '<a href="https://ekklesia.gr">' in response.text


async def test_newsletter_service_error_is_json_with_strict_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(side_effect=RuntimeError("Unavailable")))
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(CONFIRM_PATH)
    assert response.status_code == 503
    assert response.json() == {"detail": "Newsletter confirmation unavailable; retry"}
    assert_policy(response)


async def test_newsletter_validation_error_has_strict_policy() -> None:
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/v1/newsletter/subscribe", json={"email": "invalid"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid newsletter request"}
    assert_policy(response)


async def test_streaming_response_is_forwarded_without_waiting_for_completion() -> None:
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def stream(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/event-stream")]})
        await send({"type": "http.response.body", "body": b"data: first\n\n", "more_body": True})
        assert len(sent) == 2
        assert sent[1]["body"] == b"data: first\n\n"
        await send({"type": "http.response.body", "body": b"data: last\n\n"})

    await SecurityHeadersMiddleware(stream)({"type": "http", "path": "/events"}, receive, send)
    assert len(sent) == 3
    assert sent[0]["headers"] == [
        (b"content-type", b"text/event-stream"),
        (b"x-content-type-options", b"nosniff"),
        (b"content-security-policy", STRICT_CSP.encode()),
    ]
    assert sent[2]["body"] == b"data: last\n\n"


@pytest.mark.parametrize("path,content", [
    ("/docs", "SwaggerUIBundle"),
    ("/redoc", '<redoc spec-url="/openapi.json">'),
    ("/docs/oauth2-redirect", "window.opener.swaggerUIRedirectOauth2"),
])
async def test_documentation_follows_environment(path: str, content: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(path)
    if not main._is_dev:
        assert response.status_code == 404
        assert_policy(response)
        return
    assert response.status_code == 200
    assert content in response.text
    policies = response.headers.get_list("content-security-policy")
    assert len(policies) == 1
    policy = policies[0]
    assert policy.startswith(STRICT_CSP + ";")
    for script in re.findall(r"<script>(.*?)</script>", response.text, re.S):
        assert hash_source(script) in policy
    assert "'unsafe-inline'" not in policy.split("script-src ")[1].split(";")[0]
    assert response.headers["x-content-type-options"] == "nosniff"
    if path in {"/docs", "/redoc"}:
        assert "https://cdn.jsdelivr.net" in policy
        assert "connect-src 'self'" in policy
    if path == "/redoc":
        assert "style-src https://fonts.googleapis.com 'unsafe-inline'" in policy
        assert "font-src https://fonts.gstatic.com" in policy


async def test_development_docs_under_root_path_hash_the_actual_script() -> None:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, documentation_paths={"/docs": "swagger"})
    transport = ASGITransport(app=app, root_path="/gateway")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/gateway/docs")
    assert response.status_code == 200
    assert "url: '/gateway/openapi.json'" in response.text
    scripts = re.findall(r"<script>(.*?)</script>", response.text, re.S)
    assert len(scripts) == 1
    policy = response.headers.get_list("content-security-policy")
    assert len(policy) == 1
    assert hash_source(scripts[0]) in policy[0]


def test_api_edge_headers_do_not_add_a_second_csp() -> None:
    compose = Path(__file__).resolve().parents[3] / "infra/docker/docker-compose.prod.yml"
    labels = dict(label.split("=", 1) for label in yaml.safe_load(compose.read_text())["services"]["api"]["labels"])
    assert labels["traefik.http.routers.ekklesia-api.middlewares"] == "api-headers"
    assert labels["traefik.http.middlewares.api-headers.headers.contentTypeNosniff"] == "true"
    assert not any("contentsecuritypolicy" in key.lower() or "content-security-policy" in key.lower() for key in labels)
