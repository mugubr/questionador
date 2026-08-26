"""Tests for assembling the published bank out of its editable layers.

Everything here runs on inline structures. The layers that read the filesystem
are given temporary files, and the one layer that needs a subprocess — reading
the published answer keys — is replaced, because none of the rules under test
depend on how the key PDF was decoded.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tools import build, config
from tools.build import (
    BuildError,
    apply_override,
    build_answer,
    carried_generated_at,
    check_extraction_is_current,
    load_explanations,
    load_official_keys,
    load_raw_questions,
    load_topics,
    parse_question_id,
    read_json_object,
    reconcile_toolchain,
    render_javascript,
    render_json,
    render_markdown,
    report_orphan_keys,
    resolve_key_number,
    write_text,
)
from tools.config import ExamPaper
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

OPTIONS = {"a": "Dez anos.", "b": "Quinze anos.", "c": "Vinte anos.", "d": "Trinta."}


def make_raw(
    question_id: str = "ENA26-Q01",
    *,
    status: ParseStatus = ParseStatus.REVIEW,
    issues: tuple[str, ...] = ("stem: column-matching wording",),
) -> RawQuestion:
    """Build one extracted question to overlay an override on.

    Args:
        question_id: The id the question carries.
        status: Whether the extractor left it flagged for review.
        issues: The reasons it was flagged.

    Returns:
        The extracted question.
    """
    exam, _, number = question_id.partition("-Q")
    return RawQuestion(
        id=question_id,
        exam=exam,
        number=int(number),
        stem="Correlacione a coluna 1 com a coluna 2:",
        options=dict(OPTIONS),
        parse_status=status,
        issues=issues,
    )


def make_question(
    question_id: str = "ENA26-Q01",
    *,
    letter: OptionLetter | None = OptionLetter.C,
    options: Mapping[str, str] | None = None,
    duplicate_of: str | None = None,
    excluded_reason: ExcludedReason | None = None,
    known_defects: tuple[str, ...] = (),
) -> Question:
    """Build one published question for the renderers.

    Args:
        question_id: The id the question carries.
        letter: The keyed option, or None when the key annulled it.
        options: The options to publish; the four defaults when None.
        duplicate_of: The id this question repeats, when it repeats one.
        excluded_reason: Why the question must never be drawn.
        known_defects: Defects of the printed paper.

    Returns:
        The published question.
    """
    exam, _, number = question_id.partition("-Q")
    return Question(
        id=question_id,
        exam=exam,
        number=int(number),
        topic="patente",
        stem="Sobre a patente de invencao, assinale a correta:",
        options=dict(OPTIONS) if options is None else dict(options),
        answer=Answer(
            letter=letter,
            source=AnswerSource.OFFICIAL,
            reference="Gabarito-Final_ENA26.pdf",
            explanation="Material de estudo.",
        ),
        duplicate_of=duplicate_of,
        known_defects=known_defects,
        excluded_reason=excluded_reason,
    )


def make_bank(questions: Sequence[Question]) -> QuestionBank:
    """Wrap questions in the smallest bank the renderers accept.

    Args:
        questions: The questions to publish.

    Returns:
        The assembled bank.
    """
    return QuestionBank(
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
        questions=list(questions),
    )


def committed_raw_questions() -> list[RawQuestion]:
    """Read the committed extraction anchor.

    Returns:
        Every extracted question, in the order it was written.
    """
    questions, _ = load_raw_questions(config.RAW_QUESTIONS_PATH)
    return questions


def committed_keys() -> dict[str, dict[int, OptionLetter | None]]:
    """Read the committed answer keys.

    Returns:
        The parsed key of each paper, by exam id, as a mutable copy.
    """
    keys, _ = load_official_keys(config.ANSWER_KEYS_PATH)
    return {exam_id: dict(rows) for exam_id, rows in keys.items()}


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def test_parse_question_id_splits_a_well_formed_id() -> None:
    """Split an id into the exam and the number it must agree with."""
    assert parse_question_id("AV2-PI-Q13") == ("AV2-PI", 13)


@pytest.mark.parametrize(
    "question_id", ["ENA26-Q1", "ena26-Q01", "ENA26Q01", "ENA26-Q001", ""]
)
def test_parse_question_id_rejects_a_malformed_id(question_id: str) -> None:
    """Refuse an id that is not exactly `<exam>-Q<NN>`.

    Args:
        question_id: An id the contract does not allow.
    """
    assert parse_question_id(question_id) is None


# --------------------------------------------------------------------------
# The override layer
# --------------------------------------------------------------------------


def test_an_override_that_only_carries_a_comment_is_rejected() -> None:
    """Refuse an override that clears the review flag without changing text.

    An entry holding nothing but its reason used to be applied as a no-op that
    still marked the question resolved, which is how a question flagged for
    review reached the bank exactly as the parser had left it.
    """
    question = make_raw()
    errors = ErrorLog()

    result = apply_override(question, {"_reason": "conferido a mao"}, errors)

    assert result is question
    assert result.parse_status is ParseStatus.REVIEW
    assert list(errors) == ["ENA26-Q01: override must set 'stem' or 'options'"]


def test_an_override_with_an_unknown_key_is_rejected() -> None:
    """Refuse a typo that would otherwise be applied as nothing at all."""
    errors = ErrorLog()
    question = make_raw()

    result = apply_override(question, {"enunciado": "texto"}, errors)

    assert result is question
    assert any("unknown key(s): enunciado" in item for item in errors)


def test_an_override_may_replace_only_the_stem() -> None:
    """Replace the stem and keep the extracted options."""
    errors = ErrorLog()
    result = apply_override(make_raw(), {"stem": "Assinale a correta:"}, errors)

    assert result.stem == "Assinale a correta:"
    assert dict(result.options) == OPTIONS
    assert result.parse_status is ParseStatus.OK
    assert result.issues == ()
    assert not errors


def test_an_override_may_replace_only_the_options() -> None:
    """Replace the options and keep the extracted stem."""
    errors = ErrorLog()
    replacement = {"a": "1.", "b": "2.", "c": "3.", "d": "4."}

    result = apply_override(make_raw(), {"options": replacement}, errors)

    assert dict(result.options) == replacement
    assert result.stem == "Correlacione a coluna 1 com a coluna 2:"
    assert not errors


def test_an_override_stem_must_not_be_blank() -> None:
    """Refuse a blank replacement, which would empty a question."""
    errors = ErrorLog()
    question = make_raw()

    assert apply_override(question, {"stem": "   "}, errors) is question
    assert any("must be a non-empty string" in item for item in errors)


def test_an_override_options_must_map_letters_to_strings() -> None:
    """Refuse options that are not text."""
    errors = ErrorLog()
    question = make_raw()

    assert apply_override(question, {"options": {"a": 1}}, errors) is question
    assert any("must map letters to strings" in item for item in errors)


# --------------------------------------------------------------------------
# Reading the key at the right row
# --------------------------------------------------------------------------


def test_resolve_key_number_is_the_question_number_by_default() -> None:
    """Read the key at the question's own row for an ordinary question."""
    assert resolve_key_number(7, None, None) == 7


