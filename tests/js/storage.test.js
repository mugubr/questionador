// @ts-check

/**
 * Tests for `docs/assets/js/storage.js`.
 *
 * Every read and write is wrapped in try/catch because in a private window, or
 * with site data blocked, merely touching `localStorage` throws. The app has
 * to keep working — it just forgets the theme, the progress and the history.
 * The stand-in storage here is what lets that be asserted outside a browser.
 */

'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { fakeLocalStorage, loadAppScript } = require('./helpers.js');

/**
 * Install a stand-in `window.localStorage` and hand it back.
 *
 * @param {{failing?: boolean}} [options] - `failing` makes every call throw.
 * @returns {any} The stand-in storage.
 */
function installStorage(options) {
  const storage = fakeLocalStorage(options);
  /** @type {Record<string, any>} */ (globalThis).window = { localStorage: storage };
  return storage;
}

installStorage();
const AppStorage = loadAppScript('storage.js', 'AppStorage');

// ---------------------------------------------------------------------------
// The keys.
// ---------------------------------------------------------------------------

test('every key the app persists is namespaced and versioned', function () {
  assert.deepEqual(Object.keys(AppStorage.KEYS).sort(), [
    'history',
    'preferences',
    'session',
    'theme'
  ]);
  Object.values(AppStorage.KEYS).forEach(function (key) {
    assert.match(String(key), /^profnit\.[a-z]+\.v\d+$/);
  });
});

test('the theme key is the one the pre-paint inline script reads', function () {
  /* The inline script in <head> applies data-theme before the first paint, so
     reloading in dark does not flash white. It hard-codes this string. */
  assert.equal(AppStorage.KEYS.theme, 'profnit.theme.v1');
});

// ---------------------------------------------------------------------------
// Round trips.
// ---------------------------------------------------------------------------

test('what is written comes back', function () {
  const storage = installStorage();

  assert.equal(AppStorage.writeText(AppStorage.KEYS.theme, 'dark'), true);
  assert.equal(AppStorage.readText(AppStorage.KEYS.theme), 'dark');
  assert.equal(storage.entries.get(AppStorage.KEYS.theme), 'dark');
});

test('a session written as JSON is read back as the same value', function () {
  installStorage();
  const session = {
    version: 1,
    signature: '1:2026-08-26:144',
    deck: ['ENA26-Q01'],
    position: 0,
    answers: { 'ENA26-Q01': { chosen: 'c', correct: true } },
    orders: { 'ENA26-Q01': ['d', 'a', 'c', 'b'] },
    correctCount: 1,
    incorrectCount: 0,
    startedAt: 1700000000000
  };

  assert.equal(AppStorage.writeJson(AppStorage.KEYS.session, session), true);
  assert.deepEqual(AppStorage.readJson(AppStorage.KEYS.session), session);
});

test('a key that was never written reads as null', function () {
  installStorage();
  assert.equal(AppStorage.readText(AppStorage.KEYS.history), null);
  assert.equal(AppStorage.readJson(AppStorage.KEYS.history), null);
});

test('a removed key reads as null again', function () {
  installStorage();
  AppStorage.writeText(AppStorage.KEYS.session, '{}');
  AppStorage.remove(AppStorage.KEYS.session);

  assert.equal(AppStorage.readText(AppStorage.KEYS.session), null);
});

test('a half-written JSON value reads as null instead of throwing', function () {
  const storage = installStorage();
  storage.entries.set(AppStorage.KEYS.session, '{"deck":');

  assert.equal(AppStorage.readJson(AppStorage.KEYS.session), null);
});

test('a value JSON cannot serialize is refused, not thrown', function () {
  installStorage();
  /** @type {any} */
  const cyclic = {};
  cyclic.self = cyclic;

  assert.equal(AppStorage.writeJson(AppStorage.KEYS.session, cyclic), false);
});

// ---------------------------------------------------------------------------
// Storage that refuses to work at all.
// ---------------------------------------------------------------------------

test('blocked storage is detected rather than crashing the app', function () {
  installStorage({ failing: true });
  assert.equal(AppStorage.isAvailable(), false);

  installStorage();
  assert.equal(AppStorage.isAvailable(), true);
});

test('every read and write degrades quietly when storage throws', function () {
  installStorage({ failing: true });

  assert.equal(AppStorage.readText(AppStorage.KEYS.theme), null);
  assert.equal(AppStorage.readJson(AppStorage.KEYS.session), null);
  assert.equal(AppStorage.writeText(AppStorage.KEYS.theme, 'dark'), false);
  assert.equal(AppStorage.writeJson(AppStorage.KEYS.session, { a: 1 }), false);
  assert.doesNotThrow(function () {
    AppStorage.remove(AppStorage.KEYS.session);
  });
  assert.doesNotThrow(function () {
    AppStorage.forgetLegacyKeys();
  });
});

// ---------------------------------------------------------------------------
// The bank is never cached.
// ---------------------------------------------------------------------------

test('the pre-Pages keys are deleted, so no stale bank survives', function () {
  /* The bank used to be cached in storage. It now ships with the app, and a
     stale copy would be a source of silent staleness. */
  const storage = installStorage();
  storage.entries.set('quiz.bank.v1', '{"version":1}');
  storage.entries.set('quiz.session.v1', '{}');
  storage.entries.set(AppStorage.KEYS.session, '{}');

  AppStorage.forgetLegacyKeys();

  assert.equal(storage.entries.has('quiz.bank.v1'), false);
  assert.equal(storage.entries.has('quiz.session.v1'), false);
  assert.equal(storage.entries.has(AppStorage.KEYS.session), true);
});

test('no key the app writes holds the question bank', function () {
  assert.equal(
    Object.values(AppStorage.KEYS).some(function (key) {
      return String(key).indexOf('bank') !== -1;
    }),
    false
  );
});
