from scripts.gh111_nullifier_v2_canary_check import (
    IdentityKdfSnapshot,
    evaluate_canary,
    evaluate_preflight,
    read_snapshot,
    write_report,
    write_snapshot,
)


def test_preflight_blocks_when_v2_rows_already_exist() -> None:
    snapshot = IdentityKdfSnapshot(
        kdf_env="v1",
        total=17,
        with_v2=1,
        version_v2=1,
        active=17,
        revoked=0,
    )

    assert evaluate_preflight(snapshot) == [
        "v2_rows_already_present",
        "version_v2_rows_already_present",
    ]


def test_preflight_blocks_inconsistent_or_malformed_v2_state() -> None:
    snapshot = IdentityKdfSnapshot(
        kdf_env="v1",
        total=17,
        with_v2=0,
        version_v2=0,
        active=17,
        revoked=0,
        active_with_v2=1,
        v2_without_version=1,
        version_without_v2=1,
        malformed_v2=1,
    )

    blockers = evaluate_preflight(snapshot)

    assert "active_v2_rows_already_present" in blockers
    assert "v2_hash_without_v2_version_present" in blockers
    assert "v2_version_without_v2_hash_present" in blockers
    assert "malformed_v2_hash_present" in blockers


def test_existing_reregistration_requires_same_identity_counts() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(
        kdf_env="v2",
        total=17,
        with_v2=1,
        version_v2=1,
        active=17,
        revoked=0,
        active_with_v2=1,
    )

    verdict = evaluate_canary(before, after, "existing-reregistration")

    assert verdict.ok is True
    assert verdict.blockers == []


def test_existing_reregistration_blocks_duplicate_identity_row() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(kdf_env="v2", total=18, with_v2=1, version_v2=1, active=18, revoked=0)

    verdict = evaluate_canary(before, after, "existing-reregistration")

    assert verdict.ok is False
    assert "existing_reregistration_changed_total_identity_rows" in verdict.blockers
    assert "existing_reregistration_changed_active_identity_rows" in verdict.blockers


def test_new_registration_requires_exactly_one_new_active_row() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(
        kdf_env="v2",
        total=18,
        with_v2=1,
        version_v2=1,
        active=18,
        revoked=0,
        active_with_v2=1,
    )

    verdict = evaluate_canary(before, after, "new-registration")

    assert verdict.ok is True
    assert verdict.blockers == []


def test_canary_blocks_when_v2_flag_not_observed_after_window() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=1, version_v2=1, active=17, revoked=0)

    verdict = evaluate_canary(before, after, "existing-reregistration")

    assert verdict.ok is False
    assert "after_kdf_env_not_v2" in verdict.blockers


def test_canary_requires_new_active_v2_identity() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(
        kdf_env="v2",
        total=17,
        with_v2=1,
        version_v2=1,
        active=17,
        revoked=0,
        active_with_v2=0,
    )

    verdict = evaluate_canary(before, after, "existing-reregistration")

    assert verdict.ok is False
    assert "no_new_active_v2_identity_observed" in verdict.blockers


def test_canary_blocks_inconsistent_or_malformed_v2_state() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(
        kdf_env="v2",
        total=17,
        with_v2=1,
        version_v2=1,
        active=17,
        revoked=0,
        active_with_v2=1,
        v2_without_version=1,
        version_without_v2=1,
        malformed_v2=1,
    )

    verdict = evaluate_canary(before, after, "existing-reregistration")

    assert verdict.ok is False
    assert "v2_hash_without_v2_version_present" in verdict.blockers
    assert "v2_version_without_v2_hash_present" in verdict.blockers
    assert "malformed_v2_hash_present" in verdict.blockers


def test_snapshot_output_stays_compatible_with_compare_input(tmp_path) -> None:
    snapshot = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    path = tmp_path / "before.json"

    write_snapshot(snapshot, path)

    assert read_snapshot(path) == snapshot


def test_old_snapshot_without_extended_fields_is_still_readable(tmp_path) -> None:
    path = tmp_path / "old_before.json"
    path.write_text(
        """
        {
          "active": 17,
          "kdf_env": "v1",
          "revoked": 0,
          "total": 17,
          "version_v2": 0,
          "with_v2": 0
        }
        """
    )

    snapshot = read_snapshot(path)

    assert snapshot.active_with_v2 == 0
    assert snapshot.v2_without_version == 0
    assert snapshot.version_without_v2 == 0
    assert snapshot.malformed_v2 == 0


def test_report_output_can_include_preflight_blockers(tmp_path) -> None:
    snapshot = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    path = tmp_path / "preflight_report.json"

    write_report(
        {
            "snapshot": snapshot.__dict__,
            "preflight_blockers": [],
        },
        path,
    )

    assert '"preflight_blockers": []' in path.read_text()
