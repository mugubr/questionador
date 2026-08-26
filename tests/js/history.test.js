// @ts-check

/**
 * Tests for `docs/assets/js/history.js`.
 *
 * The history is what "só as que errei" and "nunca respondidas" filter on, so
 * a wrong entry silently changes which questions a student is shown. It is
 * pure — it takes a value and returns a new one — and everything that comes
 * back from storage is treated as hostile: a hand-edited or half-written value
 * must degrade to an empty history and never to a crash.
 */

'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { loadAppScript, makeQuestion } = require('./helpers.js');

const AnswerHistory = loadAppScript('history.js', 'AnswerHistory');

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
