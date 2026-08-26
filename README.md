# Questionador PROFNIT

Sorteia questões das provas do PROFNIT, corrige na hora e mostra por que aquela
é a resposta.

**➜ [rubensbraz.github.io/questionador-profnit](https://rubensbraz.github.io/questionador-profnit/)**

Abra o link e comece. Não há nada para instalar, nada para enviar, nenhum
cadastro: as 144 questões já vêm carregadas na página.

Se preferir estudar sem internet, baixe o repositório e abra `docs/index.html`
com dois cliques — funciona igual, direto do arquivo.

## Como usar

1. Escolha os filtros (caderno, tema, quantidade, o que você ainda não acertou).
2. Sorteie as questões.
3. Responda; a correção aparece na hora, com a explicação.

**Teclado:** `a`, `b`, `c` e `d` selecionam a alternativa correspondente;
`Enter` avança para a próxima questão depois que a atual já foi corrigida.
Os atalhos cedem a vez para o controle que estiver com o foco, então navegar por
`Tab` e acionar botões com `Enter` continua funcionando normalmente.

**Tema:** o botão de tema alterna entre **sistema**, **claro** e **escuro**.
A escolha fica guardada no seu navegador e vale para as próximas visitas.

## O banco de questões

144 questões, extraídas dos 7 cadernos oficiais em `exams/`.

| Caderno     | Prova                                                     | Data       | Questões |
| ----------- | --------------------------------------------------------- | ---------- | -------: |
| `ENA25`     | Exame Nacional de Acesso — ingresso em 2025                | 2024-09-14 |       20 |
| `ENA26`     | Exame Nacional de Acesso — ingresso em 2026                | 2025-11-22 |       20 |
| `ENA18`     | Exame Nacional de Acesso — edital suplementar 2018-02      | 2018-06-30 |       40 |
| `AV2-PI`    | Avaliação Nacional — Propriedade Intelectual                | 2023-11-18 |       16 |
| `AV2-MET`   | Avaliação Nacional — Metodologia da Pesquisa                | 2021-11-06 |       16 |
| `AV2-POL`   | Avaliação Nacional — Políticas Públicas de CT&I             | 2023-07-01 |       16 |
| `AV2-PROSP` | Avaliação Nacional — Prospecção Tecnológica                 | 2020-10-24 |       16 |

Os 15 temas usados no filtro: informação tecnológica, inovação, marca e
indicação geográfica, patente, desenho industrial, sistema de PI, direito
autoral, prospecção tecnológica, economia da inovação, gestão da inovação na
ICT, política pública de CT&I, metodologia científica, cultivar, transferência
de tecnologia e comunicação científica.

## De onde vem cada resposta

**Todas as 144 respostas vêm do gabarito oficial publicado pela banca.** Os sete
gabaritos estão em `exams/`, ao lado dos cadernos, e foram recuperados do
[arquivo de exames do PROFNIT](https://profnit.org.br/exames/).

Cada gabarito passou por duas verificações antes de ser aceito:

1. **Identidade do caderno por MD5.** O caderno publicado junto com o gabarito
   foi baixado e comparado byte a byte com o arquivo em `exams/`. Os sete batem.
   Isso não é excesso de zelo: o PROFNIT aplicou **duas provas ENA18
   Suplementar diferentes** para o mesmo ingresso, e a outra anula as questões
   06 e 21. Um gabarito da prova irmã pareceria plausível e estaria inteiramente
   errado.
2. **A ressalva de aleatorização.** Os gabaritos das AV2 dizem que se referem ao
   caderno *conforme publicado* — é isso que torna válido casar pelo número da
   questão. O do ENA18 não traz essa frase, mas ali a igualdade de MD5 torna a
   ressalva desnecessária, porque não existe outro caderno para a numeração
   divergir.

Além da resposta, 104 questões trazem uma **explicação** de por que aquela
alternativa está certa e uma **referência** para aprofundar. A explicação não é
o gabarito — o gabarito é oficial. Ela existe para ensinar.

### Três questões ficam fora do sorteio

- **`AV2-POL-Q14` foi anulada** pela própria banca: o gabarito oficial traz
  `ANULADA` no lugar da letra. Ela não tem resposta certa.
- **`AV2-PI-Q14` e `AV2-PI-Q16` são defeito do caderno.** Elas reproduzem
  palavra por palavra as questões 13 e 15, alternativas incluídas — mas o
  gabarito oficial dá `13=A, 14=B` e `15=C, 16=D`. Um gabarito não pode dar duas
  letras para a mesma questão, então a prova real tinha *outras* questões nas
  posições 14 e 16, e o caderno publicado é que está errado. As letras `B` e `D`
  pertencem a questões que ninguém tem.

As três continuam no banco e no arquivo de revisão, com o motivo registrado. O
sorteio apenas não as usa.

## Ressalvas conhecidas

Defeitos dos cadernos originais. Estão reproduzidos com fidelidade e registrados
no dado, em vez de corrigidos em silêncio.

- **A `AV2-MET-Q14` tem duas alternativas iguais.** As alternativas `a` e `d`
  são a mesma frase no PDF original. Na prática, é uma questão de três
  alternativas — e o app avisa isso na tela.
- **Três questões precisaram de enunciado reescrito à mão** porque o layout do
  PDF não se resolve de forma determinística: `ENA25-Q14`, `ENA25-Q09` e
  `AV2-MET-Q08` (correlação em duas colunas, que o `pdftotext -layout` renderiza
  lado a lado) e `ENA18-Q40` (texto de encerramento colado na última
  alternativa). As reescritas estão em `data/overrides.json`, cada uma com o
  motivo registrado.
- **Nem toda explicação tem um PDF de `references/` que a sustente.** As de
  metodologia, por exemplo, se apoiam em normas da ABNT, no Qualis da CAPES e em
  bibliografia clássica, que não estão no repositório. Quando é esse o caso, o
  campo de referência **diz isso** e nomeia a fonte real, em vez de apontar para
  um arquivo que não trata do assunto.

## Achou uma explicação errada?

A resposta em si vem do gabarito oficial, mas a explicação foi escrita à mão e
pode estar mal fundamentada. Corrigir é uma edição de dado, sem mexer em código:

1. Abra `data/answers/<caderno>.json` (por exemplo, `data/answers/AV2-POL.json`).
2. Ajuste a explicação e a referência da questão.
3. Rode a reconstrução:

   ```bash
   python -m tools build
   ```

`data/question-bank.md` é a superfície pensada para essa revisão: traz as 144
questões em formato legível, cada uma com resposta, tema, explicação e
referência. É o melhor lugar para ler tudo de uma vez.

Para trocar uma **letra**, o caminho é outro: confira o gabarito oficial em
`exams/`. Se o app discordar dele, é bug do extrator, não do dado.

## Regenerar o banco a partir dos PDFs

Só é necessário se você mexer nos cadernos ou no extrator. Requer Python 3.14 e
o `pdftotext` do **poppler**.

```bash
python -m tools extract    # exams/*.pdf            -> data/raw-questions.json
python -m tools build      # + correções + gabaritos + respostas -> data/ e docs/
python -m tools validate   # confere o banco publicado contra o contrato
```

> ### ⚠️ O `pdftotext` precisa ser o do poppler
>
> O **Git para Windows** instala um `pdftotext` que é do **Xpdf**, não do
> poppler. Ele tem o mesmo nome, aceita as mesmas opções, não dá erro — e
> produz um banco **diferente**, com outra codificação e outros tipos de traço.
> A extração passa, os testes quebram depois, e a causa não aparece em lugar
> nenhum.
>
> Confira antes de rodar:
>
> ```bash
> pdftotext -v
> ```
>
> A saída precisa citar **`The Poppler Developers`**. Se citar
> `Glyph & Cog, LLC`, é o Xpdf: instale o poppler e garanta que ele venha antes
> no `PATH`.
>
> Instalação: `winget install poppler` no Windows,
> `sudo apt install poppler-utils` no Debian ou Ubuntu,
> `brew install poppler` no macOS.

O extrator **falha em vez de adivinhar**: se a contagem de questões divergir do
esperado, se alguma questão não tiver exatamente 4 alternativas ou se sobrar
resíduo de cabeçalho ou rodapé, ele para e informa tudo o que encontrou. Um
banco silenciosamente incompleto seria pior do que banco nenhum.

## Estrutura

```
docs/                       o app publicado (é o que o GitHub Pages serve)
  index.html
  assets/css/  assets/js/  assets/icons/
  data/question-bank.js     o banco embutido, carregado junto com a página

data/                       o banco e as camadas que o produzem
  schema.json               o contrato do banco
  question-bank.json        o banco canônico (gerado)
  question-bank.md          as 144 questões em formato legível (gerado)
  raw-questions.json        a extração bruta dos PDFs (gerado)
  overrides.json            reescritas manuais de enunciado
  topics.json               a taxonomia e o tema das 144 questões
  answers/*.json            explicações e referências, um arquivo por caderno

tools/                      o pipeline em Python (roda na sua máquina)
tests/                      testes do pipeline e da lógica do app

exams/                      PDFs das provas e dos gabaritos (somente leitura)
references/                 PDFs de referência para aprofundar (somente leitura)
```

Nada fora de `docs/` é publicado. Os PDFs de `exams/` e `references/` ficam no
repositório, mas nunca chegam ao site.

## Privacidade

O app **não faz nenhuma requisição de rede**. Não há CDN, fonte externa,
analytics ou envio de resposta para lugar algum. O banco de questões vem junto
com a página e a correção acontece inteiramente no seu navegador.

O que fica guardado — sua preferência de tema, por exemplo — fica no
`localStorage` da sua máquina e não sai dela. Suas respostas não são registradas
em nenhum servidor, porque não existe servidor.

## Contribuindo

As regras do repositório — política de idioma, docstrings, tipos, contrato do
banco, restrições do app, acessibilidade e testes — estão em
**[AGENTS.md](AGENTS.md)**, que é a fonte única de verdade. Leia antes de abrir
um pull request.

Verificações que rodam na CI e que você pode rodar localmente:

```bash
ruff check . && ruff format --check .
mypy tools tests
python -m pytest
node --test tests/js/
python -m tools validate
```

O ambiente de desenvolvimento sai de `uv sync` — o app em si continua sem
nenhuma dependência.
