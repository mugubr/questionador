"""Tests for the hand-written validator.

Every case starts from a bank that satisfies the contract and breaks exactly
one rule, so a failure names the rule that stopped working. The exam id is one
the registry does not know, which is what lets a two-question bank stand in for
a hundred-and-forty-four-question one.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.validate import main as validate_main
from tools.validate import validate


def minimal_bank() -> dict[str, Any]:
    """Build the smallest bank that satisfies the whole contract.

    Returns:
        A fresh bank the caller may mutate.
    """
    return {
        "version": 1,
        "generatedAt": "2026-08-26",
        "toolchain": {"pdftotext": "25.07.0"},
        "exams": [
            {
                "id": "TESTE",
                "title": "Caderno de teste",
                "date": "2020-01-01",
                "file": "Prova_TESTE.pdf",
                "hasOfficialAnswerKey": True,
            }
        ],
        "topics": [
            {"id": "patente", "label": "Patente", "definition": "Sobre patentes."},
            {"id": "marca", "label": "Marca", "definition": "Sobre marcas."},
        ],
        "questions": [
            {
                "id": "TESTE-Q01",
                "exam": "TESTE",
                "number": 1,
                "topic": "patente",
                "stem": "Sobre a patente de invencao, assinale a correta:",
                "options": {"a": "Um.", "b": "Dois.", "c": "Tres.", "d": "Quatro."},
                "answer": {
                    "letter": "c",
                    "source": "official",
                    "reference": "Gabarito-Final_TESTE.pdf",
                    "explanation": "Porque a lei diz isso.",
                },
            },
            {
                "id": "TESTE-Q02",
                "exam": "TESTE",
                "number": 2,
                "topic": "marca",
                "stem": "Sobre a marca tridimensional, assinale a correta:",
                "options": {"a": "Um.", "b": "Dois.", "c": "Tres.", "d": "Quatro."},
                "answer": {
                    "letter": "a",
                    "source": "official",
                    "reference": "Gabarito-Final_TESTE.pdf",
                },
            },
        ],
    }


def errors_of(bank: dict[str, Any]) -> list[str]:
    """Validate a bank and return its problems as plain strings.

    Args:
        bank: The bank to check.

    Returns:
        Every problem found, in the order it was recorded.
    """
    return list(validate(bank, expected_total=None))


def test_the_minimal_bank_satisfies_the_contract() -> None:
    """Start every other case from a bank with nothing wrong with it."""
    assert errors_of(minimal_bank()) == []


def test_the_bank_must_be_an_object() -> None:
    """Refuse anything but a JSON object at the root."""
    assert any("must be a JSON object" in item for item in errors_of([]))  # type: ignore[arg-type]


def test_an_unknown_version_is_rejected() -> None:
    """Refuse a bank whose format version the code does not implement."""
    bank = minimal_bank()
    bank["version"] = 2
    assert any(item.startswith("version:") for item in errors_of(bank))


def test_the_generated_date_must_be_iso() -> None:
    """Refuse a build date the app cannot parse or display."""
    bank = minimal_bank()
    bank["generatedAt"] = "26/08/2026"
    assert any("generatedAt" in item for item in errors_of(bank))


def test_the_toolchain_must_record_pdftotext() -> None:
    """Refuse a bank that does not say which pdftotext produced it.

    Two builds of pdftotext produce two different banks from the same PDFs, so
    the version is provenance, not decoration.
    """
    bank = minimal_bank()
    bank["toolchain"] = {}
    assert any("missing the version of pdftotext" in item for item in errors_of(bank))


def test_an_unknown_root_field_is_rejected() -> None:
    """Refuse a field the root contract does not declare."""
    bank = minimal_bank()
    bank["topicos"] = []
    assert any("unexpected field(s): topicos" in item for item in errors_of(bank))


# --------------------------------------------------------------------------
# Identity: id, exam and number are one truth, not three fields
# --------------------------------------------------------------------------


def test_an_id_that_disagrees_with_its_number_is_rejected() -> None:
    """Refuse a question whose id and number tell different stories.

    `id`, `exam` and `number` used to be three independent fields that nobody
    cross-checked, so a renumbered question kept a stale id in silence.
    """
    bank = minimal_bank()
    bank["questions"][0]["number"] = 7
    assert any("id disagrees with exam" in item for item in errors_of(bank))


def test_an_id_that_disagrees_with_its_exam_is_rejected() -> None:
    """Refuse a question filed under an exam its id does not name."""
    bank = minimal_bank()
    bank["exams"].append(
        {
            "id": "OUTRO",
            "title": "Outro caderno",
            "date": "2020-01-01",
            "file": "Prova_OUTRO.pdf",
            "hasOfficialAnswerKey": True,
        }
    )
    bank["questions"][0]["exam"] = "OUTRO"
    assert any("id disagrees with exam" in item for item in errors_of(bank))


def test_a_malformed_id_is_rejected() -> None:
    """Refuse an id that is not `<exam>-Q<NN>`."""
    bank = minimal_bank()
    bank["questions"][0]["id"] = "TESTE-1"
    assert any("invalid id" in item for item in errors_of(bank))


def test_a_repeated_id_is_rejected() -> None:
    """Refuse two questions that claim the same identity."""
    bank = minimal_bank()
    bank["questions"][1] = copy.deepcopy(bank["questions"][0])
    assert any("duplicate id" in item for item in errors_of(bank))


def test_an_undeclared_exam_is_rejected() -> None:
    """Refuse a question pointing at an exam `exams[]` does not declare."""
    bank = minimal_bank()
    bank["questions"][0]["exam"] = "ENA99"
    assert any("is not declared in exams[]" in item for item in errors_of(bank))


def test_an_exam_without_questions_is_rejected() -> None:
    """Refuse an exam declared in the bank that holds no question."""
    bank = minimal_bank()
    bank["exams"].append(
        {
            "id": "VAZIO",
            "title": "Caderno vazio",
            "date": "2020-01-01",
            "file": "Prova_VAZIO.pdf",
            "hasOfficialAnswerKey": False,
        }
    )
    assert any("has no question" in item for item in errors_of(bank))


def test_non_contiguous_numbering_is_rejected() -> None:
    """Refuse a paper whose questions are not numbered 1..N."""
    bank = minimal_bank()
    bank["questions"][1]["id"] = "TESTE-Q05"
    bank["questions"][1]["number"] = 5
    assert any("not contiguous" in item for item in errors_of(bank))


# --------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------


def test_a_missing_option_is_rejected() -> None:
    """Refuse a question the app could not render."""
    bank = minimal_bank()
    del bank["questions"][0]["options"]["d"]
    assert any("missing option(s): d" in item for item in errors_of(bank))


def test_an_empty_option_is_rejected() -> None:
    """Refuse an option that is present but blank."""
    bank = minimal_bank()
    bank["questions"][0]["options"]["b"] = "   "
    assert any("option b is empty" in item for item in errors_of(bank))


def test_a_fifth_option_is_rejected() -> None:
    """Refuse a letter beyond a-d."""
    bank = minimal_bank()
    bank["questions"][0]["options"]["e"] = "Cinco."
    assert any("unexpected option(s): e" in item for item in errors_of(bank))


# --------------------------------------------------------------------------
# The answer and its provenance
# --------------------------------------------------------------------------


def test_a_missing_letter_needs_an_excluded_reason() -> None:
    """Refuse a gradable question that has no correct option.

    Only a question the official key withdrew may leave `letter` out.
    """
    bank = minimal_bank()
    del bank["questions"][0]["answer"]["letter"]
    assert any("only an excluded question may do" in item for item in errors_of(bank))


def test_an_excluded_question_may_omit_its_letter() -> None:
    """Accept the annulled question the official key gives no letter to.

    AV2-POL-Q14 is the real case: the key prints ANULADA where a letter
    belongs, so there is nothing to record.
    """
    bank = minimal_bank()
    del bank["questions"][0]["answer"]["letter"]
    bank["questions"][0]["excludedReason"] = "annulled"
    assert errors_of(bank) == []


def test_a_letter_outside_a_to_d_is_rejected() -> None:
    """Refuse a letter no option carries."""
    bank = minimal_bank()
    bank["questions"][0]["answer"]["letter"] = "e"
    assert any("answer.letter must be one of" in item for item in errors_of(bank))


def test_an_official_answer_must_not_carry_confidence() -> None:
    """Refuse a confidence level on a published fact.

    `official` means a published key states the letter. A published answer has
    no confidence, because it is not an inference.
    """
    bank = minimal_bank()
    bank["questions"][0]["answer"]["confidence"] = "high"
    assert any("must not carry confidence" in item for item in errors_of(bank))


def test_an_official_answer_must_not_carry_a_rationale() -> None:
    """Refuse a derived answer's argument on an official one."""
    bank = minimal_bank()
    bank["questions"][0]["answer"]["rationale"] = "porque sim"
    assert any("must not carry rationale" in item for item in errors_of(bank))


