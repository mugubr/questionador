# static-site-publishing Specification

## Purpose

Publishing the app at a public URL a student can open with no setup. GitHub
Pages serves `docs/` directly, with no build step between the committed
files and what the browser receives, and no third-party PDF or unpublished
file ever becomes reachable from the published domain. A deployment is a
statement that the committed code passed every check the repository runs on
it, not merely that someone pushed.

## Requirements

### Requirement: Publication from docs/ with GitHub Pages

The site SHALL be published with GitHub Pages from the `docs/` directory of the default branch, and `docs/` SHALL contain only the app.

#### Scenario: Pages source configured

- **WHEN** the repository Pages settings are inspected
- **THEN** the source is the `docs/` directory of the default branch, with no build step configured

#### Scenario: Published page opens ready to use

- **WHEN** a student opens the published URL
- **THEN** the app renders with the question bank already loaded, requiring no upload and no further click

#### Scenario: Jekyll disabled

- **WHEN** the site is deployed
- **THEN** `docs/.nojekyll` is present, so the files are served exactly as committed

#### Scenario: Only the app is published

- **WHEN** the contents of `docs/` are listed
- **THEN** they are `index.html`, `.nojekyll`, `assets/` and `data/question-bank.js`, and nothing else
- **AND** the whole directory is under 1 MB

### Requirement: Source material excluded from the published site

The exam PDFs in `exams/` and the reference PDFs in `references/` SHALL remain tracked in the repository and SHALL NOT be reachable from the published site.

#### Scenario: Third-party PDFs stay off the site

- **WHEN** the deployed site is inspected
- **THEN** no file from `exams/` or `references/` is served under the Pages domain

#### Scenario: Sources still available to the pipeline

- **WHEN** a developer clones the repository
- **THEN** `exams/` and `references/` are present and read-only inputs to the pipeline

#### Scenario: Publishing root cannot drift

- **WHEN** a file is added anywhere outside `docs/`
- **THEN** it does not become publicly served, because the Pages source is `docs/` and not the repository root

### Requirement: Published bank matches the committed bank

The bank served by the site SHALL be the bank produced by the pipeline from the committed data, verified on every CI run.

#### Scenario: Freshness verified in CI

- **WHEN** CI runs `python -m tools build`
- **THEN** the working tree stays clean afterwards
- **AND** a dirty tree fails the job, because `docs/data/question-bank.js` or `data/question-bank.json` is stale

#### Scenario: Bank validated in CI

- **WHEN** CI runs `python -m tools validate`
- **THEN** the committed bank passes the contract in `data/schema.json`

#### Scenario: Deployed payload matches the repository

- **WHEN** `docs/data/question-bank.js` is fetched from the published site
- **THEN** it is byte-identical to the committed file

### Requirement: No external request at runtime

The published site SHALL serve every byte it needs from its own origin and SHALL make no request to any third party.

#### Scenario: Network panel stays empty

- **WHEN** the published page is loaded and a full session is played through
- **THEN** the only requests are for documents and assets under `docs/`, and no request leaves the origin

#### Scenario: No CDN or webfont host

- **WHEN** the published HTML and CSS are inspected
- **THEN** no `<script src>`, `<link href>`, `@import` or `url()` points outside `docs/`
- **AND** typography relies on system font stacks

#### Scenario: Site works offline after first load

- **WHEN** the page is loaded and the network is then disconnected
- **THEN** the app continues to draw, grade and score questions

### Requirement: Deployment gated on a green build

A deployment SHALL happen only after the continuous integration job has passed on the commit being deployed, or through a maintainer's explicit manual override.

#### Scenario: CI runs the full gate

- **WHEN** a push or a pull request reaches the repository
- **THEN** CI runs `ruff check`, `ruff format --check`, `prettier --check`, `mypy`, `python -m pytest`, `node --test`, the JavaScript type-check and `python -m tools validate`, and the rebuild guard that fails if building the bank again changes a committed artifact

#### Scenario: Red build does not publish

- **WHEN** any check in the CI job fails on the default branch
- **THEN** no deployment runs and the previously deployed site stays in place

#### Scenario: Green build publishes

- **WHEN** every check in the CI job passes on the default branch
- **THEN** the Pages deployment runs and serves the `docs/` directory of that commit

#### Scenario: Pull request checked without deploying

- **WHEN** the CI job passes on a pull request
- **THEN** no deployment happens, because only the default branch publishes

#### Scenario: Manual dispatch bypasses the gate, visibly

- **WHEN** a maintainer triggers the deploy workflow by hand
- **THEN** the deployment runs without waiting for or checking CI's conclusion on that ref
- **AND** the run log carries an explicit warning that the CI gate was skipped
