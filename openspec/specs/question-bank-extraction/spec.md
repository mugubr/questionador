# question-bank-extraction Specification

## Purpose
TBD - created by archiving change quiz-questoes-profnit. Update Purpose after archive.
## Requirements
### Requirement: Extração de texto dos cadernos de questões

O pipeline SHALL extrair o texto dos 7 cadernos de questões em `Provas/` usando `pdftotext -layout`, preservando a ordem e a indentação necessárias para o parsing subsequente.

#### Scenario: Extração de todos os cadernos

- **WHEN** o script de extração é executado sobre `Provas/`
- **THEN** ele produz um arquivo de texto para cada um dos 7 cadernos (`Prova_ENA18`, `Prova_ENA25`, `Prova_ENA26`, `PROFNIT-AV2-PI`, `PROFNIT-AV2-MET`, `PROFNIT-AV2-POL`, `PROFNIT-AV2-201024-PROSP`)
- **AND** os 2 arquivos de gabarito são processados separadamente, não como cadernos

#### Scenario: PDF sem camada de texto

- **WHEN** `pdftotext` retorna menos de 10 linhas para um PDF de prova
- **THEN** o script aborta com erro identificando o arquivo, em vez de gerar questões vazias

### Requirement: Remoção de cabeçalho e rodapé

O parser SHALL remover cabeçalhos e rodapés de página antes de segmentar as questões, para que enunciados cortados por quebra de página sejam remontados corretamente.

#### Scenario: Rodapé no meio de um enunciado

- **WHEN** o rodapé `18 de novembro de 2023   PI   Página 7 de 8` aparece entre o enunciado e as alternativas da questão 16 de `PROFNIT-AV2-PI`
- **THEN** a questão extraída contém o enunciado completo seguido das 4 alternativas
- **AND** o texto do rodapé não aparece em nenhum campo da questão

#### Scenario: Cabeçalho institucional do ENA18

- **WHEN** as linhas `Associação Fórum Nacional de Gestores…`, `Programa de Pós-Graduação em…` e `PROFNIT` aparecem no topo de cada página de `Prova_ENA18`
- **THEN** essas linhas são removidas antes da segmentação

#### Scenario: Resíduo de rodapé detectado na validação

- **WHEN** o texto de qualquer questão extraída contém `Página \d+ de \d+` ou `Pg\. \d+/\d+`
- **THEN** a validação falha identificando a questão afetada

### Requirement: Segmentação de questões e alternativas

O parser SHALL reconhecer os dois marcadores de questão presentes no acervo e extrair exatamente 4 alternativas rotuladas de `a` a `d` por questão.

#### Scenario: Marcador em caixa alta

- **WHEN** o parser encontra uma linha `QUESTÃO 01` ou `QUESTÃO 01.`
- **THEN** ele inicia uma nova questão de número 1

#### Scenario: Marcador em caixa mista

- **WHEN** o parser encontra uma linha `Questão 01`
- **THEN** ele inicia uma nova questão de número 1

#### Scenario: Enunciado com bloco de assertivas romanas

- **WHEN** o enunciado contém assertivas numeradas `I.`, `II.`, `III.`, `IV.`
- **THEN** o bloco é preservado integralmente no campo de enunciado, com as quebras de linha mantidas
- **AND** as assertivas romanas não são confundidas com alternativas

#### Scenario: Questão colada por quebra de página

- **WHEN** o marcador `Questão 04` aparece imediatamente após a última alternativa da questão 03 em `Prova_ENA26`, sem linha em branco
- **THEN** as duas questões são segmentadas separadamente

### Requirement: Asserção de contagem por caderno

O parser SHALL falhar quando a contagem extraída divergir do esperado, em vez de emitir um banco incompleto.

#### Scenario: Contagem correta

- **WHEN** a extração termina
- **THEN** o total é de 144 questões, distribuídas como ENA18=40, ENA25=20, ENA26=20 e 16 para cada um dos 4 cadernos AV2

#### Scenario: Contagem divergente

- **WHEN** um caderno produz um número de questões diferente do esperado
- **THEN** o script falha reportando o caderno, o esperado e o obtido

#### Scenario: Questão com número de alternativas incorreto

- **WHEN** uma questão extraída não tem exatamente 4 alternativas `a`–`d`
- **THEN** o script falha reportando o identificador da questão