def test_resolve_key_number_follows_a_reprinted_question_to_its_original() -> None:
    """Read the key at the repeated question's row for a booklet reprint.

    The key row carrying the reprint's own number answers the question the real
    exam had there, which the defective booklet did not print.
    """
    number = resolve_key_number(14, ExcludedReason.SOURCE_BOOKLET_DEFECT, "AV2-PI-Q13")
    assert number == 13


def test_resolve_key_number_keeps_its_own_row_for_an_annulled_question() -> None:
    """Read the key at its own row for a question the key annulled."""
    assert resolve_key_number(14, ExcludedReason.ANNULLED, None) == 14


def test_resolve_key_number_keeps_its_own_row_without_a_duplicate() -> None:
    """Read the key at its own row when no original was registered."""
    assert resolve_key_number(14, ExcludedReason.SOURCE_BOOKLET_DEFECT, None) == 14


# --------------------------------------------------------------------------
# The answer layer
# --------------------------------------------------------------------------


def test_build_answer_reads_the_letter_from_the_published_key() -> None:
    """Take the letter from the key and nothing else."""
    errors = ErrorLog()
    answer = build_answer(
        "ENA26-Q01", "ENA26", 1, {"ENA26": {1: OptionLetter.C}}, {}, errors
    )

    assert answer is not None
    assert answer.letter is OptionLetter.C
    assert answer.source is AnswerSource.OFFICIAL
    assert answer.reference == "Gabarito-Final_ENA26.pdf"
    assert answer.confidence is None
    assert answer.rationale is None
    assert not errors


