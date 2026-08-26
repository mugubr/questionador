# Questionador PROFNIT

App estático que sorteia questões das provas do PROFNIT e corrige suas respostas na hora.

HTML, CSS e JavaScript puros — sem build, sem dependências, sem servidor.

## Usar

1. Abra `index.html` no navegador (duplo-clique serve — funciona em `file://`).
2. Envie o arquivo **`data/questions.json`** deste repositório na área de upload.
3. Escolha os filtros e clique em **Sortear questões**.

O banco fica guardado no navegador, então o upload só é necessário na primeira vez.
Se o armazenamento local estiver bloqueado (aba anônima, por exemplo), o app avisa
e continua funcionando — apenas pedindo o arquivo a cada sessão.

**Teclado:** `a`–`d` responde, `Enter` avança.

## O banco de questões

144 questões extraídas dos 7 cadernos em `Provas/`.

| Caderno | Questões | Gabarito |
|---|---:|---|
| `Prova_ENA25` | 20 | oficial |
| `Prova_ENA26` | 20 | oficial |
| `Prova_ENA18` | 40 | derivado |
| `PROFNIT-AV2-PI` | 16 | derivado |
| `PROFNIT-AV2-MET` | 16 | derivado |
| `PROFNIT-AV2-POL` | 16 | derivado |
| `PROFNIT-AV2-201024-PROSP` | 16 | derivado |

### Gabarito oficial vs. derivado

Só **ENA25 e ENA26** têm gabarito publicado — 40 questões, casadas pelo número.

As outras **104** não têm gabarito algum. A resposta delas foi **deduzida** a partir
dos materiais de referência, da legislação e das normas aplicáveis. Cada uma carrega
no dado a fonte consultada, uma justificativa e um nível de confiança:

| Confiança | Questões |
|---|---:|
| alta | 89 |
| média | 13 |
| baixa | 2 |

O app marca essas questões com um selo âmbar (ou vermelho, quando a confiança é baixa)
e mostra a justificativa junto da correção. **Uma resposta derivada pode estar errada** —
o filtro *Gabarito* permite treinar só com as 40 oficiais.

### Corrigir uma resposta derivada

Edite `data/respostas/<caderno>.json` e rode:

```bash
python3 scripts/build.py
```

O arquivo `data/questoes.md` traz as 144 questões em formato legível, com resposta,
procedência, referência e justificativa — é a superfície pensada para essa revisão.
Nenhum código do app precisa mudar.

## Regenerar o banco a partir dos PDFs

Requer `pdftotext` (pacote `poppler-utils`) e Python 3. Sem outras dependências.

```bash
python3 scripts/extract.py     # PDFs -> build/questoes-brutas.json
python3 scripts/build.py       # + gabaritos + correções + respostas -> data/
python3 scripts/validate.py    # confere o banco contra o contrato
```

`extract.py` **falha** se a contagem de questões divergir do esperado, se alguma
questão não tiver exatamente 4 alternativas, ou se sobrar resíduo de cabeçalho e
rodapé — em vez de emitir um banco silenciosamente incompleto.

## Estrutura

```
index.html              app (uma página)
styles.css              tokens de design em :root, sem framework
js/storage.js           localStorage com try/catch em toda operação
js/bank.js              leitura e validação do JSON enviado
js/session.js           baralho, sorteio, correção e placar (lógica pura)
js/ui.js                render e eventos

data/questions.json     o banco — é este arquivo que você envia no app
data/questoes.md        as 144 questões em formato legível, para revisão
data/schema.json        contrato do banco
data/correcoes.json     reescritas manuais de parsing (3 questões)
data/respostas/         as 104 respostas derivadas, por caderno
data/temas-oficiais.json  tema das 40 questões com gabarito oficial

scripts/extract.py      PDFs -> JSON bruto
scripts/gabaritos.py    leitura dos gabaritos oficiais
scripts/build.py        junta as camadas e publica data/
scripts/validate.py     validação do banco publicado

Provas/                 PDFs de origem (somente leitura)
Materiais/              PDFs de referência (somente leitura)
```

## Ressalvas conhecidas

Defeitos do material de origem, mantidos por fidelidade aos cadernos:

- **`PROFNIT-AV2-PI` repete questões.** A 14 é uma cópia da 13 com a numeração das
  assertivas corrompida, e a 16 é idêntica à 15. São 16 questões, mas 14 distintas.
- **Três questões precisaram de reescrita manual** porque o layout do PDF não se
  resolve deterministicamente: `ENA25-Q14` e `AV2-MET-Q08` (correlação em colunas
  que o `pdftotext -layout` renderiza lado a lado) e `ENA18-Q40` (texto de
  encerramento colado na última alternativa). As reescritas estão em
  `data/correcoes.json`, cada uma com o motivo registrado.
- **As respostas do `AV2-MET` citam normas ABNT, o Qualis CAPES e bibliografia de
  metodologia**, não os PDFs de `Materiais/` — esse conteúdo não é coberto por eles.

## Privacidade

O arquivo enviado é lido pelo próprio navegador, com `FileReader`. Não há requisição
de rede em ponto algum do app. O que fica gravado permanece no `localStorage` da sua
máquina.
