// @ts-check

/**
 * Tests for `docs/assets/js/bank.js`.
 *
 * The bank ships with the app, but it is still validated on every start: the
 * validator is the guard against a stale or hand-edited file, and it produces
 * the message the student reads. The first test here is the app-side golden —
 * the committed bank has to load, or the site opens to an error page.
 */

'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { loadAppScript, makeQuestion, publishedBank } = require('./helpers.js');

const { Bank } = loadAppScript('bank.js', ['Bank']);

/**
 * Wrap questions in the smallest bank the app-side validator accepts.
 *
 * @param {any[]} questions - The questions to publish.
 * @param {Record<string, any>} [overrides] - Root fields to replace.
 * @returns {any} The candidate bank.
 */
function makeBank(questions, overrides) {
  return Object.assign(
    {
      version: 1,
      generatedAt: '2026-08-26',
      exams: [{ id: 'ENA26', title: 'Exame Nacional de Acesso' }],
      topics: [{ id: 'patente', label: 'Patente', definition: 'Sobre patentes.' }],
      questions
    },
    overrides || {}
  );
}

// ---------------------------------------------------------------------------
// The committed bank has to load
// ---------------------------------------------------------------------------

test('the published bank loads without an error', function () {
  const result = Bank.validate(publishedBank());

  assert.equal(result.error, undefined, String(result.error));
  assert.ok(result.bank);
  assert.equal(result.bank.questions.length, 144);
});

test('the published bank is indexed by a Map, not an object literal', function () {
  /* The keys come from data: an id of `constructor` must not resolve to
     something inherited from Object.prototype. */
  const bank = publishedBank();
  const index = Bank.indexById(bank.questions);

  assert.ok(index instanceof Map);
  assert.equal(index.size, bank.questions.length);
  assert.equal(index.get('constructor'), undefined);
  assert.equal(index.get('ENA26-Q01').id, 'ENA26-Q01');
});

test('the exams and the topics are indexed by Maps too', function () {
  const bank = publishedBank();

  assert.equal(Bank.examsById(bank).get('ENA26').id, 'ENA26');
  assert.equal(Bank.examsById(bank).get('constructor'), undefined);
  assert.equal(Bank.topicsById(bank).get('constructor'), undefined);
  assert.equal(Bank.topicsById(bank).size, bank.topics.length);
});

test('every topic a published question names is declared in the taxonomy', function () {
  const bank = publishedBank();
  const declared = Bank.topicsById(bank);
  const undeclared = bank.questions
    .filter(function (question) {
      return !declared.has(question.topic);
    })
    .map(function (question) {
      return question.id;
    });

  assert.deepEqual(undeclared, []);
});

// ---------------------------------------------------------------------------
// The letter is allowed to be missing in exactly one case
// ---------------------------------------------------------------------------

test('a question with no letter is accepted only when it is excluded', function () {
  /* AV2-POL-Q14 was annulled by the official key: it has no correct option at
     all, and the app has to load anyway. */
  const annulled = makeQuestion({
    excludedReason: 'annulled',
    answer: { source: 'official', reference: 'Gabarito-Final_AV2-POL.pdf' }
  });

  assert.equal(Bank.validate(makeBank([annulled])).error, undefined);
});

test('a question with no letter and no reason is rejected', function () {
  const question = makeQuestion({
    answer: { source: 'official', reference: 'Gabarito-Final_ENA26.pdf' }
  });
  const result = Bank.validate(makeBank([question]));

  assert.ok(result.error);
  assert.equal(result.bank, undefined);
});

test('a letter outside a-d is rejected even on an excluded question', function () {
  const question = makeQuestion({
    excludedReason: 'annulled',
    answer: { letter: 'e', source: 'official', reference: 'Gabarito.pdf' }
  });

  assert.ok(Bank.validate(makeBank([question])).error);
});

