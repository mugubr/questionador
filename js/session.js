/**
 * Lógica pura da sessão: filtro, sorteio, correção e placar.
 *
 * Nenhuma função aqui toca no DOM ou em localStorage — por isso é a camada
 * testável do app. Todas retornam NOVOS objetos: nem o banco carregado nem o
 * estado anterior da sessão são mutados.
 */
var Session = (function () {
  'use strict';

  var LETRAS = ['a', 'b', 'c', 'd'];

  /** Valores distintos de um campo, em ordem alfabética. */
  function valoresDe(questoes, campo) {
    var vistos = {};
    questoes.forEach(function (questao) {
      vistos[questao[campo]] = true;
    });
    return Object.keys(vistos).sort();
  }

  function procedenciasDe(questoes) {
    return valoresDe(questoes.map(function (q) {
      return { procedencia: q.resposta.procedencia };
    }), 'procedencia');
  }

  /**
   * Aplica os filtros. Uma lista vazia (ou ausente) significa "não filtrar por
   * este critério" — e não "nenhum resultado".
   */
  function filtrar(questoes, filtros) {
    var criterios = filtros || {};
    return questoes.filter(function (questao) {
      if (criterios.provas && criterios.provas.length && criterios.provas.indexOf(questao.prova) === -1) {
        return false;
      }
      if (criterios.temas && criterios.temas.length && criterios.temas.indexOf(questao.tema) === -1) {
        return false;
      }
      if (criterios.procedencias && criterios.procedencias.length &&
          criterios.procedencias.indexOf(questao.resposta.procedencia) === -1) {
        return false;
      }
      return true;
    });
  }

  /** Fisher-Yates sobre uma CÓPIA: o array recebido nunca é alterado. */
  function embaralhar(itens) {
    var baralho = itens.slice();
    for (var i = baralho.length - 1; i > 0; i -= 1) {
      var j = Math.floor(Math.random() * (i + 1));
      var troca = baralho[i];
      baralho[i] = baralho[j];
      baralho[j] = troca;
    }
    return baralho;
  }

  /** Cria a sessão. Devolve null se o filtro não retornar questões. */
  function criar(questoes, filtros) {
    var selecionadas = filtrar(questoes, filtros);
    if (!selecionadas.length) {
      return null;
    }
    return {
      baralho: embaralhar(selecionadas).map(function (questao) { return questao.id; }),
      posicao: 0,
      respostas: {},
      acertos: 0,
      erros: 0
    };
  }

  function questaoAtual(sessao, porId) {
    if (!sessao || sessao.posicao >= sessao.baralho.length) {
      return null;
    }
    return porId[sessao.baralho[sessao.posicao]] || null;
  }

  function terminou(sessao) {
    return !sessao || sessao.posicao >= sessao.baralho.length;
  }

  function restantes(sessao) {
    if (!sessao) {
      return 0;
    }
    return Math.max(0, sessao.baralho.length - sessao.posicao);
  }

  /**
   * Corrige a escolha e devolve uma NOVA sessão. Uma questão já corrigida não
   * aceita nova escolha: a sessão retorna inalterada.
   */
  function responder(sessao, questao, letra) {
    if (!sessao || !questao || LETRAS.indexOf(letra) === -1) {
      return sessao;
    }
    if (sessao.respostas[questao.id]) {
      return sessao;
    }

    var acertou = letra === questao.resposta.letra;
    var respostas = Object.assign({}, sessao.respostas);
    respostas[questao.id] = { escolhida: letra, acertou: acertou };

    return Object.assign({}, sessao, {
      respostas: respostas,
      acertos: sessao.acertos + (acertou ? 1 : 0),
      erros: sessao.erros + (acertou ? 0 : 1)
    });
  }

  function foiRespondida(sessao, questao) {
    return Boolean(sessao && questao && sessao.respostas[questao.id]);
  }

  /** Avança uma posição. Só avança se a questão corrente já foi corrigida. */
  function avancar(sessao, questao) {
    if (!sessao || !foiRespondida(sessao, questao)) {
      return sessao;
    }
    return Object.assign({}, sessao, { posicao: sessao.posicao + 1 });
  }

  /** Questões erradas, na ordem em que apareceram no baralho. */
  function errosDaSessao(sessao, porId) {
    if (!sessao) {
      return [];
    }
    return sessao.baralho
      .map(function (id) {
        var registro = sessao.respostas[id];
        if (!registro || registro.acertou) {
          return null;
        }
        return { questao: porId[id], escolhida: registro.escolhida };
      })
      .filter(Boolean);
  }

  function indexarPorId(questoes) {
    var indice = {};
    questoes.forEach(function (questao) {
      indice[questao.id] = questao;
    });
    return indice;
  }

  return {
    LETRAS: LETRAS,
    valoresDe: valoresDe,
    procedenciasDe: procedenciasDe,
    filtrar: filtrar,
    embaralhar: embaralhar,
    criar: criar,
    questaoAtual: questaoAtual,
    terminou: terminou,
    restantes: restantes,
    responder: responder,
    foiRespondida: foiRespondida,
    avancar: avancar,
    errosDaSessao: errosDaSessao,
    indexarPorId: indexarPorId
  };
})();
