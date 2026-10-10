"""Static accessibility source contracts; these are not browser/rendering tests."""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGES = ("docs/index.html", "docs/community.html", "docs/wiki/index.html")
VOID_TAGS = frozenset("area base br col embed hr img input link meta param source track wbr".split())


class StyleParser(HTMLParser):
    """Ignore comments mentioning <style>; collect only actual style elements."""
    def __init__(self) -> None:
        super().__init__()
        self.in_style = False
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.styles.append(data)


class HeadingParser(HTMLParser):
    """Keep ancestor scopes, including distinct participation-grid occurrences."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, set[str]]] = []
        self.headings: list[tuple[str, dict[str, str | None], set[str]]] = []
        self.participate_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        scopes = {"." + name for name in (attributes.get("class") or "").split()}
        if attributes.get("id"):
            scopes.add("#" + str(attributes["id"]))
        if ".participate-grid" in scopes:
            self.participate_count += 1
            scopes.add(f"participate-grid:{self.participate_count}")
        if re.fullmatch(r"h[1-6]", tag):
            ancestors = set().union(*(item[1] for item in self.stack))
            self.headings.append((tag, attributes, ancestors))
        if tag not in VOID_TAGS:
            self.stack.append((tag, scopes))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)


def source(page: str) -> str:
    return (ROOT / page).read_text(encoding="utf-8")


def selector_key(selector: str) -> str:
    return re.sub(r"\s*>\s*", " > ", re.sub(r"\s+", " ", selector.strip())).replace("'", '"')


def luminance(color: str) -> float:
    components = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in components]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


class StaticAccessibilityContracts(unittest.TestCase):
    def test_language_toggle_updates_document_language(self) -> None:
        for page in PAGES:
            with self.subTest(page=page):
                match = re.search(r"function\s+toggleLang\s*\(\s*\)\s*\{(.*?)\n\}", source(page), re.DOTALL)
                self.assertIsNotNone(match)
                assert match is not None
                body = match.group(1)
                toggle = re.search(r"currentLang\s*=\s*currentLang\s*===?\s*['\"]el['\"]\s*\?\s*['\"]en['\"]\s*:\s*['\"]el['\"]", body)
                sync = re.search(r"document\.documentElement\.lang\s*=\s*currentLang\s*;", body)
                self.assertIsNotNone(toggle)
                self.assertIsNotNone(sync)
                assert toggle is not None and sync is not None
                self.assertLess(toggle.end(), sync.start())

    def test_measured_headings_preserve_visual_tags_and_level_three(self) -> None:
        expected = (
            ("docs/index.html", ".ticker-grid", 3),
            ("docs/community.html", ".principle-grid", 6),
            ("docs/community.html", "participate-grid:1", 7),
            ("docs/community.html", "#transparencyCard", 1),
            ("docs/wiki/index.html", ".card", 13),
        )
        for page, scope, count in expected:
            with self.subTest(page=page, scope=scope):
                parser = HeadingParser()
                parser.feed(source(page))
                headings = [(tag, attrs) for tag, attrs, ancestors in parser.headings if scope in ancestors]
                self.assertEqual(len(headings), count)
                for tag, attrs in headings:
                    self.assertEqual(tag, "h4")
                    self.assertEqual(attrs.get("role"), "heading")
                    self.assertEqual(attrs.get("aria-level"), "3")

    def test_color_overrides_use_exact_page_scoped_selectors(self) -> None:
        expected = (
            ("docs/index.html", "#newsletter label > span[data-el]", "#475569", False),
            ("docs/community.html", ".principle-grid .pc > p", "#475569", False),
            ("docs/community.html", 'p[data-el="Όλοι συνεισφέρουν ισότιμα. Κανείς δεν ελέγχει."]', "#475569", True),
            ("docs/community.html", ".nav-logo > span", "#475569", True),
            ("docs/wiki/index.html", ".nav-logo > span", "#475569", True),
            ("docs/wiki/index.html", "footer > p", "#cbd5e1", False),
        )
        for page, selector, color, important in expected:
            with self.subTest(page=page, selector=selector):
                parser = StyleParser()
                parser.feed(source(page))
                styles = "\n".join(parser.styles)
                styles = re.sub(r"/\*.*?\*/", "", styles, flags=re.DOTALL)
                rules = re.findall(r"([^{}]+)\{([^{}]*)\}", styles)
                declarations = [
                    body for rule, body in rules
                    if selector_key(selector) in {selector_key(item) for item in rule.split(",")}
                ]
                suffix = r"\s*!important" if important else ""
                pattern = r"\s*color\s*:\s*" + re.escape(color) + suffix + r"\s*;?\s*"
                self.assertTrue(any(re.fullmatch(pattern, body, re.IGNORECASE) for body in declarations), selector)

    def test_specified_color_pairs_have_text_contrast(self) -> None:
        pairs = [("#475569", background) for background in ("#f8fafc", "#f1f5f9", "#ffffff")]
        pairs.append(("#cbd5e1", "#0f172a"))
        for foreground, background in pairs:
            with self.subTest(foreground=foreground, background=background):
                light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
                self.assertGreaterEqual((light + 0.05) / (dark + 0.05), 4.5)


if __name__ == "__main__":
    unittest.main()
