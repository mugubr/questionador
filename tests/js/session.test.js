// @ts-check

/**
 * Tests for `docs/assets/js/session.js`.
 *
 * The session layer is pure — it touches neither the DOM nor `localStorage` —
 * which is exactly why this boundary exists: filtering, drawing, shuffling,
 * grading and scoring can all be driven from here.
 */

'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const {
  loadAppScript,
  makeCriteria,
  makeQuestion,
  makeSettings,
  publishedBank,
  seededRandom
} = require('./helpers.js');

const { Session } = loadAppScript('session.js', ['Session']);
const { AnswerHistory } = loadAppScript('preferences.js', [
  'Preferences',
  'AnswerHistory'
]);

/** A second question, so a deck can hold more than one card. */
const SECOND = makeQuestion({
  id: 'ENA26-Q02',
  number: 2,
  topic: 'marca-e-indicacao-geografica',
  answer: { letter: 'a', source: 'official', reference: 'Gabarito-Final_ENA26.pdf' }
});

/**
 * Draw a session over the given questions.
 *
 * @param {any[]} questions - The pool to draw from.
 * @param {Record<string, any>} [settings] - Settings to replace.
 * @param {Record<string, any>} [criteria] - Criteria to replace.
 * @returns {any} The new session.
 */
function draw(questions, settings, criteria) {
  return Session.create(
    questions,
    makeCriteria(criteria),
    null,
    makeSettings(settings)
  );
}

// ---------------------------------------------------------------------------
// Objects keyed by data-derived strings
// ---------------------------------------------------------------------------

test('a question whose id is "constructor" is not already answered', function () {
  /* Objects keyed by question id used `{}`, so an id of `constructor` read as
     truthy and the question appeared already-answered before any click. */
  const question = makeQuestion({ id: 'constructor' });
  const session = draw([question]);

  assert.equal(Session.isAnswered(session, question), false);
  assert.equal(Session.recordOf(session, question), null);
  assert.deepEqual(Session.presentedOrder(session, question), ['a', 'b', 'c', 'd']);
});

test('a session restored from JSON keeps a "constructor" id harmless', function () {
  const stored = JSON.parse(
    '{"version":1,"signature":"s","deck":["constructor"],"position":0,' +
      '"answers":{},"orders":{},"correctCount":0,"incorrectCount":0,"startedAt":1}'
  );
  const session = Session.fromStored(stored);
  const question = makeQuestion({ id: 'constructor' });

  assert.equal(Session.isAnswered(session, question), false);
  assert.deepEqual(Session.presentedOrder(session, question), ['a', 'b', 'c', 'd']);
});

test('grading a question named "toString" does not inherit an answer', function () {
  const question = makeQuestion({ id: 'toString' });
  const session = draw([question]);
  const graded = Session.answer(session, question, 'c');

  assert.equal(Session.isAnswered(session, question), false);
  assert.equal(Session.isAnswered(graded, question), true);
  assert.equal(graded.correctCount, 1);
});

test('a fresh history reports a "constructor" question as unanswered', function () {
  const question = makeQuestion({ id: 'constructor' });
  const history = AnswerHistory.normalize(JSON.parse('{"questions":{}}'));
  const criteria = makeCriteria({ history: 'unanswered' });

  assert.deepEqual(Session.filter([question], criteria, history), [question]);
});

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

test('an empty criterion list means "do not filter", never "no result"', function () {
  const pool = [makeQuestion(), SECOND];
  assert.deepEqual(Session.filter(pool, makeCriteria(), null), pool);
});

test('filtering by exam keeps only that paper', function () {
  const other = makeQuestion({ id: 'ENA25-Q01', exam: 'ENA25' });
  const pool = [makeQuestion(), other];
  /** @type {any[]} */
  const kept = Session.filter(pool, makeCriteria({ exams: ['ENA25'] }), null);

  assert.deepEqual(
    kept.map(function (question) {
      return question.id;
    }),
    ['ENA25-Q01']
  );
});

