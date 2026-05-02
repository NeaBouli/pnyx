"""Regression checks for the landing-chat training questions captured by Codex."""

import json
from pathlib import Path

from routers.agent import _canonical_response, _safety_response, _should_include_bills


DATASET = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "agent-bridge"
    / "LANDING_CHAT_TRAINING_DATA_20260502.jsonl"
)


def _records():
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_training_dataset_has_25_entries_with_retry():
    records = _records()

    assert len(records) == 25
    assert {r["id"] for r in records} >= {"EN-005", "EN-005-R1", "EN-011"}


def test_training_dataset_safety_questions_are_filtered():
    for record in _records():
        if record["category"] != "adversarial":
            continue
        response = _safety_response(record["question"], record["lang"])
        assert response is not None
        assert response["model"] == "safety-filter"
        assert response["sources"] == []


def test_training_dataset_high_priority_knowledge_has_canonical_answers():
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


def test_training_dataset_general_questions_do_not_attach_bill_sources():
    for record in _records():
        if record["category"] in {"identity", "legal", "privacy", "crypto", "limits"}:
            assert _should_include_bills(record["question"]) is False

