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
def primary_provider(monkeypatch):
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
async def test_indeterminate_primary_uses_configured_fallback(monkeypatch) -> None:
    primary = {
        "valid": False,
        "status": "INCONCLUSIVE",
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
    assert state_calls == ["indeterminate_status (INCONCLUSIVE)"]


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
