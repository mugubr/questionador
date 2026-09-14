# AGENTS.md

Single source of truth for how this repository is built and maintained. Every
contributor — human or agent — follows this file. `CLAUDE.md` only points here.

---

## 1. What this project is

A static study app for the PROFNIT entrance and national exams. It draws
questions from a bank extracted out of the official exam PDFs, grades the
answer immediately, and shows the rationale behind each answer key.

Two halves, deliberately decoupled:

- **A Python pipeline** (`tools/`) that turns exam PDFs into a validated,
  versioned question bank. Runs on a developer machine, never in the browser.
- **A static web app** (`docs/`) that consumes the published bank. No build
  step, no framework, no bundler, no network request at runtime.

The app is published with GitHub Pages from `docs/` and must open with the
question bank already loaded — no upload, no click, no spinner.

---

## 2. Language policy

**All code is English. All content is Portuguese.**

English, without exception:

- File and directory names.
- Identifiers: variables, functions, classes, constants, CSS classes, CSS
  custom properties, HTML `id` and `data-*` attributes.
- Comments and docstrings.
- JSON field names and enum _values_ that never reach the screen
  (`"source": "official"`, `"confidence": "high"`).
- Commit messages, `AGENTS.md`, `CLAUDE.md`, OpenSpec artifacts, test names.

Portuguese, because the audience is Brazilian students and the exams are in
Portuguese:

- `README.md`.
- Every string rendered in the interface.
- Question text, options, rationales, references.
- Taxonomy values. A `topic` slug stays Portuguese kebab-case, unaccented and
  singular (`marca-e-indicacao-geografica`); the accented label the UI actually
  shows lives beside it in `data/topics.json`.

The dividing line: **an enum the code branches on is English; a value a student
reads is Portuguese.** Enum values are mapped to Portuguese labels through an
explicit lookup table in the UI layer, never by string manipulation.

---

## 3. Documentation rules

### Python — Google-style docstrings, mandatory

Every module, class, function, and method carries one. No exceptions, including
private helpers and test functions.

```python
def parse_option_line(line: str, expected_letter: str | None) -> Option | None:
    """Parse a single answer-option line out of the extracted PDF text.

    Only opens a new option when the letter matches the expected position in
    the a-b-c-d sequence, so a stray "a)" inside a stem cannot restart
    collection and swallow the rest of the question.

    Args:
        line: One raw line from the layout-preserving PDF text.
        expected_letter: The letter that may legally open here, or None when
            all four options are already closed.

    Returns:
        The parsed option, or None when the line is not an option opener.

    Raises:
        ValueError: If expected_letter is not a single a-d character.
    """
```

Sections in this order, omitting the ones that do not apply: `Args`, `Returns`,
`Yields`, `Raises`, `Example`. The summary line is one sentence in the
imperative mood, ending with a period.

### JavaScript — JSDoc with types, mandatory

Same coverage requirement. Every file starts with `// @ts-check` and every
function carries a typed JSDoc block. `jsconfig.json` makes the editor and CI
type-check the JavaScript from these annotations, so they are load-bearing, not
decoration.

```javascript
/**
 * Grade a choice and return a NEW session.
 *
 * A question that was already graded does not accept a second choice: the
 * session is returned unchanged.
 *
 * @param {Session} session - The current session. Never mutated.
 * @param {Question} question - The question being answered.
 * @param {OptionLetter} letter - The chosen letter.
 * @returns {Session} A new session with the grade applied.
 */
```

Shared shapes (`Question`, `Session`, `QuestionBank`) are declared once in
`docs/assets/js/types.js` with `@typedef` and referenced everywhere else.

### Formatting — never by hand

Two formatters own the whole repository and nothing is styled by hand.
**`ruff format` owns Python. `prettier` owns everything else** — HTML, CSS,
JavaScript, JSON, Markdown and the workflows. Both run in CI, and a diff should
never be about whitespace.

Settings live in `pyproject.toml` and `.prettierrc.json`: 88 columns (100 for
HTML, where attributes run long), two-space indent, single quotes and
semicolons in JavaScript, LF everywhere. They were chosen to match the code
that already existed rather than to impose a new house style on it.

`.prettierignore` earns its entries, and each one has a reason written next to
it:

