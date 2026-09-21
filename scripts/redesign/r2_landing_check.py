#!/usr/bin/env python3
"""Fail-closed validator for the production landing-page redesign.

Checks:
 1. R0 byte-parity for every public page outside the separately gated Landing,
    Community and Wiki surfaces.
 2. docs/index.html preservation — metadata, JSON-LD, API/storage/external-host
    contracts, form semantics, script count and all non-navigation bilingual
    content remain present while the owner-approved design structure may change.
 3. Structural additions — semantic shell, exact handoff hero/live/history
    structures, local stylesheet links and prototype-runtime exclusion.
 4. CSS file checks — all redesign CSS files must exist inside
    docs/assets/redesign-v2/, be contained within docs/, and the CSS files
    must not introduce gradients, non-none box-shadows, negative
    letter-spacing, viewport-scaled font sizes, or external @import rules.

Exit code 0 = clean; exit code 2 = violations found (nothing written).

Run with:
    python3 scripts/redesign/r2_landing_check.py
    python3 scripts/redesign/r2_landing_check.py --json
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

# same-directory import
sys.path.insert(0, str(Path(__file__).resolve().parent))
import r0_inventory  # noqa: E402

REPO_ROOT = r0_inventory.REPO_ROOT
DOCS_DIR = r0_inventory.DOCS_DIR
R0_INVENTORY_FILE = REPO_ROOT / "docs/planning/r0/R0_DOCS_SURFACE_INVENTORY.json"

# Relative paths of the R2 CSS files (relative to docs/)
R2_CSS_RELS: list[str] = [
    "assets/redesign-v2/tokens.css",
    "assets/redesign-v2/foundation.css",
    "assets/redesign-v2/r2-landing.css",
    "assets/redesign-v2/r5-landing-fidelity.css",
]

# These parser-backed categories are functional/content contracts. R2 may not
# alter them at all; visual additions are represented by the explicit allowed
# deltas below instead of brittle string/regex counts.
PRESERVED_EXACT_KEYS: tuple[str, ...] = (
    "document",
    "meta",
    "seo",
    "json_ld",
    "forms",
    "api_contracts",
    "storage",
    "media",
    "interactions",
    "scripts",
    "external_hosts",
    "states",
    "errors",
)

# Landing R5 intentionally adds presentation markup and an aria-live region.
# Forms, media and scripts use stricter purpose-built checks below while the
# shared exact-key constant remains intact for the wiki preservation gate.
LANDING_PRESERVED_EXACT_KEYS: tuple[str, ...] = tuple(
    key for key in PRESERVED_EXACT_KEYS
    if key not in {"forms", "media", "scripts", "states"}
)

GATED_PUBLIC_PAGES = {
    "docs/index.html",
    "docs/community.html",
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
}

REMOVABLE_HEADER_PAIRS = {
    ("Beta", "Beta"),
    ("Πώς λειτουργεί", "How it works"),
    ("Διαφάνεια", "Transparency"),
    ("Χαρακτηριστικά", "Features"),
    ("Charts", "Charts"),
    ("Forum", "Forum"),
    ("Roadmap", "Roadmap"),
    ("Wiki", "Wiki"),
    ("Community", "Community"),
    ("Δήμος", "Municipality"),
    ("Λήψη App", "Download App"),
    ("Επικοινωνία", "Contact"),
}

ALLOWED_R5_INLINE_SCRIPTS = {
    0: {
        "index": 0,
        "sha256": "843121274e8ed147eb9f4e6d5bfd3e8bbc65f4c9e88e4b37f6863f5d0320518d",
        "bytes": 4938,
    },
    5: {
        "index": 5,
        "sha256": "30e923d66d004398c9c10599142edcf45fc5efeb336b4fa4cc7419d6858454d0",
        "bytes": 20518,
    },
}

ALLOWED_R2_BILINGUAL_PAIR = {
    "data_el": "Μετάβαση στο κύριο περιεχόμενο",
    "data_en": "Skip to main content",
    "tag": "a",
}
ALLOWED_R2_LINK = {
    "class": "pnx2-skip",
    "data_el": "Μετάβαση στο κύριο περιεχόμενο",
    "data_en": "Skip to main content",
    "href": "#main",
    "kind": "fragment",
    "text": "Μετάβαση στο κύριο περιεχόμενο",
}
ALLOWED_R2_FRAGMENT = {"href": "#main", "resolved": True, "target_id": "main"}
ALLOWED_R2_RESOURCES: tuple[dict[str, str], ...] = tuple(
    {"kind": "relative-file", "source": "link.href", "url": href}
    for href in R2_CSS_RELS
)
ALLOWED_R2_RESOURCES = (*ALLOWED_R2_RESOURCES, {"kind": "fragment", "source": "a.href", "url": "#main"})

# (regex pattern, human-readable label) — prohibited in all R2 CSS files.
# box-shadow: none is explicitly permitted (it is a removal rule).
CSS_PROHIBITED: list[tuple[str, str]] = [
    (r"(?:linear|radial|conic)-gradient\s*\(", "gradient"),
    (r"box-shadow\s*:[^;]*?(?:px|em|rem|%|vw|vh|rgba?\(|#[0-9a-fA-F])", "non-none box-shadow"),
    (r"letter-spacing\s*:\s*-", "negative letter-spacing"),
    (r"font-size\s*:[^;{}]*\b[\d.]+\s*vw\b", "viewport-scaled font size"),
    (r"@import\s+(?:url\(\s*)?['\"]?\s*(?:https?:)?//", "external @import"),
]

VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_r0_inventory(inv_file: Path | None = None) -> dict:
    path = inv_file or R0_INVENTORY_FILE
    if not path.is_file():
        sys.exit(f"r2_landing_check: R0 inventory missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Check 1 — 34-page byte-parity
# ---------------------------------------------------------------------------

def check_parity(inv: dict, repo_root: Path) -> list[str]:
    """Return violations for public pages outside their approved phase gates."""
    violations: list[str] = []
    for page in inv["pages"]:
        if page["path"] in GATED_PUBLIC_PAGES:
            continue
        file_path = repo_root / page["path"]
        if not file_path.is_file():
            violations.append(f"parity: {page['path']}: missing file")
            continue
        actual = _sha256_file(file_path)
        if actual != page["sha256"]:
            violations.append(
                f"parity: {page['path']}: sha256 changed — "
                f"page is outside the Landing/Community/Wiki phase gates "
                f"(got {actual[:12]}…, expected {page['sha256'][:12]}…)"
            )
    return violations


# ---------------------------------------------------------------------------
# Check 2 — docs/index.html content preservation (direct presence checks)
# ---------------------------------------------------------------------------

def _counter(values: list[object] | tuple[object, ...]) -> Counter[str]:
    return Counter(r0_inventory.canonical_json(value) for value in values)


def _check_exact_delta(
    label: str,
    baseline: list[object],
    current: list[object],
    allowed_additions: list[object] | tuple[object, ...],
) -> list[str]:
    expected = _counter(baseline) + _counter(allowed_additions)
    actual = _counter(current)
    if actual == expected:
        return []
    missing = list((expected - actual).elements())
    extra = list((actual - expected).elements())
    details: list[str] = []
    if missing:
        details.append(f"missing={missing}")
    if extra:
        details.append(f"unexpected={extra}")
    return [f"preservation: {label} differs ({'; '.join(details)})"]


def check_index_preservation(baseline: dict, current: dict) -> list[str]:
    """Preserve functional/content contracts while permitting the new layout."""
    violations: list[str] = []

    for key in LANDING_PRESERVED_EXACT_KEYS:
        if current.get(key) != baseline.get(key):
            violations.append(f"preservation: exact contract changed: {key}")

    # Header navigation is intentionally consolidated. Subtract exactly the
    # one known R0 header occurrence of each replaced pair; same-valued body
    # content remains protected.
    baseline_pairs = Counter(
        (item.get("data_el", ""), item.get("data_en", ""))
        for item in baseline["bilingual"]["pairs"]
    )
    for pair in REMOVABLE_HEADER_PAIRS:
        if baseline_pairs[pair]:
            baseline_pairs[pair] -= 1
            if not baseline_pairs[pair]:
                del baseline_pairs[pair]
    current_pairs = Counter(
        (item.get("data_el", ""), item.get("data_en", ""))
        for item in current["bilingual"]["pairs"]
    )
    if baseline_pairs - current_pairs:
        violations.append(
            "preservation: non-navigation bilingual content removed: "
            f"{list((baseline_pairs - current_pairs).elements())}"
        )

    # Form behavior is compared without visual/accessibility-only attributes.
    functional_form_keys = ("tag", "type", "id", "name", "value", "form", "required", "checked")
    normalize_controls = lambda controls: Counter(
        tuple((key, item.get(key)) for key in functional_form_keys if key in item)
        for item in controls
    )
    if normalize_controls(current["forms"]["controls"]) != normalize_controls(baseline["forms"]["controls"]):
        violations.append("preservation: functional form controls changed")
    if current["forms"]["forms"] != baseline["forms"]["forms"]:
        violations.append("preservation: form definitions changed")

    # Runtime scripts may populate the new live presentation IDs, but only the
    # two reviewed R5 fingerprints may differ from the R0 baseline.
    if current["scripts"]["external"] != baseline["scripts"]["external"]:
        violations.append("preservation: external scripts changed")
    expected_inline = [
        ALLOWED_R5_INLINE_SCRIPTS.get(item["index"], item)
        for item in baseline["scripts"]["inline"]
    ]
    if current["scripts"]["inline"] != expected_inline:
        violations.append("preservation: inline script fingerprints changed")

    # Existing media sources are content contracts. New decorative reuse is
    # allowed and alt text may improve, but no previous source may disappear.
    baseline_media = Counter(
        item.get("src") for item in baseline["media"]["elements"] if item.get("src")
    )
    current_media = Counter(
        item.get("src") for item in current["media"]["elements"] if item.get("src")
    )
    if baseline_media - current_media:
        violations.append(
            f"preservation: media sources removed: {list((baseline_media - current_media).elements())}"
        )

    for key in ("duplicate_ids", "unresolved_fragment_targets"):
        if current["navigation"][key]:
            violations.append(f"preservation: navigation.{key} is not empty")

    expected_hrefs = [entry["href"] for entry in baseline["styles"]["external"]] + list(R2_CSS_RELS)
    current_hrefs = [entry["href"] for entry in current["styles"]["external"]]
    if current_hrefs != expected_hrefs:
        violations.append(
            f"preservation: external stylesheet order differs "
            f"(got {current_hrefs}, expected {expected_hrefs})"
        )

    if current["responsive"]["viewport_meta"] != baseline["responsive"]["viewport_meta"]:
        violations.append("preservation: viewport metadata changed")

    return violations


# ---------------------------------------------------------------------------
# Check 3 — structural additions
# ---------------------------------------------------------------------------

class _StructureParser(HTMLParser):
    """Collect only the live relationships required by the R2 shell."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.skip_links: list[dict[str, str]] = []
        self.main_count = 0
        self.hero_in_main_count = 0
        self.header_count = 0
        self.footer_count = 0
        self.stylesheets: list[str] = []
        self.ids: Counter[str] = Counter()
        self.classes: Counter[str] = Counter()
        self.header_hrefs: list[str] = []

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set(attrs.get("class", "").split())

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_list}
        classes = self._classes(attrs)
        if attrs.get("id"):
            self.ids[attrs["id"]] += 1
        self.classes.update(classes)
        if tag == "a" and any(parent_tag == "nav" and "pnx2-header" in self._classes(parent_attrs) for parent_tag, parent_attrs in self.stack):
            self.header_hrefs.append(attrs.get("href", ""))
        if tag == "a" and "pnx2-skip" in classes:
            self.skip_links.append(attrs)
        if tag == "main" and attrs.get("id") == "main":
            self.main_count += 1
        if tag == "section" and "landing-hero" in classes:
            if any(parent_tag == "main" and parent_attrs.get("id") == "main" for parent_tag, parent_attrs in self.stack):
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


