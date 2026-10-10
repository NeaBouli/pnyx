"""Keep the newsletter audience selector named without changing its payload."""

from html.parser import HTMLParser
from pathlib import Path
import unittest


class NewsletterMarkup(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.elements: dict[str, list[dict[str, str | None]]] = {}
        self.option_values: list[str | None] = []
        self.inside_type = False
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.elements.setdefault(str(values["id"]), []).append(values)
        if tag == "select" and values.get("id") == "nlType":
            self.inside_type = True
        if tag == "option" and self.inside_type:
            self.option_values.append(values.get("value"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.inside_type = False


class NewsletterAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.markup = NewsletterMarkup(
            (Path(__file__).resolve().parents[2] / "docs/index.html").read_text(encoding="utf-8")
        )

    def test_selector_references_one_real_bilingual_name(self) -> None:
        selectors = self.markup.elements["nlType"]
        self.assertEqual(len(selectors), 1)
        label_id = selectors[0]["aria-labelledby"]
        labels = self.markup.elements[str(label_id)]
        self.assertEqual(len(labels), 1)
        self.assertTrue(labels[0]["data-el"])

    def test_label_uses_existing_bilingual_toggle_contract(self) -> None:
        label = self.markup.elements["nlTypeLabel"][0]
        self.assertEqual(label["data-el"], "Τύπος συνδρομητή")
        self.assertEqual(label["data-en"], "Subscriber type")
        self.assertIn("hidden", label)  # no visible redesign/layout change

    def test_subscription_type_values_unchanged(self) -> None:
        self.assertEqual(self.markup.option_values,
                         ["citizens", "press", "parties", "public_bodies", "ngos", "government"])


if __name__ == "__main__":
    unittest.main()
