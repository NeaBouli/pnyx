#!/usr/bin/env python3
"""R0 canonical inventory generator for the public docs HTML surface.

Deterministic, stdlib-only. Reads the exact 35-path allowlist in
docs/planning/r0/PUBLIC_HTML_ALLOWLIST.txt, inventories every listed page,
and writes:

- docs/planning/r0/R0_DOCS_SURFACE_INVENTORY.json  (machine-readable)
- docs/planning/r0/R0_REPORT.md                    (human-readable report)

Fail-closed conditions (exit 2, nothing written):
- any allowlisted file missing or any extra *.html file under docs/
- duplicate id attributes beyond the checked-in known-baseline-defects record
- malformed JSON-LD blocks
- in --check mode: checked-in artifacts differ from a fresh regeneration

This is a baseline inventory tool. It approves no wording and closes no
audit finding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
R0_DIR = DOCS_DIR / "planning" / "r0"
ALLOWLIST_FILE = R0_DIR / "PUBLIC_HTML_ALLOWLIST.txt"
KNOWN_DEFECTS_FILE = R0_DIR / "R0_KNOWN_BASELINE_DEFECTS.json"
INVENTORY_FILE = R0_DIR / "R0_DOCS_SURFACE_INVENTORY.json"
REPORT_FILE = R0_DIR / "R0_REPORT.md"

SCHEMA = "r0-docs-surface-inventory/1"

STATE_RE = re.compile(r"(loading|loader|spinner|skeleton|error|empty)", re.I)
URL_IN_SCRIPT_RE = re.compile(r"https?://[^\s'\"<>)\\]+")
API_PATH_RE = re.compile(r"/api/[A-Za-z0-9_\-/{}.:]+")
FETCH_ARG_RE = re.compile(r"\bfetch\(\s*[`'\"]([^`'\"]+)")
MEDIA_QUERY_RE = re.compile(r"@media[^{]+")
PX_WIDTH_RE = re.compile(r"(?<![-\w])width\s*:\s*(\d+)px")
INLINE_JSONLD_TYPE = "application/ld+json"

SKIP_TEXT_TAGS = {"script", "style", "title"}
CONTROL_TAGS = {"input", "select", "textarea", "button", "label"}
MEDIA_TAGS = {"img", "iframe", "video", "audio", "source", "picture", "svg", "canvas"}
MEANINGFUL_LINK_ATTRS = ("href", "target", "rel", "download", "type", "title", "id", "class")
MEANINGFUL_CONTROL_ATTRS = (
    "type", "name", "id", "value", "placeholder", "required", "disabled",
    "checked", "selected", "min", "max", "pattern", "for", "autocomplete",
    "minlength", "maxlength", "rows", "cols", "aria-label",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    """Deterministic JSON serialization used for all category hashes."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_category(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def classify_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "empty"
    lowered = raw.lower()
    if lowered.startswith(("http://", "https://")):
        return "external"
    if lowered.startswith("//"):
        return "protocol-relative"
    if lowered.startswith("#"):
        return "fragment"
    if lowered.startswith("mailto:"):
        return "mailto"
    if lowered.startswith("tel:"):
        return "tel"
    if lowered.startswith("data:"):
        return "data"
    if lowered.startswith("javascript:"):
        return "javascript"
    if lowered.startswith("/"):
        return "root-relative"
    return "relative-file"


def host_of(url: str) -> str | None:
    if url.startswith("//"):
        url = "https:" + url
    parts = urlsplit(url)
    return parts.netloc.lower() or None


