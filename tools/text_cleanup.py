r"""Noise patterns and text normalisation shared by `extract` and `validate`.

Both stages have to agree on what a page footer looks like. When they did not,
the remover matched ``\s+`` where the detector matched a literal space, and
thirteen footers walked straight through the checks into the published bank.
Everything either stage needs to recognise is defined once, here.

Every function is pure: it takes text and returns text or a report, so the
whole layer is tested with inline strings and never needs a PDF.
"""

from __future__ import annotations

import re
import unicodedata

# Every character a PDF may render as a dash. Poppler emits U+2013 in the
# ENA18 footer where Xpdf emits U+00AD, which is exactly how a footer regex
# written against one build of pdftotext silently stops matching under another.
# Spelled with escapes because U+00AD is invisible in an editor.
DASH_CHARACTERS = "-\xad‐‑‒–—―−"
DASH_CLASS = "[\\u002d\\u00ad\\u2010-\\u2015\\u2212]"

_DASH_TRANSLATION = {ord(char): "-" for char in DASH_CHARACTERS}

# Page markers. Precise enough to search anywhere in a stem or an option: no
# legitimate exam question says "Página 7 de 8" about itself.
PAGE_MARKER_PATTERN = re.compile(
    r"P[áa]gina\s+\d+\s+de\s+\d+|Pg\.\s*\d+\s*/\s*\d+", re.IGNORECASE
)

# The institutional header, matched in full. Matching the fragment "Programa
# de Pós-Graduação em" instead would reject any legitimate stem that mentions a
# graduate programme, which is a sentence an exam about academic policy writes.
INSTITUTIONAL_PHRASES = (
    "Associação Fórum Nacional de Gestores de Inovação e Transferência de Tecnologia",
    "Programa de Pós-Graduação em Propriedade Intelectual e Transferência de Tecnologia"
    " para Inovação",
    "Propriedade Intelectual e Transferência de Tecnologia para Inovação",
)

_INSTITUTIONAL_PATTERN = re.compile(
    "|".join(re.escape(phrase) for phrase in INSTITUTIONAL_PHRASES)
)

# Whole-line header and footer patterns, matched against the dash-normalised
# line. An explicit list, not a generic rule: a broad filter would eat stem
# text, and these are the only headers and footers the seven papers print.
NOISE_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # AV2 footer: "18 de novembro de 2023   PI   Página 7 de 8".
    re.compile(
        r"^\s*\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s+\S.*?P[áa]gina\s+\d+\s+de\s+\d+\s*$",
        re.I,
    ),
    # ENA18 footer: "Etapa 1 - Prova Nacional ... Pg. 1/15".
    re.compile(r"^\s*Etapa\s+1\s*-.*Pg\.\s*\d+\s*/\s*\d+\s*$", re.I),
    # A line that is nothing but a page marker.
    re.compile(r"^\s*(?:P[áa]gina\s+\d+\s+de\s+\d+|Pg\.\s*\d+\s*/\s*\d+)\s*$", re.I),
    # The institutional header, which breaks across lines differently per paper.
    re.compile(r"^\s*Associação Fórum Nacional de Gestores.*$", re.I),
    re.compile(r"^\s*Programa de Pós-Graduação em\s*$", re.I),
    re.compile(r"^\s*Programa de Pós-Graduação em Propriedade Intelectual.*$", re.I),
    re.compile(
        r"^\s*Propriedade Intelectual e Transferência de Tecnologia para Inovação\s*$",
        re.I,
    ),
    re.compile(r"^\s*PROFNIT\s*$"),
)

# A question that asks the student to match two columns. Broad on purpose: the
# papers say "correlacione", "associe" and "relacione", and number the columns
# either "1"/"2" or "I"/"II", so anchoring on one wording misses the others.
COLUMN_MATCHING_PATTERN = re.compile(
    r"correlacione"
    r"|associe\b"
    r"|relacione\s+(?:as\s+)?colunas?"
    r"|\bcolunas?\s+(?:[12]|IV|V|III|II|I)\b",
    re.IGNORECASE,
)

# The structural signature of two columns rendered side by side: a run of three
# or more interior spaces with a "( )" answer slot to the right of it.
SIDE_BY_SIDE_PATTERN = re.compile(r"^.*\S {3,}.*\(\s*\)", re.MULTILINE)

# The Moodle prompt that leaked into three stems when the papers were exported.
PLATFORM_INSTRUCTION_PATTERN = re.compile(r"^\s*Escolha uma:?\s*$", re.IGNORECASE)

# A roman-numeral assertion marker at the start of a line, separated from its
# text by a dash: "I- ", "IV – ", "II-".
ROMAN_DASH_MARKER_PATTERN = re.compile(
    rf"^([ \t]*)([IVX]{{1,6}})[ \t]*({DASH_CLASS})[ \t]*(?=\S)",
    re.MULTILINE,
)

# A line-initial minus sign used as a bullet. U+2212 is a mathematical
# operator; ENA25-Q18 prints five of them where the list wanted dashes.
MINUS_BULLET_PATTERN = re.compile(r"^([ \t]*)−(?=[ \t])", re.MULTILINE)

SPACE_RUN_PATTERN = re.compile(r"[ \t]{3,}")

LEFT_QUOTE = "“"
RIGHT_QUOTE = "”"


def normalize_dashes(text: str) -> str:
    """Fold every dash-like character to a plain hyphen-minus.

    Used before matching, never on published text: it exists so a pattern
    keeps matching when a different build of pdftotext picks a different dash.

    Args:
        text: Any text.

    Returns:
        The text with every dash character replaced by ``-``.
    """
    return text.translate(_DASH_TRANSLATION)


