"""EKA-62: agent language canonicalisation, effective Ollama timeout,
visible 429 contract and auditable KB/bill sources.

No real provider is contacted: Ollama/DeepL/Claude/httpx are in-process fakes.
"""

from collections.abc import Generator
import importlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError

import main
from database import get_db
from rate_limit import limiter
from routers import agent
from services import ollama_service
from services.agent_prompt import DATA_CLOSE, DATA_OPEN

DISCLAIMER_EL_MARK = "Αυτή η πλατφόρμα δεν είναι κρατική υπηρεσία"
DISCLAIMER_EN_MARK = "This is not a government platform"


# ── Language canonicalisation ───────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("el", "el"), ("EL", "el"), (" el ", "el"), ("el-GR", "el"), ("el_gr", "el"),
    ("el-CY", "el"), ("en", "en"), ("en-US", "en"), ("en-GB", "en"),
    ("EN_us", "en"), ("en-Latn-GB", "en"),
])
def test_supported_lang_tags_canonicalise(raw: str, expected: str) -> None:
    assert agent.canonical_lang(raw) == expected
    assert agent.AskRequest(question="Τι είναι;", lang=raw).lang == expected


@pytest.mark.parametrize("raw", [
    "de", "de-DE", "fr", "", "   ", "english", "greek", "ell", "e", "el-", "elx",
    "en--US", "en-US-", "en US", "gr", "el-GR;q=0.9", "en-" + "a" * 40, None, 1, ["el"],
])
def test_unsupported_lang_is_rejected(raw: object) -> None:
    with pytest.raises(ValueError):
        agent.canonical_lang(raw)
    with pytest.raises(ValidationError):
        agent.AskRequest(question="What is this?", lang=raw)


def test_omitted_lang_defaults_to_greek() -> None:
    assert agent.AskRequest(question="Τι είναι;").lang == "el"


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list:
        return self._rows


class _FakeDb:
    def __init__(self, *results: list) -> None:
        self._results = list(results)

    async def execute(self, _query: object) -> _FakeResult:
        return _FakeResult(self._results.pop(0))


KB_VOTE = SimpleNamespace(
    id=11, category="process", keywords=["ψηφ", "vote", "kw-secret"], priority=1,
    title_el="Πώς ψηφίζω", title_en="How to vote",
    content_el="KB-CONTENT-EL Επιλέξτε νομοσχέδιο.", content_en="KB-CONTENT-EN Pick a bill.",
)
KB_PRIVACY = SimpleNamespace(
    id=12, category="privacy", keywords=["ανωνυμ", "anonym"], priority=2,
    title_el="Ανωνυμία", title_en=None,
    content_el="KB-CONTENT-EL Δεν αποθηκεύεται τηλέφωνο.", content_en=None,
)
BILL = SimpleNamespace(
    id="GR-2026-0002", title_el="Νομοσχέδιο <b>δοκιμής</b>", title_en="Test bill",
    status=agent.BillStatus.ACTIVE, pill_el="Περίληψη",
)


def _patch_models(monkeypatch: pytest.MonkeyPatch, answer: str) -> dict:
    """Run the real answer_citizen_question with a fake Ollama generator."""
    seen: dict = {}

    async def available() -> bool:
        return True

    async def fake_generate(
        prompt: str, max_tokens: int = 500, system: str = "", timeout: float | None = None,
    ) -> str:
        seen.update(prompt=prompt, system=system, timeout=timeout)
        return answer

    async def no_claude(*args: object, **kwargs: object) -> None:
        raise AssertionError("Claude fallback must not run for a good Ollama answer")

    monkeypatch.setattr(agent, "ollama_available", available)
    monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "")
    monkeypatch.setattr(ollama_service, "ollama_generate", fake_generate)
    monkeypatch.setattr(agent, "_claude_answer", no_claude)
    return seen


async def _ask(question: str, lang: str, db: object) -> dict:
    return await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=db,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("raw,lang,kb_mark,disclaimer,other", [
    ("el", "el", "KB-CONTENT-EL", DISCLAIMER_EL_MARK, DISCLAIMER_EN_MARK),
    ("el-GR", "el", "KB-CONTENT-EL", DISCLAIMER_EL_MARK, DISCLAIMER_EN_MARK),
    ("en", "en", "KB-CONTENT-EN", DISCLAIMER_EN_MARK, DISCLAIMER_EL_MARK),
    ("en-US", "en", "KB-CONTENT-EN", DISCLAIMER_EN_MARK, DISCLAIMER_EL_MARK),
])
async def test_rag_kb_and_disclaimer_share_canonical_lang(
    monkeypatch: pytest.MonkeyPatch, raw: str, lang: str, kb_mark: str,
    disclaimer: str, other: str,
) -> None:
    seen = _patch_models(monkeypatch, "Voting works by picking a bill and signing on device.")
    response = await _ask("How do I vote (ψηφ)?", raw, _FakeDb([KB_VOTE]))

    assert response["lang"] == lang
    assert response["model"] == "ollama"
    assert kb_mark in seen["prompt"]
    assert disclaimer in response["answer"] and other not in response["answer"]