def test_build_answer_keeps_an_annulled_question_without_a_letter() -> None:
    """Carry the key's ANULADA through as an answer with no letter."""
    errors = ErrorLog()
    answer = build_answer(
        "AV2-POL-Q14", "AV2-POL", 14, {"AV2-POL": {14: None}}, {}, errors
    )

    assert answer is not None
    assert answer.letter is None
    assert not errors


def test_build_answer_refuses_to_invent_an_answer_without_a_key() -> None:
    """Fail loudly when a paper has no published key, rather than guessing."""
    errors = ErrorLog()

    assert build_answer("X-Q01", "X", 1, {}, {}, errors) is None
    assert any("no published answer key" in item for item in errors)


def test_build_answer_reports_a_row_the_key_does_not_have() -> None:
    """Fail when the key covers the paper but not this question."""
    errors = ErrorLog()

    assert (
        build_answer(
            "ENA26-Q02", "ENA26", 2, {"ENA26": {1: OptionLetter.C}}, {}, errors
        )
        is None
    )
    assert any("no entry in the official answer key" in item for item in errors)


def test_build_answer_rejects_an_unknown_key_in_the_answers_file() -> None:
    """Refuse a field the answers file may not carry.

    The letter and the topic are deliberately not among them: the letter is
    read from the published key and the topic lives once in data/topics.json,
    so neither can disagree with itself.
    """
    errors = ErrorLog()
    explanations = {"ENA26-Q01": {"letter": "c"}}

    answer = build_answer(
        "ENA26-Q01", "ENA26", 1, {"ENA26": {1: OptionLetter.C}}, explanations, errors
    )

    assert answer is None
    assert any("unknown key(s): letter" in item for item in errors)


