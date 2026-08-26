# CLAUDE.md

**Read [AGENTS.md](AGENTS.md) first. It is the source of truth for this
repository, and this file adds nothing to it.**

Everything that governs the work lives there: the language policy, the
mandatory Google-style docstrings and type hints, the comment rules, the
question bank contract, the pipeline invariants, the constraints on the web app
(no CDN, no build step, no `innerHTML`), the accessibility floor, the theming
rules, the testing requirements, and the known defects in the source material.

When `AGENTS.md` and any other document disagree — this file, a code comment, a
stale README paragraph, an OpenSpec artifact — `AGENTS.md` wins, and the other
one gets fixed.

## Quick reference

```bash
python -m tools extract    # exams/*.pdf -> data/raw-questions.json
python -m tools build      # publish data/ and docs/data/question-bank.js
python -m tools validate   # check the published bank against the contract

python -m pytest           # pipeline tests
node --test tests/js/      # app logic tests
ruff check . && mypy tools tests
```

Open `docs/index.html` directly in a browser to run the app. It works over
`file://` and needs no server, because the bank ships as a plain script.
