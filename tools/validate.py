"""Check a published question bank against the contract in `data/schema.json`.

Implemented with the standard library so the project keeps no runtime
dependency. `data/schema.json` is authoritative and this module implements it;
a rule that lives in one and not the other is a bug, so the field lists here
are the same ones the schema declares.

Every error names the question and the field, and all of them are reported in
one run.

Usage:
    python -m tools validate [path/to/question-bank.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools import config, configure_stdio
from tools.config import EXAM_PAPERS_BY_ID
from tools.models import (
    AnswerSource,
    Confidence,
    ErrorLog,
    ExcludedReason,
    OptionLetter,
)
from tools.text_cleanup import find_residue

QUESTION_ID_PATTERN = re.compile(r"^[A-Z0-9-]+-Q\d{2}$")
EXAM_ID_PATTERN = re.compile(r"^[A-Z0-9-]+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOPIC_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

ROOT_FIELDS = frozenset(
    {"version", "generatedAt", "toolchain", "exams", "topics", "questions"}
)
EXAM_FIELDS = frozenset({"id", "title", "date", "file", "hasOfficialAnswerKey"})
TOPIC_FIELDS = frozenset({"id", "label", "definition"})
QUESTION_FIELDS = frozenset(
    {
        "id",
        "exam",
        "number",
        "topic",
        "stem",
        "options",
        "answer",
        "duplicateOf",
        "knownDefects",
        "excludedReason",
    }
)
ANSWER_FIELDS = frozenset(
    {"letter", "source", "confidence", "reference", "explanation", "rationale"}
)

REQUIRED_TOOLS = ("pdftotext",)

LETTERS = tuple(str(letter) for letter in OptionLetter.sequence())
SOURCES = tuple(str(source) for source in AnswerSource)
CONFIDENCES = tuple(str(level) for level in Confidence)
EXCLUDED_REASONS = tuple(str(reason) for reason in ExcludedReason)


def is_nonempty_text(value: Any) -> bool:  # noqa: ANN401 - any JSON value.
    """Report whether a value is a string with something in it.

    Args:
        value: Any decoded JSON value.

    Returns:
        True when the value is a non-blank string.
    """
    return isinstance(value, str) and value.strip() != ""


def validate_root(
    bank: Any,  # noqa: ANN401 - the bank is untrusted JSON, not yet a dict.
    errors: ErrorLog,
) -> bool:
    """Check the fields the bank carries around its two arrays.

    Args:
        bank: The decoded bank.
        errors: Where to record problems.

    Returns:
        True when the bank is an object and can be inspected further.
    """
    if not isinstance(bank, dict):
        errors.add("root", "the bank must be a JSON object")
        return False

    unexpected = sorted(set(bank) - ROOT_FIELDS)
    if unexpected:
        errors.add("root", f"unexpected field(s): {', '.join(unexpected)}")

    if bank.get("version") != config.BANK_VERSION:
        errors.add(
            "version", f"expected {config.BANK_VERSION}, found {bank.get('version')!r}"
        )

    generated_at = bank.get("generatedAt")
    if not isinstance(generated_at, str) or not DATE_PATTERN.match(generated_at):
        errors.add("generatedAt", f"expected YYYY-MM-DD, found {generated_at!r}")

    toolchain = bank.get("toolchain")
    if not isinstance(toolchain, dict):
        errors.add("toolchain", "must be an object of tool name to version")
    else:
        for tool in REQUIRED_TOOLS:
            if not is_nonempty_text(toolchain.get(tool)):
                errors.add("toolchain", f"missing the version of {tool}")
        for tool, version in toolchain.items():
            if not isinstance(version, str):
                errors.add("toolchain", f"{tool} version must be a string")

    return True


def validate_exams(bank: dict[str, Any], errors: ErrorLog) -> set[str]:
    """Check ``exams[]`` and collect the ids the questions may refer to.

    Args:
        bank: The decoded bank.
        errors: Where to record problems.

    Returns:
        Every valid exam id found. Empty when the array itself is unusable.
    """
    exams = bank.get("exams")
    if not isinstance(exams, list) or not exams:
        errors.add("exams", "must be a non-empty array")
        return set()

    ids: set[str] = set()
    for index, exam in enumerate(exams):
        where = f"exams[{index}]"
        if not isinstance(exam, dict):
            errors.add(where, "must be an object")
            continue

        unexpected = sorted(set(exam) - EXAM_FIELDS)
        if unexpected:
            errors.add(where, f"unexpected field(s): {', '.join(unexpected)}")

        exam_id = exam.get("id")
        if not is_nonempty_text(exam_id) or not EXAM_ID_PATTERN.match(str(exam_id)):
            errors.add(where, f"invalid id: {exam_id!r}")
        elif exam_id in ids:
            errors.add(where, f"duplicate id: {exam_id}")
        else:
            ids.add(str(exam_id))
            where = str(exam_id)

        if not is_nonempty_text(exam.get("title")):
            errors.add(where, "title is missing or empty")

        if not is_nonempty_text(exam.get("file")):
            errors.add(where, "file is missing or empty")

        if not isinstance(exam.get("hasOfficialAnswerKey"), bool):
            errors.add(where, "hasOfficialAnswerKey must be a boolean")

        exam_date = exam.get("date")
        if not isinstance(exam_date, str) or not DATE_PATTERN.match(exam_date):
            errors.add(where, f"date must be YYYY-MM-DD, found {exam_date!r}")

    return ids


def validate_topics(bank: dict[str, Any], errors: ErrorLog) -> set[str]:
    """Check ``topics[]`` and collect the slugs the questions may refer to.

    Args:
        bank: The decoded bank.
        errors: Where to record problems.

    Returns:
        Every valid topic slug found. Empty when the array itself is unusable.
    """
    topics = bank.get("topics")
    if not isinstance(topics, list) or not topics:
        errors.add("topics", "must be a non-empty array")
        return set()

    slugs: set[str] = set()
    for index, topic in enumerate(topics):
        where = f"topics[{index}]"
        if not isinstance(topic, dict):
            errors.add(where, "must be an object")
            continue

        unexpected = sorted(set(topic) - TOPIC_FIELDS)
        if unexpected:
            errors.add(where, f"unexpected field(s): {', '.join(unexpected)}")

        topic_id = topic.get("id")
        if not is_nonempty_text(topic_id) or not TOPIC_ID_PATTERN.match(str(topic_id)):
            errors.add(where, f"invalid id: {topic_id!r} (expected kebab-case)")
        elif topic_id in slugs:
            errors.add(where, f"duplicate id: {topic_id}")
        else:
            slugs.add(str(topic_id))
            where = str(topic_id)

        for field in ("label", "definition"):
            if not is_nonempty_text(topic.get(field)):
                errors.add(where, f"{field} is missing or empty")

    return slugs


def validate_options(question: dict[str, Any], where: str, errors: ErrorLog) -> None:
    """Check that a question carries exactly the four options a-d.

    Args:
        question: The decoded question.
        where: The question id, for the error messages.
        errors: Where to record problems.
    """
    options = question.get("options")
    if not isinstance(options, dict):
        errors.add(where, "options must be an object")
        return

    missing = [letter for letter in LETTERS if letter not in options]
    if missing:
        errors.add(where, f"missing option(s): {', '.join(missing)}")

    unexpected = sorted(set(options) - set(LETTERS))
    if unexpected:
        errors.add(where, f"unexpected option(s): {', '.join(unexpected)}")

    for letter in LETTERS:
        if letter in options and not is_nonempty_text(options[letter]):
            errors.add(where, f"option {letter} is empty")


def validate_answer(question: dict[str, Any], where: str, errors: ErrorLog) -> None:
    """Check the answer and the provenance rules that go with its source.

    A question may leave `letter` out only when it carries an `excludedReason`:
    the official key annulled it, so there is no correct option to record. Any
    other answer without a letter is an answer the app cannot grade.

    Args:
        question: The decoded question.
        where: The question id, for the error messages.
        errors: Where to record problems.
    """
    answer = question.get("answer")
    if not isinstance(answer, dict):
        errors.add(where, "answer must be an object")
        return

    unexpected = sorted(set(answer) - ANSWER_FIELDS)
    if unexpected:
        errors.add(where, f"unexpected field(s) in answer: {', '.join(unexpected)}")

    if "letter" not in answer:
        if "excludedReason" not in question:
            errors.add(
                where,
                "answer.letter is missing, which only an excluded question may do",
            )
    elif answer.get("letter") not in LETTERS:
        errors.add(
            where,
            f"answer.letter must be one of {LETTERS}, found {answer.get('letter')!r}",
        )

    if not is_nonempty_text(answer.get("reference")):
        errors.add(where, "answer.reference is missing or empty")

    source = answer.get("source")
    if source not in SOURCES:
        errors.add(where, f"answer.source is invalid: {source!r}")
        return

    if source == AnswerSource.DERIVED:
        if answer.get("confidence") not in CONFIDENCES:
            errors.add(
                where,
                f"a derived answer needs confidence in {CONFIDENCES}, "
                f"found {answer.get('confidence')!r}",
            )
        if not is_nonempty_text(answer.get("rationale")):
            errors.add(where, "a derived answer needs a non-empty rationale")
        if "explanation" in answer:
            errors.add(
                where,
                "a derived answer argues for its letter in 'rationale'; "
                "'explanation' belongs to an official one",
            )
    else:
        for field in ("confidence", "rationale"):
            if field in answer:
                errors.add(where, f"an official answer must not carry {field}")
        if "explanation" in answer and not is_nonempty_text(answer["explanation"]):
            errors.add(where, "answer.explanation is present but empty")


def validate_text_fields(
    question: dict[str, Any], where: str, errors: ErrorLog
) -> None:
    """Check the stem and every option for page header or footer residue.

    Runs over the options too. A footer inside option `d` is as wrong as one
    inside the stem, and checking only the stem let thirteen of them through.

    Args:
        question: The decoded question.
        where: The question id, for the error messages.
        errors: Where to record problems.
    """
    stem = question.get("stem")
    if (
        not is_nonempty_text(stem)
        or len(str(stem).strip()) < config.MINIMUM_STEM_LENGTH
    ):
        errors.add(where, "stem is missing or too short")
        stem = None

    fields: list[tuple[str, str]] = []
    if isinstance(stem, str):
        fields.append(("stem", stem))
    options = question.get("options")
    if isinstance(options, dict):
        fields += [
            (f"option {letter}", options[letter])
            for letter in LETTERS
            if isinstance(options.get(letter), str)
        ]

    for name, value in fields:
        residue = find_residue(value)
        if residue:
            errors.add(
                where, f"{name} holds page header or footer residue: {list(residue)}"
            )


def validate_questions(
    bank: dict[str, Any], exam_ids: set[str], topic_ids: set[str], errors: ErrorLog
) -> None:
    """Check every question and the invariants that tie the bank together.

    Args:
        bank: The decoded bank.
        exam_ids: The ids declared in ``exams[]``.
        topic_ids: The slugs declared in ``topics[]``.
        errors: Where to record problems.
    """
    questions = bank.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.add("questions", "must be a non-empty array")
        return

    seen: set[str] = set()
    numbers_by_exam: dict[str, list[int]] = {}
    duplicates: dict[str, str] = {}
    used_topics: set[str] = set()

    for index, question in enumerate(questions):
        where = f"questions[{index}]"
        if not isinstance(question, dict):
            errors.add(where, "must be an object")
            continue

        question_id = question.get("id")
        if is_nonempty_text(question_id):
            where = str(question_id)

        unexpected = sorted(set(question) - QUESTION_FIELDS)
        if unexpected:
            errors.add(where, f"unexpected field(s): {', '.join(unexpected)}")

        if not is_nonempty_text(question_id) or not QUESTION_ID_PATTERN.match(
            str(question_id)
        ):
            errors.add(where, f"invalid id: {question_id!r} (expected ENA26-Q01)")
            continue
        question_id = str(question_id)
        if question_id in seen:
            errors.add(where, "duplicate id")
            continue
        seen.add(question_id)

        exam_id = question.get("exam")
        if exam_id not in exam_ids:
            errors.add(where, f"exam {exam_id!r} is not declared in exams[]")

        number = question.get("number")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or not 1 <= number <= 99
        ):
            errors.add(where, f"invalid number: {number!r}")
        elif isinstance(exam_id, str):
            numbers_by_exam.setdefault(exam_id, []).append(number)
            if question_id != f"{exam_id}-Q{number:02d}":
                errors.add(
                    where, f"id disagrees with exam {exam_id!r} and number {number}"
                )

        topic = question.get("topic")
        if not is_nonempty_text(topic):
            errors.add(where, "topic is missing or empty")
        elif topic not in topic_ids:
            errors.add(where, f"topic {topic!r} is not declared in topics[]")
        else:
            used_topics.add(str(topic))

        excluded_reason = question.get("excludedReason")
        if excluded_reason is not None and excluded_reason not in EXCLUDED_REASONS:
            errors.add(
                where,
                f"excludedReason must be one of {EXCLUDED_REASONS}, "
                f"found {excluded_reason!r}",
            )

        duplicate_of = question.get("duplicateOf")
        if duplicate_of is not None:
            if not is_nonempty_text(duplicate_of):
                errors.add(where, "duplicateOf must be a non-empty question id")
            else:
                duplicates[question_id] = str(duplicate_of)

        defects = question.get("knownDefects")
        if defects is not None:
            if not isinstance(defects, list) or not defects:
                errors.add(where, "knownDefects must be a non-empty array")
            elif not all(is_nonempty_text(item) for item in defects):
                errors.add(where, "knownDefects must hold non-empty strings")

        validate_options(question, where, errors)
        validate_answer(question, where, errors)
        validate_text_fields(question, where, errors)

    for orphan in sorted(topic_ids - used_topics):
        errors.add("topics", f"topic {orphan!r} is declared but no question uses it")

    for question_id, target in sorted(duplicates.items()):
        if target not in seen:
            errors.add(
                question_id, f"duplicateOf points at {target}, which does not exist"
            )
        elif target in duplicates:
            errors.add(
                question_id,
                f"duplicateOf points at {target}, which is itself a duplicate",
            )

    for exam_id in sorted(exam_ids):
        numbers = sorted(numbers_by_exam.get(exam_id, []))
        if not numbers:
            errors.add(exam_id, "declared in exams[] but has no question")
            continue
        paper = EXAM_PAPERS_BY_ID.get(exam_id)
        if paper is not None and len(numbers) != paper.expected_questions:
            errors.add(
                exam_id,
                f"{len(numbers)} questions, expected {paper.expected_questions} "
                "according to tools/config.py",
            )
        if numbers != list(range(1, len(numbers) + 1)):
            errors.add(exam_id, f"numbering is not contiguous 1..N: {numbers}")


def validate(
    bank: Any,  # noqa: ANN401 - the bank is untrusted JSON, not yet a dict.
    expected_total: int | None = config.EXPECTED_QUESTION_TOTAL,
) -> ErrorLog:
    """Run every check over a decoded bank.

    Args:
        bank: The decoded bank.
        expected_total: How many questions the bank must hold, or None to skip
            the total check.

    Returns:
        Every problem found, empty when the bank satisfies the contract.
    """
    errors = ErrorLog()

    if not validate_root(bank, errors):
        return errors

    exam_ids = validate_exams(bank, errors)
    topic_ids = validate_topics(bank, errors)
    if not exam_ids or not topic_ids:
        # Without a usable exams[] or topics[] every question would report the
        # same "not declared" error, burying the one failure that matters.
        errors.add("questions", "not checked: exams[] or topics[] failed to validate")
        return errors

    validate_questions(bank, exam_ids, topic_ids, errors)

    questions = bank.get("questions")
    if (
        isinstance(questions, list)
        and expected_total is not None
        and len(questions) != expected_total
    ):
        errors.add(
            "questions",
            f"expected {expected_total} questions, found {len(questions)}",
        )

    return errors


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a bank from the command line.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` by default.

    Returns:
        0 when the bank satisfies the contract, 1 otherwise.
    """
    configure_stdio()
    parser = argparse.ArgumentParser(
        prog="python -m tools validate",
        description="Check a question bank against the contract in data/schema.json.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=config.QUESTION_BANK_PATH,
        help="the bank to check (default: data/question-bank.json)",
    )
    parser.add_argument(
        "--expected-total",
        type=int,
        default=config.EXPECTED_QUESTION_TOTAL,
        help="how many questions the bank must hold (0 to skip the check)",
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"ERROR: file not found: {args.path}", file=sys.stderr)
        return 1

    try:
        with args.path.open(encoding="utf-8") as handle:
            bank = json.load(handle)
    except OSError as error:
        print(f"ERROR: could not read {args.path}: {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"ERROR: invalid JSON in {args.path}: {error}", file=sys.stderr)
        return 1

    errors = validate(bank, args.expected_total or None)

    if errors:
        print(f"FAILED: {len(errors)} error(s) in {args.path}\n", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    questions = bank["questions"]
    official = sum(
        1 for q in questions if q["answer"]["source"] == AnswerSource.OFFICIAL
    )
    duplicates = sum(1 for q in questions if "duplicateOf" in q)
    excluded = sum(1 for q in questions if "excludedReason" in q)
    print(f"OK: {args.path}")
    print(f"  {len(bank['exams'])} exams, {len(questions)} questions")
    print(
        f"  {official} with an official answer key, {len(questions) - official} derived"
    )
    print(f"  {len(bank['topics'])} topics")
    print(f"  {duplicates} marked as duplicates")
    print(f"  {excluded} excluded from the draw, {len(questions) - excluded} drawable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
