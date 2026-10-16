"""EVA-006 stage 1: QR voting honours the ZK cross-tier lock; opinion logs carry no identity references."""
import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models import BillStatus
from routers import polis_qr, voting
from routers.polis_qr import QRVoteRequest

NULLIFIER = "1" * 64
PK = "a" * 64


class _Redis:
    def __init__(self) -> None:
        self.data = {"status": "authenticated", "purpose": "vote", "bill_id": "GR-1",
                     "nullifier_hash": NULLIFIER, "public_key_hex": PK}
        self.claimed = False

    async def hgetall(self, _key):
        return dict(self.data)

    async def eval(self, *_a, **_k):
        self.claimed = True
        return 1


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DB:
    def __init__(self):
        self.calls = 0
        self.added = []
        self.statements = []

    async def execute(self, stmt, *_a, **_k):
        self.calls += 1
        self.statements.append(str(stmt))
        if self.calls == 1:
            return _Result(SimpleNamespace(public_key_hex=PK, nullifier_hash=NULLIFIER, periferia_id=None, dimos_id=None))
        if self.calls == 2:
            return _Result(SimpleNamespace(id="GR-1", status=BillStatus.ACTIVE, source="PARLIAMENT"))
        return _Result(None)

    def add(self, row):
        self.added.append(row)


@pytest.mark.asyncio
async def test_qr_vote_is_blocked_by_the_zk_tier_lock(monkeypatch):
    redis = _Redis()

    async def fake_redis():
        return redis

    async def locked(_db, *, bill_id, bill_source, nullifier_hash):
        assert (bill_id, bill_source, nullifier_hash) == ("GR-1", "PARLIAMENT", NULLIFIER)
        raise HTTPException(409, "ZK_TIER_LOCKED")

    monkeypatch.setattr(polis_qr, "_redis", fake_redis)
    monkeypatch.setattr(polis_qr, "is_public_bill", lambda _bill: True)
    monkeypatch.setattr(polis_qr, "ensure_bill_scope_allowed", lambda *_a, **_k: None)
    monkeypatch.setattr(voting, "raise_if_zk_tier1_locked", locked)
    db = _DB()
    with pytest.raises(HTTPException) as exc:
        await polis_qr.qr_web_vote(QRVoteRequest(session_id="s" * 12, bill_id="GR-1", vote="YES"), db=db)
    assert exc.value.status_code == 409
    assert redis.claimed is False and db.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize("guard,locked", [("true", True), ("false", False)])
async def test_qr_vote_locks_the_bill_row_when_the_tier_guard_is_on(monkeypatch, guard, locked):
    redis = _Redis()

    async def fake_redis():
        return redis

    async def passes(_db, **_kw):
        return None

    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", guard)
    monkeypatch.setattr(polis_qr, "_redis", fake_redis)
    monkeypatch.setattr(polis_qr, "is_public_bill", lambda _bill: True)
    monkeypatch.setattr(polis_qr, "ensure_bill_scope_allowed", lambda *_a, **_k: None)
    monkeypatch.setattr(voting, "raise_if_zk_tier1_locked", passes)
    db = _DB()
    try:
        await polis_qr.qr_web_vote(QRVoteRequest(session_id="s" * 12, bill_id="GR-1", vote="YES"), db=db)
    except Exception:
        pass  # the fake DB stops after the checks; only the bill query matters here
    bill_sql = db.statements[1]
    assert ("FOR UPDATE" in bill_sql) is locked


def _logger_call_sources(source: str) -> list[str]:
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ):
            calls.append(ast.get_source_segment(source, node) or "")
    return calls


@pytest.mark.parametrize("module", ["routers/polis_qr.py", "routers/polis_tickets.py"])
def test_opinion_logs_carry_no_identity_or_choice(module):
    source = (Path(__file__).resolve().parents[1] / module).read_text(encoding="utf-8")
    offenders = [
        call for call in _logger_call_sources(source)
        if re.search(r"nullifier|req\.vote|req\.score|vote=|score=|pk_polis|get_short_handle", call)
    ]
    assert offenders == []
