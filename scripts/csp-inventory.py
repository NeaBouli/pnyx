#!/usr/bin/env python3
"""Render/check the current docs CSP inventory without changing the frozen R0 inventory."""

import argparse
import base64
from collections import Counter, defaultdict
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/security/CSP_INVENTORY.md"
EXCLUDED = {"animation-spec", "community-audits", "planning"}
HASHED = {"docs/legal.html", "docs/municipality/article.html"}
TEMPLATE_HANDLER = re.compile(r"\bon[a-z]+\s*=\s*['\"]", re.I)


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.handlers = []
        self.urls = []
        self.embedded_handlers = []
        self.current = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        for name, value in attrs:
            if re.fullmatch(r"on\w+", name):
                self.handlers.append((line, name, value or ""))
            if value and re.match(r"\s*javascript\s*:", value, re.I):
                self.urls.append((line, name, value))
            # HTML in language/data attributes is parsed again by innerHTML.
            if value and "<" in value and TEMPLATE_HANDLER.search(value):
                self.embedded_handlers.append((line, name, value))
        if tag == "script" and "src" not in dict(attrs):
            self.current = {"line": line, "type": dict(attrs).get("type", ""), "body": ""}
            self.scripts.append(self.current)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, value):
        if self.current is not None:
            self.current["body"] += value

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = None


def code(value):
    return "<code>" + value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;") + "</code>"


def template_sites(body, start_line=1):
    return [(start_line + body[:m.start()].count("\n"), body[m.start():].splitlines()[0][:180])
            for m in TEMPLATE_HANDLER.finditer(body)]