def test_build_answer_refuses_a_paper_with_no_answer_key_pdf_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse to publish a provenance the registry cannot name.

    The key PDF is the fallback `reference` of every official answer. An
    `assert` used to stand where this check is, and an assert vanishes under
    `python -O`: what would then reach the bank is the literal string "None"
    as the provenance of every answer of the paper.

    Args:
        monkeypatch: Fixture used to stand in for the exam-paper registry.
    """
    paper = ExamPaper(
        id="TEST",
        file="Prova_TEST.pdf",
        title="Caderno de teste",
        date="2020-01-01",
        expected_questions=1,
    )
    monkeypatch.setattr(build, "EXAM_PAPERS_BY_ID", {"TEST": paper})
    errors = ErrorLog()

    answer = build_answer(
        "TEST-Q01", "TEST", 1, {"TEST": {1: OptionLetter.C}}, {}, errors
    )

    assert answer is None
    assert any("no answer-key PDF" in item for item in errors)


def test_build_answer_rejects_a_blank_explanation() -> None:
    """Refuse an explanation that is present but empty."""
    errors = ErrorLog()
    explanations = {"ENA26-Q01": {"explanation": "   "}}

    answer = build_answer(
        "ENA26-Q01", "ENA26", 1, {"ENA26": {1: OptionLetter.C}}, explanations, errors
    )

    assert answer is None
    assert any("must be a non-empty string" in item for item in errors)


# --------------------------------------------------------------------------
# Orphan keys
# --------------------------------------------------------------------------


def test_orphan_keys_are_reported_layer_by_layer() -> None:
    """Report every key of a data layer that matched no question.

    A key that matches nothing is a typo or a stale id, and ignoring it means a
    hand-written fix silently stops being applied.
    """
    errors = ErrorLog()
    report_orphan_keys(
        {
            "data/overrides.json": {"ENA26-Q01", "ENA26-Q99"},
            "data/answers/*.json": {"ENA26-Q98"},
        },
        {"ENA26-Q01"},
        errors,
    )

    assert sorted(errors) == [
        "data/answers/*.json: ENA26-Q98 matches no question",
        "data/overrides.json: ENA26-Q99 matches no question",
    ]


def test_no_orphan_is_reported_when_every_key_matches() -> None:
    """Stay silent when every layer names a question that exists."""
    errors = ErrorLog()
    report_orphan_keys({"data/overrides.json": {"ENA26-Q01"}}, {"ENA26-Q01"}, errors)
    assert not errors


# --------------------------------------------------------------------------
# Reading the input files
# --------------------------------------------------------------------------


def test_read_json_object_rejects_a_top_level_array(tmp_path: Path) -> None:
    """Refuse a file that decodes to a list where an object is required.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "overrides.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(BuildError, match="expected a JSON object"):
        read_json_object(path)


def test_read_json_object_reports_a_missing_file(tmp_path: Path) -> None:
    """Name a required file that is not there.

    Args:
        tmp_path: Fixture providing a directory that stays empty.
    """
    with pytest.raises(BuildError, match="required file is missing"):
        read_json_object(tmp_path / "absent.json")


def test_read_json_object_reports_invalid_json(tmp_path: Path) -> None:
    """Name the file when its contents are not JSON at all.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(BuildError, match="invalid JSON"):
        read_json_object(path)


def test_load_raw_questions_rejects_a_top_level_object(tmp_path: Path) -> None:
    """Refuse an extraction anchor that is not an array.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "raw-questions.json"
    path.write_text(
        json.dumps({"toolchain": {"pdftotext": "25.07.0"}, "questions": {}}),
        encoding="utf-8",
    )
    with pytest.raises(BuildError, match="must be a JSON array"):
        load_raw_questions(path)


def test_load_raw_questions_reports_a_malformed_entry(tmp_path: Path) -> None:
    """Name the field a malformed anchor entry is missing.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "raw-questions.json"
    path.write_text(
        json.dumps(
            {
                "toolchain": {"pdftotext": "25.07.0"},
                "questions": [{"id": "ENA26-Q01"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BuildError, match="missing the field"):
        load_raw_questions(path)


def test_load_explanations_rejects_a_question_defined_twice(tmp_path: Path) -> None:
    """Refuse the same question in two answers files.

    Args:
        tmp_path: Fixture providing the answers directory.
    """
    (tmp_path / "ENA26-part1.json").write_text(
        json.dumps({"ENA26-Q01": {"explanation": "um"}}), encoding="utf-8"
    )
    (tmp_path / "ENA26-part2.json").write_text(
        json.dumps({"ENA26-Q01": {"explanation": "dois"}}), encoding="utf-8"
    )
    with pytest.raises(BuildError, match="defined in more than one answers file"):
        load_explanations(tmp_path)


def test_load_explanations_reports_a_missing_directory(tmp_path: Path) -> None:
    """Name the directory when the answers layer is not there.

    Args:
        tmp_path: Fixture providing a parent for the absent directory.
    """
    with pytest.raises(BuildError, match="required directory is missing"):
        load_explanations(tmp_path / "answers")


def write_topics(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a taxonomy file for `load_topics` to read.

    Args:
        path: Where to write.
        payload: The decoded content the file should hold.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_load_topics_reads_the_taxonomy_and_the_assignments(tmp_path: Path) -> None:
    """Read the taxonomy in declaration order and one topic per question.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "topics.json"
    write_topics(
        path,
        {
            "_reason": "porque sim",
            "topics": [
                {"id": "patente", "label": "Patente", "definition": "Sobre patentes."},
                {"id": "marca", "label": "Marca", "definition": "Sobre marcas."},
            ],
            "assignments": {"ENA26-Q01": "patente"},
        },
    )

    topics, assignments = load_topics(path)

    assert [topic.id for topic in topics] == ["patente", "marca"]
    assert assignments == {"ENA26-Q01": "patente"}


