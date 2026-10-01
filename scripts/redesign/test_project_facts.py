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
    """The --claims heuristic must see markup-split, attribute and "noun: n" forms."""

    def _hits(self, line: str) -> list[tuple[str, str]]:
        found = []
        for text in (line, project_facts.TAG_RE.sub(" ", line)):
            for pattern in project_facts.CLAIM_RES:
                for m in pattern.finditer(text):
                    g = m.groups()
                    num, noun = (g[0], g[2]) if g[0].isdigit() else (g[1], g[0])
                    found.append((num, project_facts.CLAIM_KIND[noun.lower()]))
        return sorted(set(found))

    def test_markup_split_number(self) -> None:
        self.assertIn(("22", "modules"), self._hits('<strong>22</strong> Modules'))

    def test_attribute_text(self) -> None:
        self.assertIn(("18", "db_tables_orm"), self._hits('<meta content="Σχήμα: 18 πίνακες"/>'))

    def test_noun_colon_number(self) -> None:
        self.assertIn(("9", "prod_containers"), self._hits("Containers: 9"))
