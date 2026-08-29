import pytest
from fastapi import HTTPException
from nacl.signing import SigningKey
from pydantic import ValidationError
from types import SimpleNamespace

from keypair import verify_signature
from routers import evaluation
from routers.evaluation import EvaluateRequest, ScoreItem
from services.evaluation_integrity import (
    DEFAULT_EVALUATION_V2_MAX_SKEW_MS,
    EVALUATION_K_ANONYMITY_MIN,
    build_evaluation_v2_payload,
    evaluation_timestamp_is_fresh,
    evaluation_v2_max_skew_ms,
    evaluation_v2_required,
    public_evaluation_average,
)


def _scores() -> list[ScoreItem]:
    return [
        ScoreItem(question_id=8, score=5),
        ScoreItem(question_id=2, score=-3),
    ]


class _Result:
    def __init__(self, *, scalar=None, rows=None, scalars=None):
        self._scalar = scalar
        self._rows = rows or []
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def fetchall(self):
        return self._rows

    def scalars(self):
        return self

    def all(self):
        return self._scalars


class _Session:
    def __init__(self, results):
        self.results = list(results)
        self.committed = False

    async def execute(self, _statement, _params=None):
        return self.results.pop(0)

    async def commit(self):
        self.committed = True


def test_v2_payload_matches_cross_client_golden_vector():
    payload = build_evaluation_v2_payload(
        "ADA-ΕΛ-1",
        "a" * 64,
        1_787_999_123_456,
        _scores(),
    )

    assert payload == (
        'evaluate:v2:["ADA-ΕΛ-1","'
        + "a" * 64
        + '",1787999123456,[[2,-3],[8,5]]]'
    )


def test_v2_signature_binds_scores_and_context():
    signing_key = SigningKey(bytes.fromhex("01" * 32))
    public_key_hex = signing_key.verify_key.encode().hex()
    payload = build_evaluation_v2_payload("ADA-1", "b" * 64, 123_456, _scores())
    signature_hex = signing_key.sign(payload.encode("utf-8")).signature.hex()

    assert verify_signature(public_key_hex, payload, signature_hex) is True
    assert verify_signature(
        public_key_hex,
        build_evaluation_v2_payload(
            "ADA-1",
            "b" * 64,
            123_456,
            [ScoreItem(question_id=2, score=-2), ScoreItem(question_id=8, score=5)],
        ),
        signature_hex,
    ) is False


def test_request_rejects_duplicate_question_ids():
    with pytest.raises(ValidationError, match="duplicate question_id"):
        EvaluateRequest(
            nullifier_hash="c" * 64,
            scores=[
                ScoreItem(question_id=2, score=-3),
                ScoreItem(question_id=2, score=5),
            ],
            signature_hex="d" * 128,
        )


def test_k_anonymity_hides_thin_aggregates():
    assert public_evaluation_average(4.5, EVALUATION_K_ANONYMITY_MIN - 1) is None
    assert public_evaluation_average(4.5, EVALUATION_K_ANONYMITY_MIN) == 4.5
    assert public_evaluation_average(None, EVALUATION_K_ANONYMITY_MIN) is None


def test_v2_cutoff_is_explicit_and_reversible(monkeypatch):
    monkeypatch.delenv("EVALUATION_REQUIRE_V2", raising=False)
    assert evaluation_v2_required() is False

    monkeypatch.setenv("EVALUATION_REQUIRE_V2", "true")
    assert evaluation_v2_required() is True


def test_timestamp_window_rejects_stale_payloads(monkeypatch):
    monkeypatch.setenv("EVALUATION_V2_MAX_SKEW_MS", "60000")

    assert evaluation_timestamp_is_fresh(1_000_000, now_ms=1_060_000) is True
    assert evaluation_timestamp_is_fresh(1_000_000, now_ms=1_060_001) is False


def test_invalid_timestamp_window_config_uses_bounded_default(monkeypatch):
    monkeypatch.setenv("EVALUATION_V2_MAX_SKEW_MS", "unbounded")

    assert evaluation_v2_max_skew_ms() == DEFAULT_EVALUATION_V2_MAX_SKEW_MS


@pytest.mark.asyncio
async def test_list_endpoint_masks_averages_below_threshold():
    db = _Session([_Result(rows=[
        ("ADA-9", "Βουλευτής", "Αττική", "Example", 4.5, 9),
        ("ADA-10", "Βουλευτής", "Αττική", "Example", 3.0, 10),
    ])])

    result = await evaluation.list_politicians(db=db)

    assert result[0]["avg_score"] is None
    assert result[0]["scores_hidden"] is True
    assert result[0]["evaluator_count"] == 0
    assert result[0]["evaluator_count_hidden"] is True
    assert result[1]["avg_score"] == 3.0
    assert result[1]["scores_hidden"] is False


