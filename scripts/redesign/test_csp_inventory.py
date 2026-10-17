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
REPORT = "customResponseHeaders.Content-Security-Policy-Report-Only="
BINDING = "traefik.http.routers.ekklesia-web.middlewares=ekklesia-headers"


class InventoryGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in (*sorted(csp.HASHED), COMPOSE, LAYOUT, "apps/web/next.config.mjs"):
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
        self.mutate_compose(lambda text: text.replace("      - " + BINDING + "\n", ""))
        with self.assertRaisesRegex(SystemExit, "ekklesia-web must bind"):
            csp.main(["--check"])

    def test_commented_router_binding_fails_check(self):
        self.mutate_compose(lambda text: text.replace("- " + BINDING, "# - " + BINDING))
        with self.assertRaisesRegex(SystemExit, "ekklesia-web must bind"):
            csp.main(["--check"])

    def test_binding_on_other_router_fails_check(self):
        self.mutate_compose(lambda text: text.replace(BINDING, BINDING.replace("ekklesia-web.", "unused-web.")))
        with self.assertRaisesRegex(SystemExit, "ekklesia-web must bind"):
            csp.main(["--check"])

    def test_disabled_web_service_fails_check(self):
        self.mutate_compose(lambda text: text.replace("traefik.enable=true", "traefik.enable=false"))
        with self.assertRaisesRegex(SystemExit, "enabled in Traefik"):
            csp.main(["--check"])

    def test_policy_hash_drift_fails_check(self):
        self.mutate_compose(lambda text: text.replace("sha256-Dj8kl", "sha256-wrong"))
        with self.assertRaisesRegex(SystemExit, "policy/hash drift"):
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

    def test_inline_script_changes_inventory_and_fails_check(self):
        path = self.root / LAYOUT
        source = path.read_text(encoding="utf-8")
        path.write_text(source.replace("</head>", "<script>{`window.added = true;`}</script></head>"), encoding="utf-8")
        self.assertNotEqual(self.original, csp.render())
        self.assertIn(f"| `{LAYOUT}` | 1 |", csp.render())
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

    def test_duplicate_list_labels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate web label"):
            csp.compose_labels(["key=value", "key=other"])


class CallbackReferrerTests(unittest.TestCase):
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
        self.assertEqual(["../config.js", "callback.js"], [attrs["src"] for tag, attrs in parser.tags if tag == "script"])
        self.assertFalse(any("referrerpolicy" in attrs for _, attrs in parser.tags))


if __name__ == "__main__":
    unittest.main()
