import logging

import pytest

import hlr


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    response_payload: dict = {}
    requests: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        return FakeResponse(self.response_payload)


@pytest.fixture(autouse=True)
def primary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HLRLOOKUP_API_KEY", raising=False)
    monkeypatch.delenv("HLRLOOKUP_API_SECRET", raising=False)
    monkeypatch.delenv("HLRLOOKUPS_API_KEY", raising=False)
    monkeypatch.delenv("HLRLOOKUPS_API_SECRET", raising=False)
    monkeypatch.setenv("HLR_FALLBACK_API_KEY", "test-key")
    monkeypatch.setenv("HLR_FALLBACK_API_SECRET", "test-secret")
    monkeypatch.setattr(hlr.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.requests = []
    FakeAsyncClient.response_payload = {
        "results": [{
            "error": "NONE",
            "live_status": "LIVE",
            "telephone_number_type": "MOBILE",
            "original_network_details": {"country_iso3": "GRC", "name": "Test GR"},
            "current_network_details": {"country_iso3": "GRC", "name": "Test GR"},
        }]
    }


@pytest.mark.asyncio
async def test_primary_request_uses_digits_only_and_bypasses_cache() -> None:
    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is True
    request = FakeAsyncClient.requests[0]
    assert request["url"] == hlr.HLRLOOKUP_COM_URL
    assert request["json"]["requests"] == [{
        "telephone_number": "306912345678",
        "cache_days_private": 0,
        "cache_days_global": 0,
        "save_to_cache": "NO",
    }]


@pytest.mark.asyncio
async def test_primary_rejects_confirmed_dead_mobile() -> None:
    FakeAsyncClient.response_payload["results"][0]["live_status"] = "DEAD"

    result = await hlr.hlr_lookup_hlrlookupcom("6912345678")

    assert result["valid"] is False
    assert result["status"] == "DEAD"
    assert result["number_type"] == "MOBILE"
    assert result["error"] == "Ο αριθμός δεν είναι ενεργός ελληνικός αριθμός κινητού"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", sorted(hlr._PRIMARY_INDETERMINATE_STATUSES))
async def test_primary_marks_indeterminate_mobile_as_temporarily_unverified(
    status: str,
) -> None:
    FakeAsyncClient.response_payload["results"][0]["live_status"] = status

    result = await hlr.hlr_lookup_hlrlookupcom("00306912345678")

    assert result["valid"] is False
    assert result["status"] == status
    assert result["number_type"] == "MOBILE"
    assert "προσωρινά" in result["error"]


@pytest.mark.asyncio
async def test_primary_rejects_live_landline() -> None:
    FakeAsyncClient.response_payload["results"][0]["telephone_number_type"] = "FIXED_LINE"

    result = await hlr.hlr_lookup_hlrlookupcom("6912345678")

    assert result["valid"] is False
    assert result["status"] == "LIVE"
    assert result["number_type"] == "FIXED_LINE"


@pytest.mark.asyncio
async def test_fallback_accepts_connected_greek_mobile(monkeypatch) -> None:
    monkeypatch.setenv("HLRLOOKUPS_API_KEY", "test-fallback-key")
    monkeypatch.setenv("HLRLOOKUPS_API_SECRET", "test-fallback-secret")
    FakeAsyncClient.response_payload = {
        "connectivity_status": "CONNECTED",
        "original_network_name": "Test GR",
        "original_country_code": "GR",
    }

    result = await hlr.hlr_lookup("+306912345678")

    assert result["valid"] is True
    assert result["status"] == "CONNECTED"
    assert result["error"] is None
    request = FakeAsyncClient.requests[0]
    assert request["url"] == hlr.HLR_LOOKUPS_URL
    assert request["json"] == {"msisdn": "+306912345678"}
    assert request["auth"] == ("test-fallback-key", "test-fallback-secret")


@pytest.mark.asyncio
@pytest.mark.parametrize("connectivity_status", ["ABSENT", "INVALID_MSISDN", "UNDETERMINED"])
async def test_fallback_rejects_unverified_mobile_status(
    monkeypatch, connectivity_status: str
) -> None:
    monkeypatch.setenv("HLRLOOKUPS_API_KEY", "test-fallback-key")
    monkeypatch.setenv("HLRLOOKUPS_API_SECRET", "test-fallback-secret")
    FakeAsyncClient.response_payload = {
        "connectivity_status": connectivity_status,
        "original_network_name": "Test GR",
        "original_country_code": "GR",
    }

    result = await hlr.hlr_lookup("6912345678")

    assert result["valid"] is False
    assert result["status"] == connectivity_status
    if connectivity_status in hlr._FALLBACK_RETRYABLE_STATUSES:
        assert "προσωρινά" in result["error"]
    else:
        assert "έγκυρος" in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_status", sorted(hlr._PRIMARY_INDETERMINATE_STATUSES))
async def test_indeterminate_primary_uses_configured_fallback(
    monkeypatch, primary_status: str
) -> None:
    primary = {
        "valid": False,
        "status": primary_status,
        "number_type": "MOBILE",
        "error": "temporary",
    }
    fallback = {
        "valid": True,
        "status": "CONNECTED",
        "network": "Fallback GR",
        "country": "GR",
        "error": None,
    }
    fallback_calls: list[str] = []
    state_calls: list[str] = []

    async def fake_primary(phone: str) -> dict:
        return primary

    async def fake_fallback(phone: str) -> dict:
        fallback_calls.append(phone)
        return fallback

    async def enough_credits() -> int:
        return 100

    async def fake_publish_failover_state(reason: str) -> None:
        state_calls.append(reason)

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "true")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "hlr_lookup", fake_fallback)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", enough_credits)
    monkeypatch.setattr(hlr, "_publish_failover_state", fake_publish_failover_state)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is True
    assert result["status"] == "CONNECTED"
    assert result["_providers_queried"] == ["primary", "fallback"]
    assert fallback_calls == ["+306912345678"]
    assert state_calls == [f"indeterminate_status ({primary_status})"]


