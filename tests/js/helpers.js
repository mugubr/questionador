// @ts-check

/**
 * Loading the app's classic scripts into the node test runner.
 *
 * The app has no build step and no modules: every file in `docs/assets/js` is
 * a classic script that exposes one namespace object. `vm.runInThisContext`
 * is what reproduces that here — the script runs against the real global
 * object, exactly as a `<script>` tag would, with no bundler in between.
 *
 * A top-level `const` does not survive `runInThisContext` the way it survives
 * a script tag, so an export epilogue is appended to the source before it is
 * evaluated. The app's own files already assign their namespace to
 * `globalThis`; the epilogue is what makes the two that do not, testable.
 */

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const APP_SCRIPTS = path.join(REPO_ROOT, 'docs', 'assets', 'js');
const BANK_PATH = path.join(REPO_ROOT, 'data', 'question-bank.json');

/**
 * Evaluate one of the app's scripts and hand back the namespaces it defines.
 *
 * @param {string} fileName - The file inside `docs/assets/js`.
 * @param {string[]} names - The namespace objects the file defines.
 * @returns {Record<string, any>} The namespaces, keyed by name.
 */
function loadAppScript(fileName, names) {
  const source = fs.readFileSync(path.join(APP_SCRIPTS, fileName), 'utf8');
  const epilogue = '\n;Object.assign(globalThis, { ' + names.join(', ') + ' });\n';
  vm.runInThisContext(source + epilogue, { filename: fileName });

  /** @type {Record<string, any>} */
  const exported = {};
  names.forEach(function (name) {
    const namespace = /** @type {Record<string, any>} */ (globalThis)[name];
    if (!namespace) {
      throw new Error(fileName + ' did not define ' + name);
    }
    exported[name] = namespace;
  });
  return exported;
}

/**
 * Read the committed question bank.
 *
 * The arrays are typed so a callback written against them is not an implicit
 * `any` under `checkJs`; their entries stay loose on purpose, because a test
 * has to be able to hand the validator a shape the bank would never publish.
 *
 * @returns {{version: number, generatedAt: string, exams: any[],
 *   topics: any[], questions: any[]}} The bank, exactly as it is published.
 */
function publishedBank() {
  return JSON.parse(fs.readFileSync(BANK_PATH, 'utf8'));
}

/**
 * Build one question, overriding whatever a test cares about.
 *
 * @param {Record<string, any>} [overrides] - Fields to replace.
 * @returns {any} A question shaped like the ones the bank publishes.
 */
function makeQuestion(overrides) {
  return Object.assign(
    {
      id: 'ENA26-Q01',
      exam: 'ENA26',
      number: 1,
      topic: 'patente',
      stem: 'Sobre a patente de invencao, assinale a alternativa correta:',
      options: { a: 'Dez anos.', b: 'Quinze anos.', c: 'Vinte anos.', d: 'Trinta.' },
      answer: {
        letter: 'c',
        source: 'official',
        reference: 'Gabarito-Final_ENA26.pdf'
      }
    },
    overrides || {}
  );
}

/**
 * Build filter criteria that select everything.
 *
 * @param {Record<string, any>} [overrides] - Criteria to replace.
 * @returns {any} Criteria shaped like the ones the preferences hold.
 */
function makeCriteria(overrides) {
  return Object.assign(
    { exams: [], topics: [], history: 'all', includeExcluded: false },
    overrides || {}
  );
}

/**
 * Build the settings `Session.create` needs, with a reproducible shuffle.
 *
 * @param {Record<string, any>} [overrides] - Settings to replace.
 * @returns {any} The settings object.
 */
function makeSettings(overrides) {
  return Object.assign(
    {
      signature: '1:2026-08-26:144',
      size: 0,
      shuffleOptions: false,
      now: 1700000000000,
      random: seededRandom(20260826)
    },
    overrides || {}
  );
}

/**
 * A reproducible source of randomness.
 *
 * A shuffle driven by `Math.random` cannot be asserted on. This is a plain
 * linear congruential generator: the numbers are worthless as randomness and
 * perfect as a fixture.
 *
 * @param {number} seed - Any positive integer.
 * @returns {() => number} A function returning values in [0, 1).
 */
function seededRandom(seed) {
  let state = seed % 2147483647;
  if (state <= 0) {
    state += 2147483646;
  }
  return function () {
    state = (state * 16807) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

/**
 * A `localStorage` stand-in that can be told to misbehave.
 *
 * @param {{failing?: boolean}} [options] - `failing` makes every call throw,
 *   the way a private window or blocked site data does.
 * @returns {{entries: Map<string, string>, getItem: (key: string) => string | null,
 *   setItem: (key: string, value: string) => void,
 *   removeItem: (key: string) => void}} The Storage methods the app calls,
 *   plus the backing map so a test can inspect what was written.
 */
function fakeLocalStorage(options) {
  const failing = Boolean(options && options.failing);
  /** @type {Map<string, string>} */
  const entries = new Map();

  return {
    entries,
    getItem: function (key) {
      if (failing) {
        throw new Error('storage is blocked');
      }
      const stored = entries.get(key);
      return stored === undefined ? null : stored;
    },
    setItem: function (key, value) {
      if (failing) {
        throw new Error('storage is blocked');
      }
      entries.set(key, String(value));
    },
    removeItem: function (key) {
      if (failing) {
        throw new Error('storage is blocked');
      }
      entries.delete(key);
    }
  };
}

module.exports = {
  REPO_ROOT,
  loadAppScript,
  publishedBank,
  makeQuestion,
  makeCriteria,
  makeSettings,
  seededRandom,
  fakeLocalStorage
};