test('filtering by topic keeps only that topic', function () {
  const pool = [makeQuestion(), SECOND];
  const kept = Session.filter(pool, makeCriteria({ topics: ['patente'] }), null);

  assert.equal(kept.length, 1);
  assert.equal(kept[0].topic, 'patente');
});

test('"only the ones I got wrong" means the most recent answer, not ever', function () {
  /* A question answered wrong and then right is no longer pending. */
  const question = makeQuestion();
  let history = AnswerHistory.empty();
  history = AnswerHistory.record(history, question.id, false, 1);

  const criteria = makeCriteria({ history: 'incorrect' });
  assert.deepEqual(Session.filter([question], criteria, history), [question]);

  history = AnswerHistory.record(history, question.id, true, 2);
  assert.deepEqual(Session.filter([question], criteria, history), []);
});

test('"unanswered" drops every question that was ever answered', function () {
  const question = makeQuestion();
  const history = AnswerHistory.record(AnswerHistory.empty(), question.id, true, 1);
  const criteria = makeCriteria({ history: 'unanswered' });

  assert.deepEqual(Session.filter([question, SECOND], criteria, history), [SECOND]);
});

test('a history criterion with no history at all keeps everything unanswered', function () {
  const pool = [makeQuestion(), SECOND];
  const criteria = makeCriteria({ history: 'unanswered' });

  assert.deepEqual(Session.filter(pool, criteria, null), pool);
  assert.deepEqual(Session.filter(pool, makeCriteria({ history: 'incorrect' }), null), []);
});

// ---------------------------------------------------------------------------
// The questions that must never be drawn
// ---------------------------------------------------------------------------

test('an excluded question is never drawn by default', function () {
  const annulled = makeQuestion({
    id: 'AV2-POL-Q14',
    exam: 'AV2-POL',
    number: 14,
    excludedReason: 'annulled',
    answer: { source: 'official', reference: 'Gabarito-Final_AV2-POL.pdf' }
  });
  const pool = [makeQuestion(), annulled];

  assert.deepEqual(Session.filter(pool, makeCriteria(), null), [makeQuestion()]);
});

test('an excluded question is drawn only when it is asked for by name', function () {
  const reprint = makeQuestion({
    id: 'AV2-PI-Q14',
    exam: 'AV2-PI',
    number: 14,
    duplicateOf: 'AV2-PI-Q13',
    excludedReason: 'source-booklet-defect'
  });
  const criteria = makeCriteria({ includeExcluded: true });

  assert.equal(Session.filter([reprint], criteria, null).length, 1);
});

test('none of the published bank\'s excluded questions reach a default deck', function () {
  const bank = publishedBank();
  const excluded = bank.questions
    .filter(function (question) {
      return question.excludedReason;
    })
    .map(function (question) {
      return question.id;
    });

  assert.equal(excluded.length, 3);

  const session = draw(bank.questions);
  excluded.forEach(function (id) {
    assert.equal(session.deck.indexOf(id), -1, id + ' was drawn');
  });
});

// ---------------------------------------------------------------------------
// The annulled question has no letter at all
// ---------------------------------------------------------------------------

test('the annulled question of the published bank carries no letter', function () {
  const bank = publishedBank();
  const annulled = bank.questions.find(function (question) {
    return question.id === 'AV2-POL-Q14';
  });

  assert.ok(annulled, 'AV2-POL-Q14 is missing from the bank');
  assert.equal(annulled.answer.letter, undefined);
  assert.equal(annulled.excludedReason, 'annulled');
  assert.equal(Session.isGradable(annulled), false);
});

test('grading a question with no letter is never right and never throws', function () {
  const annulled = makeQuestion({
    excludedReason: 'annulled',
    answer: { source: 'official', reference: 'Gabarito-Final_AV2-POL.pdf' }
  });

  ['a', 'b', 'c', 'd'].forEach(function (letter) {
    assert.equal(Session.isCorrectChoice(annulled, letter), false);
  });
});