@pytest.mark.asyncio
async def test_confirmed_dead_primary_does_not_use_fallback(monkeypatch) -> None:
    fallback_calls: list[str] = []
    state_calls: list[str] = []

    async def fake_primary(phone: str) -> dict:
        return {"valid": False, "status": "DEAD", "error": "dead"}

    async def fake_fallback(phone: str) -> dict:
        fallback_calls.append(phone)
        return {"valid": True, "status": "CONNECTED"}

    async def enough_credits() -> int:
        return 100

    async def fake_publish_failover_state(reason: str) -> None:
        state_calls.append(reason)

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "true")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "hlr_lookup", fake_fallback)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", enough_credits)
    monkeypatch.setattr(hlr, "_publish_failover_state", fake_publish_failover_state)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "DEAD"
    assert result["_providers_queried"] == ["primary"]
    assert fallback_calls == []
    assert state_calls == []


@pytest.mark.asyncio
async def test_indeterminate_primary_without_fallback_stays_rejected(monkeypatch) -> None:
    async def fake_primary(phone: str) -> dict:
        return {
            "valid": False,
            "status": "NO_COVERAGE",
            "number_type": "MOBILE",
            "error": "temporary",
        }

    async def enough_credits() -> int:
        return 100

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "false")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", enough_credits)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is False
    assert result["error"] == "temporary"
    assert result["_providers_queried"] == ["primary"]