- **Everything the pipeline generates.** Prettier and `python -m tools build`
  would reformat those files against each other forever, and the CI rebuild
  guard would fail on the difference. The pipeline owns their formatting.
- **`openspec/changes/archive/`.** An archived change records what shipped;
  reformatting it rewrites that record.
- **`.claude/`.** Vendored plugin files, not ours to restyle.
- **`uv.lock` and `package-lock.json`.** Owned by their package managers.
- **`node_modules/` and `.venv/`.** Installed dependencies, never ours.

Markdown uses `proseWrap: preserve` so the two conventions in this repository
can coexist, each one suiting its reader. **`README.md` is unwrapped**, one line
per paragraph: GitHub reflows it in the viewer, so a hard wrap buys nothing
there and turns a two-word edit into a diff across the whole paragraph.
**`AGENTS.md` and the OpenSpec artifacts stay hand-wrapped** at their current
width, because they are read in an editor as often as on a web page. Either way
the formatter still normalises tables, list markers and code fences.

### Type hints — mandatory

Every Python signature is fully annotated, parameters and return alike. `mypy`
runs in strict mode and the build fails on any error. `Any` is a last resort
that requires a comment saying why. Prefer `X | None` over `Optional[X]`, and
built-in generics (`list[str]`) over `typing.List`.

### Comments — useful only, always end with a period

A comment earns its place by explaining **why**, or by recording a fact the
reader cannot recover from the code: a defect in the source PDFs, a non-obvious
ordering constraint, a workaround and the thing it works around.

Never restate what the code says. Delete a comment before letting it go stale.

```python
# Clean noise BEFORE segmenting: in AV2-PI a page footer splits question 16
# mid-stem, and removing it first lets the stem reassemble on its own.
```

Not this:

```python
# Loop over the questions
for question in questions:
```

Every comment ends with a period, including single-line ones.

---

## 4. Repository layout

```
AGENTS.md                     these rules; the source of truth
CLAUDE.md                     pointer to AGENTS.md
README.md                     Portuguese, written for students
pyproject.toml                package metadata, ruff, mypy, pytest config
package.json                  prettier and typescript; the app itself ships none
jsconfig.json                 type-checking for the JavaScript
.prettierrc.json              formatter settings for everything but Python
.prettierignore               what prettier must not touch, each with a reason
.editorconfig                 the same settings for the editor
.gitattributes                LF for every generated artifact
.gitignore                    caches only; nothing under data/ or docs/

.github/workflows/
  ci.yml                      lint, type-check, test, validate, rebuild guard
  pages.yml                   publishes docs/ after CI passes

docs/                         GitHub Pages serves this directory
  .nojekyll
  index.html
  assets/css/styles.css
  assets/js/*.js
  assets/icons/favicon.svg
  data/question-bank.js       generated: assigns window.QUESTION_BANK

data/                         the bank and its editable source layers
  schema.json                 the JSON contract
  question-bank.json          generated: the canonical bank
  question-bank.md            generated: human review surface
  raw-questions.json          generated and versioned: the extraction anchor
  answer-keys.json            generated and versioned: the parsed official keys
  overrides.json              hand-written parse fixes
  topics.json                 the 15 topics and all 144 topic assignments
  answers/*.json              explanation and reference, for the 104 with one

tools/                        the Python package
  __init__.py                 the package docstring and configure_stdio()
  __main__.py                 CLI: python -m tools <extract|build|validate>
  config.py                   exam paper registry and shared constants
  models.py                   dataclasses and enums
  text_cleanup.py             noise patterns shared by extract and validate
  extract.py  answer_keys.py  build.py  validate.py

tests/                        pytest for Python, node:test for JavaScript
exams/                        source exam PDFs (read-only)
references/                   reference PDFs the explanations cite (read-only)
openspec/                     spec-driven change workflow
```

Nothing outside `docs/` is published. `exams/` and `references/` stay in the
repository but never reach the public site — they are third-party PDFs.

---

## 5. The question bank contract

`data/schema.json` is authoritative. `tools/validate.py` implements it and the
two must agree; a rule in one and not the other is a bug.

