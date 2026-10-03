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


class ClaimMatcherTest(unittest.TestCase):
    """Exercise the production claims() on synthetic pages (markup, attributes, tables)."""

    FACTS = {"counts": {"modules_spec": 25, "modules_listed": 23, "api_endpoints": 189,
                        "db_tables_orm": 24, "prod_containers": 8}}

    def _run(self, text: str) -> list[tuple[str, str, str]]:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "page.html"
            page.write_text(text, encoding="utf-8")
            return [(kind, claim, cls) for _, _, kind, claim, cls in project_facts.claims(self.FACTS, [page])]

    def test_markup_split_number(self) -> None:
        self.assertIn(("modules", "22 Modules", "mismatch"), self._run("<strong>22</strong> Modules"))

    def test_attribute_text(self) -> None:
        self.assertIn(("db_tables_orm", "18 πίνακες", "mismatch"), self._run('<meta content="Σχήμα: 18 πίνακες"/>'))

    def test_markdown_table_row(self) -> None:
        self.assertIn(("prod_containers", "Containers | 11", "mismatch"), self._run("| Containers | 11 |"))

    def test_noun_colon_number(self) -> None:
        self.assertIn(("prod_containers", "Containers: 9", "mismatch"), self._run("Containers: 9"))

    def test_lower_bound_and_accepted_values(self) -> None:
        hits = self._run("70+ endpoints, 25 modules, 23 modules, 24 tables, 8 containers")
        self.assertEqual(hits, [("api_endpoints", "70+ endpoints", "lower-bound")])

    def test_one_entry_per_claim_per_line(self) -> None:
        self.assertEqual(len(self._run('<p data-el="16 Endpoints">16 Endpoints</p>')), 1)
