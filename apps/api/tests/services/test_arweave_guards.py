"""
Golden Path Regression Test: Arweave Archive Guards
Protects: bill_lifecycle.py — prevents invalid/incomplete bills from being archived
"""
import pytest
import sys
import os
from types import SimpleNamespace
from enum import Enum

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# Import the enum to match bill_lifecycle expectations
class BillStatus(str, Enum):
    ANNOUNCED = "ANNOUNCED"
    ACTIVE = "ACTIVE"
    WINDOW_24H = "WINDOW_24H"
    PARLIAMENT_VOTED = "PARLIAMENT_VOTED"
    OPEN_END = "OPEN_END"

from services.bill_lifecycle import is_arweave_eligible


def _bill(**kwargs):
    defaults = {
        "id": "GR-TEST",
        "source": "PARLIAMENT",
        "status": BillStatus.PARLIAMENT_VOTED,
        "party_votes_parliament": {"ND": "YES", "SYRIZA": "NO"},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestArweaveGuards:
    """Arweave must never archive incomplete or non-PARLIAMENT bills."""

    def test_diavgeia_never_archived(self):
        bill = _bill(source="DIAVGEIA")
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible
        assert "PARLIAMENT" in reason

    def test_parliament_voted_with_party_votes_eligible(self):
        bill = _bill()
        eligible, _ = is_arweave_eligible(bill)
        assert eligible

    def test_parliament_voted_without_party_votes_blocked(self):
        bill = _bill(party_votes_parliament=None)
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible
        assert "party_votes" in reason

    def test_open_end_without_party_votes_blocked(self):
        bill = _bill(status=BillStatus.OPEN_END, party_votes_parliament=None)
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible
        assert "party_votes" in reason

    def test_open_end_with_party_votes_eligible(self):
        bill = _bill(status=BillStatus.OPEN_END)
        eligible, _ = is_arweave_eligible(bill)
        assert eligible

    def test_active_not_eligible(self):
        bill = _bill(status=BillStatus.ACTIVE)
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible
        assert "not eligible" in reason

    def test_announced_not_eligible(self):
        bill = _bill(status=BillStatus.ANNOUNCED)
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible

    def test_window_24h_not_eligible(self):
        bill = _bill(status=BillStatus.WINDOW_24H)
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible

    def test_empty_party_votes_blocked(self):
        bill = _bill(party_votes_parliament={})
        eligible, reason = is_arweave_eligible(bill)
        assert not eligible
