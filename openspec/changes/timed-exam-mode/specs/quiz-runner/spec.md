## ADDED Requirements

### Requirement: Timed exam mode

The app SHALL offer an opt-in exam mode with a chosen duration of 30, 60, 90 or 120 minutes, SHALL compute the session's deadline once at draw time as an absolute timestamp, and SHALL end the session on its own once that deadline passes, wherever the student left it.

#### Scenario: Deadline set at draw time

- **WHEN** a session is drawn with exam mode on and a 60-minute duration
- **THEN** the session carries a deadline 60 minutes after the moment it was drawn

#### Scenario: Deadline survives a reload

- **WHEN** the page is reloaded partway through an exam-mode session
- **THEN** the remaining time reflects the wall clock since the original draw, not a fresh countdown

#### Scenario: Session ends itself at the deadline

- **WHEN** the countdown reaches zero while the student is on the question panel
- **THEN** the session ends automatically and the results panel is shown, with a spoken announcement that time ran out

#### Scenario: Deadline already passed on reload

- **WHEN** the app starts and finds a stored exam-mode session whose deadline has already passed
- **THEN** the session is ended immediately, without offering to resume it into a clock that has already run out

#### Scenario: Late answer from a throttled tab is refused

- **WHEN** an option is chosen after the deadline has passed, even if the once-a-second display has not yet caught up
- **THEN** the choice is not graded and the session ends instead

#### Scenario: Checkpoints announced once each

- **WHEN** the countdown crosses 5 minutes remaining and again 1 minute remaining
- **THEN** each crossing is announced exactly once
- **AND** resuming a session already past a checkpoint does not announce it again

### Requirement: Deferred grading in exam mode

While a session has exam mode on, the app SHALL withhold every per-question grading signal — the correct/incorrect marker, the explanation, the running score — until the session ends.

#### Scenario: No feedback shown while answering

- **WHEN** an option is chosen during an exam-mode session
- **THEN** the choice is acknowledged with a neutral confirmation
- **AND** no marker, explanation or score change is shown

#### Scenario: Scoreboard shows the clock, not the running score

- **WHEN** an exam-mode session is in progress
- **THEN** the scoreboard shows the countdown in place of the live acertos/erros count

#### Scenario: Full results revealed at the end

- **WHEN** an exam-mode session ends, by the deadline or by the student
- **THEN** the results panel shows the score, the per-question review and the total time spent, capped at the deadline

### Requirement: Confirmation before ending a session early

The app SHALL ask for confirmation before ending a session that still has unanswered questions, regardless of whether exam mode is on.

#### Scenario: Ending early asks first

- **WHEN** the student activates "Encerrar sessão" before the deck is exhausted
- **THEN** a confirmation dialog names the consequence before anything is discarded

#### Scenario: Cancelling leaves the session running

- **WHEN** the student dismisses the confirmation dialog
- **THEN** the session continues exactly as it was

#### Scenario: Global shortcuts yield to the open dialog

- **WHEN** the confirmation dialog is open
- **THEN** the answer-selection and advance keyboard shortcuts do not act on the question underneath it
