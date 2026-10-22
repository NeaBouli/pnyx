"""Response policies owned by the API, including its HTML documents."""

from base64 import b64encode
from hashlib import sha256
from html.parser import HTMLParser
from typing import Literal

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
Documentation = Literal["swagger", "redoc", "oauth2"]


def csp_hash(content: str) -> str:
    """Authorize exactly one inline script or style block."""
    digest = b64encode(sha256(content.encode("utf-8")).digest()).decode("ascii")
    return f"'sha256-{digest}'"


class _InlineScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hashes: list[str] = []
        self._script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and "src" not in dict(attrs):
            self._script = []

    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script is not None:
            self.hashes.append(csp_hash("".join(self._script)))
            self._script = None


def _documentation_csp(documentation: Documentation, body: bytes) -> str:
    scripts = _InlineScripts()
    scripts.feed(body.decode("utf-8"))
    script_sources = " ".join(scripts.hashes)
    if documentation != "oauth2":
        script_sources = f"https://cdn.jsdelivr.net {script_sources}".rstrip()
    policy = f"{API_CSP}; script-src {script_sources}"
    if documentation == "swagger":
        # Swagger UI also creates style attributes when rendering controls.
        policy += (
            "; style-src https://cdn.jsdelivr.net 'unsafe-inline'"
            "; img-src https://fastapi.tiangolo.com data:; connect-src 'self'"
        )
    elif documentation == "redoc":
        # ReDoc generates styles at runtime and uses the default Google fonts.
        policy += (
            "; style-src https://fonts.googleapis.com 'unsafe-inline'"
            "; font-src https://fonts.gstatic.com"
            "; img-src https://fastapi.tiangolo.com data:; connect-src 'self'"
            "; worker-src blob:"
        )
    return policy


class SecurityHeadersMiddleware:
    """Set one CSP and nosniff without buffering API or streaming responses."""

    def __init__(
        self, app: ASGIApp, documentation_paths: dict[str, Documentation] | None = None,
    ) -> None:
        self.app = app
        self.documentation_paths = documentation_paths or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        root_path = scope.get("root_path", "").rstrip("/")
        if root_path and path.startswith(f"{root_path}/"):
            path = path[len(root_path):]
        documentation = self.documentation_paths.get(path)
        document_start: Message | None = None
        document_body: list[bytes] = []

        async def send_with_headers(message: Message) -> None:
            nonlocal document_start
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                is_html = headers.get("content-type", "").split(";", 1)[0].strip().lower() == "text/html"
                if is_html and documentation:
                    # Only FastAPI's small, generated documentation pages need
                    # body hashes; ordinary responses pass through immediately.
                    document_start = message
                    return
                policy = headers.get("Content-Security-Policy", API_CSP) if is_html else API_CSP
                # Assignment replaces existing values, including duplicates.
                headers["Content-Security-Policy"] = policy
            elif (message["type"] == "http.response.body"
                  and document_start is not None and documentation is not None):
                document_body.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                body = b"".join(document_body)
                headers = MutableHeaders(scope=document_start)
                headers["Content-Security-Policy"] = _documentation_csp(documentation, body)
                await send(document_start)
                document_start = None
                message = {**message, "body": body}
            await send(message)

        await self.app(scope, receive, send_with_headers)
