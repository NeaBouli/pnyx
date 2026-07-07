import importlib.util
from datetime import datetime
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "backfill_parliament_metadata_summaries.py"
)
spec = importlib.util.spec_from_file_location("backfill_parliament_metadata_summaries", SCRIPT_PATH)
backfill = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(backfill)


def test_metadata_summary_is_deterministic_and_non_interpretive():
    summary = backfill.build_metadata_summary(
        title_el="  Κώδικας   Τοπικής Αυτοδιοίκησης  ",
        submitted_date=datetime(2026, 6, 24, 12, 0),
        vote_date="2026-06-25T00:00:00+00:00",
    )

    assert "Η Βουλή δημοσίευσε εγγραφή για: Κώδικας Τοπικής Αυτοδιοίκησης." in summary
    assert "Ημερομηνία κατάθεσης: 24/06/2026" in summary
    assert "Ημερομηνία συζήτησης/ψήφισης: 25/06/2026" in summary
    assert "επίσημα έγγραφα της Βουλής" in summary
    assert "ρυθμίζει" not in summary
    assert "αποσκοπεί" not in summary


def test_metadata_pill_uses_title_only_and_truncates():
    title = "Α" * 220

    pill = backfill.build_metadata_pill(title_el=title)

    assert len(pill) == 200
    assert pill.endswith("…")


def test_row_action_only_fills_empty_fields():
    row = {"summary_short_el": "υπάρχει", "pill_el": " "}

    assert backfill.row_action(row) == (False, True)


class FakeConn:
    def __init__(self):
        self.calls = []

    async def execute(self, query, *params):
        self.calls.append((query, params))
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_apply_update_is_scoped_to_parliament_and_empty_fields_only():
    conn = FakeConn()
    row = {"id": "GR-test"}

    result = await backfill.apply_update(conn, row, "summary", "pill")

    assert result == "UPDATE 1"
    query, params = conn.calls[0]
    assert "source = 'PARLIAMENT'" in query
    assert "summary_short_el IS NULL OR btrim(summary_short_el) = ''" in query
    assert "pill_el IS NULL OR btrim(pill_el) = ''" in query
    assert params == ("summary", "pill", "GR-test")
