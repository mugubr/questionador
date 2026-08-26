## Why

The app works, but only for someone who has already cloned the repository: the
question bank arrives by hand, uploaded as a JSON file, and the site is not
published anywhere. A student who is told "use this to study" has nothing to
open. At the same time the codebase is half Portuguese and half English —
directory names, JSON keys, enum values, identifiers — so every new file forces
a fresh guess about which language a name belongs to, and the boundary between
"code" and "content" is invisible.

Underneath that, a set of confirmed defects makes the current state hard to
defend: extraction dies with `UnicodeEncodeError` on Windows _after_ doing all
the work and before writing its output; 13 questions ship with page footers
inside their options while reporting `parseStatus: "ok"`; `ENA25-Q14` was fixed
by hand but `ENA25-Q09` shipped with its two-column matching table unresolved;
the session is written to `localStorage` on every answer and never read back;
answering scrolls the page to the top and loses focus; the layout overflows
horizontally by 102px at 320px; several colour pairs fail WCAG AA in both
themes; option state is conveyed by colour alone; `Enter` hijacks whichever
button has focus; and the final review discards the rationale that is the only
evidence behind 104 of the 144 answer keys.

## What Changes

**Publishing**

- **BREAKING** — the bank is no longer uploaded. It ships embedded as
  `docs/data/question-bank.js`, which assigns `window.QUESTION_BANK` and is
  loaded by a plain `<script>` tag. The site opens already loaded, with no
  `fetch`, so it behaves identically over `https://` and `file://`. Upload
  survives only as a secondary affordance for trying a hand-edited bank.
- GitHub Pages publishes from `docs/`, which contains the app and nothing else
  (~250 KB). `exams/` and `references/` stay in the repository but off the
  public site — roughly 50 MB of third-party reference PDFs and official exam
  papers.
- Pages only publishes after CI is green.

**Language**

- **BREAKING** — every JSON field name and every enum value the code branches on
  becomes English: `questoes`→`questions`, `enunciado`→`stem`,
  `alternativas`→`options`, `resposta`→`answer`, `procedencia`→`source`,
  `confianca`→`confidence`, `justificativa`→`rationale`, and so on;
  `oficial`/`derivada`→`official`/`derived` and
  `alta`/`media`/`baixa`→`high`/`medium`/`low`. Any bank produced before this
  change stops loading.
- All content stays Portuguese, including every rendered string and the `topic`
  values, which are displayed as labels.
- Directory and file renames, already applied with `git mv`: `Provas/`→`exams/`,
  `Materiais/`→`references/`, `scripts/`→`tools/`, `data/respostas/`→
  `data/answers/`, `correcoes.json`→`overrides.json`, `temas-oficiais.json`→
  `official-topics.json`, `questions.json`→`question-bank.json`,
  `questoes.md`→`question-bank.md`, `index.html`→`docs/index.html`,
  `styles.css`→`docs/assets/css/styles.css`, `js/`→`docs/assets/js/`.

**Data contract**

- **BREAKING** — new required provenance fields `generatedAt` and `toolchain`;
  new optional `duplicateOf` and `knownDefects`.
- `data/raw-questions.json` becomes a committed artifact: the extraction anchor,
  so the chain can be rebuilt and diffed without running `pdftotext`.

**Pipeline**

- `scripts/` becomes a real Python package `tools/` with a
  `python -m tools <extract|build|validate>` CLI, ending the `sys.path.insert`
  hack.
- `pdftotext` is pinned to poppler, checked at startup and recorded in the
  output. Git for Windows ships Xpdf 4.00 under the same name; it emits Latin-1
  and different dash characters and silently produces a different bank.
- Noise, column-layout and residue checks now cover options as well as stems.
- Every artifact is written with `newline="\n"`, so a rebuild is byte-identical
  across platforms.
- An orphan key in `overrides.json`, `official-topics.json` or `answers/*.json`
  is an error, not a silent no-op.
