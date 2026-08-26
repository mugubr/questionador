"""Tests for the command line and the console it prints to.

`python -m tools <stage>` is the whole public surface of the pipeline. The
console rule lives here too: Windows defaults stdout to cp1252, where a single
non-ASCII character raises `UnicodeEncodeError` and aborts the run *after* all
the work is done and *before* the output file is written.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import tools
from tools.__main__ import STAGES
from tools.__main__ import main as dispatch

TOOLS_DIR = Path(tools.__file__).resolve().parent


def printed_string_literals(path: Path) -> list[tuple[int, str]]:
    """Collect every string literal that reaches a `print` call in one module.

    Only literals are collected: what a formatted value expands to at runtime
    is data, and reconfiguring the stream is what protects that.

    Args:
        path: The module to scan.

    Returns:
        One (line number, literal) pair per string literal inside a print call.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "print":
            continue
        for literal in ast.walk(node):
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                found.append((literal.lineno, literal.value))
    return found


@pytest.mark.parametrize(
    "module",
    sorted(TOOLS_DIR.glob("*.py")),
    ids=lambda path: path.name,
)
def test_no_stage_prints_a_non_ascii_literal(module: Path) -> None:
    """Keep every progress message plain ASCII.

    Extraction once printed a check mark, and on a cp1252 console that single
    character aborted the run after all the work and before the output file was
    written. Reconfiguring the streams is the second lock on the same door;
    this is the first.

    Args:
        module: One module of the `tools` package.
    """
    offenders = [
        (line, text)
        for line, text in printed_string_literals(module)
        if not text.isascii()
    ]
    assert offenders == []


def test_at_least_one_stage_prints_something() -> None:
    """Guard the scan itself against silently finding nothing to check."""
    assert printed_string_literals(TOOLS_DIR / "build.py") != []


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------


def test_the_three_stages_are_the_documented_ones() -> None:
    """Offer exactly the three stages the pipeline is made of."""
    assert sorted(STAGES) == ["build", "extract", "validate"]


def test_no_stage_at_all_is_a_usage_error() -> None:
    """Exit non-zero when nobody said which stage to run."""
    assert dispatch([]) == 2


def test_help_is_not_an_error() -> None:
    """Exit zero when the help was what was asked for."""
    assert dispatch(["--help"]) == 0
    assert dispatch(["-h"]) == 0


def test_an_unknown_stage_is_a_usage_error() -> None:
    """Refuse a stage name the pipeline does not have."""
    assert dispatch(["publish"]) == 2


def test_a_stage_receives_its_own_arguments(tmp_path: Path) -> None:
    """Hand the stage everything after its name, so its own parser sees it.

    `python -m tools validate --help` has to reach the stage that knows what
    its options mean.

    Args:
        tmp_path: Fixture providing the directory to write a bank into.
    """
    path = tmp_path / "bank.json"
    path.write_text(json.dumps({"version": 2}), encoding="utf-8")

    assert dispatch(["validate", str(path), "--expected-total", "0"]) == 1