def render():
    pages = {}
    for path in sorted((ROOT / "docs").rglob("*.html")):
        if not EXCLUDED.intersection(path.relative_to(ROOT / "docs").parts):
            pages[path.relative_to(ROOT).as_posix()] = Page(path.read_text(encoding="utf-8"))
    hashes = {}
    for path in sorted(HASHED):
        scripts = [s for s in pages[path].scripts if s["type"] != "application/ld+json"]
        assert len(scripts) == 1, f"review hashed scripts in {path}"
        hashes[path] = "sha256-" + base64.b64encode(hashlib.sha256(scripts[0]["body"].encode("utf-8")).digest()).decode("ascii")
    compose = (ROOT / "infra/docker/docker-compose.prod.yml").read_text(encoding="utf-8")
    enforced = re.findall(r'ekklesia-headers\.headers\.contentSecurityPolicy=([^\n]+)"', compose)
    report_only = re.findall(r'ekklesia-headers\.headers\.customResponseHeaders\.Content-Security-Policy-Report-Only=([^\n]+)"', compose)
    assert len(enforced) == len(report_only) == 1, "expected exactly one enforced and one Report-Only policy"
    expected = enforced[0].replace("script-src 'self' 'unsafe-inline'", "script-src 'self' " + " ".join("'" + h + "'" for h in hashes.values()))
    expected += "; object-src 'none'; base-uri 'self'"
    assert report_only[0] == expected, "Report-Only policy/hash drift: review the compose label and inventory"
    totals = Counter()
    generated = {}
    for path, page in pages.items():
        generated[path] = [site for script in page.scripts for site in template_sites(script["body"], script["line"])]
        totals.update(js=sum(s["type"] != "application/ld+json" and bool(s["body"].strip()) for s in page.scripts),
                      data=sum(s["type"] == "application/ld+json" for s in page.scripts),
                      empty=sum(not s["body"].strip() for s in page.scripts),
                      handlers=len(page.handlers), urls=len(page.urls), generated=len(generated[path]))
    external_generated = {}
    for path in sorted((ROOT / "docs").rglob("*.js")):
        sites = template_sites(path.read_text(encoding="utf-8"))
        if sites:
            external_generated[path.relative_to(ROOT).as_posix()] = sites
    lines = ["# CSP inventory — T-9138 / EVA-023", "", "Snapshot: 2026-10-17. Regenerate with `python3 scripts/csp-inventory.py`; verify with `--check`.", "",
             f"The {len(pages)} live `docs/**/*.html` pages contain **{totals['js']} executable inline blocks**, **{totals['data']} JSON-LD blocks**, **{totals['empty']} empty block**, **{totals['handlers']} literal event-handler attributes**, and **{totals['urls']} javascript: URLs** after this change. "
             f"There are also **{totals['generated']} handler template sites** inside HTML script blocks and **{sum(map(len, external_generated.values()))}** in external docs JavaScript; runtime instances depend on data.", "",
             "Scope includes redirects, embeds, demos, and the live `wiki/audit.html` disclosure. Historical planning/community audit reports and `animation-spec/LANDING_SNIPPETS.html` (a design snippet, zero inline scripts/handlers) are excluded. The frozen `docs/planning/r0` inventory is unchanged. "
             "Production copies only the docs paths listed in `apps/web/Dockerfile.prod`; demos, mirror-setup and the legacy static sso-verify page are also inventoried because they are live docs pages on the static host.", "",
             "## Policy and migration strategy", "",
             "The existing enforced CSP remains byte-identical in `infra/docker/docker-compose.prod.yml`. The same Traefik `ekklesia-headers` middleware adds `Content-Security-Policy-Report-Only` using `customResponseHeaders` (the existing compose mechanism also used for API response headers). It applies to the shared production origin, including static HTML paths that bypass the Next proxy matcher. Static hosting outside this Traefik deployment requires its own HTTP header configuration; an HTML meta tag cannot deliver Report-Only.", "",
             "The target changes `script-src 'self' 'unsafe-inline'` to `script-src 'self'` plus the two real SHA-256 sources below, and adds `object-src 'none'; base-uri 'self'`. `frame-ancestors 'none'` and all other existing directives are retained, including `style-src 'self' 'unsafe-inline'`. There is no `unsafe-hashes`, `unsafe-eval`, fixed nonce, or `strict-dynamic` escape hatch. The script hashes allow whole script blocks, never event attributes.", "",
             "| Allowed inline script | SHA-256 source (exact UTF-8 body, including whitespace) |",
             "| --- | --- |",
             f"| `docs/legal.html:{pages['docs/legal.html'].scripts[-1]['line']}` — language toggle | `'{hashes['docs/legal.html']}'` |",
             f"| `docs/municipality/article.html:{pages['docs/municipality/article.html'].scripts[-1]['line']}` — scroll reveals | `'{hashes['docs/municipality/article.html']}'` |", "",
             "No CSP report receiver, `report-uri`, `report-to`, or Reporting-Endpoints configuration exists in the inspected API/web/infra sources. No receiver or third party is added: violations are browser-console-only. Remaining inline scripts and handlers, including Next bootstrap, intentionally produce Report-Only violations; their execution still follows the unchanged enforced policy.", "",
             "**Externalize** means move the exact body into a same-origin classic script at the same document position and preserve dependencies, then replace inline attributes/generated attributes with `addEventListener` (or CSS for hover decoration). A nonce or script hash does not authorize an `onclick` attribute. **Hash** means retain stable inline bytes and update the allowlist when they change. JSON-LD is inert structured data, listed separately from executable code: preserve it inline for SEO; hash it if the supported browser/consumer requires CSP authorization. **Nonce** is reserved for response-specific Next bootstrap/Flight scripts, not static files.", "",
             "This change moves `docs/mirror-setup.html`'s 292-character language toggle to `docs/assets/csp/mirror-setup.js` and the 2,264-character OAuth callback from `docs/tickets/auth/callback.html` to adjacent `callback.js`. Bodies are byte-identical, with no defer/module/async change; callback remains after `../config.js`. Mirror's existing inline click handler remains callable through its global `toggleLang`. Both asset locations are copied by the existing Dockerfile rules where their HTML is served. Only the two exact HTML hashes in `approved_analytics_delta.py` change; no frozen baseline or wiki/audit approvals change. These pages are absent from sitemap sources, so `node scripts/public-seo.mjs --update` correctly requires no sitemap/hash change.", "",
             "## Counts by file", "", "| File | Executable blocks | JSON-LD | Empty | Literal handlers | Generated handler sites | javascript: URLs |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for path, page in pages.items():
        counts = [sum(s["type"] != "application/ld+json" and bool(s["body"].strip()) for s in page.scripts),
                  sum(s["type"] == "application/ld+json" for s in page.scripts), sum(not s["body"].strip() for s in page.scripts),
                  len(page.handlers), len(generated[path]), len(page.urls)]
        lines.append("| `" + path + "` | " + " | ".join(map(str, counts)) + " |")
    lines += ["", "## Every remaining block and handler", "", "Locations refer to this tree. Identical handler bodies are grouped with every source line listed; counts are attribute occurrences, not distinct code strings. Template rows count creation sites, not runtime elements."]
    for path, page in pages.items():
        lines += ["", "### `" + path + "`", "", "| Location(s) | Category / item | Plan |", "| --- | --- | --- |"]
        for script in page.scripts:
            body = script["body"]
            if not body.strip():
                category, plan = "Empty script block", "Externalize: remove the empty placeholder with the surrounding script migration."
            elif script["type"] == "application/ld+json":
                category, plan = "JSON-LD data", "Hash if CSP authorization is needed; retain inline for SEO."
            else:
                label = next((s.strip() for s in body.splitlines() if s.strip()), "")[:95]
                category = "Executable: " + code(label)
                plan = "Hash: exact digest already in Report-Only." if path in HASHED else "Externalize; preserve globals and execution order."
            lines.append(f"| {script['line']} | {category} | {plan} |")
        groups = defaultdict(list)
        for line, name, value in page.handlers:
            groups[(name, value)].append(line)
        for (name, value), locations in groups.items():
            lines.append(f"| {', '.join(map(str, locations))} | {code(name + '=' + value)} | Externalize to listeners" + (" / CSS hover rules." if name.startswith("onmouse") else ".") + " |")
        for line, value in generated[path]:
            lines.append(f"| {line} | Generated handler: {code(value)} | Externalize to listeners after element creation / delegation. |")
        for line, name, value in page.embedded_handlers:
            lines.append(f"| {line} | Handler in {code(name)} HTML: {code(value)} | Externalize to listeners after translation rendering. |")
        for line, name, value in page.urls:
            lines.append(f"| {line} | {code(name + '=' + value)} | Externalize to listener with a real link/button. |")
        if not (page.scripts or page.handlers or page.urls):
            lines.append("| — | None | No inline migration needed. |")
    lines += ["", "## Generated handlers in external docs scripts", "", "Externalizing a script alone does not remove the handlers it creates. These sites are loaded by `docs/tickets/index.html`.", "", "| File:line | Item | Plan |", "| --- | --- | --- |"]
    for path, sites in external_generated.items():
        for line, value in sites:
            lines.append(f"| `{path}:{line}` | {code(value)} | Externalize to listeners / delegated events. |")
    lines += ["", "## Next.js app inventory and nonce prerequisite", "",
              "No authored inline `<script>`, `next/script`, string event-handler attribute, or `javascript:` URL occurs in production `apps/web/src`. React `onClick`/`onChange` callbacks are bundled functions registered by React, so they do not require `unsafe-inline`. Function-valued DOM `.onclick` assignments in docs scripts likewise do not constitute inline string handlers. The only authored `dangerouslySetInnerHTML` is a **style** in `src/app/[locale]/sso-verify/page.tsx:222`, outside this script hardening step.", "",
              "| File / generated item | Inline script / string handler / javascript: counts | Plan |", "| --- | --- | --- |",
              "| `apps/web/next.config.mjs` | 0 / 0 / 0 authored | No CSP here; Referrer/Permissions headers only. PWA auto-registration is enabled; inspect its built output for additional inline script and nonce compatibility. |",
              "| `apps/web/src/proxy.ts` (Next 16 middleware entry) | 0 / 0 / 0 authored | Nonce: create a fresh cryptographically random nonce per HTML response; pass the matching CSP and nonce through request headers to the Next renderer and attach that policy to the response. Preserve next-intl and all rewrite/redirect behavior. |",
              "| `apps/web/src/app/[locale]/layout.tsx` (only layout) | 0 / 0 / 0 authored | Nonce: ensure Next framework/bootstrap and any future authored script receive that request's nonce. Evaluate dynamic rendering, prefetches, streaming, error routes and caching. |",
              "| Other production `apps/web/src` files | 0 / 0 / 0 authored | Keep event callbacks in the bundle. See React callback counts below. |",
              "| Next-emitted bootstrap / hydration / Flight (`self.__next_f.push(...)`, etc.) | Response-dependent; unmeasured without a production build/render | Nonce for each response, not static hashes: contents vary with route, build and payload. No nonce is installed in this PR, so violations are expected. |", "",
              "Current nonce plumbing is absent. A static Traefik label cannot create a per-request nonce or stamp it on Next scripts. Before enforcement, retain the static-docs policy at the edge and route dynamic HTML through a matching nonce-aware application policy; avoid a second static strict enforced policy that would still block Next even if its application policy allows the nonce. Never reuse a constant nonce, echo a client-supplied nonce, or cache nonce-bearing HTML independently of its header. Current PWA `StaleWhileRevalidate` document caching also needs review before serving per-response nonces. No Next code is changed in this PR; an offline production render was unavailable because this worktree has no installed web dependencies.", "",
              "React callback occurrences (source JSX; all emit zero string handler attributes):", "", "| File | Callback props |", "| --- | ---: |"]
    for path in sorted((ROOT / "apps/web/src").rglob("*.tsx")):
        if ".test." in path.name:
            continue
        callbacks = re.findall(r"\bon[A-Z]\w*\s*=\s*\{", path.read_text(encoding="utf-8"))
        if callbacks:
            lines.append(f"| `{path.relative_to(ROOT).as_posix()}` | {len(callbacks)} |")
    lines += ["", "## Work remaining before enforcement", "",
              "1. Externalize the remaining executable blocks and all literal/generated handlers listed above, including language controls, FAQ/roadmap toggles, modals, newsletter/chat, demos, embeds and ticket rendering. Keep inert JSON-LD and approved stable hashes synchronized.",
              "2. Implement and verify the Next nonce path, rendering/cache/PWA behavior, and edge/application policy composition; exercise all locale routes, errors, hydration, navigation and offline/service-worker updates with the unchanged enforced policy plus the nonce-aware Report-Only candidate.",
              "3. Inspect console violations on deployed static and dynamic routes, including templates populated from API data and translated DOM, and verify both HTTP headers at the edge. The current local checks validate configuration, not a deployed Traefik response.",
              "4. Review other HTML served on this origin (notably `apps/representative/web`, copied separately by the Dockerfile) before changing a shared enforced header. Confirm existing `frame-ancestors 'none'` remains intentional for embeds. Remove script `unsafe-inline` from enforcement only in a later reviewed rollout after violations are resolved.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the inventory needs regeneration")
    args = parser.parse_args()
    content = render()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit("CSP inventory drift: run python3 scripts/csp-inventory.py")
        print("CSP inventory: current")
    else:
        OUTPUT.write_text(content, encoding="utf-8")
        print("wrote docs/security/CSP_INVENTORY.md")
