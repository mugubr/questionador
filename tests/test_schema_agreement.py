"""`data/schema.json` and `tools/validate.py` must accept and reject the same.

The schema is authoritative and the validator implements it, so a rule that
lives in one and not the other is a bug. Mutation testing is what finds that:
each mutation breaks the published bank in exactly one way, and both
implementations have to say no.

Some rules are referential — they cross from one array of the bank into another
— and JSON Schema 2020-12 cannot express them at all. `data/schema.json` states
each of those in a `description` and the validator is what enforces them, so
those cases are asserted against the validator alone, on purpose.

`jsonschema` is a development-only dependency: the pipeline itself must stay
free of runtime dependencies, so this module skips cleanly when it is absent.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any, cast

import pytest

from tools import config
from tools.validate import validate

jsonschema = pytest.importorskip(
    "jsonschema",
    reason=(
        "jsonschema is a development-only dependency. Add it to the [dependency-groups]"
        " dev list in pyproject.toml to run the schema-agreement tests."
    ),
)

Bank = dict[str, Any]
Mutation = Callable[[Bank], None]


def question(bank: Bank, question_id: str) -> dict[str, Any]:
    """Find one question of a bank by id.

    Args:
        bank: The decoded bank.
        question_id: The id to look for.

    Returns:
        The question object, which the caller may mutate in place.
    """
    return next(item for item in bank["questions"] if item["id"] == question_id)


def first_explained(bank: Bank) -> dict[str, Any]:
    """Find the first question whose answer carries an explanation.

    Args:
        bank: The decoded bank.

    Returns:
        The question object, which the caller may mutate in place.
    """
    return next(item for item in bank["questions"] if "explanation" in item["answer"])


# --------------------------------------------------------------------------
# Mutations both implementations must reject
# --------------------------------------------------------------------------


def drop_letter_without_a_reason(bank: Bank) -> None:
    """Remove answer.letter from a question that is not excluded.

    Args:
        bank: The bank to break.
    """
    del question(bank, "ENA26-Q01")["answer"]["letter"]


def drop_the_reason_of_the_letterless_question(bank: Bank) -> None:
    """Remove excludedReason from the annulled, letter-less question.

    Args:
        bank: The bank to break.
    """
    del question(bank, "AV2-POL-Q14")["excludedReason"]


def unknown_excluded_reason(bank: Bank) -> None:
    """Set an excludedReason outside the enum.

    Args:
        bank: The bank to break.
    """
    question(bank, "AV2-PI-Q14")["excludedReason"] = "because-i-said-so"


def derived_answer_missing_letter_on_excluded_question(bank: Bank) -> None:
    """Turn an excluded question's letter-less answer into a derived one.

    `AV2-POL-Q14` is annulled and already has no `letter`, which is legal
    only because its answer is official (there is no key to defer to). A
    derived answer has no key at all, so it always needs its own letter,
    excluded or not.

    Args:
        bank: The bank to break.
    """
    answer = question(bank, "AV2-POL-Q14")["answer"]
    answer["source"] = "derived"
    answer["confidence"] = "high"
    answer["rationale"] = "porque sim"
    answer.pop("explanation", None)


def uppercase_letter(bank: Bank) -> None:
    """Write the answer letter in upper case, as the key PDFs print it.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["answer"]["letter"] = "C"


def letter_outside_the_options(bank: Bank) -> None:
    """Point the answer at a letter no option carries.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["answer"]["letter"] = "e"


def missing_source(bank: Bank) -> None:
    """Publish an answer that does not say where it came from.

    Args:
        bank: The bank to break.
    """
    del question(bank, "ENA26-Q01")["answer"]["source"]


def missing_reference(bank: Bank) -> None:
    """Publish an answer that says nothing about what supports it.

    Args:
        bank: The bank to break.
    """
    del question(bank, "ENA26-Q01")["answer"]["reference"]


def official_answer_with_confidence(bank: Bank) -> None:
    """Give an official answer a confidence level.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["answer"]["confidence"] = "high"


