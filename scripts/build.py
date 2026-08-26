#!/usr/bin/env python3
"""Monta data/questions.json e data/questoes.md a partir das camadas do banco.

Camadas, aplicadas nesta ordem:
  1. build/questoes-brutas.json  — saída determinística de scripts/extract.py
  2. data/correcoes.json         — reescritas manuais de parsing
  3. gabaritos oficiais          — ENA25 e ENA26, via scripts/gabaritos.py
  4. data/respostas/*.json       — respostas derivadas, com tema e justificativa
  5. data/temas-oficiais.json    — tema das questões com gabarito oficial

Uso:
    python3 scripts/build.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract import CADERNOS, DIR_BUILD, RAIZ  # noqa: E402
from gabaritos import carrega_todos as carrega_gabaritos  # noqa: E402

DIR_DADOS = RAIZ / "data"
DIR_RESPOSTAS = DIR_DADOS / "respostas"


def carrega_json(caminho, obrigatorio=True):
    if not caminho.exists():
        if obrigatorio:
            raise SystemExit(f"ERRO: arquivo obrigatório ausente: {caminho}")
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def carrega_respostas_derivadas():
    """Une os arquivos por caderno, recusando qualquer id duplicado."""
    if not DIR_RESPOSTAS.exists():
        raise SystemExit(f"ERRO: diretório ausente: {DIR_RESPOSTAS}")

    todas = {}
    for caminho in sorted(DIR_RESPOSTAS.glob("*.json")):
        for qid, dados in carrega_json(caminho).items():
            if qid in todas:
                raise SystemExit(f"ERRO: {qid} definido em mais de um arquivo de respostas")
            todas[qid] = dados
    return todas


def aplica_correcoes(questao, correcoes):
    """Sobrepõe enunciado e alternativas reescritos à mão. Retorna uma cópia."""
    correcao = correcoes.get(questao["id"])
    if not correcao:
        return dict(questao)

    corrigida = dict(questao)
    if "enunciado" in correcao:
        corrigida["enunciado"] = correcao["enunciado"]
    if "alternativas" in correcao:
        corrigida["alternativas"] = dict(correcao["alternativas"])
    corrigida["parse_status"] = "ok"
    corrigida["problemas"] = []
    return corrigida


def monta_resposta(qid, gabaritos, derivadas, erros):
    """Resposta oficial quando há gabarito publicado; derivada caso contrário."""
    prova, _, sufixo = qid.partition("-Q")
    numero = int(sufixo)

    if prova in gabaritos:
        letra = gabaritos[prova].get(numero)
        if letra is None:
            erros.append(f"{qid}: sem entrada no gabarito oficial de {prova}")
            return None, None
        return {"letra": letra, "procedencia": "oficial"}, None

    derivada = derivadas.get(qid)
    if not derivada:
        erros.append(f"{qid}: sem resposta derivada em data/respostas/")
        return None, None

    faltando = [c for c in ("letra", "confianca", "referencia", "justificativa") if not derivada.get(c)]
    if faltando:
        erros.append(f"{qid}: resposta derivada incompleta — falta {', '.join(faltando)}")
        return None, None

    return {
        "letra": derivada["letra"],
        "procedencia": "derivada",
        "confianca": derivada["confianca"],
        "referencia": derivada["referencia"],
        "justificativa": derivada["justificativa"],
    }, derivada.get("tema")


def monta_banco():
    brutas = carrega_json(DIR_BUILD / "questoes-brutas.json")
    correcoes = {k: v for k, v in carrega_json(DIR_DADOS / "correcoes.json").items()
                 if not k.startswith("_")}
    derivadas = carrega_respostas_derivadas()
    temas_oficiais = carrega_json(DIR_DADOS / "temas-oficiais.json")
    gabaritos = carrega_gabaritos()

    erros = []
    questoes = []

    for bruta in brutas:
        questao = aplica_correcoes(bruta, correcoes)
        qid = questao["id"]

        if questao["parse_status"] != "ok":
            erros.append(f"{qid}: ainda marcada para revisão — {'; '.join(questao['problemas'])}")
            continue

        resposta, tema_derivado = monta_resposta(qid, gabaritos, derivadas, erros)
        if resposta is None:
            continue

        tema = temas_oficiais.get(qid) or tema_derivado
        if not tema:
            erros.append(f"{qid}: sem tema atribuído")
            continue

        questoes.append({
            "id": qid,
            "prova": questao["prova"],
            "numero": questao["numero"],
            "tema": tema,
            "enunciado": questao["enunciado"],
            "alternativas": questao["alternativas"],
            "resposta": resposta,
        })

    if erros:
        print(f"FALHOU: {len(erros)} problema(s) ao montar o banco\n", file=sys.stderr)
        for erro in erros:
            print(f"  - {erro}", file=sys.stderr)
        raise SystemExit(1)

    provas = [
        {
            "id": c["id"],
            "titulo": c["titulo"],
            "data": c["data"],
            "arquivo": c["arquivo"],
            "temGabaritoOficial": c["gabarito"] is not None,
        }
        for c in CADERNOS
    ]

    return {"versao": 1, "provas": provas, "questoes": questoes}


def escreve_markdown(banco, destino):
    """Superfície de revisão humana: uma correção aqui não exige tocar em código."""
    titulos = {p["id"]: p for p in banco["provas"]}
    linhas = [
        "# Banco de questões PROFNIT",
        "",
        f"{len(banco['questoes'])} questões extraídas de {len(banco['provas'])} cadernos em `Provas/`.",
        "",
        "Respostas marcadas como **derivada** NÃO vêm de gabarito publicado: foram deduzidas",
        "da fonte citada. Para corrigir uma delas, edite `data/respostas/<caderno>.json` e",
        "rode `python3 scripts/build.py` — nenhum código do app precisa mudar.",
        "",
    ]

    for prova in banco["provas"]:
        do_caderno = [q for q in banco["questoes"] if q["prova"] == prova["id"]]
        origem = "gabarito oficial" if prova["temGabaritoOficial"] else "respostas derivadas"
        linhas += [
            "---",
            "",
            f"## {prova['id']} — {prova['titulo']}",
            "",
            f"Prova de {prova['data']} · `{prova['arquivo']}` · {len(do_caderno)} questões · {origem}",
            "",
        ]

        for questao in do_caderno:
            resposta = questao["resposta"]
            selo = "oficial" if resposta["procedencia"] == "oficial" else f"derivada · confiança {resposta['confianca']}"
            linhas += [f"### {questao['id']} · {questao['tema']}", ""]
            linhas += [f"> {linha}" if linha.strip() else ">" for linha in questao["enunciado"].splitlines()]
            linhas.append("")
            for letra in "abcd":
                marca = "**" if letra == resposta["letra"] else ""
                linhas.append(f"- {marca}{letra}){marca} {questao['alternativas'][letra]}")
            linhas += ["", f"**Resposta: {resposta['letra']}** ({selo})", ""]
            if resposta["procedencia"] == "derivada":
                linhas += [
                    f"- Referência: {resposta['referencia']}",
                    f"- Justificativa: {resposta['justificativa']}",
                    "",
                ]

    destino.write_text("\n".join(linhas), encoding="utf-8")


def main():
    banco = monta_banco()

    destino_json = DIR_DADOS / "questions.json"
    destino_json.write_text(json.dumps(banco, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    destino_md = DIR_DADOS / "questoes.md"
    escreve_markdown(banco, destino_md)

    questoes = banco["questoes"]
    oficiais = sum(1 for q in questoes if q["resposta"]["procedencia"] == "oficial")
    confianca = {}
    for questao in questoes:
        resposta = questao["resposta"]
        if resposta["procedencia"] == "derivada":
            confianca[resposta["confianca"]] = confianca.get(resposta["confianca"], 0) + 1

    print(f"Banco montado: {len(questoes)} questões, {len(banco['provas'])} provas")
    print(f"  gabarito oficial: {oficiais}")
    print(f"  derivadas:        {len(questoes) - oficiais}  {confianca}")
    print(f"\nEscrito: {destino_json.relative_to(RAIZ)}")
    print(f"Escrito: {destino_md.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
