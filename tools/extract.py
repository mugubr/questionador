"""Turn the exam PDFs in ``exams/`` into ``data/raw-questions.json``.

One deterministic pass: cut the paper into questions, split each question into
a stem and four options, and clean the header and footer noise. Anything that
does not resolve mechanically is marked for review with the reason, rather than
guessed at.

The parsing functions take text and return structures, so they are exercised
with inline strings; only `read_paper_text`, `pdftotext_version` and `main`
touch a subprocess or the filesystem.

Usage:
    python -m tools extract
    python -m tools extract --report-only
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from tools import config, configure_stdio
from tools.config import EXAM_PAPERS, ExamPaper
from tools.models import OptionLetter, ParsedBlock, ParseStatus, RawQuestion
from tools.text_cleanup import (
    find_residue,
    has_side_by_side_columns,
    mentions_column_matching,
    normalize_extraction_noise,
    strip_noise_lines,
)

# The two question markers that coexist in the collection.
QUESTION_MARKER_PATTERN = re.compile(
    r"^[ \t]*(?:QUESTÃO|Questão)[ \t]+(\d{1,2})\.?[ \t]*$"
)

# The space after the parenthesis is optional: ENA18-Q37 prints "c)As
# conferências". The content is not — a bare "a)" does not open an option.
OPTION_PATTERN = re.compile(r"^[ \t]*([a-d])\)[ \t]*(\S.*)$")

PDFTOTEXT = "pdftotext"


class ExtractionError(RuntimeError):
    """Raised when a paper cannot be turned into questions."""


class ToolchainError(RuntimeError):
    """Raised when the required build of ``pdftotext`` is not available."""


def pdftotext_version() -> str:
    """Locate ``pdftotext`` and confirm it is the poppler build.

    Git for Windows ships Xpdf under the same name. Xpdf writes Latin-1 and
    picks different dash characters, so it silently produces a different bank
    from the same PDFs. Refusing to run is the only safe answer.

    Returns:
        The reported version, for example ``25.07.0``.

    Raises:
        ToolchainError: If the binary is missing, fails to report a version,
            or is not poppler.
    """
    if shutil.which(PDFTOTEXT) is None:
        raise ToolchainError(
            "pdftotext was not found on PATH. Install poppler-utils and put its "
            "bin directory ahead of anything else that provides pdftotext."
        )

    result = subprocess.run(
        [PDFTOTEXT, "-v"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    # poppler prints its banner on stderr; keep both streams so a build that
    # chooses stdout is still read correctly.
    banner = f"{result.stdout}\n{result.stderr}"

    if "poppler" not in banner.lower():
        raise ToolchainError(
            "pdftotext on PATH is not the poppler build. It reported:\n"
            f"{banner.strip()}\n"
            "Xpdf emits Latin-1 text and different dash characters, which "
            "produces a different question bank from the same PDFs."
        )

    match = re.search(r"pdftotext\s+version\s+(\S+)", banner, re.IGNORECASE)
    if match is None:
        raise ToolchainError(
            f"could not read the pdftotext version from:\n{banner.strip()}"
        )
    return match.group(1)


def pdf_to_text(pdf_path: Path) -> str:
    """Run ``pdftotext -layout -enc UTF-8`` over one PDF.

    Args:
        pdf_path: The PDF to read.

    Returns:
        The layout-preserving text of the whole document.

    Raises:
        ExtractionError: If the file is missing, pdftotext fails, or the PDF
            has no usable text layer.
    """
    if not pdf_path.exists():
        raise ExtractionError(f"PDF not found: {pdf_path}")

    result = subprocess.run(
        [PDFTOTEXT, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    if result.returncode != 0:
        raise ExtractionError(
            f"pdftotext exited with {result.returncode} on {pdf_path.name}: "
            f"{result.stderr.strip() or '(no stderr)'}"
        )

    text = result.stdout
    useful_lines = [line for line in text.splitlines() if line.strip()]
    if len(useful_lines) < config.MINIMUM_TEXT_LINES:
        raise ExtractionError(
            f"{pdf_path.name} produced only {len(useful_lines)} lines of text. "
            "The PDF probably has no text layer and would need OCR."
        )
    return text


def read_paper_text(paper: ExamPaper) -> str:
    """Read one exam paper and remove its header and footer lines.

    Args:
        paper: The paper to read.

    Returns:
        The paper's text, ready to be segmented into questions.

    Raises:
        ExtractionError: If the PDF cannot be read.
    """
    return strip_noise_lines(pdf_to_text(paper.pdf_path))


def split_question_block(lines: Sequence[str]) -> ParsedBlock:
    """Split the lines of one question into its stem and its options.

    An option only opens when its letter is the next one in the a-b-c-d
    sequence, so a stray "a)" inside a stem cannot restart collection and
    swallow the rest of the question. A line that opens nothing continues the
    option being collected, because the PDF wraps long options across lines.

    Once all four options are closed, a blank line ends the question: whatever
    follows is trailing text, not part of option `d`. ENA18-Q40 is why —
    "BOA PROVA!" sits under the last option of the last page and used to be
    appended to `d` without a word of complaint.

    Args:
        lines: The lines of one question block, marker line excluded.

    Returns:
        The stem, the options found, and any trailing text.
    """
    letters = [str(letter) for letter in OptionLetter.sequence()]
    stem_lines: list[str] = []
    collected: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    trailing: list[str] = []
    options_closed = False

    for line in lines:
        match = OPTION_PATTERN.match(line)
        expected = letters[len(order)] if len(order) < len(letters) else None
        if match is not None and match.group(1) == expected:
            current = match.group(1)
            order.append(current)
            collected[current] = [match.group(2).strip()]
            options_closed = False
            continue

        if current is None:
            stem_lines.append(line)
            continue

        if not line.strip():
            if len(order) == len(letters):
                options_closed = True
            continue

        if options_closed:
            trailing.append(line.strip())
        else:
            collected[current].append(line.strip())

    options = {letter: " ".join(parts).strip() for letter, parts in collected.items()}
    return ParsedBlock(
        stem="\n".join(stem_lines), options=options, trailing=tuple(trailing)
    )


def normalize_stem(text: str) -> str:
    """Trim each line of a stem and collapse repeated blank lines.

    ``pdftotext -layout`` indents every line to the column the paper printed it
    in. The indentation carries no meaning once the stem is rendered as text,
    while the line breaks between assertions do, so the breaks are kept and the
    indentation is not.

    Args:
        text: The stem as it came out of the block split.

    Returns:
        The stem with each line stripped and no repeated blank lines.
    """
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped and (not kept or not kept[-1]):
            continue
        kept.append(stripped)
    return "\n".join(kept).strip()


def count_option_openers(lines: Sequence[str]) -> dict[str, int]:
    """Count how often each option letter opens a line in one block.

    Args:
        lines: The lines of one question block.

    Returns:
        A count per letter, including the letters that never open a line.
    """
    counts = {str(letter): 0 for letter in OptionLetter.sequence()}
    for line in lines:
        match = OPTION_PATTERN.match(line)
        if match is not None:
            counts[match.group(1)] += 1
    return counts


def detect_issues(
    block: ParsedBlock, stem: str, lines: Sequence[str]
) -> tuple[str, ...]:
    """List everything that makes a parsed question unusable as extracted.

    Every check runs over the stem *and* every option. A page footer inside
    option `d` is as wrong as one inside the stem, and checking only the stem
    is how thirteen of them reached the published bank.

    Args:
        block: The split question, before the noise normalisation.
        stem: The stem after `normalize_stem`, before the noise normalisation.
        lines: The lines of the block, used to spot a repeated a)-d) set.

    Returns:
        One message per problem, in the order the checks run. Empty when the
        question parsed cleanly.
    """
    letters = [str(letter) for letter in OptionLetter.sequence()]
    issues: list[str] = []

    if len(block.options) != len(letters):
        issues.append(f"{len(block.options)} options instead of {len(letters)}")

    # A second a)-d) set in the same block means the first one belongs to the
    # stem, as in a matching question. Without this the parser takes the wrong
    # set and glues the real one inside option d.
    counts = count_option_openers(lines)
    repeated = [letter for letter in letters if counts[letter] > 1]
    if repeated:
        issues.append(
            f"duplicated a)-d) set ({', '.join(repeated)}) — the first one probably "
            "belongs to the stem"
        )

    if block.trailing:
        preview = " ".join(block.trailing)
        if len(preview) > 60:
            preview = f"{preview[:60]}..."
        issues.append(f"text after the last option: {preview!r}")

    fields: list[tuple[str, str]] = [("stem", stem)]
    fields += [
        (f"option {letter}", block.options[letter])
        for letter in letters
        if letter in block.options
    ]

    for name, value in fields:
        if has_side_by_side_columns(value):
            issues.append(
                f"{name}: two columns rendered side by side — rewrite as linear text"
            )
        elif mentions_column_matching(value):
            issues.append(
                f"{name}: column-matching wording — confirm the layout resolved"
            )

        residue = find_residue(value)
        if residue:
            issues.append(f"{name}: page header or footer residue {list(residue)}")

    if len(stem) < config.MINIMUM_STEM_LENGTH:
        issues.append(f"stem shorter than {config.MINIMUM_STEM_LENGTH} characters")

    return tuple(issues)


def find_question_starts(lines: Sequence[str]) -> list[tuple[int, int]]:
    """Locate every question marker in a paper.

    Args:
        lines: The lines of the whole paper, noise already removed.

    Returns:
        One ``(line index, question number)`` pair per marker, in order.
    """
    starts: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = QUESTION_MARKER_PATTERN.match(line)
        if match is not None:
            starts.append((index, int(match.group(1))))
    return starts


def segment_questions(text: str, paper: ExamPaper) -> list[RawQuestion]:
    """Cut one paper's text into questions.

    Args:
        text: The paper's text, noise already removed.
        paper: The paper being segmented, for the id prefix.

    Returns:
        One `RawQuestion` per marker found, in the order they are printed.
    """
    lines = text.splitlines()
    starts = find_question_starts(lines)

    questions: list[RawQuestion] = []
    for position, (index, number) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        block_lines = lines[index + 1 : end]

        block = split_question_block(block_lines)
        stem = normalize_stem(block.stem)
        issues = detect_issues(block, stem, block_lines)

        questions.append(
            RawQuestion(
                id=f"{paper.id}-Q{number:02d}",
                exam=paper.id,
                number=number,
                stem=normalize_extraction_noise(stem),
                options={
                    letter: normalize_extraction_noise(value)
                    for letter, value in block.options.items()
                },
                parse_status=ParseStatus.OK if not issues else ParseStatus.REVIEW,
                issues=issues,
            )
        )

    return questions


def check_paper(questions: Sequence[RawQuestion], paper: ExamPaper) -> None:
    """Confirm a paper produced the questions the registry says it holds.

    Args:
        questions: The questions segmented out of the paper.
        paper: The paper being checked.

    Raises:
        ExtractionError: If the count or the numbering disagrees with the
            registry in `tools.config`.
    """
    numbers = [question.number for question in questions]
    if len(questions) != paper.expected_questions:
        raise ExtractionError(
            f"{paper.file}: expected {paper.expected_questions} questions, "
            f"segmented {len(questions)}. Numbers found: {numbers}"
        )
    if numbers != list(range(1, paper.expected_questions + 1)):
        raise ExtractionError(
            f"{paper.file}: numbering is not contiguous 1..N: {numbers}"
        )


def extract_all() -> list[RawQuestion]:
    """Extract every paper in the registry, in registry order.

    Returns:
        Every question of every paper.

    Raises:
        ExtractionError: If any paper fails to read or to segment.
    """
    questions: list[RawQuestion] = []
    for paper in EXAM_PAPERS:
        of_paper = segment_questions(read_paper_text(paper), paper)
        check_paper(of_paper, paper)
        flagged = [
            question
            for question in of_paper
            if question.parse_status is ParseStatus.REVIEW
        ]
        mark = "OK" if not flagged else f"{len(flagged)} to review"
        print(f"  {paper.id:<10} {len(of_paper):>3} questions   {mark}")
        questions.extend(of_paper)

    if len(questions) != config.EXPECTED_QUESTION_TOTAL:
        raise ExtractionError(
            f"total {len(questions)}, expected {config.EXPECTED_QUESTION_TOTAL}"
        )
    return questions


def write_raw_questions(questions: Sequence[RawQuestion], destination: Path) -> None:
    """Write the raw questions as the committed extraction anchor.

    Written with an explicit LF newline so a rebuild on Windows does not turn
    into a whole-file diff on Linux.

    Args:
        questions: The questions to write, in publication order.
        destination: Where to write ``raw-questions.json``.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = [question.to_json() for question in questions]
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the extraction from the command line.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` by default.

    Returns:
        0 on success, 1 when a paper could not be extracted.
    """
    configure_stdio()
    parser = argparse.ArgumentParser(
        prog="python -m tools extract",
        description=(
            "Extract the questions of exams/*.pdf into data/raw-questions.json."
        ),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="print the report without writing data/raw-questions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=config.RAW_QUESTIONS_PATH,
        help="where to write the extraction anchor (default: data/raw-questions.json)",
    )
    args = parser.parse_args(argv)

    try:
        version = pdftotext_version()
    except ToolchainError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"pdftotext (poppler) {version}")
    print("Extracting papers:\n")

    try:
        questions = extract_all()
    except ExtractionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    flagged = [
        question
        for question in questions
        if question.parse_status is ParseStatus.REVIEW
    ]
    print(
        f"\nTotal: {len(questions)} questions "
        f"({config.EXPECTED_QUESTION_TOTAL} expected)"
    )

    if flagged:
        print(f"\nREPORT - {len(flagged)} question(s) need review:\n")
        for question in flagged:
            print(f"  {question.id}: {'; '.join(question.issues)}")
    else:
        print("\nNo question flagged for review.")

    if not args.report_only:
        write_raw_questions(questions, args.output)
        print(f"\nWritten: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
