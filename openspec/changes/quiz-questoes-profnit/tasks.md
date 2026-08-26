## 1. Estrutura e schema

- [x] 1.1 Criar os diretórios `data/`, `scripts/` e `js/` na raiz do projeto
- [x] 1.2 Escrever `data/schema.json` com o JSON Schema do banco (campos `versao`, `provas[]`, `questoes[]` conforme design D8)
- [x] 1.3 Escrever `scripts/validate.py`, que valida um `questions.json` contra o schema e falha com mensagem identificando o campo e a questão problemáticos
- [x] 1.4 Criar `.gitignore` (ignorar `__pycache__/`, `*.pyc`, arquivos `.txt` intermediários da extração)

## 2. Parser de extração

- [x] 2.1 Em `scripts/extract.py`, implementar a chamada a `pdftotext -layout` por PDF, abortando se o texto extraído tiver menos de 10 linhas
- [x] 2.2 Implementar a limpeza de cabeçalho/rodapé com a lista explícita de padrões por caderno (rodapé AV2 com data/disciplina/página, rodapé `Pg. N/15` do ENA18, cabeçalho institucional do ENA18)
- [x] 2.3 Implementar a segmentação de questões aceitando `QUESTÃO NN`, `QUESTÃO NN.` e `Questão NN`, capturando o número para casamento com o gabarito
- [x] 2.4 Implementar a separação de alternativas por `^\s*([a-d])\)\s+`, tratando linhas indentadas seguintes como continuação da alternativa anterior
- [x] 2.5 Preservar blocos de assertivas romanas (`I.`, `II.`, …) dentro do enunciado, com quebras de linha mantidas e sem confundi-los com alternativas
- [x] 2.6 Implementar as asserções de sanidade: total 144, contagem por caderno (ENA18=40, ENA25=20, ENA26=20, AV2×4=16) e exatamente 4 alternativas por questão — falhando com relatório em caso de divergência
- [x] 2.7 Marcar `parse_status: "revisar"` nas questões não resolvidas deterministicamente e emitir o relatório de extração listando-as
- [x] 2.8 Rodar o parser sobre os 7 cadernos e confirmar que a contagem bate; investigar o falso positivo de `a)` em `PROFNIT-AV2-MET` (17 ocorrências para 16 questões)

## 3. Gabaritos oficiais

- [x] 3.1 Implementar o parser da tabela `QUESTÃO | RESPOSTA CORRETA` dos dois arquivos de gabarito
- [x] 3.2 Casar ENA25 e ENA26 por número de questão, gravando `procedencia: "oficial"` e omitindo `confianca`/`justificativa`
- [x] 3.3 Falhar a extração se um gabarito não fornecer as 20 respostas esperadas
- [x] 3.4 Conferir manualmente 3 questões de cada caderno contra o PDF do gabarito, validando que o casamento por número está correto

## 4. Revisão manual do parsing

- [x] 4.1 Reescrever a questão 14 de `Prova_ENA25` (correlação `Coluna 1` × `Coluna 2`) como texto linear e passar seu `parse_status` para `"ok"`
- [x] 4.2 Resolver todas as demais questões marcadas como `"revisar"` no relatório de extração
- [x] 4.3 Verificar que nenhuma questão contém resíduo de rodapé (`Página \d+ de \d+`, `Pg\. \d+/\d+`)
- [x] 4.4 Atribuir `tema` a cada uma das 144 questões, ajustando a taxonomia proposta no design conforme o conteúdo real

## 5. Respostas derivadas (104 questões)

- [x] 5.1 Extrair o texto dos 9 PDFs de `Materiais/` para consulta durante a derivação
- [x] 5.2 Mapear cada caderno sem gabarito às suas referências prováveis em `Materiais/`, usando as citações presentes nos próprios enunciados
- [x] 5.3 Derivar as 40 respostas de `Prova_ENA18`, cada uma com `confianca`, `referencia` e `justificativa`
- [x] 5.4 Derivar as 16 respostas de `PROFNIT-AV2-PI`
- [x] 5.5 Derivar as 16 respostas de `PROFNIT-AV2-MET`
- [x] 5.6 Derivar as 16 respostas de `PROFNIT-AV2-POL`
- [x] 5.7 Derivar as 16 respostas de `PROFNIT-AV2-201024-PROSP`
- [x] 5.8 Verificar que toda questão derivada tem `procedencia: "derivada"`, `confianca` em `alta|media|baixa`, `referencia` não vazia e `justificativa` não vazia