def official_answer_with_rationale(bank: Bank) -> None:
    """Give an official answer a derived answer's rationale.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["answer"]["rationale"] = "porque sim"


def derived_answer_with_explanation(bank: Bank) -> None:
    """Give a derived answer both a rationale and an explanation.

    Args:
        bank: The bank to break.
    """
    answer = question(bank, "ENA26-Q01")["answer"]
    answer["source"] = "derived"
    answer["confidence"] = "high"
    answer["rationale"] = "porque sim"
    answer["explanation"] = "porque tambem"


def derived_answer_without_rationale(bank: Bank) -> None:
    """Declare a derived answer without the argument it needs.

    Args:
        bank: The bank to break.
    """
    answer = question(bank, "ENA26-Q01")["answer"]
    answer["source"] = "derived"
    answer["confidence"] = "high"
    answer.pop("explanation", None)


def blank_explanation(bank: Bank) -> None:
    """Leave an explanation present but blank.

    Args:
        bank: The bank to break.
    """
    first_explained(bank)["answer"]["explanation"] = "   "


def answer_with_an_undeclared_field(bank: Bank) -> None:
    """Add a field the answer contract does not allow.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["answer"]["justificativa"] = "campo antigo"


def question_with_an_undeclared_field(bank: Bank) -> None:
    """Add a field the question contract does not allow.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["excluded"] = True


def root_with_an_undeclared_field(bank: Bank) -> None:
    """Add a field the root contract does not allow.

    Args:
        bank: The bank to break.
    """
    bank["topicos"] = []


def missing_option(bank: Bank) -> None:
    """Remove one of the four options.

    Args:
        bank: The bank to break.
    """
    del question(bank, "ENA26-Q01")["options"]["d"]


def blank_option(bank: Bank) -> None:
    """Leave an option present but blank.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["options"]["b"] = "   "


def fifth_option(bank: Bank) -> None:
    """Add a letter beyond a-d.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["options"]["e"] = "Quinta."


def stem_too_short(bank: Bank) -> None:
    """Shorten a stem to something no real question could be.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["stem"] = "Ok"


def malformed_question_id(bank: Bank) -> None:
    """Give a question an id that is not `<exam>-Q<NN>`.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["id"] = "ENA26-1"


def number_out_of_range(bank: Bank) -> None:
    """Give a question a number outside 1..99.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["number"] = 0


def unknown_bank_version(bank: Bank) -> None:
    """Declare a format version the code does not implement.

    Args:
        bank: The bank to break.
    """
    bank["version"] = 2


def malformed_generated_at(bank: Bank) -> None:
    """Write the build date in a format nothing can parse.

    Args:
        bank: The bank to break.
    """
    bank["generatedAt"] = "26/08/2026"


def toolchain_without_pdftotext(bank: Bank) -> None:
    """Publish a bank that does not say which pdftotext produced it.

    Args:
        bank: The bank to break.
    """
    bank["toolchain"] = {}


def blank_toolchain_entry(bank: Bank) -> None:
    """Give a non-required toolchain entry a blank version.

    `pdftotext` is the only entry the validator checked for non-blankness
    before this test existed; every other key was only type-checked.

    Args:
        bank: The bank to break.
    """
    bank["toolchain"]["extra-tool"] = "   "


def empty_known_defects(bank: Bank) -> None:
    """Record an empty list of defects, which says nothing at all.

    Args:
        bank: The bank to break.
    """
    question(bank, "AV2-MET-Q14")["knownDefects"] = []


def empty_questions_array(bank: Bank) -> None:
    """Publish a bank with no questions in it.

    Args:
        bank: The bank to break.
    """
    bank["questions"] = []


def empty_exams_array(bank: Bank) -> None:
    """Publish a bank that declares no exam.

    Args:
        bank: The bank to break.
    """
    bank["exams"] = []


def drop_topics_array(bank: Bank) -> None:
    """Remove the taxonomy from the bank.

    Args:
        bank: The bank to break.
    """
    del bank["topics"]


def empty_topics_array(bank: Bank) -> None:
    """Leave the taxonomy declared but empty.

    Args:
        bank: The bank to break.
    """
    bank["topics"] = []


def topic_without_a_label(bank: Bank) -> None:
    """Remove the displayed label of a topic.

    Args:
        bank: The bank to break.
    """
    del bank["topics"][0]["label"]


def topic_with_a_blank_definition(bank: Bank) -> None:
    """Blank a topic's definition.

    Args:
        bank: The bank to break.
    """
    bank["topics"][0]["definition"] = "   "


def topic_with_an_undeclared_field(bank: Bank) -> None:
    """Add a field the topic contract does not allow.

    Args:
        bank: The bank to break.
    """
    bank["topics"][0]["area"] = "propriedade-intelectual"


