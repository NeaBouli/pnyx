"""T-420 (EKA-50/51/52): wiki module/table facts must match the runtime.

Sources of truth: the ``/health`` module registry in ``apps/api/main.py``,
SQLAlchemy ``__tablename__`` declarations in ``apps/api/models.py`` and the
Alembic migrations. Markdown (``wiki/``) and HTML (``docs/wiki/``) stay in sync.
"""

from __future__ import annotations

import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
PHANTOM_TABLES = {"representative_consent", "representative_profile", "citizen_evaluation"}
# Documented raw-SQL tables (T-434: cplm_history, MOD-24). Must equal the set
# derived from runtime SQL by ``runtime_raw_sql_tables()``.
RAW_SQL_TABLES = {
    "polis_identity_keys", "polis_tickets", "polis_votes", "representative_tokens",
    "rep_invitations", "bill_flags", "consensus_votes", "cplm_history",
}
RAW_SQL_MODULE = {"representative_tokens": "MOD-25", "cplm_history": "MOD-24"}
SQL_TABLE_REF = re.compile(r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([a-z_][a-z_0-9]*)\b")
SQL_CTE_NAME = re.compile(r"\b([a-z_][a-z_0-9]*)\s+AS\s*\(")


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def registry_modules() -> set[str]:
    main = read("apps/api/main.py")
    block = main[main.index('@app.get("/health")'):main.index('@app.get("/api/v1/health/modules")')]
    return set(re.findall(r'"(MOD-\d+)\b', block))


def orm_tables() -> set[str]:
    return set(re.findall(r'__tablename__\s*=\s*"([a-z_0-9]+)"', read("apps/api/models.py")))


def runtime_sql() -> str:
    api = REPO / "apps/api"
    files = sorted(api.glob("routers/*.py")) + sorted(api.glob("services/*.py"))
    return "".join(p.read_text(encoding="utf-8") for p in files)


def runtime_raw_sql_tables() -> set[str]:
    """Tables hit by raw SQL in routers/services that have no ORM model (CTEs excluded)."""
    code = runtime_sql()
    return set(SQL_TABLE_REF.findall(code)) - set(SQL_CTE_NAME.findall(code)) - orm_tables()


class Cells(HTMLParser):
    """Collect the first cell text of every table row, plus ids and nav links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.first_cells: list[str] = []
        self.ids: list[str] = []
        self.nav_links: list[str] = []
        self._cell = 0
        self._buf: list[str] | None = None
        self._nav = 0
        self._a: list[str] | None = None
        self._href = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "tr":
            self._cell = 0
        elif tag == "td":
            self._cell += 1
            if self._cell == 1:
                self._buf = []
        elif tag == "nav":
            self._nav += 1
        elif tag == "a" and self._nav and not (a.get("href") or "#").startswith("#"):
            self._href, self._a = a["href"], []

    def handle_endtag(self, tag):
        if tag == "td" and self._buf is not None:
            self.first_cells.append("".join(self._buf).strip())
            self._buf = None
        elif tag == "nav":
            self._nav -= 1
        elif tag == "a" and self._a is not None:
            self.nav_links.append(f'{self._href} {"".join(self._a).strip()}')
            self._a = None

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)
        if self._a is not None:
            self._a.append(data)


def parse(rel: str) -> Cells:
    p = Cells()
    p.feed(read(rel))
    return p


def md_first_column(rel: str) -> list[str]:
    return [line.split("|")[1].strip() for line in read(rel).splitlines()
            if line.startswith("| ") and not line.startswith("| ID") and not line.startswith("| Table")]


class ModuleRegistryTest(unittest.TestCase):
    def test_html_modules_match_registry(self) -> None:
        ids = {c for c in parse("docs/wiki/modules.html").first_cells if re.fullmatch(r"MOD-\d+", c)}
        self.assertEqual(registry_modules(), ids)

    def test_markdown_modules_match_registry(self) -> None:
        ids = {c for c in md_first_column("wiki/Modules.md") if re.fullmatch(r"MOD-\d+", c)}
        self.assertEqual(registry_modules(), ids)

    def test_phantom_modules_absent_from_tables(self) -> None:
        self.assertNotIn("MOD-13", registry_modules())
        self.assertNotIn("MOD-17", registry_modules())
        self.assertNotIn("| MOD-13 |", read("wiki/Modules.md"))
        self.assertNotIn("| MOD-17 |", read("wiki/Modules.md"))
        self.assertNotIn("MOD-13 Relevance", read("wiki/Roadmap.md"))

    def test_mod25_is_beta_everywhere(self) -> None:
        self.assertRegex(read("wiki/Modules.md"), r"\| MOD-25 \| [^|]+ \| ✅ Beta \|")
        modules = read("docs/wiki/modules.html")
        row = next(l for l in modules.splitlines() if 'id="dot-mod25"' in l)
        self.assertIn(">Beta</span>", row)
        for rel in ("docs/wiki/api.html", "docs/wiki/database.html"):
            for line in read(rel).splitlines():
                if "MOD-25" in line:
                    self.assertNotIn("Planned", line, f"{rel}: {line.strip()[:80]}")

    def test_api_mod25_paths_exist_in_routers(self) -> None:
        routers = read("apps/api/routers/evaluation.py") + read("apps/api/routers/representative.py")
        rows = [l for l in read("docs/wiki/api.html").splitlines() if "</span>MOD-25</td>" in l]
        self.assertTrue(rows)
        for row in rows:
            path = re.search(r"<td>(/[^<]+)</td>", row).group(1)
            prefix, _, rest = path.lstrip("/").partition("/")
            suffix = "/" + re.sub(r"\{ada\}", "{ada_number}", rest)
            self.assertIn(prefix, {"politicians", "rep"})
            self.assertIn(f'"{suffix}"', routers, path)


class DatabaseTablesTest(unittest.TestCase):
    def test_html_lists_exact_real_tables(self) -> None:
        cells = set(parse("docs/wiki/database.html").first_cells)
        self.assertEqual(orm_tables() | RAW_SQL_TABLES, cells)
        self.assertFalse(cells & PHANTOM_TABLES)

    def test_markdown_lists_exact_real_tables(self) -> None:
        cells = set(md_first_column("wiki/Database.md"))
        self.assertEqual(orm_tables() | RAW_SQL_TABLES, cells)
        self.assertFalse(PHANTOM_TABLES & set(re.findall(r"[a-z_]+", read("wiki/Database.md"))))

    def test_raw_sql_tables_match_runtime_code(self) -> None:
        self.assertEqual(runtime_raw_sql_tables(), RAW_SQL_TABLES)
        self.assertFalse(RAW_SQL_TABLES & orm_tables())

    def test_raw_sql_tables_documented_in_both_sources(self) -> None:
        html = parse("docs/wiki/database.html").first_cells
        md = md_first_column("wiki/Database.md")
        for table in runtime_raw_sql_tables():
            self.assertIn(table, html, table)
            self.assertIn(table, md, table)

    def test_raw_sql_module_and_schema_source(self) -> None:
        html = read("docs/wiki/database.html")
        md = read("wiki/Database.md")
        migrations = "".join(p.read_text(encoding="utf-8")
                             for p in (REPO / "apps/api/alembic/versions").glob("*.py"))
        for table, module in RAW_SQL_MODULE.items():
            self.assertIn(f"<tr><td>{table}</td><td>{module}</td>", html, table)
            self.assertRegex(md, rf"\| {table} \| {module} \|", table)
        self.assertNotIn("cplm_history", migrations)
        self.assertIn("<tr><td>cplm_history</td><td>MOD-24</td><td data-el=\"Χωρίς migration/μοντέλο στο repo\"", html)
        self.assertIn("| cplm_history | MOD-24 | No migration/model in repo |", md)

    def test_schema_drift_note_is_described_as_partial(self) -> None:
        html = read("docs/wiki/database.html")
        md = read("wiki/Database.md")
        self.assertIn("Schema drift is partly documented in", html)
        self.assertIn("Schema drift is partly documented in", md)
        self.assertIn("Η απόκλιση σχήματος τεκμηριώνεται εν μέρει στο", html)
        self.assertNotIn("Schema drift is tracked in", html)
        self.assertNotIn("Schema drift is tracked in", md)
        self.assertNotIn("Η απόκλιση σχήματος καταγράφεται στο", html)


class PageDefectTest(unittest.TestCase):
    PAGES = sorted(str(p.relative_to(REPO)) for p in DOCS.glob("wiki/*.html")) + [
        "docs/community.html", "docs/govgr-dimos.html", "docs/index.html",
    ]

    def test_no_duplicate_ids_or_nav_links(self) -> None:
        for rel in self.PAGES:
            p = parse(rel)
            self.assertEqual([], [k for k, n in Counter(p.ids).items() if n > 1], rel)
            self.assertEqual([], [k for k, n in Counter(p.nav_links).items() if n > 1], rel)

    def test_24h_footer_targets_window_24h(self) -> None:
        for rel in self.PAGES:
            for href in re.findall(r'<a href="([^"]*)" data-el="24 Ώρες"', read(rel)):
                self.assertEqual("/el/bills?status=WINDOW_24H", href, rel)

    def test_no_absolute_developer_paths(self) -> None:
        for p in list((REPO / "wiki").glob("*.md")) + list(DOCS.glob("wiki/*.html")):
            self.assertNotIn("/Users/", p.read_text(encoding="utf-8"), p.name)


if __name__ == "__main__":
    unittest.main()