## 6. Publicação do banco

- [x] 6.1 Gerar `data/questions.json` com as 144 questões e validá-lo com `scripts/validate.py`
- [x] 6.2 Gerar `data/questoes.md` com prova, número, enunciado, alternativas, resposta, procedência e — nas derivadas — referência e justificativa
- [x] 6.3 Confirmar que nenhuma questão publicada permanece com `parse_status: "revisar"`

## 7. Núcleo do app

- [x] 7.1 Criar `index.html` com marcação semântica (`header`/`main`/`footer`) e os scripts carregados como `<script defer>` clássicos, para funcionar em `file://`
- [x] 7.2 Criar `styles.css` com tokens de design em `:root` (cores, tipografia, espaçamento, durações), sem framework
- [x] 7.3 Implementar `js/storage.js`: wrapper de `localStorage` com `try/catch` em toda leitura e escrita, degradando sem erro quando indisponível
- [x] 7.4 Implementar `js/bank.js`: leitura do arquivo via `FileReader`, `JSON.parse` e validação de shape (versão, `questoes` não vazio, 4 alternativas, `resposta.letra` em `a`–`d`), retornando erro legível por caso
- [x] 7.5 Implementar `js/session.js` como lógica pura: filtro do conjunto, embaralhamento Fisher-Yates sobre cópia do array, consumo do baralho sem repetição, correção e placar
- [x] 7.6 Garantir que o estado da sessão é substituído a cada transição, sem mutação in-place, e que o banco carregado nunca é modificado

## 8. Interface

- [x] 8.1 Implementar a tela de upload com seletor de arquivo e arrastar-e-soltar, exibindo o total carregado em caso de sucesso e erro legível em caso de falha
- [x] 8.2 Implementar os filtros por prova, tema e procedência, bloqueando o início da sessão quando a combinação não retornar questões
- [x] 8.3 Implementar a tela de questão: enunciado com `white-space: pre-wrap`, 4 alternativas e escolha única
- [x] 8.4 Implementar a correção imediata: marcar acerto/erro, destacar a alternativa correta e travar a questão contra nova escolha
- [x] 8.5 Exibir justificativa e referência na correção de questões derivadas
- [x] 8.6 Implementar o selo de aviso de gabarito derivado, com variação visual para `confianca: "baixa"` e ausência de selo nas oficiais
- [x] 8.7 Implementar o placar em andamento (acertos, erros, restantes) e a tela final com revisão dos erros
- [x] 8.8 Implementar o botão de nova sessão, zerando o placar e reembaralhando
- [x] 8.9 Renderizar todo texto vindo do banco via `textContent`, sem `innerHTML` em nenhum ponto
- [x] 8.10 Implementar atalhos de teclado (`a`–`d` para selecionar, `Enter` para avançar em questão corrigida) e foco visível na navegação por `Tab`

## 9. Verificação

- [x] 9.1 Abrir `index.html` via `file://`, subir `data/questions.json` e percorrer uma sessão completa sem erro de console
- [x] 9.2 Testar os casos de rejeição: JSON malformado, schema inválido e questão com resposta fora de `a`–`d`, confirmando que o banco anterior sobrevive
- [x] 9.3 Testar a persistência: recarregar a página e confirmar que o banco é restaurado sem novo upload
- [x] 9.4 Testar com `localStorage` bloqueado (aba anônima com storage desabilitado) e confirmar que o app opera exigindo upload
- [x] 9.5 Testar que uma sessão de N questões apresenta cada questão exatamente uma vez e encerra no fim do baralho
- [x] 9.6 Testar um JSON com marcação HTML no enunciado e confirmar que é renderizado como texto literal
- [x] 9.7 Percorrer uma sessão inteira apenas pelo teclado
- [x] 9.8 Verificar responsividade em 375px, 768px e 1440px, sem overflow horizontal
- [x] 9.9 Escrever `README.md` com as instruções de uso (abrir o `index.html`, subir `data/questions.json`) e de reexecução da extração
