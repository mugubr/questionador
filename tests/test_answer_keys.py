"""Tests for reading the published answer keys.

`parse_answer_key` is where the format lives, and it is pure: every case here
is an inline string shaped like the text `pdftotext -layout` produces from a
key PDF. The three things the format hides — ANULADA in place of a letter, the
ENA18 key's two-column table, and a footer date that looks exactly like a table
row — are each pinned by a test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import config
from tools.answer_keys import (
    AnswerKeyError,
    format_key,
    main,
    parse_answer_key,
    read_answer_keys,
    write_answer_keys,
)
from tools.config import ExamPaper
from tools.extract import load_answer_key
from tools.models import OptionLetter

# One column of rows, the way six of the seven keys are laid out.
SINGLE_COLUMN_KEY = """
                              PROFNIT
                   AVALIACAO NACIONAL 2023 - PI

                    QUESTAO      RESPOSTA CORRETA
                       1                A
                       2                C
                       3                B
                       4                D
"""

# The ENA18 key prints its forty rows in two columns, so `pdftotext -layout`
# puts questions 1 and 21 on the same line.
TWO_COLUMN_KEY = """
      QUESTAO   RESPOSTA          QUESTAO   RESPOSTA
         1         C                 3         A
         2         B                 4         D
"""


def test_parse_answer_key_reads_a_single_column_table() -> None:
    """Read the one-row-per-question table six of the seven keys print."""
    answers = parse_answer_key(SINGLE_COLUMN_KEY, 4, "key.pdf")
    assert answers == {
        1: OptionLetter.A,
        2: OptionLetter.C,
        3: OptionLetter.B,
        4: OptionLetter.D,
    }


def test_parse_answer_key_reads_the_ena18_two_column_table() -> None:
    """Read a key whose rows sit two to a line.

    The ENA18 key prints forty rows in two columns, which `pdftotext -layout`
    renders with questions 1 and 21 on the same line. A pattern anchored to the
    whole line reads only the left half and reports the right half missing.
    """
    answers = parse_answer_key(TWO_COLUMN_KEY, 4, "Gabarito-Final_ENA18.pdf")
    assert answers == {
        1: OptionLetter.C,
        2: OptionLetter.B,
        3: OptionLetter.A,
        4: OptionLetter.D,
    }


def test_parse_answer_key_reads_annulada_as_an_answer_of_its_own() -> None:
    """Read ANULADA as "this question has no answer", not as a missing row.

    The official key of AV2-POL prints ANULADA where the other rows print a
    letter. That is a published fact about the question, so the number maps to
    None rather than being absent.
    """
    text = """
        QUESTAO      RESPOSTA CORRETA
           1                A
           2             ANULADA
           3                B
    """
    answers = parse_answer_key(text, 3, "Gabarito-Final_AV2-POL.pdf")
    assert answers == {1: OptionLetter.A, 2: None, 3: OptionLetter.B}


def test_parse_answer_key_accepts_a_lowercase_letter() -> None:
    """Accept a key that prints its letters in lower case."""
    assert parse_answer_key("  1    c\n  2    a\n", 2, "key.pdf") == {
        1: OptionLetter.C,
        2: OptionLetter.A,
    }


def test_parse_answer_key_ignores_a_footer_date() -> None:
    """Refuse to read "18 de novembro de 2023" as question 18, answer d.

    The AV2 footer leads with the application date, and a pattern without
    whitespace boundaries turns that date into a table row that silently
    overrides — or duplicates — a real answer.
    """
    text = """
        QUESTAO      RESPOSTA CORRETA
           1                A
           2                C
18 de novembro de 2023   PI   Pagina 1 de 1
    """
    answers = parse_answer_key(text, 2, "Gabarito-Final_AV2-PI.pdf")
    assert answers == {1: OptionLetter.A, 2: OptionLetter.C}
    assert 18 not in answers


def test_parse_answer_key_ignores_a_footer_date_alone() -> None:
    """Read nothing at all out of a bare footer line."""
    with pytest.raises(AnswerKeyError, match="no answer for question"):
        parse_answer_key("18 de novembro de 2023   PI   Pagina 1 de 1\n", 2, "key.pdf")


def test_parse_answer_key_rejects_a_repeated_question() -> None:
    """Refuse a key that answers the same question twice."""
    with pytest.raises(AnswerKeyError, match="question 1 appears more than once"):
        parse_answer_key("  1    A\n  1    B\n  2    C\n", 2, "key.pdf")


def test_parse_answer_key_rejects_a_missing_answer() -> None:
    """Refuse a key that does not cover every question of the paper."""
    with pytest.raises(AnswerKeyError, match=r"no answer for question\(s\) \[3\]"):
        parse_answer_key("  1    A\n  2    B\n", 3, "key.pdf")


def test_parse_answer_key_rejects_a_question_the_paper_does_not_have() -> None:
    """Refuse a key that answers a question beyond the paper's last one."""
    with pytest.raises(AnswerKeyError, match=r"unexpected question\(s\) \[3\]"):
        parse_answer_key("  1    A\n  2    B\n  3    C\n", 2, "key.pdf")


def test_load_answer_key_refuses_a_paper_without_one() -> None:
    """Refuse to invent a key for a paper the registry says has none."""
    paper = ExamPaper(
        id="TEST",
        file="Prova_TEST.pdf",
        title="Caderno de teste",
        date="2020-01-01",
        expected_questions=4,
    )
    with pytest.raises(AnswerKeyError, match="has no published answer key"):
        load_answer_key(paper)