- Console output is ASCII only and `stdout` is reconfigured to UTF-8 at entry,
  which is what kills the `UnicodeEncodeError`.

**App**

- Classic scripts, modernized: `const`/`let`, arrow functions, template
  literals, one namespace object per file. Not ES modules — they cannot load
  over `file://`. No bundler, no build step.
- New: resume an interrupted session, shuffle the options, configurable session
  size, cross-session history with "only the ones I got wrong" and "never
  answered" filters, and known duplicates excluded from the draw by default.
- Light/dark/system theming applied before first paint, and WCAG 2.2 level AA
  as the floor, verified in both themes.
- The final review keeps the rationale and the reference.

**Testing**

- `pytest` for the pipeline, `node:test` for the app's pure logic, plus a golden
  test that validates the committed bank on every run. CI runs lint, type-check
  and both suites.

**What stays working**

- Every question, option, answer, reference and rationale — the content itself
  is unchanged apart from the 13 footer-contaminated options and `ENA25-Q09`,
  which get fixed.
- Filters by exam paper, topic and provenance; the draw without repetition;
  immediate grading; the derived-answer badge and its confidence level; the
  session score; keyboard answering.
- Opening `docs/index.html` over `file://` with no server.
- The 144/40/104 split and the rule that a derived answer is never promoted to
  official.

## Capabilities

### New Capabilities

- `static-site-publishing`: how the app reaches a student — GitHub Pages served
  from `docs/`, the exclusion of `exams/` and `references/` from the published
  surface, the freshness relationship between `docs/data/question-bank.js` and
  `data/question-bank.json`, the no-external-request guarantee, and the CI gate
  that must pass before a deployment happens.

### Modified Capabilities

- `quiz-runner`: **BREAKING**. Upload-based loading is replaced by automatic
  loading of an embedded bank; bank-and-progress persistence changes because the
  bank is no longer cached in `localStorage` while the session now genuinely
  resumes; validation, grading, the derived badge and the review surface all
  move to the English field names. New requirements for theming, option
  shuffling, session size, cross-session history, duplicate exclusion and WCAG
  2.2 AA conformance.
- `question-bank-extraction`: the published contract is renamed to English and
  gains provenance fields; the toolchain is pinned and recorded; noise,
  column-layout and residue checks cover options as well as stems; artifacts are
  written LF so rebuilds are byte-identical across platforms; orphan keys in the
  override layers are errors; the pipeline is invoked as
  `python -m tools <extract|build|validate>`.

## Impact

- **Code**: every file in `tools/` and `docs/assets/js/`, plus
  `docs/index.html` and `docs/assets/css/styles.css`. New `tools/__main__.py`,
  `tools/config.py`, `tools/models.py`, `tools/text_cleanup.py`, and
  `docs/assets/js/types.js` for the shared `@typedef` shapes.
- **Data**: `data/schema.json`, `data/question-bank.json`,
  `data/question-bank.md`, `data/overrides.json`, `data/official-topics.json`
  and `data/answers/*.json` are all rewritten to the English contract;
  `data/raw-questions.json` and `docs/data/question-bank.js` are new committed
  artifacts.
- **Consumers**: any bank file produced before this change, and any bookmark or
  script that reads the Portuguese keys. There is no compatibility shim — the
  bank ships with the app, so there is exactly one producer and one consumer and
  they are updated in the same commit.
- **Tooling**: `pyproject.toml` (package metadata, `ruff`, `mypy` strict,
  `pytest`), `jsconfig.json` (type-checking the JavaScript from JSDoc),
  `.gitattributes` (LF for every generated artifact), `.github/workflows/` for
  CI and the Pages deployment, and a documented dependency on poppler's
  `pdftotext` at a pinned version.
- **Repository**: `docs/` becomes the published root and needs `.nojekyll`.
  `exams/` and `references/` remain read-only sources, tracked but never
  published.
- **Out of scope**: any backend, user accounts, cross-device sync, editing
  questions inside the app, and translating the interface — the audience is
  Brazilian students.