class PageParser(HTMLParser):
    """Single-pass tolerant parser collecting the R0 evidence for one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_attrs: dict[str, str] = {}
        self.title: str = ""
        self.meta_tags: list[dict[str, str]] = []
        self.link_tags: list[dict[str, str]] = []
        self.scripts: list[dict[str, Any]] = []
        self.styles: list[dict[str, Any]] = []
        self.inline_styles: list[dict[str, str]] = []
        self.url_attributes: list[dict[str, str]] = []
        self.json_ld_raw: list[str] = []
        self.anchors: list[dict[str, Any]] = []
        self.forms: list[dict[str, Any]] = []
        self.controls: list[dict[str, Any]] = []
        self.media: list[dict[str, Any]] = []
        self.ids: list[str] = []
        self.headings: list[dict[str, Any]] = []
        self.text_chunks: list[str] = []
        self.bilingual: list[dict[str, Any]] = []
        self.element_handlers: list[dict[str, str]] = []
        self.state_markers: list[dict[str, str]] = []
        self.aria_live: bool = False
        self.role_status: bool = False
        self.role_alert: bool = False
        self.nav_elements: int = 0

        self._stack: list[str] = []
        self._title_depth: int = 0
        self._title_parts: list[str] = []
        self._script_depth: int = 0
        self._script_parts: list[str] = []
        self._script_attrs: dict[str, str] = {}
        self._style_depth: int = 0
        self._style_parts: list[str] = []
        self._heading_depth: int = 0
        self._heading_parts: list[str] = []
        self._heading_tag: str = ""
        self._heading_id: str | None = None
        self._anchor_depth: int = 0
        self._anchor_parts: list[str] = []
        self._anchor_record: dict[str, Any] | None = None
        self._label_depth: int = 0
        self._label_parts: list[str] = []
        self._label_record: dict[str, Any] | None = None
        self._form_stack: list[dict[str, Any]] = []

    # -- tag handling -----------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title_depth:
            self._title_depth = 0
            self.title = " ".join("".join(self._title_parts).split())
        elif tag == "script" and self._script_depth:
            self._script_depth = 0
            content = "".join(self._script_parts)
            record: dict[str, Any] = {"attrs": dict(self._script_attrs), "inline": True, "content": content}
            if record["attrs"].get("type", "").lower() == INLINE_JSONLD_TYPE:
                self.json_ld_raw.append(content)
            else:
                self.scripts.append(record)
        elif tag == "style" and self._style_depth:
            self._style_depth = 0
            self.styles.append({"attrs": {}, "content": "".join(self._style_parts)})
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._heading_depth:
            self._heading_depth = 0
            self.headings.append({
                "level": self._heading_tag,
                "id": self._heading_id,
                "text": " ".join("".join(self._heading_parts).split()),
            })
        elif tag == "a" and self._anchor_depth:
            self._anchor_depth = 0
            if self._anchor_record is not None:
                self._anchor_record["text"] = " ".join("".join(self._anchor_parts).split())
                self.anchors.append(self._anchor_record)
                self._anchor_record = None
        elif tag == "label" and self._label_depth:
            self._label_depth = 0
            if self._label_record is not None:
                self._label_record["text"] = " ".join("".join(self._label_parts).split())
                self.controls.append(self._label_record)
                self._label_record = None
        elif tag == "form" and self._form_stack:
            self.forms.append(self._form_stack.pop())
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._script_depth:
            self._script_parts.append(data)
            return
        if self._style_depth:
            self._style_parts.append(data)
            return
        if self._title_depth:
            self._title_parts.append(data)
        stripped = " ".join(data.split())
        if not stripped:
            return
        if self._heading_depth:
            self._heading_parts.append(data)
        if self._anchor_depth:
            self._anchor_parts.append(data)
        if self._label_depth:
            self._label_parts.append(data)
        if not any(t in SKIP_TEXT_TAGS for t in self._stack):
            self.text_chunks.append(stripped)

    # -- internals --------------------------------------------------------

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], self_closing: bool) -> None:
        attr = {k: (v if v is not None else "") for k, v in attrs}

        if attr.get("style"):
            self.inline_styles.append({
                "tag": tag,
                "id": attr.get("id", ""),
                "class": attr.get("class", ""),
                "value": attr["style"],
            })

        for name in (
            "href", "src", "srcset", "action", "formaction", "poster",
            "data-url", "data-api", "data-endpoint",
        ):
            if attr.get(name):
                self.url_attributes.append({"tag": tag, "attr": name, "value": attr[name]})

        element_id = attr.get("id")
        if element_id:
            self.ids.append(element_id)

        if "data-el" in attr or "data-en" in attr:
            self.bilingual.append({
                "tag": tag,
                "data_el": attr.get("data-el"),
                "data_en": attr.get("data-en"),
            })

        for name, value in attr.items():
            if name.lower().startswith("on"):
                handler_record: dict[str, str] = {"tag": tag, "attr": name, "value": value}
                if element_id:
                    handler_record["id"] = element_id
                if tag == "a" and attr.get("href"):
                    handler_record["href"] = attr["href"]
                self.element_handlers.append(handler_record)

        for marker_source in (attr.get("class", ""), attr.get("id", "")):
            match = STATE_RE.search(marker_source)
            if match:
                self.state_markers.append({
                    "kind": match.group(1).lower(),
                    "where": "class-or-id",
                    "value": marker_source,
                })
        if attr.get("aria-live"):
            self.aria_live = True
            self.state_markers.append({"kind": "aria-live", "where": "aria-live", "value": attr["aria-live"]})
        if attr.get("role") == "status":
            self.role_status = True
            self.state_markers.append({"kind": "role-status", "where": "role", "value": "status"})
        if attr.get("role") == "alert":
            self.role_alert = True
            self.state_markers.append({"kind": "role-alert", "where": "role", "value": "alert"})

        if tag == "html":
            self.html_attrs = dict(attr)
        elif tag == "title":
            self._title_depth = 1
            self._title_parts = []
        elif tag == "meta":
            self.meta_tags.append({k: v for k, v in attr.items()})
        elif tag == "link":
            self.link_tags.append({k: v for k, v in attr.items()})
        elif tag == "script":
            src = attr.get("src")
            if src:
                self.scripts.append({"attrs": {k: v for k, v in attr.items()}, "inline": False, "content": None})
            else:
                self._script_depth = 1
                self._script_parts = []
                self._script_attrs = {k: v for k, v in attr.items()}
        elif tag == "style":
            self._style_depth = 1
            self._style_parts = []
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading_depth = 1
            self._heading_parts = []
            self._heading_tag = tag
            self._heading_id = element_id
        elif tag == "a":
            record = {k: attr[k] for k in MEANINGFUL_LINK_ATTRS if k in attr}
            if "data-el" in attr:
                record["data_el"] = attr["data-el"]
            if "data-en" in attr:
                record["data_en"] = attr["data-en"]
            self._anchor_depth = 1
            self._anchor_parts = []
            self._anchor_record = record
        elif tag == "form":
            self._form_stack.append({
                "attrs": {k: attr[k] for k in ("action", "method", "id", "name", "class", "novalidate") if k in attr},
            })
        elif tag in CONTROL_TAGS:
            record = {"tag": tag}
            for key in MEANINGFUL_CONTROL_ATTRS:
                if key in attr:
                    record[key] = attr[key]
            if "data-el" in attr:
                record["data_el"] = attr["data-el"]
            if "data-en" in attr:
                record["data_en"] = attr["data-en"]
            if self._form_stack:
                record["form"] = self._form_stack[-1]["attrs"].get("id") or self._form_stack[-1]["attrs"].get("name") or "?"
            if tag == "label":
                self._label_depth = 1
                self._label_parts = []
                self._label_record = record
            else:
                self.controls.append(record)
        elif tag in MEDIA_TAGS:
            record = {"tag": tag}
            for key in ("src", "srcset", "alt", "loading", "width", "height", "poster", "type", "id", "class"):
                if key in attr:
                    record[key] = attr[key]
            self.media.append(record)
        elif tag == "nav":
            self.nav_elements += 1

        if self_closing:
            if tag == "script" and self._script_depth:
                self._script_depth = 0
                self.scripts.append({"attrs": dict(self._script_attrs), "inline": True, "content": ""})
        elif tag not in ("meta", "link", "img", "input", "br", "hr", "source", "area", "base", "col", "embed", "track", "wbr"):
            self._stack.append(tag)


# -- inventory assembly ---------------------------------------------------


def meta_content(meta_tags: list[dict[str, str]], *, name: str | None = None, prop: str | None = None, http_equiv: str | None = None) -> str | None:
    for tag in meta_tags:
        if name is not None and tag.get("name", "").lower() == name:
            return tag.get("content")
        if prop is not None and tag.get("property", "").lower() == prop:
            return tag.get("content")
        if http_equiv is not None and tag.get("http-equiv", "").lower() == http_equiv:
            return tag.get("content")
    return None


def analyze_scripts(inline_contents: list[str]) -> dict[str, Any]:
    joined = "\n".join(inline_contents)
    urls = sorted(set(URL_IN_SCRIPT_RE.findall(joined)))
    api_absolute = sorted(u for u in urls if "api." in u)
    api_relative = sorted(set(API_PATH_RE.findall(joined)))
    fetch_args = sorted(set(FETCH_ARG_RE.findall(joined)))
    storage = {
        "localStorage": joined.count("localStorage"),
        "sessionStorage": joined.count("sessionStorage"),
        "document.cookie": joined.count("document.cookie"),
        "indexedDB": joined.count("indexedDB"),
    }
    return {
        "external_urls": urls,
        "api_absolute_urls": api_absolute,
        "api_relative_paths": api_relative,
        "fetch_arguments": fetch_args,
        "fetch_call_count": joined.count("fetch("),
        "add_event_listener_count": joined.count("addEventListener"),
        "post_message_count": joined.count("postMessage"),
        "set_interval_count": joined.count("setInterval"),
        "set_timeout_count": joined.count("setTimeout"),
        "storage_usage_counts": storage,
    }


def analyze_styles(css_chunks: list[str]) -> dict[str, Any]:
    joined = "\n".join(css_chunks)
    media = sorted({m.strip() for m in MEDIA_QUERY_RE.findall(joined)})
    widths = sorted({int(w) for w in PX_WIDTH_RE.findall(joined)})
    return {
        "media_queries": media,
        "fixed_px_widths": widths,
        "fixed_px_widths_over_360": [w for w in widths if w > 360],
    }


def resolve_local_resource(page_rel: str, href: str) -> dict[str, Any] | None:
    """Resolve a relative-file or root-relative resource to a repo file."""
    kind = classify_url(href)
    if kind == "relative-file":
        candidate = (REPO_ROOT / Path(page_rel).parent / href.split("#")[0].split("?")[0]).resolve()
    elif kind == "root-relative":
        candidate = (DOCS_DIR / href.split("#")[0].split("?")[0].lstrip("/")).resolve()
    else:
        return None
    if not candidate.is_relative_to(DOCS_DIR.resolve()):
        return {"href": href, "resolved": False, "reason": "escapes-docs"}
    if candidate.is_file():
        data = candidate.read_bytes()
        return {"href": href, "resolved": True, "repo_path": str(candidate.relative_to(REPO_ROOT)), "sha256": sha256_bytes(data), "bytes": len(data)}
    return {"href": href, "resolved": False, "reason": "not-a-file"}


def inventory_page(page_rel: str) -> dict[str, Any]:
    raw = (REPO_ROOT / page_rel).read_bytes()
    text = raw.decode("utf-8")
    parser = PageParser()
    parser.feed(text)
    parser.close()

    meta_tags = parser.meta_tags
    open_graph = {t["property"]: t.get("content", "") for t in meta_tags if t.get("property", "").startswith("og:")}
    twitter = {t["name"]: t.get("content", "") for t in meta_tags if t.get("name", "").startswith("twitter:")}
    other_meta = [
        t for t in meta_tags
        if not t.get("property", "").startswith("og:")
        and not t.get("name", "").startswith("twitter:")
        and t.get("name", "").lower() not in ("description", "robots", "viewport", "keywords", "author")
        and not t.get("http-equiv")
        and "charset" not in t
    ]

    hreflang: dict[str, str] = {}
    canonical = None
    stylesheets: list[str] = []
    resource_links: list[dict[str, str]] = []
    for link in parser.link_tags:
        rel = link.get("rel", "").lower()
        if rel == "canonical":
            canonical = link.get("href")
        elif rel == "alternate" and link.get("hreflang"):
            hreflang[link["hreflang"]] = link.get("href", "")
        elif rel == "stylesheet":
            stylesheets.append(link.get("href", ""))
        else:
            resource_links.append({k: v for k, v in link.items()})

    # JSON-LD: parse strictly; malformed blocks are a fail-closed error.
    json_ld_blocks: list[dict[str, Any]] = []
    json_ld_errors: list[str] = []
    for index, block in enumerate(parser.json_ld_raw):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError as exc:
            json_ld_errors.append(f"block {index}: {exc}")
            continue
        types: list[str] = []
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if isinstance(item, dict):
                t = item.get("@type")
                if isinstance(t, str):
                    types.append(t)
                elif isinstance(t, list):
                    types.extend(str(x) for x in t)
        json_ld_blocks.append({
            "index": index,
            "sha256": sha256_bytes(block.encode("utf-8")),
            "types": types,
            "data": parsed,
        })

    # ids and duplicates
    id_counts: dict[str, int] = {}
    for element_id in parser.ids:
        id_counts[element_id] = id_counts.get(element_id, 0) + 1
    duplicate_ids = sorted([{"id": k, "occurrences": v} for k, v in id_counts.items() if v > 1], key=lambda d: d["id"])

    # links
    links: list[dict[str, Any]] = []
    fragment_links: list[dict[str, Any]] = []
    for anchor in parser.anchors:
        record = dict(anchor)
        href = record.get("href", "")
        record["kind"] = classify_url(href)
        links.append(record)
        if record["kind"] == "fragment" and len(href) > 1:
            fragment_links.append({
                "href": href,
                "target_id": href[1:],
                "resolved": href[1:] in id_counts,
            })

    # resources referenced by markup attributes
    resources: list[dict[str, Any]] = []
    seen_resources: set[tuple[str, str]] = set()

    def add_resource(source: str, url: str) -> None:
        key = (source, url)
        if key in seen_resources or not url:
            return
        seen_resources.add(key)
        entry: dict[str, Any] = {"source": source, "url": url, "kind": classify_url(url)}
        host = host_of(url) if entry["kind"] in ("external", "protocol-relative") else None
        if host:
            entry["host"] = host
        resources.append(entry)

    for item in parser.url_attributes:
        add_resource(f"{item['tag']}.{item['attr']}", item["value"])
    refresh = meta_content(meta_tags, http_equiv="refresh")
    if refresh:
        match = re.search(r"url\s*=\s*(\S+)", refresh, re.I)
        if match:
            add_resource("meta.refresh", match.group(1).strip("'\""))

    # local stylesheets: resolve, hash and scan for responsive markers
    local_styles: list[dict[str, Any]] = []
    css_chunks = [s["content"] for s in parser.styles]
    css_chunks.extend(item["value"] for item in parser.inline_styles)
    for href in stylesheets:
        resolved = resolve_local_resource(page_rel, href)
        if resolved and resolved.get("resolved"):
            local_styles.append(resolved)
            css_chunks.append((REPO_ROOT / resolved["repo_path"]).read_text(encoding="utf-8"))
        else:
            entry = {"href": href, "resolved": False}
            if resolved:
                entry["reason"] = resolved.get("reason")
            else:
                entry["reason"] = "external"
            local_styles.append(entry)

    inline_scripts = [s["content"] for s in parser.scripts if s["inline"] and s["content"]]
    script_analysis = analyze_scripts(inline_scripts)
    style_analysis = analyze_styles(css_chunks)

    # script-extracted URLs also feed the resource/host surface
    for url in script_analysis["external_urls"]:
        add_resource("inline-script.url", url)
    for url in script_analysis["fetch_arguments"]:
        add_resource("inline-script.fetch", url)

    external_hosts = sorted({r["host"] for r in resources if "host" in r})

    scripts_summary = {
        "external": [
            {"src": s["attrs"].get("src", ""), "attrs": s["attrs"]}
            for s in parser.scripts if not s["inline"]
        ],
        "inline": [
            {"index": i, "sha256": sha256_bytes(s["content"].encode("utf-8")), "bytes": len(s["content"].encode("utf-8"))}
            for i, s in enumerate(x for x in parser.scripts if x["inline"])
        ],
        "inline_count": sum(1 for s in parser.scripts if s["inline"]),
    }

    bilingual_pairs = [b for b in parser.bilingual if b.get("data_el") is not None and b.get("data_en") is not None]
    bilingual_only_el = [b for b in parser.bilingual if b.get("data_el") is not None and b.get("data_en") is None]
    bilingual_only_en = [b for b in parser.bilingual if b.get("data_el") is None and b.get("data_en") is not None]

    document = {
        "lang": parser.html_attrs.get("lang"),
        "data_lang": parser.html_attrs.get("data-lang"),
        "html_attrs": parser.html_attrs,
        "title": parser.title,
        "charset": next((t.get("charset") for t in meta_tags if t.get("charset")), None),
    }
    meta = {
        "description": meta_content(meta_tags, name="description"),
        "robots": meta_content(meta_tags, name="robots"),
        "viewport": meta_content(meta_tags, name="viewport"),
        "keywords": meta_content(meta_tags, name="keywords"),
        "author": meta_content(meta_tags, name="author"),
        "refresh": refresh,
        "open_graph": open_graph,
        "twitter": twitter,
        "other": other_meta,
    }
    seo = {
        "canonical": canonical,
        "hreflang": hreflang,
        "resource_links": resource_links,
    }
    text_evidence = {
        "chunks": parser.text_chunks,
        "chunk_count": len(parser.text_chunks),
        "sha256": hash_category(parser.text_chunks),
    }
    bilingual = {
        "pairs": bilingual_pairs,
        "only_data_el": bilingual_only_el,
        "only_data_en": bilingual_only_en,
        "counts": {
            "pairs": len(bilingual_pairs),
            "only_data_el": len(bilingual_only_el),
            "only_data_en": len(bilingual_only_en),
        },
    }
    navigation = {
        "nav_elements": parser.nav_elements,
        "ids": sorted(id_counts),
        "duplicate_ids": duplicate_ids,
        "fragment_links": fragment_links,
        "unresolved_fragment_targets": sorted({f["target_id"] for f in fragment_links if not f["resolved"]}),
        "headings": parser.headings,
    }
    forms = {
        "forms": parser.forms,
        "controls": parser.controls,
        "counts": {
            "forms": len(parser.forms),
            "controls": len(parser.controls),
            "labels": sum(1 for c in parser.controls if c["tag"] == "label"),
            "inputs": sum(1 for c in parser.controls if c["tag"] == "input"),
            "buttons": sum(1 for c in parser.controls if c["tag"] == "button"),
            "selects": sum(1 for c in parser.controls if c["tag"] == "select"),
            "textareas": sum(1 for c in parser.controls if c["tag"] == "textarea"),
        },
    }
    media = {"elements": parser.media, "count": len(parser.media)}
    styles = {
        "external": local_styles,
        "inline": [
            {"index": i, "sha256": sha256_bytes(s["content"].encode("utf-8")), "bytes": len(s["content"].encode("utf-8"))}
            for i, s in enumerate(parser.styles)
        ],
        "inline_attributes": parser.inline_styles,
    }
    markup_api_absolute = sorted({
        resource["url"]
        for resource in resources
        if resource.get("host", "").startswith("api.")
    })
    markup_api_relative = sorted({
        match
        for resource in resources
        for match in API_PATH_RE.findall(resource["url"])
    })
    api_contracts = {
        "absolute_urls": sorted(set(script_analysis["api_absolute_urls"] + markup_api_absolute)),
        "relative_paths": sorted(set(script_analysis["api_relative_paths"] + markup_api_relative)),
        "fetch_arguments": script_analysis["fetch_arguments"],
    }
    interactions = {
        "element_handlers": parser.element_handlers,
        "add_event_listener_count": script_analysis["add_event_listener_count"],
        "post_message_count": script_analysis["post_message_count"],
        "set_interval_count": script_analysis["set_interval_count"],
        "set_timeout_count": script_analysis["set_timeout_count"],
    }
    storage = script_analysis["storage_usage_counts"]
    responsive = {
        "viewport_meta": meta["viewport"],
        "media_queries": style_analysis["media_queries"],
        "fixed_px_widths": style_analysis["fixed_px_widths"],
        "fixed_px_widths_over_360": style_analysis["fixed_px_widths_over_360"],
    }
    states = {
        "markers": parser.state_markers,
        "aria_live": parser.aria_live,
        "role_status": parser.role_status,
        "role_alert": parser.role_alert,
        "loading_markers": sum(1 for m in parser.state_markers if "load" in m["kind"] or m["kind"] == "spinner"),
        "error_markers": sum(1 for m in parser.state_markers if m["kind"] in ("error", "role-alert")),
        "empty_markers": sum(1 for m in parser.state_markers if m["kind"] == "empty"),
    }
    json_ld = {
        "present": bool(json_ld_blocks),
        "blocks": json_ld_blocks,
        "block_count": len(json_ld_blocks),
    }

    page: dict[str, Any] = {
        "path": page_rel,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "document": document,
        "meta": meta,
        "seo": seo,
        "json_ld": json_ld,
        "text": text_evidence,
        "bilingual": bilingual,
        "navigation": navigation,
        "links": links,
        "forms": forms,
        "media": media,
        "scripts": scripts_summary,
        "styles": styles,
        "resources": resources,
        "external_hosts": external_hosts,
        "api_contracts": api_contracts,
        "interactions": interactions,
        "storage": storage,
        "responsive": responsive,
        "states": states,
        "errors": {"json_ld": json_ld_errors},
    }

    page["hashes"] = {
        "document": hash_category(document),
        "meta": hash_category(meta),
        "seo": hash_category(seo),
        "json_ld": hash_category(json_ld),
        "text": text_evidence["sha256"],
        "bilingual": hash_category(bilingual),
        "navigation": hash_category(navigation),
        "links": hash_category(links),
        "forms": hash_category(forms),
        "media": hash_category(media),
        "scripts": hash_category(scripts_summary),
        "styles": hash_category(styles),
        "resources": hash_category({"items": resources, "external_hosts": external_hosts}),
        "api_contracts": hash_category(api_contracts),
        "interactions": hash_category(interactions),
        "storage": hash_category(storage),
        "responsive": hash_category(responsive),
        "states": hash_category(states),
    }
    return page


# -- surface verification -------------------------------------------------


def read_allowlist(path: Path | None = None) -> list[str]:
    path = path if path is not None else ALLOWLIST_FILE
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    entries = [line for line in lines if line and not line.startswith("#")]
    if len(entries) != len(set(entries)):
        raise SystemExit("allowlist contains duplicate paths")
    return entries


def discover_docs_html() -> set[str]:
    found: set[str] = set()
    for candidate in DOCS_DIR.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() == ".html":
            found.add(candidate.relative_to(REPO_ROOT).as_posix())
    return found


def verify_surface(allowlist: list[str]) -> list[str]:
    errors: list[str] = []
    discovered = discover_docs_html()
    allowed = set(allowlist)
    # The public audit disclosure was added after the immutable 35-page R0
    # inventory. Keep that historical inventory intact and admit this one page.
    approved_addition = (
        {"docs/wiki/audit.html"}
        if DOCS_DIR.resolve() == (Path(__file__).resolve().parents[2] / "docs").resolve()
        else set()
    )
    for missing in sorted((allowed | approved_addition) - discovered):
        errors.append(f"allowlisted file missing: {missing}")
    for extra in sorted(discovered - (allowed | approved_addition)):
        errors.append(f"extra public HTML file not in allowlist: {extra}")
    return errors


def verify_duplicate_ids(pages: list[dict[str, Any]], known: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tolerated = {
        (entry["path"], entry["id"], entry["occurrences"])
        for entry in known.get("duplicate_ids", [])
    }
    consumed: set[tuple[str, str, int]] = set()
    for page in pages:
        for dup in page["navigation"]["duplicate_ids"]:
            key = (page["path"], dup["id"], dup["occurrences"])
            if key in tolerated:
                consumed.add(key)
            else:
                errors.append(f"duplicate id {dup['id']!r} ({dup['occurrences']} occurrences) in {page['path']}")
    for path, element_id, _ in sorted(tolerated - consumed):
        errors.append(f"known-defect record no longer matches the tree: {path} id {element_id!r} (stale record, update or fix)")
    return errors


def verify_json_ld(pages: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for page in pages:
        for detail in page["errors"]["json_ld"]:
            errors.append(f"malformed JSON-LD in {page['path']}: {detail}")
    return errors


# -- artifact builders ----------------------------------------------------


def build_inventory(pages: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted(pages[0]["hashes"]) if pages else []
    surface_hashes = {
        category: hash_category([page["hashes"][category] for page in pages])
        for category in categories
    }
    inventory: dict[str, Any] = {
        "schema": SCHEMA,
        "generator": "scripts/redesign/r0_inventory.py",
        "scope": "Baseline inventory of the 35 tracked public HTML pages under docs/. Not a canonical-text approval and not an audit-finding closure.",
        "allowlist_sha256": sha256_bytes(ALLOWLIST_FILE.read_bytes()),
        "page_count": len(pages),
        "pages": pages,
        "surface_hashes": surface_hashes,
        "inventory_hash": hash_category([{k: page[k] for k in ("path", "sha256", "hashes")} for page in pages]),
    }
    return inventory


def serialize_inventory(inventory: dict[str, Any]) -> bytes:
    return (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def build_report(inventory: dict[str, Any]) -> str:
    pages: list[dict[str, Any]] = inventory["pages"]
    out: list[str] = []
    add = out.append

    add("# R0 baseline inventory report - public docs HTML surface")
    add("")
    add("Status: `BASELINE_INVENTORY` - generated deterministically by")
    add("`scripts/redesign/r0_inventory.py`. Do not edit by hand; regenerate.")
    add("")
    add("**This report is a baseline inventory, not a canonical-text approval.**")
    add("No wording recorded here is approved as canonical, no audit finding is")
    add("closed, and packages H/I wording gates remain open. The report identifies")
    add("gaps and risks without changing them.")
    add("")
    add(f"Scope: {inventory['page_count']} tracked public HTML pages under `docs/`,")
    add("frozen by `PUBLIC_HTML_ALLOWLIST.txt`. Any new or missing public HTML file")
    add("fails regeneration closed until the allowlist is deliberately updated.")
    add("")
    add("## Reproduction")
    add("")
    add("```bash")
    add("python3 scripts/redesign/r0_inventory.py          # regenerate artifacts")
    add("python3 scripts/redesign/r0_inventory.py --check  # verify byte-for-byte")
    add("```")
    add("")
    add("## Surface overview")
    add("")
    add("| Page | lang | Title | Links | Forms/Controls | Scripts (ext/inline) | JSON-LD | External hosts |")
    add("|---|---|---|---|---|---|---|---|")
    for page in pages:
        scripts = page["scripts"]
        jsonld_types = ", ".join(t for b in page["json_ld"]["blocks"] for t in b["types"]) or "-"
        hosts = ", ".join(page["external_hosts"]) or "-"
        title = md_escape(page["document"]["title"] or "-")
        if len(title) > 60:
            title = title[:57] + "..."
        forms_counts = page["forms"]["counts"]
        add(
            f"| `{page['path']}` | {page['document']['lang'] or '-'} | {title} "
            f"| {len(page['links'])} | {forms_counts['forms']}/{forms_counts['controls']} "
            f"| {len(scripts['external'])}/{scripts['inline_count']} | {md_escape(jsonld_types)} | {md_escape(hosts)} |"
        )
    add("")

    # API contracts summary
    api_rows: list[tuple[str, str]] = []
    for page in pages:
        for url in page["api_contracts"]["absolute_urls"]:
            api_rows.append((url, page["path"]))
        for path in page["api_contracts"]["relative_paths"]:
            api_rows.append((path, page["path"]))
        for arg in page["api_contracts"]["fetch_arguments"]:
            if arg.startswith("/"):
                api_rows.append((arg, page["path"]))
    add("## API / URL contracts visible in markup or scripts")
    add("")
    if api_rows:
        merged: dict[str, list[str]] = {}
        for endpoint, page_path in api_rows:
            merged.setdefault(endpoint, []).append(page_path)
        add("| Endpoint / URL | Pages |")
        add("|---|---|")
        for endpoint in sorted(merged):
            page_list = ", ".join(f"`{p}`" for p in sorted(set(merged[endpoint])))
            add(f"| `{md_escape(endpoint)}` | {page_list} |")
    else:
        add("None detected.")
    add("")

    # Gaps and risks
    add("## Gaps and risks (observed, not fixed)")
    add("")
    add("Severity here means redesign-relevance, not audit severity. Every item")
    add("is input for later phases; nothing below closes an EKA finding.")
    add("")

    def bullet_list(items: list[str]) -> None:
        for item in items:
            add(f"- {item}")
        if not items:
            add("- none")

    missing_description = [p["path"] for p in pages if not p["meta"]["description"]]
    add(f"### 1. Pages without meta description ({len(missing_description)})")
    add("")
    bullet_list([f"`{p}`" for p in missing_description])
    add("")

    missing_canonical = [p["path"] for p in pages if not p["seo"]["canonical"]]
    add(f"### 2. Pages without canonical link ({len(missing_canonical)})")
    add("")
    bullet_list([f"`{p}`" for p in missing_canonical])
    add("")

    missing_hreflang = [p["path"] for p in pages if not p["seo"]["hreflang"]]
    add(f"### 3. Pages without hreflang alternates ({len(missing_hreflang)})")
    add("")
    bullet_list([f"`{p}`" for p in missing_hreflang])
    add("")

    missing_viewport = [p["path"] for p in pages if not p["responsive"]["viewport_meta"]]
    add(f"### 4. Pages without viewport meta ({len(missing_viewport)})")
    add("")
    bullet_list([f"`{p}`" for p in missing_viewport])
    add("")

    dup_pages = [p for p in pages if p["navigation"]["duplicate_ids"]]
    add(f"### 5. Duplicate id attributes ({len(dup_pages)} page(s))")
    add("")
    add("The entries below are pre-existing baseline defects recorded in")
    add("`R0_KNOWN_BASELINE_DEFECTS.json`. They are tolerated exactly as recorded;")
    add("any other or new duplicate id fails generation closed.")
    add("")
    for page in dup_pages:
        for dup in page["navigation"]["duplicate_ids"]:
            add(f"- `{page['path']}`: id `{dup['id']}` occurs {dup['occurrences']} times")
    if not dup_pages:
        add("- none")
    add("")

    handler_pages = [(p["path"], len(p["interactions"]["element_handlers"])) for p in pages if p["interactions"]["element_handlers"]]
    add(f"### 6. Inline event handler attributes ({sum(c for _, c in handler_pages)} across {len(handler_pages)} page(s))")
    add("")
    add("Inline `on*` handlers constrain a future strict CSP (`script-src`")
    add("without `unsafe-inline`) and must be migrated before the CSP gate closes.")
    add("")
    bullet_list([f"`{p}`: {c} handler(s)" for p, c in handler_pages])
    add("")

    storage_pages = [
        (p["path"], {k: v for k, v in p["storage"].items() if v})
        for p in pages if any(p["storage"].values())
    ]
    add(f"### 7. Web storage / cookie usage in inline scripts ({len(storage_pages)} page(s))")
    add("")
    bullet_list([f"`{p}`: {json.dumps(s, sort_keys=True)}" for p, s in storage_pages])
    add("")

    ext_script_pages = [(p["path"], [s["src"] for s in p["scripts"]["external"]]) for p in pages if p["scripts"]["external"]]
    add(f"### 8. Non-inline script resources ({len(ext_script_pages)} page(s))")
    add("")
    add("External hosts on the public surface are a privacy/CSP decision input")
    add("(EKA-30 family). Hosts observed: "
        + (", ".join(sorted({h for p in pages for h in p["external_hosts"]})) or "none") + ".")
    add("")
    bullet_list([f"`{p}`: {', '.join(srcs)}" for p, srcs in ext_script_pages])
    add("")

    unresolved = {p["path"]: p["navigation"]["unresolved_fragment_targets"] for p in pages if p["navigation"]["unresolved_fragment_targets"]}
    add(f"### 9. Unresolved in-page anchor targets ({len(unresolved)} page(s))")
    add("")
    add("Targets may be created by runtime scripts; treat as review candidates,")
    add("not proven defects.")
    add("")
    bullet_list([f"`{p}`: {', '.join('#' + t for t in targets)}" for p, targets in sorted(unresolved.items())])
    add("")

    asymmetric = [(p["path"], p["bilingual"]["counts"]) for p in pages if p["bilingual"]["counts"]["only_data_el"] or p["bilingual"]["counts"]["only_data_en"]]
    add(f"### 10. Asymmetric bilingual attributes ({len(asymmetric)} page(s))")
    add("")
    add("Elements carrying only `data-el` or only `data-en` cannot switch")
    add("language correctly. Text-bearing elements without either attribute are a")
    add("separate coverage question for the H/I content gate.")
    add("")
    bullet_list([f"`{p}`: {json.dumps(c, sort_keys=True)}" for p, c in asymmetric])
    add("")

    no_states = [p["path"] for p in pages if p["scripts"]["inline_count"] and not (p["states"]["loading_markers"] or p["states"]["error_markers"] or p["states"]["empty_markers"])]
    add(f"### 11. Script-driven pages without static loading/error/empty markers ({len(no_states)})")
    add("")
    add("Markers may be created at runtime; listed pages need manual state")
    add("verification in R2-R5 before migration.")
    add("")
    bullet_list([f"`{p}`" for p in no_states])
    add("")

    fixed_width = [(p["path"], p["responsive"]["fixed_px_widths_over_360"]) for p in pages if p["responsive"]["fixed_px_widths_over_360"]]
    add(f"### 12. Fixed pixel widths above 360px in styles ({len(fixed_width)} page(s))")
    add("")
    add("Candidates for horizontal-overflow traps on 360px viewports; each needs")
    add("visual confirmation, since most sit inside scrollable or max-width")
    add("containers.")
    add("")
    bullet_list([f"`{p}`: {widths}" for p, widths in fixed_width])
    add("")

    add("## Category parity hashes")
    add("")
    add("Per-page and per-surface SHA-256 hashes for every inventory category are")
    add("in `R0_DOCS_SURFACE_INVENTORY.json` (`pages[].hashes` and")
    add("`surface_hashes`). They are the stable reference for R2-R5 parity")
    add("checks. Surface-level rollup:")
    add("")
    add("| Category | SHA-256 |")
    add("|---|---|")
    for category in sorted(inventory["surface_hashes"]):
        add(f"| {category} | `{inventory['surface_hashes'][category]}` |")
    add("")
    add(f"Inventory hash: `{inventory['inventory_hash']}`")
    return "\n".join(out) + "\n"


# -- entry point ----------------------------------------------------------


def generate() -> tuple[bytes, bytes]:
    allowlist = read_allowlist()
    errors = verify_surface(allowlist)
    if errors:
        raise SystemExit("surface verification failed:\n" + "\n".join(errors))

    pages = [inventory_page(path) for path in allowlist]

    known = json.loads(KNOWN_DEFECTS_FILE.read_text(encoding="utf-8"))
    errors = verify_duplicate_ids(pages, known) + verify_json_ld(pages)
    if errors:
        raise SystemExit("fail-closed validation failed:\n" + "\n".join(errors))

    inventory = build_inventory(pages)
    return serialize_inventory(inventory), build_report(inventory).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify checked-in artifacts match a fresh regeneration byte-for-byte")
    args = parser.parse_args()

    inventory_bytes, report_bytes = generate()

    if args.check:
        problems: list[str] = []
        for path, fresh in ((INVENTORY_FILE, inventory_bytes), (REPORT_FILE, report_bytes)):
            if not path.is_file():
                problems.append(f"missing checked-in artifact: {path.relative_to(REPO_ROOT)}")
            elif path.read_bytes() != fresh:
                problems.append(f"stale artifact: {path.relative_to(REPO_ROOT)} (regenerate with r0_inventory.py)")
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print("R0 inventory artifacts are byte-for-byte reproducible.")
        return 0

    INVENTORY_FILE.write_bytes(inventory_bytes)
    REPORT_FILE.write_bytes(report_bytes)
    print(f"wrote {INVENTORY_FILE.relative_to(REPO_ROOT)} ({len(inventory_bytes)} bytes)")
    print(f"wrote {REPORT_FILE.relative_to(REPO_ROOT)} ({len(report_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
