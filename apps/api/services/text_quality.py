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
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
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
    r"^(?:για[ \t]+να[ \t]+βρεις[ \t]+την\b|"
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
_META_ANSWER = re.compile(_without_accents(r"^απάντηση[ \t]*:"), re.IGNORECASE)
_META_ANSWER_INTRO = re.compile(_without_accents(
    r"^(?:βεβαίως[ \t]*(?:,[ \t]*)?)?(?:"
    r"η[ \t]+απάντηση[ \t]+είναι[ \t]+η[ \t]+ακόλουθη[ \t]*:|"
    r"παρακάτω[ \t]+παρατίθεται[ \t]+η[ \t]+απάντηση[ \t]*:)"
), re.IGNORECASE)
_META_SUMMARY = re.compile(_without_accents(r"^σύνοψη[ \t]*:"), re.IGNORECASE)
_PROMPT_ECHO = re.compile(_without_accents(
    r"(?:πλήρης[ \t]+ανάλυση[ \t]+min[ \t]+200[ \t]+λέξεις|"
    r"1[ \t]+πρόταση[ \t]+max[ \t]+120[ \t]+χαρακτήρες|"
    r"3[ \t]+παράγραφοι[ \t]+με[ \t]+τα[ \t]+κύρια[ \t]+σημεία|"
    r"min[ \t]+200[ \t]+words|max[ \t]+120[ \t]+chars)"), re.IGNORECASE,
)
_PROMPT_ECHO_EN = re.compile(
    r"1[ \t]+sentence[ \t]+max[ \t]+120[ \t]+chars|"
    r"3[ \t]+paragraphs[ \t]+with[ \t]+main[ \t]+points|"
    r"full[ \t]+analysis[ \t]+min[ \t]+200[ \t]+words",
    re.IGNORECASE,
)
_ENGLISH_RUN_FUNCTION_WORDS = frozenset({
    "the", "of", "to", "for", "and", "must", "before", "sets", "out", "new",
    "this", "with", "by", "is", "are", "be",
})
_LATIN_FOREIGN_RUN_FUNCTION_WORDS = frozenset(
    _without_accents(word).casefold() for word in {
        # German
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "eines", "einer",
        "und", "von", "für", "mit", "zu", "im", "am", "zum", "zur", "auf", "nach", "aus", "bei",
        "als", "auch", "dass", "ist", "sind", "nicht",
        # French
        "le", "la", "les", "un", "une", "des", "du", "de", "dans", "pour", "avec", "au", "aux",
        "par", "sur", "et", "en", "est", "sont", "que", "qui", "ce", "cette", "ces", "avant", "sans",
        "sous",
        # Spanish
        "el", "los", "las", "una", "unos", "unas", "del", "al", "para", "con", "por", "en", "y",
        "que", "es", "son",
        # Italian
        "il", "lo", "gli", "uno", "una", "di", "della", "dei", "degli", "per", "su", "da", "alla",
        "ai", "dal", "dalla", "nel", "nella", "nello", "sul", "sulla", "sullo", "e", "che",
        # Portuguese
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "do", "da", "dos", "das", "em", "no", "na",
        "nos", "nas", "com", "pelo", "pela", "pelos", "pelas", "e", "que", "são",
    }
)
_FOREIGN_FUNCTION_WORDS = frozenset({
    # Common German, French, Spanish and Italian articles/prepositions. English
    # overlaps and one-letter forms are omitted; require lowercase words with
    # Greek neighbors below to avoid treating Latin names as foreign prose.
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "eines", "einer",
    "und", "von", "für", "mit", "zu", "im", "am", "zum", "zur", "auf", "nach", "aus",
    "le", "la", "les", "un", "une", "des", "du", "de", "dans", "pour", "avec", "au", "aux",
    "par", "sur", "et", "en",
    "el", "los", "las", "una", "unos", "unas", "del", "al", "para", "con", "por",
    "il", "lo", "gli", "le", "uno", "di", "della", "dei", "degli", "per", "su", "da",
    "alla", "ai", "dal", "dalla", "nel", "nella", "nello", "sul", "sulla", "sullo",
})
_LATIN_GREEK_STYLE_ACCENTS = frozenset("áéíóúý")
_LATIN_GREEK_STYLE_I_ACCENTS = frozenset("íý")
_GREEK_UPPERCASE_MOJIBAKE_CHARS = frozenset("ÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÓÔÕÖØÙ")
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


