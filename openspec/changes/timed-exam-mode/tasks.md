Each `##` group lands as one commit. A task is done when the command next to it
passes or the stated outcome is observable.

## 1. Session state and pure logic

- [x] 1.1 Add `examMode` and `deadline` to `Session.create`'s settings and to the returned session, with `deadline` computed once as `now + durationMinutes * 60000`; `Session.create({examMode:false})` and a zero or missing duration both yield `deadline: null`
- [x] 1.2 Add `Session.remainingMs(session, now)` and `Session.isTimeUp(session, now)`, both pure functions of their arguments; `node --test tests/js/session.test.js` covers the zero boundary and the outside-exam-mode case
- [x] 1.3 Add `Session.shouldReveal(session)` and `Session.formatDuration(ms)` as the pure, testable home for the "hide grading" decision and the countdown's `MM:SS`/`H:MM:SS` formatting, so neither lives only in the untested `ui.js`
- [x] 1.4 Restore `examMode`/`deadline` in `Session.fromStored`, refusing a wrong-typed value instead of coercing it; a stored session from before this change restores to `examMode: false, deadline: null`

## 2. Settings

- [x] 2.1 Add `Preferences.EXAM_DURATIONS` (30/60/90/120) and `examMode`/`examDurationMinutes` to `Preferences.defaults()` and `Preferences.normalize()`, refusing an out-of-range or wrong-typed value
- [x] 2.2 Add the "Modo prova" switch and the duration segmented control to the filters form, the duration control hidden until the switch is on

## 3. Timer, deferred grading, confirmation dialog

- [x] 3.1 Add the scoreboard clock, swapped in for the live acertos/erros count in exam mode, ticking once a second from `Session.remainingMs`
- [x] 3.2 Announce a spoken checkpoint at 5 minutes and at 1 minute remaining, each exactly once; resuming a session already past a checkpoint seeds it as already-warned instead of re-announcing it
- [x] 3.3 Gate grading on `Session.isTimeUp` inside `choose()`, not only on the countdown's tick, so a late answer from a throttled background tab is refused
- [x] 3.4 End the session automatically at the deadline, from the question panel or from a reload that discovers time already up, closing the "Encerrar sessão?" dialog first if it happens to be open
- [x] 3.5 Withhold the correct/incorrect marker, the explanation and the running score while `examMode` is on; report "resposta registrada" and the remaining count instead
- [x] 3.6 Report the attempt's total time on the results panel, capped at the deadline rather than at whenever the panel happens to render
- [x] 3.7 Add the "Encerrar sessão?" confirmation `<dialog>`, unconditional on exam mode, with the confirm action styled to draw the eye and the global keyboard shortcuts yielding to it while it is open

## 4. Tests

- [x] 4.1 `node --test tests/js/session.test.js` covers the deadline arithmetic, `remainingMs`/`isTimeUp` boundaries, `shouldReveal`, `formatDuration`'s MM:SS/H:MM:SS boundary, and `fromStored` restoring a wrong-typed or already-past-deadline session
- [x] 4.2 `node --test tests/js/preferences.test.js` covers every rejected shape of `examMode` and `examDurationMinutes`
- [x] 4.3 The app exercised by hand in both themes, at 320px and at desktop width: a full exam-mode session drawn, answered, and ended both by the clock and by the confirmation dialog, with the scoreboard, the checkpoint announcements and the results panel all checked

## 5. Documentation

- [x] 5.1 Add an exam-mode section to `README.md`'s "Como usar", written for the student audience the rest of the file targets
