# quiz-runner Specification

## Purpose
TBD - created by archiving change quiz-questoes-profnit. Update Purpose after archive.
## Requirements
### Requirement: Carregamento do banco por upload de arquivo

O app SHALL receber o banco de questões através do upload de um arquivo JSON pelo usuário, sem realizar requisições de rede, de modo a funcionar ao abrir `index.html` diretamente no navegador.

#### Scenario: Upload pelo seletor de arquivos

- **WHEN** o usuário seleciona um arquivo JSON válido no seletor de arquivos
- **THEN** o banco é carregado e a tela de sorteio fica disponível
- **AND** o app exibe o total de questões carregadas

#### Scenario: Upload por arrastar e soltar

- **WHEN** o usuário arrasta um arquivo JSON válido para a área de upload
- **THEN** o comportamento é idêntico ao do seletor de arquivos

#### Scenario: Execução sem servidor HTTP

- **WHEN** `index.html` é aberto via `file://`
- **THEN** o app carrega e opera normalmente, sem erro de CORS

### Requirement: Validação do banco recebido

O app SHALL validar o arquivo enviado antes de usá-lo e SHALL exibir um erro legível sem descartar um banco previamente carregado.

#### Scenario: JSON malformado

- **WHEN** o arquivo enviado não é JSON válido
- **THEN** o app exibe uma mensagem de erro identificando o problema
- **AND** o banco carregado anteriormente permanece ativo

#### Scenario: Schema inválido

- **WHEN** o JSON não contém `versao` e uma lista `questoes` não vazia
- **THEN** o app rejeita o arquivo com mensagem explicando o campo ausente

#### Scenario: Questão com resposta inválida

- **WHEN** alguma questão tem `resposta.letra` fora de `a`–`d` ou não possui as 4 alternativas
- **THEN** o app rejeita o banco identificando a questão inválida

#### Scenario: Conteúdo textual hostil

- **WHEN** o texto de uma questão contém marcação HTML
- **THEN** ela é renderizada como texto literal via `textContent`, sem interpretação de HTML

### Requirement: Persistência do banco e do progresso

O app SHALL armazenar o último banco válido e o progresso da sessão em `localStorage`, e SHALL continuar funcionando quando esse armazenamento estiver indisponível.

#### Scenario: Retorno após recarregar

- **WHEN** o usuário recarrega a página após ter enviado um banco válido
- **THEN** o banco é restaurado do cache, sem exigir novo upload

#### Scenario: Armazenamento indisponível

- **WHEN** `localStorage` lança exceção na leitura ou na escrita
- **THEN** o app opera normalmente, apenas exigindo o upload a cada sessão

#### Scenario: Substituição do banco

- **WHEN** o usuário envia um novo arquivo JSON válido
- **THEN** o banco em cache é substituído e a sessão em andamento é reiniciada

### Requirement: Filtros do conjunto sorteável

O app SHALL permitir restringir o conjunto de questões por prova, por tema e por procedência do gabarito, antes de iniciar a sessão.

#### Scenario: Filtro por prova

- **WHEN** o usuário seleciona apenas `ENA26`
- **THEN** somente as 20 questões desse caderno entram no sorteio

#### Scenario: Filtro por procedência

- **WHEN** o usuário escolhe apenas gabaritos oficiais
- **THEN** somente as 40 questões de ENA25 e ENA26 entram no sorteio

#### Scenario: Filtro sem resultados

- **WHEN** a combinação de filtros não retorna nenhuma questão
- **THEN** o app informa isso e não permite iniciar a sessão

### Requirement: Sorteio sem repetição

O app SHALL sortear as questões embaralhando o conjunto filtrado e consumindo-o como um baralho, sem repetir uma questão dentro da mesma sessão.

#### Scenario: Sequência sem repetição

- **WHEN** o usuário percorre N questões de um conjunto de N
- **THEN** cada questão aparece exatamente uma vez

#### Scenario: Fim do baralho

- **WHEN** a última questão do baralho é respondida
- **THEN** a sessão termina e o placar final é exibido

#### Scenario: Banco preservado

- **WHEN** o conjunto filtrado é embaralhado
- **THEN** o array do banco carregado não é modificado

### Requirement: Resposta e correção imediata

O app SHALL apresentar as 4 alternativas, aceitar uma escolha por questão e corrigir imediatamente, exibindo a justificativa e a referência quando existirem.

#### Scenario: Resposta correta

- **WHEN** o usuário escolhe a alternativa que corresponde ao gabarito
- **THEN** a alternativa é marcada como correta e o acerto entra no placar

#### Scenario: Resposta incorreta

- **WHEN** o usuário escolhe uma alternativa diferente do gabarito
- **THEN** a escolha é marcada como incorreta, a alternativa correta é destacada, e o erro entra no placar

#### Scenario: Justificativa de resposta derivada

- **WHEN** a questão corrigida tem `procedencia: "derivada"`
- **THEN** a justificativa e a referência consultada são exibidas junto da correção

#### Scenario: Escolha travada após corrigir

- **WHEN** a questão já foi corrigida
- **THEN** as alternativas não aceitam nova escolha para aquela questão

### Requirement: Aviso de gabarito derivado

O app SHALL sinalizar visualmente as questões cuja resposta não vem de gabarito oficial, para que o usuário nunca as confunda com resposta oficial.

#### Scenario: Selo em questão derivada

- **WHEN** uma questão com `procedencia: "derivada"` é exibida
- **THEN** um selo de aviso indica que a resposta foi derivada dos materiais de referência

#### Scenario: Questão oficial sem selo

- **WHEN** uma questão com `procedencia: "oficial"` é exibida
- **THEN** nenhum selo de aviso é mostrado

#### Scenario: Indicação de confiança baixa

- **WHEN** uma questão derivada tem `confianca: "baixa"`
- **THEN** o selo diferencia esse nível dos demais

### Requirement: Placar e revisão dos erros

O app SHALL manter o placar da sessão em andamento e SHALL permitir revisar as questões erradas ao final.

#### Scenario: Placar durante a sessão

- **WHEN** o usuário está respondendo
- **THEN** o app mostra acertos, erros e quantas questões restam no baralho

#### Scenario: Revisão ao final

- **WHEN** a sessão termina
- **THEN** o app lista as questões erradas com o enunciado, a resposta escolhida e a resposta correta

#### Scenario: Nova sessão

- **WHEN** o usuário inicia uma nova sessão
- **THEN** o placar é zerado e o conjunto filtrado é reembaralhado

### Requirement: Operação por teclado

O app SHALL permitir responder e avançar pelo teclado, com foco visível.

#### Scenario: Seleção por tecla

- **WHEN** o usuário pressiona `a`, `b`, `c` ou `d`
- **THEN** a alternativa correspondente é selecionada

#### Scenario: Avanço por tecla

- **WHEN** o usuário pressiona `Enter` em uma questão já corrigida
- **THEN** o app avança para a próxima questão do baralho

#### Scenario: Navegação por Tab

- **WHEN** o usuário navega com `Tab`
- **THEN** os controles interativos recebem foco visível, em ordem coerente com a leitura

