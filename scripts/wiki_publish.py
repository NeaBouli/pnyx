#!/usr/bin/env python3
"""B10: maintain wiki facts in docs/wiki HTML; publish EL/EN Markdown mirrors.

Run project_facts.py --write / --update-consumers first, then this --write.
--check is a CI gate. No network, external parser or runtime HTML changes.
Only Security, Privacy, Whitepaper and Database are migrated in this bundle.
Shared identity/newsletter paragraphs are maintained in privacy.html alone.
"""
from __future__ import annotations

import argparse
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = {"security": "Security", "privacy": "Privacy", "whitepaper": "Whitepaper", "database": "Database"}
SHARED = {"identity-hashing": ("security", "whitepaper", "database"),
          "newsletter-email": ("security", "whitepaper")}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def find(self, predicate):
        if predicate(self):
            return self
        for child in self.children:
            if isinstance(child, Node):
                found = child.find(predicate)
                if found is not None:
                    return found
        return None


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def escape_text(text):
    text = escape(text, quote=False)
    text = re.sub(r"([\\`*{}\[\]])", r"\\\1", text)
    # CommonMark treats underscores within words (e.g. SQL identifiers) as
    # literal text; underscores at word edges can introduce emphasis.
    text = re.sub(r"(?<!\w)_|_(?!\w)", r"\\_", text)
    # Escape block markers at line start: the punctuation of an ordered-list
    # marker ("1\\."), and the character itself for "#", ">", "+", "-".
    def block_marker(match):
        indent, marker = match.group(1), match.group(2)
        if marker[0].isdigit():
            return f"{indent}{marker[:-1]}\\{marker[-1]}"
        return f"{indent}\\{marker}"
    return re.sub(r"(?m)^(\s*)([#>+\-]|\d+[.)])(?=\s)", block_marker, text)


def link_url(href, base):
    # Check before urlsplit, which silently removes some control characters.
    if re.search(r"[\x00-\x1f\x7f]", href):
        return None
    try:
        if urlsplit(href.strip()).scheme.lower() not in {"", "http", "https", "mailto"}:
            return None
        url = urljoin(base, href.strip())
        if urlsplit(url).scheme.lower() not in {"http", "https", "mailto"}:
            return None
    except ValueError:
        return None
    # Parentheses, brackets, angle brackets, quotes and whitespace cannot break
    # out of the Markdown destination, even for otherwise permitted URLs.
    return quote(url, safe="/:#?&=@%+;,~!$*'-._")


def inline_children(node):
    for child in node.children:
        if isinstance(child, Node):
            if child.tag in {"a", "strong", "b", "em", "i", "code", "img"}:
                yield child
            yield from inline_children(child)


def source_links(node, lang):
    """Include navigation/footer anchors and anchors inside translated HTML."""
    if node.tag == "a" and node.attrs.get("href"):
        yield node
    if f"data-{lang}" in node.attrs:
        fragment = Parser()
        fragment.feed(node.attrs[f"data-{lang}"])
        yield from source_links(fragment.root, lang)
    for child in node.children:
        if isinstance(child, Node):
            yield from source_links(child, lang)


def literal(node, lang):
    if isinstance(node, str):
        return node
    if f"data-{lang}" in node.attrs:
        fragment = Parser()
        fragment.feed(node.attrs[f"data-{lang}"])
        return literal(fragment.root, lang)
    return "".join(literal(c, lang) for c in node.children)


def markdown(node, lang, base):
    if isinstance(node, str):
        return escape_text(node)
    attrs, tag = node.attrs, node.tag
    if tag in {"script", "style", "button"}:
        return ""
    if f"data-{lang}" in attrs:
        # Attributes can themselves contain inline HTML (the language switch does too).
        fragment = Parser()
        fragment.feed(attrs[f"data-{lang}"])
        content = markdown(fragment.root, lang, base)
        # Older source translations contain only the surrounding prose. Keep
        # child links absent from that prose, and retain inline formatting when
        # its localized label occurs in the translation. Never borrow EL copy
        # to fill a missing EN label.
        for child in inline_children(node):
            rendered = markdown(child, lang, base)
            if not rendered or rendered in content:
                continue
            label = escape_text(clean(literal(child, lang)))
            if child.tag == "a":
                url = link_url(child.attrs.get("href", ""), base)
                if url and f"]({url})" in content:
                    continue
            replaced = False
            if label and label in content:
                # Match prose/labels only; a source word may also occur in a
                # link destination, where inserting emphasis would break it.
                parts = re.split(r"(\]\([^)]*\))", content)
                for i in range(0, len(parts), 2):
                    if label in parts[i]:
                        parts[i] = parts[i].replace(label, rendered, 1)
                        replaced = True
                        break
                content = "".join(parts)
            if not replaced and child.tag == "a":
                content = content.rstrip() + " " + rendered
    else:
        content = "".join(markdown(c, lang, base) for c in node.children)
    if tag == "a":
        url = link_url(attrs["href"], base) if attrs.get("href") else None
        return f'[{clean(content)}]({url})' if url else content
    if tag in {"strong", "b"}:
        return f"**{clean(content)}**"
    if tag in {"em", "i"}:
        return f"*{clean(content)}*"
    if tag == "code":
        code = escape(clean(literal(node, lang)), quote=False)
        fence = "`" * (max((len(m[0]) for m in re.finditer(r"`+", code)), default=0) + 1)
        return f"{fence} {code} {fence}" if "`" in code else f"{fence}{code}{fence}"
    if tag == "br":
        return " "
    if tag == "img":
        return escape_text(attrs.get("alt", ""))
    if re.fullmatch(r"h[1-6]", tag):
        return f'\n\n{"#" * min(int(tag[1]) + 1, 6)} {clean(content)}\n\n'
    if tag == "li":
        return f"\n- {clean(content)}\n"
    if tag in {"td", "th"}:
        return clean(content).replace("|", r"\|")
    if tag == "tr":
        cells = [markdown(c, lang, base) for c in node.children if isinstance(c, Node) and c.tag in {"td", "th"}]
        return "| " + " | ".join(cells) + " |\n"
    if tag == "table":
        rows = content.strip().splitlines()
        rows = [row for row in rows if row.strip()]
        if rows:
            rows.insert(1, "| " + " | ".join("---" for _ in rows[0].strip("|").split("|")) + " |")
        return "\n\n" + "\n".join(row.strip() for row in rows) + "\n\n"
    classes = attrs.get("class", "").split()
    if tag == "pre" or "code-block" in classes:
        code = escape(literal(node, lang).strip(), quote=False)
        fence = "`" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"`+", code)), default=0))
        return f"\n\n{fence}text\n{code}\n{fence}\n\n"
    if "flow" in classes:
        return "\n\n" + clean(content) + "\n\n"
    if "fnode" in classes or "farr" in classes:
        return " " + clean(content) + " "
    if tag in {"p", "div", "section", "ul", "ol"}:
        return "\n\n" + content.strip() + "\n\n"
    return content


