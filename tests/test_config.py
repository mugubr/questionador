"""Tests for the exam-paper registry and the constants derived from it.

`tools/config.py` is the one place a number two stages would otherwise
hard-code twice may live, so the invariants that make it a single source of
truth are worth asserting: ids that agree with themselves, a total that agrees
with its parts, and no entry keyed to a question that does not exist.
"""

from __future__ import annotations

import hashlib
import re

from tools import config
from tools.config import EXAM_PAPERS, EXAM_PAPERS_BY_ID
from tools.models import ExcludedReason

QUESTION_ID_PATTERN = re.compile(r"^(?P<exam>[A-Z0-9-]+)-Q(?P<number>\d{2})$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def every_registered_question_id() -> set[str]:
    """List every question id the registry could legally name.

    Returns:
        One id per question of every paper, as `<exam>-Q<NN>`.
    """
    return {
        f"{paper.id}-Q{number:02d}"
        for paper in EXAM_PAPERS
        for number in range(1, paper.expected_questions + 1)
    }


def test_exam_ids_are_unique() -> None:
    """Keep one entry per paper, so the index cannot lose one silently."""
    ids = [paper.id for paper in EXAM_PAPERS]
    assert len(ids) == len(set(ids))
    assert set(EXAM_PAPERS_BY_ID) == set(ids)


def test_exam_files_are_unique() -> None:
    """Point each registry entry at its own PDF."""
    files = [paper.file for paper in EXAM_PAPERS]
    assert len(files) == len(set(files))


def test_every_paper_declares_an_iso_date() -> None:
    """Keep the application dates in the format the bank contract requires."""
    assert all(DATE_PATTERN.match(paper.date) for paper in EXAM_PAPERS)


def test_expected_total_agrees_with_its_parts() -> None:
    """Derive the total from the papers rather than restating it.

    The expected question total once drifted between `extract` and `validate`
    because it was written down twice.
    """
    total = sum(paper.expected_questions for paper in EXAM_PAPERS)
    assert total == config.EXPECTED_QUESTION_TOTAL


def test_every_paper_has_a_published_answer_key() -> None:
    """Record that all seven keys were recovered, so no answer is derived.

    `Answer` still models a derived answer and the contract still enforces its
    rules, because a future paper may arrive without a key. This asserts the
    state of the data as it stands, not a permanent property.
    """
    assert all(paper.has_official_answer_key for paper in EXAM_PAPERS)
    assert all(paper.answer_key_path is not None for paper in EXAM_PAPERS)


def test_paper_paths_resolve_inside_the_repository() -> None:
    """Resolve every PDF under `exams/`, never anywhere else."""
    for paper in EXAM_PAPERS:
        assert paper.pdf_path.parent == config.EXAMS_DIR
        key_path = paper.answer_key_path
        assert key_path is not None
        assert key_path.parent == config.EXAMS_DIR


def test_every_source_pdf_exists() -> None:
    """Keep the registry pointing at PDFs that are really in the repository."""
    for paper in EXAM_PAPERS:
        assert paper.pdf_path.is_file(), paper.file
        key_path = paper.answer_key_path
        assert key_path is not None
        assert key_path.is_file(), paper.answer_key_file


def test_known_duplicates_name_real_questions() -> None:
    """Key every known repeat, and its target, to a question that exists.

    An entry keyed to a question that does not exist is a hand-written fix that
    silently stops being applied.
    """
    registered = every_registered_question_id()
    for question_id, target in config.KNOWN_DUPLICATES.items():
        assert question_id in registered
        assert target in registered


def test_a_duplicate_never_points_at_another_duplicate() -> None:
    """Point every repeat at the original, so the chain is one link long."""
    for target in config.KNOWN_DUPLICATES.values():
        assert target not in config.KNOWN_DUPLICATES


def test_a_duplicate_points_inside_its_own_paper() -> None:
    """Keep a repeat and its original on the same printed paper."""
    for question_id, target in config.KNOWN_DUPLICATES.items():
        source_match = QUESTION_ID_PATTERN.match(question_id)
        target_match = QUESTION_ID_PATTERN.match(target)
        assert source_match is not None
        assert target_match is not None
        assert source_match.group("exam") == target_match.group("exam")


def test_known_defects_name_real_questions() -> None:
    """Key every recorded source defect to a question that exists."""
    registered = every_registered_question_id()
    for question_id, defects in config.KNOWN_DEFECTS.items():
        assert question_id in registered
        assert defects != ()


def test_excluded_questions_name_real_questions() -> None:
    """Key every exclusion to a question that exists."""
    registered = every_registered_question_id()
    assert set(config.EXCLUDED_QUESTIONS) <= registered


def test_the_three_excluded_questions_are_the_documented_ones() -> None:
    """Pin the three questions that must never be drawn.

    AV2-POL-Q14 is annulled by its official key. AV2-PI-Q14 and AV2-PI-Q16 are
    reprints of 13 and 15 in a defective booklet, and the key gives the two
    pairs different letters, so the text the bank holds is not what those key
    rows answer.
    """
    assert dict(config.EXCLUDED_QUESTIONS) == {
        "AV2-PI-Q14": ExcludedReason.SOURCE_BOOKLET_DEFECT,
        "AV2-PI-Q16": ExcludedReason.SOURCE_BOOKLET_DEFECT,
        "AV2-POL-Q14": ExcludedReason.ANNULLED,
    }


def test_every_booklet_defect_exclusion_is_also_a_known_duplicate() -> None:
    """Tie a booklet-defect exclusion to the question it reprints.

    `resolve_key_number` reads the key at the repeated question's row, and it
    can only do that when the repeat is registered as a duplicate.
    """
    for question_id, reason in config.EXCLUDED_QUESTIONS.items():
        if reason is ExcludedReason.SOURCE_BOOKLET_DEFECT:
            assert question_id in config.KNOWN_DUPLICATES


def test_every_paper_is_pinned_in_the_md5_table() -> None:
    """Keep the checkable-provenance table complete as papers are added."""
    assert {paper.file for paper in EXAM_PAPERS} == set(config.EXAM_BOOKLET_MD5)


def test_every_booklet_matches_its_pinned_md5() -> None:
    """Catch a booklet in `exams/` silently drifting from what AGENTS.md pins.

    AGENTS.md section 5 claims every booklet matches the one published at
    profnit.org.br byte for byte. `EXAM_BOOKLET_MD5` is what makes that
    re-checkable without downloading the originals again; this test is what
    makes it re-checked, on every run, against the file actually committed.
    """
    for paper in EXAM_PAPERS:
        digest = hashlib.md5(paper.pdf_path.read_bytes()).hexdigest()
        assert digest == config.EXAM_BOOKLET_MD5[paper.file]
