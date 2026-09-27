"""Service tests for canonical citizen-action payloads, freshness and cutoff."""
import pytest

from services.citizen_action_integrity import (
    CITIZEN_ACTION_MAX_SKEW_MS_ENV,
    DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS,
    VOTE_STATUS_REQUIRE_SIGNED_ENV,
    build_flag_payload,
    build_vote_status_read_payload,
    citizen_action_max_skew_ms,
    citizen_action_timestamp_is_fresh,
    vote_status_require_signed,
)

NULLIFIER = "a" * 64
BILL = "GR-0490a766"
NOW = 1_788_000_000_000


def test_flag_payload_matches_mobile_golden_vector() -> None:
    assert build_flag_payload(BILL, NULLIFIER, NOW) == (
        f'flag:v1:["{BILL}","{NULLIFIER}",{NOW}]'
    )


def test_vote_status_read_payload_matches_mobile_golden_vector() -> None:
    assert build_vote_status_read_payload(BILL, NULLIFIER, NOW) == (
        f'vote-status-read:v1:["{BILL}","{NULLIFIER}",{NOW}]'
    )


def test_payloads_use_compact_utf8_json_without_normalization() -> None:
    ada_bill = "ADA-ΕΛ-1"
    assert build_vote_status_read_payload(ada_bill, NULLIFIER, NOW) == (
        f'vote-status-read:v1:["{ada_bill}","{NULLIFIER}",{NOW}]'
    )
    assert build_flag_payload(ada_bill, NULLIFIER, NOW).startswith("flag:v1:[")
    assert ", " not in build_flag_payload(ada_bill, NULLIFIER, NOW)


def test_max_skew_defaults_to_fifteen_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CITIZEN_ACTION_MAX_SKEW_MS_ENV, raising=False)
    assert citizen_action_max_skew_ms() == DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS == 900_000


def test_max_skew_accepts_configured_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CITIZEN_ACTION_MAX_SKEW_MS_ENV, "60000")
    assert citizen_action_max_skew_ms() == 60_000
    monkeypatch.setenv(CITIZEN_ACTION_MAX_SKEW_MS_ENV, "3600000")
    assert citizen_action_max_skew_ms() == 3_600_000


@pytest.mark.parametrize("raw", ["not-a-number", "", "59999", "3600001", "-1"])
def test_max_skew_falls_back_safely_on_invalid_config(
    monkeypatch: pytest.MonkeyPatch, raw: str,
) -> None:
    monkeypatch.setenv(CITIZEN_ACTION_MAX_SKEW_MS_ENV, raw)
    assert citizen_action_max_skew_ms() == DEFAULT_CITIZEN_ACTION_MAX_SKEW_MS


@pytest.mark.parametrize("offset", [0, -900_000, 900_000])
def test_freshness_accepts_timestamps_inside_window(
    monkeypatch: pytest.MonkeyPatch, offset: int,
) -> None:
    monkeypatch.delenv(CITIZEN_ACTION_MAX_SKEW_MS_ENV, raising=False)
    assert citizen_action_timestamp_is_fresh(NOW + offset, now_ms=NOW)


@pytest.mark.parametrize("offset", [-900_001, 900_001])
def test_freshness_rejects_stale_and_future_timestamps(
    monkeypatch: pytest.MonkeyPatch, offset: int,
) -> None:
    monkeypatch.delenv(CITIZEN_ACTION_MAX_SKEW_MS_ENV, raising=False)
    assert not citizen_action_timestamp_is_fresh(NOW + offset, now_ms=NOW)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_cutoff_parser_accepts_truthy_values(
    monkeypatch: pytest.MonkeyPatch, value: str,
) -> None:
    monkeypatch.setenv(VOTE_STATUS_REQUIRE_SIGNED_ENV, value)
    assert vote_status_require_signed()


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_cutoff_parser_accepts_explicit_false_values(
    monkeypatch: pytest.MonkeyPatch, value: str,
) -> None:
    monkeypatch.setenv(VOTE_STATUS_REQUIRE_SIGNED_ENV, value)
    assert not vote_status_require_signed()


@pytest.mark.parametrize("value", ["2", "ture", "disabled"])
def test_cutoff_parser_fails_closed_on_invalid_nonempty_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    value: str,
) -> None:
    monkeypatch.setenv(VOTE_STATUS_REQUIRE_SIGNED_ENV, value)
    assert vote_status_require_signed()
    assert VOTE_STATUS_REQUIRE_SIGNED_ENV in caplog.text
    assert "requiring signed vote-status reads" in caplog.text


def test_cutoff_parser_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VOTE_STATUS_REQUIRE_SIGNED_ENV, raising=False)
    assert not vote_status_require_signed()
