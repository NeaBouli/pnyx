"""EKA-40: docs/project-facts.json must match the counts derived from source."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("project_facts", ROOT / "scripts" / "project_facts.py")
project_facts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_facts)


class ProjectFactsTest(unittest.TestCase):
    def test_artifact_is_current(self) -> None:
        committed = (ROOT / "docs" / "project-facts.json").read_text(encoding="utf-8")
        self.assertEqual(committed, project_facts.render(project_facts.compute()),
                         "run `python3 scripts/project_facts.py --write` and commit the result")

    def test_counts_are_positive_and_consistent(self) -> None:
        counts = project_facts.compute()["counts"]
        self.assertGreaterEqual(counts["modules_spec"], counts["modules_listed"])
        self.assertLess(counts["modules_inactive"], counts["modules_listed"])
        for key in ("api_endpoints", "api_routers", "db_tables_orm", "prod_containers"):
            self.assertGreater(counts[key], 0, key)

    def test_every_count_has_a_definition(self) -> None:
        facts = project_facts.compute()
        self.assertEqual(set(facts["counts"]), set(facts["definitions"]))
