"""
Tests für MOD-04 CitizenVote + MOD-05 Divergence Score
Keine DB nötig — alle Algorithmus-Tests sind rein.
"""
import pytest
from routers.voting import compute_divergence


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
        assert "MOD-04 CitizenVote" in r.json()["modules"]
        assert "MOD-14 Relevance" in r.json()["modules"]
