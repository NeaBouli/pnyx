"""B09/B10: consumer drift and wiki publication gates must fail on real drift."""
import copy
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_project_facts import project_facts
import approved_audit_delta
import r0_inventory

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("wiki_publish", ROOT / "scripts/wiki_publish.py")
wiki_publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_publish)


class ConsumerDriftTest(unittest.TestCase):
    def test_real_consumers_and_current_claims(self):
        facts = project_facts.compute()
        self.assertEqual(project_facts.consumer_errors(facts), [])
        self.assertEqual([c for c in project_facts.claims(facts) if c[-1] != "historical"], [])

    def test_changed_single_locale_missing_and_duplicate_consumer_fail(self):
        facts = project_facts.compute()
        template = '<p data-el="{{api_endpoints}} διαδρομές" data-en="{{api_endpoints}} routes">{{api_endpoints}} διαδρομές</p>'
        rendered = template.replace("{{api_endpoints}}", str(facts["counts"]["api_endpoints"]))
        spec = [{"path": "page.html", "template": template}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "page.html"
            for bad in (rendered.replace('data-en="198', 'data-en="16'), "", rendered + "\n" + rendered):
                page.write_text(bad)
                self.assertTrue(project_facts.consumer_errors(facts, root=root, specs=spec))
            page.write_text(rendered.replace('data-en="198', 'data-en="16'))
            self.assertEqual(project_facts.consumer_errors(facts, root=root, specs=spec, update=True), [])
            self.assertEqual(page.read_text(), rendered)

    def test_separated_metric_and_cost_slots_follow_changed_facts(self):
        facts = project_facts.compute()
        specs = [{"path": "page.html", "template": '<b>{{prod_containers}}</b><p>Compose services</p>'},
                 {"path": "page.html", "template": '<p>EUR {{recurring_yearly_en}} / {{recurring_yearly_el}} EUR</p>'}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text('<b>9</b><p>Compose services</p>\n<p>EUR 309.30 / 309,30 EUR</p>')
            changed = copy.deepcopy(facts)
            changed["counts"]["prod_containers"] += 1
            changed["cost_basis"]["recurring_eur"]["server_and_domain_yearly"] += 12
            self.assertEqual(len(project_facts.consumer_errors(changed, root=root, specs=specs)), 2)

    def test_claims_command_fails_on_unlabelled_mismatch(self):
        with patch.object(project_facts, "claims", return_value=[("page", 1, "api_endpoints", "16 endpoints", "mismatch")]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(project_facts.main(["--claims"]), 1)


class WikiPublicationTest(unittest.TestCase):
    def test_real_publication_is_current(self):
        self.assertEqual(wiki_publish.check(), [])

    def test_md_locale_shared_and_missing_fact_drift_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/wiki").mkdir(parents=True)
            (root / "wiki").mkdir()
            for slug, name in wiki_publish.PAGES.items():
                shutil.copyfile(ROOT / f"docs/wiki/{slug}.html", root / f"docs/wiki/{slug}.html")
                shutil.copyfile(ROOT / f"wiki/{name}.md", root / f"wiki/{name}.md")
            target = root / "wiki/Security.md"
            target.write_text(target.read_text().replace("Argon2id v2", "SHA256-only"))
            self.assertTrue(any("Security.md" in e for e in wiki_publish.check(root=root)))
            self.assertEqual(wiki_publish.check(root=root, write=True), [])
            target = root / "docs/wiki/security.html"
            source = target.read_text()
            target.write_text(source.replace("Production uses Argon2id v2", "All deployments use Argon2id v2"))
            self.assertTrue(any("shared fact drift" in e for e in wiki_publish.check(root=root)))
            self.assertEqual(wiki_publish.check(root=root, write=True), [])
            target.write_text(source.replace('data-wiki-fact="identity-hashing"', 'data-wiki-fact="removed"'))
            self.assertTrue(any("missing/duplicated shared" in e for e in wiki_publish.check(root=root)))

    def test_bilingual_render_keeps_tables_links_and_code(self):
        source = '''<h1 data-el="Ασφάλεια" data-en="Security">Ασφάλεια</h1><div class="layout">
<p data-el="Κείμενο &lt;strong&gt;ΕΛ&lt;/strong&gt;" data-en="Copy &lt;strong&gt;EN&lt;/strong&gt;">Κείμενο</p>
<table><tr><th>A</th><th>B</th></tr><tr><td>x</td><td>y</td></tr></table>
<a href="privacy.html">Privacy</a><div class="code-block">x = 1\ny = 2</div></div>'''
        result = wiki_publish.render(source, "security")
        for expected in ("Κείμενο **ΕΛ**", "Copy **EN**", "| A | B |\n| --- | --- |\n| x | y |",
                         "(https://ekklesia.gr/wiki/privacy.html)", "```text\nx = 1\ny = 2\n```", "## English"):
            self.assertIn(expected, result)
        self.assertFalse(any(line and line.isspace() for line in result.splitlines()))

    def test_shared_claims_are_present_in_both_languages(self):
        for slug in ("privacy", "security", "whitepaper"):
            parser = wiki_publish.Parser()
            parser.feed((ROOT / f"docs/wiki/{slug}.html").read_text())
            for key in ("identity-hashing", "newsletter-email"):
                node = parser.root.find(lambda n: n.attrs.get("data-wiki-fact") == key)
                self.assertIsNotNone(node)
                for lang in ("el", "en"):
                    self.assertTrue(node.attrs.get(f"data-{lang}"))
            text = (ROOT / f"wiki/{wiki_publish.PAGES[slug]}.md").read_text()
            for wording in ("Production uses Argon2id v2", "SHA-256 compatibility anchor", "Nullifiers are versioned"):
                self.assertIn(wording, text)

    def test_bridge_stays_planned_and_inactive_without_module_id(self):
        text = (ROOT / "wiki/Whitepaper.md").read_text()
        self.assertIn("planned and inactive; it has no current module ID", text)
        self.assertIn("προγραμματισμένη και ανενεργή", text)
        self.assertNotIn("MOD-08 Bridge", text)


class PrecisePreservationTest(unittest.TestCase):
    def test_bundle_pages_accept_only_the_pinned_inventory(self):
        for path in ("docs/community.html", "docs/wiki/api.html", "docs/wiki/database.html",
                     "docs/wiki/faq.html", "docs/wiki/index.html", "docs/wiki/modules.html",
                     "docs/wiki/privacy.html", "docs/wiki/security.html", "docs/wiki/whitepaper.html"):
            current = r0_inventory.inventory_page(path)
            self.assertTrue(approved_audit_delta.matches_approved_content(path, current), path)
            changed = copy.deepcopy(current)
            changed["text"]["chunks"].append("unapproved visible copy")
            self.assertFalse(approved_audit_delta.matches_approved_content(path, changed), path)


if __name__ == "__main__":
    unittest.main()
