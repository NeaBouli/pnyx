#!/usr/bin/env python3
"""EKA-40: generated project facts (module/endpoint/table/container counts).

Counts are derived from source, so every published number can cite one dated artifact:

    python3 scripts/project_facts.py --write    regenerate docs/project-facts.json
    python3 scripts/project_facts.py --check    fail if the committed artifact is stale (CI)
    python3 scripts/project_facts.py --claims   fail on unlabelled conflicting/imprecise claims
    python3 scripts/project_facts.py --check-consumers   CI consumer drift gate
    python3 scripts/project_facts.py --update-consumers  refresh registered public copy

Standard library only. Definitions are fixed in ``DEFINITIONS`` so pages can quote them.
"""
from __future__ import annotations

import argparse
import ast
import json
from html import unescape
from html.parser import HTMLParser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "docs" / "project-facts.json"
MAIN = ROOT / "apps" / "api" / "main.py"
ROUTERS = ROOT / "apps" / "api" / "routers"
MODELS = ROOT / "apps" / "api" / "models.py"
COMPOSE_PROD = ROOT / "infra" / "docker" / "docker-compose.prod.yml"
AS_OF = "2026-10-31"
CONSUMERS = ROOT / "scripts" / "project_fact_consumers.json"

DEFINITIONS = {
    "modules_spec": "Highest module number in the /health module list (MOD-01 … MOD-NN).",
    "modules_listed": "Entries in the /health module list of apps/api/main.py.",
    "modules_inactive": "Listed entries marked (deferred) or (disabled).",
    "api_endpoints": "FastAPI route decorators (@router/@app .get/.post/.put/.patch/.delete) in apps/api/main.py and apps/api/routers/*.py.",
    "api_routers": "Python modules in apps/api/routers that declare at least one route.",
    "db_tables_orm": "__tablename__ declarations in apps/api/models.py (migration-only tables not counted).",
    "prod_containers": "Services in infra/docker/docker-compose.prod.yml.",
}

ROUTE_RE = re.compile(r"^@(?:router|app)\.(?:get|post|put|patch|delete)\(", re.MULTILINE)


def health_modules(text: str) -> list[str]:
    block = re.search(r'"modules":\s*\[(.*?)\]', text, re.DOTALL)
    if block is None:
        raise SystemExit("project_facts: /health module list not found in apps/api/main.py")
    return re.findall(r'"(MOD-\d+[^"]*)"', block.group(1))


def compose_services(text: str) -> list[str]:
    services: list[str] = []
    inside = False
    for line in text.splitlines():
        if re.match(r"^services:\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^\S", line):
            break
        match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
        if inside and match:
            services.append(match.group(1))
    return services