### Requirement: Casamento com gabarito oficial

O pipeline SHALL casar as questões de ENA25 e ENA26 com os gabaritos oficiais correspondentes, pelo número da questão.

#### Scenario: Casamento por número

- **WHEN** o gabarito `Gabarito-Final_ENA26` indica `1 → B`
- **THEN** a questão `ENA26-Q01` recebe `resposta.letra: "b"` e `resposta.procedencia: "oficial"`

#### Scenario: Gabarito incompleto

- **WHEN** um gabarito não fornece as 20 respostas esperadas
- **THEN** o script falha em vez de deixar questões sem resposta silenciosamente

#### Scenario: Resposta oficial dispensa justificativa

- **WHEN** uma questão tem `procedencia: "oficial"`
- **THEN** os campos `confianca` e `justificativa` são omitidos

### Requirement: Derivação e rotulagem das respostas sem gabarito

Para as 104 questões sem gabarito publicado, o pipeline SHALL registrar a resposta derivada acompanhada de procedência, nível de confiança, referência consultada e justificativa.

#### Scenario: Questão derivada completa

- **WHEN** uma questão de `Prova_ENA18` ou de um caderno AV2 recebe resposta
- **THEN** `resposta.procedencia` é `"derivada"`
- **AND** `resposta.confianca` é `"alta"`, `"media"` ou `"baixa"`
- **AND** `resposta.referencia` cita a fonte efetivamente consultada — um arquivo de `Materiais/` quando o conteúdo estiver coberto por ele, ou a norma, lei ou bibliografia pertinente quando não estiver
- **AND** `resposta.justificativa` é um texto não vazio explicando a escolha

#### Scenario: Conteúdo fora do alcance de Materiais/

- **WHEN** a questão trata de assunto não coberto pelos PDFs de `Materiais/` — como as normas ABNT, o Qualis CAPES e a tipologia de pesquisa cobrados em `PROFNIT-AV2-MET`
- **THEN** `resposta.referencia` nomeia a fonte real (norma, lei ou bibliografia da disciplina)
- **AND** nenhuma citação a `Materiais/` é fabricada para satisfazer o formato

#### Scenario: Enunciado que cita a referência

- **WHEN** o enunciado cita explicitamente um material (ex.: "De acordo com o material *Criando uma marca* (OMPI)")
- **THEN** `resposta.referencia` aponta para o arquivo correspondente em `Materiais/`

#### Scenario: Derivação indecidível

- **WHEN** os materiais de referência não sustentam uma única alternativa com segurança
- **THEN** a questão recebe `confianca: "baixa"` e permanece no banco, em vez de ser removida

### Requirement: Marcação de questões que exigem revisão manual

O parser SHALL sinalizar questões cuja estrutura não pôde ser resolvida de forma determinística, em vez de aplicar heurísticas de adivinhação.

#### Scenario: Questão de correlação em duas colunas

- **WHEN** o parser encontra a questão 14 de `Prova_ENA25`, cujo texto tem colunas lado a lado (`Coluna 1` × `Coluna 2`)
- **THEN** a questão é marcada com `parse_status: "revisar"`
- **AND** o relatório de extração lista todas as questões marcadas para revisão

#### Scenario: Revisão concluída

- **WHEN** uma questão marcada é reescrita manualmente como texto linear
- **THEN** seu `parse_status` passa a `"ok"`
- **AND** a validação exige que nenhuma questão publicada permaneça em `"revisar"`

### Requirement: Publicação em dois formatos

O pipeline SHALL publicar o banco em `data/questions.json` para consumo pelo app e em `data/questoes.md` para leitura e revisão humana.

#### Scenario: JSON validado contra o schema

- **WHEN** `data/questions.json` é gerado
- **THEN** ele valida contra `data/schema.json`
- **AND** contém `versao`, a lista de `provas` e as 144 `questoes`

#### Scenario: Markdown de revisão

- **WHEN** `data/questoes.md` é gerado
- **THEN** cada questão aparece com prova, número, enunciado, as 4 alternativas, a resposta, a procedência e — quando derivada — a referência e a justificativa

#### Scenario: Correção manual de uma resposta derivada

- **WHEN** o revisor corrige uma letra de resposta derivada
- **THEN** a correção é feita nos arquivos de dados, sem alteração no código do app

