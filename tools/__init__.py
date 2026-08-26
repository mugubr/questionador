"""The PROFNIT question-bank pipeline.

Three stages, each one narrow and auditable:

``extract``
    ``exams/*.pdf`` into ``data/raw-questions.json``.
``build``
    the anchor plus the hand-written layers into ``data/question-bank.json``,
    ``data/question-bank.md`` and ``docs/data/question-bank.js``.
``validate``
    the published bank against the contract in ``data/schema.json``.

Run them with ``python -m tools <stage>``.
"""

from __future__ import annotations

import io
import sys

__all__ = ["configure_stdio"]


def configure_stdio() -> None:
    """Force stdout and stderr to UTF-8 before anything is printed.

    Windows defaults the console to cp1252, where a single non-ASCII character
    raises ``UnicodeEncodeError`` and aborts the run *after* all the work is
    done and *before* the output file is written. Progress output is kept ASCII
    anyway; this is the second lock on the same door, and it also keeps a
    Portuguese error message readable when one has to be printed.
    """
    for stream in (sys.stdout, sys.stderr):
        # A test harness may have replaced the stream with something that has
        # no encoding to reconfigure, and that is not an error.
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
