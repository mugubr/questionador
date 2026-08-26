## Context

O repositório hoje contém apenas dois diretórios de PDFs e a pasta `openspec/`. Não há código, `package.json`, nem git. Levantamento feito sobre os arquivos reais:

- **Todos os 9 PDFs de `Provas/` têm camada de texto** — `pdftotext -layout` extrai limpo, sem necessidade de OCR.
- **Dois marcadores de questão convivem**: `Questão NN` (ENA25, ENA26, AV2-MET, AV2-PROSP) e `QUESTÃO NN` / `QUESTÃO NN.` (ENA18, AV2-PI, AV2-POL).
- **Alternativas sempre `a)`–`d)`**, quatro por questão, sem `e)`.
- **Só ENA25 e ENA26 têm gabarito** (arquivos separados, tabela `QUESTÃO | RESPOSTA CORRETA`, formato idêntico entre os dois).
- **Ambos os gabaritos avisam** que "as questões e as alternativas foram aleatorizadas no sistema Moodle", ou seja: a letra do gabarito vale para *aquele caderno publicado*, que é exatamente o PDF que temos. O casamento por número de questão é válido.

Restrições que moldam o design:

- O usuário decidiu que **o banco entra no app por upload de arquivo JSON**, não por `fetch`. Isso elimina a dependência de servidor HTTP e faz o `index.html` funcionar em `file://`.
- HTML/CSS/JS puro, sem build e sem dependências.

## Goals / Non-Goals

**Goals:**

- Converter as 144 questões dos 7 cadernos em um `questions.json` validável e um `questoes.md` legível.
- Rastrear a procedência de cada resposta: `oficial` (40 questões) vs `derivada` (104 questões), sempre com referência e justificativa.
- Entregar um app estático que sorteia, corrige e pontua, funcionando ao abrir o arquivo direto no navegador.
- Manter o `questoes.md` como superfície de revisão humana, para que respostas derivadas erradas sejam corrigidas sem mexer em código.

**Non-Goals:**

- Backend, autenticação, sincronização entre dispositivos.
- Editor de questões dentro do app.
- Histórico estatístico entre sessões (só o progresso da sessão corrente).
- Reprocessar os PDFs em runtime — a extração é one-off e o resultado é versionado.

## Decisions

### D1. Extração em duas passagens: parser determinístico + revisão assistida

`pdftotext -layout` → parser Python → JSON bruto → revisão.

O parser cobre o que é mecânico (recortar questões, separar alternativas, limpar cabeçalho/rodapé) e **marca explicitamente o que não conseguiu resolver** em vez de adivinhar. Cada questão sai com `parse_status: "ok" | "revisar"`.

*Alternativa descartada:* extrair tudo por LLM em uma passagem só. Rejeitada porque a estrutura dos cadernos é altamente regular — um regex resolve 90% com resultado reproduzível e diffável, e reserva o julgamento para onde ele é de fato necessário (as respostas derivadas).

### D2. Regras concretas de parsing

- **Split de questões**: `^\s*(QUESTÃO|Questão)\s+(\d{1,2})\.?\s*$`. O número capturado é a chave de casamento com o gabarito.
- **Split de alternativas**: `^\s*([a-d])\)\s+`. Tudo antes da primeira alternativa é o enunciado; linhas seguintes indentadas pertencem à alternativa anterior (wrap).
- **Limpeza de cabeçalho/rodapé** antes do split, por padrões observados:
  - `^\d{1,2} de \w+ de \d{4}\s+\w+\s+Página \d+ de \d+$` (AV2)
  - `Etapa 1 – Prova Nacional .* Pg\. \d+/\d+$` (ENA18)
  - `Associação Fórum Nacional de Gestores…`, `Programa de Pós-Graduação em…`, `PROFNIT` isolado (ENA18)
- **Blocos de assertivas romanas** (`I.`, `II.`, `III.`…) são comuns e fazem parte do enunciado — preservados como texto, com quebras de linha mantidas. O JSON guarda o enunciado com `\n` significativo e o app renderiza com `white-space: pre-wrap`.
- **Rodapé no meio da questão**: em AV2-PI a questão 16 é cortada por um rodapé de página. A limpeza acontece **antes** do split, então o enunciado remonta corretamente.

### D3. Três hazards conhecidos vão para revisão manual, não para heurística

1. **Questões de correlação em duas colunas** — ENA25 Questão 14 (`Coluna 1` × `Coluna 2`) sai do `-layout` como texto lado a lado. Marcada `parse_status: "revisar"` e reescrita à mão como texto linear.
2. **Questões coladas por quebra de página** — em ENA26, `Questão 04` aparece grudada na última alternativa da 03. O split por regex em início de linha resolve, mas o resultado é conferido pela contagem.
3. **Contagem como asserção de sanidade**: o parser **falha** se o número de questões extraídas não bater com o esperado por arquivo (ENA18=40, ENA25=20, ENA26=20, AV2×4=16 cada) ou se alguma questão não tiver exatamente 4 alternativas. AV2-MET tem 17 linhas iniciando com `a)` contra 16 questões — um falso positivo que o parser precisa isolar e reportar, não silenciar.

### D4. Respostas derivadas: rotuladas, justificadas e citadas

Cada questão sem gabarito oficial recebe:

```json
"resposta": { "letra": "b", "procedencia": "derivada", "confianca": "alta|media|baixa",
              "referencia": "Ref7-Manual_de_Oslo_2018.pdf", "justificativa": "…" }
```

`procedencia: "oficial"` dispensa `confianca` e `justificativa` — a fonte é o próprio gabarito. Os cadernos AV2 e ENA26 frequentemente citam a referência no enunciado ("De acordo com o material *Criando uma marca* (OMPI)…"), o que ancora a derivação num documento específico de `Materiais/`.

*Trade-off aceito:* 72% do banco tem resposta derivada. O dado é honesto sobre isso e o app avisa o usuário.

### D5. App carrega o banco por upload, com cache em `localStorage`

`<input type="file" accept="application/json">` + drag-and-drop → `FileReader` → `JSON.parse` → validação de shape → render. O banco validado é gravado em `localStorage` sob uma chave versionada (`quiz.bank.v1`), então o upload é necessário só na primeira vez.

*Alternativa descartada:* `fetch('data/questions.json')`. Rejeitada porque a política CORS de `file://` bloqueia `fetch` de arquivo local, o que forçaria um servidor HTTP — atrito que o upload elimina. O `questions.json` continua versionado no repo; ele é o arquivo que o usuário sobe.

**Validação na entrada é obrigatória** (fronteira do sistema): JSON malformado, schema inválido, letra de resposta fora de `a`–`d`, ou alternativa faltando produzem erro legível na UI, e o banco em cache é preservado.

### D6. Sorteio por Fisher-Yates sobre um baralho, sem repetição

O sorteio não é `Math.random()` por questão (repetiria). Ao iniciar a sessão, o conjunto filtrado é embaralhado com Fisher-Yates e consumido como um baralho. Quando acaba, a sessão termina e o placar final é exibido.

O embaralhamento produz um **novo array** (`[...arr]`), sem mutar o banco carregado — igual para o estado da sessão, que é substituído a cada transição em vez de mutado in-place.

### D7. Estrutura de arquivos

```
index.html            # marcação semântica: header / main / footer
styles.css            # tokens em :root; sem framework
js/bank.js            # parse + validação do JSON enviado
js/session.js         # baralho, sorteio, correção, placar (lógica pura, testável)
js/storage.js         # wrapper localStorage com try/catch
js/ui.js              # render e eventos
data/questions.json   # banco extraído (o arquivo a subir no app)
data/questoes.md      # versão legível para revisão humana
data/schema.json      # JSON Schema do banco
scripts/extract.py    # extração PDF -> JSON
scripts/validate.py   # valida questions.json contra o schema
```

Módulos ES (`<script type="module">`) funcionam em `file://` apenas com servidor em alguns navegadores; para garantir `file://`, os scripts são carregados como `<script defer>` clássicos, cada um expondo um namespace único no escopo global.

### D8. Formato do banco

```json
{
  "versao": 1,
  "provas": [{ "id": "ENA26", "titulo": "Exame Nacional de Acesso — Ingresso 2026",
               "data": "2025-11-22", "temGabaritoOficial": true }],
  "questoes": [{
    "id": "ENA26-Q01", "prova": "ENA26", "numero": 1,
    "tema": "marcas",
    "enunciado": "…",
    "alternativas": { "a": "…", "b": "…", "c": "…", "d": "…" },
    "resposta": { "letra": "b", "procedencia": "oficial" }
  }]
}
```

`tema` é atribuído na extração a partir da prova e do assunto (ex.: `propriedade-intelectual`, `marcas`, `patentes`, `inovacao`, `metodologia`, `politicas-cti`, `prospeccao`), alimentando o filtro do app.

## Risks / Trade-offs

- **104 respostas derivadas podem conter erros** → procedência e nível de confiança gravados no dado, aviso visual no app, e `questoes.md` como superfície de correção manual sem tocar em código.
- **`pdftotext -layout` distorce tabelas e colunas** (ENA25 Q14) → asserção de contagem no parser, `parse_status: "revisar"` e reescrita manual dos casos marcados; nenhuma heurística de desmontagem de coluna.
- **Cabeçalho/rodapé variando entre provas** → limpeza por lista explícita de padrões por arquivo, não por regra genérica; qualquer questão cujo texto ainda contenha `Página \d+ de \d+` falha a validação.
- **`localStorage` pode estar indisponível** (aba anônima, storage bloqueado) → toda leitura e escrita em `try/catch`; sem cache o app funciona normalmente, apenas exigindo upload a cada sessão.
- **Banco enviado pelo usuário é dado não confiável** → validação de schema na entrada; texto renderizado via `textContent`, nunca `innerHTML`, eliminando XSS a partir de um JSON hostil.
- **Sem gabarito oficial para ENA18 e AV2, não há como medir a acurácia da derivação** → aceito explicitamente; o app nunca apresenta resposta derivada como se fosse oficial.

## Open Questions

- **Taxonomia de temas**: os sete valores em D8 são uma primeira proposta a partir dos enunciados. Podem ser ajustados durante a extração, quando o conteúdo real das 144 questões estiver à vista.
- **Modo de estudo para confiança baixa**: se a derivação de alguma questão ficar genuinamente indecidível, a opção é marcá-la `confianca: "baixa"` e deixar o usuário filtrá-la fora — em vez de removê-la do banco.
