#!/usr/bin/env python3
"""Valida data/questions.json contra o contrato descrito em data/schema.json.

Implementado com a biblioteca padrão para manter o projeto sem dependências.
Cada erro identifica a questão e o campo problemáticos.

Uso:
    python3 scripts/validate.py [caminho/para/questions.json]
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PADRAO_ID_QUESTAO = re.compile(r"^[A-Z0-9-]+-Q\d{2}$")
PADRAO_ID_PROVA = re.compile(r"^[A-Z0-9-]+$")
PADRAO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Resíduos de cabeçalho/rodapé. Cobre marcação de página E o cabeçalho
# institucional, que quebra em linhas diferentes conforme o caderno.
PADRAO_RODAPE = re.compile(
    r"Página \d+ de \d+"
    r"|Pg\. \d+/\d+"
    r"|Associação Fórum Nacional de Gestores"
    r"|Programa de Pós-Graduação em"
)

LETRAS = ("a", "b", "c", "d")
PROCEDENCIAS = ("oficial", "derivada")
CONFIANCAS = ("alta", "media", "baixa")
VERSAO_SUPORTADA = 1
TOTAL_ESPERADO = 144

CAMPOS_QUESTAO = {
    "id", "prova", "numero", "tema", "enunciado", "alternativas", "resposta",
}
CAMPOS_RESPOSTA = {
    "letra", "procedencia", "confianca", "referencia", "justificativa",
}


class Erros:
    """Acumula erros para reportar todos de uma vez, em vez de parar no primeiro."""

    def __init__(self):
        self.itens = []

    def add(self, onde, mensagem):
        self.itens.append(f"{onde}: {mensagem}")

    def __bool__(self):
        return bool(self.itens)


def _texto_nao_vazio(valor):
    return isinstance(valor, str) and valor.strip() != ""


def valida_provas(banco, erros):
    provas = banco.get("provas")
    if not isinstance(provas, list) or not provas:
        erros.add("provas", "deve ser uma lista não vazia")
        return set()

    ids = set()
    for indice, prova in enumerate(provas):
        onde = f"provas[{indice}]"
        if not isinstance(prova, dict):
            erros.add(onde, "deve ser um objeto")
            continue

        id_prova = prova.get("id")
        if not _texto_nao_vazio(id_prova) or not PADRAO_ID_PROVA.match(id_prova):
            erros.add(onde, f"id inválido: {id_prova!r}")
        elif id_prova in ids:
            erros.add(onde, f"id duplicado: {id_prova}")
        else:
            ids.add(id_prova)

        if not _texto_nao_vazio(prova.get("titulo")):
            erros.add(onde, "titulo ausente ou vazio")

        if not isinstance(prova.get("temGabaritoOficial"), bool):
            erros.add(onde, "temGabaritoOficial deve ser booleano")

        data = prova.get("data")
        if data is not None and not (isinstance(data, str) and PADRAO_DATA.match(data)):
            erros.add(onde, f"data deve estar em AAAA-MM-DD, veio {data!r}")

    return ids


def valida_alternativas(questao, onde, erros):
    alternativas = questao.get("alternativas")
    if not isinstance(alternativas, dict):
        erros.add(onde, "alternativas deve ser um objeto")
        return

    faltando = [letra for letra in LETRAS if letra not in alternativas]
    if faltando:
        erros.add(onde, f"alternativas faltando: {', '.join(faltando)}")

    extras = sorted(set(alternativas) - set(LETRAS))
    if extras:
        erros.add(onde, f"alternativas inesperadas: {', '.join(extras)}")

    for letra in LETRAS:
        if letra in alternativas and not _texto_nao_vazio(alternativas[letra]):
            erros.add(onde, f"alternativa {letra} vazia")


def valida_resposta(questao, onde, erros):
    resposta = questao.get("resposta")
    if not isinstance(resposta, dict):
        erros.add(onde, "resposta deve ser um objeto")
        return

    extras = sorted(set(resposta) - CAMPOS_RESPOSTA)
    if extras:
        erros.add(onde, f"campos inesperados em resposta: {', '.join(extras)}")

    letra = resposta.get("letra")
    if letra not in LETRAS:
        erros.add(onde, f"resposta.letra deve ser uma de {LETRAS}, veio {letra!r}")

    procedencia = resposta.get("procedencia")
    if procedencia not in PROCEDENCIAS:
        erros.add(onde, f"resposta.procedencia inválida: {procedencia!r}")
        return

    if procedencia == "derivada":
        if resposta.get("confianca") not in CONFIANCAS:
            erros.add(onde, f"derivada exige confianca em {CONFIANCAS}, veio {resposta.get('confianca')!r}")
        if not _texto_nao_vazio(resposta.get("referencia")):
            erros.add(onde, "derivada exige referencia não vazia")
        if not _texto_nao_vazio(resposta.get("justificativa")):
            erros.add(onde, "derivada exige justificativa não vazia")
    else:
        for campo in ("confianca", "justificativa"):
            if campo in resposta:
                erros.add(onde, f"resposta oficial não deve ter {campo}")


def valida_questoes(banco, ids_provas, erros):
    questoes = banco.get("questoes")
    if not isinstance(questoes, list) or not questoes:
        erros.add("questoes", "deve ser uma lista não vazia")
        return

    vistos = set()
    for indice, questao in enumerate(questoes):
        onde = f"questoes[{indice}]"
        if not isinstance(questao, dict):
            erros.add(onde, "deve ser um objeto")
            continue

        id_questao = questao.get("id")
        if _texto_nao_vazio(id_questao):
            onde = id_questao
        if not _texto_nao_vazio(id_questao) or not PADRAO_ID_QUESTAO.match(id_questao):
            erros.add(onde, f"id inválido: {id_questao!r} (esperado como ENA26-Q01)")
        elif id_questao in vistos:
            erros.add(onde, "id duplicado")
        else:
            vistos.add(id_questao)

        extras = sorted(set(questao) - CAMPOS_QUESTAO)
        if extras:
            erros.add(onde, f"campos inesperados: {', '.join(extras)}")

        prova = questao.get("prova")
        if prova not in ids_provas:
            erros.add(onde, f"prova {prova!r} não consta em provas[]")

        numero = questao.get("numero")
        if not isinstance(numero, int) or not 1 <= numero <= 99:
            erros.add(onde, f"numero inválido: {numero!r}")

        if not _texto_nao_vazio(questao.get("tema")):
            erros.add(onde, "tema ausente ou vazio")

        enunciado = questao.get("enunciado")
        if not _texto_nao_vazio(enunciado) or len(enunciado.strip()) < 10:
            erros.add(onde, "enunciado ausente ou curto demais")
        elif PADRAO_RODAPE.search(enunciado):
            erros.add(onde, "enunciado contém resíduo de cabeçalho/rodapé de página")

        valida_alternativas(questao, onde, erros)
        valida_resposta(questao, onde, erros)


def valida(banco, total_esperado=TOTAL_ESPERADO):
    erros = Erros()

    if not isinstance(banco, dict):
        erros.add("raiz", "o banco deve ser um objeto JSON")
        return erros

    if banco.get("versao") != VERSAO_SUPORTADA:
        erros.add("versao", f"esperado {VERSAO_SUPORTADA}, veio {banco.get('versao')!r}")

    ids_provas = valida_provas(banco, erros)
    valida_questoes(banco, ids_provas, erros)

    questoes = banco.get("questoes")
    if isinstance(questoes, list) and total_esperado and len(questoes) != total_esperado:
        erros.add("questoes", f"esperadas {total_esperado} questões, encontradas {len(questoes)}")

    return erros


def main(argv):
    caminho = Path(argv[1]) if len(argv) > 1 else RAIZ / "data" / "questions.json"

    if not caminho.exists():
        print(f"ERRO: arquivo não encontrado: {caminho}", file=sys.stderr)
        return 1

    try:
        banco = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERRO: JSON inválido em {caminho}: {exc}", file=sys.stderr)
        return 1

    erros = valida(banco)

    if erros:
        print(f"FALHOU: {len(erros.itens)} erro(s) em {caminho}\n", file=sys.stderr)
        for item in erros.itens:
            print(f"  - {item}", file=sys.stderr)
        return 1

    questoes = banco["questoes"]
    oficiais = sum(1 for q in questoes if q["resposta"]["procedencia"] == "oficial")
    print(f"OK: {caminho}")
    print(f"  {len(banco['provas'])} provas, {len(questoes)} questões")
    print(f"  {oficiais} com gabarito oficial, {len(questoes) - oficiais} derivadas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