```jsonc
{
  "version": 1,
  "generatedAt": "2026-08-26",
  "toolchain": { "pdftotext": "25.07.0" },
  "exams": [
    {
      "id": "ENA26", // proper noun, never translated
      "title": "...", // Portuguese
      "date": "2025-11-22",
      "file": "Prova_ENA26.pdf",
      "hasOfficialAnswerKey": true
    }
  ],
  "topics": [
    {
      "id": "patente", // the slug a question's `topic` holds
      "label": "Patente", // Portuguese, accented: this is what the UI shows
      "definition": "..." // Portuguese: what the topic covers
    }
  ],
  "questions": [
    {
      "id": "ENA26-Q01", // always <exam>-Q<NN>, matches exam + number
      "exam": "ENA26",
      "number": 1,
      "topic": "patente", // a slug declared in topics[]
      "stem": "...", // Portuguese: the question body
      "options": { "a": "...", "b": "...", "c": "...", "d": "..." },
      "answer": {
        "letter": "c",
        "source": "official", // official | derived
        "confidence": "high", // derived only: high | medium | low
        "reference": "...", // always present: what was consulted
        "explanation": "...", // official only, optional: why the letter is right
        "rationale": "..." // derived only, required: how it was deduced
      },
      "duplicateOf": "AV2-PI-Q13", // optional, set on known repeats
      "knownDefects": ["identical-options"], // optional, defects of the source
      "excludedReason": "annulled" // optional; never drawn when present
    }
  ]
}
```

Invariants the validator enforces:

- `id == f"{exam}-Q{number:02d}"`. Three fields, one truth.
- Every `exam` appears in `exams[]`, and every exam has at least one question.
- Per-paper counts match `tools/config.py`, and numbering is contiguous 1..N.
- Every answer carries a `reference`, whatever its source.
- `source: "official"` carries neither `confidence` nor `rationale`.
  `explanation` is optional and, when present, non-empty.
- `source: "derived"` carries all of `confidence`, `reference` and `rationale`,
  and never an `explanation`.
- A question may omit `answer.letter` **only** when `excludedReason` is set.
- Every `topic` is declared in `topics[]`, and every declared topic is used by
  at least one question.
- No stem or option holds page-header or footer residue.
- A `duplicateOf` target exists and is not itself a duplicate.
- No object carries a field the contract does not declare, at any level.

### Provenance is not optional

**All seven papers have a published answer key, and every one of the 144
answers is `official`.** The keys live in `exams/` alongside the booklets. They
were recovered from `profnit.org.br`, whose `/exames/` page is a complete
archive back to 2016 and serves fine with a browser `User-Agent` — start there,
not at the Wayback CDX index.

Two verification steps make a key usable, and neither is optional:

1. **Prove the booklet identity.** Download the published question booklet and
   compare its MD5 against the copy in `exams/`. All seven match byte for byte.
   This matters more than it sounds: PROFNIT ran **two different ENA18
   Suplementar papers** for the same intake, and the other one annuls questions
   06 and 21. A key for the wrong sibling would have looked plausible and been
   entirely wrong.
2. **Check the randomization sentence.** The AV2 keys state that they refer to
   the booklet _as published_, which is what makes matching by question number
   valid. The ENA18 key does not say it — there the MD5 match makes the
   assurance redundant, because there is no separate randomized booklet for the
   numbering to drift against. Never match by number without one or the other.

`derived` stays in the schema, the validator and `models.py` because a future
paper may arrive without a key. But nothing in the bank is derived today, and
the code must not pretend otherwise or carry branches nothing exercises.

Where a derived rationale already existed, it survives as `explanation`: the
answer is published fact, and the reasoning is still what teaches. It carries
no `confidence`, because a published answer has none.

Never promote an answer to `official` without the key PDF in `exams/` and both
checks above. `official` means "a published answer key states this", nothing
else.

**The derivation work was measurably good, and that is a fact, not a
reassurance.** 104 answers were once derived, and 103 of them could be compared
against a key — the exception is `AV2-POL-Q14`, which the key annuls. 100 of
those 103 were already right. The hand-assigned confidence sorted them almost
perfectly: all 89 marked `high` were correct, both marked `low` were wrong, and
the single remaining error was one of the 12 marked `medium`. When something
must be deduced again, label its confidence honestly and the label will be
worth trusting.

---

## 6. The pipeline

```bash
python -m tools extract    # exams/*.pdf -> raw-questions.json + answer-keys.json
python -m tools build      # + overrides + answers + topics -> data/ and docs/
python -m tools validate   # checks the published bank against the contract
```