@lru_cache(maxsize=1024)
def _is_latin_letter(char: str) -> bool:
    return "LATIN" in unicodedata.name(char, "")


@lru_cache(maxsize=4096)
def _has_greek_style_latin_accent(token: str) -> bool:
    accents = [char.casefold() for char in token if char.casefold() in _LATIN_GREEK_STYLE_ACCENTS]
    if not accents or not any(_is_latin_letter(char) for char in token):
        return False
    # Require both repeated accents and an accented i/y: French, Spanish and
    # Portuguese names can contain several á/é/ó without resembling Greek.
    return len(accents) >= 2 and any(char in _LATIN_GREEK_STYLE_I_ACCENTS for char in accents)


def _looks_like_greek_uppercase_mojibake(token: str) -> bool:
    # Greek capitals decoded as Latin-1 produce this distinctive uppercase
    # alphabet (e.g. ΑΚΡΙΒΕΣ -> ÁÊÑÉÂÅÓ); keep it separate from accent counting.
    return (len(token) >= 6 and token.isupper()
            and all(char in _GREEK_UPPERCASE_MOJIBAKE_CHARS for char in token))


def _has_foreign_words(unquoted: str, *, greek_context: bool) -> bool:
    if not greek_context:
        return False
    matches = iter(_WORD_TOKEN.finditer(unquoted))
    previous = None
    current = next(matches, None)
    following = next(matches, None)
    while current is not None:
        token = current[0]
        if _is_latin_letter(token[0]):
            if _has_greek_style_latin_accent(token) or _looks_like_greek_uppercase_mojibake(token):
                return True
            if (previous is not None and following is not None and token == token.lower()
                    and token.casefold() in _FOREIGN_FUNCTION_WORDS
                    and _is_greek_token(previous[0]) and _is_greek_token(following[0])):
                return True
        previous, current = current, following
        following = next(matches, None)
    return False


_LATIN_RUN_FIELDS = frozenset({"pill_el", "summary_short_el"})


def _latin_run_reasons(unquoted: str) -> tuple[bool, bool]:
    """Return English-clause and other-European-clause signals from Latin runs."""
    # Four words require at least three horizontal separators. This keeps long
    # numeric identifiers and unbroken tokens out of the word scanner.
    if unquoted.count(" ") + unquoted.count("\t") < 3:
        return False, False
    english_clause = foreign_clause = False
    run_size = lowercase_count = english_count = foreign_count = 0
    run_is_latin = titlecase_only = True

    def finish_run() -> None:
        nonlocal english_clause, foreign_clause
        if run_size >= 4 and run_is_latin and titlecase_only and lowercase_count * 5 >= run_size * 3:
            english_clause = english_clause or english_count >= 2
            foreign_clause = foreign_clause or foreign_count >= 2

    previous_end = 0
    for match in _WORD_TOKEN.finditer(unquoted):
        gap = unquoted[previous_end:match.start()]
        if run_size and gap.strip(" \t"):
            finish_run()
            run_size = lowercase_count = english_count = foreign_count = 0
            run_is_latin = titlecase_only = True

        word = match[0]
        run_size += 1
        if run_is_latin:
            if not all(_is_latin_letter(char) for char in word):
                run_is_latin = titlecase_only = False
            else:
                is_lower = word.islower()
                lowercase_count += is_lower
                titlecase_only = titlecase_only and (
                    is_lower or (word[0].isupper() and (len(word) == 1 or word[1:].islower()))
                )
                lowered = word.casefold()
                # One-letter tokens (OCR-spaced letters, initials) never count.
                english_count += len(lowered) >= 2 and lowered in _ENGLISH_RUN_FUNCTION_WORDS
                foreign_count += len(lowered) >= 2 and (
                    lowered in _LATIN_FOREIGN_RUN_FUNCTION_WORDS
                    or (not lowered.isascii()
                        and _without_accents(lowered) in _LATIN_FOREIGN_RUN_FUNCTION_WORDS)
                )
        previous_end = match.end()
    finish_run()
    return english_clause, foreign_clause


