"""Read real external script bodies for offline behavior tests, in document order."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def page_with_scripts(path):
    path = Path(path)
    def load(match):
        src = match[1]
        if re.match(r"(?:https?:)?//", src):
            raise ValueError("behavior tests only read local assets")
        asset = ROOT / "docs" / src.lstrip("/") if src.startswith("/") else path.parent / src
        return "<script>" + asset.read_text(encoding="utf-8") + "</script>"
    return re.sub(r'<script\b[^>]*\bsrc="([^"]+)"[^>]*></script>', load, path.read_text(encoding="utf-8"))
