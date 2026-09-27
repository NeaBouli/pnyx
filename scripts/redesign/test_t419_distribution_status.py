#!/usr/bin/env python3
"""T-419 / EKA-38 + EKA-51 (download scope): distribution-status coherence.

Offline regression over every public download link and status source. The
single source for the Direct Android release is docs/download/APK_MANIFEST.md;
every version, versionCode and GitHub asset URL on a public surface must match
it. F-Droid is an independent build cycle, so public surfaces state availability
without pinning a version. The ekprosopos APK is not published, so nothing may
link it while the manifest says so.

Run with:
    cd scripts/redesign && python3 -m unittest test_t419_distribution_status.py
"""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
MANIFEST = DOCS_DIR / "download" / "APK_MANIFEST.md"

# Public surfaces that carry download links or distribution status.
SURFACES = (
    "index.html",
    "representative.html",
    "sso-verify.html",
    "llms.txt",
    "wiki/faq.html",
    "wiki/roadmap.html",
)

FDROID_URL = "https://f-droid.org/packages/ekklesia.gr/"
PLAY_TESTING_URL = "https://play.google.com/apps/testing/ekklesia.gr"
DISCOURSE_HUB_IOS_URL = "https://apps.apple.com/app/discourse-hub/id1173672076"
EKPROSOPOS_APK = "ekprosopos-latest.apk"
EKPROSOPOS_CHECKSUM = DOCS_DIR / "download" / f"{EKPROSOPOS_APK}.sha256"

# Wording that marks F-Droid as not yet live or lagging by default.
FDROID_STALE_PATTERNS = (
    r"F-Droid[^.;]{0,80}\bpending\b",
    r"F-Droid[^.;]{0,80}remain",
    r"older version",
    r"παλαιότερη έκδοση",
)


def _read(rel: str) -> str:
    return (DOCS_DIR / rel).read_text(encoding="utf-8")


def _manifest_field(text: str, field: str) -> str:
    match = re.search(rf"^\| {re.escape(field)} \| (.+?) \|$", text, re.MULTILINE)
    if not match:
        raise AssertionError(f"APK_MANIFEST.md lacks field {field!r}")
    return match.group(1).strip()


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.cards: list[dict[str, object]] = []
        self._card_depth = 0
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"] or "")
        if tag in ("br", "img", "path", "input", "meta", "link"):
            return
        self._depth += 1
        classes = (a.get("class") or "").split()
        if "download-channel-card" in classes and not self._card_depth:
            self._card_depth = self._depth
            self.cards.append({"tag": tag, "href": a.get("href"), "fills": [], "text": []})
        elif self._card_depth and tag == "svg":
            self.cards[-1]["fills"].append(a.get("fill"))  # type: ignore[union-attr]

    def handle_endtag(self, tag: str) -> None:
        if tag in ("br", "img", "path", "input", "meta", "link"):
            return
        if self._card_depth == self._depth:
            self._card_depth = 0
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._card_depth and data.strip():
            self.cards[-1]["text"].append(data.strip())  # type: ignore[union-attr]


def _collect(rel: str) -> _LinkCollector:
    parser = _LinkCollector()
    parser.feed(_read(rel))
    return parser


class ManifestSingleSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        text = MANIFEST.read_text(encoding="utf-8")
        cls.version = _manifest_field(text, "Version")
        cls.version_code = _manifest_field(text, "versionCode")
        cls.canonical_url = re.search(
            r"`(https://github\.com/NeaBouli/pnyx/releases/download/[^`]+\.apk)`",
            _manifest_field(text, "Canonical APK URL"),
        ).group(1)  # type: ignore[union-attr]
        cls.manifest = text

    def test_every_public_release_asset_is_the_canonical_apk(self) -> None:
        for rel in SURFACES:
            for url in re.findall(r"https://github\.com/NeaBouli/pnyx/releases/download/[^\s\"'<>)]+", _read(rel)):
                self.assertEqual(url, self.canonical_url, f"{rel} links a non-canonical release asset")

    def test_public_version_mentions_match_manifest(self) -> None:
        for rel in SURFACES:
            text = _read(rel)
            for v in re.findall(r"\bv(1\.\d+\.\d+)\b", text):
                self.assertEqual(v, self.version, f"{rel} mentions v{v}, manifest says {self.version}")
            for vc in re.findall(r"\bvC(\d+)\b", text):
                self.assertEqual(vc, self.version_code, f"{rel} mentions vC{vc}, manifest says {self.version_code}")

    def test_direct_card_links_canonical_apk(self) -> None:
        cards = _collect("index.html").cards
        direct = [c for c in cards if c["href"] and "releases/download" in str(c["href"])]
        self.assertEqual(len(direct), 1)
        self.assertEqual(direct[0]["href"], self.canonical_url)