**`extract` is the only stage that runs a subprocess. `build` is pure assembly
over committed files and must stay that way.** It is what lets anyone correct
an explanation and rebuild without installing poppler, and it is what makes the
CI rebuild guard meaningful — with no external tool in the loop, the only
variable left is whether the committed bank is what the committed inputs and
the current code produce. A test asserts that importing `tools.build` pulls in
neither `tools.extract`, `subprocess`, `shutil` nor `datetime`; if that test
starts failing, the dependency crept back.

Layers, applied in this order, each one narrow and auditable:

1. `data/raw-questions.json` — deterministic output of `extract`, versioned so
   the chain can be rebuilt and diffed without running `pdftotext`.
2. `data/overrides.json` — hand-written fixes for layout the parser cannot
   resolve, overlaid on the extracted text before anything else reads it. Each
   entry records its reason.
3. `data/answer-keys.json` — the parsed official keys for all seven papers,
   matched by question number, with `null` where a question was annulled.
4. `data/answers/*.json` — the explanation and reference for each question that
   has one.
5. `data/topics.json` — the 15-topic taxonomy and every question's topic.

Both extraction artifacts carry the poppler version that produced them —
provenance belongs to the step that ran the tool. `build` copies that stamp
into the bank and refuses a pair whose stamps disagree, because that means they
came from different `extract` runs.

`generatedAt` carries forward from the committed bank rather than defaulting to
today, so an unchanged rebuild produces unchanged bytes. `--generated-at` asks
for a genuinely new date.

### Rules the pipeline obeys

- **Fail loudly, never guess.** A question the parser cannot resolve is marked
  for review and blocks the build. Emitting a silently incomplete bank is worse
  than emitting nothing.
- **Accumulate errors.** Report every problem in one run, not the first one.
- **`pdftotext` is pinned.** Poppler only, invoked as
  `pdftotext -layout -enc UTF-8`, with `encoding="utf-8"` on the subprocess.
  The version is checked at startup and recorded in the output. Xpdf — which
  Git for Windows ships as `pdftotext` — emits Latin-1 and different dashes,
  and silently produces a different bank. Check `shutil.which` and the version
  before doing any work.
- **Write with `newline="\n"`.** Every generated artifact is LF on every
  platform, so a rebuild on Linux does not produce a whole-file diff.
- **Deterministic output.** Sort every iteration over a set or a glob. No
  timestamps other than the explicit `generatedAt`. Same inputs, same bytes.
- **No orphan keys.** A key in `overrides.json`, the `assignments` of
  `topics.json`, `answers/*.json` or one of the three question maps in
  `tools/config.py` that matches no question is an error, not a silent no-op.
- **Check stems _and_ options.** Noise detection, column-layout detection, and
  residue checks apply to both. A footer inside option `d` is as wrong as one
  inside the stem.
- **Never print non-ASCII to the console.** Windows defaults `stdout` to cp1252
  and a single check mark aborts the run after all the work is done. Reconfigure
  `stdout` to UTF-8 at entry and keep progress output plain.

### Correcting an explanation

Edit `data/answers/<paper>.json` and rerun `build`. No application code changes.
An entry holds `explanation` and `reference` and nothing else — the letter comes
from the published key, so the two can never disagree. `data/question-bank.md`
is the review surface: every question with its answer, provenance, reference and
explanation in readable form.

---

## 7. The web app

### Hard constraints

- **No CDN, no external request.** Every byte is served from `docs/`. No
  webfont host, no analytics, no script tag pointing anywhere else. System font
  stacks only. If something seems to need a CDN, it does not get added.
- **No build step and no bundler.** The files in `docs/` are the files that
  ship. Editing CSS and reloading is the whole loop.
- **No framework and no runtime dependency.** Plain HTML, CSS, JavaScript.
- **Classic scripts, not ES modules.** `<script>` tags with an explicit load
  order, so the app also works when `index.html` is opened over `file://`. Each
  file exposes one namespace object; nothing else touches the global scope.
- **Modern syntax.** `const`/`let`, arrow functions, template literals,
  optional chaining. `var` is not used.

### Loading the bank

`docs/data/question-bank.js` assigns `window.QUESTION_BANK` and is loaded by a
plain `<script>` tag. This is what makes the site open already loaded, and it
works identically over `https://` and `file://` because no `fetch` is involved.

