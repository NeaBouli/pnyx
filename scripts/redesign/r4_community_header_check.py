#!/usr/bin/env python3
"""Fail-closed R4 gate for Community, the public-data header and mobile chat.

R4 permits one static-page migration (``docs/community.html``), one bounded
landing CSS correction, and consolidation of the duplicate public-data nav
into ``NavHeader``. All community content and runtime contracts remain equal
to the frozen R0 inventory except for the explicit shell additions below.
"""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r0_inventory  # noqa: E402
import r2_landing_check as r2  # noqa: E402
import r3_wiki_pilot_check as r3  # noqa: E402

REPO_ROOT = r0_inventory.REPO_ROOT
DOCS_DIR = r0_inventory.DOCS_DIR
R0_INVENTORY_FILE = REPO_ROOT / "docs/planning/r0/R0_DOCS_SURFACE_INVENTORY.json"
COMMUNITY_REL = "docs/community.html"
CSS_HREFS = (
    "assets/redesign-v2/tokens.css",
    "assets/redesign-v2/foundation.css",
    "assets/redesign-v2/r4-community.css",
)
CSS_RELS = CSS_HREFS
SKIP_PAIR = {
    "data_el": "Μετάβαση στο κύριο περιεχόμενο",
    "data_en": "Skip to main content",
    "tag": "a",
}
SKIP_LINK = {
    "class": "pnx2-skip",
    "data_el": "Μετάβαση στο κύριο περιεχόμενο",
    "data_en": "Skip to main content",
    "href": "#main",
    "kind": "fragment",
    "text": "Μετάβαση στο κύριο περιεχόμενο",
}
SKIP_FRAGMENT = {"href": "#main", "resolved": True, "target_id": "main"}
ADDED_RESOURCES = tuple(
    {"kind": "relative-file", "source": "link.href", "url": href}
    for href in CSS_HREFS
) + ({"kind": "fragment", "source": "a.href", "url": "#main"},)
PRESERVED_EXACT_KEYS = r2.PRESERVED_EXACT_KEYS
PUBLIC_DATA_PAGES = (
    "apps/web/src/app/[locale]/analytics/page.tsx",
    "apps/web/src/app/[locale]/bills/page.tsx",
    "apps/web/src/app/[locale]/mp/page.tsx",
    "apps/web/src/app/[locale]/municipal/page.tsx",
    "apps/web/src/app/[locale]/results/page.tsx",
)
CSS_PROHIBITED = r3.CSS_PROHIBITED
VOID_ELEMENTS = r3.VOID_ELEMENTS


def _without_css_comments(source: str) -> str:
    """Replace CSS comments with whitespace while preserving source offsets."""
    return re.sub(r"/\*.*?\*/", lambda match: " " * len(match.group(0)), source, flags=re.DOTALL)


def _matching_brace(source: str, opening: int) -> int | None:
    """Return the closing brace for a CSS block, accounting for nesting."""
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _css_blocks(source: str, prelude_pattern: str) -> list[str]:
    """Extract balanced CSS blocks whose prelude matches the supplied regex."""
    clean = _without_css_comments(source)
    blocks: list[str] = []
    for match in re.finditer(prelude_pattern + r"\s*\{", clean, re.IGNORECASE):
        opening = clean.find("{", match.start())
        closing = _matching_brace(clean, opening)
        if closing is not None:
            blocks.append(clean[opening + 1:closing])
    return blocks


def _has_declaration(block: str, name: str, value_pattern: str) -> bool:
    """Check for a declaration inside one already-isolated CSS rule body."""
    return bool(re.search(
        rf"(?:^|;)\s*{re.escape(name)}\s*:\s*(?:{value_pattern})\s*(?:;|$)",
        block,
        re.IGNORECASE,
    ))


def _selector_has(source: str, selector_pattern: str, declarations: tuple[tuple[str, str], ...]) -> bool:
    """Require all declarations in the same matching selector block."""
    return any(
        all(_has_declaration(block, name, value) for name, value in declarations)
        for block in _css_blocks(source, selector_pattern)
    )


def _counter(values: list[object] | tuple[object, ...]) -> Counter[str]:
    return Counter(r0_inventory.canonical_json(value) for value in values)


