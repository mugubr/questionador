"""Read the official answer keys published alongside every exam paper.

All seven files share one shape: a QUESTÃO | RESPOSTA CORRETA table, one row
per question. Three details the format hides and this module has to know:

- The six 2020-2025 keys warn that "as questões e as alternativas foram
  aleatorizadas no sistema Moodle", and then state that "este é o gabarito
  referente ao caderno de questões conforme publicado". The letter is therefore
  valid for the published booklet, which is exactly the PDF the questions were
  extracted from, so matching by question number holds.
- The ENA18 key carries no such sentence, and needs none: the booklet published
  with it is byte-identical to ``exams/Prova_ENA18.pdf`` (MD5
  ``c4a2b9a0a4c417341bebbb7a48be89d1``), so there is no separate randomised
  booklet for the numbering to drift against. That match also settles which
  paper it belongs to — PROFNIT ran two ENA18 Suplementar papers for ingresso
  2018.02, and the 26/MAI/2018 one annuls questions 6 and 21 while ours, of
  30/JUN/2018, annuls nothing.
- A key may withdraw a question by printing ANULADA where a letter belongs.
  That is an answer of its own — "this question has none" — not a missing row.

`parse_answer_key` is pure and is where the format lives; the rest is a thin
wrapper around `pdftotext`.

Usage:
    python -m tools.answer_keys
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence

from tools import configure_stdio
from tools.config import EXAM_PAPERS, ExamPaper
from tools.extract import ExtractionError, pdf_to_text
from tools.models import OptionLetter

# What a key prints instead of a letter when it withdraws a question.
ANNULLED_MARKER = "ANULADA"

# One table cell, as laid out by pdftotext: "     1                        C".
# Matched anywhere in a line rather than against the whole of it, because the
# ENA18 key prints its forty rows in two columns and pdftotext puts questions 1
# and 21 on the same line. The whitespace boundaries are what keep "18 de
# novembro de 2023" in a footer from reading as question 18, answer d.
ANSWER_CELL_PATTERN = re.compile(
    rf"(?<!\S)(\d{{1,2}})\s+([A-Da-d]|{ANNULLED_MARKER})(?!\S)"
)


class AnswerKeyError(RuntimeError):
    """Raised when an answer key is missing, malformed, or incomplete."""


def parse_answer_key(
    text: str, expected: int, source: str
) -> dict[int, OptionLetter | None]:
    """Read the question-to-letter table out of an answer-key PDF's text.

    Args:
        text: The layout-preserving text of the answer-key PDF.
        expected: How many questions the key must cover.
        source: A name for the key, used in error messages.

    Returns:
        The correct letter for every question number, 1..expected. A number
        maps to None when the key annulled that question, which is a published
        fact about it and not an absence.

    Raises:
        AnswerKeyError: If a question repeats, an answer is missing, or the key
            covers a question the paper does not have.
    """
    answers: dict[int, OptionLetter | None] = {}
    for line in text.splitlines():
        for match in ANSWER_CELL_PATTERN.finditer(line):
            number = int(match.group(1))
            cell = match.group(2)
            letter = None if cell == ANNULLED_MARKER else OptionLetter(cell.lower())
            if number in answers:
                raise AnswerKeyError(
                    f"{source}: question {number} appears more than once"
                )
            answers[number] = letter

    missing = [number for number in range(1, expected + 1) if number not in answers]
    if missing:
        raise AnswerKeyError(
            f"{source}: no answer for question(s) {missing}. "
            f"Found {len(answers)} of {expected}."
        )

    unexpected = sorted(number for number in answers if number > expected)
    if unexpected:
        raise AnswerKeyError(f"{source}: unexpected question(s) {unexpected}")

    return answers


def load_answer_key(paper: ExamPaper) -> dict[int, OptionLetter | None]:
    """Read the published answer key of one exam paper.

    Args:
        paper: The paper whose key should be read.

    Returns:
        The correct letter for every question number of that paper, None where
        the key annulled the question.

    Raises:
        AnswerKeyError: If the paper has no key, the PDF is missing, or the
            table does not cover the paper.
    """
    key_path = paper.answer_key_path
    if key_path is None:
        raise AnswerKeyError(f"{paper.id} has no published answer key")
    if not key_path.exists():
        raise AnswerKeyError(f"{paper.id}: answer key not found: {key_path}")

    try:
        text = pdf_to_text(key_path)
    except ExtractionError as error:
        raise AnswerKeyError(f"{paper.id}: {error}") from error

    return parse_answer_key(text, paper.expected_questions, key_path.name)


def load_all() -> dict[str, dict[int, OptionLetter | None]]:
    """Read every published answer key, in registry order.

    Returns:
        The answers of each paper that has a published key, keyed by paper id.

    Raises:
        AnswerKeyError: If any key cannot be read.
    """
    return {
        paper.id: load_answer_key(paper)
        for paper in EXAM_PAPERS
        if paper.has_official_answer_key
    }


def format_key(answers: Mapping[int, OptionLetter | None]) -> str:
    """Render one answer key as a single compact line.

    Args:
        answers: The letters keyed by question number, None where annulled.

    Returns:
        A string such as ``1c 2a 3-``, where ``-`` marks an annulled question.
    """
    return " ".join(f"{number}{answers[number] or '-'}" for number in sorted(answers))


def main(argv: Sequence[str] | None = None) -> int:
    """Print every published answer key from the command line.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` by default.

    Returns:
        0 on success, 1 when a key could not be read.
    """
    configure_stdio()
    parser = argparse.ArgumentParser(
        prog="python -m tools.answer_keys",
        description="Print the official answer keys published in exams/.",
    )
    parser.parse_args(argv)

    try:
        keys = load_all()
    except AnswerKeyError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for exam_id, answers in keys.items():
        print(f"{exam_id} ({len(answers)} answers): {format_key(answers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
