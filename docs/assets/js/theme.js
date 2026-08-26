// @ts-check

/**
 * The three-state theme switch: system, light, dark.
 *
 * The three are presented as a segmented control rather than cycled through
 * one button, so there is no "next choice" to compute: the interface offers
 * all three at once and the user names the one they want.
 *
 * `data-theme` on the root element is the whole mechanism — the stylesheet
 * turns it into a `color-scheme`, and `light-dark()` does the rest. The
 * attribute is absent while the choice is "system", so the page follows
 * `prefers-color-scheme` with no JavaScript involved.
 */
const Theme = (function () {
  'use strict';

  /** @type {ThemeChoice[]} The cycle order of the toggle button. */
  const CHOICES = ['system', 'light', 'dark'];

  /** @type {Record<ThemeChoice, string>} Portuguese labels, shown to the user. */
  const LABELS = {
    system: 'automático',
    light: 'claro',
    dark: 'escuro'
  };

  /**
   * Narrow an unknown value to a theme choice.
   *
   * @param {unknown} value - Anything, typically a string read from storage.
   * @returns {value is ThemeChoice} True when the value is one of the three states.
   */
  function isChoice(value) {
    return value === 'system' || value === 'light' || value === 'dark';
  }

  /**
   * Read the persisted choice.
   *
   * @returns {ThemeChoice} The stored choice, or "system" when there is none.
   */
  function read() {
    const stored = AppStorage.readText(AppStorage.KEYS.theme);
    return isChoice(stored) ? stored : 'system';
  }

  /**
   * Persist a choice.
   *
   * The value is stored as a bare string rather than JSON so the inline script
   * in <head> can read it without parsing.
   *
   * @param {ThemeChoice} choice - The choice to remember.
   * @returns {void}
   */
  function store(choice) {
    AppStorage.writeText(AppStorage.KEYS.theme, choice);
  }

  /**
   * Apply a choice to the document.
   *
   * @param {ThemeChoice} choice - The choice to apply.
   * @returns {void}
   */
  function apply(choice) {
    if (choice === 'system') {
      document.documentElement.removeAttribute('data-theme');
      return;
    }
    document.documentElement.setAttribute('data-theme', choice);
  }

  /**
   * Give the Portuguese label of a choice.
   *
   * @param {ThemeChoice} choice - The choice to name.
   * @returns {string} The label, in lower case, for use inside a sentence.
   */
  function label(choice) {
    return LABELS[choice];
  }

  return { CHOICES, isChoice, read, store, apply, label };
})();
