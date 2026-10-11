"""EVA-012: REP_DEMO_ENABLED gates the DEMO-123 Diavgeia bypass, and the demo
account is excluded from evaluation endpoints regardless of the flag."""
import logging
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import evaluation, representative
from routers.evaluation import EvaluateRequest, ScoreItem
from routers.representative import VerifyRequest

DEMO = "DEMO-123"
REAL_ADA = "ΨΚΛ4ΟΡ1Γ-7ΑΒ"
INVITE = "ABCD-1234"
FLAG_ENV = "REP_DEMO_ENABLED"


class _Row:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class _CaptureDB:
    """Fake async session: records every statement, returns canned rows."""

    def __init__(self, invite_row=None):
        self.invite_row = invite_row
        self.executed = []
        self.committed = False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params or {}))
        if "FROM rep_invitations" in sql:
            return _Row(self.invite_row)
        return _Row()

    async def commit(self):
        self.committed = True


def _invite_row() -> tuple:
    return (1, "Δήμαρχος", None, None, False,
            datetime.now() + timedelta(hours=1), None, None)


def _track_diavgeia(monkeypatch, result=None) -> list:
    calls = []

    async def _diavgeia(ada: str):
        calls.append(ada)
        return result

    monkeypatch.setattr(representative, "_verify_ada_diavgeia", _diavgeia)
    return calls


# ─── Flag behaviour on /rep/verify ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flag_unset_demo_bypass_works(monkeypatch) -> None:
    monkeypatch.delenv(FLAG_ENV, raising=False)
    monkeypatch.setattr(representative.secrets, "token_urlsafe", lambda _n: "token-demo")
    diavgeia_calls = _track_diavgeia(monkeypatch)
    db = _CaptureDB(_invite_row())

    result = await representative.verify_representative(
        VerifyRequest(ada_number=DEMO, invite_code=INVITE), db=db,
    )

    assert result["ada_number"] == DEMO
    assert diavgeia_calls == []  # bypass: Diavgeia never consulted
    assert db.committed is True


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE"])
async def test_flag_true_values_keep_bypass(monkeypatch, value: str) -> None:
    monkeypatch.setenv(FLAG_ENV, value)
    monkeypatch.setattr(representative.secrets, "token_urlsafe", lambda _n: "token-demo")
    diavgeia_calls = _track_diavgeia(monkeypatch)
    db = _CaptureDB(_invite_row())

    result = await representative.verify_representative(
        VerifyRequest(ada_number=DEMO, invite_code=INVITE), db=db,
    )

    assert result["ada_number"] == DEMO
    assert diavgeia_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["false", "0", "no"])
async def test_flag_false_disables_bypass(monkeypatch, value: str) -> None:
    monkeypatch.setenv(FLAG_ENV, value)
    diavgeia_calls = _track_diavgeia(monkeypatch, result=None)
    db = _CaptureDB(_invite_row())

    with pytest.raises(HTTPException) as exc:
        await representative.verify_representative(
            VerifyRequest(ada_number=DEMO, invite_code=INVITE), db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Ο αριθμός ADA δεν βρέθηκε στη Διαύγεια."
    assert diavgeia_calls == [DEMO]  # treated like any other ADA
    assert db.committed is False  # invite not consumed


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["maybe", "2", "", "enabled"])
async def test_flag_invalid_fails_closed(monkeypatch, caplog, value: str) -> None:
    monkeypatch.setenv(FLAG_ENV, value)
    caplog.set_level(logging.WARNING, logger=representative.logger.name)
    diavgeia_calls = _track_diavgeia(monkeypatch, result=None)
    db = _CaptureDB(_invite_row())

    with pytest.raises(HTTPException) as exc:
        await representative.verify_representative(
            VerifyRequest(ada_number=DEMO, invite_code=INVITE), db=db,
        )

    assert exc.value.status_code == 403
    assert diavgeia_calls == [DEMO]
    # scope-only warning: env name logged, value never logged
    assert FLAG_ENV in caplog.text
    if value:
        assert value not in caplog.text


# ─── Demo must never enable evaluation (regardless of flag) ──────────────────


@pytest.mark.asyncio
async def test_demo_cannot_enable_evaluation_flag_unset(monkeypatch) -> None:
    monkeypatch.delenv(FLAG_ENV, raising=False)  # flag on (default)
    db = _CaptureDB()

    with pytest.raises(HTTPException) as exc:
        await representative.enable_evaluation(rep={"ada_number": DEMO}, db=db)

    assert exc.value.status_code == 403
    assert "αξιολόγηση" in exc.value.detail
    assert db.executed == []  # blocked before any write
    assert db.committed is False


@pytest.mark.asyncio
async def test_demo_cannot_enable_evaluation_flag_off(monkeypatch) -> None:
    monkeypatch.setenv(FLAG_ENV, "false")
    db = _CaptureDB()

    with pytest.raises(HTTPException) as exc:
        await representative.enable_evaluation(rep={"ada_number": DEMO}, db=db)

    assert exc.value.status_code == 403
    assert db.executed == []


# ─── Real ADA flow unchanged ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_real_ada_flow_unchanged_when_flag_off(monkeypatch) -> None:
    monkeypatch.setenv(FLAG_ENV, "false")
    monkeypatch.setattr(representative.secrets, "token_urlsafe", lambda _n: "token-real")
    _track_diavgeia(monkeypatch, result={"org_label": "ΔΗΜΟΣ ΚΑΛΑΜΑΤΑΣ", "subject": "x"})
    db = _CaptureDB(_invite_row())

    result = await representative.verify_representative(
        VerifyRequest(ada_number=REAL_ADA, invite_code=INVITE), db=db,
    )

    assert result["ada_number"] == REAL_ADA
    assert db.committed is True


# ─── Demo excluded from evaluation endpoints ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_enabled_politician_rejects_demo() -> None:
    db = _CaptureDB()

    with pytest.raises(HTTPException) as exc:
        await evaluation._get_enabled_politician(DEMO, db)

    assert exc.value.status_code == 404
    assert db.executed == []  # rejected before hitting the DB


@pytest.mark.asyncio
async def test_evaluate_politician_rejects_demo() -> None:
    req = EvaluateRequest(
        nullifier_hash="n" * 16,
        scores=[ScoreItem(question_id=1, score=1)],
        signature_hex="f" * 64,
    )
    db = _CaptureDB()

    with pytest.raises(HTTPException) as exc:
        await evaluation.evaluate_politician(DEMO, req, db=db)

    assert exc.value.status_code == 404
    assert db.executed == []


@pytest.mark.asyncio
async def test_questions_and_scores_reject_demo() -> None:
    for endpoint in (evaluation.get_questions, evaluation.get_scores):
        db = _CaptureDB()
        with pytest.raises(HTTPException) as exc:
            await endpoint(DEMO, db=db)
        assert exc.value.status_code == 404
        assert db.executed == []


@pytest.mark.asyncio
async def test_list_politicians_excludes_demo() -> None:
    db = _CaptureDB()

    result = await evaluation.list_politicians(db=db)

    sql, params = db.executed[0]
    assert "rt.ada_number <> :demo_ada" in sql
    assert params["demo_ada"] == DEMO
    assert result == []