def _exact_delta(
    label: str,
    baseline: list[object],
    current: list[object],
    additions: list[object] | tuple[object, ...],
) -> list[str]:
    expected = _counter(baseline) + _counter(additions)
    actual = _counter(current)
    if actual == expected:
        return []
    missing = list((expected - actual).elements())
    extra = list((actual - expected).elements())
    return [f"preservation: {label} differs; missing={missing}; unexpected={extra}"]


def _inventory_page(docs_dir: Path, page_rel: str) -> dict:
    saved_root = r0_inventory.REPO_ROOT
    saved_docs = r0_inventory.DOCS_DIR
    try:
        r0_inventory.REPO_ROOT = docs_dir.parent
        r0_inventory.DOCS_DIR = docs_dir
        return r0_inventory.inventory_page(page_rel)
    finally:
        r0_inventory.REPO_ROOT = saved_root
        r0_inventory.DOCS_DIR = saved_docs


def check_community_preservation(baseline: dict, current: dict) -> list[str]:
    violations: list[str] = []
    for key in PRESERVED_EXACT_KEYS:
        if current.get(key) != baseline.get(key):
            violations.append(f"preservation: exact contract changed: {key}")

    violations.extend(_exact_delta(
        "bilingual pairs", baseline["bilingual"]["pairs"],
        current["bilingual"]["pairs"], [SKIP_PAIR],
    ))
    for key in ("only_data_el", "only_data_en"):
        if current["bilingual"][key] != baseline["bilingual"][key]:
            violations.append(f"preservation: bilingual.{key} changed")

    violations.extend(_exact_delta("links", baseline["links"], current["links"], [SKIP_LINK]))
    violations.extend(_exact_delta(
        "text chunks", baseline["text"]["chunks"], current["text"]["chunks"],
        [SKIP_PAIR["data_el"]],
    ))
    violations.extend(_exact_delta(
        "navigation ids", baseline["navigation"]["ids"],
        current["navigation"]["ids"], ["main"],
    ))
    violations.extend(_exact_delta(
        "navigation fragments", baseline["navigation"]["fragment_links"],
        current["navigation"]["fragment_links"], [SKIP_FRAGMENT],
    ))
    for key in ("headings", "nav_elements", "duplicate_ids", "unresolved_fragment_targets"):
        if current["navigation"][key] != baseline["navigation"][key]:
            violations.append(f"preservation: navigation.{key} changed")

    violations.extend(_exact_delta(
        "resources", baseline["resources"], current["resources"], ADDED_RESOURCES,
    ))
    if current["styles"]["inline"] != baseline["styles"]["inline"]:
        violations.append("preservation: inline style blocks changed")
    if current["styles"]["inline_attributes"] != baseline["styles"]["inline_attributes"]:
        violations.append("preservation: inline style attributes changed")
    expected_hrefs = [entry["href"] for entry in baseline["styles"]["external"]] + list(CSS_HREFS)
    current_hrefs = [entry["href"] for entry in current["styles"]["external"]]
    if current_hrefs != expected_hrefs:
        violations.append(
            f"preservation: stylesheet order differs; expected={expected_hrefs}; got={current_hrefs}"
        )

    if current["responsive"]["viewport_meta"] != baseline["responsive"]["viewport_meta"]:
        violations.append("preservation: viewport metadata changed")
    if current["responsive"]["fixed_px_widths_over_360"]:
        violations.append("responsive: fixed width over 360px introduced")
    return violations


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.skip_links: list[dict[str, str]] = []
        self.main_count = 0
        self.hero_in_main = 0
        self.headers = 0
        self.footers = 0
        self.footer_in_main = 0
        self.stylesheets: list[str] = []

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set(attrs.get("class", "").split())

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_list}
        classes = self._classes(attrs)
        in_main = any(t == "main" and a.get("id") == "main" for t, a in self.stack)
        if tag == "a" and "pnx2-skip" in classes:
            self.skip_links.append(attrs)
        if tag == "main" and attrs.get("id") == "main":
            self.main_count += 1
        if tag == "div" and "community-hero" in classes and in_main:
            self.hero_in_main += 1
        if tag == "nav" and "pnx2-header" in classes:
            self.headers += 1
        if tag == "footer" and "pnx2-footer" in classes:
            self.footers += 1
            if in_main:
                self.footer_in_main += 1
        if tag == "link" and "stylesheet" in attrs.get("rel", "").lower().split():
            self.stylesheets.append(attrs.get("href", ""))
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


