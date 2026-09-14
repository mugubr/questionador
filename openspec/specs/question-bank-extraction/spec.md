# question-bank-extraction Specification

## Purpose

The Python pipeline that turns the official PROFNIT exam PDFs into a validated,
versioned question bank. It covers the pinned-toolchain text extraction with
`pdftotext -layout`, header and footer removal, the segmentation of questions
and options, the per-paper count assertions that make a silently incomplete
bank impossible, matching against the published answer keys, the flagging of
questions the parser cannot resolve deterministically, the marking of known
duplicates and source defects, and the publication of the bank in a
machine-readable form, a human-reviewable form, and the form the app embeds
directly.

It runs on a developer machine and never in the browser, as an importable
package invoked through `python -m tools <extract|build|validate>`. Provenance
is part of the contract: every answer is backed by a published answer key, and
the schema and the validator are required to agree on every rule.

## Requirements

### Requirement: Pipeline command-line interface

The pipeline SHALL be an importable Python package invoked as `python -m tools <extract|build|validate>`, and no module SHALL manipulate `sys.path` to import a sibling.

#### Scenario: Subcommands available

- **WHEN** `python -m tools --help` is run from the repository root
- **THEN** it lists the subcommands `extract`, `build` and `validate`

#### Scenario: Unknown subcommand

- **WHEN** an unrecognised subcommand is given
- **THEN** the CLI exits with a non-zero status and the usage message

#### Scenario: Importable package

- **WHEN** the test suite imports `tools.extract`, `tools.build` and `tools.validate`
- **THEN** the imports succeed with no `sys.path` manipulation anywhere in the package or in the tests

#### Scenario: Shared cleanup patterns have one home

- **WHEN** extraction and validation both need a noise pattern
- **THEN** both import it from `tools.text_cleanup`, so the pattern cannot drift between them

### Requirement: Pinned and recorded PDF toolchain

The pipeline SHALL require poppler's `pdftotext`, SHALL verify it before doing any work, and SHALL record the verified version in the published bank as `toolchain.pdftotext`.

#### Scenario: Toolchain verified before any work

- **WHEN** `python -m tools extract` starts
- **THEN** it resolves `pdftotext` with `shutil.which`, reads its version, and only then begins reading PDFs

#### Scenario: Xpdf found instead of poppler

- **WHEN** the resolved `pdftotext` reports Xpdf, as shipped by Git for Windows
- **THEN** the pipeline aborts naming the executable it found, the version it reported and poppler as the required implementation
- **AND** no artifact is written

#### Scenario: pdftotext absent

- **WHEN** no `pdftotext` is on `PATH`
- **THEN** the pipeline aborts with an error saying how to install poppler

#### Scenario: Version recorded in the output

- **WHEN** the bank is generated
- **THEN** `toolchain.pdftotext` holds the version string that was verified at startup

#### Scenario: UTF-8 extraction

- **WHEN** a PDF is read
- **THEN** the invocation is `pdftotext -layout -enc UTF-8` and the subprocess is decoded as UTF-8

### Requirement: Text extraction from the question papers

The pipeline SHALL extract the text of the 7 question papers in `exams/` using `pdftotext -layout`, preserving the order and the indentation that the subsequent parsing needs.

#### Scenario: Extraction of every paper

- **WHEN** `python -m tools extract` is run over `exams/`
- **THEN** it produces the extracted text for each of the 7 papers (`Prova_ENA18`, `Prova_ENA25`, `Prova_ENA26`, `PROFNIT-AV2-PI`, `PROFNIT-AV2-MET`, `PROFNIT-AV2-POL`, `PROFNIT-AV2-201024-PROSP`)
- **AND** the 7 answer-key files are processed separately, not as question papers

#### Scenario: PDF with no text layer

- **WHEN** `pdftotext` returns fewer than 10 lines for an exam PDF
- **THEN** the script aborts with an error identifying the file, instead of generating empty questions

#### Scenario: Output written before the run can fail on console encoding

- **WHEN** extraction finishes on a Windows console
- **THEN** `data/raw-questions.json` is written and the process exits successfully, with no `UnicodeEncodeError` discarding the work

### Requirement: Versioned extraction anchor

The pipeline SHALL write the deterministic output of `extract` to `data/raw-questions.json`, and that file SHALL be committed so that `build` and `validate` can run without `pdftotext`.

#### Scenario: Extract writes the anchor

- **WHEN** `python -m tools extract` completes
- **THEN** `data/raw-questions.json` holds every extracted question with its exam, number, stem, options and parse status

#### Scenario: Build without poppler

