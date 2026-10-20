#!/usr/bin/env python3
"""Render/check the current docs CSP inventory without changing the frozen R0 inventory."""

import argparse
from collections import Counter
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/security/CSP_INVENTORY.md"
EXCLUDED = {"animation-spec", "community-audits", "planning"}
TEMPLATE_HANDLER = re.compile(r"\bon[a-z]+\s*=\s*['\"]", re.I)
WEB_ROUTERS = ("ekklesia-web",)  # ekklesia-www only redirects to this router.
NEXT_COLUMNS = {
    "inline": "Inline scripts",
    "next": "next/script elements",
    "before": "beforeInteractive",
    "html": "dangerouslySetInnerHTML",
    "handlers": "String handlers",
    "urls": "javascript: URLs",
}


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


def compose_labels(raw):
    """Normalize both Compose label forms; reject ambiguous duplicate keys."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, list):
        raise ValueError("expected active web service labels")
    labels = {}
    for item in raw:
        if not isinstance(item, str) or "=" not in item:
            raise ValueError("expected key=value web label")
        key, value = item.split("=", 1)
        if key in labels:
            raise ValueError(f"duplicate web label: {key}")
        labels[key] = value
    return labels


def validate_policy(compose, hashes=None):
    """Validate default enforcement, single CSP writers and the compatibility no-op."""
    web = yaml.safe_load(compose)["services"]["web"]
    labels = compose_labels(web.get("labels"))
    if str(labels.get("traefik.enable")).lower() != "true":
        raise ValueError("web service must be enabled in Traefik")
    for router in (*WEB_ROUTERS, "ekklesia-static"):
        prefix = f"traefik.http.routers.{router}."
        bindings = {value.strip() for value in labels.get(prefix + "middlewares", "").split(",")}
        if not labels.get(prefix + "rule") or not bindings.intersection({"ekklesia-headers", "ekklesia-headers@docker"}):
            raise ValueError(f"{router} must bind the active ekklesia-headers middleware")
    static = "traefik.http.middlewares.ekklesia-static-csp.headers."
    embed = "traefik.http.middlewares.ekklesia-embed-csp.headers."
    expected = LEGACY_CSP.replace("script-src 'self' 'unsafe-inline'", "script-src 'self'") + "; font-src 'self'; object-src 'none'; base-uri 'self'"
    if any("content-security-policy-report-only" in key.lower() or "contentsecuritypolicyreportonly" in key.lower() for key in labels):
        raise ValueError("Report-Only is forbidden: exactly one enforced CSP header is required")
    if not labels.get(static + "contentSecurityPolicy"):
        raise ValueError("expected active enforced policy label on web")
    if labels[static + "contentSecurityPolicy"] != expected:
        raise ValueError("enforced policy/hash drift: review the compose label and inventory")
    if web.get("environment", {}).get("CSP_ENFORCE") != "${CSP_ENFORCE:-true}":
        raise ValueError("CSP_ENFORCE must default to true with an explicit false rollback")
    def check_writers(active, router, csp_writer=None, frameable=False):
        bindings = [value.strip().split("@")[0] for value in active.get("traefik.http.routers." + router + ".middlewares", "").split(",")]
        writers = []
        for binding in bindings:
            prefix = "traefik.http.middlewares." + binding + ".headers."
            for key in active:
                if key.startswith(prefix) and ("contentsecuritypolicy" in key.lower() or "content-security-policy" in key.lower()):
                    writers.append(binding)
            if frameable and (str(active.get(prefix + "frameDeny", "false")).lower() == "true" or
                              active.get(prefix + "customFrameOptionsValue") or
                              any(key.lower() == (prefix + "customResponseHeaders.X-Frame-Options").lower() for key in active)):
                raise ValueError("embed router must stay frameable")
        if writers != ([csp_writer] if csp_writer else []):
            raise ValueError("general web router must preserve the Next nonce policy; each static router needs one CSP writer")
        if "ekklesia-headers" not in bindings:
            raise ValueError(router + " must bind the active ekklesia-headers middleware")
        return bindings
    check_writers(labels, "ekklesia-web")
    rule = labels["traefik.http.routers.ekklesia-static.rule"]
    if re.search(r"\bPath(?:Prefix)?\([^)]*,", rule):
        raise ValueError("static router must use single-argument Path/PathPrefix matchers")
    if "`/embed/`" in rule:
        raise ValueError("embed router must stay frameable: exclude it from the static router")
    check_writers(labels, "ekklesia-static", "ekklesia-static-csp")
    if int(labels.get("traefik.http.routers.ekklesia-static.priority", 0)) < 100:
        raise ValueError("static router must bind its strict CSP at explicit priority")
    if (labels.get("traefik.http.routers.ekklesia-embed.rule") != "Host(`ekklesia.gr`) && PathPrefix(`/embed/`)" or
            int(labels.get("traefik.http.routers.ekklesia-embed.priority", 0)) <= int(labels["traefik.http.routers.ekklesia-static.priority"])):
        raise ValueError("embed router must stay frameable at a higher priority")
    check_writers(labels, "ekklesia-embed", "ekklesia-embed-csp", frameable=True)
    embed_target = expected.replace("frame-ancestors 'none'", "frame-ancestors *")
    if labels.get(embed + "contentSecurityPolicy") != embed_target:
        raise ValueError("embed router must stay frameable with its strict enforced policy")
    override = yaml.safe_load((ROOT / "infra/docker/docker-compose.csp-enforce.yml").read_text())
    if override != {"services": {}}:
        raise ValueError("CSP compatibility overlay must remain a no-op")
    source = (ROOT / "apps/web/csp.mjs").read_text()
    if json.dumps(LEGACY_CSP) not in source:
        raise ValueError("application/edge CSP drift")


LEGACY_CSP = "default-src 'self' https://api.ekklesia.gr; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://api.qrserver.com https://avatars.githubusercontent.com; connect-src 'self' https://api.ekklesia.gr https://api.coingecko.com https://arweave.net https://api.github.com https://polis-oauth-proxy.bergamolia.workers.dev; frame-ancestors 'none'"


def source_tags(source):
    """Locate source opening tags, keeping quoted '>' and JSX braces together.

    This is a conservative source-site scan, not a JS evaluator. Literal HTML
    strings are included because they can be injected into the DOM at runtime.
    """
    for match in re.finditer(r"<([A-Za-z][\w.:-]*)(?=[\s/>])", source):
        pos = match.end()
        start = pos
        braces = 0
        quote = None
        while pos < len(source):
            char = source[pos]
            if quote:
                if char == "\\":
                    pos += 2
                    continue
                if char == quote:
                    quote = None
            elif char in "\"'`":
                quote = char
            elif char == "{":
                braces += 1
            elif char == "}":
                braces -= 1
            elif char == ">" and braces == 0:
                yield match.start(), match[1], source[start:pos]
                break
            pos += 1


def has_src_attribute(attrs):
    """Match a whole src attribute outside quoted values and JSX expressions."""
    pos = 0
    braces = 0
    quote = None
    while pos < len(attrs):
        char = attrs[pos]
        if quote:
            if char == "\\":
                pos += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char == "{":
            braces += 1
        elif char == "}":
            braces -= 1
        elif braces == 0 and (pos == 0 or attrs[pos - 1].isspace()) and re.match(r"src\s*=", attrs[pos:]):
            return True
        pos += 1
    return False


def next_sites(source):
    # Mask comments but preserve strings (including URLs) and line positions.
    source = re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*[\s\S]*?\*/''',
                    lambda m: re.sub(r"[^\n]", " ", m[0]) if m[0].startswith(("//", "/*")) else m[0], source)
    aliases = set(re.findall(r'''import\s+([A-Za-z_$][\w$]*)\s*(?:,\s*\{[^}]*\}\s*)?from\s+['"]next/script['"]''', source))
    for named in re.findall(r'''import\s*(?:[A-Za-z_$][\w$]*\s*,\s*)?\{([^}]*)\}\s*from\s*['"]next/script['"]''', source):
        aliases.update(re.findall(r"(?:^|,)\s*default\s+as\s+([A-Za-z_$][\w$]*)\s*(?=,|$)", named))
    sites = []
    for pos, tag, attrs in source_tags(source):
        line = source[:pos].count("\n") + 1
        kinds = []
        if tag == "script" or tag in aliases:
            if not has_src_attribute(attrs):
                kinds.append("inline")
            if tag in aliases:
                kinds.append("next")
            if re.search(r'''\bstrategy\s*=\s*\{?\s*['"]beforeInteractive['"]''', attrs):
                kinds.append("before")
        if re.search(r"\bdangerouslySetInnerHTML\s*=", attrs):
            kinds.append("html")
        kinds.extend("handlers" for _ in re.finditer(r'''\bon\w+\s*=\s*(?:['"]|\{\s*['"`])''', attrs))
        kinds.extend("urls" for _ in re.finditer(r'''\b[\w-]+\s*=\s*\{?\s*['"`]\s*javascript\s*:''', attrs, re.I))
        kinds.extend("callbacks" for _ in re.finditer(r"\bon[A-Z]\w*\s*=\s*\{(?!\s*['\"`])", attrs))
        for kind in kinds:
            sites.append((line, kind, tag))
    return sites


def next_inventory():
    paths = [ROOT / "apps/web/next.config.mjs"]
    paths += sorted(path for path in (ROOT / "apps/web/src").rglob("*")
                    if path.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs"}
                    and not re.search(r"\.(test|spec)\.", path.name) and "__tests__" not in path.parts)
    return {path.relative_to(ROOT).as_posix(): next_sites(path.read_text(encoding="utf-8")) for path in paths}


def render():
    pages = {}
    paths = sorted((ROOT / "docs").rglob("*.html"))
    paths += sorted((ROOT / "apps/representative/web").glob("*.html"))
    for path in paths:
        if not EXCLUDED.intersection(path.relative_to(ROOT).parts):
            pages[path.relative_to(ROOT).as_posix()] = Page(path.read_text(encoding="utf-8"))
    validate_policy((ROOT / "infra/docker/docker-compose.prod.yml").read_text())
    totals = Counter()
    for path, page in pages.items():
        totals.update(js=sum(s["type"] != "application/ld+json" and bool(s["body"].strip()) for s in page.scripts),
                      data=sum(s["type"] == "application/ld+json" for s in page.scripts),
                      empty=sum(not s["body"].strip() for s in page.scripts),
                      handlers=len(page.handlers), urls=len(page.urls), embedded=len(page.embedded_handlers))
        for script in page.scripts:
            if script["type"] == "application/ld+json":
                json.loads(script["body"])  # Keep structured data valid, inert and unchanged.
    external_generated = {}
    assets = {}
    for path in sorted((ROOT / "docs").rglob("*.js")):
        relative = path.relative_to(ROOT).as_posix()
        sites = template_sites(path.read_text(encoding="utf-8"))
        if sites:
            external_generated[relative] = sites
        if path.is_relative_to(ROOT / "docs/assets/js"):
            assets[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if totals["js"] or totals["empty"] or totals["handlers"] or totals["urls"] or totals["embedded"] or external_generated:
        raise ValueError("executable inline scripts/handlers are forbidden on public pages")
    # Reject dangling script URLs (including changes to relative paths on nested pages).
    class Sources(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "script" and attrs.get("src", "").startswith(("https:", "http:")):
                raise ValueError("public scripts must be same-origin")
            if tag == "script" and "src" in attrs:
                src = attrs["src"]
                target = ROOT / "docs" / src.lstrip("/") if src.startswith("/") else self.path.parent / src
                # Representative assets resolve against its deployed /representative/ URL.
                if self.path.is_relative_to(ROOT / "apps/representative/web"):
                    target = ROOT / "docs/representative" / src
                if not target.resolve().is_file():
                    raise ValueError(f"missing public script: {self.path}: {src}")
    for relative in pages:
        parser = Sources()
        parser.path = ROOT / relative
        parser.feed(parser.path.read_text())
    lines = ["# CSP inventory — T-9156 / EVA-023 enforcement", "",
             "Snapshot: 2026-10-20. Regenerate with `python3 scripts/csp-inventory.py`; verify with `--check`.", "",
             f"The {sum(path.startswith('docs/') for path in pages)} live docs pages and representative web page contain **{totals['js']} executable inline blocks**, **{totals['data']} JSON-LD blocks**, **{totals['empty']} empty blocks**, **{totals['handlers']} literal event-handler attributes**, **0 generated handlers**, and **{totals['urls']} javascript: URLs**.", "",
             "Historical planning/community audit reports and animation-spec snippets are excluded. The frozen R0 inventory is unchanged. All production public HTML from docs and the separately copied representative app is checked. JSON-LD stays inline: application/ld+json is a non-executable data block, valid JSON, and needs neither a nonce nor a script hash. Observation run 2 reported no JSON-LD violations in Chromium/WebKit; the added offline browser regression is available for a browser-enabled environment (local launch is sandbox-blocked).", "",
             "## Enforced policy and rollback", "",
             "Production enforces the strict policy by default. Static HTML receives exactly one Content-Security-Policy with script-src 'self', font-src 'self', object-src 'none', base-uri 'self' and frame-ancestors 'none'. Other directives remain unchanged, including style-src 'unsafe-inline'. No script unsafe-inline, unsafe-eval, unsafe-hashes, strict-dynamic, build-dependent hash, or fixed nonce is added. No Content-Security-Policy-Report-Only header is emitted.", "",
             "The priority-100 ekklesia-static router covers /, top-level docs HTML and the wiki/tickets/votes/municipality/demo/representative directories, using ekklesia-static-csp. The priority-110 embed router uses ekklesia-embed-csp with frame-ancestors * and no frame-deny header. The general web router has no edge CSP writer; Next supplies a response-specific enforced nonce policy. Each response has exactly one CSP header. The gate checks router bindings, strict policies, duplicate writers, default enforcement, the compatibility no-op and app/edge legacy policy parity.", "",
             "Strict static/embed enforcement is folded into docker-compose.prod.yml. docker-compose.csp-enforce.yml remains a compatibility no-op for existing deployment commands. Next enforces by default when CSP_ENFORCE is unset or true. Explicit CSP_ENFORCE=false restores the legacy enforced Next response policy through next.config while preserving nonce rendering; it emits no Report-Only header. This app rollback does not relax the edge static/embed policies. See CSP_OBSERVATION.md for deployment and edge rollback details. Static hosting outside Traefik needs equivalent HTTP headers.", "",
             "## What moved", "",
             "All executable blocks now load deferred classic scripts in dependency order at their original document positions under docs/assets/js/. Twelve wiki legal-modal bodies share wiki-legal.js; eight wiki language bodies share wiki-language.js. Page-specific language/modal/nav logic retains its globals, with null guards. Language defaults and landing textContent match local origin/main; those old toggles never persisted language. events.js contains a closed allowlist of listener functions for data-csp-* controls; delegated listeners support generated cards, translated markup, nearest matching ancestor dispatch, return-false cancellation and vote stopPropagation. Parameters in generated controls use data-number/data-bill/data-choice/data-value, never evaluated strings. The prior mirror and OAuth callback assets moved here too; callback keeps no-referrer first in head and config-before-callback ordering. SSO verification script requests use no-referrer so the nonce query cannot leak into asset referrers. The minified QR vendor body is unchanged. Municipality Google Fonts links were removed: their existing serif/sans-serif fallbacks already render under the enforced policy, and no external font origins are authorized.", "",
             "scripts/csp-migration.json records each source page, externalized assets and original body digests for review. The table below pins current assets, including the few template bodies changed to remove generated handlers. The new-ticket auth guard now runs in the same listener path before opening the modal; it no longer wraps a removed onclick property. Redesign approvals pin the new HTML/inventory bytes without changing frozen R0 data. Sitemap source hashes and lastmod dates reflect this migration; SEO content and JSON-LD stay unchanged.", "",
             "## Counts by file", "", "| File | Executable blocks | JSON-LD | Empty | Literal handlers | Generated handler sites | javascript: URLs |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for path, page in pages.items():
        data = sum(s["type"] == "application/ld+json" for s in page.scripts)
        lines.append(f"| `{path}` | 0 | {data} | 0 | 0 | 0 | 0 |")
    lines += ["", "## Every remaining block and handler", "", "Only inert JSON-LD remains. No executable inline items, empty placeholders, string handlers or generated handler sites remain.", "", "| File:line | Category | Reason |", "| --- | --- | --- |"]
    for path, page in pages.items():
        for script in page.scripts:
            lines.append(f"| `{path}:{script['line']}` | JSON-LD data | Retain inline for SEO; inert under script-src. |")
    lines += ["", "## External script digests", "", "| Asset | SHA-256 (hex) |", "| --- | --- |"]
    for path, digest in assets.items():
        lines.append(f"| `{path}` | `{digest}` |")
    next_files = next_inventory()
    next_totals = Counter(kind for sites in next_files.values() for _, kind, _ in sites)
    lines += ["", "## Next.js nonce and rendering", "",
              f"Source scan of {len(next_files)} production files: " + ", ".join(f"**{next_totals[kind]} {label}**" for kind, label in NEXT_COLUMNS.items()) + ".", "",
              "Next 16 uses src/proxy.ts. A fresh 256-bit Web Crypto nonce replaces untrusted request nonce/CSP values. The request Content-Security-Policy and x-nonce reach Next through next-intl's request-header overrides. Next automatically nonces bootstrap, Flight and streaming scripts from that request policy (verified against the locally installed Next renderer). No authored Script/inline script components exist. Future authored Script components must read x-nonce with await headers() and pass nonce explicitly.", "",
              "The locale layout is force-dynamic, including formerly static client pages: nonce-bearing HTML cannot use prerender/ISR document caching. Existing SSR data fetches already use no-store; static docs stay fully static and need no nonce. Responses are private/no-store. PWA start-URL and navigation caching is disabled; public HTML is excluded from precache, and runtime same-origin caching is restricted to script/style/image/font destinations. A new worker must replace old document caches during rollout. No strict-dynamic exception is needed.", "",
              "## Evidence and regression checks", "",
              "T-9156 starts from production strict enforcement with zero observed violations, as reported by the owner. This change removes the redundant target Report-Only policy and makes the existing enforcement the default; no deployment or new production observation is performed here. The observer now requires an enforced header and absence of Report-Only. There is no report receiver; violations are captured locally. See CSP_OBSERVATION.md for coverage limitations and targeted offline regression commands. Verify exactly one CSP header and matching fresh HTML/Flight nonces after deployment.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the inventory needs regeneration")
    args = parser.parse_args(argv)
    try:
        content = render()
    except (ValueError, yaml.YAMLError) as error:
        raise SystemExit(str(error)) from error
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit("CSP inventory drift: run python3 scripts/csp-inventory.py")
        print("CSP inventory: current")
    else:
        OUTPUT.write_text(content, encoding="utf-8")
        print("wrote docs/security/CSP_INVENTORY.md")


if __name__ == "__main__":
    main()
