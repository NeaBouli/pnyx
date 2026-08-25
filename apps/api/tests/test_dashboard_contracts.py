"""Regression tests for dashboard-to-API request contracts."""

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock

from models import GovernanceLevel
from routers.admin import BillCreateRequest, BillTextRequest, BillUpdateRequest, admin_stats
from routers.parliament import TransitionRequest


def test_transition_auth_is_not_duplicated_in_request_body():
    request = TransitionRequest(new_status="ACTIVE")

    assert request.new_status == "ACTIVE"
    assert "admin_key" not in request.model_dump()


def test_bill_text_is_read_from_json_body():
    assert BillTextRequest(text="  Κείμενο νομοσχεδίου  ").text.startswith("  ")

    with pytest.raises(ValidationError):
        BillTextRequest.model_validate({"text_el": "wrong field"})


def test_bill_create_preserves_dashboard_scope_without_editable_fetch_url():
    request = BillCreateRequest(
        id="GR-2026-0042",
        title_el="Τίτλος",
        governance_level="REGIONAL",
    )

    assert request.governance_level is GovernanceLevel.REGIONAL
    assert "parliament_url" not in BillCreateRequest.model_fields


def test_bill_update_accepts_dashboard_scope_without_editable_fetch_url():
    request = BillUpdateRequest(
        governance_level="MUNICIPAL",
    )

    assert request.governance_level is GovernanceLevel.MUNICIPAL
    assert "parliament_url" not in BillUpdateRequest.model_fields


@pytest.mark.asyncio
async def test_admin_stats_exposes_only_aggregate_identity_counts():
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[4, 3, 2, 7, 6, 1])

    result = await admin_stats(_key=True, db=db)

    assert result["total_identities"] == 7
    assert result["active_identities"] == 6
    assert result["revoked_identities"] == 1
    assert "identities" not in result