def topic_slug_not_kebab_case(bank: Bank) -> None:
    """Give a topic a slug that is not unaccented kebab-case.

    Args:
        bank: The bank to break.
    """
    slug = bank["topics"][0]["id"]
    bank["topics"][0]["id"] = "Patente Nova"
    for item in bank["questions"]:
        if item["topic"] == slug:
            item["topic"] = "Patente Nova"


def duplicate_topic_slug(bank: Bank) -> None:
    """Declare the same topic twice, byte for byte.

    Args:
        bank: The bank to break.
    """
    bank["topics"].append(copy.deepcopy(bank["topics"][0]))


def blank_question_topic(bank: Bank) -> None:
    """Blank a question's topic.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA25-Q01")["topic"] = "   "


def missing_question_topic(bank: Bank) -> None:
    """Remove a question's topic entirely.

    Args:
        bank: The bank to break.
    """
    del question(bank, "ENA25-Q01")["topic"]


def exam_without_an_answer_key_flag(bank: Bank) -> None:
    """Remove the flag that says whether a published key backs a paper.

    Args:
        bank: The bank to break.
    """
    del bank["exams"][0]["hasOfficialAnswerKey"]


def exam_with_a_malformed_date(bank: Bank) -> None:
    """Write an exam date in a format nothing can parse.

    Args:
        bank: The bank to break.
    """
    bank["exams"][0]["date"] = "22 de novembro de 2025"


SHARED_MUTATIONS: tuple[tuple[str, Mutation], ...] = (
    (
        "answer.letter dropped on a question that is not excluded",
        drop_letter_without_a_reason,
    ),
    (
        "excludedReason dropped on the letter-less question",
        drop_the_reason_of_the_letterless_question,
    ),
    ("excludedReason outside the enum", unknown_excluded_reason),
    (
        "derived answer.letter dropped on an excluded question",
        derived_answer_missing_letter_on_excluded_question,
    ),
    ("answer.letter in upper case", uppercase_letter),
    ("answer.letter outside a-d", letter_outside_the_options),
    ("answer without a source", missing_source),
    ("answer without a reference", missing_reference),
    ("official answer carrying confidence", official_answer_with_confidence),
    ("official answer carrying rationale", official_answer_with_rationale),
    ("derived answer carrying an explanation", derived_answer_with_explanation),
    ("derived answer without a rationale", derived_answer_without_rationale),
    ("explanation present but blank", blank_explanation),
    ("answer with an undeclared field", answer_with_an_undeclared_field),
    ("question with an undeclared field", question_with_an_undeclared_field),
    ("root with an undeclared field", root_with_an_undeclared_field),
    ("a missing option", missing_option),
    ("an option present but blank", blank_option),
    ("a fifth option", fifth_option),
    ("a stem below the minimum length", stem_too_short),
    ("a malformed question id", malformed_question_id),
    ("a question number outside 1..99", number_out_of_range),
    ("an unsupported bank version", unknown_bank_version),
    ("a malformed generatedAt", malformed_generated_at),
    ("a toolchain without pdftotext", toolchain_without_pdftotext),
    ("a blank toolchain entry that is not pdftotext", blank_toolchain_entry),
    ("an empty knownDefects array", empty_known_defects),
    ("an empty questions array", empty_questions_array),
    ("an empty exams array", empty_exams_array),
    ("topics[] missing", drop_topics_array),
    ("topics[] empty", empty_topics_array),
    ("a topic without a label", topic_without_a_label),
    ("a topic with a blank definition", topic_with_a_blank_definition),
    ("a topic with an undeclared field", topic_with_an_undeclared_field),
    ("a topic slug that is not kebab-case", topic_slug_not_kebab_case),
    ("a topic slug declared twice", duplicate_topic_slug),
    ("a question topic left blank", blank_question_topic),
    ("a question with no topic at all", missing_question_topic),
    ("an exam without hasOfficialAnswerKey", exam_without_an_answer_key_flag),
    ("an exam with a malformed date", exam_with_a_malformed_date),
)


# --------------------------------------------------------------------------
# Referential mutations JSON Schema cannot express
# --------------------------------------------------------------------------


def undeclared_question_topic(bank: Bank) -> None:
    """Point a question at a topic the taxonomy does not declare.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA25-Q01")["topic"] = "tema-que-nao-existe"


