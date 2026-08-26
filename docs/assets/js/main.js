// @ts-check

/**
 * Bootstrap.
 *
 * The scripts are deferred and run in the order index.html lists them, so
 * every namespace this file needs already exists, and the document is parsed.
 * The readyState check only covers the case of the file being loaded some
 * other way.
 */
const Main = (function () {
  'use strict';

  /**
   * Put a last-resort message on the page when the interface cannot start.
   *
   * This runs only when something structural is broken — a missing element,
   * a script that failed to load — so it builds its own markup, with
   * textContent like everything else.
   *
   * @param {unknown} error - Whatever was thrown.
   * @returns {void}
   */
  function reportFatalError(error) {
    const detail = error instanceof Error ? error.message : String(error);
    window.console.error('Falha ao iniciar o Questionador:', error);

    const panel = document.createElement('section');
    panel.className = 'panel wrapper';

    const title = document.createElement('h2');
    title.className = 'panel__title';
    title.textContent = 'O app não conseguiu iniciar';

    const message = document.createElement('p');
    message.className = 'panel__support';
    message.textContent = 'Recarregue a página. Se o erro continuar, o site foi ' +
      'publicado incompleto: ' + detail;

    panel.append(title, message);
    const main = document.querySelector('main');
    if (main) {
      main.append(panel);
    } else {
      document.body.append(panel);
    }
  }

  /**
   * Start the interface, reporting any failure on the page itself.
   *
   * @returns {void}
   */
  function start() {
    try {
      UI.init();
    } catch (error) {
      reportFatalError(error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  return { start };
})();
