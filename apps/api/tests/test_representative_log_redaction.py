"""EVA-004: representative invite codes and ADAs never appear in application logs."""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from nacl.signing import SigningKey

from ip_utils import log_reference
from routers import evaluation, representative
from routers.evaluation import EvaluateRequest, ScoreItem
from routers.representative import InviteRequest, VerifyRequest

INVITE = "QX7K-M2PA"
ADA = "ΨΚΛ4ΟΡ1Γ-7ΑΒ"


class _Row:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _Session:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.committed = False

    async def execute(self, _statement, _params=None):
        return _Row(self.rows.pop(0) if self.rows else None)

    async def commit(self):
        self.committed = True


def test_log_reference_is_stable_short_and_namespaced() -> None:
    ref = log_reference(INVITE, "rep-invite")

    assert ref == log_reference(INVITE, "rep-invite")
    assert len(ref) == 12 and all(c in "0123456789abcdef" for c in ref)
    assert ref != log_reference(INVITE, "rep-ada")
    assert INVITE not in ref


@pytest.mark.asyncio
async def test_create_invite_logs_reference_not_code(monkeypatch, caplog) -> None:
    monkeypatch.setattr(representative, "_generate_invite_code", lambda: INVITE)
    caplog.set_level(logging.INFO, logger=representative.logger.name)

    result = await representative.create_invite(
        InviteRequest(role="Δήμαρχος", region="Αττικής"), _auth=True, db=_Session(),
    )

    assert result["invite_code"] == INVITE
    assert INVITE not in caplog.text
    assert f"ref={log_reference(INVITE, 'rep-invite')}" in caplog.text


@pytest.mark.asyncio
async def test_verify_logs_references_not_ada_or_invite(monkeypatch, caplog) -> None:
    async def _diavgeia(_ada):
        return {"org_label": "ΔΗΜΟΣ ΚΑΛΑΜΑΤΑΣ", "subject": "x"}

    monkeypatch.setattr(representative, "_verify_ada_diavgeia", _diavgeia)
    caplog.set_level(logging.INFO, logger=representative.logger.name)
    invite_row = (7, "Δήμαρχος", "Πελοποννήσου", "Καλαμάτας", False,
                  datetime.now() + timedelta(hours=1), 6, 22)
    db = _Session([invite_row])

    result = await representative.verify_representative(
        VerifyRequest(ada_number=ADA, invite_code=INVITE), db=db,
    )

    assert result["ada_number"] == ADA and db.committed is True
    assert ADA not in caplog.text and INVITE not in caplog.text
    # The invite reference matches the one logged at creation, so an operator
    # can still correlate both events.
    assert f"invite_ref={log_reference(INVITE, 'rep-invite')}" in caplog.text
    assert f"ada_ref={log_reference(ADA, 'rep-ada')}" in caplog.text


@pytest.mark.asyncio
async def test_diavgeia_failure_logs_no_ada_or_url(monkeypatch, caplog) -> None:
    class _FailingClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def get(self, url):
            raise ConnectionError(f"connect failed for {url}")

    monkeypatch.setattr(representative.httpx, "AsyncClient", _FailingClient)
    caplog.set_level(logging.WARNING, logger=representative.logger.name)

    assert await representative._verify_ada_diavgeia(ADA) is None
    assert ADA not in caplog.text and "diavgeia.gov.gr" not in caplog.text
    assert "error=ConnectionError" in caplog.text


@pytest.mark.asyncio
async def test_enable_evaluation_logs_reference_not_ada(caplog) -> None:
    caplog.set_level(logging.INFO, logger=representative.logger.name)

    result = await representative.enable_evaluation(rep={"ada_number": ADA}, db=_Session())

    assert result["evaluation_enabled"] is True
    assert ADA not in caplog.text
    assert f"ada_ref={log_reference(ADA, 'rep-ada')}" in caplog.text


class _EvalResult:
    def __init__(self, *, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._scalars


class _EvalSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _statement, _params=None):
        return self.results.pop(0)

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_legacy_evaluation_warning_logs_reference_not_ada(monkeypatch, caplog) -> None:
    monkeypatch.delenv("EVALUATION_REQUIRE_V2", raising=False)
    signing_key = SigningKey(bytes([9]) * 32)
    nullifier = "e" * 64
    identity = SimpleNamespace(
        public_key_hex=signing_key.verify_key.encode().hex(),
        region_locked=True, periferia_id=6, dimos_id=None,
    )

    async def _enabled(_ada_number, _db):
        return {"role": "Βουλευτής", "periferia_id": 6, "dimos_id": None}

    monkeypatch.setattr(evaluation, "_get_enabled_politician", _enabled)
    caplog.set_level(logging.INFO, logger=evaluation.logger.name)
    db = _EvalSession([
        _EvalResult(scalar=identity),
        _EvalResult(scalars=[SimpleNamespace(id=2), SimpleNamespace(id=8)]),
        _EvalResult(), _EvalResult(),
    ])
    request = EvaluateRequest(
        nullifier_hash=nullifier,
        scores=[ScoreItem(question_id=8, score=5), ScoreItem(question_id=2, score=-3)],
        signature_hex=signing_key.sign(f"evaluate:{ADA}:{nullifier}".encode()).signature.hex(),
    )

    result = await evaluation.evaluate_politician(ADA, request, db=db)

    assert result["integrity"] == "legacy"
    assert ADA not in caplog.text
    assert f"ada_ref={log_reference(ADA, 'rep-ada')}" in caplog.text


@pytest.mark.asyncio
async def test_v2_evaluation_info_log_has_no_ada(monkeypatch, caplog) -> None:
    signing_key = SigningKey(bytes([11]) * 32)
    nullifier = "d" * 64
    identity = SimpleNamespace(
        public_key_hex=signing_key.verify_key.encode().hex(),
        region_locked=True, periferia_id=6, dimos_id=None,
    )

    async def _enabled(_ada_number, _db):
        return {"role": "Βουλευτής", "periferia_id": 6, "dimos_id": None}

    monkeypatch.setattr(evaluation, "_get_enabled_politician", _enabled)
    monkeypatch.setattr(evaluation, "evaluation_timestamp_is_fresh", lambda _ts: True)
    caplog.set_level(logging.INFO, logger=evaluation.logger.name)
    scores = [ScoreItem(question_id=8, score=5), ScoreItem(question_id=2, score=-3)]
    timestamp_ms = 1_787_999_123_456
    payload = evaluation.build_evaluation_v2_payload(ADA, nullifier, timestamp_ms, scores)
    db = _EvalSession([
        _EvalResult(scalar=identity),
        _EvalResult(scalars=[SimpleNamespace(id=2), SimpleNamespace(id=8)]),
        _EvalResult(), _EvalResult(),
    ])
    request = EvaluateRequest(
        nullifier_hash=nullifier, scores=scores, payload_version=2, timestamp_ms=timestamp_ms,
        signature_hex=signing_key.sign(payload.encode()).signature.hex(),
    )

    result = await evaluation.evaluate_politician(ADA, request, db=db)

    assert result["integrity"] == "bound"
    assert ADA not in caplog.text
    assert f"ada_ref={log_reference(ADA, 'rep-ada')}" in caplog.text
