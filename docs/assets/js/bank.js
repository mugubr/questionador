// @ts-check

/**
 * Validation and indexing of the question bank.
 *
 * The bank normally ships with the app (`data/question-bank.js` assigns
 * `window.QUESTION_BANK`), but it is still validated on every start: the
 * validator is the guard against a stale or hand-edited file, and it is what
 * produces the message the student reads when something is wrong. The same
 * code path validates a file the user loads by hand, which is genuinely
 * untrusted input.
 *
 * The checks are the ones the app depends on to render and grade a question.
 * Referential and negative invariants — a `duplicateOf` that points nowhere,
 * a topic id that no entry of `topics` declares — belong to `tools/validate.py`,
 * which runs before publishing. Rejecting a usable bank over a harmless extra
 * field would cost the student the whole app for nothing.
 */
const Bank = (function () {
  'use strict';

  const SUPPORTED_VERSION = 1;

  /** @type {OptionLetter[]} */
  const LETTERS = ['a', 'b', 'c', 'd'];
  const SOURCES = ['official'];
  const EXCLUDED_REASONS = ['annulled', 'source-booklet-defect'];
  const MAX_FILE_BYTES = 20 * 1024 * 1024;

  /**
   * Report whether a value is a string with something in it.
   *
   * @param {unknown} value - Anything.
   * @returns {boolean} True for a string that is not empty or blank.
   */
  function isFilledString(value) {
    return typeof value === 'string' && value.trim() !== '';
  }

  /**
   * Validate the four options of a question.
   *
   * @param {Record<string, unknown>} question - The raw question object.
   * @param {string} id - The question id, for the message.
   * @returns {string | null} A Portuguese error message, or null when valid.
   */
  function validateOptions(question, id) {
    const options = question.options;
    if (!options || typeof options !== 'object') {
      return 'Questão ' + id + ': campo "options" ausente ou inválido.';
    }
    const record = /** @type {Record<string, unknown>} */ (options);
    for (let i = 0; i < LETTERS.length; i += 1) {
      const letter = LETTERS[i];
      if (!isFilledString(record[letter])) {
        return 'Questão ' + id + ': alternativa "' + letter + '" ausente ou vazia.';
      }
    }
    return null;
  }

  /**
   * Validate the answer of a question, including its provenance.
   *
   * A missing `letter` is legal in exactly one case: the question is excluded,
   * which is how the bank records `AV2-POL-Q14`, annulled in the official key
   * and therefore having no correct answer at all. Accepting it anywhere else
   * would let a question through that cannot be graded.
   *
   * @param {Record<string, unknown>} question - The raw question object.
   * @param {string} id - The question id, for the message.
   * @returns {string | null} A Portuguese error message, or null when valid.
   */
  function validateAnswer(question, id) {
    const answer = question.answer;
    if (!answer || typeof answer !== 'object') {
      return 'Questão ' + id + ': campo "answer" ausente ou inválido.';
    }

    const record = /** @type {Record<string, unknown>} */ (answer);
    const hasLetter = typeof record.letter === 'string' &&
      LETTERS.indexOf(/** @type {OptionLetter} */ (record.letter)) !== -1;

    if (!hasLetter) {
      if (record.letter !== undefined && record.letter !== null) {
        return 'Questão ' + id + ': answer.letter deve ser a, b, c ou d (veio ' +
          JSON.stringify(record.letter) + ').';
      }
      if (!isFilledString(question.excludedReason)) {
        return 'Questão ' + id + ': answer.letter só pode faltar quando a questão ' +
          'traz excludedReason.';
      }
    }
    if (typeof record.source !== 'string' || SOURCES.indexOf(record.source) === -1) {
      return 'Questão ' + id + ': answer.source deve ser "official" (veio ' +
        JSON.stringify(record.source) + '). Um banco com gabaritos derivados é ' +
        'anterior à recuperação das chaves oficiais; gere-o de novo com ' +
        '"python -m tools build".';
    }
    return null;
  }

  /**
   * Validate a single question.
   *
   * @param {unknown} raw - The candidate question.
   * @param {number} index - Its position in the list, for the message.
   * @param {Set<string>} seenIds - Ids already accepted; mutated on success.
   * @returns {string | null} A Portuguese error message, or null when valid.
   */
  function validateQuestion(raw, index, seenIds) {
    const position = String(index + 1);
    if (!raw || typeof raw !== 'object') {
      return 'A questão na posição ' + position + ' não é um objeto.';
    }

    const question = /** @type {Record<string, unknown>} */ (raw);
    if (!isFilledString(question.id)) {
      return 'A questão na posição ' + position + ' está sem o campo "id".';
    }

    const id = /** @type {string} */ (question.id);
    if (seenIds.has(id)) {
      return 'Questão ' + id + ': id repetido no arquivo.';
    }
    seenIds.add(id);

    if (!isFilledString(question.exam)) {
      return 'Questão ' + id + ': campo "exam" ausente.';
    }
    if (typeof question.number !== 'number') {
      return 'Questão ' + id + ': campo "number" ausente ou não numérico.';
    }
    if (!isFilledString(question.topic)) {
      return 'Questão ' + id + ': campo "topic" ausente.';
    }
    if (!isFilledString(question.stem)) {
      return 'Questão ' + id + ': enunciado ausente ou vazio.';
    }
    if (question.excludedReason !== undefined &&
        (typeof question.excludedReason !== 'string' ||
         EXCLUDED_REASONS.indexOf(question.excludedReason) === -1)) {
      return 'Questão ' + id + ': excludedReason deve ser "annulled" ou ' +
        '"source-booklet-defect".';
    }

    return validateOptions(question, id) || validateAnswer(question, id);
  }

  /**
   * Validate one entry of the exam list.
   *
   * @param {unknown} raw - The candidate exam.
   * @param {number} index - Its position in the list, for the message.
   * @returns {string | null} A Portuguese error message, or null when valid.
   */
  function validateExam(raw, index) {
    if (!raw || typeof raw !== 'object') {
      return 'A prova na posição ' + String(index + 1) + ' não é um objeto.';
    }
    const exam = /** @type {Record<string, unknown>} */ (raw);
    if (!isFilledString(exam.id)) {
      return 'A prova na posição ' + String(index + 1) + ' está sem o campo "id".';
    }
    if (!isFilledString(exam.title)) {
      return 'Prova ' + String(exam.id) + ': campo "title" ausente.';
    }
    return null;
  }

  /**
   * Validate a whole bank. Never throws.
   *
   * @param {unknown} data - The candidate bank, from the embedded file or an upload.
   * @returns {BankResult} `{bank}` when it is valid, `{error}` when it is not.
   */
  function validate(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      return { error: 'O banco não é um objeto JSON na raiz.' };
    }

    const root = /** @type {Record<string, unknown>} */ (data);
    if (root.questoes || root.provas) {
      return {
        error: 'Este arquivo está no formato antigo, com campos em português. ' +
          'Gere o banco novamente com "python -m tools build".'
      };
    }
    if (root.version !== SUPPORTED_VERSION) {
      return {
        error: 'Versão do banco não suportada: esperado ' + SUPPORTED_VERSION +
          ', veio ' + JSON.stringify(root.version) + '.'
      };
    }
    if (!Array.isArray(root.exams) || root.exams.length === 0) {
      return { error: 'O campo "exams" deve ser uma lista não vazia.' };
    }
    if (!Array.isArray(root.questions) || root.questions.length === 0) {
      return { error: 'O campo "questions" deve ser uma lista não vazia.' };
    }

    if (root.topics !== undefined && !Array.isArray(root.topics)) {
      return { error: 'O campo "topics" deve ser uma lista.' };
    }

    for (let i = 0; i < root.exams.length; i += 1) {
      const examError = validateExam(root.exams[i], i);
      if (examError) {
        return { error: examError };
      }
    }

    /** @type {Set<string>} */
    const seenIds = new Set();
    for (let i = 0; i < root.questions.length; i += 1) {
      const questionError = validateQuestion(root.questions[i], i, seenIds);
      if (questionError) {
        return { error: questionError };
      }
    }

    return { bank: /** @type {QuestionBank} */ (data) };
  }

  /**
   * Parse and validate JSON text.
   *
   * @param {string} text - The file contents.
   * @returns {BankResult} `{bank}` or `{error}`.
   */
  function parseText(text) {
    let data;
    try {
      data = JSON.parse(text);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      return { error: 'JSON inválido: ' + detail };
    }
    return validate(data);
  }

  /**
   * Read a user-selected file and hand the result to a callback.
   *
   * @param {File | null | undefined} file - The selected file.
   * @param {(result: BankResult) => void} done - Called exactly once, with `{bank}` or `{error}`.
   * @returns {void}
   */
  function readFile(file, done) {
    if (!file) {
      done({ error: 'Nenhum arquivo selecionado.' });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      done({ error: 'Arquivo grande demais (limite de 20 MB).' });
      return;
    }

    const reader = new FileReader();
    reader.onload = function () {
      done(parseText(String(reader.result)));
    };
    reader.onerror = function () {
      done({ error: 'Não foi possível ler o arquivo.' });
    };

    try {
      reader.readAsText(file, 'utf-8');
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      done({ error: 'Falha ao abrir o arquivo: ' + detail });
    }
  }

  /**
   * Build a short string that identifies this bank.
   *
   * A saved session is only offered for resuming when its signature still
   * matches, which is the cheap half of the check; the ids of the deck are
   * verified against the bank afterwards.
   *
   * @param {QuestionBank} bank - The loaded bank.
   * @returns {string} A signature that changes whenever the bank does.
   */
  function signature(bank) {
    return [bank.version, bank.generatedAt || 'sem-data', bank.questions.length].join(':');
  }

  /**
   * Index the questions by id.
   *
   * A Map is used rather than an object literal because the keys come from
   * data: an id of `constructor` must not resolve to something inherited.
   *
   * @param {Question[]} questions - The questions to index.
   * @returns {Map<string, Question>} One entry per question.
   */
  function indexById(questions) {
    /** @type {Map<string, Question>} */
    const index = new Map();
    questions.forEach(function (question) {
      index.set(question.id, question);
    });
    return index;
  }

  /**
   * Index the taxonomy by topic id.
   *
   * A Map again, for the same reason as indexById: the keys come from data.
   *
   * @param {QuestionBank} bank - The loaded bank.
   * @returns {Map<string, Topic>} One entry per topic the bank declares.
   */
  function topicsById(bank) {
    /** @type {Map<string, Topic>} */
    const index = new Map();
    (bank.topics || []).forEach(function (topic) {
      if (topic && typeof topic.id === 'string') {
        index.set(topic.id, topic);
      }
    });
    return index;
  }

  /**
   * Index the exams by id.
   *
   * @param {QuestionBank} bank - The loaded bank.
   * @returns {Map<string, Exam>} One entry per exam listed in the bank.
   */
  function examsById(bank) {
    /** @type {Map<string, Exam>} */
    const index = new Map();
    bank.exams.forEach(function (exam) {
      index.set(exam.id, exam);
    });
    return index;
  }

  return {
    SUPPORTED_VERSION,
    LETTERS,
    validate,
    parseText,
    readFile,
    signature,
    indexById,
    examsById,
    topicsById
  };
})();

/* The node test runner loads these classic scripts into a shared context, where
   a top-level `const` would not survive; the explicit assignment is what makes
   the namespace reachable from the tests. */
Object.assign(globalThis, { Bank });
