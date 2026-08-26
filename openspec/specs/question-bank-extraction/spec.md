# question-bank-extraction Specification

## Purpose

The Python pipeline that turns the official PROFNIT exam PDFs into a validated,
versioned question bank. It covers text extraction with `pdftotext -layout`,
header and footer removal, the segmentation of questions and options, the
per-paper count assertions that make a silently incomplete bank impossible,
matching against the two published answer keys, the derivation and labelling of
the 104 answers that have no published key, the flagging of questions the parser
cannot resolve deterministically, and the publication of the bank in both a
machine-readable and a human-reviewable form.

It runs on a developer machine and never in the browser. Provenance is part of
the contract: an answer is either backed by a published answer key or recorded
as derived, with its reference, its rationale and a confidence level.

## Requirements

### Requirement: Text extraction from the question papers

The pipeline SHALL extract the text of the 7 question papers in `Provas/` using `pdftotext -layout`, preserving the order and the indentation that the subsequent parsing needs.

#### Scenario: Extraction of every paper

- **WHEN** the extraction script is run over `Provas/`
- **THEN** it produces one text file for each of the 7 papers (`Prova_ENA18`, `Prova_ENA25`, `Prova_ENA26`, `PROFNIT-AV2-PI`, `PROFNIT-AV2-MET`, `PROFNIT-AV2-POL`, `PROFNIT-AV2-201024-PROSP`)
- **AND** the 2 answer-key files are processed separately, not as question papers

#### Scenario: PDF with no text layer

- **WHEN** `pdftotext` returns fewer than 10 lines for an exam PDF
- **THEN** the script aborts with an error identifying the file, instead of generating empty questions

### Requirement: Header and footer removal

The parser SHALL remove page headers and footers before segmenting the questions, so that stems cut by a page break are reassembled correctly.

#### Scenario: Footer in the middle of a stem

- **WHEN** the footer `18 de novembro de 2023   PI   Página 7 de 8` appears between the stem and the options of question 16 of `PROFNIT-AV2-PI`
- **THEN** the extracted question contains the complete stem followed by the 4 options
- **AND** the footer text does not appear in any field of the question

#### Scenario: Institutional header of ENA18

- **WHEN** the lines `Associação Fórum Nacional de Gestores…`, `Programa de Pós-Graduação em…` and `PROFNIT` appear at the top of every page of `Prova_ENA18`
- **THEN** those lines are removed before the segmentation

#### Scenario: Footer residue detected during validation

- **WHEN** the text of any extracted question contains `Página \d+ de \d+` or `Pg\. \d+/\d+`
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

### Requirement: Matching against the official answer key

The pipeline SHALL match the questions of ENA25 and ENA26 against the corresponding official answer keys, by question number.

#### Scenario: Matching by number

- **WHEN** the answer key `Gabarito-Final_ENA26` states `1 → B`
- **THEN** question `ENA26-Q01` receives `resposta.letra: "b"` and `resposta.procedencia: "oficial"`

#### Scenario: Incomplete answer key

- **WHEN** an answer key does not provide the 20 expected answers
- **THEN** the script fails instead of silently leaving questions without an answer

#### Scenario: An official answer needs no rationale

- **WHEN** a question has `procedencia: "oficial"`
- **THEN** the fields `confianca` and `justificativa` are omitted

### Requirement: Derivation and labelling of the answers with no official key

For the 104 questions with no published answer key, the pipeline SHALL record the derived answer together with its provenance, confidence level, consulted reference and rationale.

#### Scenario: Complete derived question

- **WHEN** a question from `Prova_ENA18` or from an AV2 paper receives an answer
- **THEN** `resposta.procedencia` is `"derivada"`
- **AND** `resposta.confianca` is `"alta"`, `"media"` or `"baixa"`
- **AND** `resposta.referencia` cites the source that was actually consulted — a file from `Materiais/` when the content is covered by it, or the applicable norm, law or bibliography when it is not
- **AND** `resposta.justificativa` is a non-empty text explaining the choice

#### Scenario: Content outside the reach of Materiais/

- **WHEN** the question deals with a subject not covered by the PDFs in `Materiais/` — such as the ABNT norms, the CAPES Qualis and the research typology examined in `PROFNIT-AV2-MET`
- **THEN** `resposta.referencia` names the real source (norm, law or bibliography of the discipline)
- **AND** no citation to `Materiais/` is fabricated to satisfy the format

#### Scenario: Stem that cites the reference

- **WHEN** the stem explicitly cites a material (e.g. "De acordo com o material _Criando uma marca_ (OMPI)")
- **THEN** `resposta.referencia` points to the corresponding file in `Materiais/`

#### Scenario: Underivable answer

- **WHEN** the reference material does not support a single option with confidence
- **THEN** the question receives `confianca: "baixa"` and stays in the bank, instead of being removed

### Requirement: Flagging of questions that require manual review

The parser SHALL flag questions whose structure could not be resolved deterministically, instead of applying guessing heuristics.

#### Scenario: Two-column matching question

- **WHEN** the parser finds question 14 of `Prova_ENA25`, whose text has side-by-side columns (`Coluna 1` × `Coluna 2`)
- **THEN** the question is flagged with `parse_status: "revisar"`
- **AND** the extraction report lists every question flagged for review

#### Scenario: Review completed

- **WHEN** a flagged question is manually rewritten as linear text
- **THEN** its `parse_status` becomes `"ok"`
- **AND** validation requires that no published question remains in `"revisar"`

### Requirement: Publication in two formats

The pipeline SHALL publish the bank in `data/questions.json` for consumption by the app and in `data/questoes.md` for human reading and review.

#### Scenario: JSON validated against the schema

- **WHEN** `data/questions.json` is generated
- **THEN** it validates against `data/schema.json`
- **AND** it contains `versao`, the list of `provas` and the 144 `questoes`

#### Scenario: Review markdown

- **WHEN** `data/questoes.md` is generated
- **THEN** every question appears with its paper, number, stem, the 4 options, the answer, the provenance and — when derived — the reference and the rationale

#### Scenario: Manual correction of a derived answer

- **WHEN** the reviewer corrects the letter of a derived answer
- **THEN** the correction is made in the data files, with no change to the app code
