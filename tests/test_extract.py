"""Tests for the extraction stage.

The parsing functions take text and return structures, so everything here runs
on inline strings and never opens a PDF. The two functions that do run a
subprocess are exercised through a fake `subprocess.run`, which is also how the
poppler-versus-Xpdf guard is tested without installing either build; the one
that writes the extraction anchor is given a temporary directory.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NoReturn

import pytest

from tools import configure_stdio, extract
from tools.config import ExamPaper
from tools.extract import (
    ExtractionError,
    ToolchainError,
    check_paper,
    count_option_openers,
    detect_issues,
    find_question_starts,
    normalize_stem,
    pdf_to_text,
    pdftotext_version,
    segment_questions,
    split_question_block,
    write_raw_questions,
)
from tools.models import ParsedBlock, ParseStatus

POPPLER_BANNER = "pdftotext version 25.07.0\nCopyright 2005-2025 The Poppler Developers"
XPDF_BANNER = "pdftotext version 4.00\nCopyright 1996-2017 Glyph & Cog, LLC"

TEST_PAPER = ExamPaper(
    id="TEST",
    file="Prova_TEST.pdf",
    title="Caderno de teste",
    date="2020-01-01",
    expected_questions=2,
)


class FakeCompletedProcess:
    """The subset of `subprocess.CompletedProcess` the extractor reads.

    Attributes:
        returncode: The exit status the fake process reports.
        stdout: What the fake process wrote to standard output.
        stderr: What the fake process wrote to standard error.
    """

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        """Record what the fake process should report.

        Args:
            returncode: The exit status.
            stdout: The standard output.
            stderr: The standard error.
        """
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_run_factory(
    calls: list[dict[str, Any]], result: FakeCompletedProcess
) -> Callable[..., FakeCompletedProcess]:
    """Build a `subprocess.run` replacement that records how it was called.

    Args:
        calls: Where every invocation is appended.
        result: What the fake process reports.

    Returns:
        A callable with the shape `subprocess.run` is used with here.
    """

    def fake_run(
        argv: Sequence[str],
        **kwargs: Any,  # noqa: ANN401 - subprocess.run takes arbitrary keywords.
    ) -> FakeCompletedProcess:
        """Record one invocation and return the canned result.

        Args:
            argv: The command line the caller asked for.
            **kwargs: Every keyword the caller passed.

        Returns:
            The canned result.
        """
        calls.append({"argv": list(argv), **kwargs})
        return result

    return fake_run


# --------------------------------------------------------------------------
# The toolchain guard
# --------------------------------------------------------------------------


def test_pdftotext_version_rejects_a_missing_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse to run when no pdftotext is on PATH at all.

    Args:
        monkeypatch: Fixture used to remove the binary from PATH.
    """
    monkeypatch.setattr("tools.extract.shutil.which", lambda name: None)
    with pytest.raises(ToolchainError, match="not found on PATH"):
        pdftotext_version()


def test_pdftotext_version_rejects_the_xpdf_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse the Xpdf binary Git for Windows ships under the name pdftotext.

    Xpdf writes Latin-1 and picks different dash characters, so it silently
    produces a different question bank from the same PDFs. That is exactly how
    the parser regressed once, without a single error message.

    Args:
        monkeypatch: Fixture used to fake the binary and its version banner.
    """
    monkeypatch.setattr("tools.extract.shutil.which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run_factory([], FakeCompletedProcess(stderr=XPDF_BANNER)),
    )
    with pytest.raises(ToolchainError, match="not the poppler build"):
        pdftotext_version()


def test_pdftotext_version_accepts_poppler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report the version when the binary really is poppler.

    Args:
        monkeypatch: Fixture used to fake the binary and its version banner.
    """
    monkeypatch.setattr("tools.extract.shutil.which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run_factory([], FakeCompletedProcess(stderr=POPPLER_BANNER)),
    )
    assert pdftotext_version() == "25.07.0"