@pytest.mark.asyncio
async def test_indeterminate_fallback_rejection_stays_rejected(monkeypatch) -> None:
    async def fake_primary(phone: str) -> dict:
        return {
            "valid": False,
            "status": "INCONCLUSIVE",
            "number_type": "MOBILE",
            "error": "temporary",
        }

    async def fake_fallback(phone: str) -> dict:
        return {"valid": False, "status": "NOT_CONNECTED", "error": "not active"}

    async def enough_credits() -> int:
        return 100

    async def fake_publish_failover_state(reason: str) -> None:
        return None

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "true")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "hlr_lookup", fake_fallback)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", enough_credits)
    monkeypatch.setattr(hlr, "_publish_failover_state", fake_publish_failover_state)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "NOT_CONNECTED"
    assert result["_providers_queried"] == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_unconfigured_fallback_is_not_counted_as_queried(monkeypatch) -> None:
    async def fake_primary(phone: str) -> dict:
        return {
            "valid": False,
            "status": "INCONCLUSIVE",
            "number_type": "MOBILE",
            "error": "temporary",
        }

    async def fake_fallback(phone: str) -> dict:
        return {
            "valid": False,
            "status": "FALLBACK_NOT_CONFIGURED",
            "error": "not configured",
        }

    async def enough_credits() -> int:
        return 100

    async def fake_publish_failover_state(reason: str) -> None:
        return None

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "true")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "hlr_lookup", fake_fallback)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", enough_credits)
    monkeypatch.setattr(hlr, "_publish_failover_state", fake_publish_failover_state)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "INCONCLUSIVE"
    assert result["_providers_queried"] == ["primary"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_status", ["ERROR", "TIMEOUT"])
async def test_failed_fallback_is_still_counted_as_queried(
    monkeypatch, fallback_status: str
) -> None:
    async def fake_primary(phone: str) -> dict:
        return {
            "valid": False,
            "status": "INCONCLUSIVE",
            "number_type": "MOBILE",
            "error": "temporary",
        }

    async def fake_fallback(phone: str) -> dict:
        return {
            "valid": False,
            "status": fallback_status,
            "error": "provider error",
        }

    async def enough_credits() -> int:
        return 100

    async def fake_publish_failover_state(reason: str) -> None:
        return None

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "true")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "hlr_lookup", fake_fallback)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", enough_credits)
    monkeypatch.setattr(hlr, "_publish_failover_state", fake_publish_failover_state)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "INCONCLUSIVE"
    assert result["_providers_queried"] == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_valid_primary_is_not_overridden_when_credits_are_low(monkeypatch) -> None:
    fallback_calls: list[str] = []

    async def fake_primary(phone: str) -> dict:
        return {
            "valid": True,
            "status": "LIVE",
            "number_type": "MOBILE",
            "error": None,
        }

    async def fake_fallback(phone: str) -> dict:
        fallback_calls.append(phone)
        return {"valid": False, "status": "NOT_CONNECTED"}

    async def low_credits() -> int:
        return 10

    async def fake_publish_failover_state(reason: str) -> None:
        return None

    monkeypatch.setenv("HLR_FALLBACK_ENABLED", "true")
    monkeypatch.setattr(hlr, "hlr_lookup_hlrlookupcom", fake_primary)
    monkeypatch.setattr(hlr, "hlr_lookup", fake_fallback)
    monkeypatch.setattr(hlr, "_get_primary_credits_remaining", low_credits)
    monkeypatch.setattr(hlr, "_publish_failover_state", fake_publish_failover_state)

    result = await hlr.verify_greek_number("+306912345678")

    assert result["valid"] is True
    assert result["_providers_queried"] == ["primary"]
    assert fallback_calls == []


# ── EKA-17: canonical primary credential names with legacy aliases ───────────

@pytest.fixture
def reset_credential_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hlr, "_legacy_primary_env_warned", False)
    monkeypatch.setattr(hlr, "_incomplete_canonical_env_warned", False)
    monkeypatch.setattr(hlr, "_incomplete_legacy_env_warned", False)


@pytest.mark.asyncio
async def test_primary_uses_canonical_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HLRLOOKUP_API_KEY", "canonical-key")
    monkeypatch.setenv("HLRLOOKUP_API_SECRET", "canonical-secret")

    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is True
    request = FakeAsyncClient.requests[0]
    assert request["json"]["api_key"] == "canonical-key"
    assert request["json"]["api_secret"] == "canonical-secret"


@pytest.mark.asyncio
async def test_primary_legacy_alias_credentials_still_work() -> None:
    # Autouse fixture sets only HLR_FALLBACK_API_KEY/HLR_FALLBACK_API_SECRET.
    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is True
    request = FakeAsyncClient.requests[0]
    assert request["json"]["api_key"] == "test-key"
    assert request["json"]["api_secret"] == "test-secret"


@pytest.mark.asyncio
async def test_canonical_credentials_take_precedence_over_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HLRLOOKUP_API_KEY", "canonical-key")
    monkeypatch.setenv("HLRLOOKUP_API_SECRET", "canonical-secret")

    await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    request = FakeAsyncClient.requests[0]
    assert request["json"]["api_key"] == "canonical-key"
    assert request["json"]["api_secret"] == "canonical-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configured_name",
    ("HLRLOOKUP_API_KEY", "HLRLOOKUP_API_SECRET"),
)
async def test_incomplete_canonical_pair_fails_closed_instead_of_mixing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    reset_credential_warnings: None,
    configured_name: str,
) -> None:
    monkeypatch.delenv("HLRLOOKUP_API_KEY", raising=False)
    monkeypatch.delenv("HLRLOOKUP_API_SECRET", raising=False)
    monkeypatch.setenv(configured_name, "canonical-part-sentinel")
    caplog.set_level(logging.INFO, logger="hlr")

    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "NOT_CONFIGURED"
    assert FakeAsyncClient.requests == []
    assert "canonical-part-sentinel" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configured_name",
    ("HLR_FALLBACK_API_KEY", "HLR_FALLBACK_API_SECRET"),
)
async def test_incomplete_legacy_pair_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    reset_credential_warnings: None,
    configured_name: str,
) -> None:
    monkeypatch.delenv("HLR_FALLBACK_API_KEY", raising=False)
    monkeypatch.delenv("HLR_FALLBACK_API_SECRET", raising=False)
    monkeypatch.setenv(configured_name, "legacy-part-sentinel")
    caplog.set_level(logging.INFO, logger="hlr")

    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "NOT_CONFIGURED"
    assert FakeAsyncClient.requests == []
    assert "legacy-part-sentinel" not in caplog.text


