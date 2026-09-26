## Why

Every PROFNIT exam is timed and graded only once the booklet is handed in — a
student never sees whether item 3 was right while still working on item 40.
The app's ordinary session gives neither: there is no clock, and every answer
is graded and shown the instant it is chosen. Someone rehearsing for the real
exam under real conditions — a fixed window, no peeking at the running score —
has no way to do that here.

## What Changes

- Add an opt-in **exam mode** switch next to the existing session settings,
  with a duration choice of 30, 60, 90 or 120 minutes.
- A session drawn in exam mode gets an absolute deadline (draw time plus the
  chosen duration) instead of a countdown that could drift or reset. The
  scoreboard swaps its live acertos/erros count for a running clock, with a
  spoken checkpoint at 5 minutes and at 1 minute remaining.
- Grading still happens the instant an answer is chosen — the record is
  written exactly as in a normal session — but nothing about it is _shown_
  until the session ends: no correct/incorrect marker, no explanation, no
  running score. Choosing an option is still confirmed ("resposta
  registrada"), just not scored out loud.
- The clock is enforced by the deadline itself, not only by the once-a-second
  display tick: an answer submitted after the deadline (for instance because
  the tab was backgrounded and its timer throttled) is refused and the
  session ends instead of being graded late.
- The session ends on its own the moment the deadline passes, wherever the
  student left it — mid-question or having reloaded the page long after time
  was up — and the results panel reports how long the attempt actually took,
  capped at the deadline rather than at whenever the student happens to look.
- Ending a session before the deck is exhausted — exam mode or not — now asks
  for confirmation in a modal dialog first, since it discards every
  unanswered question and that action cannot be undone.

## Capabilities

### Modified Capabilities

- `quiz-runner`: adds the timed, deferred-grading session mode described
  above, and adds a confirmation step before a session is ended early. Every
  other requirement of the capability — filtering, drawing, keyboard
  operation, accessibility, the ordinary immediate-grading session — is
  unchanged and still the default.

## Impact

- **Affected code**: `docs/assets/js/session.js` (deadline, remaining-time and
  reveal helpers), `docs/assets/js/preferences.js` (the new settings),
  `docs/assets/js/ui.js` (the countdown, the deferred-grading render path, the
  confirmation dialog), `docs/index.html` and `docs/assets/css/styles.css`
  (the scoreboard clock, the duration control, the dialog), and their tests.
- **No change to the question bank contract.** Exam mode is session state,
  never persisted to `data/` and never affecting `data/schema.json`.
- **No new dependency, no server.** The deadline is a client-side timestamp;
  nothing about the exam's timing is enforced anywhere the student cannot, in
  principle, inspect — see the design doc's note on that limit.
- **Out of scope**: per-question time limits, saving a completed exam-mode
  attempt for later review against a class average, and any server-verified
  proctoring. This is a study aid, not an exam-integrity tool.