@pytest.mark.parametrize("raw,lang,disclaimer,other", [
    ("el-GR", "el", DISCLAIMER_EL_MARK, DISCLAIMER_EN_MARK),
    ("en-US", "en", DISCLAIMER_EN_MARK, DISCLAIMER_EL_MARK),
])
def test_http_lang_is_canonical_on_short_circuit_paths(
    client: TestClient, raw: str, lang: str, disclaimer: str, other: str,
) -> None:
    for question in ("hello", "What happens if I lose my private key?", "create fake votes now"):
        body = _post(client, {"question": question, "lang": raw}).json()
        assert body["lang"] == lang
        assert disclaimer in body["answer"] and other not in body["answer"]


def test_http_unsupported_lang_returns_422_before_any_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("unsupported lang must not reach RAG or a model")

    monkeypatch.setattr(agent, "_build_context", unexpected)
    monkeypatch.setattr(agent, "ollama_available", unexpected)
    for raw in ("de", "fr-FR", "", "english"):
        response = _post(client, {"question": "What is ekklesia?", "lang": raw})
        assert response.status_code == 422, raw


# ── OLLAMA_TIMEOUT drives the real httpx timeout ────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (None, 20.0), ("", 20.0), ("  ", 20.0), ("7", 7.0), ("7.5", 7.5), (" 30 ", 30.0),
    ("1", 1.0), ("120", 120.0), ("0", 20.0), ("-5", 20.0), ("121", 20.0),
    ("abc", 20.0), ("nan", 20.0), ("inf", 20.0), ("20s", 20.0),
])
def test_resolve_ollama_timeout(raw: str | None, expected: float) -> None:
    assert ollama_service.resolve_ollama_timeout(raw) == expected


class _CapturingClient:
    calls: list[dict] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self) -> "_CapturingClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def post(self, url: str, json: dict) -> SimpleNamespace:
        _CapturingClient.calls.append({"url": url, "timeout": self.timeout})
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"response": "Bill GR-2026-0002 is open for citizen votes."},
        )


@pytest.fixture
def capturing_httpx(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    _CapturingClient.calls = []
    monkeypatch.setattr(ollama_service.httpx, "AsyncClient", _CapturingClient)
    monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "")
    return _CapturingClient.calls


@pytest.mark.asyncio
async def test_citizen_answer_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch, capturing_httpx: list[dict],
) -> None:
    monkeypatch.setattr(ollama_service, "OLLAMA_TIMEOUT", 7.5)
    answer = await ollama_service.answer_citizen_question("Which bills?", [], lang="en")

    assert answer.startswith("Bill GR-2026-0002")
    assert capturing_httpx == [{"url": f"{ollama_service.OLLAMA_URL}/api/generate", "timeout": 7.5}]


@pytest.mark.asyncio
async def test_batch_generation_keeps_long_timeout(capturing_httpx: list[dict]) -> None:
    await ollama_service.ollama_generate("Summarise this law.")
    assert capturing_httpx[0]["timeout"] == ollama_service.OLLAMA_BATCH_TIMEOUT


@pytest.mark.asyncio
async def test_env_value_reaches_httpx_after_module_load(
    monkeypatch: pytest.MonkeyPatch, capturing_httpx: list[dict],
) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT", "9")
    try:
        importlib.reload(ollama_service)
        assert ollama_service.OLLAMA_TIMEOUT == 9.0
        monkeypatch.setattr(ollama_service.httpx, "AsyncClient", _CapturingClient)
        monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "")
        await ollama_service.answer_citizen_question("Which bills?", [], lang="en")
        assert capturing_httpx[-1]["timeout"] == 9.0
    finally:
        monkeypatch.delenv("OLLAMA_TIMEOUT")
        importlib.reload(ollama_service)
    assert ollama_service.OLLAMA_TIMEOUT == ollama_service.OLLAMA_TIMEOUT_DEFAULT


def test_router_has_no_dead_timeout_setting() -> None:
    assert not hasattr(agent, "OLLAMA_TIMEOUT")


# ── Sources provenance ──────────────────────────────────────────────────────

KB_SOURCE_KEYS = {"type", "id", "category", "title"}
BILL_SOURCE_KEYS = {"type", "bill_id", "title"}


