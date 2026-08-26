#!/usr/bin/env python3
"""Extrai as questões dos cadernos em Provas/ para um JSON bruto.

Passagem determinística: recorta questões, separa alternativas e limpa
cabeçalho/rodapé. O que não é resolvido mecanicamente sai marcado com
parse_status "revisar", em vez de ser adivinhado.

Uso:
    python3 scripts/extract.py            # extrai e escreve build/questoes-brutas.json
    python3 scripts/extract.py --relatorio  # só imprime o relatório
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROVAS = RAIZ / "Provas"
DIR_BUILD = RAIZ / "build"

MINIMO_LINHAS_TEXTO = 10

# Cadernos de questões. A contagem esperada é asserção de sanidade: divergiu, falha.
CADERNOS = [
    {
        "id": "ENA18",
        "arquivo": "Prova_ENA18.pdf",
        "titulo": "Exame Nacional de Acesso — Edital Suplementar, ingresso em 2018-02",
        "data": "2018-06-30",
        "esperado": 40,
        "gabarito": None,
    },
    {
        "id": "ENA25",
        "arquivo": "Prova_ENA25.pdf",
        "titulo": "Exame Nacional de Acesso — Ingresso em 2025",
        "data": "2024-09-14",
        "esperado": 20,
        "gabarito": "Gabarito-Final_ENA25.pdf",
    },
    {
        "id": "ENA26",
        "arquivo": "Prova_ENA26.pdf",
        "titulo": "Exame Nacional de Acesso — Ingresso em 2026",
        "data": "2025-11-22",
        "esperado": 20,
        "gabarito": "Gabarito-Final_ENA26.pdf",
    },
    {
        "id": "AV2-PI",
        "arquivo": "PROFNIT-AV2-PI.pdf",
        "titulo": "Avaliação Nacional — Conceitos e Aplicações de Propriedade Intelectual",
        "data": "2023-11-18",
        "esperado": 16,
        "gabarito": None,
    },
    {
        "id": "AV2-MET",
        "arquivo": "PROFNIT-AV2-MET.pdf",
        "titulo": "Avaliação Nacional — Metodologia da Pesquisa Científica e Tecnológica",
        "data": "2021-11-06",
        "esperado": 16,
        "gabarito": None,
    },
    {
        "id": "AV2-POL",
        "arquivo": "PROFNIT-AV2-POL.pdf",
        "titulo": "Avaliação Nacional — Políticas Públicas de CT&I",
        "data": "2023-07-01",
        "esperado": 16,
        "gabarito": None,
    },
    {
        "id": "AV2-PROSP",
        "arquivo": "PROFNIT-AV2-201024-PROSP.pdf",
        "titulo": "Avaliação Nacional — Prospecção Tecnológica",
        "data": "2020-10-24",
        "esperado": 16,
        "gabarito": None,
    },
]

TOTAL_ESPERADO = sum(c["esperado"] for c in CADERNOS)

# Cabeçalhos e rodapés observados nos PDFs reais. Lista explícita por padrão,
# não regra genérica: um filtro amplo demais comeria texto de enunciado.
PADROES_RUIDO = [
    # Rodapé dos cadernos AV2: "18 de novembro de 2023   PI   Página 7 de 8"
    re.compile(r"^\s*\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s+\S.*?Página\s+\d+\s+de\s+\d+\s*$", re.I),
    # Rodapé do ENA18: "Etapa 1 – Prova Nacional ... Pg. 1/15"
    re.compile(r"^\s*Etapa\s+1\s*[–-].*Pg\.\s*\d+\s*/\s*\d+\s*$", re.I),
    # Qualquer linha que seja só marcação de página
    re.compile(r"^\s*(Página\s+\d+\s+de\s+\d+|Pg\.\s*\d+\s*/\s*\d+)\s*$", re.I),
    # Cabeçalho institucional do ENA18
    re.compile(r"^\s*Associação Fórum Nacional de Gestores.*$", re.I),
    re.compile(r"^\s*Programa de Pós-Graduação em\s*$", re.I),
    re.compile(r"^\s*Programa de Pós-Graduação em Propriedade Intelectual.*$", re.I),
    re.compile(r"^\s*Propriedade Intelectual e Transferência de Tecnologia para Inovação\s*$", re.I),
    re.compile(r"^\s*PROFNIT\s*$"),
]

# Os dois marcadores de questão que convivem no acervo.
RE_MARCADOR_QUESTAO = re.compile(r"^[ \t]*(?:QUESTÃO|Questão)[ \t]+(\d{1,2})\.?[ \t]*$")
# O espaço após o parêntese é opcional: em ENA18-Q37 o PDF traz "c)As conferências".
# O conteúdo, porém, é obrigatório — "a)" sozinho não abre alternativa.
RE_ALTERNATIVA = re.compile(r"^[ \t]*([a-d])\)[ \t]*(\S.*)$")
# Assertivas romanas fazem parte do enunciado e não podem virar alternativa.
RE_ASSERTIVA_ROMANA = re.compile(r"^[ \t]*(?:[IVX]{1,4}|[A-D])[\.\)-][ \t]+")
RE_RUIDO_RESIDUAL = re.compile(r"Página \d+ de \d+|Pg\. \d+/\d+")
# Sinais de layout em colunas, que pdftotext -layout renderiza lado a lado.
RE_COLUNAS = re.compile(r"^\s*Coluna\s+[12]\b", re.I | re.M)
RE_CORRELACIONE = re.compile(r"correlacione|coluna 1 com a coluna 2", re.I)


def pdf_para_texto(caminho_pdf):
    """Roda pdftotext -layout. Aborta se o PDF não tiver camada de texto útil."""
    resultado = subprocess.run(
        ["pdftotext", "-layout", str(caminho_pdf), "-"],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise SystemExit(f"ERRO: pdftotext falhou em {caminho_pdf.name}: {resultado.stderr.strip()}")

    texto = resultado.stdout
    linhas_uteis = [linha for linha in texto.splitlines() if linha.strip()]
    if len(linhas_uteis) < MINIMO_LINHAS_TEXTO:
        raise SystemExit(
            f"ERRO: {caminho_pdf.name} produziu apenas {len(linhas_uteis)} linhas de texto. "
            "O PDF provavelmente não tem camada de texto e exigiria OCR."
        )
    return texto


def limpa_ruido(texto):
    """Remove cabeçalho/rodapé ANTES da segmentação.

    A ordem importa: em AV2-PI a questão 16 é cortada por um rodapé no meio do
    enunciado. Limpando primeiro, o enunciado remonta sozinho.
    """
    mantidas = []
    for linha in texto.splitlines():
        if any(padrao.match(linha) for padrao in PADROES_RUIDO):
            continue
        mantidas.append(linha)
    return "\n".join(mantidas)


def separa_alternativas(linhas):
    """Divide o bloco de uma questão em enunciado e alternativas a)-d).

    Linhas seguintes que não abrem uma nova alternativa são continuação
    (quebra de linha do PDF) da alternativa anterior.
    """
    enunciado = []
    alternativas = {}
    ordem = []
    atual = None

    for linha in linhas:
        casou = RE_ALTERNATIVA.match(linha)
        # Só abre uma alternativa se a letra vier na sequência esperada (a, b, c, d).
        # Isso descarta um "a) ..." solto no meio de um enunciado, que de outro
        # modo reiniciaria a coleta e comeria o resto da questão.
        esperada = "abcd"[len(ordem)] if len(ordem) < 4 else None
        if casou and casou.group(1) == esperada:
            letra, resto = casou.group(1), casou.group(2)
            ordem.append(letra)
            alternativas[letra] = [resto.strip()]
            atual = letra
        elif atual is not None:
            if linha.strip():
                alternativas[atual].append(linha.strip())
        else:
            enunciado.append(linha)

    return (
        "\n".join(enunciado),
        {letra: " ".join(partes).strip() for letra, partes in alternativas.items()},
        ordem,
    )


def normaliza_enunciado(texto):
    """Colapsa linhas em branco repetidas, preservando as quebras significativas
    dos blocos de assertivas romanas."""
    linhas = [linha.rstrip() for linha in texto.splitlines()]
    saida = []
    for linha in linhas:
        if not linha.strip() and (not saida or not saida[-1].strip()):
            continue
        # Assertiva romana mantém a quebra; texto corrido perde a indentação extra.
        saida.append(linha.strip() if not RE_ASSERTIVA_ROMANA.match(linha) else linha.strip())
    return "\n".join(saida).strip()


def segmenta_questoes(texto, caderno):
    """Recorta o texto limpo em questões, pelo marcador de início de linha."""
    linhas = texto.splitlines()
    inicios = []
    for indice, linha in enumerate(linhas):
        casou = RE_MARCADOR_QUESTAO.match(linha)
        if casou:
            inicios.append((indice, int(casou.group(1))))

    questoes = []
    for posicao, (indice, numero) in enumerate(inicios):
        fim = inicios[posicao + 1][0] if posicao + 1 < len(inicios) else len(linhas)
        bloco = linhas[indice + 1:fim]
        enunciado_bruto, alternativas, ordem = separa_alternativas(bloco)
        enunciado = normaliza_enunciado(enunciado_bruto)

        problemas = []
        if len(ordem) != 4:
            problemas.append(f"{len(ordem)} alternativas em vez de 4")

        # Um segundo conjunto a)-d) no mesmo bloco significa que o primeiro é
        # parte do enunciado (questão de correlação). Sem isto, o parser pega o
        # conjunto errado e cola o verdadeiro dentro da alternativa d).
        repetidas = sorted(
            letra for letra in "abcd"
            if sum(1 for l in bloco if RE_ALTERNATIVA.match(l)
                   and RE_ALTERNATIVA.match(l).group(1) == letra) > 1
        )
        if repetidas:
            problemas.append(
                f"conjunto a)-d) duplicado ({', '.join(repetidas)}) — o primeiro "
                "provavelmente pertence ao enunciado"
            )
        if RE_COLUNAS.search(enunciado) or RE_CORRELACIONE.search(enunciado):
            problemas.append("layout em colunas (correlação) — reescrever como texto linear")
        if RE_RUIDO_RESIDUAL.search(enunciado):
            problemas.append("resíduo de rodapé no enunciado")
        if len(enunciado) < 10:
            problemas.append("enunciado curto demais")

        questoes.append({
            "id": f"{caderno['id']}-Q{numero:02d}",
            "prova": caderno["id"],
            "numero": numero,
            "enunciado": enunciado,
            "alternativas": alternativas,
            "parse_status": "ok" if not problemas else "revisar",
            "problemas": problemas,
        })

    return questoes


def extrai_caderno(caderno):
    caminho = DIR_PROVAS / caderno["arquivo"]
    if not caminho.exists():
        raise SystemExit(f"ERRO: caderno não encontrado: {caminho}")

    texto = limpa_ruido(pdf_para_texto(caminho))
    questoes = segmenta_questoes(texto, caderno)

    if len(questoes) != caderno["esperado"]:
        raise SystemExit(
            f"ERRO: {caderno['arquivo']} — esperadas {caderno['esperado']} questões, "
            f"segmentadas {len(questoes)}. Números encontrados: "
            f"{[q['numero'] for q in questoes]}"
        )

    numeros = [q["numero"] for q in questoes]
    if numeros != list(range(1, caderno["esperado"] + 1)):
        raise SystemExit(
            f"ERRO: {caderno['arquivo']} — numeração fora de sequência: {numeros}"
        )

    return questoes


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relatorio", action="store_true", help="só imprime o relatório")
    args = parser.parse_args(argv[1:])

    todas = []
    print("Extraindo cadernos:\n")
    for caderno in CADERNOS:
        questoes = extrai_caderno(caderno)
        revisar = [q for q in questoes if q["parse_status"] == "revisar"]
        marca = "OK " if not revisar else f"{len(revisar)} p/ revisar"
        print(f"  {caderno['id']:<10} {len(questoes):>3} questões   {marca}")
        todas.extend(questoes)

    if len(todas) != TOTAL_ESPERADO:
        raise SystemExit(f"ERRO: total {len(todas)}, esperado {TOTAL_ESPERADO}")

    revisar = [q for q in todas if q["parse_status"] == "revisar"]
    print(f"\nTotal: {len(todas)} questões ({TOTAL_ESPERADO} esperadas) ✓")

    if revisar:
        print(f"\nRELATÓRIO — {len(revisar)} questão(ões) exigindo revisão manual:\n")
        for questao in revisar:
            print(f"  {questao['id']}: {'; '.join(questao['problemas'])}")
    else:
        print("\nNenhuma questão marcada para revisão.")

    if not args.relatorio:
        DIR_BUILD.mkdir(exist_ok=True)
        destino = DIR_BUILD / "questoes-brutas.json"
        destino.write_text(
            json.dumps(todas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nEscrito: {destino.relative_to(RAIZ)}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