def compute() -> dict[str, object]:
    main_text = MAIN.read_text(encoding="utf-8")
    modules = health_modules(main_text)
    numbers = [int(re.match(r"MOD-(\d+)", m).group(1)) for m in modules]
    router_files = sorted(ROUTERS.glob("*.py"))
    per_router = {p.name: len(ROUTE_RE.findall(p.read_text(encoding="utf-8"))) for p in router_files}
    routed = {name: n for name, n in per_router.items() if n}
    endpoints = sum(routed.values()) + len(ROUTE_RE.findall(main_text))
    tables = re.findall(r"__tablename__\s*=\s*[\"']([^\"']+)[\"']", MODELS.read_text(encoding="utf-8"))
    services = compose_services(COMPOSE_PROD.read_text(encoding="utf-8"))
    # Read constants without importing application code or its environment.
    payments = ast.parse((ROOT / "apps/api/routers/payments.py").read_text(encoding="utf-8"))
    costs = {node.targets[0].id: ast.literal_eval(node.value) for node in payments.body
             if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
             and node.targets[0].id in {"SERVER_COST_MONTHLY", "DOMAIN_COST_YEARLY"}}
    monthly, domain = costs["SERVER_COST_MONTHLY"], costs["DOMAIN_COST_YEARLY"]
    return {
        "as_of": AS_OF,
        "cost_basis": {
            "as_of": "2026-10",
            "statement": "docs/community.html (October 2026 operator estimate, not an invoice)",
            "config_source": "apps/api/routers/payments.py: SERVER_COST_MONTHLY, DOMAIN_COST_YEARLY",
            "recurring_eur": {"server_monthly": monthly, "domain_yearly": domain,
                              "server_and_domain_yearly": round(monthly * 12 + domain, 2)},
            "other_recurring": "Separate USD annual account charge in the dated community statement; excluded from EUR subtotal; current invoice needs operator confirmation.",
            "usage_dependent": "HLR, translation and archival publication depend on usage, plan and funding; no current annual total is derivable from the repo.",
            "one_time": "Separate USD registration charge in the community statement; excluded from recurring totals.",
            "historical": "Superseded EUR 93.30/year and EUR 200–300/year estimates are recorded in EKA_STATUS_2026-10-23.md (EKA-39); neither is a current cost basis.",
        },
        "definitions": DEFINITIONS,
        "counts": {
            "modules_spec": max(numbers),
            "modules_listed": len(modules),
            "modules_inactive": sum(1 for m in modules if re.search(r"\((deferred|disabled)\)", m)),
            "api_endpoints": endpoints,
            "api_routers": len(routed),
            "db_tables_orm": len(tables),
            "prod_containers": len(services),
        },
        "details": {
            "modules_missing_numbers": [f"MOD-{n:02d}" for n in range(1, max(numbers) + 1) if n not in numbers],
            "prod_services": ["assistant" if name == "ollama" else name for name in services],
        },
    }


