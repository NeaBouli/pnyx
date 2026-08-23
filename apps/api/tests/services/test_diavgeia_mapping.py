"""Regression tests for deterministic municipality-to-Diavgeia matching."""

from __future__ import annotations

import copy

import pytest

from scripts.audit_diavgeia_mappings import build_audit_rows
from scripts.seed_diavgeia_orgs import load_snapshot, normalize_subsidiary_label
from services.diavgeia_mapping import (
    DimosRecord,
    is_strict_municipality,
    normalize_greek,
    propose_primary_mappings,
)


def _snapshot_orgs() -> list[dict]:
    return load_snapshot(None)["organizations"]


def _records() -> list[DimosRecord]:
    return [
        DimosRecord(19, "Ηρακλείου", 5),
        DimosRecord(42, "Αγίας Παρασκευής", 1),
        DimosRecord(44, "Ηρακλείου", 1),
        DimosRecord(59, "Αγίας Βαρβάρας", 1),
        DimosRecord(144, "Αγιάς", 4),
        DimosRecord(183, "Αγίου Νικολάου", 5),
        DimosRecord(286, "Δυτικής Λέσβου", 12),
        DimosRecord(290, "Ανατολικής Σάμου", 12),
        DimosRecord(291, "Δυτικής Σάμου", 12),
        DimosRecord(307, "Ίου", 13),
    ]


def test_normalization_handles_separators_prefix_typo_and_latin_homoglyph() -> None:
    assert normalize_greek("ΔΗΜΟΣ  Νέας-Φιλαδελφείας") == "ΝΕΑΣ ΦΙΛΑΔΕΛΦΕΙΑΣ"
    assert normalize_greek("ΔΗΜΟ ΑΡΓΟΥΣ ΟΡΕΣΤΙΚΟΥ") == "ΑΡΓΟΥΣ ΟΡΕΣΤΙΚΟΥ"
    assert normalize_greek("ΔΗΜΟΣ AΓΙΟΥ ΝΙΚΟΛΑΟΥ") == "ΑΓΙΟΥ ΝΙΚΟΛΑΟΥ"


def test_primary_normalization_does_not_change_legacy_subsidiary_matching() -> None:
    compact = "Δάφνης-Υμηττού"
    spaced = "ΔΑΦΝΗΣ - ΥΜΗΤΤΟΥ"
    assert normalize_greek(compact) == normalize_greek(spaced)
    assert normalize_subsidiary_label(compact) not in normalize_subsidiary_label(spaced)


def test_strict_candidate_filter_rejects_misclassified_non_municipality() -> None:
    bad = {
        "uid": "100072229",
        "label": "ΕΝΕΡΓΕΙΑΚΗ ΚΟΙΝΟΤΗΤΑ ΑΓΡΙΝΙΟΥ ΣΥΝ ΠΕ",
        "category": "MUNICIPALITY",
        "is_primary": True,
        "status": "active",
    }
    assert is_strict_municipality(bad) is False


def test_known_collision_and_split_corrections_are_exact() -> None:
    proposals = propose_primary_mappings(_records(), _snapshot_orgs())
    by_id = {proposal.dimos_id: proposal for proposal in proposals}

    assert by_id[19].org_uid == "6325"  # Heraklion, Crete
    assert by_id[44].org_uid == "6109"  # Irakleio, Attica
    assert by_id[42].org_uid == "6005"
    assert by_id[59].org_uid == "6004"
    assert by_id[286].org_uid == "100049040"
    assert by_id[290].org_uid == "100049544"
    assert by_id[291].org_uid == "100049554"
    assert by_id[307].org_uid == "6120"
    assert by_id[144].org_uid == "6003"  # Αγιάς must not become Αγίας ...
    assert by_id[183].org_uid == "6195"  # Snapshot contains a Latin A homoglyph.


def test_renames_resolve_but_corfu_split_stays_manual_review() -> None:
    dimoi = [
        DimosRecord(32, "Κερκυραίων", 11),
        DimosRecord(157, "Καλαμπάκας", 4),
        DimosRecord(251, "Ορεστίδος", 9),
        DimosRecord(261, "Μώλου-Αγ.Κωνσταντίνου", 10),
    ]
    by_id = {item.dimos_id: item for item in propose_primary_mappings(dimoi, _snapshot_orgs())}

    assert by_id[32].status == "manual_review"
    assert by_id[32].org_uid is None
    assert by_id[157].org_uid == "100062933"
    assert by_id[251].org_uid == "6226"
    assert by_id[261].org_uid == "6202"