def check_structure(html: str) -> list[str]:
    parser = StructureParser()
    parser.feed(html)
    parser.close()
    violations: list[str] = []
    if len(parser.skip_links) != 1 or parser.skip_links[0].get("href") != "#main":
        violations.append("structure: expected one pnx2-skip link targeting #main")
    if parser.main_count != 1:
        violations.append("structure: expected one main#main")
    if parser.hero_in_main != 1:
        violations.append("structure: community hero must be inside main#main")
    if parser.headers != 1 or parser.footers != 1:
        violations.append("structure: expected one pnx2-header and one pnx2-footer")
    if parser.footer_in_main:
        violations.append("structure: footer must remain outside main")
    for href in CSS_HREFS:
        if parser.stylesheets.count(href) != 1:
            violations.append(f"structure: expected one stylesheet: {href}")
    return violations


def check_css(docs_dir: Path) -> list[str]:
    """Validate R4 CSS files and selector-scoped visual contracts."""
    violations: list[str] = []
    for rel in CSS_RELS:
        path = docs_dir / rel
        if not path.is_file():
            violations.append(f"css: missing file: {rel}")
            continue
        try:
            path.resolve().relative_to(docs_dir.resolve())
        except ValueError:
            violations.append(f"css: path escapes docs: {rel}")
            continue
        source = path.read_text(encoding="utf-8")
        for pattern, label in CSS_PROHIBITED:
            if re.search(pattern, source, re.IGNORECASE):
                violations.append(f"css: {path.name}: prohibited: {label}")
    shell = docs_dir / CSS_RELS[-1]
    if shell.is_file():
        source = shell.read_text(encoding="utf-8")
        contracts = (
            (
                r"nav\.pnx2-header",
                (("flex-wrap", r"nowrap\s*!important"),),
                "nav.pnx2-header nowrap",
            ),
            (
                r"nav\.pnx2-header\s+\.nav-links",
                (("overflow-x", r"auto"),),
                "nav links horizontal scroll",
            ),
            (
                r"\*\s*,\s*\*::before\s*,\s*\*::after",
                (("border-radius", r"0\s*!important"), ("box-shadow", r"none\s*!important")),
                "square shadowless reset",
            ),
        )
        for selector, declarations, label in contracts:
            if not _selector_has(source, selector, declarations):
                violations.append(f"css: R4 shell missing selector contract: {label}")

        mobile_blocks = _css_blocks(source, r"@media\s*\(\s*max-width\s*:\s*480px\s*\)")
        if not mobile_blocks or not any(
            _selector_has(
                block,
                r"\.principle-grid\s*,\s*\.participate-grid",
                (("grid-template-columns", r"1fr\s*!important"),),
            )
            for block in mobile_blocks
        ):
            violations.append("css: R4 shell missing <=480px single-column card contract")
    return violations


def check_dynamic_header(repo_root: Path) -> list[str]:
    """Validate routes and responsive classes in the rendered nav structure."""
    violations: list[str] = []
    nav_path = repo_root / "apps/web/src/components/NavHeader.tsx"
    source = nav_path.read_text(encoding="utf-8") if nav_path.is_file() else ""
    nav_links = re.search(r"const\s+navLinks\s*=\s*\[(?P<body>.*?)\]\s*;", source, re.DOTALL)
    nav_element = re.search(
        r"<nav\b(?P<attrs>[^>]*)>(?P<body>.*?)</nav>", source, re.DOTALL,
    )
    links_body = nav_links.group("body") if nav_links else ""
    nav_attrs = nav_element.group("attrs") if nav_element else ""
    nav_body = nav_element.group("body") if nav_element else ""
    if not nav_links:
        violations.append("header: navLinks definition missing")
    if not nav_element or "navLinks.map" not in nav_body:
        violations.append("header: rendered nav does not consume navLinks")
    for route in ("/bills", "/results", "/mp", "/municipal", "/analytics"):
        if not re.search(rf"href\s*:\s*`?/\$\{{locale\}}{re.escape(route)}`?", links_body):
            violations.append(f"header: missing route: {route}")
    for marker in ("flex-nowrap", "overflow-x-auto", "min-w-0", "whitespace-nowrap"):
        target = nav_attrs if marker != "whitespace-nowrap" else nav_body
        if marker not in target:
            violations.append(f"header: missing responsive marker: {marker}")
    if not (repo_root / "apps/web/src/components/PublicDataNav.tsx").is_file():
        violations.append("header: PublicDataNav source was deleted instead of retained")
    for rel in PUBLIC_DATA_PAGES:
        page = repo_root / rel
        if not page.is_file():
            violations.append(f"header: missing public-data page: {rel}")
            continue
        page_source = page.read_text(encoding="utf-8")
        if "PublicDataNav" in page_source:
            violations.append(f"header: duplicate PublicDataNav remains in {rel}")
    return violations