The bank is still validated at startup: it is generated data, but the validator
is also the guard for a hand-edited or stale file, and it produces the error
message the user sees. `localStorage` never caches the bank — the embedded file
is always the truth, which removes a whole class of staleness bugs.

### Security

**Every string that originates in the bank reaches the DOM through
`textContent`. Never `innerHTML`, never `insertAdjacentHTML`, never
`document.write`.** This holds even though the bank now ships with the app; the
discipline is what makes the rule checkable, and a hand-edited bank is still
possible.

Use `Object.create(null)` or `Map` for any object keyed by data-derived
strings, so an id like `constructor` cannot collide with `Object.prototype`.

### Accessibility — WCAG 2.2 level AA is the floor

- **Contrast**: 4.5:1 for text, 3:1 for large text and for the visual boundary
  of any interactive control. Verify in **both** themes; a token that passes in
  light and fails in dark is a failure.
- **Never encode state in color alone.** A correct or incorrect option carries
  a non-color marker and an accessible name that states the outcome.
- **Reflow**: no horizontal scrolling at 320px. Grid items need
  `overflow-wrap: anywhere` or `min-width: 0`; `break-word` does not shrink a
  grid item's automatic minimum size.
- **Focus**: visible on every interactive element, and managed on every panel
  change. Moving focus into a `display: none` subtree is a defect.
- **Announcements**: exactly one `role="status"` region, always present in the
  DOM and never toggled with `hidden`, carrying a complete sentence. Content
  written into a hidden element and then revealed is not reliably announced.
- **Semantics**: real headings that name the current state, `role="progressbar"`
  with its value attributes, form controls with associated descriptions.
- **Targets**: interactive controls are at least 44x44 CSS pixels.
- **Keyboard**: a global shortcut yields to whatever has focus. Never
  `preventDefault` a key that a focused control would otherwise handle.

### Theming

Three states — system, light, dark. The choice persists in `localStorage` and a
small inline script in `<head>` applies `data-theme` **before first paint**, so
reloading in dark does not flash white.

Each color token is declared **once**, with both values side by side, using
`light-dark()`. The whole theme switch is then three `color-scheme`
declarations — bare `:root` follows the system, `[data-theme="light"]` and
`[data-theme="dark"]` pin it — and the browser paints its own scrollbars and
form controls to match for free. Two hand-synchronized palettes in a media
query and an attribute selector are what this replaces, and they must not come
back.

`light-dark()` needs one safety net. A custom property holding an unsupported
function still _parses_, so it wins the cascade and fails only at substitution
— which strips every color from the page instead of falling back. An
`@supports not (color: light-dark(white, black))` block re-declares the light
palette for those browsers. Only the light one: degrading to light theme is
graceful, and duplicating the dark palette would reintroduce exactly the
hazard `light-dark()` removed.

No color is ever hardcoded outside the token block.

---

## 8. Testing

Everything runs offline with no network and no service.

```bash
python -m pytest                    # the pipeline
node --test "tests/js/*.test.js"    # the app's pure logic
python -m tools validate            # the published bank against the contract
ruff check . && ruff format --check .
npx prettier --check .
npx tsc --project jsconfig.json
mypy tools tests
```

- **`tools/` is tested at the seams.** Parsing functions take text and return
  structures, so the parser is tested with inline strings and never needs a
  PDF. Anything touching `subprocess` or the filesystem is thin and separated
  from the logic it wraps.
- **`session.js` and `bank.js` are pure and fully tested** — filtering,
  shuffling, grading, scoring, validation. They touch neither the DOM nor
  `localStorage`, which is exactly why that boundary exists.
- **Every fixed bug gets a test** that fails before the fix. This is the main
  reason the suite exists: the parser regressed once already, silently, because
  a different `pdftotext` produced different dashes.
- **A golden test validates the committed bank** on every run. It is one
  assertion and it catches an entire class of mistakes.

CI runs all of the above on every push and pull request, and Pages only
publishes after it passes.

---

## 9. Known defects in the source material

Faithfully reproduced, never silently "fixed". Each is recorded in the data so
the app can act on it.