def test_reviewed_name_variants_use_guarded_catalog_entries() -> None:
    dimoi = [
        DimosRecord(7, "Ηλιουπόλεως", 1),
        DimosRecord(8, "Νίκαιας-Αγ.Ι.Ρέντη", 1),
        DimosRecord(47, "Μεταμορφώσεως", 1),
        DimosRecord(52, "Ψυχικού", 1),
        DimosRecord(72, "Σαλαμίνος", 1),
        DimosRecord(131, "Μεσολογγίου", 3),
        DimosRecord(170, "Μινώα Πεδιάδος", 5),
        DimosRecord(175, "Κανδάνου-Σελίνου", 5),
        DimosRecord(262, "Στυλίδος", 10),
        DimosRecord(266, "Αλιάρτου-Θεσπιέων", 10),
        DimosRecord(276, "Μαντουδίου-Λίμνης-Αγ.Άννας", 10),
        DimosRecord(297, "Νάξου και Μικρών Κυκλάδων", 13),
    ]
    by_id = {item.dimos_id: item for item in propose_primary_mappings(dimoi, _snapshot_orgs())}

    assert {dimos_id: item.org_uid for dimos_id, item in by_id.items()} == {
        7: "6107",
        8: "6215",
        47: "6191",
        52: "6322",
        72: "6266",
        131: "6119",
        170: "6194",
        175: "6134",
        262: "6289",
        266: "6020",
        276: "6182",
        297: "6203",
    }
    assert all(item.source == "catalog" for item in by_id.values())
    assert all(item.needs_review is False for item in by_id.values())


def test_matching_is_independent_of_snapshot_order() -> None:
    orgs = _snapshot_orgs()
    forward = propose_primary_mappings(_records(), orgs)
    reverse = propose_primary_mappings(_records(), list(reversed(orgs)))
    assert forward == reverse


def test_override_guards_fail_closed() -> None:
    invalid = {
        19: {
            "dimos_id": 19,
            "expected_name_el": "Ηρακλείου",
            "expected_periferia_id": 5,
            "target_uid": "does-not-exist",
        }
    }
    with pytest.raises(ValueError, match="not an active strict municipality"):
        propose_primary_mappings([DimosRecord(19, "Ηρακλείου", 5)], _snapshot_orgs(), overrides=invalid)


def test_duplicate_primary_uid_assignment_fails_closed() -> None:
    orgs = [
        {
            "uid": "1",
            "label": "ΔΗΜΟΣ ΔΟΚΙΜΗΣ",
            "category": "MUNICIPALITY",
            "is_primary": True,
            "status": "active",
        }
    ]
    dimoi = [DimosRecord(900, "Δοκιμής", 1), DimosRecord(901, "Δοκιμής", 2)]
    with pytest.raises(ValueError, match="one Diavgeia UID to multiple dimoi"):
        propose_primary_mappings(dimoi, orgs, overrides={})


def test_invalid_threshold_fails_closed() -> None:
    with pytest.raises(ValueError, match="threshold"):
        propose_primary_mappings([], [], threshold=1.01, overrides={})


def test_audit_reports_changes_without_mutating_input() -> None:
    proposals = propose_primary_mappings(
        [DimosRecord(19, "Ηρακλείου", 5), DimosRecord(32, "Κερκυραίων", 11)],
        _snapshot_orgs(),
    )
    mappings = [
        {
            "dimos_id": "19",
            "diavgeia_uid": "6109",
            "org_label": "ΔΗΜΟΣ ΗΡΑΚΛΕΙΟΥ",
            "is_primary": "t",
        }
    ]
    original = copy.deepcopy(mappings)

    rows, summary = build_audit_rows(proposals, mappings)

    assert mappings == original
    assert {row["dimos_id"]: row["action"] for row in rows} == {
        19: "correct_primary",
        32: "manual_review",
    }
    assert summary["mode"] == "read_only"
    assert summary["review_gate"] == "explicit_approval_required_before_database_write"


