/**
 * Render e eventos.
 *
 * Regra inegociável desta camada: todo texto vindo do banco é inserido com
 * textContent, nunca com innerHTML. O banco é um arquivo escolhido pelo
 * usuário e, portanto, dado não confiável.
 */
(function () {
  'use strict';

  var ROTULOS_PROCEDENCIA = { oficial: 'Gabarito oficial', derivada: 'Gabarito derivado' };
  var ROTULOS_CONFIANCA = { alta: 'confiança alta', media: 'confiança média', baixa: 'confiança baixa' };

  var estado = {
    banco: null,
    porId: {},
    sessao: null,
    filtros: { provas: [], temas: [], procedencias: [] }
  };

  var el = {};

  function pegar(id) {
    return document.getElementById(id);
  }

  function mapearElementos() {
    [
      'placar', 'placar-acertos', 'placar-erros', 'placar-restantes', 'progresso-barra',
      'painel-upload', 'area-solta', 'entrada-arquivo', 'aviso-upload', 'aviso-armazenamento',
      'painel-filtros', 'resumo-banco', 'formulario-filtros', 'fichas-provas', 'fichas-temas',
      'fichas-procedencias', 'aviso-filtros', 'botao-comecar', 'botao-trocar-banco', 'contagem-selecao',
      'painel-questao', 'questao', 'questao-meta', 'questao-enunciado', 'alternativas',
      'correcao', 'correcao-veredito', 'correcao-nota', 'correcao-fonte',
      'botao-proxima', 'botao-encerrar',
      'painel-fim', 'fim-nota', 'fim-detalhe', 'titulo-revisao', 'revisao',
      'botao-nova', 'botao-voltar-filtros', 'rodape-procedencia'
    ].forEach(function (id) {
      el[id] = pegar(id);
    });
  }

  function mostrarPainel(nome) {
    ['upload', 'filtros', 'questao', 'fim'].forEach(function (painel) {
      el['painel-' + painel].hidden = painel !== nome;
    });
    el.placar.hidden = nome !== 'questao';
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  function exibirAviso(elemento, mensagem, classe) {
    if (!mensagem) {
      elemento.hidden = true;
      elemento.textContent = '';
      return;
    }
    elemento.className = 'aviso aviso--' + (classe || 'erro');
    elemento.textContent = mensagem;
    elemento.hidden = false;
  }

  /* ---------- Upload ----------------------------------------------------- */

  function aceitarResultado(resultado) {
    if (resultado.erro) {
      exibirAviso(el['aviso-upload'], resultado.erro, 'erro');
      return;
    }
    exibirAviso(el['aviso-upload'], '', 'erro');
    adotarBanco(resultado.banco, true);
  }

  function adotarBanco(banco, gravar) {
    estado.banco = banco;
    estado.porId = Session.indexarPorId(banco.questoes);
    estado.sessao = null;

    if (gravar) {
      Storage.gravarBanco(banco);
      Storage.limparSessao();
    }

    montarFiltros();
    atualizarRodape();
    mostrarPainel('filtros');
  }

  function ligarUpload() {
    el['entrada-arquivo'].addEventListener('change', function (evento) {
      Bank.lerArquivo(evento.target.files[0], aceitarResultado);
      evento.target.value = '';
    });

    var area = el['area-solta'];
    ['dragenter', 'dragover'].forEach(function (nome) {
      area.addEventListener(nome, function (evento) {
        evento.preventDefault();
        area.classList.add('solta--ativa');
      });
    });
    ['dragleave', 'drop'].forEach(function (nome) {
      area.addEventListener(nome, function (evento) {
        evento.preventDefault();
        area.classList.remove('solta--ativa');
      });
    });
    area.addEventListener('drop', function (evento) {
      var arquivos = evento.dataTransfer && evento.dataTransfer.files;
      Bank.lerArquivo(arquivos && arquivos[0], aceitarResultado);
    });
  }

  /* ---------- Filtros ---------------------------------------------------- */

  function criarFicha(valor, rotulo, contagem, grupo) {
    var etiqueta = document.createElement('label');
    etiqueta.className = 'ficha';

    var entrada = document.createElement('input');
    entrada.type = 'checkbox';
    entrada.value = valor;
    entrada.dataset.grupo = grupo;

    var texto = document.createElement('span');
    texto.textContent = rotulo;

    var numero = document.createElement('span');
    numero.className = 'ficha__contagem';
    numero.textContent = String(contagem);

    etiqueta.append(entrada, texto, numero);
    return etiqueta;
  }

  function contar(questoes, obter) {
    return questoes.reduce(function (acumulado, questao) {
      var chave = obter(questao);
      acumulado[chave] = (acumulado[chave] || 0) + 1;
      return acumulado;
    }, {});
  }

  function montarFiltros() {
    var questoes = estado.banco.questoes;
    estado.filtros = { provas: [], temas: [], procedencias: [] };

    var porProva = contar(questoes, function (q) { return q.prova; });
    var porTema = contar(questoes, function (q) { return q.tema; });
    var porProcedencia = contar(questoes, function (q) { return q.resposta.procedencia; });

    el['fichas-provas'].replaceChildren();
    estado.banco.provas.forEach(function (prova) {
      if (porProva[prova.id]) {
        el['fichas-provas'].append(criarFicha(prova.id, prova.id, porProva[prova.id], 'provas'));
      }
    });

    el['fichas-temas'].replaceChildren();
    Object.keys(porTema).sort().forEach(function (tema) {
      el['fichas-temas'].append(criarFicha(tema, tema.replace(/-/g, ' '), porTema[tema], 'temas'));
    });

    el['fichas-procedencias'].replaceChildren();
    Object.keys(porProcedencia).sort().forEach(function (procedencia) {
      el['fichas-procedencias'].append(criarFicha(
        procedencia,
        ROTULOS_PROCEDENCIA[procedencia] || procedencia,
        porProcedencia[procedencia],
        'procedencias'
      ));
    });

    var oficiais = porProcedencia.oficial || 0;
    el['resumo-banco'].textContent =
      questoes.length + ' questões de ' + estado.banco.provas.length + ' provas · ' +
      oficiais + ' com gabarito oficial, ' + (questoes.length - oficiais) + ' derivadas.';

    atualizarSelecao();
  }

  function lerFiltros() {
    var filtros = { provas: [], temas: [], procedencias: [] };
    el['formulario-filtros'].querySelectorAll('input[type="checkbox"]:checked')
      .forEach(function (entrada) {
        filtros[entrada.dataset.grupo].push(entrada.value);
      });
    return filtros;
  }

  function atualizarSelecao() {
    estado.filtros = lerFiltros();
    var total = Session.filtrar(estado.banco.questoes, estado.filtros).length;

    el['contagem-selecao'].textContent = total + (total === 1 ? ' questão sorteável' : ' questões sorteáveis');
    el['botao-comecar'].disabled = total === 0;
    exibirAviso(
      el['aviso-filtros'],
      total === 0 ? 'Nenhuma questão corresponde a essa combinação de filtros.' : '',
      'erro'
    );
  }

  /* ---------- Questão ---------------------------------------------------- */

  function criarSelo(texto, modificador) {
    var selo = document.createElement('span');
    selo.className = 'selo selo--' + modificador;
    selo.textContent = texto;
    return selo;
  }

  function renderizarMeta(questao) {
    var meta = el['questao-meta'];
    meta.replaceChildren();

    var identificacao = document.createElement('span');
    identificacao.textContent = questao.prova + ' · questão ' + questao.numero + ' · ' + questao.tema.replace(/-/g, ' ');
    meta.append(identificacao);

    var resposta = questao.resposta;
    if (resposta.procedencia === 'oficial') {
      meta.append(criarSelo('gabarito oficial', 'oficial'));
      return;
    }

    var baixa = resposta.confianca === 'baixa';
    meta.append(criarSelo(
      'gabarito derivado · ' + (ROTULOS_CONFIANCA[resposta.confianca] || resposta.confianca),
      baixa ? 'baixa' : 'derivada'
    ));
  }

  function renderizarAlternativas(questao, registro) {
    var lista = el.alternativas;
    lista.replaceChildren();

    Session.LETRAS.forEach(function (letra) {
      var item = document.createElement('li');
      var botao = document.createElement('button');
      botao.type = 'button';
      botao.className = 'alternativa';
      botao.dataset.letra = letra;

      var marca = document.createElement('span');
      marca.className = 'alternativa__letra';
      marca.textContent = letra;

      var texto = document.createElement('span');
      texto.className = 'alternativa__texto';
      texto.textContent = questao.alternativas[letra];

      botao.append(marca, texto);

      if (registro) {
        botao.disabled = true;
        if (letra === questao.resposta.letra) {
          botao.classList.add('alternativa--certa');
        } else if (letra === registro.escolhida) {
          botao.classList.add('alternativa--errada');
        } else {
          botao.classList.add('alternativa--apagada');
        }
      } else {
        botao.addEventListener('click', function () { responder(letra); });
      }

      item.append(botao);
      lista.append(item);
    });
  }

  function renderizarCorrecao(questao, registro) {
    if (!registro) {
      el.correcao.hidden = true;
      return;
    }

    var resposta = questao.resposta;
    el['correcao-veredito'].textContent = registro.acertou ? 'Correto' : 'Incorreto';
    el['correcao-veredito'].className = 'correcao__veredito correcao__veredito--' +
      (registro.acertou ? 'acerto' : 'erro');

    el['correcao-nota'].replaceChildren();
    if (!registro.acertou) {
      var prefixo = document.createTextNode('Resposta correta: ');
      var forte = document.createElement('strong');
      forte.textContent = resposta.letra + ') ' + questao.alternativas[resposta.letra];
      el['correcao-nota'].append(prefixo, forte);
    }

    el['correcao-fonte'].replaceChildren();
    if (resposta.procedencia === 'derivada') {
      var justificativa = document.createElement('p');
      justificativa.className = 'correcao__nota';
      justificativa.textContent = resposta.justificativa;

      var fonte = document.createElement('span');
      fonte.textContent = 'Fonte: ' + resposta.referencia;

      el['correcao-fonte'].append(justificativa, fonte);
    }

    el.correcao.hidden = false;
  }

  function atualizarPlacar() {
    var sessao = estado.sessao;
    el['placar-acertos'].textContent = String(sessao.acertos);
    el['placar-erros'].textContent = String(sessao.erros);
    el['placar-restantes'].textContent = String(Session.restantes(sessao));

    var total = sessao.baralho.length;
    var feitas = Object.keys(sessao.respostas).length;
    el['progresso-barra'].style.width = total ? (feitas / total * 100) + '%' : '0';
  }

  function renderizarQuestao() {
    var sessao = estado.sessao;
    if (Session.terminou(sessao)) {
      renderizarFim();
      return;
    }

    var questao = Session.questaoAtual(sessao, estado.porId);
    if (!questao) {
      renderizarFim();
      return;
    }

    var registro = sessao.respostas[questao.id] || null;
    var resposta = questao.resposta;

    el.questao.className = 'questao' +
      (resposta.procedencia === 'derivada' ? ' questao--derivada' : '') +
      (resposta.confianca === 'baixa' ? ' questao--baixa' : '');

    renderizarMeta(questao);
    el['questao-enunciado'].textContent = questao.enunciado;
    renderizarAlternativas(questao, registro);
    renderizarCorrecao(questao, registro);

    el['botao-proxima'].disabled = !registro;
    el['botao-proxima'].textContent =
      sessao.posicao === sessao.baralho.length - 1 ? 'Ver resultado' : 'Próxima';

    atualizarPlacar();
    mostrarPainel('questao');
  }

  function responder(letra) {
    var questao = Session.questaoAtual(estado.sessao, estado.porId);
    if (!questao || Session.foiRespondida(estado.sessao, questao)) {
      return;
    }
    estado.sessao = Session.responder(estado.sessao, questao, letra);
    Storage.gravarSessao(estado.sessao);
    renderizarQuestao();
  }

  function avancar() {
    var questao = Session.questaoAtual(estado.sessao, estado.porId);
    if (!Session.foiRespondida(estado.sessao, questao)) {
      return;
    }
    estado.sessao = Session.avancar(estado.sessao, questao);
    Storage.gravarSessao(estado.sessao);
    renderizarQuestao();
  }

  /* ---------- Fim -------------------------------------------------------- */

  function renderizarFim() {
    var sessao = estado.sessao;
    var respondidas = sessao.acertos + sessao.erros;
    var percentual = respondidas ? Math.round(sessao.acertos / respondidas * 100) : 0;

    el['fim-nota'].textContent = percentual + '%';
    el['fim-detalhe'].textContent =
      sessao.acertos + ' de ' + respondidas + ' respondidas' +
      (respondidas < sessao.baralho.length
        ? ' · ' + (sessao.baralho.length - respondidas) + ' não respondidas'
        : '');

    var errados = Session.errosDaSessao(sessao, estado.porId);
    el.revisao.replaceChildren();
    el['titulo-revisao'].hidden = errados.length === 0;

    errados.forEach(function (erro) {
      var questao = erro.questao;
      var item = document.createElement('article');
      item.className = 'revisao__item';

      var cabecalho = document.createElement('p');
      cabecalho.className = 'revisao__linha';
      cabecalho.textContent = questao.prova + ' · questão ' + questao.numero;

      var enunciado = document.createElement('p');
      enunciado.className = 'revisao__enunciado';
      enunciado.textContent = questao.enunciado;

      var escolhida = document.createElement('p');
      escolhida.className = 'revisao__linha revisao__linha--errada';
      escolhida.textContent = 'Você marcou ' + erro.escolhida + ') ' + questao.alternativas[erro.escolhida];

      var correta = document.createElement('p');
      correta.className = 'revisao__linha revisao__linha--certa';
      correta.textContent = 'Correta ' + questao.resposta.letra + ') ' +
        questao.alternativas[questao.resposta.letra];

      item.append(cabecalho, enunciado, escolhida, correta);
      el.revisao.append(item);
    });

    Storage.limparSessao();
    mostrarPainel('fim');
  }

  /* ---------- Sessão ----------------------------------------------------- */

  function comecar() {
    var sessao = Session.criar(estado.banco.questoes, estado.filtros);
    if (!sessao) {
      exibirAviso(el['aviso-filtros'], 'Nenhuma questão corresponde a essa combinação de filtros.', 'erro');
      return;
    }
    estado.sessao = sessao;
    Storage.gravarSessao(sessao);
    renderizarQuestao();
  }

  function atualizarRodape() {
    var questoes = estado.banco.questoes;
    var derivadas = questoes.filter(function (q) { return q.resposta.procedencia === 'derivada'; }).length;
    el['rodape-procedencia'].textContent = derivadas
      ? derivadas + ' das ' + questoes.length + ' questões têm gabarito derivado dos materiais de referência, não publicado oficialmente.'
      : 'Todas as questões têm gabarito oficial.';
  }

  /* ---------- Teclado ---------------------------------------------------- */

  function ligarTeclado() {
    document.addEventListener('keydown', function (evento) {
      if (el['painel-questao'].hidden || evento.metaKey || evento.ctrlKey || evento.altKey) {
        return;
      }
      var alvo = evento.target;
      if (alvo && (alvo.tagName === 'INPUT' || alvo.tagName === 'TEXTAREA')) {
        return;
      }

      var tecla = evento.key.toLowerCase();
      if (Session.LETRAS.indexOf(tecla) !== -1) {
        evento.preventDefault();
        responder(tecla);
        return;
      }
      if (evento.key === 'Enter' && !el['botao-proxima'].disabled) {
        evento.preventDefault();
        avancar();
      }
    });
  }

  /* ---------- Início ----------------------------------------------------- */

  function restaurarBanco() {
    var guardado = Storage.lerBanco();
    if (!guardado) {
      return false;
    }
    var resultado = Bank.validar(guardado);
    if (resultado.erro) {
      return false;
    }
    adotarBanco(resultado.banco, false);
    return true;
  }

  function iniciar() {
    mapearElementos();
    ligarUpload();
    ligarTeclado();

    el['formulario-filtros'].addEventListener('change', atualizarSelecao);
    el['botao-comecar'].addEventListener('click', comecar);
    el['botao-trocar-banco'].addEventListener('click', function () {
      exibirAviso(el['aviso-upload'], '', 'erro');
      mostrarPainel('upload');
    });
    el['botao-proxima'].addEventListener('click', avancar);
    el['botao-encerrar'].addEventListener('click', renderizarFim);
    el['botao-nova'].addEventListener('click', comecar);
    el['botao-voltar-filtros'].addEventListener('click', function () {
      mostrarPainel('filtros');
    });

    if (!Storage.disponivel()) {
      exibirAviso(
        el['aviso-armazenamento'],
        'O armazenamento local está indisponível neste navegador. O app funciona normalmente, mas o banco precisará ser enviado a cada sessão.',
        'nota'
      );
    }

    if (!restaurarBanco()) {
      mostrarPainel('upload');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