def test_pdftotext_version_reads_a_banner_printed_on_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read the banner from either stream, since builds disagree about which.

    Args:
        monkeypatch: Fixture used to fake the binary and its version banner.
    """
    monkeypatch.setattr("tools.extract.shutil.which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run_factory([], FakeCompletedProcess(stdout=POPPLER_BANNER)),
    )
    assert pdftotext_version() == "25.07.0"


def test_pdftotext_version_rejects_an_unreadable_banner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse a poppler build whose banner carries no version number.

    Args:
        monkeypatch: Fixture used to fake the binary and its version banner.
    """
    monkeypatch.setattr("tools.extract.shutil.which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run_factory([], FakeCompletedProcess(stderr="poppler, no number here")),
    )
    with pytest.raises(ToolchainError, match="could not read the pdftotext version"):
        pdftotext_version()


def test_pdf_to_text_pins_the_layout_and_the_encoding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Invoke pdftotext with the flags and the decoding the pipeline requires.

    Without `encoding="utf-8"` the subprocess decodes with the console's code
    page, which on Windows silently produces a different bank.

    Args:
        monkeypatch: Fixture used to replace `subprocess.run`.
        tmp_path: Fixture providing a directory for the stand-in PDF.
    """
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    calls: list[dict[str, Any]] = []
    body = "\n".join(f"linha {index}" for index in range(20))
    monkeypatch.setattr(
        subprocess, "run", fake_run_factory(calls, FakeCompletedProcess(stdout=body))
    )

    assert pdf_to_text(pdf) == body
    assert calls[0]["argv"][:4] == ["pdftotext", "-layout", "-enc", "UTF-8"]
    assert calls[0]["encoding"] == "utf-8"


def test_pdf_to_text_rejects_a_pdf_without_a_text_layer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Refuse a PDF that is pure image, rather than emitting an empty paper.

    Args:
        monkeypatch: Fixture used to replace `subprocess.run`.
        tmp_path: Fixture providing a directory for the stand-in PDF.
    """
    pdf = tmp_path / "scanned.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        subprocess, "run", fake_run_factory([], FakeCompletedProcess(stdout="\n\n"))
    )
    with pytest.raises(ExtractionError, match="no text layer"):
        pdf_to_text(pdf)


def test_pdf_to_text_reports_a_missing_file() -> None:
    """Name the file rather than letting the subprocess fail obscurely."""
    with pytest.raises(ExtractionError, match="PDF not found"):
        pdf_to_text(Path("does-not-exist.pdf"))