- **WHEN** `python -m tools build` runs on a machine with no `pdftotext`
- **THEN** it builds the bank from `data/raw-questions.json` and the data layers, and succeeds

#### Scenario: Re-extraction is reviewable

- **WHEN** `extract` is re-run on unchanged PDFs with the same pinned toolchain
- **THEN** `data/raw-questions.json` is byte-identical and the working tree stays clean

### Requirement: Header and footer removal

The parser SHALL remove page headers and footers before segmenting the questions, so that stems cut by a page break are reassembled correctly, and the residue checks SHALL cover the options as well as the stems.

#### Scenario: Footer in the middle of a stem

- **WHEN** the footer `18 de novembro de 2023   PI   Página 7 de 8` appears between the stem and the options of question 16 of `PROFNIT-AV2-PI`
- **THEN** the extracted question contains the complete stem followed by the 4 options
- **AND** the footer text does not appear in any field of the question

#### Scenario: Institutional header of ENA18

- **WHEN** the lines `Associação Fórum Nacional de Gestores…`, `Programa de Pós-Graduação em…` and `PROFNIT` appear at the top of every page of `Prova_ENA18`
- **THEN** those lines are removed before the segmentation

#### Scenario: Footer residue detected inside an option

- **WHEN** the text of any option contains `Página \d+ de \d+` or `Pg\. \d+/\d+`
- **THEN** validation fails identifying the question and the option letter
- **AND** the question is not published with `parseStatus: "ok"`

#### Scenario: Footer residue detected inside a stem

- **WHEN** the text of any stem contains `Página \d+ de \d+` or `Pg\. \d+/\d+`
- **THEN** validation fails identifying the affected question

### Requirement: Segmentation of questions and options

The parser SHALL recognise the two question markers present in the collection and extract exactly 4 options labelled `a` to `d` per question.

#### Scenario: Upper-case marker

- **WHEN** the parser finds a line `QUESTÃO 01` or `QUESTÃO 01.`
- **THEN** it starts a new question with number 1

#### Scenario: Mixed-case marker

- **WHEN** the parser finds a line `Questão 01`
- **THEN** it starts a new question with number 1

#### Scenario: Stem with a block of Roman-numbered assertions

- **WHEN** the stem contains assertions numbered `I.`, `II.`, `III.`, `IV.`
- **THEN** the block is preserved in full in the stem field, with the line breaks kept
- **AND** the Roman assertions are not confused with options

#### Scenario: Question glued by a page break

- **WHEN** the marker `Questão 04` appears immediately after the last option of question 03 in `Prova_ENA26`, with no blank line
- **THEN** the two questions are segmented separately

### Requirement: Per-paper count assertion

The parser SHALL fail when the extracted count diverges from the expected one, instead of emitting an incomplete bank.

#### Scenario: Correct count

- **WHEN** the extraction finishes
- **THEN** the total is 144 questions, distributed as ENA18=40, ENA25=20, ENA26=20 and 16 for each of the 4 AV2 papers

#### Scenario: Divergent count

- **WHEN** a paper produces a number of questions different from the expected one
- **THEN** the script fails reporting the paper, the expected count and the obtained count

#### Scenario: Question with the wrong number of options

- **WHEN** an extracted question does not have exactly 4 options `a`–`d`
- **THEN** the script fails reporting the identifier of the question

### Requirement: Matching against the official answer keys

Every one of the 7 papers has a published official answer key, recovered from `profnit.org.br`, and the pipeline SHALL match every question against its paper's key by question number.

#### Scenario: Matching by number

- **WHEN** the answer key `Gabarito-Final_ENA26` states `1 → B`
- **THEN** question `ENA26-Q01` receives `answer.letter: "b"` and `answer.source: "official"`

#### Scenario: Incomplete answer key

- **WHEN** an answer key does not provide every expected answer for its paper
- **THEN** the script fails instead of silently leaving questions without an answer

#### Scenario: An official answer needs no rationale

- **WHEN** a question has `answer.source: "official"`
- **THEN** the fields `confidence` and `rationale` are omitted

#### Scenario: A withdrawn question has no letter

- **WHEN** the official key prints `ANULADA` in place of a letter
- **THEN** the question carries `excludedReason: "annulled"` and no `answer.letter`, instead of a fabricated one

#### Scenario: Booklet identity verified before trusting a key

- **WHEN** a key is adopted for a paper
- **THEN** the published booklet's MD5 is checked against the committed PDF in `exams/`, and the key's own text is checked for whether it names the booklet as published — both together are what makes matching by question number valid

### Requirement: Derivation as a still-supported, currently-unused path