def test_an_empty_explanation_is_rejected() -> None:
    """Refuse an explanation that is present but blank."""
    bank = minimal_bank()
    bank["questions"][0]["answer"]["explanation"] = "   "
    assert any("explanation is present but empty" in item for item in errors_of(bank))


def test_a_derived_answer_needs_confidence_rationale_and_reference() -> None:
    """Refuse a derived answer that cannot be audited.

    No paper in the registry needs one today, but the contract still describes
    it and the validator still enforces it, so a future paper without a
    published key has somewhere to land.
    """
    bank = minimal_bank()
    bank["questions"][0]["answer"] = {"letter": "c", "source": "derived"}
    messages = errors_of(bank)
    assert any("needs confidence" in item for item in messages)
    assert any("needs a non-empty rationale" in item for item in messages)
    assert any("reference is missing" in item for item in messages)


def test_a_derived_answer_must_not_carry_an_explanation() -> None:
    """Refuse a derived answer that argues its letter in the wrong field."""
    bank = minimal_bank()
    bank["questions"][0]["answer"] = {
        "letter": "c",
        "source": "derived",
        "confidence": "high",
        "reference": "Ref2-Patente_2021.pdf, p. 30",
        "rationale": "Deduzido do artigo 40.",
        "explanation": "Tambem porque sim.",
    }
    assert any(
        "'explanation' belongs to an official" in item for item in errors_of(bank)
    )