def check_structural(html: str) -> list[str]:
    """Validate live R2 nodes and relationships with an HTML parser."""
    violations: list[str] = []
    parser = _StructureParser()
    parser.feed(html)
    parser.close()

    if len(parser.skip_links) != 1 or parser.skip_links[0].get("href") != "#main":
        violations.append("structural: expected one live pnx2-skip link targeting #main")
    if parser.main_count != 1:
        violations.append("structural: expected one live main#main landmark")
    if parser.hero_in_main_count != 1:
        violations.append("structural: landing hero must be nested inside main#main")
    if parser.header_count != 1:
        violations.append("structural: expected one live nav.pnx2-header")
    if parser.footer_count != 1:
        violations.append("structural: expected one live footer.pnx2-footer")
    for href in R2_CSS_RELS:
        if parser.stylesheets.count(href) != 1:
            violations.append(f"structural: expected one live stylesheet link: {href}")

    for class_name in (
        "pnx2-header-frame",
        "pnx2-live-panel",
        "pnx2-democracy-data",
        "pnx2-history-band",
    ):
        if parser.classes[class_name] != 1:
            violations.append(f"structural: expected one live .{class_name}")
    for id_name in (
        "heroParliamentDecision",
        "heroLiveStatus",
        "heroCitizenDecision",
        "heroCitizenMeta",
        "heroTier1",
        "heroTier2",
        "heroTier3",
        "historyTitle",
    ):
        if parser.ids[id_name] != 1:
            violations.append(f"structural: expected one live #{id_name}")

    expected_header_hrefs = ["#main", "#main", "#votes", "#roadmap", "wiki/", "community.html", "#download"]
    if parser.header_hrefs != expected_header_hrefs:
        violations.append(
            f"structural: consolidated header targets differ "
            f"(got {parser.header_hrefs}, expected {expected_header_hrefs})"
        )

    for marker in ("support.js", "text/x-dc", "<sc-if", "{{"):
        if marker in html:
            violations.append(f"structural: prototype runtime marker present: {marker}")
    return violations


