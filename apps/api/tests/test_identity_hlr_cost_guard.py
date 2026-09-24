"""
EKA-06: HLR Kosten-/Missbrauchsschutz und datensparsamer öffentlicher Status.

Deckt ab:
- Limits greifen VOR jedem kostenpflichtigen Provideraufruf
- Gleichwertige Nummernformate teilen denselben gehashten Bucket
- Keine rohen IPs/Telefonnummern in Redis-Keys
- Redis-Ausfall verhindert den bezahlten HLR-Aufruf (fail-closed)
- Öffentliches Credits-Schema ohne exakte Felder
- Geschützter Admin-Endpoint mit exaktem bisherigem Schema
- Community-JS konsistent mit dem groben Schema
- Dashboard konsumiert exakte Daten ausschließlich über den Admin-Proxy
"""
import os
import re

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from main import app
from routers import identity


VALID_FORMATS = ["6912345678", "06912345678", "306912345678", "+306912345678"]


class FakeRedis:
    """In-memory Redis mit den vom Guard genutzten Befehlen."""

    def __init__(self, respect_cooldown: bool = True) -> None:
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.values: dict[str, str] = {}
        self.respect_cooldown = respect_cooldown

    async def get(self, key: str):
        return self.values.get(key)

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and self.respect_cooldown and key in self.values:
            return None
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    async def eval(self, _script: str, numkeys: int, *args) -> int:
        if numkeys == 1:
            key, seconds = args
            count = await self.incr(key)
            if count == 1:
                self.expirations[key] = int(seconds)
            return count

        assert numkeys == 4
        cooldown_key, number_day_key, ip_minute_key, ip_day_key = args[:4]
        (
            cooldown_seconds,
            number_day_limit,
            number_day_seconds,
            ip_minute_limit,
            ip_minute_seconds,
            ip_day_limit,
            ip_day_seconds,
        ) = map(int, args[4:])

        if self.respect_cooldown and cooldown_key in self.values:
            return -1
        if self.counts.get(number_day_key, 0) >= number_day_limit:
            return -2
        if self.counts.get(ip_minute_key, 0) >= ip_minute_limit:
            return -3
        if self.counts.get(ip_day_key, 0) >= ip_day_limit:
            return -4

        self.values[cooldown_key] = "1"
        self.expirations[cooldown_key] = cooldown_seconds
        for key, seconds in (
            (number_day_key, number_day_seconds),
            (ip_minute_key, ip_minute_seconds),
            (ip_day_key, ip_day_seconds),
        ):
            count = await self.incr(key)
            if count == 1:
                self.expirations[key] = seconds
        return 1


class FailingRedis:
    """Simuliert einen Redis-Ausfall bei jedem Befehl."""

    async def get(self, key: str):
        raise ConnectionError("redis down")

    async def set(self, *args, **kwargs):
        raise ConnectionError("redis down")

    async def eval(self, *args, **kwargs):
        raise ConnectionError("redis down")


def _request(client_host: str = "198.51.100.23") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/identity/verify",
            "headers": [],
            "client": (client_host, 12345),
        }
    )


def _redis_factory(redis):
    async def _get_redis():
        return redis

    return _get_redis


def _all_keys(redis: FakeRedis) -> list[str]:
    return list(redis.counts) + list(redis.values)


def _assert_key_pii_safe(
    key: str, *, raw_ip: str, raw_number_fragments: list[str]
) -> None:
    """Structurally validate that a Redis key contains no raw PII.

    Splits the key at the last colon to isolate the 32-char HMAC hex
    suffix from the namespace prefix.  Only the prefix is scanned for
    consecutive-digit runs — valid HMAC hex may legitimately contain
    9+ decimal digits (the false-positive that triggered this helper).
    The suffix IS checked for specific raw phone fragments: a ten-digit
    Greek phone like ``6912345678`` is also valid hex and could appear
    verbatim inside a 32-char hex string without triggering the generic
    digit-run guard.
    """
    assert key.startswith("ratelimit:hlr_verify:"), f"unbekannter Key-Prefix: {key}"
    prefix, _, suffix = key.rpartition(":")
    assert re.fullmatch(r"[0-9a-f]{32}", suffix), (
        f"Suffix ist kein gültiger 32-Zeichen HMAC-Hex: {suffix!r}"
    )
    assert raw_ip not in prefix, f"rohe IP im Key-Prefix: {key}"
    for frag in raw_number_fragments:
        assert frag not in prefix, f"rohes Nummern-Fragment im Key-Prefix: {key}"
        assert frag not in suffix, f"rohes Nummern-Fragment im HMAC-Suffix: {key}"
    assert not re.search(r"\d{9,}", prefix), (
        f"rohe Nummern-Fragmente im Key-Prefix: {key}"
    )