def test_load_topics_rejects_an_unknown_top_level_key(tmp_path: Path) -> None:
    """Refuse a key the taxonomy file may not carry.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "topics.json"
    write_topics(path, {"temas": []})
    with pytest.raises(BuildError, match="unknown top-level key"):
        load_topics(path)


def test_load_topics_rejects_a_duplicate_slug(tmp_path: Path) -> None:
    """Refuse the same slug declared twice.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    entry = {"id": "patente", "label": "Patente", "definition": "Sobre patentes."}
    path = tmp_path / "topics.json"
    write_topics(
        path,
        {"topics": [entry, dict(entry, label="Outra")], "assignments": {"X-Q01": "p"}},
    )
    with pytest.raises(BuildError, match="duplicate topic id"):
        load_topics(path)


def test_load_topics_rejects_an_incomplete_entry(tmp_path: Path) -> None:
    """Refuse a taxonomy entry that is missing a displayed field.

    Args:
        tmp_path: Fixture providing the directory to write the file into.
    """
    path = tmp_path / "topics.json"
    write_topics(
        path,
        {
            "topics": [{"id": "patente", "label": "Patente"}],
            "assignments": {"X-Q01": "patente"},
        },
    )
    with pytest.raises(BuildError, match="is missing definition"):
        load_topics(path)


# --------------------------------------------------------------------------
# Rendering the artifacts
# --------------------------------------------------------------------------


def test_render_json_is_stable_and_newline_terminated() -> None:
    """Render the same bank to the same bytes, every time."""
    bank = make_bank([make_question()])
    first = render_json(bank)
    second = render_json(bank)

    assert first == second
    assert first.endswith("\n")
    assert "\r" not in first
    assert json.loads(first)["questions"][0]["id"] == "ENA26-Q01"


def test_render_markdown_refuses_a_question_with_a_missing_option() -> None:
    """Fail before anything is written when an option is missing.

    The markdown writer used to raise `KeyError` on a missing option letter
    *after* the JSON had already been written, leaving the two artifacts out of
    sync until the next successful build.
    """
    question = make_question(options={"a": "Um.", "b": "Dois.", "c": "Tres."})
    with pytest.raises(BuildError, match="option d is missing"):
        render_markdown(make_bank([question]))


def test_render_markdown_marks_the_keyed_option() -> None:
    """Mark exactly the keyed option in the review surface."""
    markdown = render_markdown(make_bank([make_question(letter=OptionLetter.C)]))

    assert "- **c)** Vinte anos." in markdown
    assert "- a) Dez anos." in markdown
    assert "### ENA26-Q01" in markdown


def test_render_markdown_marks_an_annulled_question_as_unanswerable() -> None:
    """Show that an annulled question has no correct option to study."""
    question = make_question(letter=None, excluded_reason=ExcludedReason.ANNULLED)
    markdown = render_markdown(make_bank([question]))

    assert build.EXCLUDED_REASON_NOTES[ExcludedReason.ANNULLED] in markdown
    assert build.EXCLUDED_REASON_LABELS[ExcludedReason.ANNULLED] in markdown
    assert "**Resposta:" not in markdown
    assert "**" not in markdown.split("- a) ")[1].split("\n")[0]


