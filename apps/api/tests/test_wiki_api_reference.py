"""EKA-37: the public wiki API reference may only document real routes and fields.

docs/wiki/api.html and wiki/API.md are hand-maintained. This test pins both
endpoint tables to the FastAPI OpenAPI schema, keeps them identical to each
other, and validates the vote curl example against the real request model.
"""
import importlib
import json
import pkgutil
import re
from pathlib import Path

import pytest
from fastapi.routing import APIWebSocketRoute

import routers
from main import app
from routers.voting import VoteRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = REPO_ROOT / "docs/wiki/api.html"
MD_PATH = REPO_ROOT / "wiki/API.md"
BASE_PATH = "/api/v1"

HTML_ROW = re.compile(
    r'<tr><td><span class="dot-(?:on|off)"></span>(MOD-\d+)</td>'
    r'<td><span class="badge badge-\w+">([A-Z]+)</span></td><td>([^<]+)</td>'
)
MD_SECTION = re.compile(r"^## (MOD-\d+):", re.M)
MD_ROW = re.compile(r"^\| ([A-Z]+) \| `([^`]+)` \|", re.M)
CURL_BODY = re.compile(r"-d '(\{.*?\})'", re.S)
SHELL_VAR = re.compile(r"'\"\$([A-Z_]+)\"'")

# Documented before EKA-37; none of these is registered by the API.
KNOWN_WRONG_ROWS = {
    ("GET", "/identity/status/{hash}"),
    ("POST", "/rep/consent"),
    ("GET", "/rep/evaluation"),
    ("GET", "/politikoi"),
    ("GET", "/politikoi/{id}"),
    ("POST", "/politikoi/{id}/evaluate"),
    ("GET", "/politikoi/{id}/my-evaluation"),
}


def _shape(path: str) -> str:
    """Path parameter names are prose in the docs; compare the route shape."""
    return re.sub(r"\{[^}]+\}", "{}", path)


def _registered_routes() -> set[tuple[str, str]]:
    routes = {
        (method.upper(), _shape(path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    # WebSocket routes are not part of OpenAPI.
    for module in pkgutil.iter_modules(routers.__path__):
        router = getattr(importlib.import_module(f"routers.{module.name}"), "router", None)
        for route in getattr(router, "routes", []):
            if isinstance(route, APIWebSocketRoute):
                routes.add(("WS", _shape(route.path)))
    return routes


def html_rows(html: str) -> list[tuple[str, str, str]]:
    return HTML_ROW.findall(html)


def md_rows(markdown: str) -> list[tuple[str, str, str]]:
    rows = []
    sections = list(MD_SECTION.finditer(markdown))
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(markdown)
        for method, path in MD_ROW.findall(markdown[section.end():end]):
            rows.append((section.group(1), method, path))
    return rows


def undocumented_routes(rows: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    registered = _registered_routes()
    return [
        (method, path) for _, method, path in rows
        if (method, _shape(BASE_PATH + path)) not in registered
    ]


def curl_vote_body(text: str) -> dict:
    """Parse the curl JSON body, filling shell variables with schema-valid values."""
    match = CURL_BODY.search(text)
    assert match, "vote curl example not found"
    filled = SHELL_VAR.sub(lambda var: {
        "BILL_ID": "bill-id",
        "NULLIFIER_HASH": "0" * 64,
        "SIGNATURE_HEX": "0" * 128,
    }[var.group(1)], match.group(1))
    return json.loads(filled)


@pytest.fixture(scope="module")
def html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def markdown() -> str:
    return MD_PATH.read_text(encoding="utf-8")


def test_html_table_is_fully_parsed(html: str) -> None:
    table = html[html.index("<table>"):html.index("</table>")]
    assert html_rows(html)
    assert len(html_rows(html)) == table.count("<tr>") - 1  # minus header row


def test_every_html_endpoint_is_registered(html: str) -> None:
    assert undocumented_routes(html_rows(html)) == []


def test_every_markdown_endpoint_is_registered(markdown: str) -> None:
    assert md_rows(markdown)
    assert undocumented_routes(md_rows(markdown)) == []


def test_markdown_and_html_tables_do_not_drift(html: str, markdown: str) -> None:
    assert sorted(md_rows(markdown)) == sorted(html_rows(html))


def test_known_wrong_rows_are_gone(html: str, markdown: str) -> None:
    for rows in (html_rows(html), md_rows(markdown)):
        assert KNOWN_WRONG_ROWS.isdisjoint({(method, path) for _, method, path in rows})


def test_checker_flags_a_wrong_route(html: str) -> None:
    broken = html.replace(
        '<span class="badge badge-green">POST</span></td><td>/identity/status</td>',
        '<span class="badge badge-blue">GET</span></td><td>/identity/status/{hash}</td>',
    )
    assert undocumented_routes(html_rows(broken)) == [("GET", "/identity/status/{hash}")]


@pytest.mark.parametrize("path", [HTML_PATH, MD_PATH], ids=["html", "markdown"])
def test_vote_curl_matches_vote_request_schema(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "https://api.ekklesia.gr/api/v1/vote" in text
    body = curl_vote_body(text)
    fields = set(VoteRequest.model_fields)
    required = {name for name, field in VoteRequest.model_fields.items() if field.is_required()}
    assert set(body) <= fields
    assert required <= set(body)
    VoteRequest.model_validate(body)


def test_vote_curl_checker_rejects_legacy_fields() -> None:
    legacy = """-d '{
    "bill_id": "'"$BILL_ID"'",
    "choice": "YES",
    "nullifier_hash": "'"$NULLIFIER_HASH"'",
    "public_key": "x",
    "signature": "x"
  }'"""
    assert not set(curl_vote_body(legacy)) <= set(VoteRequest.model_fields)
