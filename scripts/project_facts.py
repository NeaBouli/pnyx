#!/usr/bin/env python3
"""EKA-40: generated project facts (module/endpoint/table/container counts).

Counts are derived from source, so every published number can cite one dated artifact:

    python3 scripts/project_facts.py --write    regenerate docs/project-facts.json
    python3 scripts/project_facts.py --check    fail if the committed artifact is stale (CI)
    python3 scripts/project_facts.py --claims   report published count claims that disagree (heuristic, see claims())

Standard library only. Definitions are fixed in ``DEFINITIONS`` so pages can quote them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "docs" / "project-facts.json"
MAIN = ROOT / "apps" / "api" / "main.py"
ROUTERS = ROOT / "apps" / "api" / "routers"
MODELS = ROOT / "apps" / "api" / "models.py"
COMPOSE_PROD = ROOT / "infra" / "docker" / "docker-compose.prod.yml"

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
    return {
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
            "prod_services": services,
        },
    }


def render(facts: dict[str, object]) -> str:
    return json.dumps(facts, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# Published count claims in EL/EN, either "<n> <noun>" or "<noun>: <n>". HTML tags are
# stripped first so "<strong>22</strong> Modules" is seen as "22 Modules".
NOUN = (r"(modules?|module|ενότητες|ενοτήτων|endpoints?|tables?|πίνακες|πινάκων|"
        r"containers?|κοντέινερ)")
CLAIM_RES = [
    re.compile(r"(\d+)(\+?)\s*" + NOUN, re.IGNORECASE),
    re.compile(NOUN + r"\s*[:=]\s*(\d+)(\+?)", re.IGNORECASE),
]
CLAIM_KIND = {
    "module": "modules", "modules": "modules", "ενότητες": "modules", "ενοτήτων": "modules",
    "endpoint": "api_endpoints", "endpoints": "api_endpoints",
    "table": "db_tables_orm", "tables": "db_tables_orm", "πίνακες": "db_tables_orm", "πινάκων": "db_tables_orm",
    "container": "prod_containers", "containers": "prod_containers", "κοντέινερ": "prod_containers",
}
TAG_RE = re.compile(r"<[^>]+>")
# Pages that quote dated audit figures; reported, but not counted as current claims.
HISTORICAL = {"docs/wiki/audit.html"}


def claim_paths() -> list[Path]:
    paths = sorted(ROOT.glob("docs/**/*.html")) + [ROOT / "docs" / "llms.txt"]
    paths += sorted((ROOT / "docs" / "wiki").glob("*.md")) + sorted((ROOT / "wiki").glob("*.md")) + [ROOT / "README.md"]
    skip = ("planning", "community-audits", "reports", "operations", "agent-bridge")
    return [p for p in paths if p.exists() and not any(part in p.parts for part in skip)]


def claims(facts: dict[str, object]) -> list[tuple[str, int, str, str, str]]:
    """Return (path, line, kind, text, class) for published counts that differ from the facts.

    class: "mismatch" (exact number that differs), "lower-bound" (e.g. "70+", true but
    imprecise when the fact is larger) or "historical" (dated audit quotes). One entry per
    distinct claim per line. Heuristic: claims phrased without one of the listed nouns
    (e.g. "32 routers", prose such as "two dozen tables") are not detected.
    """
    counts = facts["counts"]
    accepted = {
        "modules": {counts["modules_spec"], counts["modules_listed"]},
        "api_endpoints": {counts["api_endpoints"]},
        "db_tables_orm": {counts["db_tables_orm"]},
        "prod_containers": {counts["prod_containers"]},
    }
    out: list[tuple[str, int, str, str, str]] = []
    for path in claim_paths():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            seen: set[tuple[str, int, str]] = set()
            # Raw line catches attribute text (meta content, data-el/data-en); the
            # tag-stripped line catches numbers split from their noun by markup.
            for pattern, text in ((p, t) for t in (line, TAG_RE.sub(" ", line)) for p in CLAIM_RES):
                for m in pattern.finditer(text):
                    groups = m.groups()
                    num, plus, noun = (groups[0], groups[1], groups[2]) if groups[0].isdigit() else (groups[1], groups[2], groups[0])
                    kind = CLAIM_KIND.get(noun.lower())
                    value = int(num)
                    if not kind or value in accepted[kind] or (kind, value, plus) in seen:
                        continue
                    seen.add((kind, value, plus))
                    lower_ok = plus == "+" and value <= max(accepted[kind])
                    rel = str(path.relative_to(ROOT))
                    cls = "historical" if rel in HISTORICAL else ("lower-bound" if lower_ok else "mismatch")
                    out.append((rel, lineno, kind, " ".join(m.group(0).split()), cls))
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--claims", action="store_true")
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
    found = claims(facts)
    for path, lineno, kind, text, cls in found:
        print(f"{path}:{lineno}: {kind}: {cls}: {text!r}")
    lines = {(p, n) for p, n, *_ in found}
    by = {c: sum(1 for *_, x in found if x == c) for c in ("mismatch", "lower-bound", "historical")}
    print(f"{len(found)} distinct claim(s) on {len(lines)} line(s): " + ", ".join(f"{v} {k}" for k, v in by.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