# ─── Guard: Buckets, PII, Reihenfolge ────────────────────────────────────────


@pytest.mark.asyncio
async def test_equivalent_number_formats_share_the_same_bucket(monkeypatch):
    """Alle akzeptierten Eingabeformate treffen denselben gehashten Bucket."""
    normalized = {identity.normalize_greek_number(fmt) for fmt in VALID_FORMATS}
    assert len(normalized) == 1

    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    # Erster Versuch mit dem einen Format …
    await identity._enforce_hlr_verify_limits(_request(), normalized.pop())
    # … blockiert den sofortigen Zweitversuch — unabhängig vom Eingabeformat,
    # da der Guard stets die normalisierte E.164-Form hasht.
    for fmt in VALID_FORMATS:
        renorm = identity.normalize_greek_number(fmt)
        with pytest.raises(HTTPException) as excinfo:
            await identity._enforce_hlr_verify_limits(_request(), renorm)
        assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_number_bucket_is_independent_of_client_ip(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    await identity._enforce_hlr_verify_limits(_request("198.51.100.1"), "+306912345678")
    with pytest.raises(HTTPException) as excinfo:
        await identity._enforce_hlr_verify_limits(_request("203.0.113.9"), "+306912345678")
    assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_number_daily_limit_allows_three_attempts(monkeypatch):
    redis = FakeRedis(respect_cooldown=False)
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    for _ in range(identity.HLR_VERIFY_NUMBER_DAY_LIMIT):
        await identity._enforce_hlr_verify_limits(_request(), "+306912345678")
    with pytest.raises(HTTPException) as excinfo:
        await identity._enforce_hlr_verify_limits(_request(), "+306912345678")
    assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_no_raw_pii_in_redis_keys(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    await identity._enforce_hlr_verify_limits(_request("198.51.100.23"), "+306912345678")

    keys = _all_keys(redis)
    assert keys, "Guard muss Redis-Buckets schreiben"
    for key in keys:
        _assert_key_pii_safe(
            key,
            raw_ip="198.51.100.23",
            raw_number_fragments=["6912345678", "306912345678"],
        )


@pytest.mark.asyncio
async def test_numeric_heavy_hmac_suffix_no_false_positive(monkeypatch):
    """A valid 32-char hex digest with ≥9 consecutive decimal digits must not
    trigger a false PII alert — regression for GitHub Actions run 35936320815."""
    import ip_utils

    NUMERIC_DIGEST = "aaa" + "0" * 9 + "f" * 20  # 32-char valid hex, 9 digits
    assert len(NUMERIC_DIGEST) == 32
    assert re.search(r"\d{9,}", NUMERIC_DIGEST), "Digest muss ≥9 Ziffern enthalten"

    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    def _forced_numeric_hash(subject, namespace, today=None):
        return NUMERIC_DIGEST

    monkeypatch.setattr(identity, "hashed_rate_subject", _forced_numeric_hash)
    monkeypatch.setattr(ip_utils, "hashed_rate_subject", _forced_numeric_hash)

    await identity._enforce_hlr_verify_limits(_request("198.51.100.23"), "+306912345678")

    keys = _all_keys(redis)
    assert keys, "Guard muss Redis-Buckets schreiben"
    for key in keys:
        _assert_key_pii_safe(
            key,
            raw_ip="198.51.100.23",
            raw_number_fragments=["6912345678", "306912345678"],
        )


@pytest.mark.asyncio
async def test_keys_match_independently_computed_hmacs(monkeypatch):
    """Verify actual Redis keys equal independently computed expected keys.

    Structural hex validation alone cannot distinguish a genuine HMAC
    suffix from a syntactically valid hex string that embeds the raw
    phone number (e.g. ``6912345678aabbccddeeff0011223344``).  This test
    independently recomputes the expected HMAC for each known test
    subject and asserts the exact key set.
    """
    import ip_utils

    TEST_IP = "198.51.100.23"
    TEST_PHONE = "+306912345678"
    NORMALIZED = "306912345678"
    SALT = "s" * 64

    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", SALT)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    await identity._enforce_hlr_verify_limits(_request(TEST_IP), TEST_PHONE)

    today = identity.date.today()
    day = today.isoformat()

    number_hash = ip_utils.hashed_rate_subject(NORMALIZED, "hlr_verify:number", today=today)
    ip_min_hash = ip_utils.hashed_rate_subject(TEST_IP, "hlr_verify:ip_min", today=today)
    ip_day_hash = ip_utils.hashed_rate_subject(TEST_IP, "hlr_verify:ip_day", today=today)

    expected_keys = {
        f"ratelimit:hlr_verify:number_cooldown:{day}:{number_hash}",
        f"ratelimit:hlr_verify:number_day:{day}:{number_hash}",
        f"ratelimit:hlr_verify:ip_min:{day}:{ip_min_hash}",
        f"ratelimit:hlr_verify:ip_day:{day}:{ip_day_hash}",
    }

    actual_keys = set(_all_keys(redis))
    assert actual_keys == expected_keys, (
        f"Key mismatch.\n  Expected: {sorted(expected_keys)}\n  Actual:   {sorted(actual_keys)}"
    )

    # Double-check: no HMAC suffix contains the raw phone
    for key in actual_keys:
        _, _, suffix = key.rpartition(":")
        for frag in [NORMALIZED, "6912345678"]:
            assert frag not in suffix, (
                f"HMAC suffix contains raw phone fragment: {suffix}"
            )


def test_phone_embedded_in_hex_suffix_is_rejected():
    """A syntactically valid 32-char hex suffix that embeds the raw phone
    number must be rejected — the structural check alone is insufficient."""
    phone10 = "6912345678"           # 10-digit, also valid hex
    phone12 = "306912345678"         # 12-digit with country prefix, valid hex
    poisoned_10 = phone10 + "a" * 22 # 32-char valid hex containing phone
    poisoned_12 = phone12 + "a" * 20

    assert len(poisoned_10) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", poisoned_10)
    assert len(poisoned_12) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", poisoned_12)

    with pytest.raises(AssertionError, match="HMAC-Suffix"):
        _assert_key_pii_safe(
            f"ratelimit:hlr_verify:number_day:2026-09-24:{poisoned_10}",
            raw_ip="10.0.0.1",
            raw_number_fragments=[phone10],
        )

    with pytest.raises(AssertionError, match="HMAC-Suffix"):
        _assert_key_pii_safe(
            f"ratelimit:hlr_verify:number_day:2026-09-24:{poisoned_12}",
            raw_ip="10.0.0.1",
            raw_number_fragments=[phone12],
        )


def test_raw_pii_in_key_prefix_still_caught():
    """Deliberate raw phone or IP leakage in the key prefix must fail."""
    safe_suffix = "a" * 32  # valid 32-char hex

    # Raw IP in prefix → caught
    with pytest.raises(AssertionError, match="rohe IP"):
        _assert_key_pii_safe(
            f"ratelimit:hlr_verify:ip_day:198.51.100.23:{safe_suffix}",
            raw_ip="198.51.100.23",
            raw_number_fragments=["6912345678"],
        )

    # Raw phone fragment in prefix → caught
    with pytest.raises(AssertionError, match="rohes Nummern-Fragment"):
        _assert_key_pii_safe(
            f"ratelimit:hlr_verify:number_day:6912345678:{safe_suffix}",
            raw_ip="10.0.0.1",
            raw_number_fragments=["6912345678"],
        )

    # 10-digit run in prefix (not covered by fragment list) → caught
    with pytest.raises(AssertionError, match="rohe Nummern-Fragmente"):
        _assert_key_pii_safe(
            f"ratelimit:hlr_verify:number_day:0000000000:{safe_suffix}",
            raw_ip="10.0.0.1",
            raw_number_fragments=[],
        )

    # Non-hex suffix (fail-closed) → caught
    with pytest.raises(AssertionError, match="HMAC-Hex"):
        _assert_key_pii_safe(
            f"ratelimit:hlr_verify:number_day:2026-09-24:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ",
            raw_ip="10.0.0.1",
            raw_number_fragments=[],
        )


@pytest.mark.asyncio
async def test_rejected_ip_does_not_consume_number_limits(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    request = _request("198.51.100.23")
    today = identity.date.today()
    ip_minute_key = identity.rate_limit_key_for_ip(
        request, "hlr_verify:ip_min", today=today
    )
    redis.counts[ip_minute_key] = identity.HLR_VERIFY_IP_MINUTE_LIMIT

    with pytest.raises(HTTPException) as excinfo:
        await identity._enforce_hlr_verify_limits(request, "+306912345678")

    assert excinfo.value.status_code == 429
    number_keys = [key for key in _all_keys(redis) if ":number_" in key]
    assert number_keys == [], "IP-blockierte Versuche dürfen keine Nummern-Buckets verändern"


# ─── Endpunkt: Limits vor Provideraufruf, fail-closed ────────────────────────


def _patch_provider(monkeypatch, calls: list):
    async def fake_hlr(_phone: str) -> dict:
        calls.append(_phone)
        return {"valid": False, "status": "ERROR", "error": "simulated", "_providers_queried": []}

    async def fake_increment(_providers: list[str]) -> int:
        return 1

    monkeypatch.setattr(identity, "verify_greek_number", fake_hlr)
    monkeypatch.setattr(identity, "_increment_hlr_usage", fake_increment)


@pytest.mark.asyncio
async def test_ip_minute_limit_blocks_before_provider_call(monkeypatch):
    redis = FakeRedis(respect_cooldown=False)
    calls: list = []
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))
    _patch_provider(monkeypatch, calls)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        codes = []
        for i in range(identity.HLR_VERIFY_IP_MINUTE_LIMIT + 1):
            # Jeweils andere gültige Nummer → nur das IP-Minutenlimit kann greifen.
            r = await client.post(
                "/api/v1/identity/verify",
                json={"phone_number": f"+3069123456{i:02d}"},
            )
            codes.append(r.status_code)

    assert codes[: identity.HLR_VERIFY_IP_MINUTE_LIMIT] == [400] * identity.HLR_VERIFY_IP_MINUTE_LIMIT
    assert codes[-1] == 429
    # Der letzte Versuch wurde VOR dem Provideraufruf gestoppt.
    assert len(calls) == identity.HLR_VERIFY_IP_MINUTE_LIMIT


@pytest.mark.asyncio
async def test_redis_outage_prevents_paid_hlr_call(monkeypatch):
    calls: list = []
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(FailingRedis()))
    _patch_provider(monkeypatch, calls)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/identity/verify",
            json={"phone_number": "+306912345678"},
        )

    assert r.status_code == 503
    assert calls == [], "Bei Redis-Ausfall darf kein bezahlter HLR-Aufruf erfolgen"


