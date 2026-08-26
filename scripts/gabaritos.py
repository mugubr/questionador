#!/usr/bin/env python3
"""Lê os gabaritos oficiais publicados em Provas/.

Os dois arquivos têm o mesmo formato: uma tabela QUESTÃO | RESPOSTA CORRETA,
uma linha por questão. Ambos avisam que "as questões e as alternativas foram
aleatorizadas no sistema Moodle" — a letra vale para o caderno publicado, que
é exatamente o PDF de onde as questões foram extraídas, então o casamento por
número de questão é válido.

Uso:
    python3 scripts/gabaritos.py
"""

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROVAS = RAIZ / "Provas"

GABARITOS = {
    "ENA25": {"arquivo": "Gabarito-Final_ENA25.pdf", "esperado": 20},
    "ENA26": {"arquivo": "Gabarito-Final_ENA26.pdf", "esperado": 20},
}

# "     1                        C"
RE_LINHA_GABARITO = re.compile(r"^\s*(\d{1,2})\s+([A-Da-d])\s*$")


def le_gabarito(id_prova, config):
    caminho = DIR_PROVAS / config["arquivo"]
    if not caminho.exists():
        raise SystemExit(f"ERRO: gabarito não encontrado: {caminho}")

    resultado = subprocess.run(
        ["pdftotext", "-layout", str(caminho), "-"], capture_output=True, text=True
    )
    if resultado.returncode != 0:
        raise SystemExit(f"ERRO: pdftotext falhou em {config['arquivo']}")

    respostas = {}
    for linha in resultado.stdout.splitlines():
        casou = RE_LINHA_GABARITO.match(linha)
        if not casou:
            continue
        numero = int(casou.group(1))
        letra = casou.group(2).lower()
        if numero in respostas:
            raise SystemExit(
                f"ERRO: {config['arquivo']} — questão {numero} aparece mais de uma vez"
            )
        respostas[numero] = letra

    esperado = config["esperado"]
    faltando = [n for n in range(1, esperado + 1) if n not in respostas]
    if faltando:
        raise SystemExit(
            f"ERRO: {config['arquivo']} — faltam as respostas das questões {faltando}. "
            f"Encontradas {len(respostas)} de {esperado}."
        )

    extras = sorted(n for n in respostas if n > esperado)
    if extras:
        raise SystemExit(f"ERRO: {config['arquivo']} — questões inesperadas: {extras}")

    return respostas


def carrega_todos():
    return {id_prova: le_gabarito(id_prova, cfg) for id_prova, cfg in GABARITOS.items()}


def main():
    for id_prova, respostas in carrega_todos().items():
        seq = " ".join(f"{n}{respostas[n]}" for n in sorted(respostas))
        print(f"{id_prova} ({len(respostas)} respostas): {seq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
