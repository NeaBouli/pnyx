"""Deterministic, I/O-free integrity and language checks for generated prose."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from services.error_pages import looks_like_error_page


GREEK_FIELDS = ("pill_el", "summary_short_el", "summary_long_el", "analysis_el")
GENERATED_TEXT_FIELDS = GREEK_FIELDS + ("pill_en", "summary_short_en", "summary_long_en")
DEFAULT_GREEK_SHARE = 0.6


def _without_accents(value: str) -> str:
    """Greek uppercase often drops tonos, so case-insensitivity alone fails."""
    if value.isascii():
        return value
    decomposed = unicodedata.normalize("NFD", value)
    marks = {ord(c): None for c in set(decomposed) if unicodedata.combining(c)}
    return decomposed.translate(marks) if marks else decomposed


_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# These expressions run on lines with horizontal whitespace collapsed. Refusals
# must describe the speaker, rather than definitions or reported testimony.
_META = re.compile(_without_accents(
    r"^(?:tôi[ \t]+xin[ \t]+lỗi|tôi[ \t]+không[ \t]+thể|i['’]?m[ \t]+sorry|i[ \t]+am[ \t]+sorry|"
    r"i[ \t]+cannot|i[ \t]+can['’]t[ \t]+provide|as[ \t]+an?[ \t]+(?:ai|language[ \t]+model),? i)\b|"
    r"^(?:λυπάμαι|δυστυχώς)[ \t]*(?:,[ \t]*)?(?:αλλά[ \t]+)?δεν[ \t]+μπορώ\b|"
    r"^δεν[ \t]+μπορώ[ \t]+να[ \t]+(?:παράσχω|παρέχω|συνοψίσω|αναλύσω|εξαγάγω|δημιουργήσω|συντάξω|δώσω|ετοιμάσω)\b|"
    r"^δεν[ \t]+(?:έχω|διαθέτω)[ \t]+πρόσβαση\b|"
    r"^χρειάζομαι[ \t]+(?:το[ \t]+(?:πλήρες[ \t]+)?(?:κείμενο|έγγραφο)|περισσότερες[ \t]+πληροφορίες)\b|"
    r"^(?:παρακαλώ[ \t]*(?:,[ \t]*)?(?:να[ \t]+)?(?:μου[ \t]+)?"
    r"(?:στείλετε|παρέχετε|επισυνάψετε|επικολλήσετε|δώσετε)|"
    r"μπορείτε[ \t]+να[ \t]+(?:μου[ \t]+)?(?:παρέχετε|στείλετε|επισυνάψετε|επικολλήσετε))\b|"
    r"^ως[ \t]+(?:ai|(?:γλωσσικό[ \t]+)?μοντέλο(?:[ \t]+τεχνητής[ \t]+νοημοσύνης)?)"
    r"[ \t]*(?:,[ \t]*)?δεν[ \t]+(?:μπορώ|έχω|διαθέτω)\b|"
    r"^(?:απάντηση[ \t]*:|για[ \t]+να[ \t]+βρεις[ \t]+την\b|"
    r"(?:παρακαλώ[ \t]*(?:,[ \t]*)?)?(?:δώστε|δώσε|στείλτε|στείλε|παραθέστε|παραθέσε)[ \t]+"
    r"(?:μου[ \t]+)?(?:το[ \t]+)?(?:κείμενο|έγγραφο)|"
    r"(?:here[ \t]+is|here['’]s)[ \t]+(?:the|a|your)[ \t]+(?:summary|analysis)|summary[ \t]*:)|"
    r"```|~~~|^(?:\{[ \t]*\"|\[[ \t]*\{)|"
    r"<\|(?:im_start|im_end|system|assistant)\|>|\[/?INST\]|"
    r"\b(?:you[ \t]+are[ \t]+(?:an?[ \t]+)?(?:ai|greek[ \t]+legislation[ \t]+expert)|"
    r"write[ \t]+only[ \t]+in|return[ \t]+only[ \t]+(?:valid[ \t]+)?json|"
    r"summarize[ \t]+this[ \t]+greek[ \t]+law|respond[ \t]+only[ \t]+in[ \t]+json)|"
    r"επέστρεψε[ \t]+μόνο[ \t]+(?:έγκυρο[ \t]+)?json|ανάλυσε[ \t]+αυτό[ \t]+το[ \t]+ελληνικό[ \t]+νομοσχέδιο|"
    r"^(?:system|user|assistant|prompt)[ \t]*:"), re.IGNORECASE,
)
_HORIZONTAL_SPACE = re.compile(r"[ \t]+")
_LIST_PREFIX = re.compile(r"(?:[0-9]{1,9}[.)]|[•‣◦⁃∙●▪▫]) +")
# Whole English clauses are a language signal, never a structural reason for
# legacy deletion. Lowercase grammar avoids treating titles/brands as clauses.
_ENGLISH_CLAUSE = re.compile(
    r"\b(?:[Ii]ntroduces?|[Pp]rovides?|[Ee]stablishes?|[Dd]efines?|[Ii]mposes?) "
    r"(?:new|additional|the) (?:requirements?|rules?|procedures?|obligations?)\b|"
    r"\b[Pp]lease (?:provide|send|paste|attach|upload|share) (?:me )?"
    r"(?:the|your|full) (?:document|text) so [Ii] can (?:summarize|summarise|analyze|analyse)\b"
)
_SERIALIZED = re.compile(r'^(?:\{[ \t]*"|\[[ \t]*\{)')
_PROMPT_TITLE = re.compile(r"^(?:title|τιτλος)[ \t]*:", re.IGNORECASE)
_PROMPT_TEXT = re.compile(r"^(?:text|κειμενο)[ \t]*:", re.IGNORECASE)
_READER_TITLE = re.compile(r"\btitle[ \t]*:", re.IGNORECASE)
_READER_BODY = re.compile(r"\b(?:url[ \t]+source|markdown[ \t]+content)[ \t]*:", re.IGNORECASE)
_UTF8_ARTEFACT = re.compile(r"[ÃÂÎÏ][\x80-\xbfŒœŸƒˆ˜\u2010-\u203a€]")
_PUNCTUATION_ARTEFACT = re.compile(r"â(?:€[œ“”˜™šž¦]|€[\x80-\xbf]|€™|€¦|€”)")
_STRONG_ARTEFACTS = frozenset("≈ÀÕƒÃœÎÏ�")
_ARTEFACTS = _STRONG_ARTEFACTS | frozenset("«»…—∆∂¬√")
_LATIN_TOKEN = re.compile(r"[A-Za-z]+(?:[-\d]+[A-Za-z\d]*)*")
_ACRONYM = re.compile(r"[A-Z]{2,5}|(?=[A-Z\d-]*\d)[A-Z][A-Z\d]*(?:-[A-Z\d]+)*")
_WORD_TOKEN = re.compile(r"[^\W\d_]+")
# Latin lookalikes found in Greek typography (including lunate sigma/epsilon).
# Keep case: Latin N resembles Greek Ν, but n is evidence in e.g. κίνδυnu.
_GREEK_HOMOGLYPHS = frozenset("ABCEHIKMNOPTXYZaceiopuvxy")
_FOREIGN_SCRIPT_PREFIXES = (
    "CYRILLIC ", "CJK ", "HIRAGANA ", "KATAKANA ", "HANGUL ", "BOPOMOFO ", "YI ",
    "HALFWIDTH KATAKANA ", "HALFWIDTH HANGUL ",
    "DEVANAGARI ", "BENGALI ", "GURMUKHI ", "GUJARATI ", "ORIYA ",
    "TAMIL ", "TELUGU ", "KANNADA ", "MALAYALAM ", "SINHALA ",
    "BRAHMI ", "KAITHI ", "SHARADA ", "KHOJKI ", "KHUDAWADI ", "GRANTHA ",
    "NEWA ", "TIRHUTA ", "SIDDHAM ", "MODI ", "TAKRI ", "DOGRA ", "NANDINAGARI ",
    "DIVES AKURU ", "SAURASHTRA ", "OL CHIKI ", "MEETEI MAYEK ", "LEPCHA ",
    "LIMBU ", "SYLOTI NAGRI ", "GUNJALA GONDI ", "MASARAM GONDI ",
    "CHAKMA ", "MAHAJANI ", "BHAIKSUKI ",
    "ARABIC ", "HEBREW ", "THAI ",
)
_FAILURE_TOKEN = re.compile(r"\b(?:error|sorry|refusal|refused|forbidden|denied|rejected|failure|failed|timeout|unauthorized|unavailable)\b", re.IGNORECASE)


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reasons: tuple[str, ...]


# Character classifications repeat throughout long documents. Bound each cache
# independently of input size, including when auditing many different scripts.
@lru_cache(maxsize=1024)
def _is_greek_letter(char: str) -> bool:
    return not char.isascii() and char.isalpha() and "GREEK" in unicodedata.name(char, "")


@lru_cache(maxsize=1024)
def _is_foreign_letter(char: str) -> bool:
    # Numeral signs and phonetic modifiers are typography, not foreign prose.
    if char.isascii() or not char.isalpha() or unicodedata.category(char) == "Lm":
        return False
    return (char.casefold() in "ăđơư" or "\u1ea0" <= char <= "\u1ef9"
            or unicodedata.name(char, "").startswith(_FOREIGN_SCRIPT_PREFIXES))


@lru_cache(maxsize=1024)
def _is_non_homoglyph_latin_letter(char: str) -> bool:
    return char not in _GREEK_HOMOGLYPHS and "LATIN" in unicodedata.name(char, "")


@lru_cache(maxsize=1024)
def _is_mixed_short_word(token: str) -> bool:
    """Only cache tokens of at most 64 characters, bounding retained text."""
    return (any(_is_greek_letter(c) for c in token)
            and any(_is_non_homoglyph_latin_letter(c) for c in token))


def _has_mixed_words(prose: str) -> bool:
    words = mixed = 0
    for match in _WORD_TOKEN.finditer(prose):
        token = match[0]
        words += 1
        if len(token) <= 64:
            mixed += _is_mixed_short_word(token)
            continue
        # Repeated letters in an adversarial long word need classification once.
        characters = set(token)
        if (any(_is_greek_letter(c) for c in characters)
                and any(_is_non_homoglyph_latin_letter(c) for c in characters)):
            mixed += 1
    # One corrupt word in a short summary is significant. In a longer official
    # document tolerate one isolated typo, but reject repeated corruption.
    return mixed >= 2 or (mixed == 1 and words <= 200)


def _without_quotes(text: str, *, only_latin: bool) -> str:
    """Scan once, retaining incomplete quotes and, optionally, non-Latin quotes."""
    if (not (text.count('"') >= 2 or ('“' in text and '”' in text) or ('«' in text and '»' in text))
            or (only_latin and not any(_is_greek_letter(c) for c in text))):
        return text
    closing = {'"': '"', '“': '”', '«': '»'}
    chunks: list[str] = []
    start = 0
    opener: int | None = None
    end_quote = ""
    latin_only = True
    has_latin = False
    for index, char in enumerate(text):
        if opener is None:
            if char in closing:
                opener, end_quote = index, closing[char]
                latin_only, has_latin = True, False
        elif char == end_quote:
            if not only_latin or (latin_only and has_latin):
                chunks.append(text[start:opener])
                chunks.append(" ")
                start = index + 1
            opener = None
        elif char in "\r\n" and only_latin:
            # A Latin title exemption stays within a line. Reported speech may
            # span paragraphs, but must still have a complete closing quote.
            opener = None
        elif char.isalpha():
            latin = "LATIN" in unicodedata.name(char, "")
            latin_only = latin_only and latin
            has_latin = has_latin or latin
    chunks.append(text[start:])
    return "".join(chunks)


def without_quotes(text: str) -> str:
    """Drop complete quoted passages in one linear pass (shared by detectors)."""
    return _without_quotes(text, only_latin=False)


def _meta_lines(text: str) -> list[str]:
    lines = []
    for line in _without_accents(text).splitlines():
        if not line.strip():
            continue
        line = _HORIZONTAL_SPACE.sub(" ", line).replace("**", "").replace("__", "")
        line = line.lstrip(" #*>_-")
        # Strip formatting only; the anchored detector still requires the colon
        # in 'Απάντηση:', so numbered ministry answers remain ordinary prose.
        offset = 0
        while match := _LIST_PREFIX.match(line, offset):
            offset = match.end()
        lines.append(line[offset:].lstrip(" #*>_-"))
    return lines


def check_generated_text(text: str | None, *, field: str) -> QualityResult:
    """Check integrity in either language, and language in Greek fields."""
    return _check(text, field=field, greek_share=DEFAULT_GREEK_SHARE if field.endswith("_el") else None)


def check_generated_greek(
    text: str | None, *, field: str, greek_share: float = DEFAULT_GREEK_SHARE,
) -> QualityResult:
    """Accept absent database values; providers must separately require output."""
    return _check(text, field=field, greek_share=greek_share)


def _check(text: str | None, *, field: str, greek_share: float | None) -> QualityResult:
    if text is None or (isinstance(text, str) and not text.strip()):
        return QualityResult(True, ())
    if not isinstance(text, str):
        return QualityResult(False, ("non_greek",))
    normalized = unicodedata.normalize("NFC", text)
    # Compact once before the Python character scans too. Large whitespace runs
    # carry no language/integrity information; retain the raw length for density.
    compact = _HORIZONTAL_SPACE.sub(" ", normalized)
    prose = _without_quotes(_URL.sub("", compact), only_latin=True)
    unquoted = _without_quotes(prose, only_latin=False)
    reasons: list[str] = []
    if greek_share is not None:
        letters = {c: count for c, count in Counter(prose).items() if c.isalpha()}
        letter_count = sum(letters.values())
        greek_letters = sum(count for c, count in letters.items() if _is_greek_letter(c))
        latin_tokens = _LATIN_TOKEN.findall(prose)
        acronyms_only = bool(latin_tokens) and all(_ACRONYM.fullmatch(token) for token in latin_tokens)
        short_acronyms = field == "pill_el" and letter_count <= 20 and acronyms_only
        if not short_acronyms and (not letter_count or greek_letters / letter_count < greek_share
                                  or _ENGLISH_CLAUSE.search(_HORIZONTAL_SPACE.sub(" ", unquoted))):
            reasons.append("non_greek")
        if _has_mixed_words(prose):
            reasons.append("mixed_script")

    lines = _meta_lines(unquoted)
    if (any(_META.search(line) for line in lines)
            or (any(_PROMPT_TITLE.search(line) for line in lines) and any(_PROMPT_TEXT.search(line) for line in lines))
            or _FAILURE_TOKEN.fullmatch(prose.strip())
            or any(_SERIALIZED.search(line.lstrip()) for line in compact.splitlines() if line.strip())):
        reasons.append("refusal_or_meta")
    if _READER_TITLE.search(compact) and _READER_BODY.search(compact):
        reasons.append("reader_metadata")
    if looks_like_error_page(compact):
        reasons.append("error_page")
    characters = Counter(compact)
    strong = sum(count for c, count in characters.items() if c in _STRONG_ARTEFACTS)
    density = sum(count for c, count in characters.items() if c in _ARTEFACTS) / max(len(normalized), 1)
    if (_PUNCTUATION_ARTEFACT.search(compact) or len(_UTF8_ARTEFACT.findall(compact)) >= 2
            or (strong >= 3 and density >= 0.08)):
        reasons.append("mojibake")
    if any(_is_foreign_letter(c) for c in characters):
        reasons.append("foreign_script")
    return QualityResult(not reasons, tuple(reasons))