@pytest.mark.asyncio
async def test_invalid_number_rejected_locally_without_redis_or_provider(monkeypatch):
    calls: list = []
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(FailingRedis()))
    _patch_provider(monkeypatch, calls)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/identity/verify",
            json={"phone_number": "+302101234567"},
        )

    assert r.status_code == 400
    assert calls == []


# ─── Öffentliches Credits-Schema ─────────────────────────────────────────────

FORBIDDEN_PUBLIC_FIELDS = {
    "initial",
    "used",
    "remaining",
    "balance_eur",
    "cost_per_query_eur",
    "failover_reason",
    "provider",
    "enabled",
    "configured",
}


def _assert_coarse_schema(payload: dict) -> None:
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in FORBIDDEN_PUBLIC_FIELDS, f"verbotenes Feld: {key}"
                walk(value)

    walk(payload)
    assert payload["status"] in {"ok", "low", "critical"}
    assert payload["level"] in {"high", "medium", "low", "empty"}
    assert isinstance(payload["failover_active"], bool)
    assert isinstance(payload["verification_available"], bool)
    assert payload["primary"]["status"] in {"ok", "low", "critical"}
    assert payload["fallback"]["level"] in {"high", "medium", "low", "empty"}


@pytest.mark.asyncio
async def test_public_credits_schema_contains_no_exact_fields(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/identity/hlr/credits")

    assert r.status_code == 200
    _assert_coarse_schema(r.json())


@pytest.mark.asyncio
async def test_public_credits_failover_reason_not_exposed(monkeypatch):
    redis = FakeRedis()
    redis.values["hlr:failover:active"] = "true"
    redis.values["hlr:failover:reason"] = "low_credits (37)"
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))

    payload = await identity.hlr_credits()

    _assert_coarse_schema(payload)
    assert payload["failover_active"] is True
    assert "low_credits" not in str(payload)
    assert "37" not in str(payload)


