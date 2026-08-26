"""Tests for the noise patterns `extract` and `validate` share.

Every regression pinned here was a real defect: the ENA18 footer that stopped
matching because the PDF prints U+00AD where the pattern expected an en dash,
and the remover and the detector disagreeing about what a footer looks like so
that thirteen of them walked into the published bank.
"""

from __future__ import annotations

import unicodedata

import pytest

from tools.text_cleanup import (
    DASH_CHARACTERS,
    close_unbalanced_quotes,
    collapse_space_runs,
    find_residue,
    has_side_by_side_columns,
    is_noise_line,
    mentions_column_matching,
    normalize_dashes,
    normalize_extraction_noise,
    normalize_minus_bullets,
    strip_noise_lines,
    strip_platform_instruction,
    unify_roman_marker_dashes,
)

# Every character a PDF may render where the eye reads a dash. The soft hyphen
# is the one the ENA18 footer actually prints, and it is invisible in an editor.
DASH_VARIANTS = (
    "-",
    "­",
    "‐",
    "‑",
    "‒",
    "–",
    "—",
    "―",
    "−",
)

# The footers the seven papers print, each one carrying a page marker or the
# institutional header, so both the remover and the detector must know it.
NOISE_FOOTERS = (
    "18 de novembro de 2023   PI   Página 7 de 8",
    "Etapa 1 - Prova Nacional de Acesso ao PROFNIT             Pg. 15/15",
    "                              Página 3 de 8",
    "Pg. 1/15",
    "Associação Fórum Nacional de Gestores de Inovação e Transferência de Tecnologia",
    "Propriedade Intelectual e Transferência de Tecnologia para Inovação",
)


@pytest.mark.parametrize("dash", DASH_VARIANTS)
def test_normalize_dashes_folds_every_variant(dash: str) -> None:
    """Fold every dash-like character the PDFs use to a plain hyphen.

    Args:
        dash: One dash character a build of pdftotext may emit.
    """
    assert normalize_dashes(f"Etapa 1 {dash} Prova") == "Etapa 1 - Prova"


def test_dash_characters_covers_every_variant() -> None:
    """Keep the dash table and the dash character class in agreement."""
    assert set(DASH_VARIANTS) <= set(DASH_CHARACTERS)


def test_normalize_dashes_leaves_other_text_alone() -> None:
    """Touch nothing but the dashes."""
    assert normalize_dashes("Patente de invenção") == "Patente de invenção"


@pytest.mark.parametrize("dash", DASH_VARIANTS)
def test_ena18_footer_is_noise_whichever_dash_the_pdf_prints(dash: str) -> None:
    """Recognise the ENA18 footer with any dash the PDF may carry.

    The published PDF prints U+00AD, a soft hyphen, where a regex written
    against a different build of pdftotext expected an en dash. That single
    character silently stopped the footer from being stripped.

    Args:
        dash: The dash character standing between "Etapa 1" and the title.
    """
    line = f"Etapa 1 {dash} Prova Nacional de Acesso ao PROFNIT        Pg. 15/15"
    assert is_noise_line(line) is True


def test_av2_footer_is_noise() -> None:
    """Recognise the AV2 footer, which leads with its application date."""
    assert is_noise_line("18 de novembro de 2023   PI   Página 7 de 8") is True


def test_page_marker_alone_is_noise() -> None:
    """Recognise a line that holds nothing but a page marker."""
    assert is_noise_line("                    Página 3 de 8") is True
    assert is_noise_line("   Pg. 1/15  ") is True


def test_institutional_header_is_noise() -> None:
    """Recognise every line the institutional header breaks into."""
    assert is_noise_line("PROFNIT") is True
    assert is_noise_line("Programa de Pós-Graduação em") is True
    assert (
        is_noise_line(
            "Propriedade Intelectual e Transferência de Tecnologia para Inovação"
        )
        is True
    )


