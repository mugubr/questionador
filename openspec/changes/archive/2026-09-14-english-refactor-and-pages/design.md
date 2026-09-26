## Context

The project already works end to end: 144 questions extracted from 7 exam PDFs,
40 of them matched against published answer keys and 104 derived from the
reference material with a recorded reference, rationale and confidence level.
What is missing is everything around that: the app is not published, the bank
has to be uploaded by hand, and the codebase carries two languages at once.

Three constraints shape every decision below and none of them is negotiable:

- **`file://` must keep working.** The app is opened from disk today and that
  stays true. It rules out `fetch`, ES modules, and anything that needs an
  origin.
- **No build step for the app.** The files in `docs/` are the files that ship.
  Editing CSS and reloading is the whole loop.
- **No external request, ever.** No CDN, no webfont host, no analytics. The
  network panel stays empty.

The pipeline runs on a developer machine, mostly Windows, and produces artifacts
that are committed and reviewed as diffs. That combination — Windows plus
"the diff is the point" — is where most of the pipeline decisions come from.

## Goals / Non-Goals

**Goals:**

- A student opens a URL and the app is already loaded. No upload, no click, no
  spinner.
- One language rule that can be checked mechanically: code English, content
  Portuguese, with the dividing line at "does a student read this value?".
- A rebuild on any platform produces byte-identical artifacts, so a diff means a
  real change.
- The pipeline fails loudly and early instead of shipping a silently different
  bank.
- WCAG 2.2 level AA in both themes, verified rather than asserted.
- Every fixed defect is pinned by a test that fails before the fix.

**Non-Goals:**

- Any backend, account system, or cross-device sync. History is per-browser.
- Translating the interface. The audience is Brazilian students.
- A framework, a bundler, or a build step for the app.
- Re-deriving or re-reviewing the 104 derived answers. Their content is out of
  scope here; only their field names move.
- Backwards compatibility with the Portuguese bank format.

## Decisions

### D1 — The bank ships embedded as a classic script

`docs/data/question-bank.js` assigns `window.QUESTION_BANK` and is loaded by a
plain `<script>` tag before the app's own files. Upload remains, demoted to a
secondary affordance for trying a hand-edited bank.

Why: it is the only option that makes the site open already loaded _and_ keeps
`file://` working, because no request is involved at all. It also deletes a
whole class of staleness bugs — the embedded file is the truth and
`localStorage` never caches the bank.

Rejected:

- **`fetch('data/question-bank.json')` with an upload fallback.** Two loading
  paths and two error paths to keep correct, and the primary one fails outright
  over `file://`, which means the fallback is not a fallback but the normal case
  for half the usage.
- **`fetch()` only.** Kills `file://` entirely.

Cost: the bank is parsed as JavaScript source rather than JSON, so the generator
must emit a safe literal. It writes `window.QUESTION_BANK = <json>;` where
`<json>` is `json.dumps` output with `</` escaped, so the payload cannot close
the enclosing `<script>` tag. The bank is still validated at startup: it is
generated data, but the validator is also the guard for a hand-edited or stale
file, and it produces the message the user sees.

### D2 — GitHub Pages publishes from `docs/`

Pages is configured to serve the `docs/` directory of the default branch.
`docs/` holds only the app: `index.html`, `assets/`, `data/question-bank.js`,
`.nojekyll` — around 250 KB.

Why: `exams/` and `references/` are roughly 50 MB of third-party PDFs — official
exam papers and reference material. Keeping them in the repository is
deliberate; publishing them is not our call to make. A publishing root that
contains only what we authored makes that boundary structural instead of a
policy someone has to remember.

Rejected:

- **Publishing from the repository root.** Would put every PDF, plus `data/`,
  plus `tools/`, on a public URL.
- **A `gh-pages` branch built by an Action.** Introduces a build step for an app
  whose defining property is not having one, and makes the deployed bytes
  different from the reviewed bytes.

`.nojekyll` is required: without it Pages runs Jekyll, which ignores files and
directories starting with an underscore and adds a build stage we do not want.

### D3 — Code and JSON field names in English, content in Portuguese

Every field name and every enum value the code branches on becomes English.
Every value a student reads stays Portuguese, including `topic`, whose values
are rendered as labels. Enum values are mapped to Portuguese labels through an
explicit lookup table in the UI layer, never by string manipulation.

Why: the rule has to be decidable by looking at a single value. "Does this reach
the screen?" is decidable; "is this domain vocabulary?" is not.

Rejected:

- **Keeping the Portuguese JSON keys** and translating only the code. Leaves a
  permanent translation boundary at exactly the place bugs hide — the point
  where data becomes code — and every reader has to hold both vocabularies.
