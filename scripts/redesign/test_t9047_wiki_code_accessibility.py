"""Static contracts for the named, keyboard-focusable Wiki Quick Start region.

Actual language-toggle, scrolling and visible-focus behavior require browser proof.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import unittest


WIKI = Path(__file__).resolve().parents[2] / "docs/wiki/index.html"
QUICK_START_TEXT = """# Clone
git clone https://github.com/NeaBouli/pnyx && cd pnyx

# Services
cd infra/docker && docker compose up -d

# Database
cd ../../apps/api && pip install -r requirements.txt
alembic upgrade head && python seeds/seed_real_bills.py

# API → https://api.ekklesia.gr/health
uvicorn main:app --reload

# Web → https://ekklesia.gr
cd ../web && npm install && npm run dev"""


@dataclass
class Element:
    tag: str
    attrs: dict[str, str | None]
    text: list[str] = field(default_factory=list)


class WikiParser(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[Element] = []
        self.stack: list[Element] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(tag, dict(attrs))
        self.elements.append(element)
        if tag not in self.VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append(Element(tag, dict(attrs)))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        for element in self.stack:
            element.text.append(data)


class WikiCodeAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = WikiParser()
        cls.parser.feed(WIKI.read_text(encoding="utf-8"))
        cls.parser.close()

    def code_block(self) -> Element:
        blocks = [element for element in self.parser.elements
                  if "code-block" in (element.attrs.get("class") or "").split()]
        self.assertEqual(len(blocks), 1, "Quick Start must remain one code block")
        return blocks[0]

    def heading(self) -> Element:
        headings = [element for element in self.parser.elements
                    if element.attrs.get("id") == "quickStartTitle"]
        self.assertEqual(len(headings), 1, "Accessible-name target must be unique")
        self.assertEqual(headings[0].tag, "h2")
        return headings[0]

    def test_code_block_is_focusable_named_region(self) -> None:
        block = self.code_block()
        self.assertEqual(block.attrs.get("tabindex"), "0")
        self.assertEqual(block.attrs.get("role"), "region")
        self.assertEqual((block.attrs.get("aria-labelledby") or "").split(),
                         [self.heading().attrs["id"]])
        self.assertNotIn("hidden", block.attrs)
        self.assertNotEqual(block.attrs.get("aria-hidden"), "true")

    def test_region_name_retains_both_language_sources(self) -> None:
        heading = self.heading()
        self.assertEqual(heading.attrs.get("data-el"), "Γρήγορη Εκκίνηση")
        self.assertEqual(heading.attrs.get("data-en"), "Quick Start")
        self.assertEqual("".join(heading.text).strip(), "Γρήγορη Εκκίνηση")
        self.assertNotIn("hidden", heading.attrs)

    def test_existing_quick_start_commands_are_unchanged(self) -> None:
        self.assertEqual("".join(self.code_block().text).strip(), QUICK_START_TEXT)


if __name__ == "__main__":
    unittest.main()
