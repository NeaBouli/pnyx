"""CSP gate regressions; mutations stay in temporary fixture trees."""

from collections import Counter
from contextlib import redirect_stdout
from html.parser import HTMLParser
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("csp_inventory", ROOT / "scripts/csp-inventory.py")
csp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csp)
COMPOSE = "infra/docker/docker-compose.prod.yml"
LAYOUT = "apps/web/src/app/[locale]/layout.tsx"
REPORT = "customResponseHeaders.Content-Security-Policy-Report-Only:"
BINDING = 'traefik.http.routers.ekklesia-web.middlewares: "ekklesia-headers,ekklesia-no-frame"'


class InventoryGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in (COMPOSE, LAYOUT, "apps/web/next.config.mjs", "infra/docker/docker-compose.csp-enforce.yml", "apps/web/csp.mjs"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        self.output = self.root / "docs/security/CSP_INVENTORY.md"
        self.output.parent.mkdir(parents=True)
        patches = patch.multiple(csp, ROOT=self.root, OUTPUT=self.output)
        patches.start()
        self.addCleanup(patches.stop)
        self.original = csp.render()
        self.output.write_text(self.original, encoding="utf-8")

    def mutate_compose(self, transform):
        path = self.root / COMPOSE
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")

    def test_current_inventory_passes_check(self):
        with redirect_stdout(io.StringIO()):
            csp.main(["--check"])

    def test_commented_report_only_label_fails_check(self):
        self.mutate_compose(lambda text: "\n".join(
            "      # " + line.strip() if REPORT in line else line for line in text.split("\n")))
        with self.assertRaisesRegex(SystemExit, "active enforced and Report-Only"):
            csp.main(["--check"])

    def test_removed_router_binding_fails_check(self):
        self.mutate_compose(lambda text: text.replace("      " + BINDING + "\n", ""))
        with self.assertRaisesRegex(SystemExit, "ekklesia-web must bind"):
            csp.main(["--check"])

    def test_commented_router_binding_fails_check(self):
        self.mutate_compose(lambda text: text.replace(BINDING, "# " + BINDING))
        with self.assertRaisesRegex(SystemExit, "ekklesia-web must bind"):
            csp.main(["--check"])

    def test_binding_on_other_router_fails_check(self):
        self.mutate_compose(lambda text: text.replace(BINDING, BINDING.replace("ekklesia-web.", "unused-web.")))
        with self.assertRaisesRegex(SystemExit, "ekklesia-web must bind"):
            csp.main(["--check"])

    def test_disabled_web_service_fails_check(self):
        self.mutate_compose(lambda text: text.replace('traefik.enable: "true"', 'traefik.enable: "false"'))
        with self.assertRaisesRegex(SystemExit, "enabled in Traefik"):
            csp.main(["--check"])

    def test_policy_hash_drift_fails_check(self):
        self.mutate_compose(lambda text: text.replace("object-src 'none'", "object-src *"))
        with self.assertRaisesRegex(SystemExit, "policy/hash drift"):
            csp.main(["--check"])

    def test_fixed_static_target_cannot_bind_the_dynamic_router(self):
        self.mutate_compose(lambda source: source.replace(BINDING, BINDING.replace('ekklesia-no-frame', 'ekklesia-no-frame,ekklesia-static-csp')))
        with self.assertRaisesRegex(SystemExit, "general web router must preserve"):
            csp.main(["--check"])

    def test_traefik_v3_matcher_arguments_are_single_paths(self):
        self.mutate_compose(lambda source: source.replace("PathPrefix(`/wiki/`)", "PathPrefix(`/wiki/`, `/tickets/`)"))
        with self.assertRaisesRegex(SystemExit, "single-argument"):
            csp.main(["--check"])

    def test_mapping_labels_and_explicit_docker_binding_pass(self):
        def transform(text):
            compose = yaml.safe_load(text)
            labels = csp.compose_labels(compose["services"]["web"]["labels"])
            labels["traefik.http.routers.ekklesia-web.middlewares"] = "other, ekklesia-headers@docker"
            compose["services"]["web"]["labels"] = labels
            return yaml.safe_dump(compose)
        self.mutate_compose(transform)
        with redirect_stdout(io.StringIO()):
            csp.main(["--check"])

    def test_reintroduced_static_inline_code_and_handlers_are_forbidden(self):
        path = self.root / "docs/example.html"
        for source in ('<script>run()</script>', '<button onclick="run()">Run</button>',
                       '<a href="javascript:run()">Run</a>'):
            with self.subTest(source=source):
                path.write_text(source)
                with self.assertRaisesRegex(SystemExit, "executable inline scripts/handlers are forbidden"):
                    csp.main(["--check"])

    def test_external_script_drift_and_missing_source_fail_closed(self):
        path = self.root / "docs/example.html"
        path.write_text('<script src="assets/js/example.js"></script>')
        with self.assertRaisesRegex(SystemExit, "missing public script"):
            csp.main(["--check"])
        script = self.root / "docs/assets/js/example.js"
        script.parent.mkdir(parents=True)
        script.write_text('window.example = 1;')
        self.output.write_text(csp.render())
        script.write_text('window.example = 2;')
        with self.assertRaisesRegex(SystemExit, "CSP inventory drift"):
            csp.main(["--check"])
        script.write_text('var template = \'<button onclick="run()">Run</button>\';')
        with self.assertRaisesRegex(SystemExit, "executable inline scripts/handlers are forbidden"):
            csp.main(["--check"])

    def test_json_ld_is_retained_as_valid_inert_data(self):
        (self.root / "docs/example.html").write_text('<script type="application/ld+json">{"@type":"Thing"}</script>')
        self.assertIn("**1 JSON-LD blocks**", csp.render())

    def test_promotion_cannot_leave_shared_static_policy_on_next(self):
        path = self.root / "infra/docker/docker-compose.csp-enforce.yml"
        source = path.read_text().replace('    labels:', "    labels:\n      traefik.http.middlewares.ekklesia-headers.headers.contentSecurityPolicy: broken")
        path.write_text(source)
        with self.assertRaisesRegex(SystemExit, "promotion must preserve the dynamic nonce"):
            csp.main(["--check"])

    def test_embed_cannot_inherit_frame_deny(self):
        self.mutate_compose(lambda text: text.replace('middlewares: "ekklesia-headers,ekklesia-embed-csp"', 'middlewares: "ekklesia-headers,ekklesia-no-frame,ekklesia-embed-csp"'))
        with self.assertRaisesRegex(SystemExit, "embed router must stay frameable"):
            csp.main(["--check"])

    def test_embed_legacy_and_target_must_both_allow_framing(self):
        self.mutate_compose(lambda text: text.replace('frame-ancestors *', "frame-ancestors 'none'", 1))
        with self.assertRaisesRegex(SystemExit, "embed router must stay frameable"):
            csp.main(["--check"])

    def test_inline_script_changes_inventory_and_fails_check(self):
        path = self.root / LAYOUT
        source = path.read_text(encoding="utf-8")
        path.write_text(source.replace("</head>", "<script>{`window.added = true;`}</script></head>"), encoding="utf-8")
        self.assertNotEqual(self.original, csp.render())
        self.assertIn("**1 Inline scripts**", csp.render())
        with self.assertRaisesRegex(SystemExit, "CSP inventory drift"):
            csp.main(["--check"])

    def test_script_variants_change_inventory_and_fail_check(self):
        path = self.root / LAYOUT
        source = path.read_text(encoding="utf-8")
        for addition in (
            '<script dangerouslySetInnerHTML={{ __html: "window.added = true" }} />',
            '<div dangerouslySetInnerHTML={{ __html: html }} />',
            '<script type="application/ld+json">{JSON.stringify(data)}</script>',
            '<Boot strategy="beforeInteractive">{`window.added = true`}</Boot>',
            '<Boot src="/early.js" strategy={"beforeInteractive"} />',
        ):
            with self.subTest(addition=addition):
                path.write_text('import Boot from "next/script";\n' + source.replace("</head>", addition + "</head>"), encoding="utf-8")
                self.assertNotEqual(self.original, csp.render())
                with self.assertRaisesRegex(SystemExit, "CSP inventory drift"):
                    csp.main(["--check"])

    def test_new_jsx_source_is_scanned_and_test_files_are_excluded(self):
        directory = self.root / "apps/web/src/components"
        directory.mkdir()
        for name in ("Added.jsx", "Ignored.test.tsx", "Ignored.spec.tsx"):
            (directory / name).write_text('<script>{"alert(1)"}</script>', encoding="utf-8")
        files = csp.next_inventory()
        self.assertEqual([(1, "inline", "script")], files["apps/web/src/components/Added.jsx"])
        self.assertNotIn("apps/web/src/components/Ignored.test.tsx", files)
        self.assertNotIn("apps/web/src/components/Ignored.spec.tsx", files)
        with self.assertRaisesRegex(SystemExit, "CSP inventory drift"):
            csp.main(["--check"])

    def test_data_src_inline_script_changes_inventory_and_fails_check(self):
        path = self.root / LAYOUT
        source = path.read_text(encoding="utf-8")
        addition = '<script data-src="/deferred.js">{"window.added = true"}</script>'
        path.write_text(source.replace("</head>", addition + "</head>"), encoding="utf-8")
        self.assertIn("**1 Inline scripts**", csp.render())
        with self.assertRaisesRegex(SystemExit, "CSP inventory drift"):
            csp.main(["--check"])

    def test_combined_script_imports_change_inventory_and_fail_check(self):
        path = self.root / LAYOUT
        source = path.read_text(encoding="utf-8")
        for declaration, alias in (
            ('import Script, { type ScriptProps } from "next/script";', "Script"),
            ('import Boot, { type ScriptProps as Props } from "next/script";', "Boot"),
            ('import { type ScriptProps, default as Boot } from "next/script";', "Boot"),
            ('import Boot, { default as Early, type ScriptProps } from "next/script";', "Early"),
        ):
            with self.subTest(declaration=declaration):
                addition = f'<{alias}>{{"window.added = true"}}</{alias}>'
                path.write_text(declaration + "\n" + source.replace("</head>", addition + "</head>"), encoding="utf-8")
                self.assertIn("**1 next/script elements**", csp.render())
                with self.assertRaisesRegex(SystemExit, "CSP inventory drift"):
                    csp.main(["--check"])


class NextSourceTests(unittest.TestCase):
    def test_script_kinds_are_counted_from_source(self):
        source = '''import EarlyScript from "next/script";
<script>{`window.a = true`}</script>
<script src="/external.js"></script>
<EarlyScript strategy="beforeInteractive" dangerouslySetInnerHTML={{__html: "a > b"}} />
<EarlyScript src="/early.js" strategy={'beforeInteractive'} />
<style dangerouslySetInnerHTML={{__html: "body { display: block }"}} />
<a href="javascript:alert(1)" onclick="alert(1)" onMouseOver={'alert(2)'} onClick={() => run()}>x</a>
'''
        counts = Counter(kind for _, kind, _ in csp.next_sites(source))
        self.assertEqual(dict(counts), dict(inline=2, next=2, before=2, html=2, handlers=2, urls=1, callbacks=1))

    def test_comments_are_ignored_and_html_strings_are_included(self):
        source = '''// <script>ignored</script>
{/* <script dangerouslySetInnerHTML={{__html: "ignored"}} /> */}
const html = `<script>reviewMe()</script>`;
const url = "https://example.org";
<script>{"active()"}</script>
'''
        self.assertEqual([(3, "inline", "script"), (5, "inline", "script")], csp.next_sites(source))

    def test_named_default_script_import_is_counted(self):
        sites = csp.next_sites('import { default as Boot } from "next/script";\n<Boot>{"run()"}</Boot>')
        self.assertEqual([(2, "inline", "Boot"), (2, "next", "Boot")], sites)

    def test_only_src_attribute_excludes_inline_scripts(self):
        for attrs in (
            'data-src="/deferred.js"',
            'custom-src="/deferred.js"',
            'data-note="src=/deferred.js"',
            'data-note=" src=/deferred.js"',
            'data-note={" src=/deferred.js"}',
            'data-note={{ src: "deferred", note: " src=ignored" }}',
        ):
            with self.subTest(attrs=attrs):
                sites = csp.next_sites(f'<script {attrs}>{{"run()"}}</script>')
                self.assertEqual([(1, "inline", "script")], sites)
        for attrs in (
            'src="/external.js"',
            'src = {"/external.js"}',
            'data-src="/deferred.js"\n src = "/external.js"',
            'data-note={"escaped \\\" quote >"} src={external}',
        ):
            with self.subTest(attrs=attrs):
                self.assertEqual([], csp.next_sites(f'<script {attrs}></script>'))

    def test_combined_and_aliased_script_imports_are_counted(self):
        for declaration in (
            'import Boot, { type ScriptProps } from "next/script";',
            "import Boot, { type ScriptProps as Props } from 'next/script';",
            'import Boot,\n { type ScriptProps, }\n from "next/script";',
            'import { type ScriptProps, default as Boot } from "next/script";',
            'import { default as Boot, type ScriptProps } from "next/script";',
            'import Other, { type ScriptProps, default as Boot } from "next/script";',
        ):
            with self.subTest(declaration=declaration):
                line = declaration.count("\n") + 2
                source = declaration + '\n<Boot data-src="/deferred.js">{"run()"}</Boot>'
                self.assertEqual([(line, "inline", "Boot"), (line, "next", "Boot")], csp.next_sites(source))
                source = declaration + '\n<Boot src="/early.js" strategy="beforeInteractive" />'
                self.assertEqual([(line, "next", "Boot"), (line, "before", "Boot")], csp.next_sites(source))

    def test_named_types_and_other_modules_are_not_script_aliases(self):
        source = '''import Boot, { type ScriptProps as Props } from "next/script";
import Other, { type ScriptProps } from "other/script";
import type TypeOnly from "next/script";
<Props />
<Other />
<TypeOnly />
'''
        self.assertEqual([], csp.next_sites(source))

    def test_duplicate_list_labels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate web label"):
            csp.compose_labels(["key=value", "key=other"])


class CallbackReferrerTests(unittest.TestCase):
    def test_sso_asset_requests_do_not_include_the_nonce_query_in_referrer(self):
        source = (ROOT / "docs/sso-verify.html").read_text()
        scripts = [attrs for _, tag, attrs in csp.source_tags(source) if tag == "script"]
        self.assertEqual(len(scripts), 2)
        self.assertTrue(all('referrerpolicy="no-referrer"' in attrs for attrs in scripts))

    def test_no_referrer_is_first_head_element_and_script_order_is_preserved(self):
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []

            def handle_starttag(self, tag, attrs):
                self.tags.append((tag, dict(attrs)))

        parser = Tags()
        parser.feed((ROOT / "docs/tickets/auth/callback.html").read_text(encoding="utf-8"))
        head = parser.tags.index(("head", {}))
        self.assertEqual(("meta", {"name": "referrer", "content": "no-referrer"}), parser.tags[head + 1])
        self.assertEqual(["../config.js", "../../assets/js/tickets-callback.js"], [attrs["src"] for tag, attrs in parser.tags if tag == "script"])
        self.assertFalse(any("referrerpolicy" in attrs for _, attrs in parser.tags))


if __name__ == "__main__":
    unittest.main()