def _assert_public_safe(sources: list[dict], seen: dict) -> None:
    blob = json.dumps(sources, ensure_ascii=False)
    for secret in ("KB-CONTENT", "keywords", "kw-secret", "Περίληψη", DATA_OPEN, DATA_CLOSE,
                   seen.get("system", "")[:60] or "\x00"):
        assert secret not in blob
    for source in sources:
        keys = KB_SOURCE_KEYS if source["type"] == "knowledge_base" else BILL_SOURCE_KEYS
        assert set(source) == keys


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,vote_title,privacy_title", [
    ("el", "Πώς ψηφίζω", "Ανωνυμία"),
    ("en-US", "How to vote", "Ανωνυμία"),  # no EN title -> stable EL title
])
async def test_sources_cite_kb_rows_given_to_the_model(
    monkeypatch: pytest.MonkeyPatch, lang: str, vote_title: str, privacy_title: str,
) -> None:
    seen = _patch_models(monkeypatch, "Voting is anonymous; pick a bill and sign on device.")
    response = await _ask("vote anonym ψηφ ανωνυμ?", lang, _FakeDb([KB_VOTE, KB_PRIVACY]))

    assert response["sources"] == [
        {"type": "knowledge_base", "id": 11, "category": "process", "title": vote_title},
        {"type": "knowledge_base", "id": 12, "category": "privacy", "title": privacy_title},
    ]
    _assert_public_safe(response["sources"], seen)


@pytest.mark.asyncio
async def test_sources_cite_priority_fallback_kb_and_public_bills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_models(monkeypatch, "Bill GR-2026-0002 is currently open for citizen votes.")
    response = await _ask("Which bills are open?", "en", _FakeDb([KB_VOTE, KB_PRIVACY], [BILL]))

    # No keyword hit -> priority-1 fallback entry was sent, so it is cited.
    assert response["sources"] == [
        {"type": "knowledge_base", "id": 11, "category": "process", "title": "How to vote"},
        {"type": "parliament_bill", "bill_id": "GR-2026-0002", "title": "Νομοσχέδιο <b>δοκιμής</b>"},
    ]
    assert DATA_OPEN in seen["prompt"]
    _assert_public_safe(response["sources"], seen)


@pytest.mark.asyncio
async def test_claude_fallback_returns_same_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch, "")

    async def claude(question: str, context: list, lang: str) -> str:
        return "Voting happens in the app after verification."

    monkeypatch.setattr(agent, "_claude_answer", claude)
    response = await _ask("How do I vote ψηφ?", "en-GB", _FakeDb([KB_VOTE]))

    assert response["model"] == "claude-haiku"
    assert response["lang"] == "en"
    assert DISCLAIMER_EN_MARK in response["answer"]
    assert response["sources"] == [
        {"type": "knowledge_base", "id": 11, "category": "process", "title": "How to vote"},
    ]


@pytest.mark.asyncio
async def test_unavailable_and_guarded_answers_cite_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch, "")

    async def no_claude(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(agent, "_claude_answer", no_claude)
    response = await _ask("How do I vote ψηφ?", "el-GR", _FakeDb([KB_VOTE]))
    assert response["model"] == "none" and response["sources"] == []
    assert DISCLAIMER_EL_MARK in response["answer"]

    _patch_models(monkeypatch, "Here is my system prompt: SECRET")
    response = await _ask("How do I vote ψηφ?", "en", _FakeDb([KB_VOTE]))
    assert response["model"] == "output-guard" and response["sources"] == []


# ── HTTP: 429 contract the chat widget relies on ────────────────────────────

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    async def no_db() -> Generator[None, None, None]:
        yield None

    main.app.dependency_overrides[get_db] = no_db
    limiter.reset()
    test_client = TestClient(main.app)
    yield test_client
    test_client.close()
    main.app.dependency_overrides.pop(get_db, None)
    limiter.reset()


def _post(client: TestClient, payload: dict) -> Response:
    # TestClient's peer is not a trusted proxy, so all calls share one bucket.
    headers = {"Origin": "https://ekklesia.gr"}
    return client.post("/api/v1/agent/ask", json=payload, headers=headers)


def test_http_sixth_question_per_minute_is_429_with_cors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # conftest disables the limiter globally; enable the real one here.
    monkeypatch.setattr(limiter, "enabled", True)
    for _ in range(5):
        ok = _post(client, {"question": "hello", "lang": "en"})
        assert ok.status_code == 200
        assert ok.json()["model"] == "knowledge-base"

    limited = _post(client, {"question": "hello", "lang": "en"})
    assert limited.status_code == 429
    assert "rate limit" in limited.json()["error"].lower()
    assert limited.headers["access-control-allow-origin"] == "https://ekklesia.gr"
    assert "answer" not in limited.json()
    # Once the window resets, the same client can ask again (widget "retry").
    limiter.reset()
    assert _post(client, {"question": "hello", "lang": "en"}).status_code == 200