def check_mobile_chat(docs_dir: Path) -> list[str]:
    """Validate chat and static-header rules inside their intended media blocks."""
    path = docs_dir / "assets/redesign-v2/r2-landing.css"
    source = path.read_text(encoding="utf-8") if path.is_file() else ""
    narrow_blocks = _css_blocks(source, r"@media\s*\(\s*max-width\s*:\s*400px\s*\)")
    chat_blocks = [
        chat
        for media in narrow_blocks
        for chat in _css_blocks(media, r"#chatPanel")
    ]
    if not chat_blocks:
        return ["chat: missing <=400px #chatPanel rule"]
    required = (
        ("position", r"fixed\s*!important"),
        ("left", r"16px\s*!important"),
        ("right", r"16px\s*!important"),
        ("width", r"auto\s*!important"),
        ("overflow-y", r"auto\s*!important"),
    )
    body = chat_blocks[0]
    violations = [
        f"chat: missing viewport declaration: {name}"
        for name, value in required
        if not _has_declaration(body, name, value)
    ]
    if _has_declaration(body, "display", r"[^;}]+"):
        violations.append("chat: CSS must not override JavaScript-controlled display")
    header_contracts = (
        (r"nav\.pnx2-header", (("flex-wrap", r"nowrap\s*!important"),), "nowrap"),
        (
            r"nav\.pnx2-header\s+\.nav-links",
            (("overflow-x", r"auto"), ("scrollbar-width", r"none")),
            "horizontal scroll",
        ),
    )
    for selector, declarations, label in header_contracts:
        if not _selector_has(source, selector, declarations):
            violations.append(f"landing header: missing selector contract: {label}")
    mobile_header_blocks = _css_blocks(source, r"@media\s*\(\s*max-width\s*:\s*640px\s*\)")
    if not any(
        _selector_has(
            block,
            r"nav\.pnx2-header\s+\.nav-logo",
            (("font-size", r"0\s*!important"),),
        )
        for block in mobile_header_blocks
    ):
        violations.append("landing header: missing <=640px compact-logo contract")
    return violations


def check_r4(
    docs_dir: Path | None = None,
    inv_file: Path | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    target_docs = docs_dir or DOCS_DIR
    root = repo_root or target_docs.parent
    inventory_path = inv_file or R0_INVENTORY_FILE
    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    violations = r3.check_r3_all(target_docs, inventory_path)
    baseline = next((page for page in inv["pages"] if page["path"] == COMMUNITY_REL), None)
    community = target_docs / "community.html"
    if baseline is None or not community.is_file():
        violations.append("community: baseline or live file missing")
    else:
        current = _inventory_page(target_docs, COMMUNITY_REL)
        violations.extend(check_community_preservation(baseline, current))
        violations.extend(check_structure(community.read_text(encoding="utf-8")))
    violations.extend(check_css(target_docs))
    violations.extend(check_dynamic_header(root))
    violations.extend(check_mobile_chat(target_docs))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    violations = check_r4()
    if args.json:
        print(json.dumps(violations, ensure_ascii=False, indent=2))
    elif violations:
        for violation in violations:
            print(f"FAIL  {violation}")
    else:
        print("OK  r4_community_header_check: all checks passed")
    return 2 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
