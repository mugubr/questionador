Each `##` group lands as one commit. A task is done when the command next to it
passes or the stated outcome is observable.

## 1. Rules, renames and OpenSpec

- [x] 1.1 Write `AGENTS.md` as the single source of truth: language policy, documentation rules, layout, bank contract, pipeline rules, app constraints, testing and working agreements
- [x] 1.2 Reduce `CLAUDE.md` to a pointer at `AGENTS.md`
- [x] 1.3 Apply the directory renames with `git mv` so history follows: `Provas/`→`exams/`, `Materiais/`→`references/`, `scripts/`→`tools/`, `data/respostas/`→`data/answers/`, `correcoes.json`→`overrides.json`, `temas-oficiais.json`→`official-topics.json`, `questions.json`→`question-bank.json`, `questoes.md`→`question-bank.md` — verify with `git log --follow` on one moved file
- [x] 1.4 Move the app under the publishing root: `index.html`→`docs/index.html`, `styles.css`→`docs/assets/css/styles.css`, `js/`→`docs/assets/js/`
- [x] 1.5 Rewrite the archived specs in English and give each a real Purpose; `openspec validate --specs` passes
- [x] 1.6 Write `proposal.md`, `design.md`, the three spec deltas and `tasks.md` for this change; `openspec validate english-refactor-and-pages --strict` passes

## 2. Python pipeline package

- [ ] 2.1 Add `pyproject.toml` with the package metadata and the `ruff`, `mypy` (strict) and `pytest` configuration; `python -c "import tomllib,pathlib;tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` succeeds
- [ ] 2.2 Create `tools/__init__.py` and `tools/__main__.py` with the `extract | build | validate` subcommands; `python -m tools --help` lists all three and an unknown subcommand exits non-zero
- [ ] 2.3 Move the exam registry and the per-paper expected counts into `tools/config.py`, and the dataclasses and enums into `tools/models.py`; nothing else defines them
- [ ] 2.4 Move every noise, footer and column-layout pattern into `tools/text_cleanup.py` and import it from both `extract.py` and `validate.py`; `grep -rn "Página" tools/ | grep -v text_cleanup.py` returns nothing
- [ ] 2.5 Delete every `sys.path.insert` from `tools/` and from `tests/`; `grep -rn "sys.path" tools tests` returns nothing and `python -c "import tools.extract, tools.build, tools.validate"` succeeds
- [ ] 2.6 Add the `pdftotext` startup check: resolve with `shutil.which`, read the version, require poppler, abort naming the executable and the version when Xpdf answers; verify by running with an Xpdf-first `PATH` and observing the abort before any PDF is read
- [ ] 2.7 Invoke `pdftotext -layout -enc UTF-8` with `encoding="utf-8"` on the subprocess everywhere; `grep -rn "pdftotext" tools/` shows no other invocation
- [ ] 2.8 Reconfigure `stdout` to UTF-8 at CLI entry and strip every non-ASCII character from progress output; `chcp 1252 && python -m tools extract` completes and writes its output
- [ ] 2.9 Write every artifact through one helper that opens with `newline="\n"`, and sort every iteration over a set, dict or glob; `grep -rn "open(" tools/ | grep -v newline` returns nothing
- [ ] 2.10 Add full Google-style docstrings and type hints across `tools/`; `ruff check . && ruff format --check . && mypy tools` is clean
- [ ] 2.11 Regenerate the bank in the still-Portuguese format and confirm the restructure changed nothing: the only diff versus the previous artifact is line endings

## 3. Data migration and normalization

