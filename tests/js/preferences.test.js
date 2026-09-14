// @ts-check

/**
 * Tests for `docs/assets/js/preferences.js`.
 *
 * The namespace is pure: it takes a value and returns a new one, and never
 * touches `localStorage`. Everything that comes back from storage is treated
 * as hostile, so a hand-edited or half-written value must degrade to the
 * defaults and never to a crash.
 */

'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { loadAppScript } = require('./helpers.js');

const Preferences = loadAppScript('preferences.js', 'Preferences');

test('the defaults leave the excluded questions out of the draw', function () {
  const defaults = Preferences.defaults();

  assert.equal(defaults.version, Preferences.VERSION);
  assert.equal(defaults.shuffleOptions, true);
  assert.equal(defaults.sessionSize, 20);
  assert.equal(defaults.examMode, false);
  assert.equal(defaults.examDurationMinutes, 60);
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

test('an exam-mode flag that is not a boolean is refused', function () {
  assert.equal(Preferences.normalize({ examMode: 'sim' }).examMode, false);
  assert.equal(Preferences.normalize({ examMode: true }).examMode, true);
});

test('an exam duration the app does not offer is refused', function () {
  assert.equal(
    Preferences.normalize({ examDurationMinutes: 45 }).examDurationMinutes,
    60
  );
  assert.equal(
    Preferences.normalize({ examDurationMinutes: '30' }).examDurationMinutes,
    60
  );

  /** @type {number[]} */ (Preferences.EXAM_DURATIONS).forEach(function (minutes) {
    assert.equal(
      Preferences.normalize({ examDurationMinutes: minutes }).examDurationMinutes,
      minutes
    );
  });
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
