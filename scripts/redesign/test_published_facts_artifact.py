"""The dated facts linked from public pages must ship in the web image."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PublishedFactsArtifactTest(unittest.TestCase):
    def test_linked_project_facts_are_copied_into_public(self):
        consumers = [p for p in (ROOT / "docs").rglob("*") if p.suffix in {".html", ".txt"}
                     and "/project-facts.json" in p.read_text(encoding="utf-8", errors="ignore")]
        self.assertTrue(consumers, "expected public pages to link /project-facts.json")
        dockerfile = (ROOT / "apps/web/Dockerfile.prod").read_text(encoding="utf-8")
        copies = [line for line in dockerfile.splitlines()
                  if re.match(r"\s*COPY\b", line) and line.rstrip().endswith("./public/")]
        self.assertTrue(any(re.search(r"(^|\s)docs/project-facts\.json(\s|$)", line) for line in copies),
                        "docs/project-facts.json must be copied to ./public/ in apps/web/Dockerfile.prod")
        self.assertTrue((ROOT / "docs/project-facts.json").is_file())


if __name__ == "__main__":
    unittest.main()