def test_render_markdown_records_the_source_defects() -> None:
    """Show a repeat and a source defect where a reviewer will see them."""
    question = make_question(
        "ENA26-Q14",
        duplicate_of="ENA26-Q13",
        known_defects=("identical-options",),
    )
    markdown = render_markdown(make_bank([question]))

    assert "ENA26-Q13" in markdown
    assert "identical-options" in markdown


def test_render_javascript_escapes_what_a_script_tag_cannot_hold() -> None:
    """Escape the characters JSON allows in a string but a script does not.

    An unescaped closing script tag inside a stem would end the enclosing
    element from inside a string literal, and the two Unicode line separators
    are not valid in a script at all. Built with `chr` because all three are
    either invisible or would break this file.
    """
    line_separator = chr(0x2028)
    paragraph_separator = chr(0x2029)
    bank_json = (
        '{"stem": "a <script> b '
        + line_separator
        + paragraph_separator
        + '"}'
        + chr(10)
    )
    rendered = render_javascript(bank_json)
    payload = rendered.split("=", 1)[1]

    assert "<" not in payload
    assert ">" not in payload
    assert line_separator not in payload
    assert paragraph_separator not in payload
    assert "u003c" in payload
    assert rendered.endswith(";" + chr(10))


def test_render_javascript_assigns_the_global_the_app_reads() -> None:
    """Assign the one global a plain script tag makes the app find."""
    rendered = render_javascript('{"version": 1}\n')
    assert f"window.{config.BANK_GLOBAL_NAME} = " in rendered


def test_write_text_uses_lf_on_every_platform(tmp_path: Path) -> None:
    """Write every generated artifact with LF, whatever the platform.

    Artifacts written with CRLF on Windows made a Linux rebuild produce a
    whole-file diff, which hides the change that actually mattered.
    """
    path = tmp_path / "nested" / "artifact.md"
    write_text(path, "primeira\nsegunda\n")

    assert path.read_bytes() == b"primeira\nsegunda\n"


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_main_writes_nothing_when_the_markdown_cannot_be_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render every artifact before writing any, so none can go out of sync.

    Args:
        monkeypatch: Fixture used to stand in for the toolchain and the layers.
    """
    written: list[Path] = []
    bank = make_bank([make_question(options={"a": "Um.", "b": "Dois.", "c": "Tres."})])

    monkeypatch.setattr(build, "build_bank", lambda generated_at: bank)
    monkeypatch.setattr(build, "write_text", lambda path, content: written.append(path))

    assert build.main(["--generated-at", "2026-08-26"]) == 1
    assert written == []


def test_main_writes_all_three_artifacts_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Write the canonical bank, the review surface and the app's script.

    Args:
        monkeypatch: Fixture used to stand in for the toolchain and the layers.
        tmp_path: Fixture providing the directory the artifacts go into.
    """
    bank = make_bank([make_question()])
    monkeypatch.setattr(build, "build_bank", lambda generated_at: bank)
    monkeypatch.setattr(config, "QUESTION_BANK_PATH", tmp_path / "bank.json")
    monkeypatch.setattr(config, "QUESTION_BANK_MD_PATH", tmp_path / "bank.md")
    monkeypatch.setattr(config, "QUESTION_BANK_JS_PATH", tmp_path / "bank.js")
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)

    assert build.main(["--generated-at", "2026-08-26"]) == 0

    for name in ("bank.json", "bank.md", "bank.js"):
        raw = (tmp_path / name).read_bytes()
        assert b"\r\n" not in raw, name
    assert (
        json.loads((tmp_path / "bank.json").read_text(encoding="utf-8"))["generatedAt"]
        == "2026-08-26"
    )


# --------------------------------------------------------------------------
# The two extraction artifacts have to describe one extraction
# --------------------------------------------------------------------------