- [ ] 3.1 Rewrite `data/schema.json` to the English contract: `version`, `generatedAt`, `toolchain`, `exams[]`, `questions[]` with `stem`, `options`, `answer{letter,source,confidence,reference,rationale}`, plus optional `duplicateOf` and `knownDefects`
- [ ] 3.2 Rewrite `tools/validate.py` to enforce exactly what the schema declares — id/exam/number agreement, per-paper counts, contiguous numbering, `official` without `confidence` or `rationale`, `derived` with all three, no residue, `duplicateOf` target valid
- [ ] 3.3 Migrate `data/overrides.json`, `data/official-topics.json` and `data/answers/*.json` to the English keys and enum values, content untouched; `git diff --stat` shows no change in any Portuguese string
- [ ] 3.4 Commit `data/raw-questions.json` as the extraction anchor and make `build` read it, so `python -m tools build` succeeds on a machine with no `pdftotext`
- [ ] 3.5 Turn on the option-level residue check and fix the 13 questions carrying page footers inside their options; `python -m tools validate` reports zero residues and none of the 13 is published as `parseStatus: "ok"` with a footer
- [ ] 3.6 Extend the column-layout detection to the options, so `ENA25-Q09` is flagged, and write its linear rewrite into `data/overrides.json` with its reason
- [ ] 3.7 Make an orphan key in any data layer a hard error that accumulates: add a bogus id to each of the three layers at once and confirm all three are reported in one run
- [ ] 3.8 Set `duplicateOf` on `AV2-PI-Q14` and `AV2-PI-Q16`, and `knownDefects: ["identical-options"]` on `AV2-MET-Q14`; validation confirms each `duplicateOf` target exists and is not itself a duplicate
- [ ] 3.9 Emit `generatedAt` and `toolchain.pdftotext` into the bank, and regenerate `data/question-bank.json` and `data/question-bank.md`; the review markdown still shows answer, provenance, reference and rationale for all 144 questions
- [ ] 3.10 Emit `docs/data/question-bank.js` assigning `window.QUESTION_BANK`, with `</` escaped; a node one-liner that evaluates the file and deep-compares it to `data/question-bank.json` reports equal
- [ ] 3.11 Add `.gitattributes` pinning LF for every generated artifact, then re-run `python -m tools build` twice and confirm `git status` stays clean

## 4. Web app

- [ ] 4.1 Add `docs/.nojekyll`, `docs/assets/icons/favicon.svg`, and `jsconfig.json` with `checkJs` enabled
- [ ] 4.2 Declare `Question`, `Session`, `QuestionBank` and the option/confidence unions once in `docs/assets/js/types.js` with `@typedef`
- [ ] 4.3 Load the bank with a plain `<script src="data/question-bank.js">` before the app scripts, and drop every `fetch`; opening `docs/index.html` over `file://` shows the draw screen with the question count and an empty network panel
- [ ] 4.4 Report a missing or invalid `window.QUESTION_BANK` by naming `docs/data/question-bank.js` and leaving the draw controls disabled; verify by renaming the file
- [ ] 4.5 Rewrite `bank.js` validation against the English contract, including `answer.source` and the derived-answer required fields, and keep the upload path as a session-only override
- [ ] 4.6 Stop caching the bank in `localStorage` and delete any previously cached copy at first start; `grep -rn "localStorage" docs/assets/js/` shows keys for the session, the history and the theme only
- [ ] 4.7 Read the stored session back at startup and offer to resume it, discarding it when the stored bank `version` or `generatedAt` differs; verified by reloading mid-session and by bumping `generatedAt` by hand
- [ ] 4.8 Shuffle the options per question at draw time and resolve the choice against the original letter; the review and the history report bank letters
- [ ] 4.9 Add the configurable session size, truncating the shuffled deck and preselecting the last used size
- [ ] 4.10 Add the cross-session history keyed by question id in a `Map` or `Object.create(null)`, with the "only the ones I got wrong" and "never answered" filters and a clear-history control; a question id of `constructor` behaves like any other
- [ ] 4.11 Exclude `duplicateOf` questions from the draw by default with an opt-in toggle, and surface `knownDefects` on the drawn question; drawing from `AV2-PI` yields 14 questions and says 2 were excluded
- [ ] 4.12 Keep the rationale, the reference and the confidence in the end-of-session review of every derived answer
- [ ] 4.13 Add the theme control with system/light/dark, persisted in `localStorage` and applied by an inline `<head>` script before first paint; reloading in dark shows no white flash
- [ ] 4.14 Rebuild the palette as tokens on `:root`, redefining only what changes under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` and `:root[data-theme="dark"]` from one shared declaration list, and declare `color-scheme`; `grep -nE "#[0-9a-fA-F]{3,8}|rgb\(" docs/assets/css/styles.css` matches only inside the token block
- [ ] 4.15 Fix the contrast failures in both themes; every text pair measures at least 4.5:1 and every large-text and control-boundary pair at least 3:1, checked on computed values
- [ ] 4.16 Give correct and incorrect options a non-colour marker and an accessible name stating the outcome; the state is still readable with colour filtering on
- [ ] 4.17 Fix the 320px reflow by giving the grid items `min-width: 0` (and `overflow-wrap: anywhere` where needed); at a 320px viewport `document.documentElement.scrollWidth` equals `clientWidth`
- [ ] 4.18 Stop the scroll-to-top on answering and move focus to the grading result; the graded option stays in view
- [ ] 4.19 Manage focus on every panel change and never move it into a `display: none` subtree; walking the whole flow with `Tab` alone never loses the focus ring
- [ ] 4.20 Keep exactly one `role="status"` region, always in the DOM, never toggled with `hidden`, carrying complete sentences
- [ ] 4.21 Make the `Enter` shortcut yield to the focused control and never `preventDefault` a key a focused control would handle; `Enter` on the theme button toggles the theme instead of advancing
- [ ] 4.22 Add the real headings that name the current state, `role="progressbar"` with its value attributes, and 44x44 CSS pixel minimums on every interactive control
- [ ] 4.23 Modernize every app file to `const`/`let`, arrow functions and template literals, one namespace object per file; `grep -rn "\bvar\b" docs/assets/js/` returns nothing and no file declares a second global
- [ ] 4.24 Add `// @ts-check` and typed JSDoc to every function in `docs/assets/js/`; `npx tsc -p jsconfig.json --noEmit` is clean
- [ ] 4.25 Confirm every bank string still reaches the DOM through `textContent`; `grep -rn "innerHTML\|insertAdjacentHTML\|document.write" docs/` returns nothing