def unused_topic(bank: Bank) -> None:
    """Declare a topic no question is filed under.

    Args:
        bank: The bank to break.
    """
    bank["topics"].append(
        {"id": "orfao", "label": "Orfao", "definition": "Nada usa este tema."}
    )


def undeclared_exam(bank: Bank) -> None:
    """Point a question at an exam that exams[] does not declare.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["exam"] = "ENA99"


def dangling_duplicate_of(bank: Bank) -> None:
    """Point duplicateOf at a question that does not exist.

    Args:
        bank: The bank to break.
    """
    question(bank, "AV2-PI-Q14")["duplicateOf"] = "AV2-PI-Q99"


def id_disagreeing_with_its_number(bank: Bank) -> None:
    """Renumber a question without renaming it.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["number"] = 7


def footer_residue_in_an_option(bank: Bank) -> None:
    """Put a page footer back inside an option.

    Args:
        bank: The bank to break.
    """
    question(bank, "ENA26-Q01")["options"]["d"] += " Etapa 1 - Prova Pg. 15/15"


REFERENTIAL_MUTATIONS: tuple[tuple[str, Mutation], ...] = (
    ("question.topic not declared in topics[]", undeclared_question_topic),
    ("a topic declared but never used", unused_topic),
    ("question.exam not declared in exams[]", undeclared_exam),
    ("duplicateOf pointing at no question", dangling_duplicate_of),
    ("id disagreeing with exam and number", id_disagreeing_with_its_number),
    ("page footer residue inside an option", footer_residue_in_an_option),
)


# --------------------------------------------------------------------------
# The tests
# --------------------------------------------------------------------------


def load_schema() -> dict[str, Any]:
    """Read the authoritative contract.

    Returns:
        The decoded `data/schema.json`.
    """
    return cast(
        "dict[str, Any]",
        json.loads((config.DATA_DIR / "schema.json").read_text(encoding="utf-8")),
    )


def load_bank() -> Bank:
    """Decode the committed question bank afresh for one mutation to break.

    Every mutation below edits the bank in place, so each case has to start
    from its own copy: a shared one would carry the previous case's damage and
    make the failures depend on the order the tests happened to run in.

    Returns:
        The decoded bank, exactly as it is published.
    """
    return cast(
        "Bank",
        json.loads(config.QUESTION_BANK_PATH.read_text(encoding="utf-8")),
    )


def test_the_published_bank_satisfies_the_json_schema() -> None:
    """Accept the published bank with the authoritative contract itself."""
    checker = jsonschema.Draft202012Validator(load_schema())
    assert sorted(error.message for error in checker.iter_errors(load_bank())) == []


def test_the_schema_is_itself_a_valid_json_schema() -> None:
    """Check the contract against the meta-schema it declares."""
    jsonschema.Draft202012Validator.check_schema(load_schema())


@pytest.mark.parametrize(
    ("name", "mutate"),
    SHARED_MUTATIONS,
    ids=[name for name, _ in SHARED_MUTATIONS],
)
def test_the_schema_and_the_validator_reject_the_same_mutation(
    name: str, mutate: Mutation
) -> None:
    """Reject one broken bank with both implementations of the contract.

    A mutation only one of them catches is a rule that lives in one and not the
    other, which is the bug this test exists to find.

    Args:
        name: What the mutation breaks, for the failure message.
        mutate: The mutation to apply.
    """
    candidate = load_bank()
    mutate(candidate)

    checker = jsonschema.Draft202012Validator(load_schema())
    rejected_by_schema = not checker.is_valid(candidate)
    rejected_by_validator = bool(validate(candidate))

    assert rejected_by_schema, f"data/schema.json accepts {name}"
    assert rejected_by_validator, f"tools/validate.py accepts {name}"


@pytest.mark.parametrize(
    ("name", "mutate"),
    REFERENTIAL_MUTATIONS,
    ids=[name for name, _ in REFERENTIAL_MUTATIONS],
)
def test_the_validator_enforces_the_referential_rules(
    name: str, mutate: Mutation
) -> None:
    """Reject a rule that crosses from one array of the bank into another.

    JSON Schema 2020-12 cannot express these, so `data/schema.json` states each
    of them in a `description` and the validator is what enforces them. The
    assertion is one-sided on purpose.

    Args:
        name: What the mutation breaks, for the failure message.
        mutate: The mutation to apply.
    """
    candidate = load_bank()
    mutate(candidate)

    assert bool(validate(candidate)), f"tools/validate.py accepts {name}"