- **Translating the UI to English too.** The exams are in Portuguese and so are
  the students. Consistency is not worth an unusable app.

### D4 — Classic scripts, modernized

`<script>` tags with an explicit load order. Each file exposes exactly one
namespace object and touches nothing else on the global scope. Inside the files:
`const`/`let`, arrow functions, template literals, optional chaining; `var` is
not used.

Why: ES modules cannot load over `file://` — the module fetch is blocked by the
origin rules regardless of the syntax used. Classic scripts are the only way to
keep both "modern code" and "opens from disk".

Rejected:

- **ES modules with a dev server for local work.** Trades the project's simplest
  property for an import statement.
- **A bundler producing a single classic script.** A build step, for a project
  whose whole point is not having one.

Type safety comes from `// @ts-check` plus typed JSDoc, with the shared shapes
(`Question`, `Session`, `QuestionBank`) declared once in
`docs/assets/js/types.js` and referenced everywhere. `jsconfig.json` makes the
editor and CI check them, so the annotations are load-bearing.

### D5 — `tools/` is a real package with a subcommand CLI

`python -m tools extract | build | validate`, with `tools/__main__.py` as the
single entry point, `tools/config.py` holding the exam registry and shared
constants, `tools/models.py` the dataclasses and enums, and `tools/text_cleanup.py`
the noise patterns shared by extract and validate.

Why: the old `scripts/` directory was not importable, so every script began with
a `sys.path.insert` to reach its siblings. That hack is the reason the noise
patterns were duplicated between extraction and validation and drifted — which
is how 13 footer-contaminated options passed validation.

Rejected: keeping standalone scripts and adding a `conftest.py` to make the
tests import them. Fixes the tests, not the duplication.

### D6 — `pdftotext` is pinned to poppler and the version is recorded

At startup the pipeline resolves `pdftotext` via `shutil.which`, runs
`pdftotext -v`, requires poppler, and refuses to run otherwise. The resolved
version is written into the bank as `toolchain.pdftotext`. The invocation is
always `pdftotext -layout -enc UTF-8` with `encoding="utf-8"` on the subprocess.

Why: Git for Windows ships **Xpdf 4.00** as `pdftotext`, and on a default
Windows `PATH` it usually wins. It emits Latin-1 and different dash characters,
and it produces a _different bank_ without failing — the parser regressed
silently once already for exactly this reason. Checking before doing any work
turns a silent data corruption into a startup error, and recording the version
in the output makes a future divergence diagnosable from the artifact alone.

Rejected:

- **Normalizing dashes after extraction.** Papers over one symptom of running
  the wrong tool and leaves the encoding difference in place.
- **Vendoring the extracted text and never running `pdftotext` in CI.** This is
  half-adopted deliberately: `data/raw-questions.json` _is_ committed as the
  extraction anchor, so `build` and `validate` run anywhere without poppler.
  But `extract` still has to be reproducible, so the pin stays.

### D7 — Deterministic, byte-identical artifacts

Every generated file is opened with `newline="\n"`. Every iteration over a set
or a glob is sorted. The only timestamp is the explicit `generatedAt` date.
Console output is ASCII only, and `stdout` is reconfigured to UTF-8 at entry.

Why: two separate failures. Without `newline="\n"`, a rebuild on Windows writes
CRLF and every generated file shows up as a whole-file diff, which destroys the
review surface that `question-bank.md` exists to provide. And without the
`stdout` reconfiguration, a single non-ASCII character in a progress message
raises `UnicodeEncodeError` on a cp1252 console — the current extraction dies
that way, after all the work and before writing its output.

### D8 — The contract changes, and it changes all at once

This is the part that touches the question bank contract, so it is spelled out.

Field renames: `versao`→`version`, `provas`→`exams`, `questoes`→`questions`,
`enunciado`→`stem`, `alternativas`→`options`, `resposta`→`answer`,
`letra`→`letter`, `procedencia`→`source`, `confianca`→`confidence`,
`referencia`→`reference`, `justificativa`→`rationale`, `tema`→`topic`,
`prova`→`exam`, `numero`→`number`, `parse_status`→`parseStatus`.

Enum renames: `oficial`→`official`, `derivada`→`derived`; `alta`→`high`,
`media`→`medium`, `baixa`→`low`.

New fields: `generatedAt` (the build date), `toolchain` (the recorded
`pdftotext` version), `duplicateOf` (set on a question that repeats another),
`knownDefects` (defects of the source PDF, faithfully reproduced rather than
silently fixed).