## 5. Tests and CI

- [ ] 5.1 Add `tests/test_text_cleanup.py` covering the footer, header and column patterns with inline strings, including the AV2-PI footer that splits question 16 mid-stem
- [ ] 5.2 Add a regression test per fixed defect, each failing before its fix: the cp1252 console run, the 13 footer-contaminated options, `ENA25-Q09`'s two-column option, and the orphan-key accumulation
- [ ] 5.3 Add the toolchain-pin tests: an Xpdf version string aborts, a poppler one proceeds, and the version reaches `toolchain.pdftotext`
- [ ] 5.4 Add the determinism test: build twice into a temp tree and assert byte equality, and assert no CR byte in any artifact
- [ ] 5.5 Add the golden test that runs the validator against the committed `data/question-bank.json` and asserts it passes
- [ ] 5.6 Add `tests/js/` with `node:test` coverage of `session.js` and `bank.js`: filtering, duplicate exclusion, shuffling, letter resolution, grading, scoring, session size, resume guard, history filters and bank validation; `node --test tests/js/` is green
- [ ] 5.7 Assert in a test that `session.js` and `bank.js` reference neither `document` nor `localStorage`
- [ ] 5.8 Add `.github/workflows/ci.yml` running `ruff check`, `ruff format --check`, `mypy tools tests`, `python -m pytest`, `node --test tests/js/` and `python -m tools validate` on every push and pull request
- [ ] 5.9 Add the freshness step: CI runs `python -m tools build` and fails when the working tree is dirty afterwards; verify by pushing a stale `docs/data/question-bank.js`
- [ ] 5.10 Confirm the whole suite runs offline with no network and no service: unplug and run every command in section 8 of `AGENTS.md`

## 6. GitHub Pages and README

- [ ] 6.1 Enable Pages on the `docs/` directory of the default branch with no build step, and confirm `docs/` holds only `index.html`, `.nojekyll`, `assets/` and `data/question-bank.js`, under 1 MB total
- [ ] 6.2 Add `.github/workflows/pages.yml` deploying `docs/` only on the default branch and only after the CI job succeeds; a deliberately failing build produces no deployment
- [ ] 6.3 Verify the published site: it opens already loaded, `docs/data/question-bank.js` fetched from the site is byte-identical to the committed file, and the network panel shows no request outside the origin
- [ ] 6.4 Verify no file from `exams/` or `references/` is reachable under the Pages domain
- [ ] 6.5 Play a full session on the published site with the network disconnected after first load; drawing, grading and scoring keep working
- [ ] 6.6 Rewrite `README.md` in Portuguese for students: the published link first, then how to study offline, how the bank is built, and the derived-answer warning with the 40/104 split
- [ ] 6.7 Run the pre-flight from section 10 of `AGENTS.md`: lint, types, both suites, `python -m tools validate`, the app exercised in both themes at 320px and desktop width, and an empty network panel