def test_matching_toolchain_stamps_are_carried_into_the_bank() -> None:
    """Publish the agreed versions when both artifacts say the same thing."""
    stamp = {"pdftotext": "25.07.0"}
    assert reconcile_toolchain(stamp, dict(stamp)) == stamp


def test_disagreeing_toolchain_stamps_are_refused() -> None:
    """Refuse a pair of artifacts that were produced by different runs.

    `extract` writes both in one run with one binary. A disagreement means one
    of them is stale, and stamping either version into the bank would claim a
    provenance that is not true of half the input.
    """
    with pytest.raises(BuildError, match="disagree about the toolchain"):
        reconcile_toolchain({"pdftotext": "25.07.0"}, {"pdftotext": "24.02.0"})


def test_a_toolchain_stamp_with_an_extra_tool_is_refused() -> None:
    """Refuse stamps that differ in which tools they name, not only versions."""
    with pytest.raises(BuildError, match="disagree about the toolchain"):
        reconcile_toolchain(
            {"pdftotext": "25.07.0"}, {"pdftotext": "25.07.0", "qpdf": "11.9.0"}
        )


def test_a_current_extraction_passes_the_staleness_check() -> None:
    """Accept an extraction that covers exactly the registry."""
    check_extraction_is_current(committed_raw_questions(), committed_keys())


def test_an_extraction_missing_a_paper_is_reported_as_stale() -> None:
    """Name the artifact and the paper when a registered paper is absent.

    Adding a paper to `tools.config` without re-running `extract` would
    otherwise fail somewhere far from the cause.
    """
    questions = [
        question for question in committed_raw_questions() if question.exam != "ENA26"
    ]
    with pytest.raises(BuildError, match="holds no question of ENA26"):
        check_extraction_is_current(questions, committed_keys())


def test_an_extraction_of_an_unregistered_paper_is_reported_as_stale() -> None:
    """Name a paper the artifacts carry and the registry does not."""
    questions = list(committed_raw_questions())
    questions.append(
        RawQuestion(
            id="ENA99-Q01",
            exam="ENA99",
            number=1,
            stem="Sobre a patente de invencao, assinale a correta:",
            options=dict(OPTIONS),
            parse_status=ParseStatus.OK,
        )
    )
    with pytest.raises(BuildError, match="ENA99"):
        check_extraction_is_current(questions, committed_keys())


def test_a_key_that_does_not_cover_its_paper_is_reported_as_stale() -> None:
    """Name the paper whose key stops short of its last question."""
    keys = committed_keys()
    keys["ENA26"] = {number: keys["ENA26"][number] for number in range(1, 11)}
    with pytest.raises(BuildError, match=r"not questions 1\.\.20"):
        check_extraction_is_current(committed_raw_questions(), keys)


def test_a_missing_key_artifact_is_refused_rather_than_regenerated(
    tmp_path: Path,
) -> None:
    """Fail rather than quietly running pdftotext during a build.

    Regenerating the keys here is exactly what made the build unreproducible:
    the letters would come from whatever binary happened to be on PATH.

    Args:
        tmp_path: Fixture providing a directory that stays empty.
    """
    with pytest.raises(BuildError, match="python -m tools extract"):
        load_official_keys(tmp_path / "answer-keys.json")


# --------------------------------------------------------------------------
# The build date is carried forward, not taken from the clock
# --------------------------------------------------------------------------


def test_the_build_date_is_carried_from_the_committed_bank(tmp_path: Path) -> None:
    """Reuse the date the committed bank already carries.

    Defaulting to today meant a rebuild from unchanged inputs produced changed
    bytes the next morning: the same bank, stamped with a different day.

    Args:
        tmp_path: Fixture providing the directory to write the bank into.
    """
    path = tmp_path / "question-bank.json"
    path.write_text(json.dumps({"generatedAt": "2026-08-26"}), encoding="utf-8")

    assert carried_generated_at(path) == "2026-08-26"


