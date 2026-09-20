#!/usr/bin/env python3
"""Fail-closed validator for the R3 wiki-shell pilot.

The R3 pilot may change only ``docs/wiki/index.html`` within the public HTML
surface. The R2 landing remains semantically exact, and the other 33 pages
remain byte-identical to the frozen R0 inventory.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r0_inventory  # noqa: E402
import r2_landing_check  # noqa: E402

REPO_ROOT = r0_inventory.REPO_ROOT
DOCS_DIR = r0_inventory.DOCS_DIR
R0_INVENTORY_FILE = REPO_ROOT / "docs/planning/r0/R0_DOCS_SURFACE_INVENTORY.json"
PILOT_REL = "docs/wiki/index.html"

R3_CSS_HREFS = (
    "../assets/redesign-v2/tokens.css",
    "../assets/redesign-v2/foundation.css",
    "../assets/redesign-v2/r3-wiki.css",
)
R3_CSS_RELS = (
    "assets/redesign-v2/tokens.css",
    "assets/redesign-v2/foundation.css",
    "assets/redesign-v2/r3-wiki.css",
)

PRESERVED_EXACT_KEYS = r2_landing_check.PRESERVED_EXACT_KEYS
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
    for href in R3_CSS_HREFS
) + ({"kind": "fragment", "source": "a.href", "url": "#main"},)

CSS_PROHIBITED = (
    (r"(?:linear|radial|conic)-gradient\s*\(", "gradient"),
    (r"box-shadow\s*:[^;]*?(?:px|em|rem|%|vw|vh|rgba?\(|#[0-9a-fA-F])", "non-none box-shadow"),
    (r"text-shadow\s*:[^;]*?(?:px|em|rem|rgba?\(|#[0-9a-fA-F])", "text shadow"),
    (r"letter-spacing\s*:\s*-", "negative letter-spacing"),
    (r"font-size\s*:[^;{}]*\b[\d.]+\s*vw\b", "viewport-scaled font size"),
    (r"@import\s+(?:url\(\s*)?['\"]?\s*(?:https?:)?//", "external @import"),
    (r"url\(\s*['\"]?\s*(?:https?:)?//", "external url"),
    (r"(?:backdrop-)?filter\s*:[^;{}]*\bblur\s*\(", "blur filter"),
)

VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inventory(path: Path | None = None) -> dict:
    target = path or R0_INVENTORY_FILE
    if not target.is_file():
        raise FileNotFoundError(f"R0 inventory missing: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


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
    if expected == actual:
        return []
    details: list[str] = []
    missing = list((expected - actual).elements())
    extra = list((actual - expected).elements())
    if missing:
        details.append(f"missing={missing}")
    if extra:
        details.append(f"unexpected={extra}")
    return [f"preservation: {label} differs ({'; '.join(details)})"]


def check_nonpilot_parity(inv: dict, repo_root: Path) -> list[str]:
    """Require byte identity for every R0 page outside the R2/R3 pages."""
    violations: list[str] = []
    allowed = {"docs/index.html", PILOT_REL}
    for page in inv["pages"]:
        if page["path"] in allowed:
            continue
        target = repo_root / page["path"]
        if not target.is_file():
            violations.append(f"parity: {page['path']}: missing file")
            continue
        actual = _sha256_file(target)
        if actual != page["sha256"]:
            violations.append(
                f"parity: {page['path']}: sha256 changed; R3 pilot permits only {PILOT_REL}"
            )
    return violations


def check_landing_r2(inv: dict, docs_dir: Path) -> list[str]:
    """Keep the already accepted R2 landing contracts exact during R3."""
    violations: list[str] = []
    baseline = next((p for p in inv["pages"] if p["path"] == "docs/index.html"), None)
    landing = docs_dir / "index.html"
    if baseline is None or not landing.is_file():
        return ["r2: landing baseline or live file missing"]
    current = _inventory_page_at(docs_dir, "docs/index.html")
    violations.extend(r2_landing_check.check_index_preservation(baseline, current))
    violations.extend(r2_landing_check.check_structural(landing.read_text(encoding="utf-8")))
    violations.extend(r2_landing_check.check_css_files(docs_dir))
    return [f"r2: {item}" for item in violations]


def _inventory_page_at(docs_dir: Path, page_rel: str) -> dict:
    saved_root = r0_inventory.REPO_ROOT
    saved_docs = r0_inventory.DOCS_DIR
    try:
        r0_inventory.REPO_ROOT = docs_dir.parent
        r0_inventory.DOCS_DIR = docs_dir
        return r0_inventory.inventory_page(page_rel)
    finally:
        r0_inventory.REPO_ROOT = saved_root
        r0_inventory.DOCS_DIR = saved_docs


def check_pilot_preservation(baseline: dict, current: dict) -> list[str]:
    violations: list[str] = []
    for key in PRESERVED_EXACT_KEYS:
        if current.get(key) != baseline.get(key):
            violations.append(f"preservation: exact contract changed: {key}")

    violations.extend(_exact_delta(
        "bilingual pairs", baseline["bilingual"]["pairs"],
        current["bilingual"]["pairs"], [SKIP_PAIR],
    ))
    if current["bilingual"]["only_data_el"] != baseline["bilingual"]["only_data_el"]:
        violations.append("preservation: bilingual.only_data_el changed")
    if current["bilingual"]["only_data_en"] != baseline["bilingual"]["only_data_en"]:
        violations.append("preservation: bilingual.only_data_en changed")
    if current["bilingual"]["counts"]["pairs"] != baseline["bilingual"]["counts"]["pairs"] + 1:
        violations.append("preservation: bilingual pair count differs")

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
    external = current["styles"]["external"]
    if [entry.get("href") for entry in external] != list(R3_CSS_HREFS):
        violations.append("preservation: external stylesheet order differs")
    for entry in external:
        if not entry.get("resolved") or not entry.get("repo_path", "").startswith("docs/assets/redesign-v2/"):
            violations.append(f"preservation: stylesheet did not resolve locally: {entry.get('href')}")

    responsive = current["responsive"]
    if responsive["viewport_meta"] != baseline["responsive"]["viewport_meta"]:
        violations.append("preservation: viewport metadata changed")
    if responsive["fixed_px_widths_over_360"]:
        violations.append("responsive: fixed width over 360px introduced")
    expected_media = {
        "@media (max-width: 640px)",
        "@media (max-width: 920px)",
        "@media (prefers-reduced-motion: reduce)",
    }
    if set(responsive["media_queries"]) != expected_media:
        violations.append("responsive: media-query set differs from the bounded R3 shell")
    return violations


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.skip_links: list[dict[str, str]] = []
        self.main_count = 0
        self.hero_in_main_count = 0
        self.header_count = 0
        self.footer_count = 0
        self.stylesheets: list[str] = []

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set(attrs.get("class", "").split())

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_list}
        classes = self._classes(attrs)
        if tag == "a" and "pnx2-skip" in classes:
            self.skip_links.append(attrs)
        if tag == "main" and attrs.get("id") == "main":
            self.main_count += 1
        if tag == "div" and "hero" in classes and any(
            parent_tag == "main" and parent_attrs.get("id") == "main"
            for parent_tag, parent_attrs in self.stack
        ):
            self.hero_in_main_count += 1
        if tag == "nav" and "pnx2-header" in classes:
            self.header_count += 1
        if tag == "footer" and "pnx2-footer" in classes:
            self.footer_count += 1
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
    if len(parser.skip_links) != 1:
        violations.append("structural: expected one live pnx2-skip link")
    else:
        skip = parser.skip_links[0]
        if skip.get("href") != "#main" or skip.get("data-el") != SKIP_PAIR["data_el"] or skip.get("data-en") != SKIP_PAIR["data_en"]:
            violations.append("structural: live skip link contract differs")
    if parser.main_count != 1:
        violations.append("structural: expected one live main#main landmark")
    if parser.hero_in_main_count != 1:
        violations.append("structural: wiki hero must be nested inside main#main")
    if parser.header_count != 1:
        violations.append("structural: expected one live nav.pnx2-header")
    if parser.footer_count != 1:
        violations.append("structural: expected one live footer.pnx2-footer")
    for href in R3_CSS_HREFS:
        if parser.stylesheets.count(href) != 1:
            violations.append(f"structural: expected one live stylesheet link: {href}")
    return violations


def check_css_files(docs_dir: Path) -> list[str]:
    violations: list[str] = []
    for rel in R3_CSS_RELS:
        target = docs_dir / rel
        if not target.is_file():
            violations.append(f"css: missing file: {rel}")
            continue
        try:
            target.resolve().relative_to(docs_dir.resolve())
        except ValueError:
            violations.append(f"css: path escapes docs/: {rel}")
            continue
        content = target.read_text(encoding="utf-8")
        for pattern, label in CSS_PROHIBITED:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"css: {target.name}: prohibited: {label}")
    shell = docs_dir / R3_CSS_RELS[-1]
    if shell.is_file():
        content = shell.read_text(encoding="utf-8")
        if "border-radius: 0 !important" not in content:
            violations.append("css: R3 shell must enforce square corners")
        if "box-shadow: none !important" not in content:
            violations.append("css: R3 shell must disable legacy shadows")
    return violations


def check_r3(
    docs_dir: Path | None = None,
    inv_file: Path | None = None,
) -> list[str]:
    target_docs = docs_dir or DOCS_DIR
    inv = _load_inventory(inv_file)
    violations = check_nonpilot_parity(inv, target_docs.parent)
    violations.extend(check_landing_r2(inv, target_docs))
    pilot_path = target_docs / "wiki/index.html"
    baseline = next((p for p in inv["pages"] if p["path"] == PILOT_REL), None)
    if baseline is None or not pilot_path.is_file():
        violations.append("preservation: R0 wiki pilot baseline or live file missing")
    else:
        current = _inventory_page_at(target_docs, PILOT_REL)
        violations.extend(check_pilot_preservation(baseline, current))
        violations.extend(check_structure(pilot_path.read_text(encoding="utf-8")))
    violations.extend(check_css_files(target_docs))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    violations = check_r3()
    if args.json:
        print(json.dumps(violations, ensure_ascii=False, indent=2))
    elif violations:
        for violation in violations:
            print(f"FAIL  {violation}")
    else:
        print("OK  r3_wiki_pilot_check: all checks passed")
    return 2 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