def render(facts: dict[str, object]) -> str:
    return json.dumps(facts, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# Qualified public EL/EN count phrases, including the llms snapshot vocabulary.
CLAIM_NOUNS = {
    "modules": r"(?:(?:listed|inactive|disabled|deferred)\s+)?modules?|(?:(?:καταχωρισμένες|ανενεργές)\s+)?ενότητες|ενοτήτων",
    "api_endpoints": r"(?:API\s+)?route\s+decorators?|endpoints?|δηλώσεις\s+διαδρομών(?:\s+API)?",
    "api_routers": r"routers?",
    "db_tables_orm": r"(?:ORM\s+)?tables?|πίνακες(?:\s+ORM)?|πινάκων",
    "prod_containers": r"(?:production\s+)?Compose\s+services|υπηρεσίες\s+(?:production\s+)?Compose|containers?|κοντέινερ",
}
NOUN = "(?:" + "|".join(CLAIM_NOUNS.values()) + ")"
CLAIM_RES = [
    re.compile(r"(?P<num>\d+)(?P<plus>\+?)\s*(?P<noun>" + NOUN + r")\b", re.IGNORECASE),
    re.compile(r"\b(?P<noun>" + NOUN + r")\s*(?:[:=]|\|)\s*(?P<num>\d+)(?P<plus>\+?)", re.IGNORECASE),
]
TAG_RE = re.compile(r"<[^>]+>")
HISTORICAL_RE = re.compile(r"(?:historical|ιστορικ\w*)[^;·.!?\n]*?\b20\d{2}-\d{2}-\d{2}\b", re.IGNORECASE)
INACTIVE_RE = re.compile(r"\b(?:inactive|disabled|deferred|ανενεργές)\b", re.IGNORECASE)
CLAUSE_BOUNDARY_RE = re.compile(r"[;·.!?\n]|\b(?:current(?:ly)?|today|now|τρέχ\w*|σημεριν\w*|σήμερα|τώρα)\b", re.IGNORECASE)


class ClaimTextParser(HTMLParser):
    """Keep translated attributes, metadata and visible prose in separate runs.

    Inline tags may split a number from its noun; block tags end a run. Dates
    in an attribute can never exempt the visible text or another translation.
    """
    BLOCKS = {"p", "div", "li", "tr", "td", "th", "section", "article", "meta",
              "h1", "h2", "h3", "h4", "h5", "h6", "br", "script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.runs = []
        self.parts = []
        self.line = 1

    def flush(self):
        if self.parts:
            self.runs.append((self.line, " ".join(self.parts), True))
            self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS:
            self.flush()
        for key, value in attrs:
            if value:
                self.runs.append((self.getpos()[0], TAG_RE.sub(" ", unescape(value)), key in {"data-el", "data-en"}))

    def handle_endtag(self, tag):
        if tag in self.BLOCKS:
            self.flush()

    def handle_data(self, data):
        for offset, text in enumerate(data.split("\n")):
            line = self.getpos()[0] + offset
            if line != self.line:
                self.flush()
                self.line = line
            self.parts.append(text)


def claim_paths() -> list[Path]:
    paths = sorted(ROOT.glob("docs/**/*.html")) + [ROOT / "docs" / "llms.txt"]
    paths += sorted((ROOT / "docs" / "wiki").glob("*.md")) + sorted((ROOT / "wiki").glob("*.md")) + [ROOT / "README.md"]
    skip = ("planning", "community-audits", "reports", "operations", "agent-bridge")
    return [p for p in paths if p.exists() and not any(part in p.parts for part in skip)]


def claims(facts: dict[str, object], paths: list[Path] | None = None) -> list[tuple[str, int, str, str, str]]:
    """Return differing claims, exempting only a dated claim in its own locale.

    A historical label applies to the next count in the same clause/locale,
    even when that count already agrees with the facts. Subset module counts
    use their own bound (or exact inactive count), never the global total.
    """
    counts = facts["counts"]
    accepted = {**{k: {counts[k]} for k in
                   ("api_endpoints", "db_tables_orm", "prod_containers")},
                "modules": {counts["modules_listed"]},
                "api_routers": {counts["api_routers"]}}
    out: list[tuple[str, int, str, str, str]] = []
    for path in (claim_paths() if paths is None else paths):
        parser = ClaimTextParser()
        parser.feed(path.read_text(encoding="utf-8"))
        parser.flush()
        seen = set()
        for lineno, text, visible in parser.runs:
            matches = sorted((m for p in CLAIM_RES for m in p.finditer(text)), key=lambda m: m.start())
            previous_end = 0
            for m in matches:
                noun, num, plus = m["noun"], m["num"], m["plus"]
                kind = next(k for k, pattern in CLAIM_NOUNS.items() if re.fullmatch(pattern, noun, re.IGNORECASE))
                prefix = text[previous_end:m.start()]
                previous_end = m.end()
                label = HISTORICAL_RE.search(prefix) if visible else None
                historical = label and not CLAUSE_BOUNDARY_RE.search(prefix[label.end():])
                values = accepted[kind]
                if kind == "modules":
                    suffix = text[m.end():]
                    if INACTIVE_RE.search(noun) or re.match(r"\s+(?:disabled|inactive|deferred|ανενεργές)\b", suffix, re.IGNORECASE):
                        values = {counts["modules_inactive"]}
                    elif re.search(r"(?:including|of which|περιλαμβάνονται|από τις οποίες)\s*$", prefix, re.IGNORECASE):
                        values = range(counts["modules_listed"] + 1)
                value = int(num)
                if value in values and not plus:
                    continue
                lower_ok = plus == "+" and value <= max(values)
                cls = "historical" if historical else ("lower-bound" if lower_ok else "mismatch")
                identity = (lineno, kind, value, plus, cls)
                if identity in seen:
                    continue
                seen.add(identity)
                rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                out.append((rel, lineno, kind, " ".join(m.group(0).split()), cls))
    return out


TOKEN_RE = re.compile(r"\{\{([a-z0-9_]+)\}\}")


def consumer_values(facts: dict) -> dict[str, str]:
    costs = facts["cost_basis"]["recurring_eur"]
    return {**{k: str(v) for k, v in facts["counts"].items()},
            "as_of": facts["as_of"], "cost_as_of": facts["cost_basis"]["as_of"],
            "server_monthly": f'{costs["server_monthly"]:g}',
            "server_yearly": f'{costs["server_monthly"] * 12:g}',
            "domain_yearly_en": f'{costs["domain_yearly"]:.2f}',
            "domain_yearly_el": f'{costs["domain_yearly"]:.2f}'.replace(".", ","),
            "recurring_yearly_en": f'{costs["server_and_domain_yearly"]:.2f}',
            "recurring_yearly_el": f'{costs["server_and_domain_yearly"]:.2f}'.replace(".", ",")}


def consumer_errors(facts: dict, *, update: bool = False, root: Path = ROOT,
                    specs: list[dict] | None = None) -> list[str]:
    """Check exact rendered lines, including EL/EN, metadata and separated metric cards.

    The registry contains prose/templates, never an independent copy of a count.
    Missing/duplicated lines fail closed. Updates replace only known numeric slots.
    The broader claims scan also rejects new, unregistered conflicting claims.
    """
    values = consumer_values(facts)
    errors = []
    for spec in json.loads(CONSUMERS.read_text()) if specs is None else specs:
        path = root / spec["path"]
        source = path.read_text(encoding="utf-8")
        template = spec["template"]
        expected = TOKEN_RE.sub(lambda m: values[m[1]], template)
        pattern = "^" + "[^\\n]*?".join(re.escape(s) for s in TOKEN_RE.split(template)[::2]) + "$"
        matches = list(re.finditer(pattern, source, re.MULTILINE))
        if len(matches) != spec.get("occurrences", 1):
            errors.append(f'{spec["path"]}: missing/duplicated consumer: {expected.strip()[:100]}')
        elif any(m[0] != expected for m in matches):
            if update:
                source = re.sub(pattern, lambda _: expected, source, flags=re.MULTILINE)
                path.write_text(source, encoding="utf-8")
            else:
                errors.append(f'{spec["path"]}: consumer drift: {expected.strip()[:100]}')
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--claims", action="store_true")
    mode.add_argument("--check-consumers", action="store_true")
    mode.add_argument("--update-consumers", action="store_true")
    args = parser.parse_args(argv)
    facts = compute()
    if args.write:
        ARTIFACT.write_text(render(facts), encoding="utf-8")
        print(f"wrote {ARTIFACT.relative_to(ROOT)}: {facts['counts']}")
        return 0
    if args.check:
        current = ARTIFACT.read_text(encoding="utf-8") if ARTIFACT.exists() else ""
        if current != render(facts):
            print("project facts drift: run `python3 scripts/project_facts.py --write` and commit the result", file=sys.stderr)
            return 1
        print(f"project facts ok: {facts['counts']}")
        return 0
    if args.check_consumers or args.update_consumers:
        errors = consumer_errors(facts, update=args.update_consumers)
        if args.check_consumers and (not ARTIFACT.exists() or ARTIFACT.read_text() != render(facts)):
            errors.append("project-facts.json is stale; run --write")
        for error in errors:
            print(error, file=sys.stderr)
        if errors:
            return 1
        if args.update_consumers:
            print("updated project fact consumers; run scripts/wiki_publish.py --write next")
            return 0
    found = claims(facts)
    for path, lineno, kind, text, cls in found:
        print(f"{path}:{lineno}: {kind}: {cls}: {text!r}")
    lines = {(p, n) for p, n, *_ in found}
    by = {c: sum(1 for *_, x in found if x == c) for c in ("mismatch", "lower-bound", "historical")}
    print(f"{len(found)} distinct claim(s) on {len(lines)} line(s): " + ", ".join(f"{v} {k}" for k, v in by.items()))
    return int(any(cls != "historical" for *_, cls in found))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
