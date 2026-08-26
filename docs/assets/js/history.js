// @ts-check

/**
 * The cross-session answer history: what the student has answered, ever.
 *
 * It is what "só as que errei" and "nunca respondidas" filter on, and what the
 * results panel reads to put a lifetime figure beside each topic of the
 * session. Like Preferences, the namespace is pure — it takes a value and
 * returns a new one, and never touches `localStorage` or the DOM.
 *
 * Everything that comes back from storage is treated as hostile: a hand-edited
 * or half-written file must degrade to an empty history, never to a crash.
 */

const AnswerHistory = (function () {
  'use strict';

  const VERSION = 1;

  /**
   * Build an empty history.
   *
   * The question map has a null prototype so a question id like `constructor`
   * cannot collide with something inherited from `Object.prototype`.
   *
   * @returns {AnswerHistory} A history with no entries.
   */
  function empty() {
    return {
      version: VERSION,
      questions: /** @type {Record<string, HistoryEntry>} */ (Object.create(null))
    };
  }

  /**
   * Coerce an unknown value into a valid history.
   *
   * @param {unknown} raw - Whatever came out of storage.
   * @returns {AnswerHistory} A history holding only the entries that parsed.
   */
  function normalize(raw) {
    const result = empty();
    if (!raw || typeof raw !== 'object') {
      return result;
    }

    const source = /** @type {Record<string, unknown>} */ (raw);
    if (!source.questions || typeof source.questions !== 'object') {
      return result;
    }

    const entries = /** @type {Record<string, unknown>} */ (source.questions);
    Object.keys(entries).forEach(function (id) {
      const entry = entries[id];
      if (!entry || typeof entry !== 'object') {
        return;
      }
      const record = /** @type {Record<string, unknown>} */ (entry);
      result.questions[id] = {
        seen: typeof record.seen === 'number' ? record.seen : 0,
        correct: typeof record.correct === 'number' ? record.correct : 0,
        incorrect: typeof record.incorrect === 'number' ? record.incorrect : 0,
        lastCorrect: record.lastCorrect === true,
        lastAt: typeof record.lastAt === 'number' ? record.lastAt : 0
      };
    });

    return result;
  }

  /**
   * Read one entry.
   *
   * @param {AnswerHistory} history - The history to look in.
   * @param {string} questionId - The question to look up.
   * @returns {HistoryEntry | null} The entry, or null when the question was never answered.
   */
  function entryOf(history, questionId) {
    return history.questions[questionId] || null;
  }

  /**
   * Record an outcome and return a NEW history.
   *
   * @param {AnswerHistory} history - The current history. Never mutated.
   * @param {string} questionId - The question that was answered.
   * @param {boolean} correct - Whether the answer was right.
   * @param {number} now - Epoch milliseconds of the answer.
   * @returns {AnswerHistory} A new history with the outcome folded in.
   */
  function record(history, questionId, correct, now) {
    const result = empty();
    Object.keys(history.questions).forEach(function (id) {
      result.questions[id] = history.questions[id];
    });

    const previous = history.questions[questionId];
    result.questions[questionId] = {
      seen: (previous ? previous.seen : 0) + 1,
      correct: (previous ? previous.correct : 0) + (correct ? 1 : 0),
      incorrect: (previous ? previous.incorrect : 0) + (correct ? 0 : 1),
      lastCorrect: correct,
      lastAt: now
    };

    return result;
  }

  /**
   * Count how many of the given questions were ever answered.
   *
   * @param {AnswerHistory} history - The history to read.
   * @param {Question[]} questions - The questions to look up.
   * @returns {number} How many of them have at least one recorded answer.
   */
  function answeredCount(history, questions) {
    return questions.filter(function (question) {
      return Boolean(history.questions[question.id]);
    }).length;
  }

  /**
   * Aggregate the lifetime history per topic.
   *
   * @param {AnswerHistory} history - The history to read.
   * @param {Question[]} questions - The questions of the bank, which carry the topics.
   * @returns {Map<string, {correct: number, answered: number}>} One entry per topic that was ever answered.
   */
  function byTopic(history, questions) {
    /** @type {Map<string, {correct: number, answered: number}>} */
    const totals = new Map();
    questions.forEach(function (question) {
      const entry = history.questions[question.id];
      if (!entry) {
        return;
      }
      const current = totals.get(question.topic) || { correct: 0, answered: 0 };
      current.correct += entry.correct;
      current.answered += entry.correct + entry.incorrect;
      totals.set(question.topic, current);
    });
    return totals;
  }

  return { VERSION, empty, normalize, entryOf, record, answeredCount, byTopic };
})();

/* The node test runner loads these classic scripts into a shared context, where
   a top-level `const` would not survive; the explicit assignment is what makes
   the namespace reachable from the tests. */
Object.assign(globalThis, { AnswerHistory });