class FDroidStatusTest(unittest.TestCase):
    def test_fdroid_links_use_official_package_page(self) -> None:
        for rel in SURFACES:
            for url in re.findall(r"https?://[^\s\"'<>)]*f-droid\.org[^\s\"'<>)]*", _read(rel)):
                self.assertEqual(url, FDROID_URL, f"{rel} has unexpected F-Droid URL {url}")

    def test_fdroid_card_is_available_and_unversioned(self) -> None:
        cards = [c for c in _collect("index.html").cards if c["href"] == FDROID_URL]
        self.assertEqual(len(cards), 1)
        text = " ".join(cards[0]["text"])  # type: ignore[arg-type]
        self.assertIn("Διαθέσιμο", text)
        self.assertNotRegex(text, r"\bv\d+\.\d+|\bvC\d+", "F-Droid builds independently; do not pin a version")

    def test_no_surface_calls_fdroid_pending_or_stale(self) -> None:
        for rel in SURFACES:
            text = _read(rel)
            for pattern in FDROID_STALE_PATTERNS:
                self.assertNotRegex(text, pattern, f"{rel} contradicts F-Droid availability")


class PlayAndIOSStatusTest(unittest.TestCase):
    def test_play_is_never_claimed_available(self) -> None:
        for rel in SURFACES:
            text = _read(rel)
            self.assertNotRegex(text, r"(available|διαθέσιμ\w*) (on|στο) Google Play", rel)
        cards = [c for c in _collect("index.html").cards if c["href"] == PLAY_TESTING_URL]
        self.assertEqual(len(cards), 1)
        self.assertIn("Υπό έλεγχο", " ".join(cards[0]["text"]))  # type: ignore[arg-type]

    def test_only_apple_link_is_discourse_hub(self) -> None:
        for rel in SURFACES:
            for url in re.findall(r"https?://(?:apps|itunes)\.apple\.com[^\s\"'<>)]*", _read(rel)):
                self.assertEqual(url, DISCOURSE_HUB_IOS_URL, f"{rel} has unexpected Apple URL")

    def test_ekklesia_app_store_card_is_not_a_link(self) -> None:
        cards = [c for c in _collect("index.html").cards if "App Store" in c["text"]]
        self.assertEqual(len(cards), 1)
        self.assertNotEqual(cards[0]["tag"], "a")
        self.assertIsNone(cards[0]["href"])


class EkprosoposArtifactTest(unittest.TestCase):
    def test_unpublished_ekprosopos_apk_is_not_linked(self) -> None:
        manifest = MANIFEST.read_text(encoding="utf-8")
        if "Status: **not published.**" not in manifest.split("## ekklesia mobile")[0]:
            self.skipTest("manifest marks ekprosopos as published")
        for rel in SURFACES:
            self.assertNotIn(EKPROSOPOS_APK, "\n".join(_collect(rel).hrefs) if rel.endswith(".html") else _read(rel), rel)

    def test_unpublished_ekprosopos_has_no_public_checksum_artifact(self) -> None:
        manifest = MANIFEST.read_text(encoding="utf-8")
        if "Status: **not published.**" not in manifest.split("## ekklesia mobile")[0]:
            self.skipTest("manifest marks ekprosopos as published")
        self.assertFalse(
            EKPROSOPOS_CHECKSUM.exists(),
            "a public checksum without its APK is a misleading release signal",
        )

    def test_representative_download_says_in_development(self) -> None:
        self.assertIn('data-en="Android APK — In development"', _read("representative.html"))


class DownloadCardPresentationTest(unittest.TestCase):
    def test_card_icons_are_not_white_on_white(self) -> None:
        cards = _collect("index.html").cards
        self.assertEqual(len(cards), 4)
        for card in cards:
            for fill in card["fills"]:  # type: ignore[union-attr]
                self.assertNotIn(str(fill).lower(), ("white", "#fff", "#ffffff"), f"invisible icon in {card['text']}")

    def test_stale_disabled_comment_removed(self) -> None:
        html = _read("index.html")
        self.assertNotIn("DEAKTIVIERT bis User-Release", html)
        self.assertIn("<!-- Mobile App Download -->", html)


if __name__ == "__main__":
    unittest.main()
