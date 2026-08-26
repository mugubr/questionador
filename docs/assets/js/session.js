// @ts-check

/**
 * The session: filtering, drawing, grading and scoring.
 *
 * Nothing here touches the DOM or `localStorage`, which is exactly why this
 * boundary exists — it is the layer the tests can drive. Every function
 * returns a NEW value: neither the loaded bank nor the previous state of the
 * session is ever mutated.
 */
const Session = (function () {
  'use strict';

  const VERSION = 1;

  /** @type {OptionLetter[]} The letters, in the order a paper prints them. */
  const LETTERS = ['a', 'b', 'c', 'd'];

  /**
   * Report whether a question carries a given defect of the source paper.
   *
   * @param {Question} question - The question to inspect.
   * @param {string} defect - The defect name, as the bank spells it.
   * @returns {boolean} True when the bank records that defect.
   */
  function hasDefect(question, defect) {
    return (
      Array.isArray(question.knownDefects) &&
      question.knownDefects.indexOf(defect) !== -1
    );
  }

  /**
   * Report whether a question can be graded at all.
   *
   * `AV2-POL-Q14` was annulled in the official key: it has no `answer.letter`
   * and no correct option exists. It can still be read — it is a real question
   * from a real paper — but nothing about it can be right or wrong, so it never
   * enters the score.
   *
   * @param {Question | null} question - The question to inspect.
   * @returns {boolean} True when the bank records a correct letter for it.
   */
  function isGradable(question) {
    return Boolean(question && question.answer && question.answer.letter);
  }

  /**
   * List the distinct topics of a set of questions.
   *
   * @param {Question[]} questions - The questions to scan.
   * @returns {string[]} The topics, sorted alphabetically.
   */
  function topicsOf(questions) {
    /** @type {Set<string>} */
    const topics = new Set();
    questions.forEach(function (question) {
      topics.add(question.topic);
    });
    return Array.from(topics).sort();
  }

  /**
   * Report whether a question passes the history criterion.
   *
   * "Só as que errei" means the most recent answer was wrong, not "was ever
   * wrong": a question answered wrong and then right is no longer pending.
   *
   * @param {Question} question - The question to test.
   * @param {HistoryFilter} rule - The criterion to apply.
   * @param {AnswerHistory | null} history - A history from AnswerHistory.normalize, or null.
   * @returns {boolean} True when the question passes.
   */
  function passesHistory(question, rule, history) {
    if (rule === 'all') {
      return true;
    }
    const entry = history ? history.questions[question.id] : undefined;
    if (rule === 'unanswered') {
      return !entry;
    }
    return entry ? !entry.lastCorrect : false;
  }

  /**
   * Apply the filters.
   *
   * An empty list means "do not filter by this criterion" — never "no result".
   *
   * @param {Question[]} questions - The whole bank.
   * @param {FilterCriteria} criteria - The criteria to apply.
   * @param {AnswerHistory | null} history - A history from AnswerHistory.normalize, or null.
   * @returns {Question[]} The questions that pass, in bank order.
   */
  function filter(questions, criteria, history) {
    return questions.filter(function (question) {
      /* An annulled question and a booklet's own repeats stay in the bank —
         the exclusion is a property of the draw, not a deletion — but they are
         out of it unless the user asks for them by name. */
      if (!criteria.includeExcluded && question.excludedReason) {
        return false;
      }
      if (criteria.exams.length && criteria.exams.indexOf(question.exam) === -1) {
        return false;
      }
      if (criteria.topics.length && criteria.topics.indexOf(question.topic) === -1) {
        return false;
      }
      return passesHistory(question, criteria.history, history);
    });
  }

  /**
   * Fisher-Yates over a COPY: the array received is never altered.
   *
   * @template T
   * @param {T[]} items - The items to shuffle.
   * @param {() => number} [random] - Source of randomness, for deterministic tests.
   * @returns {T[]} A new, shuffled array.
   */
  function shuffle(items, random) {
    const pick = random || Math.random;
    const deck = items.slice();
    for (let i = deck.length - 1; i > 0; i -= 1) {
      const j = Math.floor(pick() * (i + 1));
      const swap = deck[i];
      deck[i] = deck[j];
      deck[j] = swap;
    }
    return deck;
  }

  /**
   * Create a session out of the filtered, shuffled and truncated pool.
   *
   * @param {Question[]} questions - The whole bank.
   * @param {FilterCriteria} criteria - The filters to apply first.
   * @param {AnswerHistory | null} history - A history from AnswerHistory.normalize, or null.
   * @param {{signature: string, size: number, shuffleOptions: boolean, now?: number, random?: () => number}} settings
   *   `size` of 0 means "every question that matches"; `shuffleOptions` decides
   *   whether the four options are presented in the order the paper prints them.
   * @returns {Session | null} The new session, or null when the filters match nothing.
   */
  function create(questions, criteria, history, settings) {
    const pool = filter(questions, criteria, history);
    if (!pool.length) {
      return null;
    }

    const random = settings.random || Math.random;
    const drawn = shuffle(pool, random);
    const deck = settings.size > 0 ? drawn.slice(0, settings.size) : drawn;

    /** @type {Record<string, OptionLetter[]>} */
    const orders = Object.create(null);
    deck.forEach(function (question) {
      orders[question.id] = settings.shuffleOptions
        ? shuffle(LETTERS, random)
        : LETTERS.slice();
    });

    return {
      version: VERSION,
      signature: settings.signature,
      deck: deck.map(function (question) {
        return question.id;
      }),
      position: 0,
      answers: /** @type {Record<string, AnswerRecord>} */ (Object.create(null)),
      orders,
      correctCount: 0,
      incorrectCount: 0,
      startedAt: settings.now || Date.now()
    };
  }

  /**
   * Give the order in which a question's options are presented.
   *
   * @param {Session} session - The session that drew the question.
   * @param {Question} question - The question being presented.
   * @returns {OptionLetter[]} The source letters, in display order.
   */
  function presentedOrder(session, question) {
    const stored = session.orders[question.id];
    return Array.isArray(stored) && stored.length === LETTERS.length
      ? stored
      : LETTERS.slice();
  }

  /**
   * Give the question at the current position.
   *
   * @param {Session | null} session - The session to read.
   * @param {Map<string, Question>} byId - The bank, indexed by id.
   * @returns {Question | null} The current question, or null when the deck is spent.
   */
  function currentQuestion(session, byId) {
    if (!session || session.position >= session.deck.length) {
      return null;
    }
    return byId.get(session.deck[session.position]) || null;
  }

  /**
   * Report whether the deck is spent.
   *
   * @param {Session | null} session - The session to read.
   * @returns {boolean} True when there is no question left to show.
   */
  function isFinished(session) {
    return !session || session.position >= session.deck.length;
  }

  /**
   * Count the questions of the deck that are still unanswered.
   *
   * Deliberately not "cards left in the deck": the scoreboard reads "restantes"
   * and must drop the moment a question is graded, not one click later when
   * the position advances.
   *
   * @param {Session | null} session - The session to read.
   * @returns {number} How many questions are still waiting for an answer.
   */
  function unansweredCount(session) {
    if (!session) {
      return 0;
    }
    return Math.max(0, session.deck.length - answeredCount(session));
  }

  /**
   * Count the questions already graded.
   *
   * @param {Session | null} session - The session to read.
   * @returns {number} How many questions were answered.
   */
  function answeredCount(session) {
    if (!session) {
      return 0;
    }
    return session.correctCount + session.incorrectCount;
  }

  /**
   * Report whether a chosen letter counts as correct.
   *
   * AV2-MET-Q14 prints the same text as options `a` and `d`, so the paper
   * really offers three answers. When the bank flags that defect, the twin of
   * the keyed option grades as correct too — otherwise the student would be
   * marked wrong for choosing a string identical to the answer key.
   *
   * @param {Question} question - The question being graded.
   * @param {OptionLetter} letter - The chosen letter, as the bank spells it.
   * @returns {boolean} True when the choice matches the answer key.
   */
  function isCorrectChoice(question, letter) {
    const keyed = question.answer.letter;
    if (!keyed) {
      return false;
    }
    if (letter === keyed) {
      return true;
    }
    if (!hasDefect(question, 'identical-options')) {
      return false;
    }
    return question.options[letter] === question.options[keyed];
  }

  /**
   * Read the grade recorded for a question.
   *
   * @param {Session | null} session - The session to read.
   * @param {Question | null} question - The question to look up.
   * @returns {AnswerRecord | null} The record, or null when the question is not graded.
   */
  function recordOf(session, question) {
    if (!session || !question) {
      return null;
    }
    return session.answers[question.id] || null;
  }

  /**
   * Report whether a question was already graded.
   *
   * @param {Session | null} session - The session to read.
   * @param {Question | null} question - The question to look up.
   * @returns {boolean} True when a grade is recorded.
   */
  function isAnswered(session, question) {
    return recordOf(session, question) !== null;
  }

  /**
   * Grade a choice and return a NEW session.
   *
   * A question that was already graded does not accept a second choice: the
   * session is returned unchanged.
   *
   * @param {Session} session - The current session. Never mutated.
   * @param {Question} question - The question being answered.
   * @param {OptionLetter} letter - The chosen letter, as the bank spells it.
   * @returns {Session} A new session with the grade applied, or the same one.
   */
  function answer(session, question, letter) {
    if (!session || !question || LETTERS.indexOf(letter) === -1) {
      return session;
    }
    /* An annulled question has no right answer, so recording a choice for it
       would mean scoring the student against nothing. */
    if (!isGradable(question)) {
      return session;
    }
    if (session.answers[question.id]) {
      return session;
    }

    const correct = isCorrectChoice(question, letter);

    /** @type {Record<string, AnswerRecord>} */
    const answers = Object.create(null);
    Object.keys(session.answers).forEach(function (id) {
      answers[id] = session.answers[id];
    });
    answers[question.id] = { chosen: letter, correct };

    return Object.assign({}, session, {
      answers,
      correctCount: session.correctCount + (correct ? 1 : 0),
      incorrectCount: session.incorrectCount + (correct ? 0 : 1)
    });
  }

  /**
   * Move one position forward, but only over a question that was graded.
   *
   * @param {Session} session - The current session. Never mutated.
   * @param {Question | null} question - The question currently on screen.
   * @returns {Session} A new session one position ahead, or the same one.
   */
  function advance(session, question) {
    if (!session) {
      return session;
    }
    /* A question that cannot be graded can never be "answered", so it would
       otherwise trap the session on its own position forever. */
    if (!isAnswered(session, question) && isGradable(question)) {
      return session;
    }
    return Object.assign({}, session, { position: session.position + 1 });
  }

  /**
   * Collect the questions to review, in the order they were drawn.
   *
   * @param {Session} session - The finished session.
   * @param {Map<string, Question>} byId - The bank, indexed by id.
   * @param {boolean} includeCorrect - Whether to include the questions that were right.
   * @returns {ReviewEntry[]} One entry per graded question that qualifies.
   */
  function reviewEntries(session, byId, includeCorrect) {
    /** @type {ReviewEntry[]} */
    const entries = [];
    session.deck.forEach(function (id) {
      const record = session.answers[id];
      const question = byId.get(id);
      if (!record || !question) {
        return;
      }
      if (record.correct && !includeCorrect) {
        return;
      }
      entries.push({ question, chosen: record.chosen, correct: record.correct });
    });
    return entries;
  }

  /**
   * Summarize the session by topic.
   *
   * @param {Session} session - The finished session.
   * @param {Map<string, Question>} byId - The bank, indexed by id.
   * @returns {TopicStat[]} One entry per topic answered, sorted by topic.
   */
  function topicStats(session, byId) {
    /** @type {Map<string, TopicStat>} */
    const totals = new Map();
    session.deck.forEach(function (id) {
      const record = session.answers[id];
      const question = byId.get(id);
      if (!record || !question) {
        return;
      }
      const current = totals.get(question.topic) || {
        topic: question.topic,
        correct: 0,
        answered: 0
      };
      current.correct += record.correct ? 1 : 0;
      current.answered += 1;
      totals.set(question.topic, current);
    });
    return Array.from(totals.values()).sort(function (left, right) {
      return left.topic.localeCompare(right.topic, 'pt-BR');
    });
  }

  /**
   * Report whether a stored session still describes the loaded bank.
   *
   * The signature is the cheap check; verifying every drawn id against the
   * bank is the one that actually protects the render, because a rebuilt bank
   * can drop or renumber a question.
   *
   * @param {Session | null} session - The stored session.
   * @param {Map<string, Question>} byId - The loaded bank, indexed by id.
   * @param {string} signature - The signature of the loaded bank.
   * @returns {boolean} True when the session can safely be resumed.
   */
  function matchesBank(session, byId, signature) {
    if (!session || session.version !== VERSION || session.signature !== signature) {
      return false;
    }
    if (!Array.isArray(session.deck) || session.deck.length === 0) {
      return false;
    }
    return session.deck.every(function (id) {
      return byId.has(id);
    });
  }

  /**
   * Coerce a stored value back into a session.
   *
   * `JSON.parse` hands back plain objects that inherit from
   * `Object.prototype`, so a question id of `constructor` would read as an
   * answer that was never given. The maps are rebuilt without a prototype.
   *
   * The two counters are recomputed rather than trusted, because this function
   * drops the answer records it cannot parse: keeping the stored totals would
   * leave a scoreboard counting answers that no longer exist, and "restantes"
   * is derived from them.
   *
   * @param {unknown} raw - Whatever came out of storage.
   * @returns {Session | null} The session, or null when the value is unusable.
   */
  function fromStored(raw) {
    if (!raw || typeof raw !== 'object') {
      return null;
    }
    const stored = /** @type {Record<string, unknown>} */ (raw);
    if (!Array.isArray(stored.deck) || typeof stored.position !== 'number') {
      return null;
    }

    /** @type {Record<string, AnswerRecord>} */
    const answers = Object.create(null);
    if (stored.answers && typeof stored.answers === 'object') {
      const source = /** @type {Record<string, AnswerRecord>} */ (stored.answers);
      Object.keys(source).forEach(function (id) {
        const record = source[id];
        if (
          record &&
          typeof record === 'object' &&
          LETTERS.indexOf(record.chosen) !== -1
        ) {
          answers[id] = { chosen: record.chosen, correct: record.correct === true };
        }
      });
    }

    /** @type {Record<string, OptionLetter[]>} */
    const orders = Object.create(null);
    if (stored.orders && typeof stored.orders === 'object') {
      const source = /** @type {Record<string, OptionLetter[]>} */ (stored.orders);
      Object.keys(source).forEach(function (id) {
        const order = source[id];
        if (Array.isArray(order) && order.length === LETTERS.length) {
          orders[id] = order;
        }
      });
    }

    const graded = Object.keys(answers);
    const correctCount = graded.filter(function (id) {
      return answers[id].correct;
    }).length;

    return {
      version: typeof stored.version === 'number' ? stored.version : 0,
      signature: typeof stored.signature === 'string' ? stored.signature : '',
      deck: stored.deck.filter(function (id) {
        return typeof id === 'string';
      }),
      position: stored.position,
      answers,
      orders,
      correctCount,
      incorrectCount: graded.length - correctCount,
      startedAt: typeof stored.startedAt === 'number' ? stored.startedAt : 0
    };
  }

  return {
    VERSION,
    LETTERS,
    hasDefect,
    isGradable,
    topicsOf,
    filter,
    shuffle,
    create,
    presentedOrder,
    currentQuestion,
    isFinished,
    unansweredCount,
    answeredCount,
    isCorrectChoice,
    recordOf,
    isAnswered,
    answer,
    advance,
    reviewEntries,
    topicStats,
    matchesBank,
    fromStored
  };
})();

/* The node test runner loads these classic scripts into a shared context, where
   a top-level `const` would not survive; the explicit assignment is what makes
   the namespace reachable from the tests. */
Object.assign(globalThis, { Session });
