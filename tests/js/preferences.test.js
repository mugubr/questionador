// @ts-check

/**
 * Tests for `docs/assets/js/preferences.js`.
 *
 * Both namespaces are pure: they take a value and return a new one, and never
 * touch `localStorage`. Everything that comes back from storage is treated as
 * hostile, so a hand-edited or half-written value must degrade to the
 * defaults and never to a crash.
 */

'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { loadAppScript, makeQuestion } = require('./helpers.js');

const { Preferences, AnswerHistory } = loadAppScript('preferences.js', [
  'Preferences',
  'AnswerHistory'
]);

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

test('the defaults leave the excluded questions out of the draw', function () {
  const defaults = Preferences.defaults();

  assert.equal(defaults.version, Preferences.VERSION);
  assert.equal(defaults.shuffleOptions, true);
  assert.equal(defaults.sessionSize, 20);
  assert.deepEqual(defaults.filters, {
    exams: [],
    topics: [],
    history: 'all',
    includeExcluded: false
  });
});

test('the defaults are a fresh object every time', function () {
  const first = Preferences.defaults();
  first.filters.exams.push('ENA26');

  assert.deepEqual(Preferences.defaults().filters.exams, []);
});

test('a value that is not an object falls back to the defaults', function () {
  [null, undefined, 7, 'texto', true].forEach(function (raw) {
    assert.deepEqual(Preferences.normalize(raw), Preferences.defaults());
  });
});

test('a session size the app does not offer is refused', function () {
  assert.equal(Preferences.normalize({ sessionSize: 33 }).sessionSize, 20);
  assert.equal(Preferences.normalize({ sessionSize: '10' }).sessionSize, 20);

  /** @type {number[]} */ (Preferences.SIZES).forEach(function (size) {
    assert.equal(Preferences.normalize({ sessionSize: size }).sessionSize, size);
  });
});

test('a shuffle flag that is not a boolean is refused', function () {
  assert.equal(Preferences.normalize({ shuffleOptions: 'sim' }).shuffleOptions, true);
  assert.equal(Preferences.normalize({ shuffleOptions: false }).shuffleOptions, false);
});

test('filter entries that are not filled strings are dropped', function () {
  const normalized = Preferences.normalize({
    filters: { exams: ['ENA26', '', 7, null, 'AV2-PI'], topics: 'patente' }
  });

  assert.deepEqual(normalized.filters.exams, ['ENA26', 'AV2-PI']);
  assert.deepEqual(normalized.filters.topics, []);
});

test('a history rule outside the three is refused', function () {
  assert.equal(
    Preferences.normalize({ filters: { history: 'todas' } }).filters.history,
    'all'
  );
  assert.equal(
    Preferences.normalize({ filters: { history: 'incorrect' } }).filters.history,
    'incorrect'
  );
  assert.equal(
    Preferences.normalize({ filters: { history: 'unanswered' } }).filters.history,
    'unanswered'
  );
});

test('preferences saved before the excluded rename fall back safely', function () {
  /* Older saved preferences carry `includeDuplicates`. The safe default is to
     leave the excluded questions out of the draw, not to guess. */
  const normalized = Preferences.normalize({
    filters: { includeDuplicates: true, sources: ['official'] }
  });

  assert.equal(normalized.filters.includeExcluded, false);
  assert.equal(normalized.filters.sources, undefined);
});

test('includeExcluded is only honoured when it is exactly true', function () {
  assert.equal(
    Preferences.normalize({ filters: { includeExcluded: true } }).filters
      .includeExcluded,
    true
  );
  assert.equal(
    Preferences.normalize({ filters: { includeExcluded: 'sim' } }).filters
      .includeExcluded,
    false
  );
});

// ---------------------------------------------------------------------------
// The cross-session answer history
// ---------------------------------------------------------------------------

test('an empty history has no inherited entries', function () {
  /* The map has a null prototype so an id like `constructor` cannot collide
     with something inherited from Object.prototype. */
  const history = AnswerHistory.empty();

  assert.equal(AnswerHistory.entryOf(history, 'constructor'), null);
  assert.equal(AnswerHistory.entryOf(history, 'toString'), null);
  assert.equal(AnswerHistory.entryOf(history, 'ENA26-Q01'), null);
  assert.equal(Object.getPrototypeOf(history.questions), null);
});