def render(source, slug):
    parser = Parser()
    parser.feed(source)
    layout = parser.root.find(lambda n: "layout" in n.attrs.get("class", "").split())
    title = parser.root.find(lambda n: n.tag == "h1")
    if layout is None or title is None:
        raise ValueError(f"{slug}: missing h1/layout")
    base = f"https://ekklesia.gr/wiki/{slug}.html"
    heading = " / ".join(dict.fromkeys(clean(markdown(title, lang, base)).lstrip("# ") for lang in ("el", "en")))
    output = (f"<!-- Generated by scripts/wiki_publish.py from docs/wiki/{slug}.html; edit the HTML source. -->\n"
              f"<!-- @ai-anchor WIKI_{slug.upper()} -->\n\n"
              f"# {heading}\n\n"
              f"[Δημοσιευμένη σελίδα / Published page]({base})\n")
    for lang, label in (("el", "Ελληνικά"), ("en", "English")):
        output += f"\n## {label}\n\n"
        article = markdown(layout, lang, base)
        output += article
        remaining = {}
        for link in source_links(parser.root, lang):
            url = link_url(link.attrs["href"], base)
            if url and f"]({url})" not in article:
                # Prefer a localized navigation label over an earlier logo
                # anchor that happens to point to the same page.
                if url not in remaining or f"data-{lang}" in link.attrs:
                    remaining[url] = link
        if remaining:
            label = "Σύνδεσμοι σελίδας" if lang == "el" else "Page links"
            output += f"\n\n### {label}\n\n" + "\n".join("- " + clean(markdown(link, lang, base)) for link in remaining.values()) + "\n"
    output = "\n".join(line.rstrip() for line in output.splitlines())
    return re.sub(r"\n{3,}", "\n\n", output).strip() + "\n"


def shared_pattern(key):
    return re.compile(r'<p\b[^>]*\bdata-wiki-fact="' + re.escape(key) + r'"[^>]*>.*?</p>', re.DOTALL)


def check(*, write=False, root=ROOT):
    errors = []
    canonical = (root / "docs/wiki/privacy.html").read_text(encoding="utf-8")
    for key, slugs in SHARED.items():
        pattern = shared_pattern(key)
        matches = pattern.findall(canonical)
        if len(matches) != 1:
            errors.append(f"privacy.html: expected one canonical {key}")
            continue
        for slug in slugs:
            path = root / f"docs/wiki/{slug}.html"
            source = path.read_text(encoding="utf-8")
            mirrors = pattern.findall(source)
            if len(mirrors) != 1:
                errors.append(f"{path.name}: missing/duplicated shared {key}")
            elif mirrors[0] != matches[0]:
                if write:
                    path.write_text(pattern.sub(lambda _: matches[0], source), encoding="utf-8")
                else:
                    errors.append(f"{path.name}: shared fact drift: {key}")
    for slug, name in PAGES.items():
        expected = render((root / f"docs/wiki/{slug}.html").read_text(encoding="utf-8"), slug)
        target = root / f"wiki/{name}.md"
        if write:
            target.write_text(expected, encoding="utf-8")
        elif not target.exists() or target.read_text(encoding="utf-8") != expected:
            errors.append(f"wiki/{name}.md: publication drift; run python3 scripts/wiki_publish.py --write")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors = check(write=args.write)
    print("\n".join(errors) if errors else "wiki publication ok: 4 EL/EN Markdown pages; shared identity/newsletter facts")
    raise SystemExit(bool(errors))
