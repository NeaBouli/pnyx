"""DOI evidence and read-only readiness. This module cannot enroll or send."""
import json
from collections import Counter
from datetime import datetime
from typing import Any

from pydantic import EmailStr, TypeAdapter


CONFIRMED_KEY = "newsletter:confirmed"
CONSENT_SCHEMA = 2
MAX_READINESS_CONTACTS = 100
TOPICS = {"new_proposals", "active_votes", "vote_results", "system_news", "breaking_news"}
_EMAIL = TypeAdapter(EmailStr)

# Compare payload, retain existing consent, then consume the token. HSETNX must
# succeed before DEL; GETDEL alone could lose proof on a subsequent write failure.
CONFIRM_ONCE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
local created = redis.call('HSETNX', KEYS[2], ARGV[2], ARGV[3])
redis.call('DEL', KEYS[1])
if created == 1 then return 1 end
return 2
"""

# Bound the hash read atomically so concurrent signups cannot defeat the limit.
READ_CONSENT_SNAPSHOT = """
local count = redis.call('HLEN', KEYS[1])
if count > tonumber(ARGV[1]) then return {count} end
local result = {count}
local entries = redis.call('HGETALL', KEYS[1])
for i = 1, #entries do result[#result + 1] = entries[i] end
return result
"""


def confirmation_payload(data: dict[str, Any], now: datetime) -> str:
    """Timestamp this click only; never backfill existing confirmed records."""
    confirmed = dict(data)
    confirmed["confirmed_at"] = now.isoformat()
    confirmed["confirmation_method"] = "double_opt_in"
    # Old in-flight links still work, but lack the new request-time evidence.
    if data.get("consent_schema") != CONSENT_SCHEMA:
        confirmed["consent_schema"] = 1
    return json.dumps(confirmed)


def parse_consent(email: str, raw: str) -> dict[str, Any] | None:
    """Do not infer or normalize a missing/mismatched local identity."""
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("email") != email:
            return None
        _EMAIL.validate_python(email)
        return data
    except (TypeError, ValueError):
        return None


def _has_evidence(data: dict[str, Any], now: datetime) -> bool:
    if (type(data.get("consent_schema")) is not int or data["consent_schema"] != CONSENT_SCHEMA
            or data.get("confirmation_method") != "double_opt_in"):
        return False
    try:
        requested = datetime.fromisoformat(data["requested_at"])
        confirmed = datetime.fromisoformat(data["confirmed_at"])
        return (requested.tzinfo is not None and confirmed.tzinfo is not None
                and requested <= confirmed <= now
                and (confirmed - requested).total_seconds() <= 86400)
    except (KeyError, TypeError, ValueError):
        return False


def classify_contact(
    email: str, raw: str, provider_status: int | None,
    provider: Any, list_id: int, now: datetime,
) -> tuple[str, list[str]]:
    """KEEP means no change, not approved consent. No result authorizes a write."""
    data = parse_consent(email, raw)
    if data is None:
        return "EXCLUDE", ["invalid_consent_record"]
    reasons = []
    if not _has_evidence(data, now):
        reasons.append("missing_confirmation_evidence")
    topics = data.get("topics")
    if not isinstance(topics, dict) or set(topics) != TOPICS or any(type(v) is not bool for v in topics.values()):
        return "EXCLUDE", reasons + ["invalid_preferences"]
    if not any(topics.values()):
        return "EXCLUDE", reasons + ["no_topics_selected"]
    if (data.get("frequency") != "monthly" or data.get("language") != "el"
            or data.get("subscriber_type") != "citizens" or not all(topics.values())):
        reasons.append("unsupported_delivery_profile")
    if provider_status == 404:
        return "HOLD", reasons + ["provider_missing_history"]
    if provider_status != 200:
        return "HOLD", reasons + ["provider_lookup_failed"]
    if (not isinstance(provider, dict) or not isinstance(provider.get("email"), str)
            or provider["email"].casefold() != email.casefold()):
        return "HOLD", reasons + ["provider_state_incomplete"]
    memberships = provider.get("listIds")
    unsubscribed = provider.get("listUnsubscribed")
    if provider.get("emailBlacklisted") is True or (isinstance(unsubscribed, list) and list_id in unsubscribed):
        return "EXCLUDE", reasons + ["provider_suppressed"]
    if (provider.get("emailBlacklisted") is not False
            or not isinstance(memberships, list) or not isinstance(unsubscribed, list)
            or any(type(v) is not int for v in memberships + unsubscribed)):
        return "HOLD", reasons + ["provider_state_incomplete"]
    if list_id in memberships:
        return "KEEP", reasons + ["existing_list_member"]
    # Manual campaigns share the monthly list without enforcing preferences.
    return "HOLD", reasons + ["campaign_preferences_not_enforced"]


def readiness_summary(
    decisions: list[tuple[str, list[str]]], confirmed_count: int, complete: bool,
) -> dict[str, Any]:
    actions = Counter(action for action, _ in decisions)
    reasons = Counter(reason for _, items in decisions for reason in items)
    return {
        "mode": "read_only", "scope": "locally_confirmed_only",
        "confirmed_count": confirmed_count, "evaluated_count": len(decisions),
        "complete": complete, "proposed_writes": 0,
        "actions": {name: actions[name] for name in ("KEEP", "HOLD", "EXCLUDE")},
        "reasons": dict(sorted(reasons.items())),
        "delivery_ready": False,
        "blockers": ["campaign_preferences_not_enforced", "provider_history_requires_review"]
        + ([] if complete else ["snapshot_limit_exceeded"]),
    }
