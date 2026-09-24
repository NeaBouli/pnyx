#!/usr/bin/env python3
"""Fail-closed validator for the R3 wiki-shell (pilot + full wiki migration).

The R3 phase changes all 14 wiki pages (docs/wiki/*.html).  The R2 landing
remains semantically exact, and the other 21 non-wiki pages remain
byte-identical to the frozen R0 inventory.

Public interface
----------------
``check_r3()``        — historical pilot-only gate
``check_r3_all()``    — full-wiki gate (all 14 wiki pages)
``check_r3_wiki_page(page_rel, baseline, docs_dir)``
                      — per-page preservation + structure check
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
FAQ_REL = "docs/wiki/faq.html"

# All 14 wiki pages (pilot + 13 migrated)
WIKI_RELS: tuple[str, ...] = (
    "docs/wiki/index.html",
    "docs/wiki/api.html",
    "docs/wiki/architecture.html",
    "docs/wiki/broadcasting.html",
    "docs/wiki/contributing.html",
    "docs/wiki/database.html",
    "docs/wiki/delete-account.html",
    "docs/wiki/faq.html",
    "docs/wiki/modules.html",
    "docs/wiki/privacy.html",
    "docs/wiki/roadmap.html",
    "docs/wiki/security.html",
    "docs/wiki/whitepaper.html",
    "docs/wiki/zk-voting.html",
)

# Pages whose R0 baseline contained a .hero element inside the page content
WIKI_PAGES_WITH_HERO: frozenset[str] = frozenset(WIKI_RELS) - frozenset({"docs/wiki/zk-voting.html"})

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
FAQ_A11Y_SCRIPT_HREF = "../assets/redesign-v2/r3-faq-accessibility.js"
FAQ_A11Y_SCRIPT_REL = "assets/redesign-v2/r3-faq-accessibility.js"
FAQ_A11Y_RESOURCE = {
    "kind": "relative-file",
    "source": "script.src",
    "url": FAQ_A11Y_SCRIPT_HREF,
}
FAQ_A11Y_SCRIPT = {
    "src": FAQ_A11Y_SCRIPT_HREF,
    "attrs": {"defer": "", "src": FAQ_A11Y_SCRIPT_HREF},
}

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
    """Require byte identity for every R0 page outside the R2/R3 pages.

    For the pilot-only gate the only allowed changes are docs/index.html and
    the pilot docs/wiki/index.html.  For the full-wiki gate use
    ``check_nonwiki_parity`` instead.
    """
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
        if actual != r2_landing_check.approved_analytics_delta.expected_sha256(page["path"], page["sha256"]):
            violations.append(
                f"parity: {page['path']}: sha256 changed; R3 pilot permits only {PILOT_REL}"
            )
    return violations


def check_nonwiki_parity(inv: dict, repo_root: Path) -> list[str]:
    """Require byte identity outside the gated R2-R4 public pages.

    The later R4 gate owns ``docs/community.html`` preservation, while this
    historical R3 gate continues to validate the landing and all 14 wiki pages.
    """
    violations: list[str] = []
    # T-346: representative.html download section repaired (broken APK + dead web route).
    allowed = frozenset({"docs/index.html", "docs/community.html", "docs/representative.html"} | set(WIKI_RELS))
    for page in inv["pages"]:
        if page["path"] in allowed:
            continue
        target = repo_root / page["path"]
        if not target.is_file():
            violations.append(f"parity: {page['path']}: missing file")
            continue
        actual = _sha256_file(target)
        if actual != r2_landing_check.approved_analytics_delta.expected_sha256(page["path"], page["sha256"]):
            violations.append(
                f"parity: {page['path']}: sha256 changed; "
                "R2-R4 gates permit only docs/index.html, docs/community.html and wiki pages"
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
    """Backward-compatible pilot-only preservation gate.

    Delegates to the generic ``check_wiki_page_preservation`` for the shared
    contract, then adds the pilot-specific media-query check.
    """
    violations = check_wiki_page_preservation(PILOT_REL, baseline, current)
    # Strip the page_rel prefix added by the generic function so existing tests
    # that compare plain violation strings remain compatible.
    violations = [v.replace(f"({PILOT_REL})", "").replace(f"preservation({PILOT_REL}): ", "preservation: ").replace(f"responsive({PILOT_REL}): ", "responsive: ") for v in violations]

    # Pilot-specific check: exact media-query set from the R3 shell
    responsive = current["responsive"]
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
        self.footer_in_main_count = 0
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
            if any(
                parent_tag == "main" and parent_attrs.get("id") == "main"
                for parent_tag, parent_attrs in self.stack
            ):
                self.footer_in_main_count += 1
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


def check_structure(html: str, requires_hero: bool = True) -> list[str]:
    """Parser-backed structural gate.

    Parameters
    ----------
    html:
        Full HTML source of the page.
    requires_hero:
        ``True`` (default) when the R0 baseline contained a ``.hero`` element
        inside the page content — all wiki pages except ``zk-voting.html``.
        Pass ``False`` for pages that had no hero in the baseline.
    """
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
    if requires_hero and parser.hero_in_main_count != 1:
        violations.append("structural: wiki hero must be nested inside main#main")
    if not requires_hero and parser.hero_in_main_count != 0:
        violations.append("structural: hero must not appear on this page (no R0 baseline)")
    if parser.header_count != 1:
        violations.append("structural: expected one live nav.pnx2-header")
    if parser.footer_count != 1:
        violations.append("structural: expected one live footer.pnx2-footer")
    if parser.footer_in_main_count:
        violations.append("structural: footer.pnx2-footer must be outside main#main")
    for href in R3_CSS_HREFS:
        if parser.stylesheets.count(href) != 1:
            violations.append(f"structural: expected one live stylesheet link: {href}")
    return violations


def check_wiki_page_preservation(
    page_rel: str, baseline: dict, current: dict
) -> list[str]:
    """Preservation gate for a single wiki page (pilot or one of the 13 migrated).

    Allows only:
    - the bilingual skip-link pair
    - the skip-link in the links list
    - the skip text chunk
    - the ``id="main"`` navigation id
    - the ``#main`` fragment link
    - the three R3 CSS resource entries
    - the three R3 external stylesheets appended after any R0 stylesheets

    Everything else must be identical to the R0 baseline.
    """
    baseline = r2_landing_check.approved_analytics_delta.baseline_without_analytics(baseline)
    violations: list[str] = []
    for key in PRESERVED_EXACT_KEYS:
        if page_rel == FAQ_REL and key == "scripts":
            continue
        if current.get(key) != baseline.get(key):
            violations.append(f"preservation({page_rel}): exact contract changed: {key}")

    if page_rel == FAQ_REL:
        for key in ("inline", "inline_count"):
            if current["scripts"][key] != baseline["scripts"][key]:
                violations.append(f"preservation({page_rel}): scripts.{key} changed")
        violations.extend(_exact_delta(
            f"external scripts ({page_rel})",
            baseline["scripts"]["external"],
            current["scripts"]["external"],
            [FAQ_A11Y_SCRIPT],
        ))

    violations.extend(_exact_delta(
        f"bilingual pairs ({page_rel})",
        baseline["bilingual"]["pairs"],
        current["bilingual"]["pairs"],
        [SKIP_PAIR],
    ))
    if current["bilingual"]["only_data_el"] != baseline["bilingual"]["only_data_el"]:
        violations.append(f"preservation({page_rel}): bilingual.only_data_el changed")
    if current["bilingual"]["only_data_en"] != baseline["bilingual"]["only_data_en"]:
        violations.append(f"preservation({page_rel}): bilingual.only_data_en changed")
    if current["bilingual"]["counts"]["pairs"] != baseline["bilingual"]["counts"]["pairs"] + 1:
        violations.append(f"preservation({page_rel}): bilingual pair count differs")

    violations.extend(_exact_delta(
        f"links ({page_rel})", baseline["links"], current["links"], [SKIP_LINK]
    ))
    violations.extend(_exact_delta(
        f"text chunks ({page_rel})",
        baseline["text"]["chunks"],
        current["text"]["chunks"],
        [SKIP_PAIR["data_el"]],
    ))
    violations.extend(_exact_delta(
        f"navigation ids ({page_rel})",
        baseline["navigation"]["ids"],
        current["navigation"]["ids"],
        ["main"],
    ))
    violations.extend(_exact_delta(
        f"navigation fragments ({page_rel})",
        baseline["navigation"]["fragment_links"],
        current["navigation"]["fragment_links"],
        [SKIP_FRAGMENT],
    ))
    for key in ("headings", "nav_elements", "duplicate_ids", "unresolved_fragment_targets"):
        if current["navigation"][key] != baseline["navigation"][key]:
            violations.append(f"preservation({page_rel}): navigation.{key} changed")

    resource_additions = ADDED_RESOURCES + (
        (FAQ_A11Y_RESOURCE,) if page_rel == FAQ_REL else ()
    )
    violations.extend(_exact_delta(
        f"resources ({page_rel})",
        baseline["resources"],
        current["resources"],
        resource_additions,
    ))
    if current["styles"]["inline"] != baseline["styles"]["inline"]:
        violations.append(f"preservation({page_rel}): inline style blocks changed")
    if current["styles"]["inline_attributes"] != baseline["styles"]["inline_attributes"]:
        violations.append(f"preservation({page_rel}): inline style attributes changed")

    # Stylesheets: R0 stylesheets preserved in order, then exactly R3_CSS_HREFS appended
    r0_external_hrefs = [e.get("href") for e in baseline["styles"]["external"]]
    current_external_hrefs = [e.get("href") for e in current["styles"]["external"]]
    expected_hrefs = r0_external_hrefs + list(R3_CSS_HREFS)
    if current_external_hrefs != expected_hrefs:
        violations.append(
            f"preservation({page_rel}): external stylesheet order differs; "
            f"expected {expected_hrefs!r}, got {current_external_hrefs!r}"
        )
    for entry in current["styles"]["external"]:
        if entry.get("href") in R3_CSS_HREFS:
            if not entry.get("resolved") or not entry.get("repo_path", "").startswith(
                "docs/assets/redesign-v2/"
            ):
                violations.append(
                    f"preservation({page_rel}): R3 stylesheet did not resolve locally: "
                    f"{entry.get('href')}"
                )

    responsive = current["responsive"]
    if responsive["viewport_meta"] != baseline["responsive"]["viewport_meta"]:
        violations.append(f"preservation({page_rel}): viewport metadata changed")
    if responsive["fixed_px_widths_over_360"]:
        violations.append(f"responsive({page_rel}): fixed width over 360px introduced")
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


def check_faq_accessibility_asset(docs_dir: Path) -> list[str]:
    """Require the local FAQ keyboard adapter and its bounded behavior."""
    path = docs_dir / FAQ_A11Y_SCRIPT_REL
    if not path.is_file():
        return [f"faq accessibility: missing local asset: {FAQ_A11Y_SCRIPT_REL}"]
    source = path.read_text(encoding="utf-8")
    required = (
        'question.setAttribute("role", "button")',
        'question.setAttribute("tabindex", "0")',
        '"aria-expanded"',
        'question.setAttribute("aria-controls", answerId)',
        'event.key === "Enter"',
        'event.key === " "',
        "event.preventDefault()",
        "question.click()",
    )
    return [
        f"faq accessibility: missing behavior marker: {marker}"
        for marker in required
        if marker not in source
    ]


def check_r3_wiki_page(
    page_rel: str,
    baseline: dict,
    docs_dir: Path,
) -> list[str]:
    """Run preservation + structural checks for a single wiki page.

    Parameters
    ----------
    page_rel:
        Repository-relative path, e.g. ``"docs/wiki/api.html"``.
    baseline:
        R0 inventory page entry for *page_rel*.
    docs_dir:
        Absolute path to the ``docs/`` directory.
    """
    page_path = docs_dir.parent / page_rel
    if not page_path.is_file():
        return [f"preservation({page_rel}): live file missing"]
    current = _inventory_page_at(docs_dir, page_rel)
    violations = check_wiki_page_preservation(page_rel, baseline, current)
    requires_hero = page_rel in WIKI_PAGES_WITH_HERO
    violations.extend(check_structure(page_path.read_text(encoding="utf-8"), requires_hero=requires_hero))
    return violations


def check_r3(
    docs_dir: Path | None = None,
    inv_file: Path | None = None,
) -> list[str]:
    """Pilot-only gate (backward-compatible).  Checks the R3 pilot page
    (``docs/wiki/index.html``) and requires byte-identity for all other pages
    except the R2 landing.  The 13 newly migrated wiki pages are NOT checked
    by this function; use ``check_r3_all()`` instead.
    """
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


def check_r3_all(
    docs_dir: Path | None = None,
    inv_file: Path | None = None,
) -> list[str]:
    """Full-wiki gate.  Checks all 14 wiki pages and requires byte-identity
    for every other page except the R2 landing (``docs/index.html``).
    """
    target_docs = docs_dir or DOCS_DIR
    inv = _load_inventory(inv_file)
    violations = check_nonwiki_parity(inv, target_docs.parent)
    violations.extend(check_landing_r2(inv, target_docs))
    baselines = {p["path"]: p for p in inv["pages"]}
    for page_rel in WIKI_RELS:
        baseline = baselines.get(page_rel)
        if baseline is None:
            violations.append(f"preservation({page_rel}): R0 baseline entry missing")
            continue
        violations.extend(check_r3_wiki_page(page_rel, baseline, target_docs))
    violations.extend(check_css_files(target_docs))
    violations.extend(check_faq_accessibility_asset(target_docs))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--all",
        action="store_true",
        dest="all_wiki",
        help="Run the full-wiki gate (default; retained for explicit CI commands).",
    )
    mode.add_argument(
        "--pilot",
        action="store_true",
        help="Run the historical pilot-only gate.",
    )
    args = parser.parse_args()
    full_wiki = not args.pilot
    violations = check_r3_all() if full_wiki else check_r3()
    label = "r3_wiki_all_check" if full_wiki else "r3_wiki_pilot_check"
    if args.json:
        print(json.dumps(violations, ensure_ascii=False, indent=2))
    elif violations:
        for violation in violations:
            print(f"FAIL  {violation}")
    else:
        print(f"OK  {label}: all checks passed")
    return 2 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