def test_the_first_build_has_to_be_given_a_date(tmp_path: Path) -> None:
    """Say to pass the flag when there is no committed bank to carry from.

    Args:
        tmp_path: Fixture providing a directory that stays empty.
    """
    with pytest.raises(BuildError, match="--generated-at"):
        carried_generated_at(tmp_path / "question-bank.json")


def test_a_malformed_carried_date_is_refused(tmp_path: Path) -> None:
    """Refuse to carry forward something that is not a date.

    Args:
        tmp_path: Fixture providing the directory to write the bank into.
    """
    path = tmp_path / "question-bank.json"
    path.write_text(json.dumps({"generatedAt": "26/08/2026"}), encoding="utf-8")

    with pytest.raises(BuildError, match="not a YYYY-MM-DD date"):
        carried_generated_at(path)


def test_main_refuses_a_malformed_generated_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse a build date the contract could not publish.

    Args:
        monkeypatch: Fixture used to keep the build from touching the layers.
    """
    monkeypatch.setattr(build, "build_bank", lambda generated_at: make_bank([]))
    assert build.main(["--generated-at", "26/08/2026"]) == 1


# --------------------------------------------------------------------------
# The build is hermetic
# --------------------------------------------------------------------------

# Everything that would let `build` reach a PDF or a clock. Named once, so the
# import-footprint check and the source scan can never guard different lists.
FORBIDDEN_MODULES = ("tools.extract", "subprocess", "shutil", "datetime")

# Imported in a fresh process, because the rest of this suite has `tools.extract`
# in `sys.modules` long before any of these run.
HERMETIC_DRIVER = f"""
import sys

FORBIDDEN = {FORBIDDEN_MODULES!r}

before = [name for name in FORBIDDEN if name in sys.modules]

import tools.build

after = [name for name in FORBIDDEN if name in sys.modules]
sys.stdout.write(",".join(before) + "|" + ",".join(after))
"""


def import_footprint() -> tuple[list[str], list[str]]:
    """Import `tools.build` in a fresh process and see what came with it.

    Returns:
        The forbidden modules already loaded before the import, and the ones
        loaded after it.
    """
    result = subprocess.run(
        [sys.executable, "-c", HERMETIC_DRIVER],
        cwd=config.REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    before, _, after = result.stdout.strip().partition("|")
    return (
        [name for name in before.split(",") if name],
        [name for name in after.split(",") if name],
    )


def test_importing_build_pulls_in_no_subprocess_and_no_clock() -> None:
    """Keep `build` pure assembly over committed files.

    `build` used to shell out to pdftotext to parse the key PDFs and stamp the
    poppler version. That meant nobody could correct one explanation and
    rebuild without installing poppler — which defeats the reason
    `raw-questions.json` is committed — and it meant CI could never match the
    recorded version, since Ubuntu ships a different poppler.

    `datetime` is on the list for the same reason: reading the clock made a
    rebuild from unchanged inputs produce changed bytes the next morning.

    One assertion holds all four doors shut.
    """
    before, after = import_footprint()

    assert before == [], "the check is vacuous: these were loaded at startup"
    assert after == []


def imported_modules(path: Path) -> set[str]:
    """Collect every module one file imports, including inside a function body.

    Args:
        path: The module to scan.

    Returns:
        The module named by every `import` and `from ... import` statement
        anywhere in the file.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_the_build_stage_never_looks_the_binary_up_or_runs_it() -> None:
    """Keep the tool that reads PDFs out of the assembly stage.

    `build` names the binary in one string, to publish the version its inputs
    already recorded. What it must never do is locate it or run it, and it must
    not import the modules that could — including from inside a function, which
    the import-footprint check above cannot see, because that check only
    observes what importing the module pulls in.
    """
    path = Path(build.__file__)
    source = path.read_text(encoding="utf-8")

    assert "pdftotext_version" not in source
    assert "shutil.which" not in source
    assert sorted(imported_modules(path) & set(FORBIDDEN_MODULES)) == []