def test_main_checks_the_toolchain_before_it_reads_a_single_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abort on the wrong binary before any extraction work happens.

    The guard is only worth having if it runs first. Segmenting seven papers
    with Xpdf and noticing afterwards produces a different bank from the same
    PDFs, and the run that produced it reported nothing wrong.

    Args:
        monkeypatch: Fixture used to fail the toolchain guard, and to notice an
            extraction that ran in spite of it.
    """

    def refuse_the_binary() -> str:
        """Fail the way the guard fails on an Xpdf build.

        Returns:
            Never; the guard raises instead.

        Raises:
            ToolchainError: Always.
        """
        raise ToolchainError("pdftotext on PATH is not the poppler build")

    def unreachable() -> NoReturn:
        """Fail the test if the extraction ran anyway.

        Raises:
            AssertionError: Always.
        """
        raise AssertionError("extract_all ran after the toolchain guard failed")

    monkeypatch.setattr(extract, "pdftotext_version", refuse_the_binary)
    monkeypatch.setattr(extract, "extract_all", unreachable)

    assert extract.main([]) == 1


# --------------------------------------------------------------------------
# Splitting one question block
# --------------------------------------------------------------------------


def test_split_question_block_separates_stem_from_options() -> None:
    """Split a plain question into its stem and its four options."""
    block = split_question_block(
        [
            "Sobre a patente de invencao, assinale a correta:",
            "a) Vigora por dez anos.",
            "b) Vigora por quinze anos.",
            "c) Vigora por vinte anos.",
            "d) Vigora por trinta anos.",
        ]
    )
    assert block.stem == "Sobre a patente de invencao, assinale a correta:"
    assert dict(block.options) == {
        "a": "Vigora por dez anos.",
        "b": "Vigora por quinze anos.",
        "c": "Vigora por vinte anos.",
        "d": "Vigora por trinta anos.",
    }
    assert block.trailing == ()


def test_split_question_block_joins_an_option_wrapped_across_lines() -> None:
    """Continue an option across the lines the PDF wraps it onto."""
    block = split_question_block(
        [
            "Assinale a correta:",
            "a) Primeira alternativa que segue",
            "   em uma segunda linha.",
            "b) Segunda.",
            "c) Terceira.",
            "d) Quarta.",
        ]
    )
    assert block.options["a"] == "Primeira alternativa que segue em uma segunda linha."


def test_split_question_block_opens_an_option_without_a_space() -> None:
    """Open an option printed as "c)As", which ENA18-Q37 really does."""
    block = split_question_block(
        [
            "Assinale a correta:",
            "a)Primeira.",
            "b)Segunda.",
            "c)As conferencias nacionais.",
            "d)Quarta.",
        ]
    )
    assert block.options["c"] == "As conferencias nacionais."


def test_split_question_block_keeps_text_after_the_last_option_out_of_d() -> None:
    """Keep whatever follows the fourth option out of option `d`.

    Everything after the fourth option used to be appended to `d` in silence,
    which is how ``"...BOA PROVA! Etapa 1 ... Pg. 15/15"`` ended up inside an
    option of ENA18-Q40 with no complaint from anything.
    """
    block = split_question_block(
        [
            "Assinale a correta:",
            "a) Primeira.",
            "b) Segunda.",
            "c) Terceira.",
            "d) Quarta.",
            "",
            "BOA PROVA!",
            "Etapa 1 - Prova Nacional          Pg. 15/15",
        ]
    )
    assert block.options["d"] == "Quarta."
    assert block.trailing == (
        "BOA PROVA!",
        "Etapa 1 - Prova Nacional          Pg. 15/15",
    )


def test_split_question_block_does_not_restart_on_an_out_of_sequence_letter() -> None:
    """Refuse to open an option whose letter is not the next one in sequence.

    A stray "a)" printed inside an option must not restart collection and
    swallow the rest of the question.
    """
    block = split_question_block(
        [
            "Assinale a correta:",
            "a) Primeira.",
            "b) Segunda, conforme",
            "a) o texto citado.",
            "c) Terceira.",
            "d) Quarta.",
        ]
    )
    assert block.options["b"] == "Segunda, conforme a) o texto citado."
    assert set(block.options) == {"a", "b", "c", "d"}


def test_split_question_block_reports_a_short_option_set() -> None:
    """Report the options actually found when the paper printed fewer."""
    block = split_question_block(["Assinale a correta:", "a) Primeira.", "b) Segunda."])
    assert set(block.options) == {"a", "b"}


# --------------------------------------------------------------------------
# Normalising and counting
# --------------------------------------------------------------------------


def test_normalize_stem_drops_indentation_and_keeps_line_breaks() -> None:
    """Drop the column indentation but keep the breaks between assertions."""
    stem = "    Considere:\n\n\n      I- Primeira\n      II- Segunda\n"
    assert normalize_stem(stem) == "Considere:\n\nI- Primeira\nII- Segunda"


def test_count_option_openers_counts_every_letter() -> None:
    """Count how often each letter opens a line, including the absent ones."""
    counts = count_option_openers(["a) Um.", "b) Dois.", "a) Tres."])
    assert counts == {"a": 2, "b": 1, "c": 0, "d": 0}


def test_find_question_starts_reads_both_markers() -> None:
    """Locate the two question markers that coexist in the collection."""
    lines = ["QUESTÃO 1", "texto", "Questão 2.", "texto"]
    assert find_question_starts(lines) == [(0, 1), (2, 2)]


def test_find_question_starts_ignores_a_marker_inside_a_sentence() -> None:
    """Ignore a marker that is not alone on its line."""
    assert find_question_starts(["A QUESTÃO 1 trata de patentes."]) == []


# --------------------------------------------------------------------------
# Detecting what makes a question unusable
# --------------------------------------------------------------------------


def test_detect_issues_finds_a_footer_inside_an_option() -> None:
    """Check every option for residue, not only the stem.

    Thirteen questions shipped with a page footer inside their *options* while
    reporting ``parseStatus: "ok"``, because noise, column-layout and residue
    checks all ran on the stem alone.
    """
    block = ParsedBlock(
        stem="Sobre as conferencias nacionais de CT&I, assinale a correta:",
        options={
            "a": "Primeira.",
            "b": "Segunda.",
            "c": "Terceira.",
            "d": "Quarta. Etapa 1 - Prova Nacional Pg. 15/15",
        },
    )
    issues = detect_issues(block, block.stem, [])
    assert any("option d" in issue and "residue" in issue for issue in issues)


def test_detect_issues_finds_column_wording_inside_an_option() -> None:
    """Check every option for column-matching wording, not only the stem."""
    block = ParsedBlock(
        stem="Sobre a marca, assinale a alternativa correta a seguir:",
        options={
            "a": "Correlacione a coluna 1 com a coluna 2.",
            "b": "Segunda.",
            "c": "Terceira.",
            "d": "Quarta.",
        },
    )
    issues = detect_issues(block, block.stem, [])
    assert any("option a" in issue and "column-matching" in issue for issue in issues)


def test_detect_issues_finds_side_by_side_columns_in_the_stem() -> None:
    """Flag a matching table that pdftotext rendered as two columns."""
    stem = "Correlacione:\n1- Marca Nominativa       ( ) Palavra"
    block = ParsedBlock(
        stem=stem,
        options={"a": "1.", "b": "2.", "c": "3.", "d": "4."},
    )
    issues = detect_issues(block, stem, [])
    assert any("two columns rendered side by side" in issue for issue in issues)


def test_detect_issues_reports_a_repeated_option_set() -> None:
    """Flag a block that holds two a)-d) sets.

    The first set belongs to the stem, as in a matching question. Without this
    the parser takes the wrong set and glues the real one inside option `d`.
    """
    lines = [
        "Associe as colunas:",
        "a) Um.",
        "b) Dois.",
        "c) Tres.",
        "d) Quatro.",
        "Assinale:",
        "a) 1234.",
        "b) 4321.",
        "c) 2143.",
        "d) 3412.",
    ]
    block = split_question_block(lines)
    issues = detect_issues(block, normalize_stem(block.stem), lines)
    assert any("duplicated a)-d) set" in issue for issue in issues)


def test_detect_issues_reports_trailing_text() -> None:
    """Flag whatever the paper printed after the fourth option."""
    block = ParsedBlock(
        stem="Sobre a patente de invencao, assinale a correta:",
        options={"a": "1.", "b": "2.", "c": "3.", "d": "4."},
        trailing=("BOA PROVA!",),
    )
    issues = detect_issues(block, block.stem, [])
    assert any("text after the last option" in issue for issue in issues)


def test_detect_issues_reports_a_missing_option() -> None:
    """Flag a question that did not produce all four options."""
    block = ParsedBlock(
        stem="Sobre a patente de invencao, assinale a correta:",
        options={"a": "1.", "b": "2.", "c": "3."},
    )
    assert any(
        "3 options instead of 4" in issue
        for issue in detect_issues(block, block.stem, [])
    )


def test_detect_issues_reports_a_stem_that_is_too_short() -> None:
    """Flag a stem so short it can only be a parsing failure."""
    block = ParsedBlock(
        stem="Ok",
        options={"a": "1.", "b": "2.", "c": "3.", "d": "4."},
    )
    assert any("shorter than" in issue for issue in detect_issues(block, "Ok", []))


def test_detect_issues_is_silent_on_a_clean_question() -> None:
    """Report nothing for a question that parsed cleanly."""
    block = ParsedBlock(
        stem="Sobre a patente de invencao, assinale a alternativa correta:",
        options={"a": "Dez.", "b": "Quinze.", "c": "Vinte.", "d": "Trinta."},
    )
    assert detect_issues(block, block.stem, []) == ()


# --------------------------------------------------------------------------
# Segmenting a whole paper
# --------------------------------------------------------------------------


PAPER_TEXT = """QUESTÃO 1
Sobre a patente de invencao, assinale a alternativa correta:
a) Vigora por dez anos.
b) Vigora por quinze anos.
c) Vigora por vinte anos.
d) Vigora por trinta anos.

