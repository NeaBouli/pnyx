"""Initial Greek copy is complete before any language-switch JavaScript runs."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
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


MAINTAINED_PAGES = ("docs/index.html", "docs/community.html", "docs/wiki/*.html")
PLACEHOLDER = re.compile(r"\{\s*(\w+)")


def unpaired_language_attrs(source: str) -> list[str]:
    """Elements with only one of data-el/data-en, or an empty side."""
    return [
        f"<{element.tag} data-el={element.attrs.get('data-el')!r} "
        f"data-en={element.attrs.get('data-en')!r}>"
        for element in InitialTextParser(source).elements
        if ("data-el" in element.attrs or "data-en" in element.attrs)
        and not all(
            (element.attrs.get(lang) or "").strip() for lang in ("data-el", "data-en")
        )
    ]


def catalog_leaves(tree: object, prefix: str = "") -> dict[str, object]:
    if not isinstance(tree, dict):
        return {prefix: tree}
    leaves: dict[str, object] = {}
    for key, value in tree.items():
        leaves.update(catalog_leaves(value, f"{prefix}.{key}" if prefix else key))
    return leaves


def catalog_mismatches(el: dict, en: dict) -> list[str]:
    """Key shape, nonempty string leaves and matching ICU argument names."""
    el_leaves, en_leaves = catalog_leaves(el), catalog_leaves(en)
    problems = [f"missing en: {key}" for key in sorted(el_leaves.keys() - en_leaves.keys())]
    problems += [f"missing el: {key}" for key in sorted(en_leaves.keys() - el_leaves.keys())]
    for key in sorted(el_leaves.keys() & en_leaves.keys()):
        pair = (el_leaves[key], en_leaves[key])
        if not all(isinstance(value, str) and value.strip() for value in pair):
            problems.append(f"empty or non-string: {key}")
        elif set(PLACEHOLDER.findall(pair[0])) != set(PLACEHOLDER.findall(pair[1])):
            problems.append(f"placeholder mismatch: {key}")
    return problems


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


    def test_maintained_static_pages_pair_every_language_attribute(self) -> None:
        pages = sorted(
            path for pattern in MAINTAINED_PAGES for path in REPO.glob(pattern)
        )
        self.assertGreaterEqual(len(pages), 10, "Maintained page scope must not be empty")
        for page in pages:
            with self.subTest(page=str(page.relative_to(REPO))):
                self.assertEqual(
                    unpaired_language_attrs(page.read_text(encoding="utf-8")), []
                )

    def test_language_pair_guard_rejects_missing_or_empty_side(self) -> None:
        self.assertEqual(unpaired_language_attrs('<p data-el="Α" data-en="A">Α</p>'), [])
        self.assertEqual(len(unpaired_language_attrs('<p data-el="Α">Α</p>')), 1)
        self.assertEqual(len(unpaired_language_attrs('<p data-en="A">A</p>')), 1)
        self.assertEqual(len(unpaired_language_attrs('<p data-el="Α" data-en=" ">Α</p>')), 1)

    def test_web_message_catalogs_share_keys_and_placeholders(self) -> None:
        messages = REPO / "apps/web/src/messages"
        el = json.loads((messages / "el.json").read_text(encoding="utf-8"))
        en = json.loads((messages / "en.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(catalog_leaves(el)), 20, "Catalog must not be empty")
        self.assertEqual(catalog_mismatches(el, en), [])

    def test_catalog_guard_rejects_missing_empty_and_placeholder_drift(self) -> None:
        el = {"vote": {"title": "Ψήφος {count}", "cta": "Ψήφισε"}}
        self.assertEqual(
            catalog_mismatches(el, {"vote": {"title": "Vote {count}", "cta": "Vote"}}), []
        )
        self.assertEqual(
            catalog_mismatches(el, {"vote": {"title": "Vote {count}"}}),
            ["missing en: vote.cta"],
        )
        self.assertEqual(
            catalog_mismatches(el, {"vote": {"title": "Vote {total}", "cta": " "}}),
            ["empty or non-string: vote.cta", "placeholder mismatch: vote.title"],
        )


if __name__ == "__main__":
    unittest.main()
