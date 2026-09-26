## Context

The app already has one session shape: draw, answer, grade immediately, review
at the end. Exam mode does not replace that shape — it is the same `Session`
object with two more fields (`examMode`, `deadline`) and a handful of places
that check them before doing what the ordinary session would do unconditionally.
The three hard constraints from `AGENTS.md` still apply without exception: no
server, no build step, no external request, and every fixed defect gets a test
that fails before its fix.

## Goals / Non-Goals

**Goals:**

- Let a student rehearse under the same two constraints the real exam imposes:
  a fixed time budget and no mid-exam feedback.
- Make the deadline survive exactly what a real exam's clock survives — a
  closed laptop, a reloaded tab, a backgrounded browser — with no extra time
  granted for any of them.
- Keep the ordinary, immediately-graded session as the default and change
  nothing about its behaviour.

**Non-Goals:**

- Any guarantee that the student cannot see their own grading before the
  results panel does. This is a client-only app with no server to keep a
  secret from the person running the client; see D2.
- Per-question timers, saved exam attempts, or anything that compares one
  student's attempt against another's.
- Changing what a normal, non-exam session does or looks like.

## Decisions

### D1 — The deadline is an absolute timestamp, computed once at draw time

`Session.create` stores `deadline = now + durationMinutes * 60000`, not a
remaining-duration counter that ticks down and gets re-saved every second.
`Session.remainingMs(session, now)` and `Session.isTimeUp(session, now)` are
the only two places that ever read it, and both take `now` as an argument
instead of calling `Date.now()` themselves, which is what makes them pure and
testable with `node:test` at exact millisecond boundaries.

Rejected: a counter decremented on a `setInterval` tick, saved back to
`localStorage` periodically. It drifts under tab-throttling, it needs a
save-cadence decision that trades write frequency against resume accuracy for
no benefit, and it cannot be unit-tested without faking timers.

### D2 — Exam mode hides grading from the UI; it does not hide it from the client

`Session.answer` grades and stores the record the moment a choice is made,
identically to a normal session — `Session.shouldReveal(session)` is checked
only by `ui.js`, deciding whether to _render_ the correct/incorrect marker and
the explanation. The record sits in `localStorage` in plain JSON throughout
the attempt, exactly where a normal session's record sits too.

This is a deliberate limit, not an oversight: a purely client-side, no-server
app (a hard constraint of this whole project) has nothing to keep the grading
secret from the machine it is running on — a student who opens devtools mid-exam
can read `localStorage.getItem('profnit.session.v1')` and see every grade
already assigned. Exam mode is a study aid that removes the _temptation_ and
the _convenience_ of checking, not an anti-cheating control, and the feature
should never be described to a student as the latter.

Rejected: encrypting the stored record until the session ends. There is no
secret key a client-only app can hold that the same client cannot also read;
it would add real complexity for a protection that only looks real.

### D3 — The deadline gates grading directly, not only the countdown's tick

`choose()` in `ui.js` checks `Session.isTimeUp(session, Date.now())` itself
before grading a choice, in addition to the countdown's own `setInterval`
check. A backgrounded tab can have its timers throttled well past a second by
the browser, so the display tick alone is not a reliable enforcement point —
a student could return from a throttled background tab and answer once more
after time had already run out. The deadline is timestamp comparison against
the real clock, so it is correct regardless of how late the UI noticed.

### D4 — Confirming an early end applies to every session, not only exam mode

"Encerrar sessão" discards every unanswered question in the deck, which is
just as irreversible in a normal session as in a timed one. Gating the
confirmation dialog on `examMode` would have protected the mode that already
has the least to lose from an accidental click (an exam-mode student who ends
early loses time they were tracking anyway) while leaving the ordinary session
exposed. The dialog is unconditional.

### D5 — Duration is one of four fixed choices, not a free-form field

30/60/90/120 minutes match the PROFNIT papers' own published durations closely
enough for rehearsal, and a fixed, small `Preferences.EXAM_DURATIONS` list is
what keeps `Session.create`'s deadline arithmetic covered by a handful of exact
test cases instead of an open-ended input needing its own range validation
(and a plausible-typo guard — nobody meant to type a 3000-minute exam).

## Risks / Trade-offs

- **The plaintext-`localStorage` limit (D2) is real and stated on purpose.**
  If this feature is ever pitched to students as "exam-proof," that pitch is
  false advertising for a project with no server. The proposal and this
  design both say so; product copy introduced later should too.
- **Resuming a session after being away for a while must not re-announce a
  checkpoint the wall clock already passed.** Handled by seeding the
  "already warned" set from `remainingMs` at the moment a session
  (re)starts, not by suppressing the checkpoint logic itself.
- **A session that expires while the confirmation dialog is open** must not
  leave that dialog floating over the results panel. Handled by closing the
  dialog as part of the same auto-end path that the countdown's zero-crossing
  already takes.

## Migration Plan

Fully additive and backward compatible. `examMode` and `deadline` are absent
from every session stored before this change; `Session.fromStored` already
treats a missing or wrong-typed value as "not exam mode, no deadline," so an
in-progress session resumed after an upgrade behaves exactly as it did before
this change shipped. No data migration, no bank-contract change, no new
dependency.

## Open Questions

- Should the results panel eventually let a student export or screenshot the
  timing summary for their own records? Not needed for this change; the
  "tempo total" line already reported is enough for a first version.
