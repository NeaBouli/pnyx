"""Regression checks for the landing-chat training questions captured by Codex.

The tracked fixture holds only id/lang/category/question; captured answers,
endpoints and timestamps stay in the private agent-bridge dataset.
"""

import json
from pathlib import Path
from typing import Any

from routers.agent import _canonical_response, _safety_response, _should_include_bills


DATASET = Path(__file__).resolve().parent / "fixtures" / "landing_chat_training_questions.jsonl"
FIXTURE_FIELDS = {"id", "lang", "category", "question"}


def _records() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_training_dataset_has_25_entries_with_retry() -> None:
    records = _records()

    assert len(records) == 25
    assert len({r["id"] for r in records}) == 25
    assert all(set(r) == FIXTURE_FIELDS for r in records)
    assert {r["id"] for r in records} >= {"EN-005", "EN-005-R1", "EN-011"}


def test_training_dataset_safety_questions_are_filtered() -> None:
    for record in _records():
        if record["category"] != "adversarial":
            continue
        response = _safety_response(record["question"], record["lang"])
        assert response is not None
        assert response["model"] == "safety-filter"
        assert response["sources"] == []


def test_training_dataset_high_priority_knowledge_has_canonical_answers() -> None:
    expected = {
        "EL-009": "cplm",
        "EL-012": "govgr",
        "EN-005": "nullifier_hash",
        "EN-005-R1": "nullifier_hash",
        "EN-006": "private_key",
        "EN-008": "municipal",
    }

    by_id = {r["id"]: r for r in _records()}
    for record_id, topic in expected.items():
        response = _canonical_response(by_id[record_id]["question"], by_id[record_id]["lang"])
        assert response is not None
        assert response["model"] == "knowledge-base"
        assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]


def test_training_dataset_general_questions_do_not_attach_bill_sources() -> None:
    for record in _records():
        if record["category"] in {"identity", "legal", "privacy", "crypto", "limits"}:
            assert _should_include_bills(record["question"]) is False