# ---------------------------------------------------------------------------
# Check 4 — CSS file quality
# ---------------------------------------------------------------------------

def check_css_files(docs_dir: Path) -> list[str]:
    """Return violations for missing, escaped, or prohibited-pattern CSS files."""
    violations: list[str] = []
    for rel in R2_CSS_RELS:
        css_path = docs_dir / rel
        # 4a. File must exist
        if not css_path.is_file():
            violations.append(f"css: missing file: {rel}")
            continue
        # 4b. Resolved path must stay inside docs/
        try:
            css_path.resolve().relative_to(docs_dir.resolve())
        except ValueError:
            violations.append(f"css: path escapes docs/: {rel}")
            continue
        # 4c. Prohibited pattern scan
        content = css_path.read_text(encoding="utf-8")
        for pattern, label in CSS_PROHIBITED:
            if re.search(pattern, content):
                violations.append(
                    f"css: {Path(rel).name}: prohibited: {label}"
                )
    return violations


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_r2(
    docs_dir: Path | None = None,
    inv_file: Path | None = None,
) -> list[str]:
    """Run all R2 checks and return a list of violation strings.

    An empty list means clean.

    *docs_dir* and *inv_file* allow tests to inject alternative roots and
    inventories without touching the real docs/ tree.
    """
    target_docs = docs_dir if docs_dir is not None else DOCS_DIR
    inv = _load_r0_inventory(inv_file)
    return _run_all(inv, target_docs)


