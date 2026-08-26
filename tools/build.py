"""Assemble the published question bank from its editable layers.

Layers, applied in this order, each one narrow and auditable:

1. ``data/raw-questions.json`` — the deterministic output of `extract`.
2. ``data/overrides.json`` — hand-written parse fixes, each with its reason.
3. The official answer key of every paper, matched by question number.
4. ``data/answers/*.json`` — the explanation and the reference of each answer.
5. ``data/topics.json`` — the taxonomy and one topic per question.

Three artifacts come out: ``data/question-bank.json`` (canonical),
``data/question-bank.md`` (review surface) and ``docs/data/question-bank.js``
(a mechanical wrapper of the JSON, loaded by a plain script tag). All three are
rendered in full and checked before any of them is written, so a failure never
leaves two of them disagreeing.

Usage:
    python -m tools build
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from tools import config, configure_stdio
from tools.answer_keys import AnswerKeyError
from tools.answer_keys import load_all as load_answer_keys
from tools.config import EXAM_PAPERS, EXAM_PAPERS_BY_ID
from tools.extract import ToolchainError, pdftotext_version
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
)

QUESTION_ID_PATTERN = re.compile(r"^(?P<exam>[A-Z0-9-]+)-Q(?P<number>\d{2})$")

# The only keys an override entry may carry. Anything else is a typo that would
# otherwise be applied as nothing at all.
OVERRIDE_KEYS = frozenset({"_reason", "stem", "options"})

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

    duplicated = sorted(
        {topic.id for topic in topics if [t.id for t in topics].count(topic.id) > 1}
    )
    if duplicated:
        raise BuildError(f"{path}: duplicate topic id(s): {', '.join(duplicated)}")

    assignments = payload.get("assignments")
    if not isinstance(assignments, dict) or not assignments:
        raise BuildError(f"{path}: 'assignments' must be a non-empty object")
    for question_id, slug in assignments.items():
        if not isinstance(slug, str) or not slug.strip():
            raise BuildError(f"{path}: {question_id} must map to a non-empty string")

    return topics, {key: str(value) for key, value in assignments.items()}


def load_raw_questions(path: Path) -> list[RawQuestion]:
    """Read the committed extraction anchor.

    Args:
        path: ``data/raw-questions.json``.

    Returns:
        Every extracted question, in the order it was written.

    Raises:
        BuildError: If the file is not a list of well-formed questions.
    """
    payload = read_json(path)
    if not isinstance(payload, list):
        raise BuildError(
            f"{path}: expected a JSON array, found {type(payload).__name__}"
        )

    questions: list[RawQuestion] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise BuildError(f"{path}: entry {index} is not an object")
        try:
            questions.append(RawQuestion.from_json(item))
        except ValueError as error:
            raise BuildError(f"{path}: {error}") from error
    return questions


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

    An override has to replace text. One that carries only a comment would
    otherwise clear the review flag while changing nothing, which is how a
    question marked for review can quietly reach the bank untouched.

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

    paper = EXAM_PAPERS_BY_ID[exam_id]
    # The key PDF is the whole provenance of an official answer, and it is what
    # `reference` says when the answers file offers nothing better.
    assert paper.answer_key_file is not None

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
    reference = entry.get("reference") or paper.answer_key_file
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


def build_bank(generated_at: str, toolchain: Mapping[str, str]) -> QuestionBank:
    """Assemble the bank from every layer, reporting all problems at once.

    Args:
        generated_at: The build date, ``YYYY-MM-DD``.
        toolchain: The version of every external tool that shaped the output.

    Returns:
        The assembled bank.

    Raises:
        BuildError: If an input file is missing or malformed, or if any layer
            leaves a question unresolved.
    """
    raw_questions = load_raw_questions(config.RAW_QUESTIONS_PATH)
    overrides = {
        key: value
        for key, value in read_json_object(config.OVERRIDES_PATH).items()
        if not key.startswith("_")
    }
    explanations = load_explanations(config.ANSWERS_DIR)
    topics, assignments = load_topics(config.TOPICS_PATH)
    topic_ids = {topic.id for topic in topics}

    try:
        official_keys = load_answer_keys()
    except AnswerKeyError as error:
        raise BuildError(str(error)) from error

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
                question.id, f"still flagged for review — {'; '.join(question.issues)}"
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
        default=date.today().isoformat(),
        help="the date recorded in generatedAt (default: today)",
    )
    args = parser.parse_args(argv)

    try:
        version = pdftotext_version()
    except ToolchainError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        bank = build_bank(args.generated_at, {"pdftotext": version})
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