# ─── Community-Kachel konsistent mit dem groben Schema ───────────────────────


def test_community_tile_matches_coarse_schema():
    community = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "community.html")
    with open(community, encoding="utf-8") as fh:
        html = fh.read()

    # Kein Bezug mehr auf exakte/gelöschte API-Felder.
    assert "failover_reason" not in html
    assert "costPerQuery" not in html
    assert "data.initial" not in html
    assert "data.used" not in html
    assert "data.remaining" not in html
    # Grobes Schema wird weiterhin verarbeitet.
    assert "updateHlrTile" in html
    assert "failover_active" in html
    assert "pData.level" in html
    assert "pData.status" in html


# ─── Admin-Endpoint: exaktes Schema nur hinter verify_admin ──────────────────


@pytest.mark.asyncio
async def test_admin_credits_refuses_without_auth(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/admin/hlr/credits")

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_credits_refuses_wrong_key(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/admin/hlr/credits",
            headers={"Authorization": "Bearer wrong-key"},
        )

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_credits_returns_exact_legacy_schema(monkeypatch):
    redis = FakeRedis()
    redis.values[identity.HLR_PRIMARY_REDIS_KEY] = "37"
    redis.values[identity.HLR_FALLBACK_REDIS_KEY] = "12"
    monkeypatch.setattr(identity, "_get_hlr_redis", _redis_factory(redis))
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/admin/hlr/credits",
            headers={"Authorization": "Bearer synthetic-admin-key"},
        )

    assert r.status_code == 200
    payload = r.json()

    expected_remaining = identity.HLR_PRIMARY_INITIAL_CREDITS - 37
    expected_balance = round(expected_remaining * identity.HLR_PRIMARY_COST_PER_QUERY, 2)

    # Flat-Felder (aktiver bzw. primärer Pfad, rückwärtskompatibel)
    assert payload["initial"] == identity.HLR_PRIMARY_INITIAL_CREDITS
    assert payload["used"] == 37
    assert payload["remaining"] == expected_remaining
    assert payload["balance_eur"] == expected_balance
    assert payload["cost_per_query_eur"] == identity.HLR_PRIMARY_COST_PER_QUERY
    assert payload["status"] in {"ok", "low", "critical"}

    primary = payload["primary"]
    assert primary["provider"] == "hlrlookup.com"
    assert primary["initial"] == identity.HLR_PRIMARY_INITIAL_CREDITS
    assert primary["used"] == 37
    assert primary["remaining"] == expected_remaining
    assert primary["balance_eur"] == expected_balance
    assert primary["cost_per_query_eur"] == identity.HLR_PRIMARY_COST_PER_QUERY
    assert primary["status"] in {"ok", "low", "critical"}

    fallback = payload["fallback"]
    assert fallback["provider"] == "hlr-lookups.com"
    assert isinstance(fallback["enabled"], bool)
    assert isinstance(fallback["configured"], bool)
    assert fallback["initial"] == identity.HLR_FALLBACK_INITIAL_CREDITS
    assert fallback["used"] == 12
    assert fallback["remaining"] == identity.HLR_FALLBACK_INITIAL_CREDITS - 12
    assert fallback["balance_eur"] == round(
        (identity.HLR_FALLBACK_INITIAL_CREDITS - 12) * identity.HLR_FALLBACK_COST_PER_QUERY, 2
    )
    assert fallback["cost_per_query_eur"] == identity.HLR_FALLBACK_COST_PER_QUERY
    assert fallback["status"] in {"ok", "low", "critical"}

    assert payload["failover_active"] is False
    assert "failover_reason" in payload


# ─── Dashboard konsumiert exakte Daten nur über den Admin-Proxy ──────────────


def test_dashboard_has_no_public_hlr_credits_reference():
    dashboard_src = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "apps", "dashboard", "src"
    )
    offenders = []
    proxy_consumers = []
    for root, _dirs, files in os.walk(dashboard_src):
        for name in files:
            if not name.endswith((".ts", ".tsx")):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            if "/api/v1/identity/hlr/credits" in content:
                offenders.append(path)
            if "admin/hlr/credits" in content:
                proxy_consumers.append(path)

    assert not offenders, f"Dashboard referenziert noch den öffentlichen Endpoint: {offenders}"
    assert proxy_consumers, "Dashboard muss exakte HLR-Daten über /api/proxy/admin/hlr/credits beziehen"
