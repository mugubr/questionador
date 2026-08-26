// @ts-check

/**
 * Rendering and events.
 *
 * The non-negotiable rule of this layer: every string that comes from the bank
 * reaches the DOM through `textContent`. Never `innerHTML`, never
 * `insertAdjacentHTML`. The bank ships with the app, but the discipline is what
 * makes the rule checkable, and a hand-loaded bank is still possible.
 *
 * Enum values from the data are English and are turned into Portuguese through
 * the lookup tables below, never by string manipulation.
 */
const UI = (function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';

  /** @type {Record<AnswerSource, string>} */
  const SOURCE_LABELS = {
    official: 'Gabarito oficial'
  };

  /**
   * Why a question sits outside the draw, said plainly. Both reasons are
   * defects of the published material, not of the app, and the student is
   * entitled to the detail.
   *
   * @type {Record<ExcludedReason, string>}
   */
  const EXCLUDED_LABELS = {
    annulled:
      'O gabarito oficial anulou esta questão: ela não tem resposta correta e ' +
      'não entra no placar. Está aqui porque caiu na prova.',
    'source-booklet-defect':
      'O caderno publicado repete esta questão de outra do mesmo ' +
      'exame, palavra por palavra, e o gabarito oficial dá letras diferentes para as duas — ' +
      'prova de que o caderno é que está errado. A resposta mostrada é a da questão repetida.'
  };

  /**
   * The same reasons, counted in a summary. Both forms are spelled out because
   * Portuguese agreement is not a suffix rule the code gets to guess.
   *
   * @type {Record<ExcludedReason, {one: string, many: string}>}
   */
  const EXCLUDED_SHORT = {
    annulled: {
      one: 'anulada no gabarito oficial',
      many: 'anuladas no gabarito oficial'
    },
    'source-booklet-defect': {
      one: 'repetida por defeito do caderno',
      many: 'repetidas por defeito do caderno'
    }
  };

  /** @type {Record<HistoryFilter, string>} */
  const HISTORY_LABELS = {
    all: 'Todas',
    incorrect: 'Só as que errei',
    unanswered: 'Nunca respondidas'
  };

  /** @type {Record<HistoryFilter, string>} The same enum, inside a sentence. */
  const HISTORY_SUMMARY = {
    all: '',
    incorrect: 'só as que errei',
    unanswered: 'nunca respondidas'
  };

  /**
   * Why a filter combination can end up empty, phrased as advice rather than
   * as an error: the student did nothing wrong by asking.
   *
   * @type {Record<HistoryFilter, string>}
   */
  const EMPTY_REASONS = {
    all: 'Nenhuma questão corresponde a esta combinação. Limpe os filtros ou escolha outra prova.',
    incorrect:
      'Você não errou nenhuma questão que passe por estes filtros. ' +
      'Troque o histórico para "Todas" para treinar mesmo assim.',
    unanswered:
      'Você já respondeu todas as questões que passam por estes filtros. ' +
      'Troque o histórico para "Todas" para repeti-las.'
  };

  /**
   * The icon set, as path data on a 24x24 grid. Inline SVG only: an icon font
   * or a sprite file would be an external request, and an external `<use>`
   * href does not resolve at all over `file://`.
   *
   * @type {Record<string, string[]>}
   */
  const ICON_PATHS = {
    check: ['M4.5 12.5l5 5L19.5 6.5'],
    cross: ['M6.5 6.5l11 11M17.5 6.5l-11 11'],
    'check-circle': ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M8 12.2l2.7 2.7L16 9.6'],
    'cross-circle': ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M9 9l6 6M15 9l-6 6'],
    alert: ['M12 4.2 2.6 20h18.8L12 4.2z', 'M12 10v4.2M12 17.2v.1'],
    info: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 11.2v5M12 7.8v.1'],
    'shield-check': [
      'M12 3.2 5 6v5.4c0 4.2 2.9 7.7 7 9.4 4.1-1.7 7-5.2 7-9.4V6l-7-2.8z',
      'M9.2 11.8l2.2 2.2 4-4'
    ],
    search: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z', 'M16.1 16.1 20.6 20.6'],
    minus: ['M6 12h12']
  };

  /**
   * Panel name to the id of its section and of its heading.
   *
   * @type {Record<string, {section: string, heading: string}>}
   */
  const PANELS = {
    error: { section: 'panel-error', heading: 'error-heading' },
    filters: { section: 'panel-filters', heading: 'filters-heading' },
    question: { section: 'panel-question', heading: 'question-heading' },
    results: { section: 'panel-results', heading: 'results-heading' }
  };

  /**
   * Every element the app writes to or listens on, plus `selection-figure`,
   * which it never touches but which "Sortear" names in `aria-describedby`:
   * losing that one would break the button's description silently, and this
   * list is the only thing that would notice.
   */
  const ELEMENT_IDS = [
    'scoreboard',
    'score-correct',
    'score-incorrect',
    'score-remaining',
    'progress',
    'progress-bar',
    'theme-switch',
    'theme-system',
    'theme-light',
    'theme-dark',
    'status',
    'panel-error',
    'error-heading',
    'error-detail',
    'panel-filters',
    'filters-heading',
    'bank-summary',
    'storage-notice',
    'filter-form',
    'chips-exams',
    'chips-topics',
    'chips-history',
    'chips-size',
    'chips-options',
    'filters-notice',
    'start-card',
    'selection-figure',
    'selection-count',
    'selection-unit',
    'selection-summary',
    'start-disabled-reason',
    'start-button',
    'reset-filters-button',
    'disclosure-scope',
    'scope-summary',
    'session-summary',
    'resume',
    'resume-detail',
    'resume-continue',
    'resume-discard',
    'dropzone',
    'file-input',
    'upload-notice',
    'panel-question',
    'question-heading',
    'question',
    'question-exam',
    'question-meta',
    'question-excluded',
    'question-defect',
    'question-stem',
    'options',
    'feedback',
    'feedback-verdict',
    'feedback-answer',
    'feedback-explanation-label',
    'feedback-explanation',
    'feedback-order-note',
    'feedback-reference',
    'next-button',
    'next-hint',
    'end-button',
    'panel-results',
    'results-heading',
    'score-summary',
    'score-label',
    'score-detail',
    'result-correct',
    'result-incorrect',
    'result-skipped',
    'stat-skipped',
    'results-empty',
    'topic-stats',
    'topic-stats-heading',
    'review-head',
    'review-heading',
    'review-toggle',
    'review-toggle-chip',
    'review',
    'new-session-button',
    'back-to-filters-button',
    'footer-provenance'
  ];

  /** @type {Record<string, HTMLElement>} The elements of index.html, by id. */
  const el = Object.create(null);

  const state = {
    /** @type {QuestionBank | null} */
    bank: null,
    /** @type {Map<string, Question>} */
    byId: new Map(),
    /** @type {Map<string, Exam>} */
    exams: new Map(),
    /** @type {Map<string, Topic>} */
    topics: new Map(),
    /** @type {string} */
    signature: '',
    /** @type {Session | null} */
    session: null,
    /** @type {Session | null} */
    resumable: null,
    /** @type {Preferences} */
    preferences: Preferences.defaults(),
    /** @type {AnswerHistory} */
    history: AnswerHistory.empty(),
    /** @type {ThemeChoice} */
    theme: 'system',
    /** @type {string} */
    panel: '',
    /** @type {boolean} Whether the last read of the filters matched nothing. */
    emptySelection: false,
    /** @type {number} How many questions the next draw would take. */
    drawn: 0,
    /** @type {number} How many questions pass the current filters. */
    poolSize: 0
  };

  /* ---------- Small helpers ---------------------------------------------- */

  /**
   * Look an element up and fail loudly when the HTML lost it.
   *
   * @param {string} id - The element id.
   * @returns {HTMLElement} The element.
   */
  function requireElement(id) {
    const node = document.getElementById(id);
    if (!node) {
      throw new Error('Elemento ausente no HTML: ' + id);
    }
    return node;
  }

  /**
   * Look up every element of ELEMENT_IDS once, up front.
   *
   * @returns {void}
   */
  function cacheElements() {
    ELEMENT_IDS.forEach(function (id) {
      el[id] = requireElement(id);
    });
  }

  /**
   * Build one icon from the inline path table.
   *
   * @param {string} name - A key of ICON_PATHS.
   * @param {string} className - The class the caller styles it with.
   * @param {number} [strokeWidth] - Stroke weight; small icons need a heavier one.
   * @returns {SVGSVGElement} A decorative icon, hidden from assistive tech.
   */
  function createIcon(name, className, strokeWidth) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', className);
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', String(strokeWidth || 2));
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');

    (ICON_PATHS[name] || []).forEach(function (data) {
      const path = document.createElementNS(SVG_NS, 'path');
      path.setAttribute('d', data);
      svg.append(path);
    });
    return svg;
  }

  /**
   * Build a span carrying one string.
   *
   * @param {string} text - Portuguese, straight from the data or from a label.
   * @param {string} [className] - The class to put on it.
   * @returns {HTMLSpanElement} The span, ready to append.
   */
  function createSpan(text, className) {
    const span = document.createElement('span');
    if (className) {
      span.className = className;
    }
    span.textContent = text;
    return span;
  }

  /**
   * Announce a complete sentence in the single status region.
   *
   * @param {string} sentence - Portuguese, complete enough to stand alone.
   * @returns {void}
   */
  function announce(sentence) {
    el.status.textContent = sentence;
  }

  /**
   * Show or clear a notice, with the icon its variant calls for.
   *
   * @param {HTMLElement} element - The notice paragraph.
   * @param {string} message - The message, or an empty string to hide it.
   * @param {"error" | "info" | "warn" | "quiet"} [variant] - Which notice style to use.
   * @returns {void}
   */
  function showNotice(element, message, variant) {
    if (!message) {
      element.hidden = true;
      element.replaceChildren();
      return;
    }
    const kind = variant || 'error';
    element.className = 'note note--' + kind;
    element.replaceChildren(
      createIcon(kind === 'error' || kind === 'warn' ? 'alert' : 'info', 'note__icon'),
      createSpan(message, 'note__text')
    );
    element.hidden = false;
  }

  /**
   * Format an ISO date for a Brazilian reader.
   *
   * `new Date("2025-11-22")` is parsed as UTC midnight and prints the day
   * before in any negative offset, Brazil included, so the string is taken
   * apart by hand.
   *
   * @param {string} iso - A date in `YYYY-MM-DD`.
   * @returns {string} The date as `DD/MM/YYYY`, or the input when it is not a date.
   */
  function formatDate(iso) {
    const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return parts ? parts[3] + '/' + parts[2] + '/' + parts[1] : iso || '';
  }

  /**
   * Name a topic for a human.
   *
   * The bank carries a taxonomy with proper accented Portuguese labels, so the
   * id is looked up rather than de-hyphenated. De-hyphenating produced
   * "indicacao geografica", which is not a Portuguese phrase.
   *
   * @param {string} topic - The topic id the question carries.
   * @returns {string} The label, or the id when the bank does not declare it.
   */
  function topicLabel(topic) {
    const entry = state.topics.get(topic);
    return entry && entry.label ? entry.label : topic;
  }

  /**
   * List the topic ids present in the bank, in the taxonomy's own order.
   *
   * The taxonomy is ordered by how much of the bank each topic covers, which
   * is a more useful order for a chip cloud than the alphabet. Anything a
   * question claims but the taxonomy omits is appended rather than dropped.
   *
   * @returns {string[]} The topic ids to build chips for.
   */
  function orderedTopics() {
    const bank = state.bank;
    if (!bank) {
      return [];
    }
    const present = Session.topicsOf(bank.questions);
    const declared = (bank.topics || [])
      .map(function (topic) {
        return topic.id;
      })
      .filter(function (id) {
        return present.indexOf(id) !== -1;
      });
    return declared.concat(
      present.filter(function (id) {
        return declared.indexOf(id) === -1;
      })
    );
  }

  /**
   * Name an exam for a human, falling back to its slug.
   *
   * @param {string} examId - The exam id carried by the question.
   * @returns {string} The exam title, or the id when the bank does not list it.
   */
  function examTitle(examId) {
    const exam = state.exams.get(examId);
    return exam ? exam.title : examId;
  }

  /**
   * Report whether this question is being shown out of the paper's order.
   *
   * It matters because an explanation cites the letters the paper printed
   * ("elimina as alternativas a, b e d"), and those stop matching the screen
   * as soon as the options are shuffled.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The question on screen.
   * @returns {boolean} True when the presented order differs from a-b-c-d.
   */
  function isReordered(session, question) {
    return Session.presentedOrder(session, question).some(function (letter, index) {
      return letter !== Session.LETTERS[index];
    });
  }

  /**
   * Give the sentence that warns about the letters cited in an explanation.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The question on screen.
   * @returns {string} The warning, or an empty string when it does not apply.
   */
  function orderNote(session, question) {
    if (!question.answer.explanation || !isReordered(session, question)) {
      return '';
    }
    return (
      'As letras citadas no comentário seguem a ordem do caderno original, ' +
      'que não é a ordem sorteada aqui.'
    );
  }

  /**
   * Give the letter under which an option is being shown.
   *
   * The options are shuffled, so the letter the student sees is the position
   * in the presented order, not the letter the paper printed.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The question on screen.
   * @param {OptionLetter} sourceLetter - The letter as the bank spells it.
   * @returns {OptionLetter} The letter as the student sees it.
   */
  function displayLetter(session, question, sourceLetter) {
    const order = Session.presentedOrder(session, question);
    const position = order.indexOf(sourceLetter);
    return position === -1 ? sourceLetter : Session.LETTERS[position];
  }

  /**
   * Agree a noun with its count.
   *
   * @param {number} count - How many.
   * @param {string} singular - The noun for one.
   * @param {string} plural - The noun for none or many.
   * @returns {string} The count and the noun, in Portuguese agreement.
   */
  function pluralize(count, singular, plural) {
    return count + ' ' + (count === 1 ? singular : plural);
  }

  /**
   * Close a sentence without doubling the punctuation.
   *
   * Option texts are quoted mid-sentence and most of them already end with a
   * full stop, which produced "a resposta correta é b) ...corretas..".
   *
   * @param {string} text - The sentence so far.
   * @returns {string} The sentence, ending in exactly one mark.
   */
  function endSentence(text) {
    return /[.!?:]$/.test(text) ? text : text + '.';
  }

  /**
   * Quote an option the way the interface always quotes one.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The question on screen.
   * @param {OptionLetter} sourceLetter - The letter as the bank spells it.
   * @returns {string} Something like `b) o depósito da patente`.
   */
  function quoteOption(session, question, sourceLetter) {
    return (
      displayLetter(session, question, sourceLetter) +
      ') ' +
      question.options[sourceLetter]
    );
  }

  /* ---------- Panels ------------------------------------------------------ */

  /**
   * Show one panel and hide the others.
   *
   * Scrolling and focus only happen on an actual change of panel: rendering a
   * grade re-renders the question panel, and jumping to the top of the page or
   * stealing focus on every answer would be maddening.
   *
   * @param {"error" | "filters" | "question" | "results"} name - The panel to show.
   * @param {boolean} [moveFocus] - Whether to move focus to its heading. Defaults to true.
   * @returns {void}
   */
  function showPanel(name, moveFocus) {
    const changed = state.panel !== name;

    Object.keys(PANELS).forEach(function (key) {
      el[PANELS[key].section].hidden = key !== name;
    });
    el.scoreboard.hidden = name !== 'question';
    el.progress.hidden = name !== 'question';

    if (name !== 'question') {
      resetProgress();
    }
    if (!changed) {
      return;
    }

    state.panel = name;
    window.scrollTo({ top: 0, behavior: 'auto' });
    if (moveFocus !== false) {
      el[PANELS[name].heading].focus();
    }
  }

  /* ---------- Theme ------------------------------------------------------- */

  /**
   * Apply the current theme and check the segment that matches it.
   *
   * @returns {void}
   */
  function renderTheme() {
    Theme.apply(state.theme);
    Theme.CHOICES.forEach(function (choice) {
      /** @type {HTMLInputElement} */ (el['theme-' + choice]).checked =
        state.theme === choice;
    });
  }

  /**
   * Adopt the theme the segmented control now says.
   *
   * @returns {void}
   */
  function pickTheme() {
    const chosen = Theme.CHOICES.filter(function (choice) {
      return /** @type {HTMLInputElement} */ (el['theme-' + choice]).checked;
    })[0];
    if (!chosen || chosen === state.theme) {
      return;
    }
    state.theme = chosen;
    Theme.store(state.theme);
    renderTheme();
    announce('Tema ' + Theme.label(state.theme) + '.');
  }

  /* ---------- Scoreboard and progress ------------------------------------- */

  /**
   * Redraw the scoreboard from the running session.
   *
   * @returns {void}
   */
  function updateScoreboard() {
    const session = state.session;
    el['score-correct'].textContent = String(session ? session.correctCount : 0);
    el['score-incorrect'].textContent = String(session ? session.incorrectCount : 0);
    el['score-remaining'].textContent = String(Session.unansweredCount(session));
    updateProgress();
  }

  /**
   * Redraw the progress bar and its semantics.
   *
   * @returns {void}
   */
  function updateProgress() {
    const session = state.session;
    const total = session ? session.deck.length : 0;
    const done = Session.answeredCount(session);

    el.progress.setAttribute('aria-valuemax', String(total));
    el.progress.setAttribute('aria-valuenow', String(done));
    el.progress.setAttribute(
      'aria-valuetext',
      done + ' de ' + total + ' questões respondidas'
    );
    el['progress-bar'].style.width = total ? String((done / total) * 100) + '%' : '0';
  }

  /**
   * Empty the progress bar when no session is running.
   *
   * @returns {void}
   */
  function resetProgress() {
    el.progress.setAttribute('aria-valuemax', '0');
    el.progress.setAttribute('aria-valuenow', '0');
    el.progress.setAttribute('aria-valuetext', 'Nenhuma sessão em andamento');
    el['progress-bar'].style.width = '0';
  }

  /* ---------- Filter controls --------------------------------------------- */

  /**
   * Build the hidden input every filter control is really made of.
   *
   * @param {{group: string, value: string, type: "checkbox" | "radio", name?: string, checked: boolean}} config
   *   `group` ends up in `data-group` and is how the form is read back.
   * @returns {HTMLInputElement} The input, ready to append.
   */
  function createControlInput(config) {
    const input = document.createElement('input');
    input.className = 'control__input';
    input.type = config.type;
    input.value = config.value;
    input.checked = config.checked;
    input.dataset.group = config.group;
    if (config.name) {
      input.name = config.name;
    }
    return input;
  }

  /**
   * Build one filter chip.
   *
   * The selected state is an ink fill AND a check mark, because a fill alone
   * is a color difference and the outline-only version that preceded it
   * measured 1.20:1 against the surface.
   *
   * @param {{group: string, value: string, label: string, note?: string, title?: string,
   *   hint?: string, type: "checkbox" | "radio", name?: string, checked: boolean,
   *   counted?: boolean, variant?: string}} config
   *   `counted` adds the slot updateCounts writes the tally into; `title` is
   *   the long name, which becomes the tooltip and part of the accessible name;
   *   `hint` is a tooltip only, for a label that already reads in full.
   * @returns {HTMLLabelElement} The chip, ready to append.
   */
  function createChip(config) {
    const chip = document.createElement('label');
    chip.className = 'chip' + (config.variant ? ' chip--' + config.variant : '');

    /* Everything visible lives in a face that FOLLOWS the input, so the
       selected state is styled with `input:checked + .face` and never depends
       on `:has()`. See the note above the control block in styles.css. */
    const face = document.createElement('span');
    face.className = 'chip__face';
    face.append(
      createIcon('check', 'chip__check', 3),
      createSpan(config.label, 'chip__label')
    );

    /* The exam chips show only the slug, so the full title has to reach a
       screen reader some other way; the tooltip covers the pointer. */
    if (config.title) {
      chip.title = config.title;
      face.append(createSpan(config.title, 'visually-hidden'));
    } else if (config.hint) {
      chip.title = config.hint;
    }

    if (config.note) {
      face.append(createSpan(config.note, 'chip__note'));
    }

    if (config.counted) {
      const count = document.createElement('span');
      count.className = 'chip__count';
      count.dataset.countFor = config.group + ':' + config.value;
      face.append(count);
    }

    chip.append(createControlInput(config), face);
    return chip;
  }

  /**
   * Build one segment of a segmented control.
   *
   * @param {{group: string, value: string, label: string, name: string, checked: boolean}} config
   * @returns {HTMLLabelElement} The segment, ready to append.
   */
  function createSegment(config) {
    const segment = document.createElement('label');
    segment.className = 'segment';

    const face = document.createElement('span');
    face.className = 'segment__face';
    face.append(createIcon('check', 'segment__check', 3.5), createSpan(config.label));

    segment.append(
      createControlInput({
        group: config.group,
        value: config.value,
        type: 'radio',
        name: config.name,
        checked: config.checked
      }),
      face
    );
    return segment;
  }

  /**
   * Build one preference switch.
   *
   * A preference is not a filter: it changes how the session behaves rather
   * than which questions it holds, so it reads as a switch and carries a line
   * saying what it actually does.
   *
   * @param {{group: string, label: string, note: string, checked: boolean}} config
   * @returns {HTMLLabelElement} The switch, ready to append.
   */
  function createSwitch(config) {
    const control = document.createElement('label');
    control.className = 'switch';

    const input = createControlInput({
      group: config.group,
      value: 'on',
      type: 'checkbox',
      checked: config.checked
    });
    input.setAttribute('role', 'switch');

    const track = document.createElement('span');
    track.className = 'switch__track';
    track.setAttribute('aria-hidden', 'true');
    const thumb = document.createElement('span');
    thumb.className = 'switch__thumb';
    thumb.append(createIcon('check', '', 3.5));
    track.append(thumb);

    const text = document.createElement('span');
    text.className = 'switch__label';
    text.append(
      document.createTextNode(config.label),
      createSpan(config.note, 'switch__note')
    );

    /* The track follows the input for the same reason the chip face does:
       the on state is `input:checked + .switch__track`, a sibling combinator. */
    control.append(input, track, text);
    return control;
  }

  /**
   * Build every control of the filter form from the loaded bank.
   *
   * @returns {void}
   */
  function renderFilters() {
    const bank = state.bank;
    if (!bank) {
      return;
    }
    const selected = state.preferences.filters;

    el['chips-exams'].replaceChildren();
    bank.exams.forEach(function (exam) {
      el['chips-exams'].append(
        createChip({
          group: 'exams',
          variant: 'exam',
          counted: true,
          value: exam.id,
          label: exam.id,
          note: formatDate(exam.date),
          title: exam.title,
          type: 'checkbox',
          checked: selected.exams.indexOf(exam.id) !== -1
        })
      );
    });

    el['chips-topics'].replaceChildren();
    orderedTopics().forEach(function (topic) {
      const entry = state.topics.get(topic);
      el['chips-topics'].append(
        createChip({
          group: 'topics',
          counted: true,
          value: topic,
          label: topicLabel(topic),
          /* The taxonomy carries a one-sentence definition per topic. As a
           tooltip it answers "what counts as prospecção?" without spending a
           line of the chip on it. */
          hint: entry ? entry.definition : '',
          type: 'checkbox',
          checked: selected.topics.indexOf(topic) !== -1
        })
      );
    });

    el['chips-history'].replaceChildren();
    /** @type {HistoryFilter[]} */
    const historyRules = ['all', 'incorrect', 'unanswered'];
    historyRules.forEach(function (rule) {
      el['chips-history'].append(
        createChip({
          group: 'history',
          counted: true,
          value: rule,
          label: HISTORY_LABELS[rule],
          type: 'radio',
          name: 'history-filter',
          checked: selected.history === rule
        })
      );
    });

    el['chips-size'].replaceChildren();
    Preferences.SIZES.forEach(function (size) {
      el['chips-size'].append(
        createSegment({
          group: 'size',
          value: String(size),
          label: size === 0 ? 'Todas' : String(size),
          name: 'session-size',
          checked: state.preferences.sessionSize === size
        })
      );
    });

    el['chips-options'].replaceChildren();
    el['chips-options'].append(
      createSwitch({
        group: 'shuffle',
        label: 'Embaralhar alternativas',
        note: 'A ordem a-b-c-d do caderno é sorteada de novo em cada questão.',
        checked: state.preferences.shuffleOptions
      })
    );

    const excluded = excludedQuestions();
    if (excluded.length > 0) {
      el['chips-options'].append(
        createSwitch({
          group: 'excluded',
          label: 'Incluir as questões fora do sorteio',
          note:
            'São ' +
            pluralize(excluded.length, 'questão', 'questões') +
            ': ' +
            describeExcludedParts(excluded) +
            '. Ficam de fora por padrão, e a razão aparece na própria questão.',
          checked: selected.includeExcluded
        })
      );
    }

    renderBankSummary();
    updateSelection();
  }

  /**
   * List the questions the bank keeps but never draws.
   *
   * @returns {Question[]} The excluded questions, in bank order.
   */
  function excludedQuestions() {
    const bank = state.bank;
    if (!bank) {
      return [];
    }
    return bank.questions.filter(function (question) {
      return Boolean(question.excludedReason);
    });
  }

  /**
   * Count the excluded questions by reason, in Portuguese.
   *
   * @param {Question[]} questions - The excluded questions.
   * @returns {string} Something like `2 repetidas… e 1 anulada…`.
   */
  function describeExcludedParts(questions) {
    /** @type {Map<string, number>} */
    const byReason = new Map();
    questions.forEach(function (question) {
      const reason = String(question.excludedReason);
      byReason.set(reason, (byReason.get(reason) || 0) + 1);
    });

    const parts = Array.from(byReason.entries()).map(function (entry) {
      const forms = EXCLUDED_SHORT[/** @type {ExcludedReason} */ (entry[0])];
      if (!forms) {
        return String(entry[1]) + ' ' + entry[0];
      }
      return pluralize(entry[1], forms.one, forms.many);
    });
    return parts.join(' e ');
  }

  /**
   * Describe the loaded bank above the filters.
   *
   * @returns {void}
   */
  function renderBankSummary() {
    const bank = state.bank;
    if (!bank) {
      return;
    }
    const explained = bank.questions.filter(function (question) {
      return Boolean(question.answer.explanation);
    }).length;
    const answered = AnswerHistory.answeredCount(state.history, bank.questions);

    const parts = [
      bank.questions.length + ' questões de ' + bank.exams.length + ' provas',
      'todas com gabarito oficial'
    ];
    if (explained > 0) {
      parts.push(explained + ' com comentário da resposta');
    }
    if (answered > 0) {
      parts.push('você já respondeu ' + answered + ' delas alguma vez');
    }
    el['bank-summary'].textContent = parts.join(' · ') + '.';
  }

  /**
   * Read the filter form back into a criteria object.
   *
   * @returns {FilterCriteria} What the controls currently say.
   */
  function readCriteria() {
    /** @type {FilterCriteria} */
    const criteria = {
      exams: [],
      topics: [],
      history: 'all',
      includeExcluded: false
    };

    const inputs = el['filter-form'].querySelectorAll('input');
    inputs.forEach(function (input) {
      if (!input.checked) {
        return;
      }
      const group = input.dataset.group;
      if (group === 'exams') {
        criteria.exams.push(input.value);
      } else if (group === 'topics') {
        criteria.topics.push(input.value);
      } else if (group === 'history') {
        criteria.history = /** @type {HistoryFilter} */ (input.value);
      } else if (group === 'excluded') {
        criteria.includeExcluded = true;
      }
    });

    return criteria;
  }

  /**
   * Read the session size and the option-shuffling switch back from the form.
   *
   * @returns {{size: number, shuffleOptions: boolean}} What the controls currently say.
   */
  function readSettings() {
    let size = state.preferences.sessionSize;
    let shuffleOptions = false;

    const inputs = el['filter-form'].querySelectorAll('input');
    inputs.forEach(function (input) {
      if (!input.checked) {
        return;
      }
      if (input.dataset.group === 'size') {
        size = Number(input.value);
      } else if (input.dataset.group === 'shuffle') {
        shuffleOptions = true;
      }
    });

    return { size, shuffleOptions };
  }

  /**
   * Write the count of a chip without rebuilding it, so focus is never lost.
   *
   * @param {string} group - The chip group.
   * @param {string} value - The chip value.
   * @param {number} count - The number to show.
   * @returns {void}
   */
  function setChipCount(group, value, count) {
    const node = el['filter-form'].querySelector(
      '[data-count-for="' + group + ':' + value + '"]'
    );
    if (node) {
      node.textContent = String(count);
    }
  }

  /**
   * Recount every chip against the current selection.
   *
   * Exam, topic and provenance counts are measured over the whole drawable
   * bank so they do not shift under the cursor; the history counts are
   * measured inside the current selection, where they answer a real question.
   *
   * @param {FilterCriteria} criteria - The criteria the form currently holds.
   * @returns {void}
   */
  function updateCounts(criteria) {
    const bank = state.bank;
    if (!bank) {
      return;
    }

    /** @type {FilterCriteria} */
    const base = {
      exams: [],
      topics: [],
      history: 'all',
      includeExcluded: criteria.includeExcluded
    };
    const pool = Session.filter(bank.questions, base, state.history);

    bank.exams.forEach(function (exam) {
      setChipCount(
        'exams',
        exam.id,
        pool.filter(function (question) {
          return question.exam === exam.id;
        }).length
      );
    });

    orderedTopics().forEach(function (topic) {
      setChipCount(
        'topics',
        topic,
        pool.filter(function (question) {
          return question.topic === topic;
        }).length
      );
    });

    /** @type {HistoryFilter[]} */
    const historyRules = ['all', 'incorrect', 'unanswered'];
    historyRules.forEach(function (rule) {
      const scoped = Object.assign({}, criteria, { history: rule });
      setChipCount(
        'history',
        rule,
        Session.filter(bank.questions, scoped, state.history).length
      );
    });
  }

  /**
   * Report whether anything at all is being filtered out.
   *
   * @param {FilterCriteria} criteria - The criteria the form currently holds.
   * @returns {boolean} True when at least one filter is narrowing the bank.
   */
  function isFiltered(criteria) {
    return (
      criteria.exams.length > 0 ||
      criteria.topics.length > 0 ||
      criteria.history !== 'all'
    );
  }

  /**
   * Describe which questions the current filters keep.
   *
   * @param {FilterCriteria} criteria - The criteria the form currently holds.
   * @returns {string} Something like `todas as provas · 2 temas · só as que errei`.
   */
  function describeScope(criteria) {
    const bank = state.bank;
    const examCount = bank ? bank.exams.length : 0;
    const topicCount = orderedTopics().length;

    const parts = [];
    if (criteria.exams.length === 0) {
      parts.push(examCount ? 'todas as ' + examCount + ' provas' : 'todas as provas');
    } else if (criteria.exams.length <= 3) {
      parts.push(criteria.exams.join(', '));
    } else {
      parts.push(pluralize(criteria.exams.length, 'prova', 'provas'));
    }

    if (criteria.topics.length === 0) {
      parts.push(topicCount ? 'todos os ' + topicCount + ' temas' : 'todos os temas');
    } else if (criteria.topics.length <= 2) {
      parts.push(criteria.topics.map(topicLabel).join(', '));
    } else {
      parts.push(pluralize(criteria.topics.length, 'tema', 'temas'));
    }

    return parts.join(' · ');
  }

  /**
   * Describe how the session will be run, leaving out how long it will be.
   *
   * @param {FilterCriteria} criteria - The criteria the form currently holds.
   * @param {{size: number, shuffleOptions: boolean}} settings - The session settings.
   * @returns {string} Something like `só as que errei · alternativas embaralhadas`.
   */
  function describeMode(criteria, settings) {
    const parts = [];
    if (HISTORY_SUMMARY[criteria.history]) {
      parts.push(HISTORY_SUMMARY[criteria.history]);
    }
    parts.push(
      settings.shuffleOptions ? 'alternativas embaralhadas' : 'ordem do caderno'
    );
    if (criteria.includeExcluded) {
      parts.push('com as excluídas');
    }
    return parts.join(' · ');
  }

  /**
   * Describe the whole session, length included.
   *
   * The start card leaves the length out, because the length is the large
   * number printed right beside the sentence; the disclosure summary keeps it,
   * because that is the section the length is set in.
   *
   * @param {FilterCriteria} criteria - The criteria the form currently holds.
   * @param {{size: number, shuffleOptions: boolean}} settings - The session settings.
   * @returns {string} Something like `20 questões · alternativas embaralhadas`.
   */
  function describeSession(criteria, settings) {
    const length =
      settings.size === 0 ? 'todas as que passarem' : settings.size + ' questões';
    return length + ' · ' + describeMode(criteria, settings);
  }

  /**
   * Say how big the next draw is, as a sentence that can stand alone.
   *
   * @returns {string} Something like `20 de 141 questões no sorteio.`.
   */
  function selectionSentence() {
    if (state.poolSize === 0) {
      return 'Nenhuma questão no sorteio.';
    }
    if (state.drawn === state.poolSize) {
      return pluralize(state.drawn, 'questão no sorteio.', 'questões no sorteio.');
    }
    return (
      state.drawn +
      ' de ' +
      pluralize(state.poolSize, 'questão no sorteio.', 'questões no sorteio.')
    );
  }

  /**
   * Re-read the form, persist it and update everything that depends on it.
   *
   * @returns {void}
   */
  function updateSelection() {
    const bank = state.bank;
    if (!bank) {
      return;
    }

    const criteria = readCriteria();
    const settings = readSettings();
    state.preferences = {
      version: Preferences.VERSION,
      shuffleOptions: settings.shuffleOptions,
      sessionSize: settings.size,
      filters: criteria
    };
    AppStorage.writeJson(AppStorage.KEYS.preferences, state.preferences);

    updateCounts(criteria);

    const pool = Session.filter(bank.questions, criteria, state.history);
    const drawn =
      settings.size > 0 ? Math.min(settings.size, pool.length) : pool.length;
    const empty = pool.length === 0;
    state.drawn = drawn;
    state.poolSize = pool.length;

    el['selection-count'].textContent = String(drawn);
    el['selection-unit'].textContent =
      drawn === pool.length
        ? drawn === 1
          ? 'questão no sorteio'
          : 'questões no sorteio'
        : 'de ' + pluralize(pool.length, 'questão', 'questões');
    el['selection-summary'].textContent = empty
      ? 'Nenhuma questão passa por estes filtros.'
      : endSentence(describeScope(criteria) + ' · ' + describeMode(criteria, settings));

    el['scope-summary'].textContent = describeScope(criteria);
    el['session-summary'].textContent = describeSession(criteria, settings);

    el['start-card'].classList.toggle('start-card--empty', empty);
    el['start-disabled-reason'].textContent = empty
      ? EMPTY_REASONS[criteria.history]
      : '';
    /** @type {HTMLButtonElement} */ (el['start-button']).disabled = empty;
    el['reset-filters-button'].hidden = !isFiltered(criteria);

    /* Only the transition is worth announcing: this runs on every keystroke
       inside the filter form, and narrating each one would be noise. */
    if (empty !== state.emptySelection && state.panel === 'filters') {
      announce(empty ? EMPTY_REASONS[criteria.history] : selectionSentence());
    }
    state.emptySelection = empty;
  }

  /**
   * Put every filter back to "everything", keeping the session settings.
   *
   * Size and shuffling survive on purpose: they are how the student likes to
   * study, not a narrowing of the bank, and clearing them would be a surprise.
   *
   * @returns {void}
   */
  function resetFilters() {
    const inputs = el['filter-form'].querySelectorAll('input');
    inputs.forEach(function (input) {
      const group = input.dataset.group;
      if (group === 'exams' || group === 'topics') {
        input.checked = false;
      } else if (group === 'history') {
        input.checked = input.value === 'all';
      }
    });

    updateSelection();
    announce('Filtros limpos. ' + selectionSentence());
    /* The button that was just pressed hides itself, so focus has to go
       somewhere deliberate rather than back to the document. */
    el['start-button'].focus();
  }

  /* ---------- Resuming ---------------------------------------------------- */

  /**
   * Offer to continue a session that was interrupted, if there is one.
   *
   * @returns {void}
   */
  function renderResumeOffer() {
    const stored = Session.fromStored(AppStorage.readJson(AppStorage.KEYS.session));
    const usable =
      stored &&
      Session.matchesBank(stored, state.byId, state.signature) &&
      !Session.isFinished(stored);

    if (!usable || !stored) {
      state.resumable = null;
      el.resume.hidden = true;
      AppStorage.remove(AppStorage.KEYS.session);
      return;
    }

    state.resumable = stored;
    el['resume-detail'].textContent =
      Session.answeredCount(stored) +
      ' de ' +
      stored.deck.length +
      ' questões respondidas' +
      (stored.startedAt ? ' · começou em ' + formatTimestamp(stored.startedAt) : '') +
      '.';
    el.resume.hidden = false;
  }

  /**
   * Pad one component of a date to two digits.
   *
   * @param {number} value - A day, month, hour or minute.
   * @returns {string} The value, at least two characters wide.
   */
  function padTwo(value) {
    return String(value).padStart(2, '0');
  }

  /**
   * Format an epoch timestamp for a Brazilian reader.
   *
   * @param {number} epochMs - Epoch milliseconds.
   * @returns {string} Something like `26/08/2026 às 14:32`.
   */
  function formatTimestamp(epochMs) {
    const moment = new Date(epochMs);
    return (
      padTwo(moment.getDate()) +
      '/' +
      padTwo(moment.getMonth() + 1) +
      '/' +
      moment.getFullYear() +
      ' às ' +
      padTwo(moment.getHours()) +
      ':' +
      padTwo(moment.getMinutes())
    );
  }

  /* ---------- Question ---------------------------------------------------- */

  /**
   * Build the provenance badge.
   *
   * There is only one badge left. Every answer in the bank now comes from a
   * published key verified against the booklet in `exams/`, so the badge no
   * longer distinguishes anything — it states, quietly and on every question,
   * where the answer came from. That is worth one small mark and no more.
   *
   * @param {string} text - The Portuguese label.
   * @returns {HTMLSpanElement} The badge, ready to append.
   */
  function createBadge(text) {
    const badge = document.createElement('span');
    badge.className = 'badge badge--official';
    badge.append(createIcon('shield-check', 'badge__icon'), createSpan(text));
    return badge;
  }

  /**
   * Redraw the identification lines above the stem.
   *
   * @param {Question} question - The question on screen.
   * @returns {void}
   */
  function renderQuestionMeta(question) {
    el['question-exam'].textContent = examTitle(question.exam);

    const answer = question.answer;
    const meta = el['question-meta'];
    meta.replaceChildren();

    const exam = state.exams.get(question.exam);
    meta.append(
      createSpan(
        [
          question.exam,
          exam ? formatDate(exam.date) : '',
          'questão ' + question.number,
          topicLabel(question.topic)
        ]
          .filter(Boolean)
          .join(' · '),
        'question__identity'
      )
    );

    meta.append(createBadge(SOURCE_LABELS[answer.source] || SOURCE_LABELS.official));

    /* A question kept in the bank but normally left out of the draw is on
       screen only because the student asked for it, and is owed the reason. */
    const reason = question.excludedReason;
    let excluded = reason ? EXCLUDED_LABELS[reason] : '';
    if (reason === 'source-booklet-defect' && question.duplicateOf) {
      excluded = 'Esta questão repete a ' + question.duplicateOf + '. ' + excluded;
    }
    showNotice(el['question-excluded'], excluded, 'warn');

    /* The repeated option only changes the grading when the answer key itself
       is one of the twins, so the second sentence is conditional. */
    const keyed = answer.letter;
    const twinned = Session.hasDefect(question, 'identical-options');
    const answerHasTwin =
      twinned &&
      keyed !== undefined &&
      Session.LETTERS.some(function (letter) {
        return letter !== keyed && question.options[letter] === question.options[keyed];
      });
    showNotice(
      el['question-defect'],
      twinned
        ? 'Atenção: o caderno original repete duas alternativas idênticas nesta questão, ' +
            'que na prática oferece três respostas distintas.' +
            (answerHasTwin
              ? ' Qualquer uma das duas idênticas conta como correta.'
              : '')
        : '',
      'info'
    );
  }

  /**
   * Redraw the four options in the order this session presents them.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The question on screen.
   * @returns {void}
   */
  function renderOptions(session, question) {
    const list = el.options;
    list.replaceChildren();

    Session.presentedOrder(session, question).forEach(function (sourceLetter, index) {
      const item = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'option';
      button.dataset.letter = sourceLetter;

      const body = document.createElement('span');
      body.className = 'option__body';
      body.append(createSpan(question.options[sourceLetter], 'option__text'));

      button.append(createSpan(Session.LETTERS[index], 'option__letter'), body);

      /* An annulled question has no correct answer, so its options are read,
         not chosen. They are drawn in the same flat grey as an option nobody
         picked, which is the one state in this interface that already means
         "there is nothing to do here". */
      if (Session.isGradable(question)) {
        button.addEventListener('click', function () {
          choose(/** @type {OptionLetter} */ (sourceLetter), false);
        });
      } else {
        button.setAttribute('aria-disabled', 'true');
        button.classList.add('option--muted');
      }

      item.append(button);
      list.append(item);
    });
  }

  /**
   * Mark the options once the question is graded.
   *
   * `aria-disabled` rather than `disabled`, so the options stay reachable by
   * keyboard and by a screen reader after the answer — the guard against a
   * second choice lives in the session logic, not in the control.
   *
   * Four states have to be told apart without color: the answer you chose and
   * got right, the answer you chose and got wrong, the right answer you did
   * not choose, and the ones nobody picked. The first three carry an icon and
   * a written tag; the fourth is dimmed to a flat, still-readable grey.
   *
   * @param {Question} question - The graded question.
   * @param {AnswerRecord} record - The grade.
   * @returns {void}
   */
  function markGradedOptions(question, record) {
    const buttons = el.options.querySelectorAll('button.option');
    buttons.forEach(function (node) {
      const button = /** @type {HTMLButtonElement} */ (node);
      const letter = /** @type {OptionLetter} */ (button.dataset.letter);
      button.setAttribute('aria-disabled', 'true');

      const isAnswer = Session.isCorrectChoice(question, letter);
      const isChosen = letter === record.chosen;
      if (!isAnswer && !isChosen) {
        button.classList.add('option--muted');
        return;
      }

      button.classList.add(isAnswer ? 'option--correct' : 'option--incorrect');

      const text = button.querySelector('.option__text');
      if (text) {
        text.prepend(
          createIcon(
            isChosen ? (isAnswer ? 'check-circle' : 'cross-circle') : 'check',
            'option__mark',
            isChosen ? 2 : 3
          )
        );
      }

      const body = button.querySelector('.option__body');
      if (body) {
        const tag = document.createElement('span');
        tag.className = 'option__tag';
        tag.append(
          createIcon(isAnswer ? 'check' : 'cross', '', 3.5),
          createSpan(
            isAnswer
              ? isChosen
                ? 'Sua resposta, correta.'
                : 'Resposta correta, você não marcou.'
              : 'Sua resposta, incorreta.'
          )
        );
        body.append(tag);
      }
    });
  }

  /**
   * Write the correction below the options.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The graded question.
   * @param {AnswerRecord} record - The grade.
   * @returns {void}
   */
  function renderFeedback(session, question, record) {
    const answer = question.answer;

    el['feedback-verdict'].replaceChildren(
      createIcon(record.correct ? 'check-circle' : 'cross-circle', '', 2),
      createSpan(record.correct ? 'Correto' : 'Incorreto')
    );
    el['feedback-verdict'].className =
      'feedback__verdict feedback__verdict--' +
      (record.correct ? 'correct' : 'incorrect');

    el['feedback-answer'].replaceChildren();
    const keyed = answer.letter;
    const lead = document.createTextNode(
      record.correct ? 'A resposta é ' : 'A resposta correta é '
    );
    const quoted = document.createElement('strong');
    quoted.textContent = keyed
      ? endSentence(quoteOption(session, question, keyed))
      : '';
    el['feedback-answer'].append(lead, quoted);
    if (!record.correct) {
      el['feedback-answer'].append(
        document.createTextNode(
          ' Você marcou ' + endSentence(quoteOption(session, question, record.chosen))
        )
      );
    }

    /* The explanation used to justify a deduction and was hedged accordingly.
       It now explains a published answer, so it is labelled as teaching. */
    el['feedback-explanation'].textContent = answer.explanation || '';
    el['feedback-explanation-label'].textContent = answer.explanation
      ? 'Por que esta é a resposta'
      : '';
    el['feedback-order-note'].textContent = orderNote(session, question);
    el['feedback-reference'].textContent = answer.reference
      ? 'Fonte: ' + answer.reference
      : '';
    el.feedback.hidden = false;
  }

  /**
   * Compose the sentence the status region announces after a grade.
   *
   * @param {Session} session - The running session.
   * @param {Question} question - The graded question.
   * @param {AnswerRecord} record - The grade.
   * @returns {string} One complete sentence, scoreboard included.
   */
  function outcomeSentence(session, question, record) {
    const keyed = question.answer.letter;
    const correctText = keyed ? endSentence(quoteOption(session, question, keyed)) : '';
    const verdict = record.correct
      ? 'Correto. A resposta é ' + correctText
      : 'Incorreto. Você marcou ' +
        endSentence(quoteOption(session, question, record.chosen)) +
        ' A resposta correta é ' +
        correctText;

    return (
      verdict +
      ' Placar: ' +
      pluralize(session.correctCount, 'acerto', 'acertos') +
      ', ' +
      pluralize(session.incorrectCount, 'erro', 'erros') +
      ', ' +
      pluralize(
        Session.unansweredCount(session),
        'questão restante',
        'questões restantes'
      ) +
      '.'
    );
  }

  /**
   * Say why "Próxima" is inert, or what the student is looking at when it is not.
   *
   * @param {boolean} settled - Whether the question on screen needs no more input.
   * @param {boolean} gradable - Whether the question has a correct answer at all.
   * @returns {void}
   */
  function renderNextHint(settled, gradable) {
    if (!gradable) {
      el['next-hint'].textContent = 'Questão anulada: não há o que marcar.';
      return;
    }
    el['next-hint'].textContent = settled
      ? ''
      : 'Escolha uma alternativa para liberar o avanço.';
  }

  /**
   * Draw the whole question panel from scratch.
   *
   * @returns {void}
   */
  function renderQuestion() {
    const session = state.session;
    if (!session || Session.isFinished(session)) {
      renderResults();
      return;
    }

    const question = Session.currentQuestion(session, state.byId);
    if (!question) {
      renderResults();
      return;
    }

    el.question.className =
      'question' + (question.excludedReason ? ' question--excluded' : '');

    el['question-heading'].textContent =
      'Questão ' + (session.position + 1) + ' de ' + session.deck.length;

    renderQuestionMeta(question);
    el['question-stem'].textContent = question.stem;
    renderOptions(session, question);

    const gradable = Session.isGradable(question);
    const record = Session.recordOf(session, question);
    if (record) {
      markGradedOptions(question, record);
      renderFeedback(session, question, record);
    } else {
      el.feedback.hidden = true;
    }

    const next = /** @type {HTMLButtonElement} */ (el['next-button']);
    next.disabled = !record && gradable;
    next.textContent =
      session.position === session.deck.length - 1 ? 'Ver resultado' : 'Próxima';
    renderNextHint(Boolean(record) || !gradable, gradable);

    updateScoreboard();
    showPanel('question');
  }

  /**
   * Grade the chosen option.
   *
   * @param {OptionLetter} sourceLetter - The letter as the bank spells it.
   * @param {boolean} fromKeyboard - True when a keyboard shortcut made the choice.
   * @returns {void}
   */
  function choose(sourceLetter, fromKeyboard) {
    const session = state.session;
    const question = Session.currentQuestion(session, state.byId);
    if (!session || !question || Session.isAnswered(session, question)) {
      return;
    }

    const graded = Session.answer(session, question, sourceLetter);
    const record = Session.recordOf(graded, question);
    if (!record) {
      return;
    }

    state.session = graded;
    state.history = AnswerHistory.record(
      state.history,
      question.id,
      record.correct,
      Date.now()
    );
    AppStorage.writeJson(AppStorage.KEYS.history, state.history);
    AppStorage.writeJson(AppStorage.KEYS.session, graded);

    markGradedOptions(question, record);
    renderFeedback(graded, question, record);
    updateScoreboard();

    const next = /** @type {HTMLButtonElement} */ (el['next-button']);
    next.disabled = false;
    renderNextHint(true, true);
    announce(outcomeSentence(graded, question, record));

    /* Focus goes to "Próxima", never to the option that was just graded. That
       option is now aria-disabled, so it swallows Enter and does nothing with
       it, which is what left a keyboard user stranded after answering with
       a-d. On the button, Enter advances natively, with no global handler
       involved, and a screen reader announces the next action instead of
       repeating the choice the status region already read out. A pointer user
       is not scrolled away from the correction they are about to read. */
    next.focus({ preventScroll: !fromKeyboard });
    if (fromKeyboard) {
      next.scrollIntoView({ block: 'nearest' });
    }
  }

  /**
   * Grade the option shown under a given letter.
   *
   * @param {number} index - The position of the option on screen, 0 to 3.
   * @returns {void}
   */
  function chooseByPosition(index) {
    const session = state.session;
    const question = Session.currentQuestion(session, state.byId);
    if (!session || !question) {
      return;
    }
    const order = Session.presentedOrder(session, question);
    if (index >= 0 && index < order.length) {
      choose(order[index], true);
    }
  }

  /**
   * Move to the next question, or to the results when the deck is spent.
   *
   * @returns {void}
   */
  function advance() {
    const session = state.session;
    const question = Session.currentQuestion(session, state.byId);
    /* The gradability half of the guard is not optional: an annulled question
       can never be "answered", so requiring an answer here trapped the session
       on it forever once the excluded questions were opted into. */
    if (
      !session ||
      (!Session.isAnswered(session, question) && Session.isGradable(question))
    ) {
      return;
    }

    state.session = Session.advance(session, question);
    AppStorage.writeJson(AppStorage.KEYS.session, state.session);
    renderQuestion();

    /* The panel did not change, so showPanel moved no focus — and the button
       that was just pressed is about to be disabled for the next question. */
    if (state.panel === 'question') {
      el['question-heading'].focus();
    }
  }

  /* ---------- Results ----------------------------------------------------- */

  /**
   * Draw the per-topic accuracy of the session, with the lifetime figure beside it.
   *
   * The bar is a second reading of a number that is also printed: it makes the
   * weak topics findable at a glance without ever being the only signal.
   *
   * @param {Session} session - The finished session.
   * @returns {void}
   */
  function renderTopicStats(session) {
    const stats = Session.topicStats(session, state.byId);
    const lifetime = state.bank
      ? AnswerHistory.byTopic(state.history, state.bank.questions)
      : new Map();

    el['topic-stats'].replaceChildren();
    el['topic-stats-heading'].hidden = stats.length === 0;

    stats.forEach(function (stat) {
      const percent = Math.round((stat.correct / stat.answered) * 100);

      const item = document.createElement('li');
      item.className = 'topic-stat';
      item.append(
        createSpan(topicLabel(stat.topic), 'topic-stat__name'),
        createSpan(
          stat.correct + ' de ' + stat.answered + ' · ' + percent + '%',
          'topic-stat__value'
        )
      );

      const meter = document.createElement('span');
      meter.className = 'topic-stat__meter';
      const fill = document.createElement('span');
      fill.className = 'topic-stat__fill';
      fill.style.width = percent + '%';
      meter.append(fill);
      item.append(meter);

      const overall = lifetime.get(stat.topic);
      if (overall && overall.answered > stat.answered) {
        item.append(
          createSpan(
            overall.correct +
              ' de ' +
              overall.answered +
              ' no histórico (' +
              Math.round((overall.correct / overall.answered) * 100) +
              '%)',
            'topic-stat__history'
          )
        );
      }

      el['topic-stats'].append(item);
    });
  }

  /**
   * Draw one reviewed question, with its options, explanation and reference.
   *
   * The explanation is the teaching material — it says why the published key
   * is right — so it belongs here. This is where the studying happens.
   *
   * @param {Session} session - The finished session.
   * @param {ReviewEntry} entry - The question to review.
   * @returns {HTMLElement} The article, ready to append.
   */
  function createReviewItem(session, entry) {
    const question = entry.question;
    const answer = question.answer;

    const item = document.createElement('article');
    item.className = 'review__item' + (entry.correct ? ' review__item--correct' : '');

    const head = document.createElement('p');
    head.className = 'review__head';
    head.append(
      createSpan(
        [question.exam, 'questão ' + question.number, topicLabel(question.topic)].join(
          ' · '
        ),
        'review__meta'
      )
    );

    const outcome = document.createElement('span');
    outcome.className =
      'review__outcome review__outcome--' + (entry.correct ? 'correct' : 'incorrect');
    outcome.append(
      createIcon(entry.correct ? 'check' : 'cross', '', 3.5),
      createSpan(entry.correct ? 'você acertou' : 'você errou')
    );
    head.append(outcome);

    const stem = document.createElement('p');
    stem.className = 'review__stem';
    stem.textContent = question.stem;

    const options = document.createElement('ul');
    options.className = 'review__options';
    Session.presentedOrder(session, question).forEach(function (letter) {
      const isAnswer = Session.isCorrectChoice(question, letter);
      const isChosen = letter === entry.chosen;

      const option = document.createElement('li');
      option.className =
        'review__option' +
        (isAnswer ? ' review__option--answer' : '') +
        (isChosen && !isAnswer ? ' review__option--chosen' : '');

      if (isAnswer) {
        option.append(createIcon('check', '', 3));
      } else if (isChosen) {
        option.append(createIcon('cross', '', 3));
      } else {
        option.append(createIcon('minus', 'review__marker', 2));
      }

      const suffix = isAnswer
        ? isChosen
          ? ' — resposta correta, você marcou'
          : ' — resposta correta'
        : isChosen
          ? ' — você marcou'
          : '';
      option.append(createSpan(quoteOption(session, question, letter) + suffix));
      options.append(option);
    });

    item.append(head, stem, options);

    if (answer.explanation) {
      const explanation = document.createElement('p');
      explanation.className = 'review__line review__line--explanation';
      explanation.textContent = answer.explanation;
      item.append(explanation);
    }
    const note = orderNote(session, question);
    if (note) {
      const aside = document.createElement('p');
      aside.className = 'review__line review__line--aside';
      aside.textContent = note;
      item.append(aside);
    }
    if (answer.reference) {
      const reference = document.createElement('p');
      reference.className = 'review__line review__line--source';
      reference.textContent = 'Fonte: ' + answer.reference;
      item.append(reference);
    }

    return item;
  }

  /**
   * Draw the review list, honouring the "also show the hits" switch.
   *
   * @returns {void}
   */
  function renderReview() {
    const session = state.session;
    if (!session) {
      return;
    }

    const includeCorrect = /** @type {HTMLInputElement} */ (el['review-toggle'])
      .checked;
    const entries = Session.reviewEntries(session, state.byId, includeCorrect);
    const answered = Session.answeredCount(session);

    el['review-head'].hidden = answered === 0;
    el['review-heading'].hidden = answered === 0;
    el['review-toggle-chip'].hidden = session.correctCount === 0;

    el.review.replaceChildren();
    entries.forEach(function (entry) {
      el.review.append(createReviewItem(session, entry));
    });
  }

  /**
   * Build the block that stands in for a report with nothing to report.
   *
   * @param {string} title - The Portuguese heading.
   * @param {string} detail - One sentence saying what to do next.
   * @returns {HTMLElement} The empty state, ready to append.
   */
  function createEmptyState(title, detail) {
    const box = document.createElement('div');
    box.className = 'empty';
    box.append(createIcon('search', 'empty__icon', 1.7));

    const heading = document.createElement('p');
    heading.className = 'empty__title';
    heading.textContent = title;

    const text = document.createElement('p');
    text.className = 'empty__detail';
    text.textContent = detail;

    box.append(heading, text);
    return box;
  }

  /**
   * End the session and draw the results panel.
   *
   * @returns {void}
   */
  function renderResults() {
    const session = state.session;
    if (!session) {
      showPanel('filters');
      return;
    }

    const answered = Session.answeredCount(session);
    const skipped = session.deck.length - answered;

    /* A session with no answers measured nothing; reporting 0% would be a
       score, and there is no score to report. */
    el['score-summary'].textContent =
      answered === 0
        ? '—'
        : String(Math.round((session.correctCount / answered) * 100)) + '%';
    el['score-label'].textContent = answered === 0 ? '' : 'de acerto';
    el['score-detail'].textContent =
      answered === 0
        ? 'Nenhuma questão respondida nesta sessão.'
        : session.correctCount +
          ' de ' +
          answered +
          ' respondidas' +
          (skipped > 0
            ? ' · ' + skipped + (skipped === 1 ? ' não respondida' : ' não respondidas')
            : '') +
          '.';

    el['result-correct'].textContent = String(session.correctCount);
    el['result-incorrect'].textContent = String(session.incorrectCount);
    el['result-skipped'].textContent = String(skipped);
    el['stat-skipped'].hidden = skipped === 0;

    el['results-empty'].replaceChildren();
    if (answered === 0) {
      el['results-empty'].append(
        createEmptyState(
          'Nada para revisar ainda',
          'Esta sessão foi encerrada antes da primeira resposta. Sorteie de novo quando quiser começar.'
        )
      );
    }

    renderTopicStats(session);
    renderReview();

    /* The session is over: nothing left to resume. */
    AppStorage.remove(AppStorage.KEYS.session);
    state.resumable = null;

    announce(
      answered === 0
        ? 'Sessão encerrada sem respostas.'
        : 'Sessão encerrada. ' +
            session.correctCount +
            ' acertos em ' +
            answered +
            ' questões respondidas.'
    );

    showPanel('results');
  }

  /* ---------- Session control --------------------------------------------- */

  /**
   * Draw a new session from the current filters.
   *
   * @returns {void}
   */
  function startSession() {
    const bank = state.bank;
    if (!bank) {
      return;
    }

    const session = Session.create(
      bank.questions,
      state.preferences.filters,
      state.history,
      {
        signature: state.signature,
        size: state.preferences.sessionSize,
        shuffleOptions: state.preferences.shuffleOptions
      }
    );

    if (!session) {
      showNotice(
        el['filters-notice'],
        'Nenhuma questão corresponde a essa combinação de filtros.',
        'error'
      );
      announce('Nenhuma questão corresponde a essa combinação de filtros.');
      showPanel('filters');
      return;
    }

    showNotice(el['filters-notice'], '');
    state.session = session;
    state.resumable = null;
    el.resume.hidden = true;
    AppStorage.writeJson(AppStorage.KEYS.session, session);
    announce(
      'Sessão iniciada com ' +
        session.deck.length +
        (session.deck.length === 1 ? ' questão.' : ' questões.')
    );
    renderQuestion();
  }

  /**
   * Continue the interrupted session.
   *
   * @returns {void}
   */
  function resumeSession() {
    if (!state.resumable) {
      return;
    }
    state.session = state.resumable;
    state.resumable = null;
    el.resume.hidden = true;
    renderQuestion();
  }

  /**
   * Go back to the filters with every count re-measured.
   *
   * The session that just ended fed every question it graded into the history,
   * so "só as que errei", "nunca respondidas", the per-chip tallies and the
   * "você já respondeu N delas" line are all stale by the time the student
   * gets here. Showing the panel without recounting offered a number that the
   * next draw would not honour.
   *
   * @returns {void}
   */
  function backToFilters() {
    renderBankSummary();
    updateSelection();
    showPanel('filters');
  }

  /**
   * Throw the interrupted session away.
   *
   * @returns {void}
   */
  function discardSession() {
    state.resumable = null;
    AppStorage.remove(AppStorage.KEYS.session);
    el.resume.hidden = true;
    announce('Sessão anterior descartada.');
    el['filters-heading'].focus();
  }

  /* ---------- Loading the bank -------------------------------------------- */

  /**
   * Adopt a validated bank and go to the filters.
   *
   * The bank is never cached in `localStorage`: the file that ships with the
   * app is the only truth, which removes a whole class of staleness bugs.
   *
   * @param {QuestionBank} bank - The validated bank.
   * @param {boolean} borrowed - True when the user loaded it by hand.
   * @returns {void}
   */
  function adoptBank(bank, borrowed) {
    state.bank = bank;
    state.byId = Bank.indexById(bank.questions);
    state.exams = Bank.examsById(bank);
    state.topics = Bank.topicsById(bank);
    state.signature = Bank.signature(bank);
    state.session = null;

    renderFilters();
    renderFooter();

    if (borrowed) {
      state.resumable = null;
      el.resume.hidden = true;
    } else {
      renderResumeOffer();
    }
  }

  /**
   * Take the result of reading a hand-loaded file.
   *
   * @param {BankResult} result - What the validator returned.
   * @returns {void}
   */
  function acceptLoadedBank(result) {
    if (result.error || !result.bank) {
      showNotice(el['upload-notice'], result.error || 'Arquivo inválido.', 'error');
      announce('O arquivo não foi aceito. ' + (result.error || ''));
      return;
    }

    adoptBank(result.bank, true);
    showNotice(
      el['upload-notice'],
      'Banco carregado do arquivo, com ' +
        result.bank.questions.length +
        ' questões. Ele vale só nesta aba: ao recarregar a página o banco publicado volta.',
      'info'
    );
    announce(
      'Banco carregado do arquivo, com ' + result.bank.questions.length + ' questões.'
    );
    showPanel('filters');
  }

  /**
   * Describe the provenance of the bank in the footer.
   *
   * @returns {void}
   */
  function renderFooter() {
    const bank = state.bank;
    if (!bank) {
      return;
    }
    const excluded = excludedQuestions();
    const sentences = [
      'Os ' +
        bank.questions.length +
        ' gabaritos vêm das chaves de resposta oficiais ' +
        'publicadas das ' +
        bank.exams.length +
        ' provas, conferidas contra os cadernos originais.'
    ];
    if (excluded.length > 0) {
      sentences.push(
        (excluded.length === 1
          ? 'Uma questão fica fora do sorteio por padrão: '
          : excluded.length + ' questões ficam fora do sorteio por padrão: ') +
          describeExcludedParts(excluded) +
          '.'
      );
    }
    el['footer-provenance'].textContent = sentences.join(' ');
  }

  /**
   * Show the failure to load the embedded bank.
   *
   * @param {string} detail - The validator message, in Portuguese.
   * @returns {void}
   */
  function showBankFailure(detail) {
    showNotice(el['error-detail'], detail, 'error');
    announce('Não foi possível carregar o banco de questões. ' + detail);
    showPanel('error', false);
  }

  /* ---------- Events ------------------------------------------------------ */

  /**
   * Wire the drag-and-drop of the secondary bank loader.
   *
   * @returns {void}
   */
  function bindDropzone() {
    /* Without this, a file dropped anywhere else replaces the app with the
       file the browser decided to open. */
    ['dragover', 'drop'].forEach(function (name) {
      document.addEventListener(name, function (event) {
        event.preventDefault();
      });
    });

    const zone = el.dropzone;
    ['dragenter', 'dragover'].forEach(function (name) {
      zone.addEventListener(name, function (event) {
        event.preventDefault();
        zone.classList.add('dropzone--active');
      });
    });
    zone.addEventListener('dragleave', function () {
      zone.classList.remove('dropzone--active');
    });
    zone.addEventListener('drop', function (event) {
      event.preventDefault();
      zone.classList.remove('dropzone--active');
      const transfer = /** @type {DragEvent} */ (event).dataTransfer;
      Bank.readFile(
        transfer && transfer.files ? transfer.files[0] : null,
        acceptLoadedBank
      );
    });

    el['file-input'].addEventListener('change', function (event) {
      const input = /** @type {HTMLInputElement} */ (event.target);
      Bank.readFile(input.files ? input.files[0] : null, acceptLoadedBank);
      /* Clearing it makes selecting the same file twice fire `change` again. */
      input.value = '';
    });
  }

  /**
   * Report whether a control would do anything at all with a key press.
   *
   * A `disabled` button and an `aria-disabled` one both swallow the key and
   * act on nothing, so a global shortcut must not stand aside for them. This
   * is the precise version of "a shortcut yields to whatever has focus": it
   * yields to a control that works, not to one that is merely present.
   *
   * @param {Element | null} control - The focused control, or null.
   * @returns {boolean} True when the control will handle the key itself.
   */
  function handlesKeys(control) {
    if (!control) {
      return false;
    }
    if (control.getAttribute('aria-disabled') === 'true') {
      return false;
    }
    return !(control instanceof HTMLButtonElement && control.disabled);
  }

  /**
   * Wire the global keyboard shortcuts.
   *
   * A shortcut always yields to whatever has focus: `Enter` on a focused,
   * working button must press that button, not advance the question.
   *
   * @returns {void}
   */
  function bindKeyboard() {
    document.addEventListener('keydown', function (event) {
      if (
        el['panel-question'].hidden ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey
      ) {
        return;
      }

      const target = event.target instanceof Element ? event.target : null;
      if (target && target.closest('input, textarea, select, [contenteditable]')) {
        return;
      }

      const position = Session.LETTERS.indexOf(
        /** @type {OptionLetter} */ (String(event.key || '').toLowerCase())
      );
      if (position !== -1) {
        event.preventDefault();
        chooseByPosition(position);
        return;
      }

      if (event.key !== 'Enter') {
        return;
      }
      /* Enter belongs to whatever is focused; hijacking it turned "Encerrar
         sessão" into "Próxima". An inert control is not "whatever is focused"
         for this purpose — it would do nothing with the key. */
      if (
        handlesKeys(
          target && target.closest('button, a[href], summary, [role="button"]')
        )
      ) {
        return;
      }
      if (/** @type {HTMLButtonElement} */ (el['next-button']).disabled) {
        return;
      }
      event.preventDefault();
      advance();
    });
  }

  /**
   * Wire every button and form control.
   *
   * @returns {void}
   */
  function bindControls() {
    el['theme-switch'].addEventListener('change', pickTheme);
    el['filter-form'].addEventListener('change', updateSelection);
    el['filter-form'].addEventListener('submit', function (event) {
      event.preventDefault();
    });
    el['start-button'].addEventListener('click', startSession);
    el['reset-filters-button'].addEventListener('click', resetFilters);
    el['resume-continue'].addEventListener('click', resumeSession);
    el['resume-discard'].addEventListener('click', discardSession);
    el['next-button'].addEventListener('click', advance);
    el['end-button'].addEventListener('click', renderResults);
    el['new-session-button'].addEventListener('click', startSession);
    el['back-to-filters-button'].addEventListener('click', backToFilters);
    el['review-toggle'].addEventListener('change', renderReview);
    bindDropzone();
    bindKeyboard();
  }

  /* ---------- Start ------------------------------------------------------- */

  /**
   * Boot the interface: theme, stored state, bank, first panel.
   *
   * @returns {void}
   */
  function init() {
    cacheElements();

    state.theme = Theme.read();
    renderTheme();

    AppStorage.forgetLegacyKeys();

    /* Opened over file://, or in a window with site data blocked, nothing can
       be remembered. Saying so is better than letting the theme and the
       progress silently reset on every reload. */
    if (!AppStorage.isAvailable()) {
      showNotice(
        el['storage-notice'],
        'O armazenamento local está indisponível neste navegador. O app funciona ' +
          'normalmente, mas o tema, o histórico e a sessão em andamento não serão guardados.',
        'quiet'
      );
    }

    state.preferences = Preferences.normalize(
      AppStorage.readJson(AppStorage.KEYS.preferences)
    );
    state.history = AnswerHistory.normalize(
      AppStorage.readJson(AppStorage.KEYS.history)
    );

    bindControls();

    const embedded = /** @type {{QUESTION_BANK?: unknown}} */ (window).QUESTION_BANK;
    if (typeof embedded === 'undefined') {
      showBankFailure(
        'O arquivo data/question-bank.js não foi carregado. Se você abriu o site a ' +
          'partir de uma cópia local, confirme que a pasta data/ veio junto.'
      );
      return;
    }

    const result = Bank.validate(embedded);
    if (result.error || !result.bank) {
      showBankFailure(result.error || 'Banco inválido.');
      return;
    }

    adoptBank(result.bank, false);
    showPanel('filters', false);

    /* A student who arrives with a narrowed selection saved from last time
       should see it, not wonder why the count is not the whole bank. */
    if (isFiltered(state.preferences.filters)) {
      /** @type {HTMLDetailsElement} */ (el['disclosure-scope']).open = true;
    }
  }

  return { init };
})();