test('a question with no letter never enters the score', function () {
  const annulled = makeQuestion({
    excludedReason: 'annulled',
    answer: { source: 'official', reference: 'Gabarito-Final_AV2-POL.pdf' }
  });
  const session = draw([annulled], undefined, { includeExcluded: true });
  const after = Session.answer(session, annulled, 'a');

  assert.equal(after, session);
  assert.equal(after.correctCount, 0);
  assert.equal(after.incorrectCount, 0);
});

test('a question that cannot be graded does not trap the session', function () {
  const annulled = makeQuestion({
    excludedReason: 'annulled',
    answer: { source: 'official', reference: 'Gabarito-Final_AV2-POL.pdf' }
  });
  const session = draw([annulled], undefined, { includeExcluded: true });

  assert.equal(Session.advance(session, annulled).position, 1);
});

// ---------------------------------------------------------------------------
// Shuffling
// ---------------------------------------------------------------------------

test('shuffling returns a new array and never touches the one it was given', function () {
  const source = ['a', 'b', 'c', 'd'];
  const shuffled = Session.shuffle(source, seededRandom(3));

  assert.notEqual(shuffled, source);
  assert.deepEqual(source, ['a', 'b', 'c', 'd']);
  assert.deepEqual(shuffled.slice().sort(), ['a', 'b', 'c', 'd']);
});

test('shuffling the options remaps which display slot holds the answer', function () {
  /* The order stores SOURCE letters in display order, so grading has to go
     back through it. Grading the display letter instead marks the student
     wrong for clicking the answer. */
  const question = makeQuestion();
  const session = draw([question], { shuffleOptions: true, random: seededRandom(11) });
  /** @type {string[]} */
  const order = Session.presentedOrder(session, question);

  assert.deepEqual(order.slice().sort(), ['a', 'b', 'c', 'd']);
  assert.notDeepEqual(order, Session.LETTERS);

  order.forEach(function (sourceLetter, displayIndex) {
    const isTheAnswer = sourceLetter === question.answer.letter;
    assert.equal(Session.isCorrectChoice(question, sourceLetter), isTheAnswer);
    /* What the student reads in that slot is the source option, not the
       option that happens to share the slot's own letter. */
    assert.equal(
      question.options[sourceLetter],
      question.options[order[displayIndex]]
    );
  });
});

test('answering through the presented order scores the shuffled question', function () {
  const question = makeQuestion();
  const session = draw([question], { shuffleOptions: true, random: seededRandom(11) });
  const order = Session.presentedOrder(session, question);
  const displayIndex = order.indexOf(question.answer.letter);

  const graded = Session.answer(session, question, order[displayIndex]);

  assert.equal(graded.correctCount, 1);
  assert.equal(graded.incorrectCount, 0);
  assert.equal(Session.recordOf(graded, question).chosen, question.answer.letter);
});

test('every drawn question gets its own presented order', function () {
  const session = draw([makeQuestion(), SECOND], {
    shuffleOptions: true,
    random: seededRandom(5)
  });

  assert.equal(Object.keys(session.orders).length, 2);
  assert.equal(session.orders['ENA26-Q01'].length, 4);
  assert.equal(session.orders['ENA26-Q02'].length, 4);
});

test('the printed order is kept when shuffling is off', function () {
  const session = draw([makeQuestion()], { shuffleOptions: false });
  assert.deepEqual(Session.presentedOrder(session, makeQuestion()), ['a', 'b', 'c', 'd']);
});

test('shuffling never rewrites the shared letter table', function () {
  draw([makeQuestion(), SECOND], { shuffleOptions: true, random: seededRandom(9) });
  assert.deepEqual(Session.LETTERS, ['a', 'b', 'c', 'd']);
});

test('a stored order of the wrong length falls back to the printed one', function () {
  const session = draw([makeQuestion()]);
  session.orders['ENA26-Q01'] = ['a', 'b'];

  assert.deepEqual(Session.presentedOrder(session, makeQuestion()), ['a', 'b', 'c', 'd']);
});

// ---------------------------------------------------------------------------
// The two identical options of AV2-MET-Q14
// ---------------------------------------------------------------------------

