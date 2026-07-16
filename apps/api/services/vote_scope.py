"""Shared geographic authorization policy for bill interactions."""
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import HTTPException, status

from models import GovernanceLevel


class ScopeAction(str, Enum):
    VOTE = "vote"
    CONSENSUS = "consensus"


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str
    detail_el: str


def _governance_level(value: Any) -> GovernanceLevel | None:
    if value is None:
        return None
    if isinstance(value, GovernanceLevel):
        return value
    try:
        return GovernanceLevel(str(value).upper())
    except ValueError:
        return None


def evaluate_bill_scope(
    identity: Any,
    bill: Any,
    *,
    action: ScopeAction = ScopeAction.VOTE,
) -> ScopeDecision:
    """Return the geographic authorization decision without mutating state.

    NATIONAL and INSTITUTIONAL preserve the existing country-wide behavior.
    Every geographically scoped or unsupported level fails closed unless its
    required bill scope is configured and matches the server-side identity.
    """
    raw_level = getattr(bill, "governance_level", None)
    level = _governance_level(raw_level)
    noun = "αξιολόγηση" if action == ScopeAction.CONSENSUS else "ψηφοφορία"

    # Historical Parliament rows without an explicit level are national.
    if raw_level is None or level in (GovernanceLevel.NATIONAL, GovernanceLevel.INSTITUTIONAL):
        return ScopeDecision(True, "country_wide", "")

    if level == GovernanceLevel.REGIONAL:
        bill_periferia = getattr(bill, "periferia_id", None)
        if not bill_periferia:
            return ScopeDecision(
                False,
                "regional_scope_missing",
                f"Η {noun} δεν είναι διαθέσιμη επειδή δεν έχει οριστεί Περιφέρεια.",
            )
        if getattr(identity, "periferia_id", None) != bill_periferia:
            return ScopeDecision(
                False,
                "regional_scope_mismatch",
                f"Αυτή η {noun} αφορά μόνο κατοίκους αυτής της Περιφέρειας.",
            )
        return ScopeDecision(True, "regional_match", "")

    if level == GovernanceLevel.MUNICIPAL:
        bill_dimos = getattr(bill, "dimos_id", None)
        if not bill_dimos:
            return ScopeDecision(
                False,
                "municipal_scope_missing",
                f"Η {noun} δεν είναι διαθέσιμη επειδή δεν έχει οριστεί Δήμος.",
            )
        if getattr(identity, "dimos_id", None) != bill_dimos:
            return ScopeDecision(
                False,
                "municipal_scope_mismatch",
                f"Αυτή η {noun} αφορά μόνο κατοίκους αυτού του Δήμου.",
            )
        return ScopeDecision(True, "municipal_match", "")

    return ScopeDecision(
        False,
        "unsupported_scope",
        f"Αυτό το γεωγραφικό επίπεδο δεν υποστηρίζεται ακόμη για {noun}.",
    )


def ensure_bill_scope_allowed(
    identity: Any,
    bill: Any,
    *,
    action: ScopeAction = ScopeAction.VOTE,
) -> None:
    decision = evaluate_bill_scope(identity, bill, action=action)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision.detail_el,
        )
