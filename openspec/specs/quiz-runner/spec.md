# quiz-runner Specification

## Purpose

The static web app a student actually uses. It takes a validated question bank,
draws questions according to the chosen filters, collects one answer per
question and grades it immediately, shows the rationale and the reference behind
each answer key, flags every derived answer so it is never mistaken for an
official one, and keeps the score and the progress of the session.

It is plain HTML, CSS and JavaScript with no build step, no framework and no
network request at runtime, so it works when `index.html` is opened straight
from disk over `file://`. Every string that comes from the bank reaches the DOM
through `textContent`, and the bank is validated before it is used.

## Requirements

### Requirement: Bank loading by file upload

The app SHALL receive the question bank through a JSON file uploaded by the user, without making any network request, so that it works when `index.html` is opened directly in the browser.

#### Scenario: Upload through the file picker

- **WHEN** the user selects a valid JSON file in the file picker
- **THEN** the bank is loaded and the draw screen becomes available
- **AND** the app displays the total number of loaded questions

#### Scenario: Upload by drag and drop

- **WHEN** the user drags a valid JSON file onto the upload area
- **THEN** the behaviour is identical to the file picker

#### Scenario: Running without an HTTP server

- **WHEN** `index.html` is opened over `file://`
- **THEN** the app loads and operates normally, with no CORS error

### Requirement: Validation of the received bank

The app SHALL validate the uploaded file before using it and SHALL display a readable error without discarding a previously loaded bank.

#### Scenario: Malformed JSON

- **WHEN** the uploaded file is not valid JSON
- **THEN** the app displays an error message identifying the problem
- **AND** the previously loaded bank stays active

#### Scenario: Invalid schema

- **WHEN** the JSON does not contain `versao` and a non-empty `questoes` list
- **THEN** the app rejects the file with a message explaining the missing field

#### Scenario: Question with an invalid answer

- **WHEN** some question has `resposta.letra` outside `a`–`d` or does not have the 4 options
- **THEN** the app rejects the bank identifying the invalid question

#### Scenario: Hostile textual content

- **WHEN** the text of a question contains HTML markup
- **THEN** it is rendered as literal text through `textContent`, with no HTML interpretation

### Requirement: Persistence of the bank and of the progress

The app SHALL store the last valid bank and the progress of the session in `localStorage`, and SHALL keep working when that storage is unavailable.

#### Scenario: Coming back after a reload

- **WHEN** the user reloads the page after having uploaded a valid bank
- **THEN** the bank is restored from the cache, with no new upload required

#### Scenario: Storage unavailable

- **WHEN** `localStorage` throws on read or on write
- **THEN** the app operates normally, only requiring the upload once per session

#### Scenario: Replacing the bank

- **WHEN** the user uploads a new valid JSON file
- **THEN** the cached bank is replaced and the session in progress is restarted

### Requirement: Filters on the drawable set

The app SHALL allow the drawable set of questions to be restricted by exam paper, by topic and by answer-key provenance, before the session starts.

#### Scenario: Filter by exam paper

- **WHEN** the user selects only `ENA26`
- **THEN** only the 20 questions of that paper enter the draw

#### Scenario: Filter by provenance

- **WHEN** the user chooses official answer keys only
- **THEN** only the 40 questions of ENA25 and ENA26 enter the draw

#### Scenario: Filter with no results

- **WHEN** the combination of filters returns no question
- **THEN** the app says so and does not allow the session to start

### Requirement: Draw without repetition

The app SHALL draw the questions by shuffling the filtered set and consuming it like a deck, without repeating a question within the same session.

#### Scenario: Sequence without repetition

- **WHEN** the user goes through N questions of a set of N
- **THEN** each question appears exactly once

#### Scenario: End of the deck

- **WHEN** the last question of the deck is answered
- **THEN** the session ends and the final score is displayed

#### Scenario: Bank preserved

- **WHEN** the filtered set is shuffled
- **THEN** the array of the loaded bank is not modified

### Requirement: Answering and immediate grading

The app SHALL present the 4 options, accept one choice per question and grade it immediately, displaying the rationale and the reference when they exist.

#### Scenario: Correct answer

- **WHEN** the user chooses the option that matches the answer key
- **THEN** the option is marked as correct and the hit enters the score

#### Scenario: Incorrect answer

- **WHEN** the user chooses an option different from the answer key
- **THEN** the choice is marked as incorrect, the correct option is highlighted, and the miss enters the score

#### Scenario: Rationale of a derived answer

- **WHEN** the graded question has `procedencia: "derivada"`
- **THEN** the rationale and the consulted reference are displayed next to the grading

#### Scenario: Choice locked after grading

- **WHEN** the question has already been graded
- **THEN** the options do not accept a new choice for that question

### Requirement: Derived answer key warning

The app SHALL visually flag the questions whose answer does not come from an official answer key, so that the user never confuses them with an official answer.

#### Scenario: Badge on a derived question

- **WHEN** a question with `procedencia: "derivada"` is displayed
- **THEN** a warning badge indicates that the answer was derived from the reference material

#### Scenario: Official question without a badge

- **WHEN** a question with `procedencia: "oficial"` is displayed
- **THEN** no warning badge is shown

#### Scenario: Low confidence indication

- **WHEN** a derived question has `confianca: "baixa"`
- **THEN** the badge distinguishes that level from the others

### Requirement: Score and review of the mistakes

The app SHALL keep the score of the session in progress and SHALL allow the missed questions to be reviewed at the end.

#### Scenario: Score during the session

- **WHEN** the user is answering
- **THEN** the app shows hits, misses and how many questions are left in the deck

#### Scenario: Review at the end

- **WHEN** the session ends
- **THEN** the app lists the missed questions with the stem, the chosen answer and the correct answer

#### Scenario: New session

- **WHEN** the user starts a new session
- **THEN** the score is reset and the filtered set is reshuffled

### Requirement: Keyboard operation

The app SHALL allow the user to answer and to advance from the keyboard, with visible focus.

#### Scenario: Selection by key

- **WHEN** the user presses `a`, `b`, `c` or `d`
- **THEN** the corresponding option is selected

#### Scenario: Advancing by key

- **WHEN** the user presses `Enter` on an already graded question
- **THEN** the app advances to the next question of the deck

#### Scenario: Tab navigation

- **WHEN** the user navigates with `Tab`
- **THEN** the interactive controls receive visible focus, in an order consistent with the reading order