Unchanged, on purpose: `topic` **values** stay Portuguese kebab-case, exam ids
stay proper nouns (`ENA26`, `AV2-PI`), question ids stay
`<exam>-Q<NN>`, and every Portuguese string — stem, options, reference,
rationale, exam title — is untouched.

There is no migration shim and no version negotiation. The bank ships with the
app, so there is exactly one producer and one consumer and both change in the
same commit. `data/schema.json` and `tools/validate.py` are updated together; a
rule in one and not the other is a bug.

### D9 — A third capability, `static-site-publishing`

The Pages deployment and the CI gate become their own capability rather than
extra requirements inside `quiz-runner`.

Why: `quiz-runner` requirements describe what the app does for a student, and
their scenarios are verifiable by running the app — `node --test` on the pure
logic, or a browser on the rendered page. "Pages publishes only after CI passes"
and "`references/` never reaches the public site" cannot be verified that way at
all; they are properties of the repository and its deployment, checked by
inspecting the workflow, the published directory listing, and the deployed URL.
Mixing the two would put untestable-by-the-app requirements into a capability
whose whole value is that its scenarios are testable.

The seam is clean: `quiz-runner` owns "the bank is already loaded when the app
starts"; `static-site-publishing` owns "the bank that is served matches the bank
that was committed, and it got there only after CI was green".

Rejected: folding both into `quiz-runner`. It would make the capability mean
"the app and also how we host it", and the first requirement that has nothing to
do with a student using the app is the moment the boundary stops meaning
anything.

### D10 — New app behaviour, and where the state lives

- **Session resume.** The session is already written to `localStorage` on every
  answer; it is simply never read back. Resume reads it at startup, checks that
  the stored bank `version` and `generatedAt` match the embedded bank, and
  offers to continue. A mismatch discards the stored session rather than
  resuming into questions that may no longer exist.
- **Option shuffling.** The options are shuffled per question at draw time; the
  stored answer letter is resolved against the _original_ letter, so the graded
  result and the review surface stay in the bank's terms.
- **Configurable session size.** The deck is truncated to N after shuffling.
- **Cross-session history.** A separate `localStorage` key holds, per question
  id, the last outcome and the number of attempts. It powers the "only the ones
  I got wrong" and "never answered" filters. It is keyed by data-derived
  strings, so it lives in a `Map` or an `Object.create(null)`, never a plain
  object literal — an id like `constructor` must not collide with
  `Object.prototype`.
- **Duplicates excluded by default.** A question carrying `duplicateOf` is out
  of the draw unless the user opts in. `AV2-PI` has sixteen numbered items and
  fourteen distinct questions.

All of it is pure logic in `session.js` and `bank.js`, which touch neither the
DOM nor `localStorage` — that boundary exists precisely so this is testable
with `node --test`.

### D11 — Theming and accessibility

Three states: system, light, dark. The choice persists in `localStorage`, and a
small inline script in `<head>` applies `data-theme` **before first paint**, so
a reload in dark mode does not flash white. The full light palette is defined on
bare `:root`; only the tokens that change are redefined under
`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` and
again under `:root[data-theme="dark"]`, sharing one declaration list rather than
two hand-synchronized copies. `color-scheme` is declared so the browser paints
its own surfaces to match. No colour is hardcoded outside the token block.

The accessibility work is defect-driven, not aspirational:

- Contrast is verified in **both** themes. A token that passes in light and
  fails in dark is a failure.
- Option state carries a non-color marker and an accessible name stating the
  outcome. Colour alone is not state.
- Reflow at 320px: the current overflow is 102px and comes from grid items
  without `min-width: 0`. `overflow-wrap: anywhere` alone does not shrink a grid
  item's automatic minimum size.
- Focus is managed on every panel change, and never moved into a
  `display: none` subtree.
- Exactly one `role="status"` region, always present in the DOM, never toggled
  with `hidden`, carrying a complete sentence. Text written into a hidden
  element and then revealed is not reliably announced.
- The `Enter` shortcut yields to whatever has focus. A global handler must never
  `preventDefault` a key a focused control would otherwise handle — that is the
  current hijack.
- Interactive controls are at least 44x44 CSS pixels.

### D12 — Testing and the CI gate

`pytest` for the pipeline, tested at the seams: parsing functions take text and
return structures, so they are exercised with inline strings and never need a
PDF. `node --test tests/js/` for `session.js` and `bank.js`. A golden test runs
the validator against the committed bank on every run — one assertion that
catches an entire class of mistakes.