def test_load_answer_key_reports_a_missing_file() -> None:
    """Name the file rather than letting the subprocess fail obscurely."""
    paper = ExamPaper(
        id="TEST",
        file="Prova_TEST.pdf",
        title="Caderno de teste",
        date="2020-01-01",
        expected_questions=4,
        answer_key_file="Gabarito-Final_TEST.pdf",
    )
    with pytest.raises(AnswerKeyError, match="answer key not found"):
        load_answer_key(paper)


def test_format_key_marks_an_annulled_question() -> None:
    """Render an annulled question as a dash, not as a blank."""
    assert format_key({1: OptionLetter.C, 2: None, 3: OptionLetter.A}) == "1c 2- 3a"


# ---------------------------------------------------------------------------
# The committed artifact
# ---------------------------------------------------------------------------


def test_the_answer_key_artifact_round_trips(tmp_path: Path) -> None:
    """Read back exactly the table that was written, annulled rows included.

    ``data/answer-keys.json`` is what lets `build` run without poppler, so the
    letters it carries have to survive the trip through JSON's string keys.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
    """
    keys: dict[str, dict[int, OptionLetter | None]] = {
        "ENA26": {1: OptionLetter.C, 2: OptionLetter.A},
        "AV2-POL": {1: OptionLetter.B, 14: None},
    }
    destination = tmp_path / "nested" / "answer-keys.json"

    write_answer_keys(keys, {"pdftotext": "25.07.0"}, destination)
    restored, toolchain = read_answer_keys(destination)

    assert restored == keys
    assert toolchain == {"pdftotext": "25.07.0"}


def test_the_answer_key_artifact_is_written_with_lf(tmp_path: Path) -> None:
    """Write the artifact with LF, so a Linux rebuild is not a whole-file diff.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
    """
    destination = tmp_path / "answer-keys.json"
    write_answer_keys(
        {"ENA26": {1: OptionLetter.C}}, {"pdftotext": "25.07.0"}, destination
    )

    raw = destination.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")


def test_reading_a_missing_artifact_names_the_command_that_makes_it(
    tmp_path: Path,
) -> None:
    """Say how to produce the artifact rather than just failing to find it.

    Args:
        tmp_path: Fixture providing a directory that stays empty.
    """
    with pytest.raises(AnswerKeyError, match="python -m tools extract"):
        read_answer_keys(tmp_path / "answer-keys.json")


def test_an_artifact_without_a_toolchain_stamp_is_rejected(tmp_path: Path) -> None:
    """Refuse a key table that does not say which pdftotext produced it.

    The stamp is provenance: what it promises is that *this* build of pdftotext
    produced *these* letters.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
    """
    path = tmp_path / "answer-keys.json"
    path.write_text('{"keys": {"ENA26": {"1": "c"}}}', encoding="utf-8")

    with pytest.raises(AnswerKeyError, match="toolchain"):
        read_answer_keys(path)


def test_an_artifact_with_an_unknown_letter_is_rejected(tmp_path: Path) -> None:
    """Refuse a stored letter no option carries.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
    """
    path = tmp_path / "answer-keys.json"
    path.write_text(
        '{"toolchain": {"pdftotext": "25.07.0"}, "keys": {"ENA26": {"1": "e"}}}',
        encoding="utf-8",
    )

    with pytest.raises(AnswerKeyError, match="unknown letter"):
        read_answer_keys(path)


def test_an_artifact_with_an_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    """Refuse a field the artifact contract does not declare.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
    """
    path = tmp_path / "answer-keys.json"
    path.write_text(
        '{"toolchain": {"pdftotext": "25.07.0"}, "keys": {"ENA26": {"1": "c"}},'
        ' "gabaritos": {}}',
        encoding="utf-8",
    )

    with pytest.raises(AnswerKeyError, match="unknown top-level key"):
        read_answer_keys(path)


def test_an_artifact_that_is_not_json_is_rejected(tmp_path: Path) -> None:
    """Name the file when its contents are not JSON at all.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
    """
    path = tmp_path / "answer-keys.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(AnswerKeyError, match="invalid JSON"):
        read_answer_keys(path)


def test_main_reports_a_missing_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit non-zero and name the problem, instead of a raw traceback.

    Args:
        tmp_path: Fixture providing a directory that stays empty.
        monkeypatch: Fixture to point ANSWER_KEYS_PATH at the empty directory.
        capsys: Fixture to capture what main() printed.
    """
    monkeypatch.setattr(config, "ANSWER_KEYS_PATH", tmp_path / "answer-keys.json")

    assert main([]) == 1
    assert "ERROR" in capsys.readouterr().err


def test_main_prints_every_committed_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Print the toolchain and one line per exam, and exit zero.

    Args:
        tmp_path: Fixture providing the directory to write the artifact into.
        monkeypatch: Fixture to point ANSWER_KEYS_PATH at the written file.
        capsys: Fixture to capture what main() printed.
    """
    path = tmp_path / "answer-keys.json"
    write_answer_keys(
        {"ENA26": {1: OptionLetter.C, 2: None}}, {"pdftotext": "25.07.0"}, path
    )
    monkeypatch.setattr(config, "ANSWER_KEYS_PATH", path)

    assert main([]) == 0
    out = capsys.readouterr().out
    assert "pdftotext (poppler) 25.07.0" in out
    assert "ENA26 (2 answers)" in out
