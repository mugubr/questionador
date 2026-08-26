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
- JSON field names and enum *values* that never reach the screen
  (`"source": "official"`, `"confidence": "high"`).
- Commit messages, `AGENTS.md`, `CLAUDE.md`, OpenSpec artifacts, test names.

Portuguese, because the audience is Brazilian students and the exams are in
Portuguese:

- `README.md`.
- Every string rendered in the interface.
- Question text, options, rationales, references.
- Taxonomy values that are displayed as labels — `topic` values stay Portuguese
  kebab-case (`propriedade-intelectual`), because the UI shows them.

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
jsconfig.json                 type-checking for the JavaScript
.gitattributes                LF for every generated artifact

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
  overrides.json              hand-written parse fixes
  official-topics.json        topic for the officially-keyed questions
  answers/*.json              derived answers, one file per exam paper

tools/                        the Python package
  __main__.py                 CLI: python -m tools <extract|build|validate>
  config.py                   exam paper registry and shared constants
  models.py                   dataclasses and enums
  text_cleanup.py             noise patterns shared by extract and validate
  extract.py  answer_keys.py  build.py  validate.py

tests/                        pytest for Python, node:test for JavaScript
exams/                        source exam PDFs (read-only)
references/                   reference PDFs used to derive answers (read-only)
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
  "exams": [{
    "id": "ENA26",              // proper noun, never translated
    "title": "...",             // Portuguese
    "date": "2025-11-22",
    "file": "Prova_ENA26.pdf",
    "hasOfficialAnswerKey": true
  }],
  "questions": [{
    "id": "ENA26-Q01",          // always <exam>-Q<NN>, matches exam + number
    "exam": "ENA26",
    "number": 1,
    "topic": "patentes",        // Portuguese: it is displayed
    "stem": "...",              // Portuguese: the question body
    "options": { "a": "...", "b": "...", "c": "...", "d": "..." },
    "answer": {
      "letter": "c",
      "source": "official",     // official | derived
      "confidence": "high",     // derived only: high | medium | low
      "reference": "...",       // what was consulted
      "rationale": "..."        // Portuguese: why this answer
    },
    "duplicateOf": "AV2-PI-Q13",           // optional, set on known repeats
    "knownDefects": ["identical-options"]  // optional, defects of the source
  }]
}
```

Invariants the validator enforces:

- `id == f"{exam}-Q{number:02d}"`. Three fields, one truth.
- Every `exam` appears in `exams[]`, and every exam has at least one question.
- Per-paper counts match `tools/config.py`, and numbering is contiguous 1..N.
- `source: "official"` carries no `confidence` and no `rationale`.
- `source: "derived"` carries all of `confidence`, `reference`, `rationale`.
- No stem or option holds page-header or footer residue.
- A `duplicateOf` target exists and is not itself a duplicate.

### Provenance is not optional

Only ENA25 and ENA26 have a published answer key — 40 questions. The other 104
answers were **derived** from the reference PDFs and applicable law. Each one
records its reference, its rationale, and a confidence level, and the app marks
it visibly. A derived answer can be wrong, and the data says so.

Never promote a derived answer to `official`. `official` means "a published
answer key states this", nothing else.

---

## 6. The pipeline

```bash
python -m tools extract    # exams/*.pdf      -> data/raw-questions.json
python -m tools build      # + overrides + keys + answers -> data/ and docs/
python -m tools validate   # checks the published bank against the contract
```

Layers, applied in this order, each one narrow and auditable:

1. `data/raw-questions.json` — deterministic output of `extract`, versioned so
   the chain can be rebuilt and diffed without running `pdftotext`.
2. `data/overrides.json` — hand-written fixes for layout the parser cannot
   resolve. Each entry records its reason.
3. Official answer keys — ENA25 and ENA26, matched by question number.
4. `data/answers/*.json` — the 104 derived answers.
5. `data/official-topics.json` — topics for the officially-keyed questions.

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
- **No orphan keys.** A key in `overrides.json`, `official-topics.json`, or
  `answers/*.json` that matches no question is an error, not a silent no-op.
- **Check stems *and* options.** Noise detection, column-layout detection, and
  residue checks apply to both. A footer inside option `d` is as wrong as one
  inside the stem.
- **Never print non-ASCII to the console.** Windows defaults `stdout` to cp1252
  and a single check mark aborts the run after all the work is done. Reconfigure
  `stdout` to UTF-8 at entry and keep progress output plain.

### Correcting a derived answer

Edit `data/answers/<exam>.json` and rerun `build`. No application code changes.
`data/question-bank.md` is the review surface: every question with its answer,
provenance, reference, and rationale in readable form.

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

Define the full light palette on bare `:root`. Redefine only the tokens that
change under
`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }`
and again under `:root[data-theme="dark"]`, sharing one declaration list — never
two hand-synchronized copies. Declare `color-scheme` so the browser paints its
own surfaces to match.

No color is ever hardcoded outside the token block.

---

## 8. Testing

Everything runs offline with no network and no service.

```bash
python -m pytest              # the pipeline
node --test tests/js/         # the app's pure logic
python -m tools validate      # the published bank against the contract
ruff check . && ruff format --check .
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

- **`AV2-PI` repeats questions.** Q14 duplicates Q13 with corrupted assertion
  numbering (`I, II, III, III`), and Q16 is identical to Q15. Sixteen numbered
  items, fourteen distinct questions. Both repeats carry `duplicateOf` and are
  excluded from the draw by default.
- **`AV2-MET-Q14` has two identical options.** Options `a` and `d` are the same
  string in the original PDF. Effectively a three-option question. Recorded in
  `knownDefects`.
- **Three questions needed hand-written stems** because the PDF layout does not
  resolve deterministically: `ENA25-Q14` and `AV2-MET-Q08` (two-column matching
  tables that `pdftotext -layout` renders side by side) and `ENA18-Q40`
  (closing text glued onto the last option). See `data/overrides.json`.
- **`AV2-MET` answers rest on general methodology bibliography** — ABNT norms,
  the CAPES Qualis, classic references — not on the PDFs in `references/`,
  which do not cover the subject. Their `reference` fields say so plainly
  rather than pointing at a file that does not support them.
- **Derived answers show a weaker length bias than the official ones.** In the
  40 officially-keyed questions the correct option is the longest 60% of the
  time; in the 104 derived ones, 33% (Fisher p=0.0042). This is a signal that
  some derived keys may be wrong, not proof. Treat it as a standing reason to
  re-review, and never as grounds to change an answer on its own.

---

## 10. Working agreements

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