- **The `AV2-PI` booklet is defective, and the official key proves it.** Items
  14 and 16 reprint items 13 and 15, options included — 16 to the character, 14
  with the assertions of its list renumbered. But the
  published key reads `13=A, 14=B` and `15=C, 16=D` — and a key cannot give two
  letters to one question. So the real exam had _different_ questions at 14 and
  16, and the booklet in `exams/` is the thing that is wrong. Re-keying them to
  B and D would attach real answers to questions nobody has. They carry
  `duplicateOf` and `excludedReason: "source-booklet-defect"`, and are never
  drawn.
- **`AV2-POL-Q14` is annulled.** The official key prints `ANULADA` where a
  letter should be. The question has no `answer.letter` and carries
  `excludedReason: "annulled"`.
- **`AV2-MET-Q14` has two identical options.** Options `a` and `d` are the same
  string in the original PDF. Effectively a three-option question. Recorded in
  `knownDefects`, and the app treats a choice of either twin consistently.
- **`AV2-MET-Q08`'s option `d` cites an item the stem never lists.** The stem's
  "Ordenações propostas" numbers its items I through IV; option `d` reads
  "Apenas IV e V estão corretas," and there is no V. Confirmed against the
  printed booklet — a defect of the source, not of the stem-rewrite override
  this question also carries. Recorded in `knownDefects` as
  `phantom-item-reference`.
- **Five questions carry an entry in `data/overrides.json`**, because
  `pdftotext -layout` does not resolve their layout deterministically.
  `ENA25-Q09`, `ENA25-Q14` and `AV2-MET-Q08` have a rewritten stem: two-column
  matching tables rendered side by side, and in `AV2-MET-Q08` a second `a)-d)`
  set that belongs to the stem. `AV2-POL-Q10` and `ENA18-Q40` were flagged,
  reviewed and found already correct — their extracted text is pinned verbatim,
  which is what clears the flag. Each entry's `_reason` says which of the two it
  is.
- **`AV2-MET` explanations rest on general methodology bibliography** — ABNT
  norms, the CAPES Qualis, classic references — not on the PDFs in
  `references/`, which do not cover the subject. `AV2-MET-Q09` is the one
  exception, backed by the Frascati manual. The other `reference` fields say
  plainly that no file supports them rather than pointing at one that does not.
  A reference naming no document is better than one naming the wrong document.
- **`references/Ref8` has no text layer.** 127 pages of pure image; extracting
  it yields zero characters. It is the PROSP PROFNIT book and is named by 15
  answers that could never be checked against it. It has since been OCRed, so
  its content is searchable — but the PDF in the repository is still
  unsearchable by ordinary tools, and anyone verifying against it needs to know
  that before concluding "the source does not say this".

### One superseded finding, kept as a lesson

A statistical audit once flagged that the correct option is the longest 60% of
the time among officially-keyed questions but only 33% among derived ones
(Fisher p=0.0042), and concluded that roughly 28 derived answers were suspect.

When the real answer keys arrived, **that inference was wrong**. The derived
answers agreed with the official keys 97% of the time, and the three genuine
errors were not the ones the length signal predicted — the `confidence` field,
assigned by hand, predicted them precisely. Do not change an answer because a
distribution looks unusual. Get the key.

---

## 10. Working agreements

### This is a fork, and the work goes upstream

The repository forks [`mugubr/questionador`](https://github.com/mugubr/questionador)
and exists to contribute back to it. Shape the work accordingly: small,
independent commits a maintainer can review and take one at a time, not one
sweeping change.

### Changes go through OpenSpec

Non-trivial work starts with a change under `openspec/changes/`: proposal,
design, spec deltas, tasks. Implementation follows the tasks and ticks them
off. A completed change is archived so its specs land in `openspec/specs/`.

Small, obvious fixes do not need a change. A refactor, a new capability, or
anything touching the data contract does.

### Git

- Commit messages in English, imperative mood, scoped by phase.
- Never commit generated artifacts that are not meant to be reviewed. The bank,
  the markdown, and `raw-questions.json` **are** meant to be reviewed — they are
  committed on purpose, and their diffs are the point.
- Never rewrite published history.

### Before calling anything done

1. `ruff check`, `ruff format --check`, `mypy` clean.
2. `pytest` and `node --test` green.
3. `python -m tools validate` green.
4. The app opened and exercised in both themes, at 320px and at desktop width.
5. No new external request. Check the network panel: it must stay empty.
