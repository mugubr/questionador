"""The published answer keys: their printed format and their committed table.

All seven key PDFs share one shape: a QUESTÃO | RESPOSTA CORRETA table, one row
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

Nothing here runs ``pdftotext``. `parse_answer_key` is pure and is where the
format lives; `read_answer_keys` and `write_answer_keys` are the two ends of
``data/answer-keys.json``, the artifact `extract` commits so that `build` never
has to open a PDF. Reading a key PDF is `tools.extract.load_answer_key`, which
is where the subprocess belongs.

Usage:
    python -m tools.answer_keys
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools import config, configure_stdio
from tools.models import OptionLetter, parse_toolchain

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

# One paper's key: the correct letter of every question number, None where the
# key printed ANULADA. This is what `parse_answer_key` returns and what
# ``data/answer-keys.json`` round-trips.
AnswerKeyTable = dict[int, OptionLetter | None]

# The only keys data/answer-keys.json may carry at its top level.
ANSWER_KEYS_FILE_KEYS = frozenset({"toolchain", "keys"})


class AnswerKeyError(RuntimeError):
    """Raised when an answer key is missing, malformed, or incomplete."""


def parse_answer_key(text: str, expected: int, source: str) -> AnswerKeyTable:
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
    answers: AnswerKeyTable = {}
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


def format_key(answers: Mapping[int, OptionLetter | None]) -> str:
    """Render one answer key as a single compact line.

    Args:
        answers: The letters keyed by question number, None where annulled.

    Returns:
        A string such as ``1c 2a 3-``, where ``-`` marks an annulled question.
    """
    return " ".join(f"{number}{answers[number] or '-'}" for number in sorted(answers))


def write_answer_keys(
    keys: Mapping[str, Mapping[int, OptionLetter | None]],
    toolchain: Mapping[str, str],
    destination: Path,
) -> None:
    """Write the parsed keys of every paper as a committed artifact.

    The poppler version is stamped here rather than by whoever reads the file,
    because this is the step that actually ran the tool: what the stamp
    promises is that *this* build of ``pdftotext`` produced *these* letters.

    Numbers become strings because JSON has no integer keys; `read_answer_keys`
    turns them back. Written with an explicit LF newline so a rebuild on
    Windows does not turn into a whole-file diff on Linux.

    Args:
        keys: The parsed key of each paper, by exam id, in registry order.
        toolchain: The version of every external tool that produced them.
        destination: Where to write ``answer-keys.json``.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "toolchain": dict(toolchain),
        "keys": {
            exam_id: {
                str(number): None if answers[number] is None else str(answers[number])
                for number in sorted(answers)
            }
            for exam_id, answers in keys.items()
        },
    }
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_answer_keys(path: Path) -> tuple[dict[str, AnswerKeyTable], dict[str, str]]:
    """Read the committed answer-key artifact back into the shape it was written from.

    Args:
        path: ``data/answer-keys.json``.

    Returns:
        The parsed key of each paper, by exam id, and the toolchain that
        produced them.

    Raises:
        AnswerKeyError: If the file is missing, is not valid JSON, or does not
            hold the expected shape.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as error:
        raise AnswerKeyError(
            f"{path} is missing. Run 'python -m tools extract' to produce it."
        ) from error
    except OSError as error:
        raise AnswerKeyError(f"could not read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise AnswerKeyError(f"invalid JSON in {path}: {error}") from error

    if not isinstance(payload, dict):
        raise AnswerKeyError(
            f"{path}: expected a JSON object, found {type(payload).__name__}"
        )
    unknown = sorted(set(payload) - ANSWER_KEYS_FILE_KEYS)
    if unknown:
        raise AnswerKeyError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    try:
        toolchain = parse_toolchain(payload.get("toolchain"))
    except ValueError as error:
        raise AnswerKeyError(f"{path}: {error}") from error

    declared = payload.get("keys")
    if not isinstance(declared, dict) or not declared:
        raise AnswerKeyError(f"{path}: 'keys' must be a non-empty object")

    keys: dict[str, AnswerKeyTable] = {}
    for exam_id, rows in declared.items():
        if not isinstance(rows, dict) or not rows:
            raise AnswerKeyError(f"{path}: {exam_id} must map to a non-empty object")
        keys[str(exam_id)] = dict(
            _read_answer_row(exam_id, raw_number, raw_letter, path)
            for raw_number, raw_letter in rows.items()
        )
    return keys, toolchain


def _read_answer_row(
    exam_id: str,
    raw_number: str,
    raw_letter: Any,  # noqa: ANN401 - one decoded JSON value, validated here.
    path: Path,
) -> tuple[int, OptionLetter | None]:
    """Turn one stored ``"14": null`` row back into a number and a letter.

    Args:
        exam_id: The paper the row belongs to, for the error message.
        raw_number: The question number as JSON stored it, a string.
        raw_letter: The letter as JSON stored it, or None when annulled.
        path: The file being read, for the error message.

    Returns:
        The question number and its letter, None where the key annulled it.

    Raises:
        AnswerKeyError: If the number is not an integer or the letter is not
            one of a-d.
    """
    where = f"{path}: {exam_id}"
    try:
        number = int(raw_number)
    except ValueError as error:
        message = f"{where}: {raw_number!r} is not a question number"
        raise AnswerKeyError(message) from error
    if raw_letter is None:
        return number, None
    try:
        return number, OptionLetter(raw_letter)
    except ValueError as error:
        raise AnswerKeyError(
            f"{where}: question {number} has an unknown letter {raw_letter!r}"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    """Print every committed answer key from the command line.

    Reads ``data/answer-keys.json`` rather than the key PDFs, so it needs no
    poppler and shows exactly the letters the bank was built from.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` by default.

    Returns:
        0 on success, 1 when the artifact could not be read.
    """
    configure_stdio()
    parser = argparse.ArgumentParser(
        prog="python -m tools.answer_keys",
        description=(
            "Print the official answer keys committed in data/answer-keys.json."
        ),
    )
    parser.parse_args(argv)

    try:
        keys, toolchain = read_answer_keys(config.ANSWER_KEYS_PATH)
    except AnswerKeyError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"pdftotext (poppler) {toolchain.get('pdftotext', 'unknown')}")
    for exam_id, answers in keys.items():
        print(f"{exam_id} ({len(answers)} answers): {format_key(answers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
