"""Initial Greek copy is complete before any language-switch JavaScript runs."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


@dataclass
class Element:
    tag: str
    attrs: dict[str, str | None]
    in_roadmap: bool
    in_nav: bool
    text: list[str] = field(default_factory=list)


class InitialTextParser(HTMLParser):
    """Read rendered text, including descendants, without executing scripts."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[Element] = []
        self.elements: list[Element] = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element = Element(
            tag=tag,
            attrs=values,
            in_roadmap=values.get("id") == "roadmap"
            or any(parent.in_roadmap for parent in self.stack),
            in_nav=tag == "nav" or any(parent.in_nav for parent in self.stack),
        )
        self.elements.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        for element in self.stack:
            element.text.append(data)


def normalize(text: str) -> str:
    """Ignore indentation only, not omitted words or punctuation."""
    return " ".join(text.split())


class InitialLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.landing = InitialTextParser(
            (REPO / "docs/index.html").read_text(encoding="utf-8")
        )
        cls.wiki = InitialTextParser(
            (REPO / "docs/wiki/zk-voting.html").read_text(encoding="utf-8")
        )

    def assert_initial_greek(self, elements: list[Element]) -> None:
        for element in elements:
            with self.subTest(tag=element.tag, expected=element.attrs["data-el"]):
                self.assertEqual(
                    normalize("".join(element.text)),
                    normalize(element.attrs["data-el"] or ""),
                )

    def test_landing_roadmap_initial_text_matches_existing_greek_pairs(self) -> None:
        elements = [
            element for element in self.landing.elements
            if element.in_roadmap and "data-el" in element.attrs
        ]
        self.assertGreaterEqual(len(elements), 30, "Roadmap scope must not be empty")
        self.assert_initial_greek(elements)

    def test_zk_wiki_initial_text_matches_existing_greek_pairs(self) -> None:
        elements = [
            element for element in self.wiki.elements if "data-el" in element.attrs
        ]
        self.assertGreaterEqual(len(elements), 20, "Wiki pairs must not be empty")
        self.assert_initial_greek(elements)

    def test_zk_wiki_has_exactly_one_wired_navigation_language_button(self) -> None:
        buttons = [
            element for element in self.wiki.elements
            if element.attrs.get("id") == "langBtn"
        ]
        self.assertEqual(len(buttons), 1)
        button = buttons[0]
        self.assertEqual(button.tag, "button")
        self.assertTrue(button.in_nav)
        self.assertEqual(button.attrs.get("onclick"), "toggleLang()")
        self.assertEqual(normalize("".join(button.text)), "EN")

    def test_zk_wiki_existing_toggle_updates_document_and_bilingual_elements(self) -> None:
        script = "\n".join(
            "".join(element.text) for element in self.wiki.elements
            if element.tag == "script" and "src" not in element.attrs
        )
        self.assertEqual(len(re.findall(r"function\s+toggleLang\s*\(", script)), 1)
        self.assertRegex(script, r'var\s+currentLang\s*=\s*[\'"]el[\'"]')
        self.assertRegex(script, r"document\.documentElement\.lang\s*=\s*currentLang")
        self.assertRegex(script, r'getElementById\([\'"]langBtn[\'"]\)\.textContent')
        self.assertRegex(script, r'querySelectorAll\([\'"]\[data-el\][\'"]\)')
        self.assertRegex(script, r'getAttribute\([\'"]data-[\'"]\s*\+\s*currentLang\)')


if __name__ == "__main__":
    unittest.main()
