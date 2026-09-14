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

### Requirement: Automatic loading of the embedded bank

The app SHALL load the question bank from `docs/data/question-bank.js`, which assigns `window.QUESTION_BANK` and is loaded by a plain `<script>` tag before the app's own scripts. The app SHALL NOT issue any network request to obtain the bank, and SHALL behave identically over `https://` and over `file://`.

#### Scenario: Site opens already loaded

- **WHEN** the user opens the published page
- **THEN** the bank is available with no upload, no click and no spinner
- **AND** the draw screen is shown with the total number of loaded questions

#### Scenario: Opening from disk

- **WHEN** `docs/index.html` is opened over `file://`
- **THEN** the app loads the same bank and operates identically, with no CORS error and no request in the network panel

#### Scenario: Embedded bank missing or not assigned

- **WHEN** `window.QUESTION_BANK` is undefined after the scripts have loaded
- **THEN** the app displays an error naming `docs/data/question-bank.js` as the missing file
- **AND** the draw controls stay disabled

#### Scenario: Override with an uploaded bank

- **WHEN** the user uploads a valid JSON bank through the secondary upload control
- **THEN** the uploaded bank replaces the embedded one for that session only
- **AND** reloading the page returns to the embedded bank

### Requirement: Validation of the loaded bank

The app SHALL validate the bank before using it and SHALL display a readable error identifying the problem, without silently operating on an invalid bank.

#### Scenario: Malformed uploaded JSON

- **WHEN** an uploaded file is not valid JSON
- **THEN** the app displays an error message identifying the problem
- **AND** the embedded bank stays active

#### Scenario: Invalid schema

- **WHEN** the bank does not contain `version` and a non-empty `questions` list
- **THEN** the app rejects it with a message explaining the missing field

#### Scenario: Question with an invalid answer

- **WHEN** some question has `answer.letter` outside `a`–`d` or does not have the 4 options
- **THEN** the app rejects the bank identifying the invalid question

#### Scenario: Invalid provenance

- **WHEN** some question has `answer.source` outside `official` and `derived`, or a `derived` answer is missing `confidence`, `reference` or `rationale`
- **THEN** the app rejects the bank identifying the invalid question and the missing field

#### Scenario: Invalid embedded bank

- **WHEN** the embedded `window.QUESTION_BANK` fails validation
- **THEN** the app displays the validation error naming `docs/data/question-bank.js`
- **AND** the draw controls stay disabled instead of starting a session on partial data

#### Scenario: Hostile textual content

- **WHEN** the text of a question contains HTML markup
- **THEN** it is rendered as literal text through `textContent`, with no HTML interpretation

### Requirement: Session persistence and resume

The app SHALL store the progress of the session in `localStorage`, SHALL read it back at startup and offer to resume it, and SHALL keep working when that storage is unavailable. The app SHALL NOT cache the question bank in `localStorage`: the embedded bank is always the truth.

#### Scenario: Resuming an interrupted session

- **WHEN** the user reloads the page in the middle of a session
- **THEN** the app offers to resume it
- **AND** resuming restores the remaining deck, the answered questions and the score

#### Scenario: Declining the resume

- **WHEN** the user declines the offer to resume
- **THEN** the stored session is discarded and the draw screen is shown

#### Scenario: Stored session no longer matches the bank

- **WHEN** the stored session was recorded against a different bank `version` or `generatedAt`
- **THEN** the stored session is discarded and the app explains why, instead of resuming into questions that may no longer exist

#### Scenario: Bank never cached

- **WHEN** the app starts
- **THEN** the questions come from the embedded bank and no bank copy is read from or written to `localStorage`

#### Scenario: Storage unavailable

- **WHEN** `localStorage` throws on read or on write
- **THEN** the app operates normally, only losing the ability to resume an interrupted session

### Requirement: Theme selection

The app SHALL offer three theme states — system, light and dark — SHALL persist the choice in `localStorage`, and SHALL apply the stored choice before the first paint.

#### Scenario: Reload in dark mode does not flash

- **WHEN** the user has chosen dark and reloads the page
- **THEN** the page paints dark on the first frame, with no white flash
- **AND** the `data-theme` attribute is already set when the body renders

#### Scenario: Following the system setting

- **WHEN** the theme is set to system and the operating system is in dark mode
- **THEN** the app renders in dark
- **AND** the app switches with the system setting without a reload

#### Scenario: Storage unavailable

- **WHEN** `localStorage` throws on read or on write
- **THEN** the app renders in the system theme and the theme control keeps working for the current page

### Requirement: Filters on the drawable set