@pytest.mark.parametrize(
    "mappings",
    [
        [],
        [
            {
                "dimos_id": "999",
                "diavgeia_uid": "9999",
                "org_label": "ΔΗΜΟΣ ΔΟΚΙΜΗΣ - ΑΓΙΟΥ ΠΑΡΑΔΕΙΓΜΑΤΟΣ",
                "is_primary": "t",
            }
        ],
        [
            {
                "dimos_id": "999",
                "diavgeia_uid": "8888",
                "org_label": "ΔΗΜΟΣ ΠΑΛΑΙΑΣ ΔΟΚΙΜΗΣ",
                "is_primary": "t",
            }
        ],
    ],
    ids=["would_add", "would_remain_unchanged", "would_correct"],
)
def test_audit_withholds_review_required_fuzzy_match_from_apply_actions(
    mappings: list[dict[str, str]],
) -> None:
    proposals = propose_primary_mappings(
        [DimosRecord(999, "Δοκιμής-Αγ.Παραδείγματος", 1)],
        [
            {
                "uid": "9999",
                "label": "ΔΗΜΟΣ ΔΟΚΙΜΗΣ - ΑΓΙΟΥ ΠΑΡΑΔΕΙΓΜΑΤΟΣ",
                "category": "MUNICIPALITY",
                "is_primary": True,
                "status": "active",
            }
        ],
        overrides={},
    )
    assert proposals[0].status == "matched"
    assert proposals[0].needs_review is True

    rows, summary = build_audit_rows(proposals, mappings)

    assert rows[0]["action"] == "manual_review"
    assert summary["actions"] == {"manual_review": 1}


def test_audit_blocks_primary_uid_owned_by_another_municipality() -> None:
    proposals = propose_primary_mappings(
        [DimosRecord(19, "Ηρακλείου", 5)],
        _snapshot_orgs(),
    )
    mappings = [
        {
            "dimos_id": "999",
            "diavgeia_uid": "6325",
            "org_label": "ΔΗΜΟΣ ΗΡΑΚΛΕΙΟΥ (ΚΡΗΤΗΣ)",
            "is_primary": "t",
        }
    ]

    rows, _ = build_audit_rows(proposals, mappings)

    assert rows[0]["action"] == "blocked_primary_uid_owned"
    assert rows[0]["conflicting_primary_dimos_ids"] == "999"


def test_audit_allows_uid_when_current_owner_moves_away_in_same_plan() -> None:
    proposals = propose_primary_mappings(
        [
            DimosRecord(19, "Ηρακλείου", 5),
            DimosRecord(44, "Ηρακλείου", 1),
        ],
        _snapshot_orgs(),
    )
    mappings = [
        {
            "dimos_id": "19",
            "diavgeia_uid": "6109",
            "org_label": "ΔΗΜΟΣ ΗΡΑΚΛΕΙΟΥ",
            "is_primary": "t",
        }
    ]

    rows, _ = build_audit_rows(proposals, mappings)
    by_id = {row["dimos_id"]: row for row in rows}

    assert by_id[19]["action"] == "correct_primary"
    assert by_id[44]["action"] == "add_primary"


def test_audit_blocks_uid_when_current_owner_has_no_accepted_move() -> None:
    proposals = propose_primary_mappings(
        [
            DimosRecord(19, "Ηρακλείου", 5),
            DimosRecord(32, "Κερκυραίων", 11),
        ],
        _snapshot_orgs(),
    )
    mappings = [
        {
            "dimos_id": "32",
            "diavgeia_uid": "6325",
            "org_label": "ΔΗΜΟΣ ΗΡΑΚΛΕΙΟΥ (ΚΡΗΤΗΣ)",
            "is_primary": "t",
        }
    ]

    rows, _ = build_audit_rows(proposals, mappings)
    by_id = {row["dimos_id"]: row for row in rows}

    assert by_id[19]["action"] == "blocked_primary_uid_owned"
    assert by_id[19]["conflicting_primary_dimos_ids"] == "32"
    assert by_id[32]["action"] == "manual_review"
