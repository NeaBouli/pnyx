"""
Tests für MOD-04 CitizenVote + MOD-05 Divergence Score
Keine DB nötig — alle Algorithmus-Tests sind rein.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from routers import voting
from routers.voting import compute_divergence, vote_percent, votes_in_progress_threshold
from models import BillStatus, GovernanceLevel, VoteChoice


class _FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, values):
        self.values = list(values)
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return _FakeScalarResult(self.values.pop(0))


class TestDivergenceScore:
    def test_strong_divergence(self):
        # 80% Bürger dagegen, Parlament hat angenommen
        result = compute_divergence(
            yes=20, no=80, abstain=0,
            parliament_votes={"ΝΔ": "ΝΑΙ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΟΧΙ"}
        )
        assert result is not None
        assert result.score > 0.4
        assert "Απόκλιση" in result.label_el
        assert result.parliament_result == "ΕΓΚΡΙΘΗΚΕ"
        assert result.citizen_majority == "ΚΑΤΑ"

    def test_convergence(self):
        # 70% Bürger dafür, Parlament hat angenommen
        result = compute_divergence(
            yes=70, no=30, abstain=0,
            parliament_votes={"ΝΔ": "ΝΑΙ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΟΧΙ"}
        )
        assert result is not None
        assert result.score <= 0.3
        assert result.citizen_majority == "ΥΠΕΡ"
        assert result.parliament_result == "ΕΓΚΡΙΘΗΚΕ"

    def test_no_parliament_votes_returns_none(self):
        result = compute_divergence(yes=50, no=50, abstain=0, parliament_votes=None)
        assert result is None

    def test_empty_parliament_votes_returns_none(self):
        result = compute_divergence(yes=50, no=50, abstain=0, parliament_votes={})
        assert result is None

    def test_zero_votes_returns_none(self):
        result = compute_divergence(
            yes=0, no=0, abstain=0,
            parliament_votes={"ΝΔ": "ΝΑΙ"}
        )
        assert result is None

    def test_score_is_between_0_and_1(self):
        result = compute_divergence(
            yes=60, no=30, abstain=10,
            parliament_votes={"ΝΔ": "ΟΧΙ", "ΣΥΡΙΖΑ": "ΟΧΙ"}
        )
        assert result is not None
        assert 0.0 <= result.score <= 1.0

    def test_parliament_rejected(self):
        result = compute_divergence(
            yes=30, no=70, abstain=0,
            parliament_votes={"ΝΔ": "ΟΧΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΚΚΕ": "ΝΑΙ"}
        )
        assert result is not None
        assert result.parliament_result == "ΑΠΟΡΡΙΦΘΗΚΕ"

    def test_disclaimer_exists(self):
        """Disclaimer muss in jedem Results-Response enthalten sein"""
        from routers.voting import BillResults
        fields = BillResults.model_fields
        assert "disclaimer_el" in fields


class TestVotesInProgressHelpers:
    def test_vote_percent_handles_zero_total(self):
        assert vote_percent(3, 0) == 0

    def test_vote_percent_rounds_whole_percent(self):
        assert vote_percent(2, 3) == 67

    def test_votes_in_progress_threshold_defaults_to_50(self, monkeypatch):
        monkeypatch.delenv("VOTES_IN_PROGRESS_THRESHOLD", raising=False)
        assert votes_in_progress_threshold() == 50

    def test_votes_in_progress_threshold_uses_env(self, monkeypatch):
        monkeypatch.setenv("VOTES_IN_PROGRESS_THRESHOLD", "3")
        assert votes_in_progress_threshold() == 3

    def test_votes_in_progress_threshold_rejects_invalid_values(self, monkeypatch):
        monkeypatch.setenv("VOTES_IN_PROGRESS_THRESHOLD", "nope")
        assert votes_in_progress_threshold() == 50

    def test_votes_in_progress_threshold_minimum_one(self, monkeypatch):
        monkeypatch.setenv("VOTES_IN_PROGRESS_THRESHOLD", "0")
        assert votes_in_progress_threshold() == 1


class TestZkTier1Guard:
    def test_zk_tier1_guard_defaults_to_disabled(self, monkeypatch):
        monkeypatch.delenv("ZK_TIER1_GUARD_ENABLED", raising=False)
        assert voting.zk_tier1_guard_enabled() is False

    def test_zk_tier1_guard_requires_explicit_true(self, monkeypatch):
        monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
        assert voting.zk_tier1_guard_enabled() is True

        monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "1")
        assert voting.zk_tier1_guard_enabled() is False

    @pytest.mark.asyncio
    async def test_submit_vote_rejects_tier1_when_zk_lock_exists(self, monkeypatch):
        monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
        monkeypatch.setenv("SERVER_SALT", "s" * 64)
        monkeypatch.setattr(voting, "verify_signature", lambda *_args: True)

        async def locked(*_args, **_kwargs):
            return True

        monkeypatch.setattr(voting, "tier1_vote_blocked_by_zk_lock", locked)
        req = voting.VoteRequest(
            nullifier_hash="a" * 64,
            bill_id="GR-0490a766",
            vote="YES",
            signature_hex="b" * 128,
        )
        identity = SimpleNamespace(public_key_hex="c" * 64, periferia_id=None, dimos_id=None)
        bill = SimpleNamespace(
            id="GR-0490a766",
            status=BillStatus.ACTIVE,
            governance_level=GovernanceLevel.NATIONAL,
        )
        db = _FakeDb([identity, bill])

        with pytest.raises(HTTPException) as exc:
            await voting.submit_vote(req, db)

        assert exc.value.status_code == 409
        assert "Semaphore ZK" in exc.value.detail
        assert "FOR UPDATE" in str(db.executed[1])

    @pytest.mark.asyncio
    async def test_zk_guard_misconfiguration_returns_controlled_503(self, monkeypatch):
        monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
        monkeypatch.delenv("SERVER_SALT", raising=False)

        with pytest.raises(HTTPException) as exc:
            await voting.raise_if_zk_tier1_locked(
                _FakeDb([]),
                bill_id="GR-0490a766",
                nullifier_hash="a" * 64,
            )

        assert exc.value.status_code == 503
        assert "not configured" in exc.value.detail

    @pytest.mark.asyncio
    async def test_submit_vote_does_not_check_zk_lock_when_guard_disabled(self, monkeypatch):
        monkeypatch.delenv("ZK_TIER1_GUARD_ENABLED", raising=False)
        monkeypatch.setattr(voting, "verify_signature", lambda *_args: True)
        called = False

        async def locked(*_args, **_kwargs):
            nonlocal called
            called = True
            return True

        monkeypatch.setattr(voting, "tier1_vote_blocked_by_zk_lock", locked)
        req = voting.VoteRequest(
            nullifier_hash="a" * 64,
            bill_id="GR-0490a766",
            vote="YES",
            signature_hex="b" * 128,
        )
        identity = SimpleNamespace(public_key_hex="c" * 64, periferia_id=None, dimos_id=None)
        bill = SimpleNamespace(
            id="GR-0490a766",
            status=BillStatus.ACTIVE,
            governance_level=GovernanceLevel.NATIONAL,
        )
        existing_vote = SimpleNamespace()
        db = _FakeDb([identity, bill, existing_vote])

        with pytest.raises(HTTPException):
            await voting.submit_vote(req, db)

        assert called is False

    @pytest.mark.asyncio
    async def test_correct_vote_rejects_when_zk_lock_exists(self, monkeypatch):
        monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
        monkeypatch.setenv("SERVER_SALT", "s" * 64)
        monkeypatch.setattr(voting, "verify_signature", lambda *_args: True)

        async def locked(*_args, **_kwargs):
            return True

        monkeypatch.setattr(voting, "tier1_vote_blocked_by_zk_lock", locked)
        req = voting.CorrectionRequest(
            nullifier_hash="a" * 64,
            bill_id="GR-0490a766",
            vote="YES",
            signature_hex="b" * 128,
        )
        bill = SimpleNamespace(id="GR-0490a766", status=BillStatus.WINDOW_24H)
        identity = SimpleNamespace(public_key_hex="c" * 64)
        existing_vote = SimpleNamespace(is_correction=False, vote=VoteChoice.NO)
        db = _FakeDb([bill, identity, existing_vote])

        with pytest.raises(HTTPException) as exc:
            await voting.correct_vote("GR-0490a766", req, db)

        assert exc.value.status_code == 409
        assert "Semaphore ZK" in exc.value.detail
        assert "FOR UPDATE" in str(db.executed[0])


class TestVoteEndpointStructure:
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Braucht laufende PostgreSQL — läuft in Docker CI")
    async def test_vote_route_exists(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/v1/vote", json={
                "nullifier_hash": "a" * 64,
                "bill_id": "GR-TEST",
                "vote": "YES",
                "signature_hex": "b" * 64,
            })
        assert r.status_code != 404

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Braucht laufende PostgreSQL — läuft in Docker CI")
    async def test_invalid_vote_choice(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/v1/vote", json={
                "nullifier_hash": "a" * 64,
                "bill_id": "GR-TEST",
                "vote": "INVALID_CHOICE",
                "signature_hex": "b" * 64,
            })
        assert r.status_code != 404

    @pytest.mark.asyncio
    async def test_health_includes_mod04(self):
        from httpx import AsyncClient, ASGITransport
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/health")
        assert any("MOD-04" in m for m in r.json()["modules"])
        assert any("MOD-14" in m for m in r.json()["modules"])
