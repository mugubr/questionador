// @ts-check

/**
 * The study preferences: how the student likes a session to be drawn.
 *
 * The namespace is pure — it takes a value and returns a new one, and never
 * touches `localStorage` or the DOM. The I/O lives in AppStorage, which is
 * what makes this testable outside a browser. The other half of the persisted
 * state, the cross-session answer history, lives in `history.js`.
 *
 * Everything that comes back from storage is treated as hostile: a hand-edited
 * or half-written file must degrade to the defaults, never to a crash.
 */

const Preferences = (function () {
  'use strict';

  const VERSION = 1;

  /** @type {number[]} Offered session sizes; 0 means "every question that matches". */
  const SIZES = [10, 20, 50, 0];

  /** @type {number[]} Offered exam-mode durations, in minutes. */
  const EXAM_DURATIONS = [30, 60, 90, 120];

  /**
   * Build the default preferences.
   *
   * @returns {Preferences} A fresh object; the caller may mutate it freely.
   */
  function defaults() {
    return {
      version: VERSION,
      shuffleOptions: true,
      sessionSize: 20,
      examMode: false,
      examDurationMinutes: 60,
      filters: {
        exams: [],
        topics: [],
        history: 'all',
        includeExcluded: false
      }
    };
  }

  /**
   * Keep the entries of an unknown value that are non-empty strings.
   *
   * @param {unknown} value - Anything; only arrays contribute entries.
   * @returns {string[]} The surviving strings, in order.
   */
  function stringList(value) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value.filter(function (entry) {
      return typeof entry === 'string' && entry !== '';
    });
  }

  /**
   * Coerce an unknown value into valid preferences.
   *
   * @param {unknown} raw - Whatever came out of storage.
   * @returns {Preferences} Valid preferences, falling back field by field.
   */
  function normalize(raw) {
    const result = defaults();
    if (!raw || typeof raw !== 'object') {
      return result;
    }

    const source = /** @type {Record<string, unknown>} */ (raw);
    if (typeof source.shuffleOptions === 'boolean') {
      result.shuffleOptions = source.shuffleOptions;
    }
    if (
      typeof source.sessionSize === 'number' &&
      SIZES.indexOf(source.sessionSize) !== -1
    ) {
      result.sessionSize = source.sessionSize;
    }
    if (typeof source.examMode === 'boolean') {
      result.examMode = source.examMode;
    }
    if (
      typeof source.examDurationMinutes === 'number' &&
      EXAM_DURATIONS.indexOf(source.examDurationMinutes) !== -1
    ) {
      result.examDurationMinutes = source.examDurationMinutes;
    }

    if (source.filters && typeof source.filters === 'object') {
      const filters = /** @type {Record<string, unknown>} */ (source.filters);
      result.filters.exams = stringList(filters.exams);
      result.filters.topics = stringList(filters.topics);
      if (filters.history === 'incorrect' || filters.history === 'unanswered') {
        result.filters.history = filters.history;
      }
      /* Preferences saved before the excluded-questions rename carry
         `includeDuplicates`; they simply fall back to the safe default, which
         is to leave the excluded questions out of the draw. */
      result.filters.includeExcluded = filters.includeExcluded === true;
    }

    return result;
  }

  return { VERSION, SIZES, EXAM_DURATIONS, defaults, normalize };
})();

/* The node test runner loads these classic scripts into a shared context, where
   a top-level `const` would not survive; the explicit assignment is what makes
   the namespace reachable from the tests. */
Object.assign(globalThis, { Preferences });
