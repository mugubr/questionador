"""Tests for the dataclasses and enums every stage shares.

The JSON renderers are the contract: a field the contract distinguishes as
absent must not be published as null, because `tools/validate.py` and
`data/schema.json` both branch on presence.
"""

from __future__ import annotations

import pytest

from tools.models import (
    Answer,
    AnswerSource,
    Confidence,
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

RAW_PAYLOAD = {
    "id": "ENA26-Q01",
    "exam": "ENA26",
    "number": 1,
    "stem": "Sobre a patente de invencao, assinale a correta:",
    "options": {"a": "Dez.", "b": "Quinze.", "c": "Vinte.", "d": "Trinta."},
    "parseStatus": "ok",
    "issues": [],
}


def test_option_letter_sequence_is_the_printed_order() -> None:
    """Give the letters in the order an exam paper prints them."""
    assert OptionLetter.sequence() == (
        OptionLetter.A,
        OptionLetter.B,
        OptionLetter.C,
        OptionLetter.D,
    )


def test_raw_question_round_trips_through_json() -> None:
    """Rebuild a raw question from exactly what was written to disk."""
    question = RawQuestion.from_json(RAW_PAYLOAD)
    assert question.to_json() == RAW_PAYLOAD


def test_raw_question_keeps_its_issues_and_status() -> None:
    """Carry the review flag and its reasons through the round trip."""
    payload = dict(RAW_PAYLOAD, parseStatus="review", issues=["stem too short"])
    question = RawQuestion.from_json(payload)
    assert question.parse_status is ParseStatus.REVIEW
    assert question.issues == ("stem too short",)
    assert question.to_json() == payload


def test_raw_question_rejects_a_missing_field() -> None:
    """Name the field rather than raising a bare KeyError."""
    payload = dict(RAW_PAYLOAD)
    del payload["stem"]
    with pytest.raises(ValueError, match="missing the field 'stem'"):
        RawQuestion.from_json(payload)


def test_raw_question_rejects_a_boolean_number() -> None:
    """Refuse `True` as a question number, which `isinstance(x, int)` allows."""
    with pytest.raises(ValueError, match="number must be an integer"):
        RawQuestion.from_json(dict(RAW_PAYLOAD, number=True))


def test_raw_question_rejects_options_that_are_not_strings() -> None:
    """Refuse options that do not map letters to text."""
    with pytest.raises(ValueError, match="options must map letters to strings"):
        RawQuestion.from_json(dict(RAW_PAYLOAD, options={"a": 1}))


def test_raw_question_rejects_an_unknown_parse_status() -> None:
    """Refuse a status outside the enum instead of coercing it."""
    with pytest.raises(ValueError, match="unknown parseStatus"):
        RawQuestion.from_json(dict(RAW_PAYLOAD, parseStatus="maybe"))


def test_official_answer_publishes_no_derived_fields() -> None:
    """Omit the derived-only fields on an official answer.

    The contract distinguishes absent from empty: an official answer carrying
    `confidence` is rejected by both the schema and the validator.
    """
    answer = Answer(
        letter=OptionLetter.C,
        source=AnswerSource.OFFICIAL,
        reference="Gabarito-Final_ENA26.pdf",
        explanation="Porque a lei diz isso.",
    )
    assert answer.to_json() == {
        "letter": "c",
        "source": "official",
        "reference": "Gabarito-Final_ENA26.pdf",
        "explanation": "Porque a lei diz isso.",
    }


def test_derived_answer_publishes_its_confidence_and_rationale() -> None:
    """Publish everything a derived answer needs to be auditable."""
    answer = Answer(
        letter=OptionLetter.A,
        source=AnswerSource.DERIVED,
        reference="Ref2-Patente_2021.pdf, p. 30",
        confidence=Confidence.HIGH,
        rationale="Deduzido do artigo 40.",
    )
    assert answer.to_json() == {
        "letter": "a",
        "source": "derived",
        "confidence": "high",
        "reference": "Ref2-Patente_2021.pdf, p. 30",
        "rationale": "Deduzido do artigo 40.",
    }


def test_an_answer_without_a_letter_omits_the_field_entirely() -> None:
    """Leave `letter` out rather than publishing it as null.

    AV2-POL-Q14 was annulled by the official key and has no correct option at
    all. Nothing downstream may assume the field exists.
    """
    answer = Answer(
        letter=None,
        source=AnswerSource.OFFICIAL,
        reference="Gabarito-Final_AV2-POL.pdf: ANULADA",
    )
    payload = answer.to_json()
    assert "letter" not in payload
    assert payload["source"] == "official"


def test_question_omits_the_optional_fields_it_does_not_carry() -> None:
    """Publish only the optional fields the question actually has."""
    question = Question(
        id="ENA26-Q01",
        exam="ENA26",
        number=1,
        topic="patente",
        stem="Sobre a patente de invencao, assinale a correta:",
        options={"a": "Dez.", "b": "Quinze.", "c": "Vinte.", "d": "Trinta."},
        answer=Answer(
            letter=OptionLetter.C,
            source=AnswerSource.OFFICIAL,
            reference="Gabarito-Final_ENA26.pdf",
        ),
    )
    payload = question.to_json()
    assert "duplicateOf" not in payload
    assert "knownDefects" not in payload
    assert "excludedReason" not in payload


def test_question_publishes_the_optional_fields_it_does_carry() -> None:
    """Publish the source defects the bank records rather than hides."""
    question = Question(
        id="AV2-PI-Q14",
        exam="AV2-PI",
        number=14,
        topic="patente",
        stem="Sobre o registro, assinale a alternativa correta:",
        options={"a": "Um.", "b": "Dois.", "c": "Tres.", "d": "Quatro."},
        answer=Answer(
            letter=OptionLetter.A,
            source=AnswerSource.OFFICIAL,
            reference="Gabarito-Final_AV2-PI.pdf",
        ),
        duplicate_of="AV2-PI-Q13",
        known_defects=("identical-options",),
        excluded_reason=ExcludedReason.SOURCE_BOOKLET_DEFECT,
    )
    payload = question.to_json()
    assert payload["duplicateOf"] == "AV2-PI-Q13"
    assert payload["knownDefects"] == ["identical-options"]
    assert payload["excludedReason"] == "source-booklet-defect"


def test_question_bank_renders_every_section() -> None:
    """Render the whole bank with the published field names."""
    bank = QuestionBank(
        version=1,
        generated_at="2026-08-26",
        toolchain={"pdftotext": "25.07.0"},
        exams=[
            ExamEntry(
                id="ENA26",
                title="Exame Nacional de Acesso",
                date="2025-11-22",
                file="Prova_ENA26.pdf",
                has_official_answer_key=True,
            )
        ],
        topics=[Topic(id="patente", label="Patente", definition="Sobre patentes.")],
        questions=[],
    )
    payload = bank.to_json()
    assert set(payload) == {
        "version",
        "generatedAt",
        "toolchain",
        "exams",
        "topics",
        "questions",
    }
    assert payload["exams"][0]["hasOfficialAnswerKey"] is True
    assert payload["topics"][0] == {
        "id": "patente",
        "label": "Patente",
        "definition": "Sobre patentes.",
    }


def test_error_log_accumulates_instead_of_stopping_at_the_first() -> None:
    """Report every problem of a run, not the first one.

    Stopping at the first error hides the other nine, which turns one fix into
    ten runs.
    """
    errors = ErrorLog()
    assert not errors
    assert len(errors) == 0

    errors.add("ENA26-Q01", "stem is missing")
    errors.extend("ENA26-Q02", ["option d is empty", "topic is unknown"])

    assert bool(errors) is True
    assert len(errors) == 3
    assert list(errors) == [
        "ENA26-Q01: stem is missing",
        "ENA26-Q02: option d is empty",
        "ENA26-Q02: topic is unknown",
    ]


def test_a_toolchain_stamp_is_read_as_a_map_of_versions() -> None:
    """Accept the stamp both artifacts of `extract` carry."""
    assert parse_toolchain({"pdftotext": "25.07.0"}) == {"pdftotext": "25.07.0"}


@pytest.mark.parametrize("payload", [None, {}, [], "25.07.0", 25])
def test_an_absent_or_empty_toolchain_stamp_is_refused(
    payload: object,
) -> None:
    """Refuse a stamp that promises nothing.

    The stamp is load-bearing provenance: it says which build of pdftotext
    produced the text, and two builds produce two different banks.

    Args:
        payload: A stamp the contract does not allow.
    """
    with pytest.raises(ValueError, match="must be a non-empty object"):
        parse_toolchain(payload)


def test_a_toolchain_version_that_is_not_text_is_refused() -> None:
    """Refuse a version that is blank or not a string at all."""
    with pytest.raises(ValueError, match="must be a non-empty string"):
        parse_toolchain({"pdftotext": "   "})
    with pytest.raises(ValueError, match="must be a non-empty string"):
        parse_toolchain({"pdftotext": 25})