The app SHALL allow the drawable set of questions to be restricted by exam paper, by topic and by answer provenance, before the session starts.

#### Scenario: Filter by exam paper

- **WHEN** the user selects only `ENA26`
- **THEN** only the 20 questions of that paper enter the draw

#### Scenario: Filter by provenance

- **WHEN** the user chooses official answers only, that is `answer.source == "official"`
- **THEN** only the 40 questions of ENA25 and ENA26 enter the draw

#### Scenario: Filter by topic

- **WHEN** the user selects a topic
- **THEN** only questions whose `topic` equals that value enter the draw
- **AND** the topic is displayed with its Portuguese label

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

### Requirement: Option shuffling

The app SHALL shuffle the order in which the four options of a question are displayed, and SHALL grade and record the choice against the original letter from the bank.

#### Scenario: Displayed order differs from the bank order

- **WHEN** a question is drawn
- **THEN** its options are presented in a shuffled order
- **AND** the letter shown next to each option matches its displayed position

#### Scenario: Grading resolves to the original letter

- **WHEN** the user chooses the option whose original letter matches `answer.letter`
- **THEN** the choice is graded as correct regardless of the position it was displayed in

#### Scenario: Review reports bank letters

- **WHEN** a missed question appears in the end-of-session review
- **THEN** the chosen answer and the correct answer are reported using the original letters from the bank

#### Scenario: Bank preserved

- **WHEN** the options of a question are shuffled
- **THEN** the object of the loaded bank is not modified

### Requirement: Configurable session size

The app SHALL let the user choose how many questions a session contains, drawing that many from the shuffled filtered set.

#### Scenario: Session limited to the chosen size

- **WHEN** the user sets the session size to 10 and starts a session over a filtered set of 40
- **THEN** the session contains exactly 10 questions
- **AND** the session ends after the tenth answer

#### Scenario: Size larger than the filtered set

- **WHEN** the chosen size is larger than the number of questions available after filtering
- **THEN** the session contains every available question and the app states how many were drawn

#### Scenario: Size persists between sessions

- **WHEN** the user starts a new session after having chosen a size
- **THEN** the previously chosen size is preselected

### Requirement: Exclusion of known duplicates from the draw

The app SHALL exclude from the draw, by default, every question carrying `duplicateOf`, and SHALL let the user include them explicitly.

#### Scenario: Duplicates excluded by default

- **WHEN** a session is drawn from `AV2-PI`, whose 16 numbered items include 2 repeats
- **THEN** 14 distinct questions enter the draw
- **AND** the app states that 2 known duplicates were excluded

#### Scenario: Duplicates included on request

- **WHEN** the user enables the option to include known duplicates
- **THEN** all 16 questions of `AV2-PI` enter the draw

#### Scenario: Known defects surfaced

- **WHEN** a drawn question carries `knownDefects`
- **THEN** the app displays a note describing the defect of the source exam paper

### Requirement: Answering and immediate grading

The app SHALL present the 4 options, accept one choice per question and grade it immediately, displaying the rationale and the reference when they exist.

#### Scenario: Correct answer

- **WHEN** the user chooses the option that matches the answer key
- **THEN** the option is marked as correct and the hit enters the score

#### Scenario: Incorrect answer

- **WHEN** the user chooses an option different from the answer key
- **THEN** the choice is marked as incorrect, the correct option is highlighted, and the miss enters the score

#### Scenario: Rationale of a derived answer

- **WHEN** the graded question has `answer.source: "derived"`
- **THEN** the rationale and the consulted reference are displayed next to the grading

#### Scenario: Choice locked after grading

- **WHEN** the question has already been graded
- **THEN** the options do not accept a new choice for that question

#### Scenario: Grading keeps the reading position

- **WHEN** a question is graded
- **THEN** the viewport does not jump to the top of the page
- **AND** focus moves to the grading result rather than being lost

### Requirement: Derived answer key warning

The app SHALL visually flag the questions whose answer does not come from an official answer key, so that the user never confuses them with an official answer.

#### Scenario: Badge on a derived question

- **WHEN** a question with `answer.source: "derived"` is displayed
- **THEN** a warning badge indicates that the answer was derived from the reference material
- **AND** the badge is announced as part of the accessible name, not conveyed by colour alone

#### Scenario: Official question without a badge

- **WHEN** a question with `answer.source: "official"` is displayed
- **THEN** no warning badge is shown

#### Scenario: Low confidence indication

- **WHEN** a derived question has `answer.confidence: "low"`
- **THEN** the badge distinguishes that level from the others