QUESTÃO 2
Sobre o desenho industrial, assinale a alternativa correta:
a) Primeira.
b) Segunda.
c) Terceira.
d) Quarta.
"""


def test_segment_questions_numbers_and_identifies_every_question() -> None:
    """Cut a paper into questions and give each one its stable id."""
    questions = segment_questions(PAPER_TEXT, TEST_PAPER)
    assert [question.id for question in questions] == ["TEST-Q01", "TEST-Q02"]
    assert [question.number for question in questions] == [1, 2]
    assert all(question.exam == "TEST" for question in questions)
    assert all(question.parse_status is ParseStatus.OK for question in questions)


def test_segment_questions_marks_a_broken_question_for_review() -> None:
    """Mark a question the parser could not resolve, rather than guessing."""
    text = PAPER_TEXT + "\nQUESTÃO 3\nCurto\na) Um.\n"
    paper = ExamPaper(
        id="TEST",
        file="Prova_TEST.pdf",
        title="Caderno de teste",
        date="2020-01-01",
        expected_questions=3,
    )
    questions = segment_questions(text, paper)
    assert questions[2].parse_status is ParseStatus.REVIEW
    assert questions[2].issues != ()


def test_check_paper_rejects_a_wrong_question_count() -> None:
    """Fail when segmentation disagrees with the registry's count."""
    questions = segment_questions(PAPER_TEXT, TEST_PAPER)
    paper = ExamPaper(
        id="TEST",
        file="Prova_TEST.pdf",
        title="Caderno de teste",
        date="2020-01-01",
        expected_questions=3,
    )
    with pytest.raises(ExtractionError, match="expected 3 questions"):
        check_paper(questions, paper)