test('a history parsed out of JSON has no inherited entries either', function () {
  const history = AnswerHistory.normalize(JSON.parse('{"version":1,"questions":{}}'));
  assert.equal(AnswerHistory.entryOf(history, 'constructor'), null);
});

test('recording an answer returns a new history and never mutates the old', function () {
  const before = AnswerHistory.empty();
  const after = AnswerHistory.record(before, 'ENA26-Q01', true, 1700000000000);

  assert.notEqual(after, before);
  assert.equal(AnswerHistory.entryOf(before, 'ENA26-Q01'), null);
  assert.deepEqual(AnswerHistory.entryOf(after, 'ENA26-Q01'), {
    seen: 1,
    correct: 1,
    incorrect: 0,
    lastCorrect: true,
    lastAt: 1700000000000
  });
});

test('a second answer accumulates and replaces only the last outcome', function () {
  let history = AnswerHistory.record(AnswerHistory.empty(), 'ENA26-Q01', false, 1);
  history = AnswerHistory.record(history, 'ENA26-Q01', true, 2);

  assert.deepEqual(AnswerHistory.entryOf(history, 'ENA26-Q01'), {
    seen: 2,
    correct: 1,
    incorrect: 1,
    lastCorrect: true,
    lastAt: 2
  });
});

test('recording keeps every other question untouched', function () {
  let history = AnswerHistory.record(AnswerHistory.empty(), 'ENA26-Q01', true, 1);
  history = AnswerHistory.record(history, 'ENA26-Q02', false, 2);

  assert.equal(AnswerHistory.entryOf(history, 'ENA26-Q01').correct, 1);
  assert.equal(AnswerHistory.entryOf(history, 'ENA26-Q02').incorrect, 1);
});

test('a stored history that is not an object degrades to empty', function () {
  [null, 'texto', 42, { questions: 'nada' }].forEach(function (raw) {
    const history = AnswerHistory.normalize(raw);
    assert.deepEqual(Object.keys(history.questions), []);
    assert.equal(Object.getPrototypeOf(history.questions), null);
  });
});

test('a stored entry with missing counters is coerced, not dropped', function () {
  const history = AnswerHistory.normalize({
    questions: { 'ENA26-Q01': { seen: 'muitas', lastCorrect: 'sim' } }
  });

  assert.deepEqual(AnswerHistory.entryOf(history, 'ENA26-Q01'), {
    seen: 0,
    correct: 0,
    incorrect: 0,
    lastCorrect: false,
    lastAt: 0
  });
});

test('a stored entry that is not an object is dropped', function () {
  const history = AnswerHistory.normalize({
    questions: { 'ENA26-Q01': 'nao e um registro', 'ENA26-Q02': { seen: 1 } }
  });

  assert.equal(AnswerHistory.entryOf(history, 'ENA26-Q01'), null);
  assert.equal(AnswerHistory.entryOf(history, 'ENA26-Q02').seen, 1);
});

test('the history counts how many of a set of questions were ever answered', function () {
  const first = makeQuestion();
  const second = makeQuestion({ id: 'ENA26-Q02' });
  const history = AnswerHistory.record(AnswerHistory.empty(), first.id, true, 1);

  assert.equal(AnswerHistory.answeredCount(history, [first, second]), 1);
  assert.equal(AnswerHistory.answeredCount(AnswerHistory.empty(), [first]), 0);
});

test('the lifetime history aggregates per topic', function () {
  const first = makeQuestion();
  const second = makeQuestion({ id: 'ENA26-Q02', topic: 'marca' });
  let history = AnswerHistory.record(AnswerHistory.empty(), first.id, true, 1);
  history = AnswerHistory.record(history, first.id, false, 2);
  history = AnswerHistory.record(history, second.id, true, 3);

  const totals = AnswerHistory.byTopic(history, [first, second]);

  assert.deepEqual(totals.get('patente'), { correct: 1, answered: 2 });
  assert.deepEqual(totals.get('marca'), { correct: 1, answered: 1 });
});

test('a topic nobody answered is absent from the aggregate', function () {
  const totals = AnswerHistory.byTopic(AnswerHistory.empty(), [makeQuestion()]);
  assert.equal(totals.size, 0);
});
