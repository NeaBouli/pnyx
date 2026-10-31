"""PR #728 regressions: missed consumers, claim scope and safe wiki publication."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urljoin

from test_eka_bundle3_publication import ROOT, project_facts, wiki_publish


class ReviewClaimsTest(unittest.TestCase):
    def scan(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.html"
            page.write_text(text)
            return project_facts.claims(project_facts.compute(), [page])

    def test_qualified_counts_in_both_locales(self):
        for phrase, kind in (
            ("route decorators", "api_endpoints"), ("API route decorators", "api_endpoints"),
            ("routers", "api_routers"), ("ORM tables", "db_tables_orm"),
            ("listed modules", "modules"), ("Compose services", "prod_containers"),
            ("production Compose services", "prod_containers"),
            ("δηλώσεις διαδρομών API", "api_endpoints"), ("πίνακες ORM", "db_tables_orm"),
            ("καταχωρισμένες ενότητες", "modules"), ("υπηρεσίες production Compose", "prod_containers"),
        ):
            for text in (f"999 {phrase}", f"{phrase}: 999", f"| {phrase} | 999 |"):
                with self.subTest(text=text):
                    self.assertEqual([(c[2], c[4]) for c in self.scan(text)], [(kind, "mismatch")])

    def test_historical_label_does_not_exempt_next_claim(self):
        for separator in ("; current API: ", ", ", ". Current API: ", " and current API: "):
            with self.subTest(separator=separator):
                hits = self.scan("Historical 2026-09-15: 188 endpoints" + separator + "999 endpoints")
                self.assertEqual([c[-1] for c in hits], ["historical", "mismatch"])

    def test_historical_labels_are_local_to_each_locale_and_visible_claim(self):
        samples = (
            '<p data-el="Ιστορικά 2026-09-15: 188 endpoints" data-en="Current API: 999 endpoints">Ιστορικά 2026-09-15: 188 endpoints</p>',
            '<p data-en="Historical 2026-09-15: 188 endpoints">999 endpoints</p>',
            '<p>Historical 2026-09-15: 188 endpoints</p><p>999 endpoints</p>',
            '<p data-note="Historical 2026-09-15">999 endpoints</p>',
            '<p>Historical 2026-09-15; current API: 999 endpoints</p>',
            '<p>Ιστορικά 2026-09-15· Τρέχον API: 999 endpoints</p>',
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertTrue(any(c[3] == "999 endpoints" and c[-1] == "mismatch" for c in self.scan(text)))

    def test_matching_historical_claim_does_not_exempt_next_count(self):
        hits = self.scan("Historical 2026-09-15: 198 endpoints, 999 routers")
        self.assertEqual([(c[2], c[-1]) for c in hits], [("api_routers", "mismatch")])

    def test_inactive_subset_is_checked_against_subset_fact(self):
        for text in ("23 modules including 2 modules disabled", "23 listed modules (2 inactive modules)",
                     "23 καταχωρισμένες ενότητες, από τις οποίες 2 ανενεργές ενότητες"):
            with self.subTest(text=text):
                self.assertEqual(self.scan(text), [])
        self.assertTrue(self.scan("23 modules including 3 modules disabled"))
        self.assertTrue(self.scan("23 modules including 2 modules disabled; current total: 999 modules"))


class ReviewConsumerTest(unittest.TestCase):
    def test_cost_mutations_fail_consumer_gate_including_markdown(self):
        facts = project_facts.compute()
        specs = json.loads(project_facts.CONSUMERS.read_text())
        samples = (
            ("docs/community.html", 'data-en="€300/year"', 'data-en="€999/year"'),
            ("docs/community.html", '<strong>9,30€/', '<strong>99,30€/'),
            ("wiki/Whitepaper.md", "EUR 25/month", "EUR 999/month"),
            ("wiki/Whitepaper.md", "9,30 EUR/έτος", "99,30 EUR/έτος"),
        )
        for rel, before, after in samples:
            with self.subTest(path=rel, before=before), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                page = root / rel
                page.parent.mkdir(parents=True)
                source = (ROOT / rel).read_text()
                self.assertIn(before, source)
                page.write_text(source.replace(before, after, 1))
                selected = [s for s in specs if s["path"] == rel]
                self.assertTrue(project_facts.consumer_errors(facts, root=root, specs=selected))

    def test_appended_llms_claim_fails_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "llms.txt"
            page.write_text((ROOT / "docs/llms.txt").read_text() +
                            "\n999 route decorators, 999 routers, 999 ORM tables, 999 listed modules and 99 Compose services.\n")
            with patch.object(project_facts, "claim_paths", return_value=[page]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(project_facts.main(["--check-consumers"]), 1)
            self.assertEqual(len(project_facts.claims(project_facts.compute(), [page])), 5)


class ReviewWikiTest(unittest.TestCase):
    def render(self, body):
        return wiki_publish.render('<h1>Test</h1><div class="layout">' + body + '</div>', "privacy")

    def test_translation_keeps_nested_links_and_inline_elements(self):
        result = self.render('''<p data-el="Οδηγίες: κλειδί" data-en="Instructions: key">
<strong data-el="κλειδί" data-en="key">κλειδί</strong>
<span><a href="delete-account.html" data-el="Διαγραφή" data-en="Delete">Διαγραφή</a></span></p>''')
        el, en = result.split("## Ελληνικά\n", 1)[1].split("## English\n", 1)
        for text, label, emphasis in ((el, "Διαγραφή", "κλειδί"), (en, "Delete", "key")):
            self.assertIn(f"[{label}](https://ekklesia.gr/wiki/delete-account.html)", text)
            self.assertIn(f"**{emphasis}**", text)
            self.assertIn(f"**{emphasis}** [{label}]", text)
        # Inline formatting must not rewrite matching words inside a URL.
        result = self.render('''<p data-el="&lt;a href='https://example.org/key'&gt;Link&lt;/a&gt;" data-en="&lt;a href='https://example.org/key'&gt;Link&lt;/a&gt;">
<strong>key</strong></p>''')
        self.assertIn("[Link](https://example.org/key)", result)

    def test_every_source_link_survives_in_each_language(self):
        def walk(node):
            if not isinstance(node, wiki_publish.Node):
                return
            yield node
            for child in node.children:
                yield from walk(child)

        for slug, name in wiki_publish.PAGES.items():
            parser = wiki_publish.Parser()
            parser.feed((ROOT / f"docs/wiki/{slug}.html").read_text())
            text = (ROOT / f"wiki/{name}.md").read_text()
            languages = text.split("## Ελληνικά\n", 1)[1].split("## English\n", 1)
            base = f"https://ekklesia.gr/wiki/{slug}.html"
            for lang, output in zip(("el", "en"), languages):
                for node in walk(parser.root):
                    nodes = [node]
                    if f"data-{lang}" in node.attrs:
                        fragment = wiki_publish.Parser()
                        fragment.feed(node.attrs[f"data-{lang}"])
                        nodes += list(walk(fragment.root))
                    for link in nodes:
                        if link.tag == "a" and link.attrs.get("href"):
                            with self.subTest(slug=slug, lang=lang, href=link.attrs["href"]):
                                self.assertIn(f'({urljoin(base, link.attrs["href"])})', output)

    def test_literal_html_and_markdown_cannot_create_active_content(self):
        result = self.render('''<p>&lt;script&gt;alert(1)&lt;/script&gt; [click](javascript:alert(1)) **literal**</p>
<p data-el="&amp;lt;script&amp;gt;alert(1)&amp;lt;/script&amp;gt;" data-en="&amp;lt;img src=x onerror=alert(1)&amp;gt;">EL</p>
<pre>```\n&lt;script&gt;alert(1)&lt;/script&gt;</pre>''')
        self.assertNotRegex(result, r"<\s*(?:script|img)\b")
        self.assertIn("&lt;script&gt;", result)
        self.assertIn(r"\[click\]", result)
        self.assertIn(r"\*\*literal\*\*", result)
        self.assertIn("````text", result)

    def test_only_safe_url_schemes_and_safe_destinations_survive(self):
        for url in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,bad", "vbscript:bad", "ftp://example.org", "java&#10;script:bad"):
            with self.subTest(url=url):
                self.assertNotIn("](", self.render(f'<a href="{url}">Unsafe</a>').split("## Ελληνικά", 1)[1])
        for url in ("https://example.org/ok", "http://example.org/ok", "mailto:a@example.org", "../legal.html", "#section", "/el/bills"):
            with self.subTest(url=url):
                self.assertIn(f'({urljoin("https://ekklesia.gr/wiki/privacy.html", url)})', self.render(f'<a href="{url}">Safe</a>'))
        result = self.render('<a href="https://example.org/a) &lt;script&gt;">Safe</a>')
        self.assertIn("a%29%20%3Cscript%3E", result)

    def test_argon_claim_is_dated_scoped_and_matches_code_default(self):
        for slug, name in wiki_publish.PAGES.items():
            source = (ROOT / f"docs/wiki/{slug}.html").read_text()
            output = (ROOT / f"wiki/{name}.md").read_text()
            for text in (source, output):
                with self.subTest(slug=slug):
                    self.assertIn("Production uses Argon2id v2 with a SHA-256 compatibility anchor (checked 2026-10-31); the code default is v1.", text)
                    self.assertIn("Στην παραγωγή (έλεγχος 2026-10-31) χρησιμοποιείται Argon2id v2 με άγκυρα συμβατότητας SHA-256· η προεπιλογή του κώδικα είναι v1.", text)


if __name__ == "__main__":
    unittest.main()
