## Why

O material de estudo do PROFNIT está preso em 9 PDFs (`Provas/`) e 9 PDFs de referência (`Materiais/`). Estudar exige abrir o caderno de questões, anotar a resposta, abrir o gabarito em outro arquivo e conferir manualmente — e 5 das 7 provas não têm gabarito publicado. Não há como sortear questões, medir acerto ou revisar erros.

A proposta transforma esse acervo em um banco de questões estruturado (JSON) e um app estático em HTML/CSS/JS que sorteia questões e corrige as respostas na hora.

## What Changes

**Extração (one-off, gera dados versionados)**

- Extrair as **144 questões** das 7 provas via `pdftotext -layout` (todos os PDFs são text-layer; não é preciso OCR):

  | Prova | Questões | Gabarito oficial |
  |---|---|---|
  | `Prova_ENA25` | 20 | ✅ `Gabarito-Final_ENA25` |
  | `Prova_ENA26` | 20 | ✅ `Gabarito-Final_ENA26` |
  | `Prova_ENA18` | 40 | ❌ |
  | `PROFNIT-AV2-PI` | 16 | ❌ |
  | `PROFNIT-AV2-MET` | 16 | ❌ |
  | `PROFNIT-AV2-POL` | 16 | ❌ |
  | `PROFNIT-AV2-201024-PROSP` | 16 | ❌ |

- Casar as 40 questões de ENA25/ENA26 com os gabaritos oficiais.
- Derivar a resposta das **104 questões sem gabarito** a partir dos PDFs de `Materiais/`, registrando em cada questão a procedência (`oficial` vs `derivada`), a referência consultada e uma justificativa curta.
- Publicar dois formatos: **`data/questions.json`** (consumo pelo app) e **`data/questoes.md`** (leitura humana, revisão e correção manual das derivadas).

**App (novo, estático)**

- Página única em HTML/CSS/JS puro (sem build, sem dependências) que **recebe o banco por upload de um arquivo JSON** feito pelo usuário — sem `fetch`, funciona abrindo o `index.html` direto no navegador (`file://`).
- Sorteio aleatório de questões, com filtros por prova, tema e procedência do gabarito.
- Resposta pelo usuário, correção imediata, justificativa e referência da resposta.
- Selo visual de aviso nas questões de gabarito derivado.
- Placar da sessão (acertos/erros/pendentes) e revisão dos erros ao final.
- Persistência do último banco carregado e do progresso em `localStorage`.

Não há mudanças **BREAKING** — o projeto ainda não tem código.

## Capabilities

### New Capabilities

- `question-bank-extraction`: pipeline de extração dos PDFs de `Provas/` para um banco de questões estruturado; parsing dos cadernos de questões, casamento com os gabaritos oficiais, derivação e rotulagem de procedência das respostas sem gabarito, e o schema/validação do JSON publicado.
- `quiz-runner`: aplicação web estática que carrega um banco de questões por upload, sorteia questões conforme os filtros, coleta a resposta do usuário, corrige, exibe justificativa e referência, e mantém placar e progresso da sessão.

### Modified Capabilities

Nenhuma — `openspec/specs/` está vazio, este é o primeiro change do projeto.

## Impact

- **Novos diretórios**: `data/` (banco extraído: `questions.json`, `questoes.md`, `schema.json`), `scripts/` (extração/validação), `app/` ou raiz (`index.html`, `styles.css`, `app.js`).
- **Ferramentas**: `pdftotext` (poppler-utils, já instalado) e `python3` (já instalado) para a extração one-off. O app em si não tem dependências nem etapa de build.
- **Fontes intocadas**: os PDFs em `Provas/` e `Materiais/` são somente-leitura; nada é modificado neles.
- **Risco principal**: a correção das 104 respostas derivadas depende de julgamento sobre os PDFs de referência. Mitigação: campo de procedência no dado, justificativa citando a referência, aviso visual no app e o `questoes.md` como superfície de revisão manual.
- **Fora de escopo**: backend, contas de usuário, sincronização entre dispositivos, estatísticas históricas entre sessões e edição de questões dentro do app.