test('AV2-MET-Q14 really does print the same string twice', function () {
  const bank = publishedBank();
  const defective = bank.questions.find(function (question) {
    return question.id === 'AV2-MET-Q14';
  });

  assert.ok(defective, 'AV2-MET-Q14 is missing from the bank');
  assert.equal(defective.options.a, defective.options.d);
  assert.deepEqual(defective.knownDefects, ['identical-options']);
  assert.equal(Session.hasDefect(defective, 'identical-options'), true);
});

test('a twin of the keyed option grades as correct', function () {
  /* Otherwise the student is marked wrong for choosing a string identical to
     the answer key. */
  const question = makeQuestion({
    options: { a: 'Mesma coisa.', b: 'Outra.', c: 'Terceira.', d: 'Mesma coisa.' },
    answer: { letter: 'a', source: 'official', reference: 'Gabarito-Final.pdf' },
    knownDefects: ['identical-options']
  });

  assert.equal(Session.isCorrectChoice(question, 'a'), true);
  assert.equal(Session.isCorrectChoice(question, 'd'), true);
  assert.equal(Session.isCorrectChoice(question, 'b'), false);
});

test('a twin that is not the keyed option is still wrong', function () {
  const bank = publishedBank();
  const defective = bank.questions.find(function (question) {
    return question.id === 'AV2-MET-Q14';
  });

  assert.equal(Session.isCorrectChoice(defective, defective.answer.letter), true);
  assert.equal(Session.isCorrectChoice(defective, 'a'), false);
  assert.equal(Session.isCorrectChoice(defective, 'd'), false);
});

test('identical options do not grade as correct without the recorded defect', function () {
  const question = makeQuestion({
    options: { a: 'Mesma coisa.', b: 'Outra.', c: 'Terceira.', d: 'Mesma coisa.' },
    answer: { letter: 'a', source: 'official', reference: 'Gabarito-Final.pdf' }
  });

  assert.equal(Session.isCorrectChoice(question, 'd'), false);
});

// ---------------------------------------------------------------------------
// Drawing a deck
// ---------------------------------------------------------------------------

test('a size of zero draws every question that matches', function () {
  const session = draw([makeQuestion(), SECOND], { size: 0 });
  assert.equal(session.deck.length, 2);
});

test('a positive size truncates the deck', function () {
  const session = draw([makeQuestion(), SECOND], { size: 1 });
  assert.equal(session.deck.length, 1);
});

test('filters that match nothing produce no session at all', function () {
  const session = draw([makeQuestion()], undefined, { exams: ['ENA18'] });
  assert.equal(session, null);
});

test('a new session starts unanswered, at the top of its deck', function () {
  const session = draw([makeQuestion(), SECOND]);

  assert.equal(session.version, Session.VERSION);
  assert.equal(session.position, 0);
  assert.equal(session.correctCount, 0);
  assert.equal(session.incorrectCount, 0);
  assert.equal(session.startedAt, 1700000000000);
  assert.equal(Session.isFinished(session), false);
});

// ---------------------------------------------------------------------------
// Grading and scoring
// ---------------------------------------------------------------------------

test('grading returns a new session and never mutates the old one', function () {
  const question = makeQuestion();
  const session = draw([question]);
  const graded = Session.answer(session, question, 'c');

  assert.notEqual(graded, session);
  assert.equal(session.correctCount, 0);
  assert.equal(Session.isAnswered(session, question), false);
  assert.equal(graded.correctCount, 1);
  assert.deepEqual(Session.recordOf(graded, question), { chosen: 'c', correct: true });
});

test('a wrong choice is recorded as the letter the student picked', function () {
  const question = makeQuestion();
  const graded = Session.answer(draw([question]), question, 'a');

  assert.equal(graded.incorrectCount, 1);
  assert.deepEqual(Session.recordOf(graded, question), { chosen: 'a', correct: false });
});