def test_ordinary_stem_text_is_not_noise() -> None:
    """Leave a legitimate stem alone, even when it names a graduate programme.

    Matching the fragment "Programa de Pós-Graduação em" anywhere would reject
    a sentence an exam about academic policy really does write.
    """
    programme = "O Programa de Pós-Graduação em questão foi avaliado."
    assert is_noise_line(programme) is False
    assert is_noise_line("Sobre a patente de invenção, é correto afirmar:") is False


def test_strip_noise_lines_reassembles_a_stem_a_footer_split() -> None:
    """Drop the footer that cuts a stem in half so the halves rejoin.

    In AV2-PI a page footer lands mid-stem, and removing it before segmenting
    is what lets the question reassemble on its own.
    """
    text = (
        "Sobre o registro de desenho industrial, considere que o\n"
        "18 de novembro de 2023   PI   Página 7 de 8\n"
        "PROFNIT\n"
        "prazo de vigência é contado do depósito."
    )
    assert strip_noise_lines(text) == (
        "Sobre o registro de desenho industrial, considere que o\n"
        "prazo de vigência é contado do depósito."
    )


@pytest.mark.parametrize("footer", NOISE_FOOTERS)
def test_remover_and_detector_agree_on_every_footer(footer: str) -> None:
    """Make the noise remover and the residue detector recognise the same text.

    When they disagreed — one matching a run of whitespace, the other a single
    literal space — thirteen footers survived into the published bank while
    every question still reported ``parseStatus: "ok"``.

    Args:
        footer: One header or footer line the papers print.
    """
    assert is_noise_line(footer) is True
    assert find_residue(footer) != ()


def test_find_residue_reports_each_fragment_once() -> None:
    """List every distinct fragment once, in the order it first appears."""
    text = "Página 3 de 8 e de novo Página 3 de 8, depois Pg. 4/15."
    assert find_residue(text) == ("Página 3 de 8", "Pg. 4/15")


def test_find_residue_is_empty_on_clean_text() -> None:
    """Report nothing for text that carries no page furniture."""
    assert find_residue("A patente de invenção vigora por vinte anos.") == ()


def test_find_residue_runs_on_an_option_too() -> None:
    """Find a footer that landed inside an option, not only inside a stem.

    Thirteen questions shipped with a footer inside their options while the
    checks ran on the stem alone.
    """
    option = "As conferências nacionais de CT&I. Etapa 1 - Prova Pg. 15/15"
    assert find_residue(option) == ("Pg. 15/15",)


@pytest.mark.parametrize(
    "stem",
    [
        "Correlacione a coluna 1 com a coluna 2:",
        "Associe a primeira com a segunda coluna:",
        "Relacione as colunas a seguir:",
        "Analise a Coluna I e a Coluna II abaixo:",
        "Observe a coluna 1 e a coluna 2:",
    ],
)
def test_column_matching_is_detected_however_the_paper_words_it(stem: str) -> None:
    """Detect a two-column exercise under every wording the papers use.

    A table escaped detection when the stem said "Associe a primeira com a
    segunda coluna" instead of "correlacione", and again when it numbered its
    columns "I" and "II" in roman instead of "1" and "2".

    Args:
        stem: One wording that announces a column-matching exercise.
    """
    assert mentions_column_matching(stem) is True


def test_ordinary_stem_is_not_column_matching() -> None:
    """Leave a stem that merely mentions an association alone."""
    assert mentions_column_matching("A associação de inventores foi criada.") is False
    assert mentions_column_matching("Sobre a marca tridimensional:") is False


def test_side_by_side_columns_are_detected() -> None:
    """Detect the two-column signature `pdftotext -layout` leaves behind."""
    stem = (
        "1- Marca Nominativa          ( ) Palavra\n2- Marca Mista          ( ) Logotipo"
    )
    assert has_side_by_side_columns(stem) is True


