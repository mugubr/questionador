// @ts-check

/**
 * Shared type declarations.
 *
 * Every file in this app is a classic script, so these typedefs land in the
 * global type scope and are referenced by name from the other modules. The
 * file emits no code on purpose: it exists only so `Question`, `Session` and
 * friends are declared once instead of once per module.
 */

/**
 * @typedef {"a" | "b" | "c" | "d"} OptionLetter
 * A letter as it appears in the source exam paper.
 */

/**
 * @typedef {"official"} AnswerSource
 * `official` means a published answer key states this, and nothing else.
 *
 * There used to be a second member, `derived`, for answers deduced from the
 * reference material. Published keys were since recovered and verified for all
 * seven papers, so no row in the bank is derived any more and the concept is
 * gone from the data. A bank that still carries one is stale, and the
 * validator says so rather than pretending to understand it.
 */

/**
 * @typedef {"annulled" | "source-booklet-defect"} ExcludedReason
 * Why a question is never drawn. `annulled` is the official key printing
 * ANULADA where a letter should be; `source-booklet-defect` is an item the
 * published booklet reproduced from another one.
 */

/**
 * @typedef {Object} Topic
 * @property {string} id - Kebab-case, unaccented; what `question.topic` holds.
 * @property {string} label - Portuguese, accented, shown to the student.
 * @property {string} definition - Portuguese, one sentence on what it covers.
 */

/**
 * @typedef {Object} Exam
 * @property {string} id - Proper noun, never translated (`ENA26`).
 * @property {string} title - Portuguese, shown to the student.
 * @property {string} date - ISO `YYYY-MM-DD`.
 * @property {string} file - Source PDF file name.
 * @property {boolean} hasOfficialAnswerKey
 */

/**
 * @typedef {Object} Answer
 * @property {OptionLetter} [letter] - Absent only when the question is excluded.
 * @property {AnswerSource} source
 * @property {string} [reference] - The published key this came from.
 * @property {string} [explanation] - Portuguese; why the keyed option is right.
 */

/**
 * @typedef {Object} Question
 * @property {string} id - Always `<exam>-Q<NN>`.
 * @property {string} exam
 * @property {number} number
 * @property {string} topic - The id of an entry in the bank's `topics`.
 * @property {string} stem - Portuguese.
 * @property {Record<OptionLetter, string>} options
 * @property {Answer} answer
 * @property {string} [duplicateOf] - Set on known repeats in the source paper.
 * @property {string[]} [knownDefects] - Defects of the source, e.g. `identical-options`.
 * @property {ExcludedReason} [excludedReason] - Present means never drawn by default.
 */

/**
 * @typedef {Object} QuestionBank
 * @property {number} version
 * @property {string} [generatedAt]
 * @property {Record<string, string>} [toolchain]
 * @property {Exam[]} exams
 * @property {Topic[]} [topics] - The taxonomy `question.topic` indexes into.
 * @property {Question[]} questions
 */

/**
 * @typedef {Object} BankResult
 * @property {QuestionBank} [bank] - Present when the bank is valid.
 * @property {string} [error] - Portuguese message, present when it is not.
 */

/**
 * @typedef {"all" | "incorrect" | "unanswered"} HistoryFilter
 * `incorrect` keeps the questions whose most recent answer was wrong.
 */

/**
 * @typedef {Object} FilterCriteria
 * @property {string[]} exams - Empty means "do not filter by exam".
 * @property {string[]} topics
 * @property {HistoryFilter} history
 * @property {boolean} includeExcluded - Whether the three excluded questions may be drawn.
 */

/**
 * @typedef {Object} AnswerRecord
 * @property {OptionLetter} chosen - The letter as it exists in the bank.
 * @property {boolean} correct
 */

/**
 * @typedef {Object} Session
 * @property {number} version
 * @property {string} signature - Identifies the bank this deck was drawn from.
 * @property {string[]} deck - Question ids, in draw order.
 * @property {number} position
 * @property {Record<string, AnswerRecord>} answers - Keyed by question id.
 * @property {Record<string, OptionLetter[]>} orders - Presented order per question id.
 * @property {number} correctCount
 * @property {number} incorrectCount
 * @property {number} startedAt - Epoch milliseconds.
 */

/**
 * @typedef {Object} HistoryEntry
 * @property {number} seen
 * @property {number} correct
 * @property {number} incorrect
 * @property {boolean} lastCorrect
 * @property {number} lastAt - Epoch milliseconds.
 */

/**
 * @typedef {Object} AnswerHistory
 * @property {number} version
 * @property {Record<string, HistoryEntry>} questions - Keyed by question id.
 */

/**
 * @typedef {Object} Preferences
 * @property {number} version
 * @property {boolean} shuffleOptions
 * @property {number} sessionSize - `0` means "all the questions that match".
 * @property {FilterCriteria} filters
 */

/** @typedef {"system" | "light" | "dark"} ThemeChoice */

/**
 * @typedef {Object} TopicStat
 * @property {string} topic
 * @property {number} correct
 * @property {number} answered
 */

/**
 * @typedef {Object} ReviewEntry
 * @property {Question} question
 * @property {OptionLetter | null} chosen - Null when the question was skipped.
 * @property {boolean} correct
 */
