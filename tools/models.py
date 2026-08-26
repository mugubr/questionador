"""Data shapes shared by every stage of the question-bank pipeline.

The enums are the vocabulary the code branches on and are therefore English,
while every value a student reads — stems, options, topics, rationales — stays
Portuguese and is carried through as plain strings.

Nothing here touches the filesystem or a subprocess: the dataclasses are the
seam the parser and the builder are tested against.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self


class AnswerSource(StrEnum):
    """Where the answer letter comes from.

    ``OFFICIAL`` means a published answer key states it, and nothing else. A
    derived answer is never promoted to official.
    """

    OFFICIAL = "official"
    DERIVED = "derived"


class Confidence(StrEnum):
    """How much trust a derived answer carries."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OptionLetter(StrEnum):
    """The four answer options every question in the bank has."""

    A = "a"
    B = "b"
    C = "c"
    D = "d"

    @classmethod
    def sequence(cls) -> tuple[OptionLetter, ...]:
        """Return the letters in the a-b-c-d order the parser expects.

        Returns:
            The four letters, in the order an exam paper prints them.
        """
        return (cls.A, cls.B, cls.C, cls.D)


class ExcludedReason(StrEnum):
    """Why a question must never be drawn, even though it stays in the bank.

    ``ANNULLED`` is the official key printing ANULADA instead of a letter.
    ``SOURCE_BOOKLET_DEFECT`` is a question the printed booklet gets wrong in a
    way that leaves the bank without the text the key answers.
    """

    ANNULLED = "annulled"
    SOURCE_BOOKLET_DEFECT = "source-booklet-defect"


class ParseStatus(StrEnum):
    """Whether a raw question came out of the PDF cleanly.

    ``REVIEW`` blocks the build: an unresolved question is reported, never
    guessed at and never silently shipped.
    """

    OK = "ok"
    REVIEW = "review"


