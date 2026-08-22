"""Deterministic matching for local municipalities and Diavgeia organizations."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from rapidfuzz import fuzz


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_OVERRIDE_PATH = DATA_DIR / "diavgeia_primary_overrides.json"
_PREFIX_RE = re.compile(r"^(?:ΔΗΜΟΣ|ΔΗΜΟΥ|ΔΗΜΟΙ|ΔΗΜΟ)\s+")
_SEPARATOR_RE = re.compile(r"[-‐‑‒–—―().,;/]+")
_SPACE_RE = re.compile(r"\s+")
_LATIN_HOMOGLYPHS = str.maketrans(
    {
        "A": "Α",
        "B": "Β",
        "E": "Ε",
        "H": "Η",
        "I": "Ι",
        "K": "Κ",
        "M": "Μ",
        "N": "Ν",
        "O": "Ο",
        "P": "Ρ",
        "T": "Τ",
        "X": "Χ",
        "Y": "Υ",
        "Z": "Ζ",
    }
)


@dataclass(frozen=True)
class DimosRecord:
    id: int
    name_el: str
    periferia_id: int


@dataclass(frozen=True)
class PrimaryMatch:
    dimos_id: int
    dimos_name_el: str
    status: str
    org_uid: str | None
    org_label: str | None
    token_set_score: float
    ratio_score: float
    needs_review: bool
    source: str
    reason: str | None = None
    evidence_url: str | None = None


def normalize_greek(text: str) -> str:
    """Canonicalize Greek organization names without changing word meaning."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(char for char in nfkd if not unicodedata.combining(char))
    normalized = stripped.upper().translate(_LATIN_HOMOGLYPHS)
    normalized = _SEPARATOR_RE.sub(" ", normalized)
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    normalized = _PREFIX_RE.sub("", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


def is_strict_municipality(org: dict[str, Any]) -> bool:
    """Accept only active primary municipality records with a municipality label."""
    label = normalize_greek(org.get("label", ""))
    raw_label = unicodedata.normalize("NFKD", org.get("label") or "").upper()
    return (
        org.get("category") == "MUNICIPALITY"
        and org.get("is_primary") is True
        and org.get("status", "active") == "active"
        and raw_label.startswith(("ΔΗΜΟΣ ", "ΔΗΜΟ "))
        and bool(label)
        and bool(str(org.get("uid", "")))
    )


def load_overrides(path: Path = DEFAULT_OVERRIDE_PATH) -> dict[int, dict[str, Any]]:
    """Load and minimally validate the guarded manual decision catalog."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if payload.get("version") != 1 or not isinstance(payload.get("entries"), list):
        raise ValueError(f"Malformed Diavgeia override catalog: {path}")

    entries: dict[int, dict[str, Any]] = {}
    for entry in payload["entries"]:
        dimos_id = entry.get("dimos_id")
        action = entry.get("action", "map")
        if not isinstance(dimos_id, int) or dimos_id in entries:
            raise ValueError(f"Invalid or duplicate dimos_id in override catalog: {dimos_id}")
        if action not in {"map", "manual_review"}:
            raise ValueError(f"Invalid override action for dimos_id={dimos_id}: {action}")
        if action == "map":
            if not str(entry.get("target_uid", "")):
                raise ValueError(f"Missing target_uid for dimos_id={dimos_id}")
            if not str(entry.get("expected_target_label", "")):
                raise ValueError(f"Missing expected_target_label for dimos_id={dimos_id}")
        entries[dimos_id] = entry
    return entries


def _stable_uid_key(uid: str) -> tuple[int, int | str]:
    return (0, int(uid)) if uid.isdigit() else (1, uid)


def _validate_override(
    dimos: DimosRecord,
    entry: dict[str, Any],
    candidates_by_uid: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    expected_name = entry.get("expected_name_el")
    expected_periferia = entry.get("expected_periferia_id")
    if normalize_greek(str(expected_name)) != normalize_greek(dimos.name_el):
        raise ValueError(f"Override name guard failed for dimos_id={dimos.id}")
    if expected_periferia != dimos.periferia_id:
        raise ValueError(f"Override region guard failed for dimos_id={dimos.id}")
    if entry.get("action", "map") == "manual_review":
        return None

    target_uid = str(entry["target_uid"])
    target = candidates_by_uid.get(target_uid)
    if target is None:
        raise ValueError(
            f"Override target is not an active strict municipality: dimos_id={dimos.id}, uid={target_uid}"
        )
    expected_target_label = entry.get("expected_target_label")
    if normalize_greek(str(expected_target_label)) != normalize_greek(target.get("label", "")):
        raise ValueError(f"Override target label guard failed for dimos_id={dimos.id}")
    return target


def propose_primary_mappings(
    dimoi: Iterable[DimosRecord],
    organizations: Iterable[dict[str, Any]],
    *,
    threshold: float = 0.85,
    overrides: dict[int, dict[str, Any]] | None = None,
) -> list[PrimaryMatch]:
    """Return one deterministic primary proposal or explicit review result per dimos."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    override_entries = load_overrides() if overrides is None else overrides
    candidates = [org for org in organizations if is_strict_municipality(org)]
    candidates_by_uid = {str(org["uid"]): org for org in candidates}
    if len(candidates_by_uid) != len(candidates):
        raise ValueError("Duplicate municipality UID in Diavgeia snapshot")

    normalized = [(org, normalize_greek(org.get("label", ""))) for org in candidates]
    results: list[PrimaryMatch] = []

    for dimos in sorted(dimoi, key=lambda item: item.id):
        dimos_norm = normalize_greek(dimos.name_el)
        entry = override_entries.get(dimos.id)
        if entry is not None:
            target = _validate_override(dimos, entry, candidates_by_uid)
            if target is None:
                results.append(
                    PrimaryMatch(
                        dimos_id=dimos.id,
                        dimos_name_el=dimos.name_el,
                        status="manual_review",
                        org_uid=None,
                        org_label=None,
                        token_set_score=0.0,
                        ratio_score=0.0,
                        needs_review=True,
                        source="catalog",
                        reason=entry.get("reason"),
                        evidence_url=entry.get("evidence_url"),
                    )
                )
                continue

            target_norm = normalize_greek(target.get("label", ""))
            results.append(
                PrimaryMatch(
                    dimos_id=dimos.id,
                    dimos_name_el=dimos.name_el,
                    status="matched",
                    org_uid=str(target["uid"]),
                    org_label=target.get("label", ""),
                    token_set_score=fuzz.token_set_ratio(dimos_norm, target_norm) / 100.0,
                    ratio_score=fuzz.ratio(dimos_norm, target_norm) / 100.0,
                    needs_review=False,
                    source="catalog",
                    reason=entry.get("reason"),
                    evidence_url=entry.get("evidence_url"),
                )
            )
            continue

        ranked: list[tuple[float, float, int, tuple[int, int | str], dict[str, Any]]] = []
        for org, org_norm in normalized:
            token_set_score = fuzz.token_set_ratio(dimos_norm, org_norm) / 100.0
            ratio_score = fuzz.ratio(dimos_norm, org_norm) / 100.0
            ranked.append(
                (
                    token_set_score,
                    ratio_score,
                    len(org_norm.split()),
                    _stable_uid_key(str(org["uid"])),
                    org,
                )
            )
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        best = ranked[0] if ranked else None
        if best is None or best[0] < threshold:
            results.append(
                PrimaryMatch(
                    dimos_id=dimos.id,
                    dimos_name_el=dimos.name_el,
                    status="unmatched",
                    org_uid=None,
                    org_label=None,
                    token_set_score=best[0] if best else 0.0,
                    ratio_score=best[1] if best else 0.0,
                    needs_review=True,
                    source="fuzzy",
                )
            )
            continue

        score_tie = sum(item[:3] == best[:3] for item in ranked) > 1
        results.append(
            PrimaryMatch(
                dimos_id=dimos.id,
                dimos_name_el=dimos.name_el,
                status="matched",
                org_uid=str(best[4]["uid"]),
                org_label=best[4].get("label", ""),
                token_set_score=best[0],
                ratio_score=best[1],
                needs_review=best[1] < 0.95 or score_tie,
                source="fuzzy",
            )
        )

    assigned_uids = [result.org_uid for result in results if result.org_uid]
    if len(assigned_uids) != len(set(assigned_uids)):
        raise ValueError("Proposed primary mappings assign one Diavgeia UID to multiple dimoi")
    return results
