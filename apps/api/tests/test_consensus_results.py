from datetime import datetime

import pytest
from fastapi import HTTPException

from routers.consensus_results import (
    K_ANONYMITY_MIN,
    _public_visibility_sql,
    _scope_sql,
    _view_payload,
    get_consensus_representation,
)


class _Result:
    def __init__(self, *, scalar=None, rows=None, one=None):
        self._scalar = scalar
        self._rows = rows or []
        self._one = one

    def scalar_one_or_none(self):
        return self._scalar

    def mappings(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def one(self):
        return self._one


class _Session:
    def __init__(self, results):
        self.results = list(results)
        self.params = []
        self.statements = []
        self.visibility_queries = []

    async def execute(self, statement, params=None):
        if " AS results_visible" in str(statement):
            self.visibility_queries.append(statement)
            return _Result(rows=[(bill_id, True) for bill_id in ("DIAV-1", "DIAV-2", "DIAV-3", "DIAV-OUTSIDE-LIMIT")])
        if str(statement).startswith("SELECT parliament_bills.id \n"):
            self.visibility_queries.append(statement)
            return _Result(rows=["DIAV-1", "DIAV-2", "DIAV-3"])
        self.statements.append(str(statement))
        self.params.append(params or {})
        return self.results.pop(0)


def test_scope_sql_keeps_geographic_views_separate():
    assert "governance_level = 'MUNICIPAL'" in _scope_sql("municipal")
    assert "dimos_id = :dimos_id" in _scope_sql("municipal")
    assert "governance_level = 'REGIONAL'" in _scope_sql("regional")
    assert "periferia_id = :periferia_id" in _scope_sql("regional")


def test_national_scope_excludes_institutional_and_unmapped_rows():
    predicate = _scope_sql("national")
    assert "INSTITUTIONAL" not in predicate
    assert "dimos_id IS NOT NULL" in predicate
    assert "periferia_id IS NOT NULL" in predicate


def test_view_payload_is_weighted_by_vote_count_and_aggregate_only():
    rows = [
        {
            "contributor_ids": ["DIAV-1", "DIAV-OUTSIDE-LIMIT"],
        "bill_id": "DIAV-1",
            "title_el": "Απόφαση 1",
            "governance_level": "MUNICIPAL",
            "dimos_id": 22,
            "periferia_id": 6,
            "org_label": "Δήμος",
            "diavgeia_ada": "ADA-1",
            "updated_at": datetime(2026, 7, 15),
            "consensus_score": 5.0,
            "consensus_count": 10,
            "total_bills": 2,
            "total_consensus_votes": 40,
            "weighted_score_sum": -100.0,
        },
        {
            "bill_id": "DIAV-2",
            "title_el": "Απόφαση 2",
            "governance_level": "MUNICIPAL",
            "dimos_id": 22,
            "periferia_id": 6,
            "org_label": "Δήμος",
            "diavgeia_ada": "ADA-2",
            "updated_at": datetime(2026, 7, 14),
            "consensus_score": -5.0,
            "consensus_count": 30,
            "total_bills": 2,
            "total_consensus_votes": 40,
            "weighted_score_sum": -100.0,
        },
    ]

    payload = _view_payload("municipal", rows)

    assert payload["weighted_score"] == -2.5
    assert payload["consensus_vote_count"] == 40
    assert payload["bill_count"] == 2
    assert "nullifier_hash" not in str(payload)
    assert "identity" not in str(payload)


def test_missing_region_returns_unavailable_empty_view():
    assert _view_payload("regional", [], available=False) == {
        "view": "regional",
        "available": False,
        "bill_count": 0,
        "consensus_vote_count": 0,
        "weighted_score": None,
        "bills": [],
    }


def test_national_scope_does_not_claim_institutional_coverage():
    predicate = _scope_sql("national")
    assert "governance_level = 'NATIONAL'" in predicate
    assert "governance_level = 'INSTITUTIONAL'" not in predicate


def test_public_visibility_guard_matches_sensitive_diavgeia_policy():
    predicate, params = _public_visibility_sql()

    assert "admin_hidden" in predicate
    assert "coalesce(pb.sensitive_override, pb.sensitive_public_block) IS NOT true" in predicate
    assert "summary_" not in predicate and "public_bill_sensitive" not in predicate
    assert not params  # The fixed predicate must match the partial index under generic plans.


@pytest.mark.asyncio
async def test_representation_rejects_mismatched_dimos_and_periferia():
    db = _Session([_Result(scalar=1), _Result(scalar=6)])

    with pytest.raises(HTTPException) as exc_info:
        await get_consensus_representation(dimos_id=22, periferia_id=7, limit=20, db=db)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_representation_endpoint_keeps_views_separate_and_public():
    coverage = {
        "total_diavgeia_bills": 3,
        "geographically_represented_bills": 2,
        "institutional_or_unresolved_bills": 1,
        "geographic_mapping_gaps": 0,
    }
    row = {
        "contributor_ids": ["DIAV-1", "DIAV-OUTSIDE-LIMIT"],
        "bill_id": "DIAV-1",
        "title_el": "Απόφαση 1",
        "governance_level": "MUNICIPAL",
        "dimos_id": 22,
        "periferia_id": 6,
        "org_label": "Δήμος",
        "diavgeia_ada": "ADA-1",
        "updated_at": datetime(2026, 7, 15),
        "consensus_score": 3.0,
        "consensus_count": 2,
        "total_bills": 1,
        "total_consensus_votes": 2,
        "weighted_score_sum": 6.0,
    }
    db = _Session([
        _Result(scalar=1),
        _Result(scalar=6),
        _Result(one=coverage),
        _Result(rows=[row]),
        _Result(rows=[]),
        _Result(rows=[row]),
    ])

    result = await get_consensus_representation(
        dimos_id=22, periferia_id=6, limit=20, db=db,
    )

    assert result["privacy"] == "aggregate_only"
    assert result["minimum_group_size"] == K_ANONYMITY_MIN
    assert result["views"]["municipal"]["bill_count"] == 1
    assert result["views"]["regional"]["bill_count"] == 0
    assert result["views"]["national"]["consensus_vote_count"] == 2
    assert result["coverage"]["complete_geographic_representation"] is False
    assert len(db.visibility_queries) == 2  # Provenance at fill, fresh authorization at serve.
    assert all("sensitive_term_0" not in params for params in db.params[2:])
    assert all(params["k_anonymity_min"] == K_ANONYMITY_MIN for params in db.params[3:])
    assert all("HAVING COUNT(*) >= :k_anonymity_min" in statement for statement in db.statements[3:])