The schema, the validator and the models SHALL keep supporting a `derived` answer — one recorded without a published key, carrying its own confidence level, consulted reference and rationale — for a future paper that may arrive without one, even though every answer in the bank today is `official`.

#### Scenario: Derived shape when it is needed

- **WHEN** a question's `answer.source` is `"derived"`
- **THEN** `answer.confidence` is `"high"`, `"medium"` or `"low"`
- **AND** `answer.reference` cites the source that was actually consulted — a file from `references/` when the content is covered by it, or the applicable norm, law or bibliography when it is not
- **AND** `answer.rationale` is a non-empty Portuguese text explaining the choice, and `explanation` is absent

#### Scenario: Nothing in the published bank is derived

- **WHEN** `python -m tools validate` runs against the committed bank
- **THEN** all 144 answers report `source: "official"` and zero report `source: "derived"`

#### Scenario: Content outside the reach of references/

- **WHEN** an official answer's explanation deals with a subject not covered by the PDFs in `references/` — such as the ABNT norms, the CAPES Qualis and the research typology examined in `PROFNIT-AV2-MET`
- **THEN** `answer.reference` names the real source (norm, law or bibliography of the discipline)
- **AND** no citation to `references/` is fabricated to satisfy the format

### Requirement: Flagging of questions that require manual review

The parser SHALL flag questions whose structure could not be resolved deterministically, instead of applying guessing heuristics, and the column-layout detection SHALL cover the options as well as the stem.

#### Scenario: Two-column matching question

- **WHEN** the parser finds a question whose text has side-by-side columns, such as question 14 of `Prova_ENA25` (`Coluna 1` × `Coluna 2`)
- **THEN** the question is flagged with `parseStatus: "needs-review"`
- **AND** the extraction report lists every question flagged for review

#### Scenario: Two-column layout inside an option

- **WHEN** side-by-side columns appear inside an option rather than in the stem, as in `ENA25-Q09`
- **THEN** the question is flagged with `parseStatus: "needs-review"` instead of being published as resolved

#### Scenario: Review completed

- **WHEN** a flagged question is rewritten as linear text in `data/overrides.json`
- **THEN** its `parseStatus` becomes `"ok"`
- **AND** validation requires that no published question remains in `"needs-review"`

### Requirement: Marking of duplicate questions and source defects

The pipeline SHALL record known repeats with `duplicateOf` and known defects of the source exam papers with `knownDefects`, reproducing the source faithfully instead of silently fixing it.

#### Scenario: Repeated questions marked

- **WHEN** the bank is built from `AV2-PI`, whose Q14 repeats Q13 with corrupted assertion numbering and whose Q16 is identical to Q15
- **THEN** both repeats carry `duplicateOf` pointing at the question they repeat
- **AND** the 16 numbered items are all published

#### Scenario: Duplicate target validated

- **WHEN** a question carries `duplicateOf`
- **THEN** validation requires the target to exist and to not itself be a duplicate

#### Scenario: Identical options recorded

- **WHEN** `AV2-MET-Q14` is built, whose options `a` and `d` are the same string in the original PDF
- **THEN** the question carries `identical-options` in `knownDefects`
- **AND** both options are published exactly as they appear in the PDF

#### Scenario: A defect that is not a duplicate is still recorded

- **WHEN** a question's own text cites an item its stem never lists, as `AV2-MET-Q08`'s option `d` cites a nonexistent item "V"
- **THEN** the question carries a defect naming what is wrong in `knownDefects`, without being excluded or re-keyed

#### Scenario: A booklet defect excludes rather than re-keys

- **WHEN** the printed booklet reprints an earlier question at a later number, as `AV2-PI` does at 14 and 16
- **THEN** the reprint carries `excludedReason: "source-booklet-defect"` and `duplicateOf`, and the official key's letter for that number is never attached to the reprinted text

### Requirement: Deterministic, byte-identical artifacts

Every artifact the pipeline writes SHALL be identical byte for byte when regenerated from the same inputs on any platform.

#### Scenario: LF on every platform

- **WHEN** any artifact is written
- **THEN** it is opened with `newline="\n"` and contains no CR byte, on Windows as on Linux

#### Scenario: Rebuild produces no diff

- **WHEN** `python -m tools build` is re-run with unchanged inputs
- **THEN** `git status` reports a clean working tree

#### Scenario: Sorted iteration

- **WHEN** the pipeline iterates a set, a dict or a glob to produce output
- **THEN** the iteration is sorted, so the ordering does not depend on the filesystem or on hash seeding

#### Scenario: Console output survives a cp1252 terminal