def _run_all(inv: dict, docs_dir: Path) -> list[str]:
    violations: list[str] = []
    violations.extend(check_parity(inv, docs_dir.parent))
    if (docs_dir / "index.html").is_file():
        html = (docs_dir / "index.html").read_text(encoding="utf-8")
        baseline = next(
            (page for page in inv["pages"] if page["path"] == "docs/index.html"),
            None,
        )
        if baseline is None:
            violations.append("preservation: R0 landing baseline missing")
        else:
            saved_root = r0_inventory.REPO_ROOT
            saved_docs = r0_inventory.DOCS_DIR
            try:
                r0_inventory.REPO_ROOT = docs_dir.parent
                r0_inventory.DOCS_DIR = docs_dir
                current = r0_inventory.inventory_page("docs/index.html")
            finally:
                r0_inventory.REPO_ROOT = saved_root
                r0_inventory.DOCS_DIR = saved_docs
            violations.extend(check_index_preservation(baseline, current))
        violations.extend(check_structural(html))
    else:
        violations.append("structural: docs/index.html missing")
    violations.extend(check_css_files(docs_dir))
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="Output JSON array")
    args = ap.parse_args()

    violations = check_r2()
    if args.json:
        print(json.dumps(violations, ensure_ascii=False, indent=2))
    else:
        if violations:
            for v in violations:
                print(f"FAIL  {v}")
        else:
            print("OK  r2_landing_check: all checks passed")
    return 2 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
