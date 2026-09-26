"""Assemble the published question bank from its editable layers.

Layers, applied in this order, each one narrow and auditable:

1. ``data/raw-questions.json`` — the deterministic output of `extract`.
2. ``data/overrides.json`` — hand-written parse fixes, each with its reason.
3. ``data/answer-keys.json`` — the official key of every paper, also from
   `extract`, matched by question number.
4. ``data/answers/*.json`` — the explanation and the reference of each answer.
5. ``data/topics.json`` — the taxonomy and one topic per question.

Three artifacts come out: ``data/question-bank.json`` (canonical),
``data/question-bank.md`` (review surface) and ``docs/data/question-bank.js``
(a mechanical wrapper of the JSON, loaded by a plain script tag). The two that
can fail are rendered in full before either of them is written, so a question
the markdown cannot render never leaves a published JSON behind it. The script
is then wrapped from the JSON that was actually written, so it can never
describe a bank nobody published.

**This stage is hermetic: every byte it reads is a committed file.** It runs no
subprocess, opens no PDF, and reads no clock. The `pdftotext` version it stamps
into ``toolchain`` is copied from the extraction artifacts, which is where the
tool actually ran, and the date it stamps into ``generatedAt`` is carried from
the bank already committed unless ``--generated-at`` says otherwise. Both are
what make a rebuild from unchanged inputs produce unchanged bytes — on a
machine with no poppler at all, and tomorrow as well as today.

Usage:
    python -m tools build
    python -m tools build --generated-at 2026-08-26
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
from tools.answer_keys import AnswerKeyError, AnswerKeyTable, read_answer_keys
from tools.config import EXAM_PAPERS, EXAM_PAPERS_BY_ID
from tools.models import (
    Answer,
    AnswerSource,
    ErrorLog,
    ExamEntry,
    ExcludedReason,
    OptionLetter,
    ParseStatus,
    Question,
    QuestionBank,
    RawQuestion,
    Topic,
    parse_toolchain,
)

QUESTION_ID_PATTERN = re.compile(r"^(?P<exam>[A-Z0-9-]+)-Q(?P<number>\d{2})$")

# What `generatedAt` has to look like, checked here rather than only in
# `validate`, so a typed `--generated-at` cannot reach a committed artifact.
GENERATED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The only keys data/raw-questions.json may carry at its top level.
RAW_QUESTIONS_FILE_KEYS = frozenset({"toolchain", "questions"})

# The only keys an override entry may carry. Anything else is a typo that would
# otherwise be applied as nothing at all.
OVERRIDABLE_FIELDS = frozenset({"stem", "options"})
OVERRIDE_KEYS = OVERRIDABLE_FIELDS | frozenset({"_reason", "_verbatim"})

# The only keys an entry of data/answers/<exam>.json may carry. The letter is
# not among them: it is read from the published key, so the two can never
# disagree. Neither is the topic, which lives once in data/topics.json.
EXPLANATION_KEYS = frozenset({"explanation", "reference"})

# The only keys data/topics.json may carry at its top level.
TOPICS_FILE_KEYS = frozenset({"_reason", "topics", "assignments"})

# The only keys one taxonomy entry may carry.
TOPIC_KEYS = frozenset({"id", "label", "definition"})

# Portuguese labels for the review surface. The data stays English; the
# document a human reads is mapped through these tables and nothing else.
#
# There is no label for a derived answer because this stage cannot produce one:
# every paper in the registry has a published key and `build_answer` refuses to
# invent an answer for one that does not. The bank contract still describes a
# derived answer, and `tools/validate.py` still enforces its rules, so a future
# paper without a key has somewhere to land — but nothing here renders a state
# the data cannot reach.
SOURCE_LABELS: Mapping[AnswerSource, str] = {
    AnswerSource.OFFICIAL: "gabarito oficial",
}
EXCLUDED_REASON_LABELS: Mapping[ExcludedReason, str] = {
    ExcludedReason.ANNULLED: "anulada",
    ExcludedReason.SOURCE_BOOKLET_DEFECT: "caderno defeituoso",
}
EXCLUDED_REASON_NOTES: Mapping[ExcludedReason, str] = {
    ExcludedReason.ANNULLED: (
        "Nunca sorteada: o gabarito oficial imprime ANULADA no lugar da letra, "
        "ou seja, a própria banca retirou a questão. Ela continua no banco e na "
        "contagem do caderno porque a prova impressa realmente a numerou."
    ),
    ExcludedReason.SOURCE_BOOKLET_DEFECT: (
        "Nunca sorteada: o caderno publicado repete uma questão anterior neste "
        "número, mas o gabarito oficial dá letras diferentes às duas. Um "
        "gabarito não atribui duas letras à mesma questão, logo a prova real "
        "trazia aqui outra questão e o caderno publicado está defeituoso. A "
        "letra abaixo é a da questão repetida, que é o texto que temos; a letra "
        "que o gabarito dá a este número responde uma questão que não está no "
        "banco."
    ),
}


class BuildError(RuntimeError):
    """Raised when an input file cannot be read or has the wrong shape."""


def read_json(path: Path) -> Any:  # noqa: ANN401 - JSON decodes to any value.
    """Read one JSON file, turning every failure into a clean message.

    Args:
        path: The file to read.

    Returns:
        The decoded JSON value.

    Raises:
        BuildError: If the file is missing, unreadable, or not valid JSON.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise BuildError(f"required file is missing: {path}") from error
    except OSError as error:
        raise BuildError(f"could not read {path}: {error}") from error
    except UnicodeDecodeError as error:
        raise BuildError(f"{path} is not valid UTF-8: {error}") from error
    except json.JSONDecodeError as error:
        raise BuildError(f"invalid JSON in {path}: {error}") from error


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON file that must hold an object at its top level.

    Guards the caller from a file that decodes to a list and then explodes on
    the first ``.items()``.

    Args:
        path: The file to read.

    Returns:
        The decoded object.

    Raises:
        BuildError: If the file does not hold a JSON object.
    """
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise BuildError(
            f"{path}: expected a JSON object, found {type(payload).__name__}"
        )
    return payload


def load_topics(path: Path) -> tuple[list[Topic], dict[str, str]]:
    """Read the taxonomy and the topic of every question.

    Topic has exactly one home. It used to live twice — a `topic` field on each
    derived answer and a separate file for the officially-keyed ones — and the
    two could disagree about the same question.

    Args:
        path: ``data/topics.json``.

    Returns:
        The taxonomy in declaration order, and the topic slug of each question.

    Raises:
        BuildError: If the file is missing or does not have the expected shape.
    """
    payload = read_json_object(path)
    unknown = sorted(set(payload) - TOPICS_FILE_KEYS)
    if unknown:
        raise BuildError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    declared = payload.get("topics")
    if not isinstance(declared, list) or not declared:
        raise BuildError(f"{path}: 'topics' must be a non-empty array")

    topics: list[Topic] = []
    for index, entry in enumerate(declared):
        where = f"{path}: topics[{index}]"
        if not isinstance(entry, dict):
            raise BuildError(f"{where} is not an object")
        missing = sorted(TOPIC_KEYS - set(entry))
        if missing:
            raise BuildError(f"{where} is missing {', '.join(missing)}")
        extra = sorted(set(entry) - TOPIC_KEYS)
        if extra:
            raise BuildError(f"{where} has unknown key(s): {', '.join(extra)}")
        if not all(isinstance(entry[key], str) and entry[key].strip() for key in entry):
            raise BuildError(f"{where}: every field must be a non-empty string")
        topics.append(
            Topic(
                id=str(entry["id"]),
                label=str(entry["label"]),
                definition=str(entry["definition"]),
            )
        )

    slugs = [topic.id for topic in topics]
    duplicated = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicated:
        raise BuildError(f"{path}: duplicate topic id(s): {', '.join(duplicated)}")

    assignments = payload.get("assignments")
    if not isinstance(assignments, dict) or not assignments:
        raise BuildError(f"{path}: 'assignments' must be a non-empty object")
    for question_id, slug in assignments.items():
        if not isinstance(slug, str) or not slug.strip():
            raise BuildError(f"{path}: {question_id} must map to a non-empty string")

    return topics, {key: str(value) for key, value in assignments.items()}


def load_raw_questions(path: Path) -> tuple[list[RawQuestion], dict[str, str]]:
    """Read the committed extraction anchor and the toolchain that wrote it.

    Args:
        path: ``data/raw-questions.json``.

    Returns:
        Every extracted question, in the order it was written, and the version
        of every external tool that produced it.

    Raises:
        BuildError: If the file is missing, or does not hold a toolchain stamp
            and a list of well-formed questions. `build` never regenerates it:
            producing it means reading seven PDFs with poppler, and quietly
            doing that here is what made the build unreproducible.
    """
    if not path.exists():
        raise BuildError(
            f"{path} is missing. Run 'python -m tools extract' to produce it."
        )
    payload = read_json_object(path)
    unknown = sorted(set(payload) - RAW_QUESTIONS_FILE_KEYS)
    if unknown:
        raise BuildError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    try:
        toolchain = parse_toolchain(payload.get("toolchain"))
    except ValueError as error:
        raise BuildError(f"{path}: {error}") from error

    declared = payload.get("questions")
    if not isinstance(declared, list):
        raise BuildError(
            f"{path}: 'questions' must be a JSON array, found {type(declared).__name__}"
        )

    questions: list[RawQuestion] = []
    for index, item in enumerate(declared):
        if not isinstance(item, dict):
            raise BuildError(f"{path}: entry {index} is not an object")
        try:
            questions.append(RawQuestion.from_json(item))
        except ValueError as error:
            raise BuildError(f"{path}: {error}") from error
    return questions, toolchain


def load_official_keys(path: Path) -> tuple[dict[str, AnswerKeyTable], dict[str, str]]:
    """Read the committed answer keys and the toolchain that wrote them.

    Args:
        path: ``data/answer-keys.json``.

    Returns:
        The parsed key of each paper, by exam id, and the version of every
        external tool that produced them.

    Raises:
        BuildError: If the artifact is missing or malformed. `build` never
            regenerates it: the keys come out of seven PDFs, reading them needs
            poppler, and quietly running the tool here is exactly what made the
            build unreproducible.
    """
    try:
        return read_answer_keys(path)
    except AnswerKeyError as error:
        raise BuildError(str(error)) from error


def reconcile_toolchain(
    raw_toolchain: Mapping[str, str], keys_toolchain: Mapping[str, str]
) -> dict[str, str]:
    """Confirm both extraction artifacts name the same tool versions.

    `extract` writes the two in one run with one binary, so a disagreement
    means one of them was produced by a different run and the pair no longer
    describes a single extraction. Stamping either version into the bank would
    then claim a provenance that is not true of half the input.

    Args:
        raw_toolchain: The stamp of ``data/raw-questions.json``.
        keys_toolchain: The stamp of ``data/answer-keys.json``.

    Returns:
        The agreed versions, ready to be published as the bank's ``toolchain``.

    Raises:
        BuildError: If the two stamps differ in any tool or version.
    """
    if dict(raw_toolchain) != dict(keys_toolchain):
        raise BuildError(
            "the extraction artifacts disagree about the toolchain that "
            f"produced them: {config.RAW_QUESTIONS_PATH.name} records "
            f"{dict(raw_toolchain)} and {config.ANSWER_KEYS_PATH.name} records "
            f"{dict(keys_toolchain)}. One of them is stale - run "
            "'python -m tools extract' to rebuild both from the PDFs."
        )
    return dict(raw_toolchain)


def check_extraction_is_current(
    raw_questions: Sequence[RawQuestion],
    official_keys: Mapping[str, Mapping[int, OptionLetter | None]],
) -> None:
    """Confirm the committed extraction still describes the registry.

    Adding a paper to `tools.config` without re-running `extract` leaves the
    artifacts covering the old set. The build would then fail somewhere far
    from the cause — a question with no key, a paper with no questions — so the
    mismatch is named here instead, with the command that fixes it.

    Args:
        raw_questions: The questions read from the extraction anchor.
        official_keys: The keys read from the answer-key artifact.

    Raises:
        BuildError: If either artifact covers a different set of papers, or a
            key does not cover its paper's questions.
    """
    errors = ErrorLog()
    extracted = {question.exam for question in raw_questions}
    registered = {paper.id for paper in EXAM_PAPERS}
    keyed = {paper.id for paper in EXAM_PAPERS if paper.has_official_answer_key}

    for exam_id in sorted(registered - extracted):
        errors.add(config.RAW_QUESTIONS_PATH.name, f"holds no question of {exam_id}")
    for exam_id in sorted(extracted - registered):
        errors.add(
            config.RAW_QUESTIONS_PATH.name,
            f"holds questions of {exam_id}, which tools/config.py does not register",
        )
    for exam_id in sorted(keyed - set(official_keys)):
        errors.add(config.ANSWER_KEYS_PATH.name, f"holds no key for {exam_id}")
    for exam_id in sorted(set(official_keys) - keyed):
        errors.add(
            config.ANSWER_KEYS_PATH.name,
            f"holds a key for {exam_id}, which tools/config.py does not register "
            "as having one",
        )

    for paper in EXAM_PAPERS:
        key = official_keys.get(paper.id)
        if key is None:
            continue
        expected = set(range(1, paper.expected_questions + 1))
        if set(key) != expected:
            errors.add(
                config.ANSWER_KEYS_PATH.name,
                f"the key of {paper.id} covers {sorted(key)}, "
                f"not questions 1..{paper.expected_questions}",
            )

    if errors:
        raise BuildError(
            "the committed extraction is stale - run 'python -m tools extract'\n"
            + "\n".join(f"  - {item}" for item in errors)
        )


def load_explanations(directory: Path) -> dict[str, dict[str, Any]]:
    """Merge every ``data/answers/*.json`` file into one mapping.

    Args:
        directory: ``data/answers``.

    Returns:
        The explanation and the reference of each answer, keyed by question id.

    Raises:
        BuildError: If the directory is missing, a file has the wrong shape, or
            a question id is defined in more than one file.
    """
    if not directory.is_dir():
        raise BuildError(f"required directory is missing: {directory}")

    merged: dict[str, dict[str, Any]] = {}
    # Sorted so the merge order, and therefore any error message, is stable.
    for path in sorted(directory.glob("*.json")):
        for question_id, entry in read_json_object(path).items():
            if not isinstance(entry, dict):
                raise BuildError(f"{path}: {question_id} must map to an object")
            if question_id in merged:
                raise BuildError(
                    f"{question_id} is defined in more than one answers file"
                )
            merged[question_id] = entry
    return merged


def parse_question_id(question_id: str) -> tuple[str, int] | None:
    """Split a question id into its exam id and its number.

    Args:
        question_id: The id to split, such as ``ENA26-Q01``.

    Returns:
        The exam id and the number, or None when the id is malformed.
    """
    match = QUESTION_ID_PATTERN.match(question_id)
    if match is None:
        return None
    return match.group("exam"), int(match.group("number"))


def apply_override(
    question: RawQuestion, override: Mapping[str, Any], errors: ErrorLog
) -> RawQuestion:
    """Overlay a hand-written fix on one extracted question.

    Clearing the review flag is the whole power of an override, so every field
    it carries must be accounted for. A field that replaces the extracted text
    is a fix. A field identical to the extracted text is a *pin*: someone read
    what the parser produced, found it correct, and wants the flag cleared
    without changing a character. Both are legitimate, and they must be told
    apart, because a pin silently reverts whatever a later ``extract`` run
    produces for that field. ``_verbatim`` names the pinned fields, which turns
    that revert into a build failure the next time the two diverge.

    Args:
        question: The question as extracted.
        override: The entry from ``data/overrides.json``.
        errors: Where to record a malformed override.

    Returns:
        The corrected question, or the original one when the override is
        malformed.
    """
    unknown = sorted(set(override) - OVERRIDE_KEYS)
    if unknown:
        errors.add(question.id, f"override has unknown key(s): {', '.join(unknown)}")
        return question

    stem = override.get("stem")
    options = override.get("options")
    if stem is None and options is None:
        errors.add(question.id, "override must set 'stem' or 'options'")
        return question

    verbatim = override.get("_verbatim", [])
    if not isinstance(verbatim, list) or not all(
        item in OVERRIDABLE_FIELDS for item in verbatim
    ):
        errors.add(
            question.id,
            "override '_verbatim' must list field names, each one of "
            f"{', '.join(sorted(OVERRIDABLE_FIELDS))}",
        )
        return question

    if stem is not None and (not isinstance(stem, str) or not stem.strip()):
        errors.add(question.id, "override 'stem' must be a non-empty string")
        return question

    if options is not None and (
        not isinstance(options, dict)
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in options.items()
        )
    ):
        errors.add(question.id, "override 'options' must map letters to strings")
        return question

    for field, replacement, extracted in (
        ("stem", stem, question.stem),
        ("options", options, dict(question.options)),
    ):
        if replacement is None:
            continue
        pinned = field in verbatim
        if replacement == extracted and not pinned:
            errors.add(
                question.id,
                f"override '{field}' is identical to the extracted text. Drop it, "
                f"or add it to '_verbatim' to record that it was reviewed as-is",
            )
            return question
        if replacement != extracted and pinned:
            errors.add(
                question.id,
                f"override '{field}' is declared verbatim but no longer matches "
                f"the extracted text. Re-read the question and either update the "
                f"override or drop it from '_verbatim'",
            )
            return question

    return RawQuestion(
        id=question.id,
        exam=question.exam,
        number=question.number,
        stem=question.stem if stem is None else stem,
        options=dict(question.options) if options is None else dict(options),
        parse_status=ParseStatus.OK,
        issues=(),
    )


def build_answer(
    question_id: str,
    exam_id: str,
    key_number: int,
    official_keys: Mapping[str, Mapping[int, OptionLetter | None]],
    explanations: Mapping[str, Mapping[str, Any]],
    errors: ErrorLog,
) -> Answer | None:
    """Resolve the answer of one question from its paper's published key.

    Every paper in the registry has a published key, so every answer in the
    bank is official. `Answer` can still carry a derived one and the contract
    still enforces the rules that go with it, because a future paper may arrive
    without a key — but no layer here manufactures one, and the code does not
    pretend a branch exists that no data reaches.

    Args:
        question_id: The question's id.
        exam_id: The exam the question belongs to.
        key_number: The row of the published key that answers this question.
            Usually the question's own number; see `resolve_key_number`.
        official_keys: The published answer keys, by exam id.
        explanations: The explanation and reference of each answer, by id.
        errors: Where to record a missing or malformed entry.

    Returns:
        The answer, or None when it could not be resolved.
    """
    key = official_keys.get(exam_id)
    if key is None:
        errors.add(
            question_id,
            f"{exam_id} has no published answer key, and no layer derives an "
            "answer without one",
        )
        return None
    if key_number not in key:
        errors.add(question_id, f"no entry in the official answer key of {exam_id}")
        return None

    # The key PDF is the whole provenance of an official answer, and it is what
    # `reference` says when the answers file offers nothing better. Checked
    # rather than asserted: an assert vanishes under `python -O`, and what would
    # then reach the bank is the literal string "None" as the provenance of
    # every answer of the paper.
    key_pdf = EXAM_PAPERS_BY_ID[exam_id].answer_key_file
    if key_pdf is None:
        errors.add(
            question_id,
            f"the answer key of {exam_id} was parsed, but tools/config.py "
            "registers no answer-key PDF to cite as the reference",
        )
        return None

    entry = explanations.get(question_id, {})
    unknown = sorted(set(entry) - EXPLANATION_KEYS)
    if unknown:
        errors.add(
            question_id, f"answer entry has unknown key(s): {', '.join(unknown)}"
        )
        return None
    for field in sorted(EXPLANATION_KEYS):
        value = entry.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.add(
                question_id, f"answer entry: '{field}' must be a non-empty string"
            )
            return None

    explanation = entry.get("explanation")
    reference = entry.get("reference") or key_pdf
    return Answer(
        letter=key[key_number],
        source=AnswerSource.OFFICIAL,
        reference=str(reference),
        explanation=None if explanation is None else str(explanation),
    )


def resolve_key_number(
    number: int, excluded: ExcludedReason | None, duplicate_of: str | None
) -> int:
    """Decide which row of the published key answers this question.

    Normally the question's own number. The exception is a question the printed
    booklet reprints from an earlier number: the key row that carries its
    number answers the question the real exam had there, which the booklet did
    not print and the bank does not hold. The letter that applies to the text we
    do have is the one the key gives to the question it repeats.

    Args:
        number: The question number printed on the paper.
        excluded: Why the question is excluded from the draw, if it is.
        duplicate_of: The id of the question it repeats, if it repeats one.

    Returns:
        The question number to read the published key at.
    """
    if excluded is ExcludedReason.SOURCE_BOOKLET_DEFECT and duplicate_of is not None:
        repeated = parse_question_id(duplicate_of)
        if repeated is not None:
            return repeated[1]
    return number


def report_orphan_keys(
    used: Mapping[str, set[str]], known_ids: set[str], errors: ErrorLog
) -> None:
    """Report every key of a data layer that matched no question.

    A key that matches nothing is a typo or a stale id, and silently ignoring
    it means a hand-written fix stops being applied without a word.

    Args:
        used: The keys each layer offered, by layer name.
        known_ids: Every question id that exists.
        errors: Where to record the orphans.
    """
    for layer, keys in used.items():
        for key in sorted(keys - known_ids):
            errors.add(layer, f"{key} matches no question")


def build_bank(generated_at: str) -> QuestionBank:
    """Assemble the bank from every layer, reporting all problems at once.

    Args:
        generated_at: The build date, ``YYYY-MM-DD``.

    Returns:
        The assembled bank.

    Raises:
        BuildError: If an input file is missing, malformed or stale, or if any
            layer leaves a question unresolved.
    """
    raw_questions, raw_toolchain = load_raw_questions(config.RAW_QUESTIONS_PATH)
    official_keys, keys_toolchain = load_official_keys(config.ANSWER_KEYS_PATH)
    toolchain = reconcile_toolchain(raw_toolchain, keys_toolchain)
    check_extraction_is_current(raw_questions, official_keys)

    overrides = {
        key: value
        for key, value in read_json_object(config.OVERRIDES_PATH).items()
        if not key.startswith("_")
    }
    explanations = load_explanations(config.ANSWERS_DIR)
    topics, assignments = load_topics(config.TOPICS_PATH)
    topic_ids = {topic.id for topic in topics}

    errors = ErrorLog()
    known_ids = {question.id for question in raw_questions}
    report_orphan_keys(
        {
            "data/overrides.json": set(overrides),
            "data/topics.json assignments": set(assignments),
            "data/answers/*.json": set(explanations),
            "tools/config.py KNOWN_DUPLICATES": set(config.KNOWN_DUPLICATES),
            "tools/config.py KNOWN_DEFECTS": set(config.KNOWN_DEFECTS),
            "tools/config.py EXCLUDED_QUESTIONS": set(config.EXCLUDED_QUESTIONS),
        },
        known_ids,
        errors,
    )

    questions: list[Question] = []
    for raw in raw_questions:
        override = overrides.get(raw.id)
        question = raw if override is None else apply_override(raw, override, errors)

        if question.parse_status is not ParseStatus.OK:
            errors.add(
                question.id, f"still flagged for review - {'; '.join(question.issues)}"
            )
            continue

        identity = parse_question_id(question.id)
        if identity is None:
            errors.add(question.id, "malformed id, expected <exam>-Q<NN>")
            continue
        exam_id, number = identity
        if exam_id != question.exam or number != question.number:
            errors.add(
                question.id,
                "id disagrees with exam "
                f"{question.exam!r} and number {question.number}",
            )
            continue

        missing_options = [
            str(letter)
            for letter in OptionLetter.sequence()
            if letter not in question.options
        ]
        if missing_options:
            errors.add(question.id, f"missing option(s): {', '.join(missing_options)}")
            continue

        excluded = config.EXCLUDED_QUESTIONS.get(question.id)
        duplicate_of = config.KNOWN_DUPLICATES.get(question.id)
        answer = build_answer(
            question.id,
            exam_id,
            resolve_key_number(number, excluded, duplicate_of),
            official_keys,
            explanations,
            errors,
        )
        if answer is None:
            continue

        # An annulled question and a question without a letter have to be the
        # same question: a key row that says ANULADA is the only thing that may
        # leave a letter out, and a question marked annulled with a letter in
        # the key means the registry and the key disagree about the paper.
        if answer.letter is None and excluded is not ExcludedReason.ANNULLED:
            errors.add(
                question.id,
                "the official key annuls it, but it is not registered as "
                "excluded with reason 'annulled' in tools/config.py",
            )
            continue
        if answer.letter is not None and excluded is ExcludedReason.ANNULLED:
            errors.add(
                question.id,
                f"registered as annulled, but the official key gives {answer.letter!r}",
            )
            continue

        topic = assignments.get(question.id)
        if not topic:
            errors.add(question.id, "no topic assigned in data/topics.json")
            continue
        if topic not in topic_ids:
            errors.add(question.id, f"unknown topic {topic!r} in data/topics.json")
            continue

        questions.append(
            Question(
                id=question.id,
                exam=question.exam,
                number=question.number,
                topic=topic,
                stem=question.stem,
                options={
                    str(letter): question.options[str(letter)]
                    for letter in OptionLetter.sequence()
                },
                answer=answer,
                duplicate_of=duplicate_of,
                known_defects=config.KNOWN_DEFECTS.get(question.id, ()),
                excluded_reason=excluded,
            )
        )

    used_topics = {question.topic for question in questions}
    for orphan in sorted(topic_ids - used_topics):
        errors.add("data/topics.json", f"topic {orphan!r} is declared but never used")

    for paper in EXAM_PAPERS:
        found = sum(1 for question in questions if question.exam == paper.id)
        if found != paper.expected_questions:
            errors.add(
                paper.id,
                f"{found} questions built, expected {paper.expected_questions}",
            )

    if errors:
        raise BuildError(
            f"{len(errors)} problem(s) while assembling the bank\n"
            + "\n".join(f"  - {item}" for item in errors)
        )

    exams = [
        ExamEntry(
            id=paper.id,
            title=paper.title,
            date=paper.date,
            file=paper.file,
            has_official_answer_key=paper.has_official_answer_key,
        )
        for paper in EXAM_PAPERS
    ]
    return QuestionBank(
        version=config.BANK_VERSION,
        generated_at=generated_at,
        toolchain=dict(toolchain),
        exams=exams,
        topics=topics,
        questions=questions,
    )


def render_json(bank: QuestionBank) -> str:
    """Render the bank as the canonical JSON document.

    Args:
        bank: The assembled bank.

    Returns:
        The complete file content, ending in a newline.
    """
    return json.dumps(bank.to_json(), ensure_ascii=False, indent=2) + "\n"


def render_markdown(bank: QuestionBank) -> str:
    """Render the human review surface.

    Written in Portuguese because it is read next to the Portuguese questions
    it presents; the English enum values are mapped through explicit label
    tables rather than shown raw, and a topic is shown by its label so nobody
    has to read a slug.

    Args:
        bank: The assembled bank.

    Returns:
        The complete file content, ending in a newline.

    Raises:
        BuildError: If a question lacks one of the four options.
    """
    labels = {topic.id: topic.label for topic in bank.topics}
    excluded = [q for q in bank.questions if q.excluded_reason is not None]

    lines = [
        "# Banco de questões PROFNIT",
        "",
        f"{len(bank.questions)} questões extraídas de "
        f"{len(bank.exams)} cadernos em `exams/`.",
        "",
        "Todas as respostas vêm de gabarito oficial publicado: a letra é fato",
        "publicado, não dedução. A **explicação** é material de estudo escrito a",
        "partir da fonte citada em **Referência** — essa parte pode errar, e a",
        "referência diz com todas as letras quando nenhum documento de",
        "`references/` sustenta a questão. Para corrigir uma explicação ou uma",
        "referência, edite `data/answers/<caderno>.json` e rode",
        "`python -m tools build` — nenhum código do app precisa mudar.",
        "",
        f"{len(excluded)} questões continuam no banco, na contagem do caderno e",
        "neste documento, mas **nunca são sorteadas**:",
        "",
    ]
    lines += [
        f"- `{question.id}` — {EXCLUDED_REASON_LABELS[reason]}."
        for question in excluded
        if (reason := question.excluded_reason) is not None
    ]
    lines += ["", "## Temas", ""]
    lines += [
        f"- **{topic.label}** (`{topic.id}`): {topic.definition}"
        for topic in bank.topics
    ]
    lines.append("")

    for exam in bank.exams:
        of_exam = [question for question in bank.questions if question.exam == exam.id]
        origin = SOURCE_LABELS[AnswerSource.OFFICIAL]
        lines += [
            "---",
            "",
            f"## {exam.id} — {exam.title}",
            "",
            f"Prova de {exam.date} · `{exam.file}` · "
            f"{len(of_exam)} questões · {origin}",
            "",
        ]

        for question in of_exam:
            answer = question.answer
            topic_label = labels.get(question.topic, question.topic)
            lines += [f"### {question.id} · {topic_label}", ""]
            if question.duplicate_of is not None:
                lines += [f"> Repete {question.duplicate_of} no caderno original.", ""]
            if question.known_defects:
                lines += [
                    f"> Defeitos da fonte: {', '.join(question.known_defects)}.",
                    "",
                ]
            if question.excluded_reason is not None:
                lines += [f"> {EXCLUDED_REASON_NOTES[question.excluded_reason]}", ""]
            lines += [
                f"> {line}" if line.strip() else ">"
                for line in question.stem.splitlines()
            ]
            lines.append("")

            for letter in OptionLetter.sequence():
                text = question.options.get(str(letter))
                if text is None:
                    raise BuildError(f"{question.id}: option {letter} is missing")
                mark = "**" if letter == answer.letter else ""
                lines.append(f"- {mark}{letter}){mark} {text}")

            lines.append("")
            if answer.letter is None:
                lines.append("**Sem resposta correta** (questão anulada)")
            else:
                lines.append(
                    f"**Resposta: {answer.letter}** ({SOURCE_LABELS[answer.source]})"
                )
            lines.append("")
            lines.append(f"- Referência: {answer.reference}")
            if answer.explanation is not None:
                lines.append(f"- Explicação: {answer.explanation}")
            lines.append("")

    return "\n".join(lines)


def render_javascript(bank_json: str) -> str:
    """Wrap the canonical JSON as the script the static app loads.

    A plain ``<script>`` tag works identically over ``https://`` and
    ``file://``, which ``fetch`` does not, and it is what makes the site open
    with the bank already loaded.

    Args:
        bank_json: The exact content of ``data/question-bank.json``.

    Returns:
        The complete file content, ending in a newline.
    """
    # JSON is a subset of modern JavaScript except for these characters: the
    # line separators are not valid in a script, and the angle brackets could
    # close the enclosing script element from inside a string.
    escaped = (
        bank_json.strip()
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return (
        "// Generated by `python -m tools build` from data/question-bank.json.\n"
        "// Do not edit by hand: the next build overwrites it.\n"
        f"window.{config.BANK_GLOBAL_NAME} = {escaped};\n"
    )


def carried_generated_at(path: Path) -> str:
    """Read the build date the committed bank already carries.

    This used to default to ``date.today()``, which meant a rebuild from
    unchanged inputs produced changed bytes the next morning: the same
    question bank, stamped with a different day. Carrying the committed date
    forward instead makes a plain ``python -m tools build`` a fixpoint — same
    inputs, same bytes, any day — which is the property the rebuild guard in
    CI checks and the reason a correction to one explanation shows up as a
    diff of that explanation and nothing else.

    Requiring ``--generated-at`` on every run would buy the same
    reproducibility, but it would make every CI job and every one-line fix
    restate a date that is already committed two lines above the change, and a
    date restated by hand is a date that eventually gets restated wrong. So the
    flag stays for the case it is actually for — a genuinely new build date —
    and is required only for the first build, when there is no committed bank
    to carry a date from.

    Args:
        path: ``data/question-bank.json``, the bank being rebuilt.

    Returns:
        The ``generatedAt`` of the committed bank.

    Raises:
        BuildError: If there is no committed bank yet, or its ``generatedAt``
            is missing or malformed. Both say to pass ``--generated-at``.
    """
    if not path.exists():
        raise BuildError(
            f"{path} does not exist yet, so there is no build date to carry "
            "forward. Pass --generated-at YYYY-MM-DD for this first build."
        )
    previous = read_json_object(path).get("generatedAt")
    if not isinstance(previous, str) or not GENERATED_AT_PATTERN.match(previous):
        raise BuildError(
            f"{path}: generatedAt is {previous!r}, not a YYYY-MM-DD date, so it "
            "cannot be carried forward. Pass --generated-at YYYY-MM-DD."
        )
    return previous


def write_text(path: Path, content: str) -> None:
    """Write one generated artifact with LF newlines on every platform.

    Args:
        path: Where to write.
        content: The complete file content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    """Build the bank from the command line.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` by default.

    Returns:
        0 on success, 1 when a layer could not be resolved.
    """
    configure_stdio()
    parser = argparse.ArgumentParser(
        prog="python -m tools build",
        description=(
            "Assemble data/question-bank.json, its markdown, and the app's bank script."
        ),
    )
    parser.add_argument(
        "--generated-at",
        help=(
            "the date recorded in generatedAt "
            "(default: the one the committed bank already carries)"
        ),
    )
    args = parser.parse_args(argv)

    try:
        generated_at = args.generated_at or carried_generated_at(
            config.QUESTION_BANK_PATH
        )
        if not GENERATED_AT_PATTERN.match(generated_at):
            raise BuildError(
                f"--generated-at must be YYYY-MM-DD, found {generated_at!r}"
            )
        bank = build_bank(generated_at)
        bank_json = render_json(bank)
        markdown = render_markdown(bank)
    except BuildError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1

    # Everything rendered and checked; only now is anything written, so a
    # failure can never leave the JSON and the markdown out of sync.
    write_text(config.QUESTION_BANK_PATH, bank_json)
    write_text(config.QUESTION_BANK_MD_PATH, markdown)
    # Read the canonical file back so the script can only ever wrap what was
    # actually published.
    published = config.QUESTION_BANK_PATH.read_text(encoding="utf-8")
    write_text(config.QUESTION_BANK_JS_PATH, render_javascript(published))

    official = sum(
        1
        for question in bank.questions
        if question.answer.source is AnswerSource.OFFICIAL
    )
    excluded = sum(1 for question in bank.questions if question.excluded_reason)
    explained = sum(1 for question in bank.questions if question.answer.explanation)

    print(f"Bank assembled: {len(bank.questions)} questions, {len(bank.exams)} exams")
    print(f"  generated at:        {bank.generated_at}")
    print(f"  pdftotext (poppler): {bank.toolchain.get('pdftotext', 'unknown')}")
    print(f"  official answer key: {official}")
    print(f"  derived:             {len(bank.questions) - official}")
    print(f"  topics:              {len(bank.topics)}")
    print(f"  with an explanation: {explained}")
    print(f"  excluded from draws: {excluded}")
    print(f"  drawable:            {len(bank.questions) - excluded}")
    for path in (
        config.QUESTION_BANK_PATH,
        config.QUESTION_BANK_MD_PATH,
        config.QUESTION_BANK_JS_PATH,
    ):
        print(f"Written: {path.relative_to(config.REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
