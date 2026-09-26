"""Paths, the exam-paper registry, and the constants every stage agrees on.

Anything two stages would otherwise hard-code twice lives here, so that a
number cannot drift between `extract` and `validate` the way the expected
question total once did.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from tools.models import ExcludedReason

REPO_ROOT = Path(__file__).resolve().parent.parent

EXAMS_DIR = REPO_ROOT / "exams"
DATA_DIR = REPO_ROOT / "data"
ANSWERS_DIR = DATA_DIR / "answers"
DOCS_DATA_DIR = REPO_ROOT / "docs" / "data"

RAW_QUESTIONS_PATH = DATA_DIR / "raw-questions.json"
ANSWER_KEYS_PATH = DATA_DIR / "answer-keys.json"
OVERRIDES_PATH = DATA_DIR / "overrides.json"
TOPICS_PATH = DATA_DIR / "topics.json"
QUESTION_BANK_PATH = DATA_DIR / "question-bank.json"
QUESTION_BANK_MD_PATH = DATA_DIR / "question-bank.md"
QUESTION_BANK_JS_PATH = DOCS_DATA_DIR / "question-bank.js"

BANK_VERSION = 1

# Below this, the PDF has no usable text layer and would need OCR instead.
MINIMUM_TEXT_LINES = 10

# A stem shorter than this is a parsing failure, not a terse question.
MINIMUM_STEM_LENGTH = 10

# The global assigned by docs/data/question-bank.js, read by a plain <script>.
BANK_GLOBAL_NAME = "QUESTION_BANK"


@dataclass(frozen=True)
class ExamPaper:
    """One exam paper and everything the pipeline needs to process it.

    Attributes:
        id: Short identifier, a proper noun that is never translated.
        file: The exam PDF, relative to ``exams/``.
        title: Portuguese title shown to the student.
        date: Application date, ``YYYY-MM-DD``.
        expected_questions: How many questions the paper holds. A sanity
            assertion: if segmentation disagrees, the run fails.
        answer_key_file: The published answer-key PDF, or None when the paper
            has none and its answers would have to be derived.
    """

    id: str
    file: str
    title: str
    date: str
    expected_questions: int
    answer_key_file: str | None = None

    @property
    def has_official_answer_key(self) -> bool:
        """Report whether a published answer key backs this paper.

        Returns:
            True when an answer-key PDF exists for the paper.
        """
        return self.answer_key_file is not None

    @property
    def pdf_path(self) -> Path:
        """Locate the exam PDF on disk.

        Returns:
            The absolute path of the paper inside ``exams/``.
        """
        return EXAMS_DIR / self.file

    @property
    def answer_key_path(self) -> Path | None:
        """Locate the published answer-key PDF on disk.

        Returns:
            The absolute path of the answer key, or None when there is none.
        """
        return (
            None if self.answer_key_file is None else EXAMS_DIR / self.answer_key_file
        )


# AGENTS.md claims all seven booklets in exams/ match the published PDF byte
# for byte; these are the MD5s that back that claim, so re-checking it later
# means downloading the booklet again and comparing a hash, not eyeballing.
# fmt: off
EXAM_BOOKLET_MD5 = {
    "Prova_ENA18.pdf":                  "c4a2b9a0a4c417341bebbb7a48be89d1",
    "Prova_ENA25.pdf":                  "1aafb4bf7f7fce0680828faebee49da8",
    "Prova_ENA26.pdf":                  "5a2a5501f3405a9777871c65c8f43903",
    "PROFNIT-AV2-PI.pdf":               "28d9fd875dbbacc9a5253e9b4a5e11f8",
    "PROFNIT-AV2-MET.pdf":              "394e541faaadcf45b63ceb70965b1e35",
    "PROFNIT-AV2-POL.pdf":              "226765e1e621ce15b9d090ac8b34d7d6",
    "PROFNIT-AV2-201024-PROSP.pdf":     "b39d5e96b1be002abf555dceea5110c4",
}
# fmt: on

EXAM_PAPERS: tuple[ExamPaper, ...] = (
    ExamPaper(
        id="ENA18",
        file="Prova_ENA18.pdf",
        title="Exame Nacional de Acesso — Edital Suplementar, ingresso em 2018-02",
        date="2018-06-30",
        expected_questions=40,
        answer_key_file="Gabarito-Final_ENA18.pdf",
    ),
    ExamPaper(
        id="ENA25",
        file="Prova_ENA25.pdf",
        title="Exame Nacional de Acesso — Ingresso em 2025",
        date="2024-09-14",
        expected_questions=20,
        answer_key_file="Gabarito-Final_ENA25.pdf",
    ),
    ExamPaper(
        id="ENA26",
        file="Prova_ENA26.pdf",
        title="Exame Nacional de Acesso — Ingresso em 2026",
        date="2025-11-22",
        expected_questions=20,
        answer_key_file="Gabarito-Final_ENA26.pdf",
    ),
    ExamPaper(
        id="AV2-PI",
        file="PROFNIT-AV2-PI.pdf",
        title="Avaliação Nacional — Conceitos e Aplicações de Propriedade Intelectual",
        date="2023-11-18",
        expected_questions=16,
        answer_key_file="Gabarito-Final_AV2-PI.pdf",
    ),
    ExamPaper(
        id="AV2-MET",
        file="PROFNIT-AV2-MET.pdf",
        title="Avaliação Nacional — Metodologia da Pesquisa Científica e Tecnológica",
        date="2021-11-06",
        expected_questions=16,
        answer_key_file="Gabarito-Final_AV2-MET.pdf",
    ),
    ExamPaper(
        id="AV2-POL",
        file="PROFNIT-AV2-POL.pdf",
        title="Avaliação Nacional — Políticas Públicas de CT&I",
        date="2023-07-01",
        expected_questions=16,
        answer_key_file="Gabarito-Final_AV2-POL.pdf",
    ),
    ExamPaper(
        id="AV2-PROSP",
        file="PROFNIT-AV2-201024-PROSP.pdf",
        title="Avaliação Nacional — Prospecção Tecnológica",
        date="2020-10-24",
        expected_questions=16,
        answer_key_file="Gabarito-Final_AV2-PROSP.pdf",
    ),
)

EXAM_PAPERS_BY_ID: Mapping[str, ExamPaper] = MappingProxyType(
    {paper.id: paper for paper in EXAM_PAPERS}
)

EXPECTED_QUESTION_TOTAL = sum(paper.expected_questions for paper in EXAM_PAPERS)

# Questions the source paper prints twice. Both copies are kept and labelled
# rather than dropped, because the printed paper really does number them.
KNOWN_DUPLICATES: Mapping[str, str] = MappingProxyType(
    {
        "AV2-PI-Q14": "AV2-PI-Q13",
        "AV2-PI-Q16": "AV2-PI-Q15",
    }
)

# Defects of the printed paper, reproduced faithfully and recorded so the app
# can warn about them. AV2-MET-Q14 prints the same string as options a and d.
# AV2-MET-Q08's option d ("Apenas IV e V estão corretas") refers to item V,
# but the stem's "Ordenações propostas" list only goes up to IV -- confirmed
# against the printed booklet, not an artifact of the stem-rewrite override.
KNOWN_DEFECTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "AV2-MET-Q08": ("phantom-item-reference",),
        "AV2-MET-Q14": ("identical-options",),
    }
)

# Questions that stay in the bank but must never be drawn, because no letter
# in the bank is a valid answer to the text the bank holds.
#
# AV2-POL-Q14: the official key prints ANULADA where the other rows print a
# letter, so the paper itself withdrew the question.
#
# AV2-PI-Q14 and AV2-PI-Q16: the booklet in exams/ reprints questions 13 and 15
# verbatim as 14 and 16, but the official key gives 13=A, 14=B and 15=C, 16=D.
# A key cannot give two letters to one question, so the real exam had different
# questions at 14 and 16 and the published booklet is defective. Re-keying the
# reprints to B and D would attach an official answer to questions we do not
# have; the text the bank does hold is question 13 and question 15, whose
# letters are read from the key rows of the questions they repeat.
EXCLUDED_QUESTIONS: Mapping[str, ExcludedReason] = MappingProxyType(
    {
        "AV2-PI-Q14": ExcludedReason.SOURCE_BOOKLET_DEFECT,
        "AV2-PI-Q16": ExcludedReason.SOURCE_BOOKLET_DEFECT,
        "AV2-POL-Q14": ExcludedReason.ANNULLED,
    }
)
