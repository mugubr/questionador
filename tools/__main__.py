"""Command-line entry point: ``python -m tools <extract|build|validate>``.

Each stage owns its own `argparse` parser, so ``python -m tools build --help``
reaches the stage that knows what its options mean.

Usage:
    python -m tools extract
    python -m tools build
    python -m tools validate
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence

from tools import build, configure_stdio, extract, validate

STAGES: dict[str, Callable[[Sequence[str] | None], int]] = {
    "extract": extract.main,
    "build": build.main,
    "validate": validate.main,
}

USAGE = f"usage: python -m tools {{{'|'.join(STAGES)}}} [options]"


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to one pipeline stage.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` by default.

    Returns:
        The exit status of the stage, or 2 when no known stage was named.
    """
    configure_stdio()
    arguments = list(sys.argv[1:] if argv is None else argv)

    if not arguments or arguments[0] in {"-h", "--help"}:
        print(USAGE)
        print("\nStages:")
        print("  extract   exams/*.pdf -> data/raw-questions.json + answer-keys.json")
        print("  build     the data layers -> data/ and docs/data/")
        print("  validate  check the published bank against the contract")
        return 0 if arguments else 2

    stage = arguments[0]
    if stage not in STAGES:
        print(f"ERROR: unknown stage {stage!r}\n{USAGE}", file=sys.stderr)
        return 2

    return STAGES[stage](arguments[1:])


if __name__ == "__main__":
    raise SystemExit(main())
