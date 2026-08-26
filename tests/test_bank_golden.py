"""The golden tests: the committed artifacts, exactly as they are published.

One of these validates `data/question-bank.json` against the whole contract.
It is a single assertion and it catches an entire class of mistakes, which is
why the suite exists at all. The rest hold the three artifacts to the promises
the pipeline makes about them: LF everywhere, the app's script wrapping the
canonical bank and nothing else, and the same bytes out of two runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tools import config
from tools.answer_keys import read_answer_keys
from tools.build import render_javascript, resolve_key_number
from tools.models import ExcludedReason
from tools.validate import validate

# Every artifact the pipeline generates and the repository commits.
GENERATED_ARTIFACTS = (
    config.RAW_QUESTIONS_PATH,
    config.ANSWER_KEYS_PATH,
    config.QUESTION_BANK_PATH,
    config.QUESTION_BANK_MD_PATH,
    config.QUESTION_BANK_JS_PATH,
)

# Two builds of the same inputs, in two processes whose string hashing differs.
# An unsorted iteration over a set or a glob only shows up across processes,
# because within one process the order is stable however wrong it is.
DETERMINISM_DRIVER = """
import hashlib
import json
import sys

from tools import build, config
from tools.build import render_javascript, render_json, render_markdown

published = json.loads(config.QUESTION_BANK_PATH.read_text(encoding="utf-8"))
bank = build.build_bank(published["generatedAt"])
canonical = render_json(bank)
payload = canonical + render_markdown(bank) + render_javascript(canonical)
sys.stdout.write(hashlib.sha256(payload.encode("utf-8")).hexdigest())
"""


def published_bank() -> dict[str, Any]:
    """Read the committed question bank.

    Returns:
        The decoded bank, exactly as it is published.
    """
    return cast(
        "dict[str, Any]",
        json.loads(config.QUESTION_BANK_PATH.read_text(encoding="utf-8")),
    )


def build_digest(hash_seed: str, search_path: str | None = None) -> str:
    """Rebuild the artifacts in a fresh process and digest them.

    Args:
        hash_seed: The value of `PYTHONHASHSEED` for that process.
        search_path: What to put in `PATH`, or None to inherit it.

    Returns:
        The hex digest of the three rendered artifacts concatenated.
    """
    environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
    if search_path is not None:
        environment["PATH"] = search_path
    result = subprocess.run(
        [sys.executable, "-c", DETERMINISM_DRIVER],
        cwd=config.REPO_ROOT,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


# --------------------------------------------------------------------------
# The golden assertion
# --------------------------------------------------------------------------


def test_the_committed_bank_satisfies_the_contract() -> None:
    """Validate the published bank against every rule of the contract.

    One assertion, the whole contract: field shapes, provenance rules, the
    numbering of each paper, the taxonomy, the duplicates, and the absence of
    page furniture in any stem or option.
    """
    errors = list(validate(published_bank()))
    assert errors == []


# --------------------------------------------------------------------------
# Line endings
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", GENERATED_ARTIFACTS, ids=lambda path: path.name)
def test_every_generated_artifact_is_stored_with_lf(path: Path) -> None:
    """Keep every artifact LF, so a Linux rebuild is not a whole-file diff.

    Artifacts written with CRLF on Windows made the rebuild on CI report the
    entire file as changed, which hides the change that actually mattered.

    Args:
        path: One committed artifact.
    """
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")


# --------------------------------------------------------------------------
# The artifacts agree with each other
# --------------------------------------------------------------------------


def test_the_app_script_wraps_exactly_the_canonical_bank() -> None:
    """Serve the app the same bytes the canonical bank holds.

    `docs/data/question-bank.js` is a mechanical wrapper of
    `data/question-bank.json`. If the two drift, the site publishes a bank
    nothing validated.
    """
    canonical = config.QUESTION_BANK_PATH.read_text(encoding="utf-8")
    published = config.QUESTION_BANK_JS_PATH.read_text(encoding="utf-8")
    assert published == render_javascript(canonical)


def test_the_app_script_carries_no_raw_angle_bracket() -> None:
    """Escape every angle bracket, so no stem can close the script element."""
    published = config.QUESTION_BANK_JS_PATH.read_text(encoding="utf-8")
    assert "<" not in published
    assert ">" not in published


def test_the_review_surface_covers_every_question() -> None:
    """Give every published question a heading in the review surface."""
    markdown = config.QUESTION_BANK_MD_PATH.read_text(encoding="utf-8")
    missing = [
        question["id"]
        for question in published_bank()["questions"]
        if f"### {question['id']} " not in markdown
    ]
    assert missing == []


def test_the_extraction_anchor_holds_the_same_questions() -> None:
    """Keep the committed anchor and the published bank in step.

    `data/raw-questions.json` is what the rest of the chain is rebuilt from, so
    a bank holding a question the anchor does not is a bank nobody can rebuild.
    """
    anchor = json.loads(config.RAW_QUESTIONS_PATH.read_text(encoding="utf-8"))
    anchor_ids = [entry["id"] for entry in anchor["questions"]]
    bank_ids = [question["id"] for question in published_bank()["questions"]]

    assert anchor_ids == bank_ids
    assert len(anchor_ids) == config.EXPECTED_QUESTION_TOTAL


# --------------------------------------------------------------------------
# The layers name questions that exist
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "layer",
    ["overrides", "topics", "answers"],
)
def test_no_data_layer_carries_an_orphan_key(layer: str) -> None:
    """Key every hand-written layer to a question the bank holds.

    A key that matches nothing was silently ignored, which is how a
    hand-written fix stops being applied without a word.

    Args:
        layer: Which hand-written layer to check.
    """
    known = {question["id"] for question in published_bank()["questions"]}

    if layer == "overrides":
        payload = json.loads(config.OVERRIDES_PATH.read_text(encoding="utf-8"))
        keys = {key for key in payload if not key.startswith("_")}
    elif layer == "topics":
        payload = json.loads(config.TOPICS_PATH.read_text(encoding="utf-8"))
        keys = set(payload["assignments"])
    else:
        keys = set()
        for path in sorted(config.ANSWERS_DIR.glob("*.json")):
            keys |= set(json.loads(path.read_text(encoding="utf-8")))

    assert sorted(keys - known) == []


# --------------------------------------------------------------------------
# The known defects of the source material, as published
# --------------------------------------------------------------------------


def test_the_three_excluded_questions_are_published_as_excluded() -> None:
    """Publish exactly the three questions that must never be drawn."""
    excluded = {
        question["id"]: question["excludedReason"]
        for question in published_bank()["questions"]
        if "excludedReason" in question
    }
    assert excluded == {
        question_id: str(reason)
        for question_id, reason in config.EXCLUDED_QUESTIONS.items()
    }


def test_the_annulled_question_carries_no_letter() -> None:
    """Publish the annulled question without a letter at all.

    The official key of AV2-POL prints ANULADA where the other rows print a
    letter, so there is no correct option to record and nothing downstream may
    assume the field exists.
    """
    questions = {question["id"]: question for question in published_bank()["questions"]}
    annulled = questions["AV2-POL-Q14"]

    assert "letter" not in annulled["answer"]
    assert annulled["excludedReason"] == "annulled"


def test_every_other_question_carries_a_letter() -> None:
    """Publish a correct option for every question that can be graded."""
    without_letter = [
        question["id"]
        for question in published_bank()["questions"]
        if "letter" not in question["answer"] and "excludedReason" not in question
    ]
    assert without_letter == []


def test_the_question_with_identical_options_records_the_defect() -> None:
    """Record that AV2-MET-Q14 prints the same string as options a and d.

    The paper really offers three answers there. Reproduced faithfully and
    recorded, so the app can grade either twin as correct instead of marking a
    student wrong for choosing a string identical to the answer key.
    """
    questions = {question["id"]: question for question in published_bank()["questions"]}
    defective = questions["AV2-MET-Q14"]

    assert defective["knownDefects"] == ["identical-options"]
    assert defective["options"]["a"] == defective["options"]["d"]


def test_every_identity_agrees_with_itself() -> None:
    """Keep `id`, `exam` and `number` telling one story across the bank.

    They used to be three independent fields nobody cross-checked.
    """
    mismatched = [
        question["id"]
        for question in published_bank()["questions"]
        if question["id"] != f"{question['exam']}-Q{question['number']:02d}"
    ]
    assert mismatched == []


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_building_twice_produces_identical_artifacts() -> None:
    """Produce the same bytes from the same inputs, in two fresh processes.

    The two processes hash their strings differently, so an unsorted iteration
    over a set or a glob shows up here and nowhere else: within one process the
    order is stable however wrong it is.
    """
    assert build_digest("0") == build_digest("1")


# --------------------------------------------------------------------------
# The extraction artifacts and the bank agree about their provenance
# --------------------------------------------------------------------------


def test_both_extraction_artifacts_name_the_same_toolchain() -> None:
    """Keep the two artifacts of one extraction describing one extraction.

    `extract` writes them in a single run with a single binary, so a
    disagreement means one of them is stale and the pair no longer describes
    the same pass over the PDFs.
    """
    anchor = json.loads(config.RAW_QUESTIONS_PATH.read_text(encoding="utf-8"))
    keys = json.loads(config.ANSWER_KEYS_PATH.read_text(encoding="utf-8"))

    assert anchor["toolchain"] == keys["toolchain"]
    assert anchor["toolchain"]["pdftotext"]


def test_the_bank_carries_the_toolchain_of_its_inputs() -> None:
    """Publish the pdftotext that produced the text, not the one on PATH.

    Two builds of pdftotext produce two different banks from the same PDFs, so
    the stamp has to come from the artifacts that were actually parsed.
    """
    anchor = json.loads(config.RAW_QUESTIONS_PATH.read_text(encoding="utf-8"))
    assert published_bank()["toolchain"] == anchor["toolchain"]


def test_the_committed_keys_cover_every_paper_exactly() -> None:
    """Hold one key row per question of every paper the registry declares."""
    keys, _ = read_answer_keys(config.ANSWER_KEYS_PATH)

    assert set(keys) == {paper.id for paper in config.EXAM_PAPERS}
    for paper in config.EXAM_PAPERS:
        assert sorted(keys[paper.id]) == list(range(1, paper.expected_questions + 1))


def test_the_only_annulled_row_is_the_one_the_bank_publishes() -> None:
    """Leave exactly one key row without a letter, and make it AV2-POL 14.

    The official key of AV2-POL prints ANULADA there. Any other letter-less row
    would mean a question the bank cannot answer and does not know it.
    """
    keys, _ = read_answer_keys(config.ANSWER_KEYS_PATH)
    annulled = sorted(
        (exam_id, number)
        for exam_id, rows in keys.items()
        for number, letter in rows.items()
        if letter is None
    )

    assert annulled == [("AV2-POL", 14)]


def test_every_published_letter_comes_from_the_committed_key() -> None:
    """Take every published letter from the key row that answers the question.

    The letter is read from the key and never written by hand, so the two can
    never disagree. A booklet reprint is the one exception, and it reads the
    row of the question it repeats.
    """
    keys, _ = read_answer_keys(config.ANSWER_KEYS_PATH)
    mismatched = []
    for question in published_bank()["questions"]:
        reason = question.get("excludedReason")
        number = resolve_key_number(
            question["number"],
            ExcludedReason(reason) if reason else None,
            question.get("duplicateOf"),
        )
        expected = keys[question["exam"]][number]
        published = question["answer"].get("letter")
        if (expected if expected is None else str(expected)) != published:
            mismatched.append(question["id"])

    assert mismatched == []


def test_the_build_needs_nothing_on_path() -> None:
    """Assemble the bank with an empty `PATH`, byte for byte the same.

    `build` used to shell out to pdftotext, which meant correcting one
    explanation required installing poppler, and CI could never match the
    recorded version because Ubuntu ships a different one. The keys and the
    toolchain stamp now come from committed artifacts, and this is what says so
    in a way that cannot quietly stop being true.
    """
    assert build_digest("0", search_path="") == build_digest("0")