@pytest.mark.asyncio
async def test_score_endpoint_masks_each_thin_question(monkeypatch):
    async def _enabled(_ada_number, _db):
        return {"org_label": "Example"}

    monkeypatch.setattr(evaluation, "_get_enabled_politician", _enabled)
    db = _Session([_Result(rows=[
        (1, "Question 1", None, "trust", 5.0, 1),
        (2, "Question 2", None, "trust", 2.0, 10),
    ])])

    result = await evaluation.get_scores("ADA-1", db=db)

    assert result["questions"][0]["avg_score"] is None
    assert result["questions"][0]["vote_count"] == 0
    assert result["questions"][0]["vote_count_hidden"] is True
    assert result["questions"][1]["avg_score"] == 2.0
    assert result["scores_hidden"] is True
    assert result["minimum_group_size"] == EVALUATION_K_ANONYMITY_MIN


@pytest.mark.asyncio
async def test_v2_endpoint_accepts_bound_signature(monkeypatch):
    signing_key = SigningKey(bytes.fromhex("02" * 32))
    timestamp_ms = 1_000_000
    scores = _scores()
    payload = build_evaluation_v2_payload("ADA-1", "e" * 64, timestamp_ms, scores)
    signature_hex = signing_key.sign(payload.encode("utf-8")).signature.hex()
    identity = SimpleNamespace(
        public_key_hex=signing_key.verify_key.encode().hex(),
        region_locked=True,
        periferia_id=6,
        dimos_id=None,
    )

    async def _enabled(_ada_number, _db):
        return {"role": "Βουλευτής", "periferia_id": 6, "dimos_id": None}

    monkeypatch.setattr(evaluation, "_get_enabled_politician", _enabled)
    monkeypatch.setattr(evaluation, "evaluation_timestamp_is_fresh", lambda _ts: True)
    db = _Session([
        _Result(scalar=identity),
        _Result(scalars=[SimpleNamespace(id=2), SimpleNamespace(id=8)]),
        _Result(),
        _Result(),
    ])
    request = EvaluateRequest(
        nullifier_hash="e" * 64,
        scores=scores,
        signature_hex=signature_hex,
        payload_version=2,
        timestamp_ms=timestamp_ms,
    )

    result = await evaluation.evaluate_politician("ADA-1", request, db=db)

    assert result["integrity"] == "bound"
    assert result["payload_version_accepted"] == 2
    assert db.committed is True


@pytest.mark.asyncio
async def test_v2_endpoint_rejects_stale_timestamp(monkeypatch):
    signing_key = SigningKey(bytes.fromhex("04" * 32))
    identity = SimpleNamespace(
        public_key_hex=signing_key.verify_key.encode().hex(),
        region_locked=True,
        periferia_id=6,
        dimos_id=None,
    )

    async def _enabled(_ada_number, _db):
        return {"role": "Βουλευτής", "periferia_id": 6, "dimos_id": None}

    monkeypatch.setattr(evaluation, "_get_enabled_politician", _enabled)
    monkeypatch.setattr(evaluation, "evaluation_timestamp_is_fresh", lambda _ts: False)
    db = _Session([_Result(scalar=identity)])
    request = EvaluateRequest(
        nullifier_hash="a" * 64,
        scores=_scores(),
        signature_hex="0" * 128,
        payload_version=2,
        timestamp_ms=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        await evaluation.evaluate_politician("ADA-1", request, db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_legacy_endpoint_is_rejected_after_cutoff(monkeypatch):
    signing_key = SigningKey(bytes.fromhex("03" * 32))
    identity = SimpleNamespace(
        public_key_hex=signing_key.verify_key.encode().hex(),
        region_locked=True,
        periferia_id=6,
        dimos_id=None,
    )

    async def _enabled(_ada_number, _db):
        return {"role": "Βουλευτής", "periferia_id": 6, "dimos_id": None}

    monkeypatch.setattr(evaluation, "_get_enabled_politician", _enabled)
    monkeypatch.setenv("EVALUATION_REQUIRE_V2", "true")
    db = _Session([_Result(scalar=identity)])
    request = EvaluateRequest(
        nullifier_hash="f" * 64,
        scores=_scores(),
        signature_hex="0" * 128,
    )

    with pytest.raises(HTTPException) as exc_info:
        await evaluation.evaluate_politician("ADA-1", request, db=db)

    assert exc_info.value.status_code == 426
