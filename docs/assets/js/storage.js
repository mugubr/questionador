// @ts-check

/**
 * The `localStorage` wrapper.
 *
 * Every read and write is wrapped in try/catch: in a private window, or with
 * site data blocked, merely touching `localStorage` throws, and the app has to
 * keep working — it just forgets the theme, the progress and the history.
 *
 * The namespace is called AppStorage because `Storage` is already a DOM global
 * (the interface behind `localStorage`), and shadowing it would be a trap.
 */
const AppStorage = (function () {
  'use strict';

  /**
   * Storage keys. `theme` is also read by the inline script in <head> that
   * applies the theme before the first paint; the two must stay in sync.
   */
  const KEYS = {
    theme: 'profnit.theme.v1',
    session: 'profnit.session.v1',
    history: 'profnit.history.v1',
    preferences: 'profnit.preferences.v1'
  };

  /* The bank used to be cached here. It now ships with the app, and a stale
     copy in storage would be a source of silent staleness, so it is deleted. */
  const LEGACY_KEYS = ['quiz.bank.v1', 'quiz.session.v1'];

  /**
   * Report whether `localStorage` can actually be written to.
   *
   * @returns {boolean} True when a probe write and delete both succeed.
   */
  function isAvailable() {
    try {
      const probe = '__profnit_probe__';
      window.localStorage.setItem(probe, '1');
      window.localStorage.removeItem(probe);
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Read a raw string.
   *
   * @param {string} key - One of the values in KEYS.
   * @returns {string | null} The stored string, or null when absent or unreadable.
   */
  function readText(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  /**
   * Write a raw string.
   *
   * @param {string} key - One of the values in KEYS.
   * @param {string} value - The string to store.
   * @returns {boolean} True when the write succeeded.
   */
  function writeText(key, value) {
    try {
      window.localStorage.setItem(key, value);
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Read and parse a JSON value.
   *
   * @param {string} key - One of the values in KEYS.
   * @returns {unknown} The parsed value, or null when absent, unreadable or malformed.
   */
  function readJson(key) {
    const raw = readText(key);
    if (raw === null) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  }

  /**
   * Serialize and write a JSON value.
   *
   * @param {string} key - One of the values in KEYS.
   * @param {unknown} value - Anything JSON.stringify accepts.
   * @returns {boolean} True when the write succeeded.
   */
  function writeJson(key, value) {
    try {
      return writeText(key, JSON.stringify(value));
    } catch (error) {
      return false;
    }
  }

  /**
   * Delete a key.
   *
   * @param {string} key - One of the values in KEYS.
   * @returns {void}
   */
  function remove(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (error) {
      /* With no storage there is nothing to remove. */
    }
  }

  /**
   * Delete the keys used by the pre-Pages version of the app.
   *
   * @returns {void}
   */
  function forgetLegacyKeys() {
    LEGACY_KEYS.forEach(remove);
  }

  return {
    KEYS,
    isAvailable,
    readText,
    writeText,
    readJson,
    writeJson,
    remove,
    forgetLegacyKeys
  };
})();

/* The node test runner loads these classic scripts into a shared context, where
   a top-level `const` would not survive; the explicit assignment is what makes
   the namespace reachable from the tests. */
Object.assign(globalThis, { AppStorage });