test('an excludedReason outside the enum is rejected', function () {
  const question = makeQuestion({ excludedReason: 'porque-sim' });
  assert.ok(Bank.validate(makeBank([question])).error);
});

// ---------------------------------------------------------------------------
// Everything the app needs to render and grade
// ---------------------------------------------------------------------------

test('a missing option is rejected', function () {
  const question = makeQuestion({
    options: { a: 'Um.', b: 'Dois.', c: 'Tres.' }
  });
  assert.ok(Bank.validate(makeBank([question])).error);
});

test('an option present but blank is rejected', function () {
  const question = makeQuestion({
    options: { a: 'Um.', b: '   ', c: 'Tres.', d: 'Quatro.' }
  });
  assert.ok(Bank.validate(makeBank([question])).error);
});

test('a question without a stem is rejected', function () {
  assert.ok(Bank.validate(makeBank([makeQuestion({ stem: '  ' })])).error);
});

test('a question without a topic is rejected', function () {
  assert.ok(Bank.validate(makeBank([makeQuestion({ topic: '' })])).error);
});

test('a question without a number is rejected', function () {
  assert.ok(Bank.validate(makeBank([makeQuestion({ number: '1' })])).error);
});

test('a repeated question id is rejected', function () {
  const result = Bank.validate(makeBank([makeQuestion(), makeQuestion()]));
  assert.ok(result.error);
});

test('an answer that is not an object is rejected', function () {
  assert.ok(Bank.validate(makeBank([makeQuestion({ answer: 'c' })])).error);
});

// ---------------------------------------------------------------------------
// The shape of the bank itself
// ---------------------------------------------------------------------------

test('a bank that is not an object is rejected', function () {
  assert.ok(Bank.validate(null).error);
  assert.ok(Bank.validate([]).error);
  assert.ok(Bank.validate('texto').error);
});

test('an unsupported version is rejected', function () {
  const result = Bank.validate(makeBank([makeQuestion()], { version: 2 }));
  assert.ok(result.error);
  assert.match(result.error, /2/);
});

test('the old Portuguese format is rejected by name', function () {
  const result = Bank.validate({ version: 1, questoes: [], provas: [] });
  assert.ok(result.error);
  assert.match(result.error, /python -m tools build/);
});

test('an empty exams or questions list is rejected', function () {
  assert.ok(Bank.validate(makeBank([makeQuestion()], { exams: [] })).error);
  assert.ok(Bank.validate(makeBank([])).error);
});

test('an exam without a title is rejected', function () {
  const bank = makeBank([makeQuestion()], { exams: [{ id: 'ENA26' }] });
  assert.ok(Bank.validate(bank).error);
});

test('topics that are not a list are rejected', function () {
  const bank = makeBank([makeQuestion()], { topics: {} });
  assert.ok(Bank.validate(bank).error);
});

// ---------------------------------------------------------------------------
// Parsing and identifying
// ---------------------------------------------------------------------------

test('invalid JSON is reported rather than thrown', function () {
  const result = Bank.parseText('{');
  assert.ok(result.error);
  assert.match(result.error, /JSON/);
});

test('valid JSON goes straight through the validator', function () {
  const result = Bank.parseText(JSON.stringify(makeBank([makeQuestion()])));
  assert.equal(result.error, undefined);
  assert.ok(result.bank);
});

test('the signature changes whenever the bank does', function () {
  const bank = makeBank([makeQuestion()]);
  const original = Bank.signature(bank);

  assert.equal(Bank.signature(bank), original);
  assert.notEqual(
    Bank.signature(Object.assign({}, bank, { generatedAt: '2026-08-27' })),
    original
  );
  assert.notEqual(
    Bank.signature(
      Object.assign({}, bank, { questions: [makeQuestion(), makeQuestion()] })
    ),
    original
  );
});

test('a bank with no build date still has a signature', function () {
  const bank = makeBank([makeQuestion()], { generatedAt: undefined });
  assert.equal(typeof Bank.signature(bank), 'string');
});