@lru_cache(maxsize=4096)
def _is_greek_token(token: str) -> bool:
    return any(_is_greek_letter(char) for char in token)


def _without_quotes(text: str, *, only_latin: bool, placeholder: str = " ") -> str:
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
                chunks.append(placeholder)
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


def without_quotes(text: str, *, placeholder: str = " ") -> str:
    """Replace complete quoted passages in one linear pass (shared by detectors).

    A non-space placeholder keeps the quote's position, so prose after a leading
    quotation is never promoted to the start of a line.
    """
    return _without_quotes(text, only_latin=False, placeholder=placeholder)


def _meta_lines(text: str) -> tuple[list[str], bool]:
    lines = []
    prefixed_answer = False
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
        line = line[offset:].lstrip(" #*>_-")
        prefixed_answer = prefixed_answer or bool(offset and _META_ANSWER.search(line))
        lines.append(line)
    return lines, prefixed_answer


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
    prose = _without_quotes(_EMAIL.sub("", _URL.sub("", compact)), only_latin=True)
    unquoted = _without_quotes(prose, only_latin=False)
    reasons: list[str] = []
    if greek_share is not None:
        letters = {c: count for c, count in Counter(prose).items() if c.isalpha()}
        letter_count = sum(letters.values())
        greek_letters = sum(count for c, count in letters.items() if _is_greek_letter(c))
        latin_letters_present = any(_is_latin_letter(char) for char in letters)
        latin_tokens = _LATIN_TOKEN.findall(prose)
        acronyms_only = bool(latin_tokens) and all(_ACRONYM.fullmatch(token) for token in latin_tokens)
        short_acronyms = field == "pill_el" and letter_count <= 20 and acronyms_only
        if not short_acronyms and (not letter_count or greek_letters / letter_count < greek_share):
            reasons.append("non_greek")
        if _has_mixed_words(prose):
            reasons.append("mixed_script")
        if latin_letters_present:
            # Whole Latin sentences are only judged in the short generated
            # summaries: long fields hold official extracted text with unquoted
            # English project titles, e-mail lines and OCR-spaced letters
            # (54 false positives in a 2026-11-13 production comparison).
            english_run, foreign_run = (
                _latin_run_reasons(unquoted) if field in _LATIN_RUN_FIELDS else (False, False)
            )
            if english_run or _ENGLISH_CLAUSE.search(_HORIZONTAL_SPACE.sub(" ", unquoted)):
                reasons.append("english_clause")
            greek_context = bool(greek_letters and letter_count and greek_letters / letter_count >= greek_share)
            if foreign_run or _has_foreign_words(unquoted, greek_context=greek_context):
                reasons.append("foreign_word")

    lines, prefixed_answer = _meta_lines(unquoted)
    summary_label = any(_META_SUMMARY.search(line) for line in lines)
    answer_intro = any(_META_ANSWER_INTRO.search(line) for line in lines)
    meta_answer = (prefixed_answer or summary_label or answer_intro
                   or any(_META_ANSWER.search(line) for line in lines))
    if (any(_META.search(line) for line in lines)
            or meta_answer
            or (any(_PROMPT_TITLE.search(line) for line in lines) and any(_PROMPT_TEXT.search(line) for line in lines))
            or _FAILURE_TOKEN.fullmatch(prose.strip())
            or any(_SERIALIZED.search(line.lstrip()) for line in compact.splitlines() if line.strip())):
        reasons.append("refusal_or_meta")
    if prefixed_answer or summary_label or answer_intro:
        reasons.append("meta_answer")
    prompt_echo = _PROMPT_ECHO_EN if field.endswith("_en") else _PROMPT_ECHO
    if prompt_echo.search(_without_accents(unquoted)):
        reasons.append("prompt_echo")
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