@pytest.mark.asyncio
async def test_fallback_env_names_never_configure_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HLR_FALLBACK_API_KEY", raising=False)
    monkeypatch.delenv("HLR_FALLBACK_API_SECRET", raising=False)
    monkeypatch.delenv("HLRLOOKUP_API_KEY", raising=False)
    monkeypatch.delenv("HLRLOOKUP_API_SECRET", raising=False)
    monkeypatch.setenv("HLRLOOKUPS_API_KEY", "fallback-key")
    monkeypatch.setenv("HLRLOOKUPS_API_SECRET", "fallback-secret")

    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "NOT_CONFIGURED"
    assert FakeAsyncClient.requests == []


@pytest.mark.asyncio
async def test_missing_primary_credentials_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "HLRLOOKUP_API_KEY",
        "HLRLOOKUP_API_SECRET",
        "HLR_FALLBACK_API_KEY",
        "HLR_FALLBACK_API_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "NOT_CONFIGURED"
    assert FakeAsyncClient.requests == []


@pytest.mark.asyncio
async def test_canonical_primary_does_not_configure_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HLRLOOKUP_API_KEY", "canonical-key")
    monkeypatch.setenv("HLRLOOKUP_API_SECRET", "canonical-secret")
    monkeypatch.delenv("HLRLOOKUPS_API_KEY", raising=False)
    monkeypatch.delenv("HLRLOOKUPS_API_SECRET", raising=False)

    result = await hlr.hlr_lookup("+306912345678")

    assert result["valid"] is False
    assert result["status"] == "FALLBACK_NOT_CONFIGURED"
    assert FakeAsyncClient.requests == []


@pytest.mark.asyncio
async def test_legacy_alias_logs_single_deprecation_warning_without_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    reset_credential_warnings: None,
) -> None:
    monkeypatch.setenv("HLR_FALLBACK_API_KEY", "legacy-key-sentinel")
    monkeypatch.setenv("HLR_FALLBACK_API_SECRET", "legacy-secret-sentinel")
    caplog.set_level(logging.INFO, logger="hlr")

    await hlr.hlr_lookup_hlrlookupcom("+306912345678")
    await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "deprecated env names" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert "HLRLOOKUP_API_KEY" in warnings[0]
    assert "HLR_FALLBACK_API_KEY" in warnings[0]
    assert "legacy-key-sentinel" not in caplog.text
    assert "legacy-secret-sentinel" not in caplog.text


@pytest.mark.asyncio
async def test_no_secret_values_logged_in_any_primary_config(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    reset_credential_warnings: None,
) -> None:
    caplog.set_level(logging.INFO, logger="hlr")
    sentinels = ("canon-key-sentinel", "canon-secret-sentinel",
                 "leg-key-sentinel", "leg-secret-sentinel")
    monkeypatch.setenv("HLRLOOKUP_API_KEY", sentinels[0])
    monkeypatch.setenv("HLRLOOKUP_API_SECRET", sentinels[1])
    monkeypatch.setenv("HLR_FALLBACK_API_KEY", sentinels[2])
    monkeypatch.setenv("HLR_FALLBACK_API_SECRET", sentinels[3])

    # Configured path (canonical precedence, no legacy warning).
    await hlr.hlr_lookup_hlrlookupcom("+306912345678")
    # Missing-credentials path.
    for name in ("HLRLOOKUP_API_KEY", "HLRLOOKUP_API_SECRET",
                 "HLR_FALLBACK_API_KEY", "HLR_FALLBACK_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    result = await hlr.hlr_lookup_hlrlookupcom("+306912345678")

    assert result["status"] == "NOT_CONFIGURED"
    for sentinel in sentinels:
        assert sentinel not in caplog.text