CI runs `ruff check`, `ruff format --check`, `mypy` in strict mode, `pytest`,
`node --test` and `python -m tools validate` on every push and pull request.
The Pages deployment depends on that job succeeding, so a red build cannot
publish.

Every defect listed in the proposal gets a test that fails before its fix. This
is the main reason the suite exists: the parser already regressed once,
silently.

## Risks / Trade-offs

- **The contract rename is a flag day.** Every data file, the schema, the
  validator and the app change together, and a partial application produces a
  bank that loads nowhere. → The renames land in one commit per phase with
  `python -m tools validate` green before and after, and the golden test makes a
  half-migrated bank fail immediately rather than at runtime.

- **`docs/data/question-bank.js` can drift from `data/question-bank.json`.** Two
  files, one truth. → `build` writes both from the same in-memory object, and
  CI re-runs `build` and fails if the working tree is dirty afterwards. The
  freshness check is a requirement of `static-site-publishing`, not a
  convention.

- **The bank is executable JavaScript now.** A malicious or corrupted bank file
  is script, not data. → It is generated by us, committed, and reviewed as a
  diff; the generator escapes `</` so the payload cannot break out of the
  `<script>` tag; and the app still reaches the DOM only through `textContent`,
  so bank strings are never interpreted as markup regardless.

- **Shuffled options break the reflex of remembering "the answer is C".** That
  is the point, but it also means a stored session from before the shuffle
  cannot be resumed positionally. → The session stores the resolved original
  letter, not the displayed position.

- **Cross-session history is per-browser and silently lost.** Clearing site data
  or switching device wipes it. → It is a convenience, never a source of truth;
  the app works fully with an empty history and with `localStorage` throwing on
  every call.

- **The Xpdf trap can reappear on a fresh Windows machine.** → The version check
  runs before any work, the failure message names poppler explicitly, and
  `toolchain.pdftotext` in the committed bank makes a past divergence
  diagnosable from the artifact.

- **WCAG 2.2 AA is asserted more easily than it is met.** → Contrast pairs are
  checked as computed values in both themes, reflow is checked at 320px, and
  focus order is walked with the keyboard before the phase is called done.

- **Fixing `ENA25-Q09` and the 13 footer-contaminated options changes question
  text.** Content edits are exactly what this change said it would not do. →
  These are defect fixes with a recorded reason in `data/overrides.json`, and
  each one shows up as a reviewable diff in `data/question-bank.md`. No answer
  letter, confidence or rationale changes.

## Migration Plan

The phases land as separate commits, in this order, each one leaving the
repository in a working state:

1. **Rules and OpenSpec** — `AGENTS.md`, `CLAUDE.md`, the OpenSpec change, and
   the `git mv` renames. No behaviour change. _Already applied._
2. **Pipeline package** — `tools/` becomes importable with a subcommand CLI, the
   toolchain pin, LF writing and ASCII console output. The bank is regenerated
   in the _old_ format and must come out byte-identical apart from line endings,
   which proves the restructure changed nothing.
3. **Data migration** — schema, validator and every data file move to the
   English contract in one commit, with `data/raw-questions.json` committed and
   the option-level noise checks turned on. `ENA25-Q09` and the 13 contaminated
   options are fixed here.
4. **App** — the embedded bank, the modernized scripts, theming, accessibility,
   and the new session features.
5. **Tests and CI** — the two suites, the golden test, and the workflow.
6. **Pages and README** — Pages enabled on `docs/`, the deploy gated on CI, and
   the README rewritten in Portuguese for students, pointing at the published
   URL.

Rollback: phases 2 through 5 are ordinary reverts — nothing outside the
repository has changed. Phase 6 is the only one with external state; rolling it
back means disabling Pages in the repository settings, and the app keeps working
over `file://` exactly as before.

## Open Questions

- **How many previous outcomes should the history keep per question?** The
  filters need only the last outcome and an attempt count, which is what D10
  specifies. A full attempt log would enable spaced repetition later, at the
  cost of unbounded `localStorage` growth. Deferred until spaced repetition is
  actually proposed.
- **Should the default session size be 10, 20, or the whole filtered set?** The
  exam papers are 16, 20 and 40 questions, so 20 matches a real paper. To be
  settled by using it during phase 4.
- **Does the derived-answer length bias warrant re-review inside this change?**
  In the 40 officially-keyed questions the correct option is the longest 60% of
  the time; in the 104 derived ones, 33% (Fisher p=0.0042). That is a signal,
  not proof, and re-deriving answers is a Non-Goal here. Option shuffling
  removes the _student's_ exposure to the bias; the standing reason to re-review
  the keys remains, as its own change.