def test_a_valid_derived_answer_is_accepted() -> None:
    """Accept a derived answer that carries everything it needs."""
    bank = minimal_bank()
    bank["questions"][0]["answer"] = {
        "letter": "c",
        "source": "derived",
        "confidence": "high",
        "reference": "Ref2-Patente_2021.pdf, p. 30",
        "rationale": "Deduzido do artigo 40.",
    }
    assert errors_of(bank) == []


def test_an_unknown_source_is_rejected() -> None:
    """Refuse a provenance the contract does not define."""
    bank = minimal_bank()
    bank["questions"][0]["answer"]["source"] = "guessed"
    assert any("answer.source is invalid" in item for item in errors_of(bank))


def test_a_missing_reference_is_rejected() -> None:
    """Refuse an answer that says nothing about what supports it."""
    bank = minimal_bank()
    del bank["questions"][0]["answer"]["reference"]
    assert any("reference is missing" in item for item in errors_of(bank))


def test_an_unknown_answer_field_is_rejected() -> None:
    """Refuse a field the answer contract does not declare."""
    bank = minimal_bank()
    bank["questions"][0]["answer"]["justificativa"] = "campo antigo"
    assert any("unexpected field(s) in answer" in item for item in errors_of(bank))


# --------------------------------------------------------------------------
# Topics
# --------------------------------------------------------------------------


def test_an_undeclared_topic_is_rejected() -> None:
    """Refuse a topic slug the taxonomy does not declare."""
    bank = minimal_bank()
    bank["questions"][0]["topic"] = "propriedade-intelectual"
    assert any("is not declared in topics[]" in item for item in errors_of(bank))


def test_a_topic_nothing_uses_is_rejected() -> None:
    """Refuse a taxonomy entry no question is filed under."""
    bank = minimal_bank()
    bank["topics"].append(
        {"id": "orfao", "label": "Orfao", "definition": "Nada usa este tema."}
    )
    assert any("declared but no question uses it" in item for item in errors_of(bank))


def test_a_topic_slug_must_be_kebab_case() -> None:
    """Refuse a slug that is not the unaccented kebab-case the app expects."""
    bank = minimal_bank()
    bank["topics"][0]["id"] = "Patente Nova"
    bank["questions"][0]["topic"] = "Patente Nova"
    assert any("expected kebab-case" in item for item in errors_of(bank))


def test_a_topic_without_a_label_is_rejected() -> None:
    """Refuse a taxonomy entry with nothing to display."""
    bank = minimal_bank()
    del bank["topics"][0]["label"]
    assert any("label is missing or empty" in item for item in errors_of(bank))


def test_a_missing_topics_array_buries_nothing() -> None:
    """Report the one failure that matters when the taxonomy is unusable.

    Without it every question would report the same "not declared" error,
    burying the real problem under a hundred and forty-four copies of itself.
    """
    bank = minimal_bank()
    bank["topics"] = []
    messages = errors_of(bank)
    assert any("topics: must be a non-empty array" in item for item in messages)
    assert len(messages) == 2


# --------------------------------------------------------------------------
# Duplicates, defects and exclusions
# --------------------------------------------------------------------------


