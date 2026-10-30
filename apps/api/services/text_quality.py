"""Deterministic, I/O-free checks for generated bill prose.

These checks detect language/transport failures, not factual accuracy. URLs and
quoted Latin titles do not dilute the Greek letter share. English counterpart
fields use the same integrity checks without requiring Greek.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


GREEK_FIELDS = ("pill_el", "summary_short_el", "summary_long_el", "analysis_el")
GENERATED_TEXT_FIELDS = GREEK_FIELDS + ("pill_en", "summary_short_en", "summary_long_en")
DEFAULT_GREEK_SHARE = 0.6


def _without_accents(value: str) -> str:
    """Greek uppercase often drops tonos, so case-insensitivity alone fails."""
    return "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))


_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_QUOTED_LATIN = re.compile(r'"[^"\n]+"|“[^”\n]+”|«[^»\n]+»')
_META = re.compile(_without_accents(
    r"\b(?:tôi\s+xin\s+lỗi|tôi\s+không\s+thể|i['’]?m\s+sorry|i\s+am\s+sorry|"
    r"i\s+cannot|i\s+can['’]t\s+provide|as\s+an?\s+(?:ai|language\s+model))\b|"
    r"λυπάμαι\s*,?\s*αλλά\s+δεν\s+μπορώ|ως\s+(?:μοντέλο|ai)\b|"
    r"^\s*(?:[#*>-]+\s*)?(?:απάντηση\s*:|για\s+να\s+βρεις\s+την\b|"
    r"(?:here\s+is|here['’]s)\s+(?:the|a|your)\s+(?:summary|analysis)|summary\s*:)|"
    r"```|~~~|^\s*(?:\{\s*\"|\[\s*\{)|"
    r"<\|(?:im_start|im_end|system|assistant)\|>|\[/?INST\]|"
    r"\b(?:you\s+are\s+(?:an?\s+)?(?:ai|greek\s+legislation\s+expert)|"
    r"write\s+only\s+in|return\s+only\s+(?:valid\s+)?json|"
    r"summarize\s+this\s+greek\s+law|respond\s+only\s+in\s+json)|"
    r"επέστρεψε\s+μόνο\s+(?:έγκυρο\s+)?json|ανάλυσε\s+αυτό\s+το\s+ελληνικό\s+νομοσχέδιο|"
    r"(?:^|\n)\s*(?:system|user|assistant|prompt)\s*:"),
    re.IGNORECASE,
)
_PROMPT_TITLE = re.compile(r"(?:^|\n)\s*(?:title|τιτλος)\s*:", re.IGNORECASE)
_PROMPT_TEXT = re.compile(r"(?:^|\n)\s*(?:text|κειμενο)\s*:", re.IGNORECASE)
_READER_TITLE = re.compile(r"\btitle\s*:", re.IGNORECASE)
_READER_BODY = re.compile(r"\b(?:url\s+source|markdown\s+content)\s*:", re.IGNORECASE)
_UTF8_ARTEFACT = re.compile(r"[ÃÂÎÏ][\x80-\xbfŒœŸƒˆ˜\u2010-\u203a€]")
# Quotes, ellipses and dashes alone are normal Greek typography. Require
# several *distinctive* encoding artefacts before considering their density.
_STRONG_ARTEFACTS = frozenset("≈ÀÕƒÃœÎÏ�")
_ARTEFACTS = _STRONG_ARTEFACTS | frozenset("«»…—∆∂¬√")


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reasons: tuple[str, ...]


def _is_greek_letter(char: str) -> bool:
    return char.isalpha() and "GREEK" in unicodedata.name(char, "")


def check_generated_text(text: str | None, *, field: str) -> QualityResult:
    """Check integrity in either language, and language in Greek fields."""
    if field.endswith("_el"):
        return check_generated_greek(text, field=field)
    return _check(text, field=field, greek_share=None)


def check_generated_greek(
    text: str | None, *, field: str, greek_share: float = DEFAULT_GREEK_SHARE,
) -> QualityResult:
    """Accept absent values; reject detectable failures in generated Greek.

    Very short pills may contain a single acronym or Greek plus short Latin
    acronyms. Longer pills use the same 60% minimum as summaries and analyses.
    """
    return _check(text, field=field, greek_share=greek_share)


def _check(text: str | None, *, field: str, greek_share: float | None) -> QualityResult:
    if text is None or (isinstance(text, str) and not text.strip()):
        return QualityResult(True, ())
    if not isinstance(text, str):
        return QualityResult(False, ("non_greek",))
    normalized = unicodedata.normalize("NFC", text)
    prose = _URL.sub("", normalized)
    reasons: list[str] = []
    if greek_share is not None:
        # English titles in otherwise Greek prose are useful source citations.
        if any(_is_greek_letter(c) for c in prose):
            prose = _QUOTED_LATIN.sub(
                lambda m: m[0] if any(_is_greek_letter(c) for c in m[0]) else "", prose,
            )
        letters = [c for c in prose if c.isalpha()]
        greek_letters = sum(_is_greek_letter(c) for c in letters)
        acronym = field == "pill_el" and bool(re.fullmatch(r"[A-Z]{2,5}", prose.strip()))
        short_acronyms = (
            field == "pill_el" and len(letters) <= 20 and greek_letters >= 3
            and all(_is_greek_letter(c) or (c.isascii() and c.isupper()) for c in letters)
            and all(len(token) <= 5 for token in re.findall(r"[A-Z]+", prose))
        )
        if not (acronym or short_acronyms) and (not letters or greek_letters / len(letters) < greek_share):
            reasons.append("non_greek")
    folded = _without_accents(normalized)
    if _META.search(folded) or (_PROMPT_TITLE.search(folded) and _PROMPT_TEXT.search(folded)):
        reasons.append("refusal_or_meta")
    if _READER_TITLE.search(normalized) and _READER_BODY.search(normalized):
        reasons.append("reader_metadata")
    strong = sum(c in _STRONG_ARTEFACTS for c in normalized)
    density = sum(c in _ARTEFACTS for c in normalized) / max(len(normalized), 1)
    if len(_UTF8_ARTEFACT.findall(normalized)) >= 2 or (strong >= 3 and density >= 0.08):
        reasons.append("mojibake")
    if any(c.casefold() in "ăđơư" or "\u1ea0" <= c <= "\u1ef9" for c in normalized):
        reasons.append("foreign_script")
    return QualityResult(not reasons, tuple(reasons))