@dataclass(frozen=True)
class ParsedBlock:
    """The result of splitting one question block into stem and options.

    Attributes:
        stem: The question body, with its significant line breaks kept.
        options: The options found, keyed by letter, in a-b-c-d order.
        trailing: Text that followed the last option and belongs to neither.
    """

    stem: str
    options: Mapping[str, str]
    trailing: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawQuestion:
    """One question as `extract` recovered it, before any hand-written fix.

    This is the shape persisted in ``data/raw-questions.json``, which is
    committed so the rest of the chain can be rebuilt and diffed without
    running ``pdftotext``.

    Attributes:
        id: The stable identifier, always ``<exam>-Q<NN>``.
        exam: The id of the exam paper the question came from.
        number: The question number printed on the paper, 1-based.
        stem: The question body.
        options: The options found, keyed by letter.
        parse_status: Whether the question is usable as extracted.
        issues: Every problem found, in the order they were detected.
    """

    id: str
    exam: str
    number: int
    stem: str
    options: Mapping[str, str]
    parse_status: ParseStatus
    issues: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """Render the question as the JSON object stored on disk.

        Returns:
            A dict with the published field names, ready for ``json.dump``.
        """
        return {
            "id": self.id,
            "exam": self.exam,
            "number": self.number,
            "stem": self.stem,
            "options": dict(self.options),
            "parseStatus": str(self.parse_status),
            "issues": list(self.issues),
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Self:
        """Rebuild a question from a ``data/raw-questions.json`` entry.

        Args:
            payload: One decoded JSON object from the raw-questions file.

        Returns:
            The reconstructed question.

        Raises:
            ValueError: If a required field is missing or has the wrong type.
        """
        try:
            identifier = payload["id"]
            exam = payload["exam"]
            number = payload["number"]
            stem = payload["stem"]
            options = payload["options"]
            status = payload["parseStatus"]
            issues = payload["issues"]
        except KeyError as exc:
            raise ValueError(
                f"raw question is missing the field {exc.args[0]!r}"
            ) from exc

        if (
            not isinstance(identifier, str)
            or not isinstance(exam, str)
            or not isinstance(stem, str)
        ):
            raise ValueError(
                f"raw question {identifier!r}: id, exam and stem must be strings"
            )
        if not isinstance(number, int) or isinstance(number, bool):
            raise ValueError(f"raw question {identifier!r}: number must be an integer")
        if not isinstance(options, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in options.items()
        ):
            raise ValueError(
                f"raw question {identifier!r}: options must map letters to strings"
            )
        if not isinstance(issues, list) or not all(
            isinstance(item, str) for item in issues
        ):
            raise ValueError(
                f"raw question {identifier!r}: issues must be a list of strings"
            )
        try:
            parse_status = ParseStatus(status)
        except ValueError as exc:
            raise ValueError(
                f"raw question {identifier!r}: unknown parseStatus {status!r}"
            ) from exc

        return cls(
            id=identifier,
            exam=exam,
            number=number,
            stem=stem,
            options=dict(options),
            parse_status=parse_status,
            issues=tuple(issues),
        )


@dataclass(frozen=True)
class Answer:
    """The answer to one question, together with its provenance.

    Attributes:
        letter: The correct option, or None when the question has no valid
            answer at all — the official key annulled it, or the printed
            booklet is defective. Only an excluded question may leave it out.
        source: Whether a published key states it or it was derived.
        reference: What was consulted — the source that supports the answer,
            or a plain statement that no document in ``references/`` does.
        confidence: How much trust the derived answer carries; absent on
            official answers.
        explanation: Portuguese explanation of an official answer — why the
            published letter is the right one. Teaching material, not
            provenance: the letter is a published fact either way.
        rationale: Portuguese explanation of a derived answer, which argues
            for a letter no published key states; absent on official answers.
    """

    letter: OptionLetter | None
    source: AnswerSource
    reference: str
    confidence: Confidence | None = None
    explanation: str | None = None
    rationale: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Render the answer as the JSON object published in the bank.

        Fields that do not apply to the source are omitted rather than set to
        null, because the contract distinguishes absent from empty.

        Returns:
            A dict with the published field names.
        """
        payload: dict[str, Any] = {}
        if self.letter is not None:
            payload["letter"] = str(self.letter)
        payload["source"] = str(self.source)
        if self.confidence is not None:
            payload["confidence"] = str(self.confidence)
        payload["reference"] = self.reference
        if self.explanation is not None:
            payload["explanation"] = self.explanation
        if self.rationale is not None:
            payload["rationale"] = self.rationale
        return payload


@dataclass(frozen=True)
class Question:
    """One published question, with everything the app needs to show it.

    Attributes:
        id: The stable identifier, always ``<exam>-Q<NN>``.
        exam: The id of the exam paper.
        number: The question number printed on the paper.
        topic: The topic slug, declared once in the bank's ``topics``.
        stem: The question body.
        options: The four options, keyed by letter.
        answer: The answer and its provenance.
        duplicate_of: The id this question repeats, when the paper repeats one.
        known_defects: Defects of the source material, recorded not fixed.
        excluded_reason: Why the question must never be drawn. It still counts
            towards its paper and still appears in the review surface.
    """

    id: str
    exam: str
    number: int
    topic: str
    stem: str
    options: Mapping[str, str]
    answer: Answer
    duplicate_of: str | None = None
    known_defects: tuple[str, ...] = ()
    excluded_reason: ExcludedReason | None = None

    def to_json(self) -> dict[str, Any]:
        """Render the question as the JSON object published in the bank.

        Returns:
            A dict with the published field names.
        """
        payload: dict[str, Any] = {
            "id": self.id,
            "exam": self.exam,
            "number": self.number,
            "topic": self.topic,
            "stem": self.stem,
            "options": dict(self.options),
            "answer": self.answer.to_json(),
        }
        if self.duplicate_of is not None:
            payload["duplicateOf"] = self.duplicate_of
        if self.known_defects:
            payload["knownDefects"] = list(self.known_defects)
        if self.excluded_reason is not None:
            payload["excludedReason"] = str(self.excluded_reason)
        return payload


@dataclass(frozen=True)
class Topic:
    """One entry of the taxonomy every question's topic is drawn from.

    The slug is Portuguese kebab-case, like the rest of the taxonomy values,
    but it is never what the student reads: `label` is, so the app shows
    "Marca e indicação geográfica" without de-hyphenating anything.

    Attributes:
        id: The slug stored in ``Question.topic``.
        label: Portuguese label, displayed.
        definition: Portuguese sentence saying what the topic covers.
    """

    id: str
    label: str
    definition: str

    def to_json(self) -> dict[str, Any]:
        """Render the topic as the JSON object published in the bank.

        Returns:
            A dict with the published field names.
        """
        return {"id": self.id, "label": self.label, "definition": self.definition}


@dataclass(frozen=True)
class ExamEntry:
    """One exam paper as published in the bank's ``exams[]`` array.

    Attributes:
        id: Short identifier, a proper noun that is never translated.
        title: Portuguese title of the paper.
        date: Application date, ``YYYY-MM-DD``.
        file: The source PDF in ``exams/``.
        has_official_answer_key: Whether a published key backs its answers.
    """

    id: str
    title: str
    date: str
    file: str
    has_official_answer_key: bool

    def to_json(self) -> dict[str, Any]:
        """Render the exam paper as the JSON object published in the bank.

        Returns:
            A dict with the published field names.
        """
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date,
            "file": self.file,
            "hasOfficialAnswerKey": self.has_official_answer_key,
        }


@dataclass(frozen=True)
class QuestionBank:
    """The complete bank, exactly as it is published.

    Attributes:
        version: Format version the app checks before reading anything else.
        generated_at: The date the bank was built, ``YYYY-MM-DD``.
        toolchain: Version of every external tool that shaped the output.
        exams: The exam papers, in registry order.
        topics: The taxonomy, in the order the taxonomy file declares it.
        questions: The questions, in exam-then-number order.
    """

    version: int
    generated_at: str
    toolchain: Mapping[str, str]
    exams: Sequence[ExamEntry]
    topics: Sequence[Topic]
    questions: Sequence[Question]

    def to_json(self) -> dict[str, Any]:
        """Render the whole bank as the JSON object written to disk.

        Returns:
            A dict with the published field names.
        """
        return {
            "version": self.version,
            "generatedAt": self.generated_at,
            "toolchain": dict(self.toolchain),
            "exams": [exam.to_json() for exam in self.exams],
            "topics": [topic.to_json() for topic in self.topics],
            "questions": [question.to_json() for question in self.questions],
        }


@dataclass
class ErrorLog:
    """Accumulates every problem in a run so all of them are reported at once.

    Stopping at the first error hides the other nine, which turns one fix into
    ten runs. The log behaves like the collection it is: truthy when it holds
    anything, sized, and iterable.

    Attributes:
        items: The formatted messages, in the order they were added.
    """

    items: list[str] = field(default_factory=list)

    def add(self, where: str, message: str) -> None:
        """Record one problem.

        Args:
            where: The question id, field path, or file the problem is about.
            message: What is wrong, in English.
        """
        self.items.append(f"{where}: {message}")

    def extend(self, where: str, messages: Sequence[str]) -> None:
        """Record several problems that share one location.

        Args:
            where: The question id, field path, or file the problems are about.
            messages: What is wrong with each, in English.
        """
        for message in messages:
            self.add(where, message)

    def __bool__(self) -> bool:
        """Report whether anything was recorded.

        Returns:
            True when at least one problem was recorded.
        """
        return bool(self.items)

    def __len__(self) -> int:
        """Report how many problems were recorded.

        Returns:
            The number of recorded messages.
        """
        return len(self.items)

    def __iter__(self) -> Iterator[str]:
        """Iterate the recorded problems in insertion order.

        Yields:
            One formatted message at a time.
        """
        return iter(self.items)