def test_a_duplicate_of_pointing_nowhere_is_rejected() -> None:
    """Refuse a repeat that names a question the bank does not hold."""
    bank = minimal_bank()
    bank["questions"][1]["duplicateOf"] = "TESTE-Q99"
    assert any("which does not exist" in item for item in errors_of(bank))


def test_a_duplicate_of_pointing_at_a_duplicate_is_rejected() -> None:
    """Refuse a chain of repeats, so every repeat names one original."""
    bank = minimal_bank()
    bank["questions"][0]["duplicateOf"] = "TESTE-Q02"
    bank["questions"][1]["duplicateOf"] = "TESTE-Q01"
    assert any("which is itself a duplicate" in item for item in errors_of(bank))


def test_an_unknown_excluded_reason_is_rejected() -> None:
    """Refuse an exclusion reason outside the enum."""
    bank = minimal_bank()
    bank["questions"][0]["excludedReason"] = "because-i-said-so"
    assert any("excludedReason must be one of" in item for item in errors_of(bank))


def test_empty_known_defects_are_rejected() -> None:
    """Refuse an empty defect list, which says nothing at all."""
    bank = minimal_bank()
    bank["questions"][0]["knownDefects"] = []
    assert any("must be a non-empty array" in item for item in errors_of(bank))


def test_an_unknown_question_field_is_rejected() -> None:
    """Refuse a field the question contract does not declare."""
    bank = minimal_bank()
    bank["questions"][0]["excluded"] = True
    assert any("unexpected field(s): excluded" in item for item in errors_of(bank))


# --------------------------------------------------------------------------
# Residue
# --------------------------------------------------------------------------


def test_residue_in_the_stem_is_rejected() -> None:
    """Refuse a stem that still holds a page footer."""
    bank = minimal_bank()
    bank["questions"][0]["stem"] += " Pagina 3 de 8"
    assert any("stem holds page header or footer" in item for item in errors_of(bank))


def test_residue_in_an_option_is_rejected() -> None:
    """Refuse an option that still holds a page footer.

    Noise, column-layout and residue checks once ran on the stem alone, so
    thirteen questions shipped with a footer inside their *options* while
    reporting `parseStatus: "ok"`.
    """
    bank = minimal_bank()
    bank["questions"][0]["options"]["d"] = "Quatro. Etapa 1 - Prova Pg. 15/15"
    assert any(
        "option d holds page header or footer" in item for item in errors_of(bank)
    )


def test_a_stem_that_is_too_short_is_rejected() -> None:
    """Refuse a stem so short it can only be a parsing failure."""
    bank = minimal_bank()
    bank["questions"][0]["stem"] = "Ok"
    assert any("stem is missing or too short" in item for item in errors_of(bank))


# --------------------------------------------------------------------------
# Totals and the command line
# --------------------------------------------------------------------------


def test_the_expected_total_is_enforced_when_given() -> None:
    """Refuse a bank that holds a different number of questions than asked."""
    errors = list(validate(minimal_bank(), expected_total=144))
    assert any("expected 144 questions, found 2" in item for item in errors)


def test_main_reports_a_missing_file(tmp_path: Path) -> None:
    """Exit non-zero when the bank to check is not there.

    Args:
        tmp_path: Fixture providing a directory that stays empty.
    """
    assert validate_main([str(tmp_path / "absent.json")]) == 1


def test_main_reports_invalid_json(tmp_path: Path) -> None:
    """Exit non-zero when the file is not JSON at all.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "bank.json"
    path.write_text("{", encoding="utf-8")
    assert validate_main([str(path)]) == 1


def test_main_accepts_a_valid_bank(tmp_path: Path) -> None:
    """Exit zero for a bank that satisfies the contract.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(minimal_bank(), ensure_ascii=False), encoding="utf-8")
    assert validate_main([str(path), "--expected-total", "0"]) == 0


def test_main_rejects_a_broken_bank(tmp_path: Path) -> None:
    """Exit non-zero for a bank that breaks the contract.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    bank = minimal_bank()
    del bank["questions"][0]["answer"]["letter"]
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    assert validate_main([str(path), "--expected-total", "0"]) == 1


@pytest.mark.parametrize("field", ["exams", "topics", "questions"])
def test_an_empty_array_is_rejected(field: str) -> None:
    """Refuse a bank missing one of the three arrays it is made of.

    Args:
        field: The array to empty.
    """
    bank = minimal_bank()
    bank[field] = []
    assert any(item.startswith(f"{field}:") for item in errors_of(bank))