### Requirement: Score and review of the mistakes

The app SHALL keep the score of the session in progress and SHALL allow the missed questions to be reviewed at the end, with the whole evidence behind each answer key.

#### Scenario: Score during the session

- **WHEN** the user is answering
- **THEN** the app shows hits, misses and how many questions are left in the deck

#### Scenario: Review at the end

- **WHEN** the session ends
- **THEN** the app lists the missed questions with the stem, the chosen answer and the correct answer

#### Scenario: Review keeps the evidence

- **WHEN** a missed question in the review has `answer.source: "derived"`
- **THEN** the review also shows its `rationale`, its `reference` and its `confidence`
- **AND** the derived badge is shown, exactly as during the session

#### Scenario: New session

- **WHEN** the user starts a new session
- **THEN** the score is reset and the filtered set is reshuffled

### Requirement: Cross-session history

The app SHALL record, per question id, the outcome of the last attempt and the number of attempts, SHALL keep that record across sessions in `localStorage`, and SHALL offer it as filters on the drawable set.

#### Scenario: Only the ones I got wrong

- **WHEN** the user enables the "only the ones I got wrong" filter
- **THEN** only questions whose last recorded outcome was incorrect enter the draw

#### Scenario: Never answered

- **WHEN** the user enables the "never answered" filter
- **THEN** only questions with no recorded attempt enter the draw

#### Scenario: History survives a reload

- **WHEN** the user answers a question, closes the browser and opens the app again
- **THEN** that question's outcome and attempt count are still recorded

#### Scenario: Hostile question id

- **WHEN** the history is keyed by a question id such as `constructor` or `__proto__`
- **THEN** the lookup returns that question's own record and does not collide with `Object.prototype`

#### Scenario: History cleared by the user

- **WHEN** the user clears the history
- **THEN** every question counts as never answered and the score of the current session is untouched

#### Scenario: Storage unavailable

- **WHEN** `localStorage` throws on read or on write
- **THEN** the app operates normally with an empty history and the history filters are disabled with an explanation

### Requirement: Keyboard operation

The app SHALL allow the user to answer and to advance from the keyboard, with visible focus, and SHALL never take a key away from the control that has focus.

#### Scenario: Selection by key

- **WHEN** the user presses `a`, `b`, `c` or `d`
- **THEN** the option displayed in the corresponding position is selected

#### Scenario: Advancing by key

- **WHEN** the user presses `Enter` on an already graded question with no interactive control focused
- **THEN** the app advances to the next question of the deck

#### Scenario: Shortcut yields to the focused control

- **WHEN** the user presses `Enter` while a button, a link or a form control has focus
- **THEN** that control handles the key and the global shortcut does not run
- **AND** the app does not call `preventDefault` on the event

#### Scenario: Tab navigation

- **WHEN** the user navigates with `Tab`
- **THEN** the interactive controls receive visible focus, in an order consistent with the reading order

### Requirement: Accessibility conformance to WCAG 2.2 level AA

The app SHALL conform to WCAG 2.2 level AA in every theme it offers.

#### Scenario: Contrast in both themes

- **WHEN** the computed colour pairs are measured in light and in dark
- **THEN** text reaches at least 4.5:1, and large text and the visual boundary of every interactive control reach at least 3:1
- **AND** a token that passes in one theme and fails in the other counts as a failure

#### Scenario: State not conveyed by colour alone

- **WHEN** an option is marked correct or incorrect after grading
- **THEN** it also carries a non-colour marker
- **AND** its accessible name states the outcome

#### Scenario: Reflow at 320px

- **WHEN** the app is rendered at a 320px viewport width
- **THEN** no horizontal scrolling is required and no content is clipped

#### Scenario: Focus managed on every panel change

- **WHEN** the app moves from one panel to another
- **THEN** focus is placed on a visible element of the new panel
- **AND** focus is never moved into a `display: none` subtree

#### Scenario: Answering does not move the viewport

- **WHEN** the user answers a question
- **THEN** the page does not scroll to the top and the graded option stays in view

#### Scenario: Single live region

- **WHEN** the app announces the result of an action
- **THEN** the message is written into exactly one `role="status"` region that is always present in the DOM and never toggled with `hidden`
- **AND** the message is a complete sentence

#### Scenario: Target size

- **WHEN** an interactive control is measured
- **THEN** it is at least 44x44 CSS pixels

#### Scenario: Semantics of the current state

- **WHEN** a session is in progress
- **THEN** a real heading names the current state and the progress is exposed through `role="progressbar"` with its value attributes