def test_check_paper_rejects_non_contiguous_numbering() -> None:
    """Fail when the numbers found are not 1..N."""
    text = PAPER_TEXT.replace("QUESTÃO 2", "QUESTÃO 5")
    questions = segment_questions(text, TEST_PAPER)
    with pytest.raises(ExtractionError, match="not contiguous"):
        check_paper(questions, TEST_PAPER)


def test_check_paper_accepts_the_expected_paper() -> None:
    """Accept a paper that produced exactly the questions the registry says."""
    check_paper(segment_questions(PAPER_TEXT, TEST_PAPER), TEST_PAPER)


# --------------------------------------------------------------------------
# Writing the extraction anchor
# --------------------------------------------------------------------------


def test_write_raw_questions_uses_lf_on_every_platform(tmp_path: Path) -> None:
    """Write the anchor with LF so a Linux rebuild is not a whole-file diff.

    Args:
        tmp_path: Fixture providing the directory to write into.
    """
    destination = tmp_path / "nested" / "raw-questions.json"
    write_raw_questions(
        segment_questions(PAPER_TEXT, TEST_PAPER),
        {"pdftotext": "25.07.0"},
        destination,
    )

    raw = destination.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")

    payload = json.loads(raw)
    assert payload["toolchain"] == {"pdftotext": "25.07.0"}
    assert [entry["id"] for entry in payload["questions"]] == ["TEST-Q01", "TEST-Q02"]


# --------------------------------------------------------------------------
# Console encoding
# --------------------------------------------------------------------------


def test_a_cp1252_console_really_does_reject_a_check_mark() -> None:
    """Confirm the failure mode the entry-point guard exists to prevent.

    A single non-ASCII character aborted the run on a Windows console *after*
    all the work was done and *before* the output file was written.
    """
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    with pytest.raises(UnicodeEncodeError):
        stream.write("✓ pronto")
        stream.flush()


def test_configure_stdio_makes_a_cp1252_console_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconfigure both streams to UTF-8 before anything is printed.

    Args:
        monkeypatch: Fixture used to stand in for the console streams.
    """
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    configure_stdio()

    assert stream.encoding == "utf-8"
    print("✓ pronto")
    stream.flush()


def test_configure_stdio_tolerates_a_replaced_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do nothing when a harness replaced the stream with something else.

    Args:
        monkeypatch: Fixture used to replace the console streams.
    """
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    configure_stdio()