test('a graded question does not accept a second choice', function () {
  const question = makeQuestion();
  const graded = Session.answer(draw([question]), question, 'a');
  const again = Session.answer(graded, question, 'c');

  assert.equal(again, graded);
  assert.equal(again.correctCount, 0);
  assert.equal(again.incorrectCount, 1);
});

test('a letter outside a-d is not a choice', function () {
  const question = makeQuestion();
  const session = draw([question]);

  assert.equal(Session.answer(session, question, 'e'), session);
  assert.equal(Session.answer(session, question, 'C'), session);
});

test('"restantes" drops the moment a question is graded', function () {
  /* Deliberately not "cards left in the deck": the scoreboard must fall on the
     click that grades, not one click later when the position advances. */
  const question = makeQuestion();
  const session = draw([question, SECOND]);

  assert.equal(Session.unansweredCount(session), 2);
  const graded = Session.answer(session, question, 'c');
  assert.equal(Session.unansweredCount(graded), 1);
  assert.equal(Session.answeredCount(graded), 1);
  assert.equal(graded.position, 0);
});

test('the deck advances only over a question that was graded', function () {
  const question = makeQuestion();
  const session = draw([question, SECOND]);

  assert.equal(Session.advance(session, question), session);
  const graded = Session.answer(session, question, 'c');
  assert.equal(Session.advance(graded, question).position, 1);
});

test('a spent deck is finished and has no current question', function () {
  const session = draw([makeQuestion()]);
  const spent = Object.assign({}, session, { position: 1 });
  const byId = new Map([['ENA26-Q01', makeQuestion()]]);

  assert.equal(Session.isFinished(spent), true);
  assert.equal(Session.currentQuestion(spent, byId), null);
  assert.equal(Session.currentQuestion(session, byId).id, 'ENA26-Q01');
});

test('a deck card the bank no longer holds resolves to nothing', function () {
  const session = draw([makeQuestion()]);
  assert.equal(Session.currentQuestion(session, new Map()), null);
});

test('counts of a session that does not exist are zero', function () {
  assert.equal(Session.answeredCount(null), 0);
  assert.equal(Session.unansweredCount(null), 0);
  assert.equal(Session.isFinished(null), true);
  assert.equal(Session.isAnswered(null, makeQuestion()), false);
});

// ---------------------------------------------------------------------------
// Review and statistics
// ---------------------------------------------------------------------------

test('the review lists the graded questions in the order they were drawn', function () {
  const first = makeQuestion();
  const session = draw([first, SECOND], { size: 0, shuffleOptions: false });
  const byId = new Map([
    ['ENA26-Q01', first],
    ['ENA26-Q02', SECOND]
  ]);

  let graded = Session.answer(session, first, 'a');
  graded = Session.answer(graded, SECOND, 'a');

  /** @type {any[]} */
  const wrongOnly = Session.reviewEntries(graded, byId, false);
  assert.deepEqual(
    wrongOnly.map(function (entry) {
      return entry.question.id;
    }),
    ['ENA26-Q01']
  );

  /** @type {any[]} */
  const everything = Session.reviewEntries(graded, byId, true);
  assert.deepEqual(
    everything.map(function (entry) {
      return entry.question.id;
    }),
    graded.deck
  );
});

test('the review skips a question that was never graded', function () {
  const first = makeQuestion();
  const session = draw([first, SECOND]);
  const byId = new Map([
    ['ENA26-Q01', first],
    ['ENA26-Q02', SECOND]
  ]);

  const graded = Session.answer(session, first, 'a');
  assert.equal(Session.reviewEntries(graded, byId, true).length, 1);
});

test('the statistics group the session by topic, sorted', function () {
  const first = makeQuestion();
  const session = draw([first, SECOND]);
  const byId = new Map([
    ['ENA26-Q01', first],
    ['ENA26-Q02', SECOND]
  ]);

  let graded = Session.answer(session, first, 'c');
  graded = Session.answer(graded, SECOND, 'b');

  assert.deepEqual(Session.topicStats(graded, byId), [
    { topic: 'marca-e-indicacao-geografica', correct: 0, answered: 1 },
    { topic: 'patente', correct: 1, answered: 1 }
  ]);
});