def is_noise_line(line: str) -> bool:
    """Report whether a line is a page header or footer rather than content.

    Args:
        line: One raw line of layout-preserving PDF text.

    Returns:
        True when the line is header or footer noise.
    """
    normalized = normalize_dashes(line)
    return any(pattern.match(normalized) for pattern in NOISE_LINE_PATTERNS)


def strip_noise_lines(text: str) -> str:
    """Drop every header and footer line from the extracted text.

    Runs before segmentation on purpose: in AV2-PI a footer splits question 16
    mid-stem, and removing the footer first lets the stem reassemble on its own.

    Args:
        text: The full layout-preserving text of one exam paper.

    Returns:
        The same text with the noise lines removed.
    """
    return "\n".join(line for line in text.splitlines() if not is_noise_line(line))


def find_residue(text: str) -> tuple[str, ...]:
    """Find page header or footer fragments left inside published text.

    Args:
        text: A stem or an option.

    Returns:
        Every distinct fragment found, in the order it first appears. Empty
        when the text is clean.
    """
    found: list[str] = []
    for match in PAGE_MARKER_PATTERN.finditer(text):
        if match.group(0) not in found:
            found.append(match.group(0))
    for match in _INSTITUTIONAL_PATTERN.finditer(text):
        if match.group(0) not in found:
            found.append(match.group(0))
    return tuple(found)


def mentions_column_matching(text: str) -> bool:
    """Report whether the text asks the student to match two columns.

    Args:
        text: A stem.

    Returns:
        True when the wording announces a column-matching exercise.
    """
    return COLUMN_MATCHING_PATTERN.search(text) is not None


def has_side_by_side_columns(text: str) -> bool:
    """Report whether two columns were rendered side by side.

    ``pdftotext -layout`` keeps the horizontal position of both columns, so the
    two halves end up on one line separated by a run of spaces. Pairing them by
    line then reads as an answer the paper never printed.

    Args:
        text: A stem.

    Returns:
        True when a line carries the two-column signature.
    """
    return SIDE_BY_SIDE_PATTERN.search(text) is not None


def collapse_space_runs(text: str) -> str:
    """Collapse runs of three or more spaces or tabs into a single space.

    ``pdftotext -layout`` pads a roman assertion marker out to the column its
    text starts in, which reaches the screen as ``I.      A Organização``.

    Args:
        text: A stem or an option.

    Returns:
        The text with the padding runs collapsed.
    """
    return SPACE_RUN_PATTERN.sub(" ", text)


def strip_platform_instruction(text: str) -> str:
    """Remove the trailing "Escolha uma:" the exam platform leaked into a stem.

    The line is an instruction of the Moodle export, not part of the question,
    and the app renders its own instruction above the options.

    Args:
        text: A stem.

    Returns:
        The stem without the trailing platform instruction.
    """
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and PLATFORM_INSTRUCTION_PATTERN.match(lines[-1]):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines)


def close_unbalanced_quotes(text: str) -> str:
    """Close a curly quotation mark the source paper opened and never closed.

    The closer is appended to the end of the paragraph that opened the quote,
    which is where the quoted passage ends — not to the end of the stem, which
    would swallow the sentence that introduces the options.

    Args:
        text: A stem or an option.

    Returns:
        The text with every unbalanced opening quote closed.
    """
    if text.count(LEFT_QUOTE) <= text.count(RIGHT_QUOTE):
        return text

    paragraphs = re.split(r"(\n[ \t]*\n)", text)
    for index, chunk in enumerate(paragraphs):
        missing = chunk.count(LEFT_QUOTE) - chunk.count(RIGHT_QUOTE)
        if missing > 0:
            paragraphs[index] = chunk.rstrip() + RIGHT_QUOTE * missing
    return "".join(paragraphs)


def normalize_minus_bullets(text: str) -> str:
    """Rewrite a line-initial minus sign used as a list bullet to a hyphen.

    Args:
        text: A stem or an option.

    Returns:
        The text with every minus-sign bullet replaced by a hyphen.
    """
    return MINUS_BULLET_PATTERN.sub(r"\1-", text)


def unify_roman_marker_dashes(text: str) -> str:
    """Make the roman assertion markers of one stem use a single dash form.

    Only fires when the stem mixes dash *characters* — ENA18-Q01 prints ``I-``
    for the first three assertions and ``IV –`` for the fourth. Spacing after
    the marker varies harmlessly across twenty other ENA18 stems, so it is not
    part of the trigger and those stems are left exactly as printed.

    Args:
        text: A stem.

    Returns:
        The stem with every roman marker rewritten as ``<numeral>- `` when the
        dash characters disagreed, and unchanged otherwise.
    """
    matches = list(ROMAN_DASH_MARKER_PATTERN.finditer(text))
    if len({match.group(3) for match in matches}) < 2:
        return text
    return ROMAN_DASH_MARKER_PATTERN.sub(r"\1\2- ", text)


def normalize_extraction_noise(text: str) -> str:
    """Apply every extraction-noise fix to one stem or option.

    The order matters: the bullet and marker fixes look at line starts, which
    the space collapse would otherwise leave untouched but the quote and
    instruction fixes look at line ends.

    Args:
        text: A stem or an option, as segmented out of the PDF.

    Returns:
        The cleaned text.
    """
    cleaned = unicodedata.normalize("NFC", text)
    cleaned = normalize_minus_bullets(cleaned)
    cleaned = unify_roman_marker_dashes(cleaned)
    cleaned = collapse_space_runs(cleaned)
    cleaned = close_unbalanced_quotes(cleaned)
    cleaned = strip_platform_instruction(cleaned)
    return cleaned.strip()
