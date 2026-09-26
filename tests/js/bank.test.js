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

const Bank = loadAppScript('bank.js', 'Bank');

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
// The committed bank has to load.
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
// The letter is allowed to be missing in exactly one case.
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

  assert.match(result.error, /excludedReason/);
  assert.equal(result.bank, undefined);
});

test('a letter outside a-d is rejected even on an excluded question', function () {
  const question = makeQuestion({
    excludedReason: 'annulled',
    answer: { letter: 'e', source: 'official', reference: 'Gabarito.pdf' }
  });

  assert.match(Bank.validate(makeBank([question])).error, /a, b, c ou d/);
});

test('an excludedReason outside the enum is rejected', function () {
  const question = makeQuestion({ excludedReason: 'porque-sim' });
  assert.match(Bank.validate(makeBank([question])).error, /excludedReason/);
});

// ---------------------------------------------------------------------------
// Everything the app needs to render and grade.
// ---------------------------------------------------------------------------

test('a missing option is rejected', function () {
  const question = makeQuestion({
    options: { a: 'Um.', b: 'Dois.', c: 'Tres.' }
  });
  assert.match(Bank.validate(makeBank([question])).error, /alternativa "d"/);
});

test('an option present but blank is rejected', function () {
  const question = makeQuestion({
    options: { a: 'Um.', b: '   ', c: 'Tres.', d: 'Quatro.' }
  });
  assert.match(Bank.validate(makeBank([question])).error, /alternativa "b"/);
});

test('a question without a stem is rejected', function () {
  const error = Bank.validate(makeBank([makeQuestion({ stem: '  ' })])).error;
  assert.match(error, /enunciado/);
});

test('a question without a topic is rejected', function () {
  const error = Bank.validate(makeBank([makeQuestion({ topic: '' })])).error;
  assert.match(error, /"topic"/);
});

test('a question without a number is rejected', function () {
  const error = Bank.validate(makeBank([makeQuestion({ number: '1' })])).error;
  assert.match(error, /"number"/);
});

test('a repeated question id is rejected', function () {
  const result = Bank.validate(makeBank([makeQuestion(), makeQuestion()]));
  assert.match(result.error, /id repetido/);
});

test('an answer that is not an object is rejected', function () {
  const error = Bank.validate(makeBank([makeQuestion({ answer: 'c' })])).error;
  assert.match(error, /"answer"/);
});

// ---------------------------------------------------------------------------
// The shape of the bank itself.
// ---------------------------------------------------------------------------

test('a bank that is not an object is rejected', function () {
  assert.match(Bank.validate(null).error, /objeto JSON na raiz/);
  assert.match(Bank.validate([]).error, /objeto JSON na raiz/);
  assert.match(Bank.validate('texto').error, /objeto JSON na raiz/);
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
  const noExams = Bank.validate(makeBank([makeQuestion()], { exams: [] }));
  const noQuestions = Bank.validate(makeBank([]));

  assert.match(noExams.error, /"exams"/);
  assert.match(noQuestions.error, /"questions"/);
});

test('an exam without a title is rejected', function () {
  const bank = makeBank([makeQuestion()], { exams: [{ id: 'ENA26' }] });
  assert.match(Bank.validate(bank).error, /"title"/);
});

test('topics that are not a list are rejected', function () {
  const bank = makeBank([makeQuestion()], { topics: {} });
  assert.match(Bank.validate(bank).error, /"topics"/);
});

// ---------------------------------------------------------------------------
// Reading a hand-picked file.
// ---------------------------------------------------------------------------
//
// `FileReader` is replaced with a fake constructor for the duration of each
// test, rather than relying on Node's own global one: the fake is driven
// synchronously (`done` runs before `Bank.readFile` returns), so nothing
// here needs to await a real read, and the tests do not depend on whichever
// FileReader implementation the Node version running them happens to ship.

test('readFile refuses when nothing was selected', function () {
  /** @type {any} */
  let captured;
  Bank.readFile(null, function (/** @type {any} */ result) {
    captured = result;
  });

  assert.deepEqual(captured, { error: 'Nenhum arquivo selecionado.' });
});

test('readFile refuses an oversized file without ever touching FileReader', function () {
  const originalFileReader = globalThis.FileReader;
  /** @type {any} */ (globalThis).FileReader = function () {
    throw new Error('FileReader must not be constructed for an oversized file');
  };

  try {
    /** @type {any} */
    let captured;
    /** @type {any} */
    const oversized = { size: 21 * 1024 * 1024 };
    Bank.readFile(oversized, function (/** @type {any} */ result) {
      captured = result;
    });

    assert.match(captured.error, /grande demais/);
  } finally {
    globalThis.FileReader = originalFileReader;
  }
});

test('readFile hands a valid file straight to the validator', function () {
  const originalFileReader = globalThis.FileReader;
  const text = JSON.stringify(makeBank([makeQuestion()]));
  /** @type {any} */ (globalThis).FileReader = function () {
    /** @type {any} */
    const reader = {};
    reader.readAsText = function () {
      reader.result = text;
      reader.onload();
    };
    return reader;
  };

  try {
    /** @type {any} */
    let captured;
    /** @type {any} */
    const file = { size: text.length };
    Bank.readFile(file, function (/** @type {any} */ result) {
      captured = result;
    });

    assert.equal(captured.error, undefined);
    assert.equal(captured.bank.questions.length, 1);
  } finally {
    globalThis.FileReader = originalFileReader;
  }
});

test('readFile reports a FileReader failure instead of hanging', function () {
  const originalFileReader = globalThis.FileReader;
  /** @type {any} */ (globalThis).FileReader = function () {
    /** @type {any} */
    const reader = {};
    reader.readAsText = function () {
      reader.onerror();
    };
    return reader;
  };

  try {
    /** @type {any} */
    let captured;
    /** @type {any} */
    const file = { size: 10 };
    Bank.readFile(file, function (/** @type {any} */ result) {
      captured = result;
    });

    assert.match(captured.error, /Não foi possível ler/);
  } finally {
    globalThis.FileReader = originalFileReader;
  }
});

test('readFile reports readAsText throwing synchronously', function () {
  const originalFileReader = globalThis.FileReader;
  /** @type {any} */ (globalThis).FileReader = function () {
    /** @type {any} */
    const reader = {};
    reader.readAsText = function () {
      throw new Error('disco em chamas');
    };
    return reader;
  };

  try {
    /** @type {any} */
    let captured;
    /** @type {any} */
    const file = { size: 10 };
    Bank.readFile(file, function (/** @type {any} */ result) {
      captured = result;
    });

    assert.match(captured.error, /Falha ao abrir/);
  } finally {
    globalThis.FileReader = originalFileReader;
  }
});

// ---------------------------------------------------------------------------
// Parsing and identifying.
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