test('the topics of a set of questions are listed once, sorted', function () {
  const pool = [makeQuestion(), SECOND, makeQuestion({ id: 'ENA26-Q03' })];
  assert.deepEqual(Session.topicsOf(pool), [
    'marca-e-indicacao-geografica',
    'patente'
  ]);
});

// ---------------------------------------------------------------------------
// Resuming a stored session
// ---------------------------------------------------------------------------

test('a session survives being written out and read back', function () {
  /* A session used to be saved on every answer and never read back, so the
     progress it recorded could not be resumed. */
  const question = makeQuestion();
  const byId = new Map([
    ['ENA26-Q01', question],
    ['ENA26-Q02', SECOND]
  ]);
  const signature = '1:2026-08-26:144';

  const session = draw([question, SECOND], { shuffleOptions: true, signature });
  let graded = Session.answer(session, question, 'c');
  graded = Session.advance(graded, question);

  const restored = Session.fromStored(JSON.parse(JSON.stringify(graded)));

  assert.equal(Session.matchesBank(restored, byId, signature), true);
  assert.deepEqual(restored.deck, graded.deck);
  assert.equal(restored.position, graded.position);
  assert.equal(restored.correctCount, 1);
  assert.equal(Session.isAnswered(restored, question), true);
  assert.deepEqual(
    Session.presentedOrder(restored, question),
    Session.presentedOrder(graded, question)
  );
});

test('a stored session is refused when the bank changed', function () {
  const question = makeQuestion();
  const byId = new Map([['ENA26-Q01', question]]);
  const session = draw([question], { signature: 'antiga' });

  assert.equal(Session.matchesBank(session, byId, 'nova'), false);
});

test('a stored session is refused when its version is not this one', function () {
  const question = makeQuestion();
  const byId = new Map([['ENA26-Q01', question]]);
  const session = Object.assign({}, draw([question]), { version: 0 });

  assert.equal(Session.matchesBank(session, byId, session.signature), false);
});

test('a stored session is refused when a drawn question is gone', function () {
  const question = makeQuestion();
  const session = draw([question]);

  assert.equal(Session.matchesBank(session, new Map(), session.signature), false);
});

test('an empty deck is never resumable', function () {
  const session = Object.assign({}, draw([makeQuestion()]), { deck: [] });
  assert.equal(Session.matchesBank(session, new Map(), session.signature), false);
});

test('a stored value that is not a session at all is refused', function () {
  assert.equal(Session.fromStored(null), null);
  assert.equal(Session.fromStored('texto'), null);
  assert.equal(Session.fromStored({}), null);
  assert.equal(Session.fromStored({ deck: [], position: 'zero' }), null);
});

test('a stored session drops the entries that did not parse', function () {
  const restored = Session.fromStored({
    version: 1,
    signature: 's',
    deck: ['ENA26-Q01', 7, null],
    position: 0,
    answers: {
      'ENA26-Q01': { chosen: 'c', correct: true },
      'ENA26-Q02': { chosen: 'z', correct: true },
      'ENA26-Q03': 'nao e um registro'
    },
    orders: {
      'ENA26-Q01': ['d', 'c', 'b', 'a'],
      'ENA26-Q02': ['a', 'b']
    },
    correctCount: 1,
    incorrectCount: 0,
    startedAt: 5
  });

  assert.deepEqual(restored.deck, ['ENA26-Q01']);
  assert.deepEqual(Object.keys(restored.answers), ['ENA26-Q01']);
  assert.deepEqual(Object.keys(restored.orders), ['ENA26-Q01']);
});

test('a stored session with missing counters falls back to zero', function () {
  const restored = Session.fromStored({ deck: ['ENA26-Q01'], position: 0 });

  assert.equal(restored.version, 0);
  assert.equal(restored.signature, '');
  assert.equal(restored.correctCount, 0);
  assert.equal(restored.incorrectCount, 0);
  assert.equal(restored.startedAt, 0);
});
