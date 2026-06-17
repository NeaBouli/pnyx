from scripts.gh111_nullifier_v2_canary_check import (
    IdentityKdfSnapshot,
    evaluate_canary,
    evaluate_preflight,
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


def test_existing_reregistration_requires_same_identity_counts() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(kdf_env="v2", total=17, with_v2=1, version_v2=1, active=17, revoked=0)

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
    after = IdentityKdfSnapshot(kdf_env="v2", total=18, with_v2=1, version_v2=1, active=18, revoked=0)

    verdict = evaluate_canary(before, after, "new-registration")

    assert verdict.ok is True
    assert verdict.blockers == []


def test_canary_blocks_when_v2_flag_not_observed_after_window() -> None:
    before = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=0, version_v2=0, active=17, revoked=0)
    after = IdentityKdfSnapshot(kdf_env="v1", total=17, with_v2=1, version_v2=1, active=17, revoked=0)

    verdict = evaluate_canary(before, after, "existing-reregistration")

    assert verdict.ok is False
    assert "after_kdf_env_not_v2" in verdict.blockers