- **WHEN** the pipeline runs on a Windows console whose default encoding is cp1252
- **THEN** it reconfigures `stdout` to UTF-8 at entry, prints only ASCII progress output, and completes without `UnicodeEncodeError`

#### Scenario: generatedAt carries forward

- **WHEN** `build` runs with no `--generated-at` argument
- **THEN** the published bank's `generatedAt` is copied from the bank already committed, not from today's date, so an unchanged rebuild produces unchanged bytes

### Requirement: No orphan keys in the data layers

A key in `data/overrides.json`, `data/topics.json` or `data/answers/*.json` that matches no question, or a question in `tools/config.py`'s duplicate/defect/exclusion maps that matches no question, SHALL be an error, not a silent no-op.

#### Scenario: Orphan override

- **WHEN** `data/overrides.json` contains an entry whose question id is not in the extracted set
- **THEN** the build fails naming the file and the orphan id

#### Scenario: Orphan derived answer

- **WHEN** `data/answers/<exam>.json` contains an answer for a question id that does not exist
- **THEN** the build fails naming the file and the orphan id

#### Scenario: Every error reported in one run

- **WHEN** several layers contain orphan keys at once
- **THEN** the build reports all of them in a single run, instead of stopping at the first

#### Scenario: Every override records its reason

- **WHEN** an entry is added to `data/overrides.json`
- **THEN** it carries a non-empty reason, and the build fails if it does not

### Requirement: English question bank contract

The published bank SHALL use English field names and English enum values for everything the code branches on, and SHALL keep in Portuguese every value a student reads.

#### Scenario: English field names

- **WHEN** the bank is generated
- **THEN** its fields are `version`, `generatedAt`, `toolchain`, `exams`, `questions`, and each question carries `id`, `exam`, `number`, `topic`, `stem`, `options`, `answer`
- **AND** the answer carries `letter`, `source`, and for a derived answer `confidence`, `reference` and `rationale`

#### Scenario: English enum values

- **WHEN** an answer is written
- **THEN** `source` is `official` or `derived`
- **AND** `confidence`, when present, is `high`, `medium` or `low`

#### Scenario: Content stays Portuguese

- **WHEN** a question is written
- **THEN** its `stem`, its `options`, its exam `title`, and its `reference` and `rationale` are the Portuguese text
- **AND** `topic` is a Portuguese kebab-case value such as `propriedade-intelectual`

#### Scenario: Identifiers unchanged

- **WHEN** a question is written
- **THEN** its `exam` is the unchanged proper noun such as `ENA26` or `AV2-PI`
- **AND** its `id` is `<exam>-Q<NN>` and equals `f"{exam}-Q{number:02d}"`

#### Scenario: Generation date recorded

- **WHEN** the bank is generated
- **THEN** `generatedAt` holds the build date and is the only timestamp in the artifact

#### Scenario: Schema and validator agree

- **WHEN** `python -m tools validate` runs
- **THEN** it enforces the same rules `data/schema.json` declares, and a rule present in only one of the two is reported as a defect

### Requirement: Publication in two formats

The pipeline SHALL publish the bank in `data/question-bank.json` for consumption by the app and in `data/question-bank.md` for human reading and review.

#### Scenario: JSON validated against the schema

- **WHEN** `data/question-bank.json` is generated
- **THEN** it validates against `data/schema.json`
- **AND** it contains `version`, `generatedAt`, `toolchain`, the list of `exams` and the 144 `questions`

#### Scenario: Review markdown

- **WHEN** `data/question-bank.md` is generated
- **THEN** every question appears with its exam, number, stem, the 4 options, the answer, the provenance and — when derived — the reference and the rationale

#### Scenario: Manual correction of a derived answer

- **WHEN** the reviewer corrects the letter of a derived answer in `data/answers/<exam>.json` and re-runs `build`
- **THEN** the correction reaches both artifacts with no change to the app code

### Requirement: Embedded bank artifact for the app

The pipeline SHALL write `docs/data/question-bank.js`, which assigns `window.QUESTION_BANK` the same bank object that is written to `data/question-bank.json`.

#### Scenario: Both artifacts from one build

- **WHEN** `python -m tools build` completes
- **THEN** `data/question-bank.json` and `docs/data/question-bank.js` are written from the same in-memory bank in the same run

#### Scenario: Embedded payload matches the JSON

- **WHEN** the assignment in `docs/data/question-bank.js` is parsed
- **THEN** it is deeply equal to the contents of `data/question-bank.json`

#### Scenario: Payload cannot break out of the script tag

- **WHEN** the serialized bank contains the sequence `</`
- **THEN** it is escaped in the emitted JavaScript, so the payload cannot close the enclosing `<script>` tag
