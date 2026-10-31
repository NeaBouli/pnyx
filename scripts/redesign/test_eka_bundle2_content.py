"""EKA-42/47/51: first-render Greek, FAQ grouping, badges and structured answers."""

import json
from pathlib import Path
import unittest

from test_t9032_initial_language import InitialTextParser, normalize


ROOT = Path(__file__).resolve().parents[2]
INITIAL_PAGES = (
    "docs/index.html", "docs/representative.html", "docs/community.html",
    "docs/wiki/faq.html",
)


def rendered(fragment):
    parser = InitialTextParser("<div>" + fragment + "</div>")
    return normalize("".join(parser.elements[0].text))


def initial_mismatches(source):
    return [
        (element.tag, normalize("".join(element.text)), rendered(element.attrs["data-el"]))
        for element in InitialTextParser(source).elements
        if "data-el" in element.attrs
        and normalize("".join(element.text)) != rendered(element.attrs["data-el"])
    ]


class Bundle2ContentTests(unittest.TestCase):
    def test_compass_key_selection_covers_incomplete_migrations_in_both_languages(self):
        wording = (
            "Για νέες αποθηκεύσεις χρησιμοποιείται το ξεχωριστό μη εξαγώγιμο κλειδί AES του IndexedDB όταν υπάρχει· αλλιώς παράγεται κλειδί από το παλαιό ιδιωτικό κλειδί ταυτότητας. Μια ατελής μεταφορά μπορεί να διατηρεί και τα δύο.",
            "New writes use the separate non-extractable AES key in IndexedDB when available; otherwise they derive a key from the legacy identity private key. An incomplete migration can retain both.",
        )
        for name in ("docs/wiki/privacy.html", "docs/wiki/faq.html", "docs/wiki/roadmap.html",
                     "docs/llms.txt", "apps/api/data/agent_facts.json", "apps/api/scripts/seed_knowledge_base.py"):
            with self.subTest(source=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                for sentence in wording:
                    self.assertIn(sentence, source)
                self.assertNotIn("before migration, the encryption key is derived", source)
                self.assertNotIn("πριν από αυτήν, το κλειδί κρυπτογράφησης παράγεται", source)

    def test_initial_greek_equals_el_toggle_on_corrected_pages(self):
        for name in INITIAL_PAGES:
            with self.subTest(page=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                self.assertGreater(source.count("data-el="), 20)
                self.assertEqual(initial_mismatches(source), [])

    def test_first_render_guard_checks_words_and_decoded_inline_markup(self):
        self.assertEqual(initial_mismatches(
            '<p data-el="Κύριο &amp; πλήρες">Κύριο &amp; <strong>πλήρες</strong></p>'
        ), [])
        self.assertEqual(len(initial_mismatches(
            '<p data-el="Κύριο και πλήρες">Κύριο</p>'
        )), 1)

    def faq_elements(self):
        return InitialTextParser(
            (ROOT / "docs/wiki/faq.html").read_text(encoding="utf-8")
        ).elements

    def test_section_badges_count_items_and_survive_translation(self):
        sections = []
        for element in self.faq_elements():
            classes = (element.attrs.get("class") or "").split()
            if element.tag == "h2" and "fade-in" in classes:
                # toggleLang replaces innerHTML on [data-el]; the heading must
                # keep its badge outside the translated label's element.
                self.assertNotIn("data-el", element.attrs)
                sections.append({"badge": None, "items": 0})
            elif "faq-count" in classes:
                sections[-1]["badge"] = int("".join(element.text))
            elif "faq-q" in classes:
                sections[-1]["items"] += 1
        self.assertEqual(len(sections), 9)
        for index, section in enumerate(sections):
            with self.subTest(section=index):
                self.assertEqual(section["badge"], section["items"])

    def test_semaphore_is_under_identity_and_security(self):
        heading = None
        matches = []
        for element in self.faq_elements():
            if element.tag == "h2":
                heading = normalize("".join(element.text))
            if element.attrs.get("data-en") == "What is Semaphore ZK Voting?":
                matches.append(heading)
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].startswith("Ταυτότητα & Ασφάλεια"))

    def test_all_visible_questions_and_answers_match_faq_json_ld(self):
        elements = self.faq_elements()
        questions = [normalize("".join(e.text)) for e in elements
                     if "faq-q" in (e.attrs.get("class") or "").split()]
        answers = [normalize("".join(e.text)) for e in elements
                   if "faq-a" in (e.attrs.get("class") or "").split()]
        schemas = [json.loads("".join(e.text)) for e in elements
                   if e.tag == "script" and e.attrs.get("type") == "application/ld+json"]
        faq = [schema for schema in schemas if schema.get("@type") == "FAQPage"]
        self.assertEqual(len(faq), 1)
        self.assertEqual(faq[0]["inLanguage"], "el")
        self.assertEqual(len(questions), 58)
        self.assertEqual(len(questions), len(answers))
        self.assertEqual(
            [(entry["name"], entry["acceptedAnswer"]["text"])
             for entry in faq[0]["mainEntity"]],
            list(zip(questions, answers)),
        )


if __name__ == "__main__":
    unittest.main()