def test_linear_text_has_no_side_by_side_columns() -> None:
    """Leave a stem rewritten as stacked lists alone."""
    stem = "Primeira coluna:\n1- Marca Nominativa\n\nSegunda coluna:\n( ) Palavra"
    assert has_side_by_side_columns(stem) is False


def test_collapse_space_runs() -> None:
    """Collapse the padding a layout-preserving extraction leaves behind."""
    assert collapse_space_runs("I.      A Organização") == "I. A Organização"
    assert collapse_space_runs("dois  espaços") == "dois  espaços"


def test_strip_platform_instruction_removes_the_moodle_prompt() -> None:
    """Remove the trailing "Escolha uma:" the exam platform leaked in."""
    assert strip_platform_instruction("Assinale a correta:\n\nEscolha uma:") == (
        "Assinale a correta:"
    )


def test_strip_platform_instruction_keeps_the_stem_when_it_is_absent() -> None:
    """Leave a stem that never carried the platform prompt untouched."""
    assert strip_platform_instruction("Assinale a correta:") == "Assinale a correta:"


def test_close_unbalanced_quotes_closes_the_paragraph_that_opened_it() -> None:
    """Close the quote at the end of its own paragraph, not the end of the stem.

    Closing at the end of the stem would swallow the sentence that introduces
    the options into the quoted passage.
    """
    text = "Segundo o autor, “a inovação é um processo.\n\nCom base no texto:"
    assert close_unbalanced_quotes(text) == (
        "Segundo o autor, “a inovação é um processo.”\n\nCom base no texto:"
    )


def test_close_unbalanced_quotes_leaves_balanced_text_alone() -> None:
    """Change nothing when every opening quote already has its closer."""
    text = "Segundo o autor, “a inovação é um processo”, o que implica:"
    assert close_unbalanced_quotes(text) == text


def test_normalize_minus_bullets() -> None:
    """Rewrite the mathematical minus ENA25-Q18 uses as a list bullet."""
    assert normalize_minus_bullets("− primeiro\n− segundo") == ("- primeiro\n- segundo")


def test_unify_roman_marker_dashes_only_fires_on_a_mixed_stem() -> None:
    """Unify the roman markers of a stem that mixes two dash characters.

    ENA18-Q01 prints ``I-`` for its first three assertions and ``IV –`` for the
    fourth, which reaches the screen as two different list styles.
    """
    mixed = "I- Primeira\nII- Segunda\nIII- Terceira\nIV – Quarta"
    assert unify_roman_marker_dashes(mixed) == (
        "I- Primeira\nII- Segunda\nIII- Terceira\nIV- Quarta"
    )


def test_unify_roman_marker_dashes_leaves_a_consistent_stem_as_printed() -> None:
    """Leave the spacing of a stem whose markers already agree exactly as it is.

    Spacing after the marker varies harmlessly across twenty other ENA18 stems,
    so it is not part of the trigger and those stems must not be rewritten.
    """
    consistent = "I - Primeira\nII - Segunda"
    assert unify_roman_marker_dashes(consistent) == consistent


def test_normalize_extraction_noise_applies_every_fix_in_order() -> None:
    """Apply the bullet, marker, spacing and trailing fixes in one pass."""
    text = (
        "I- Primeira\nIV – Quarta\n− um item\nI.      A Organização\n\nEscolha uma:\n"
    )
    assert normalize_extraction_noise(text) == (
        "I- Primeira\nIV- Quarta\n- um item\nI. A Organização"
    )


def test_normalize_extraction_noise_composes_accents_to_nfc() -> None:
    """Compose decomposed accents so two spellings of a word compare equal.

    Built with an explicit NFD pass because the two forms are
    indistinguishable on screen, and a bank holding both would break every
    string comparison the app and the pipeline make.
    """
    decomposed = unicodedata.normalize("NFD", "inovação")
    assert decomposed != "inovação"
    assert normalize_extraction_noise(decomposed) == "inovação"
