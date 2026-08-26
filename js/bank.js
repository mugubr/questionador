/**
 * Leitura e validação do banco de questões enviado pelo usuário.
 *
 * O arquivo é dado NÃO CONFIÁVEL: tudo é validado na entrada e nenhum campo
 * chega à tela sem passar por aqui. Erros são devolvidos em português, com o
 * campo e a questão problemáticos identificados.
 */
var Bank = (function () {
  'use strict';

  var VERSAO_SUPORTADA = 1;
  var LETRAS = ['a', 'b', 'c', 'd'];
  var PROCEDENCIAS = ['oficial', 'derivada'];
  var CONFIANCAS = ['alta', 'media', 'baixa'];
  var TAMANHO_MAXIMO_BYTES = 20 * 1024 * 1024;

  function ehTextoNaoVazio(valor) {
    return typeof valor === 'string' && valor.trim() !== '';
  }

  function validaAlternativas(questao, id) {
    var alternativas = questao.alternativas;
    if (!alternativas || typeof alternativas !== 'object') {
      return 'Questão ' + id + ': campo "alternativas" ausente ou inválido.';
    }
    for (var i = 0; i < LETRAS.length; i += 1) {
      var letra = LETRAS[i];
      if (!ehTextoNaoVazio(alternativas[letra])) {
        return 'Questão ' + id + ': alternativa "' + letra + '" ausente ou vazia.';
      }
    }
    return null;
  }

  function validaResposta(questao, id) {
    var resposta = questao.resposta;
    if (!resposta || typeof resposta !== 'object') {
      return 'Questão ' + id + ': campo "resposta" ausente ou inválido.';
    }
    if (LETRAS.indexOf(resposta.letra) === -1) {
      return 'Questão ' + id + ': resposta.letra deve ser a, b, c ou d (veio "' + resposta.letra + '").';
    }
    if (PROCEDENCIAS.indexOf(resposta.procedencia) === -1) {
      return 'Questão ' + id + ': resposta.procedencia deve ser "oficial" ou "derivada".';
    }
    if (resposta.procedencia === 'derivada') {
      if (CONFIANCAS.indexOf(resposta.confianca) === -1) {
        return 'Questão ' + id + ': resposta derivada exige confianca alta, media ou baixa.';
      }
      if (!ehTextoNaoVazio(resposta.justificativa)) {
        return 'Questão ' + id + ': resposta derivada exige justificativa.';
      }
    }
    return null;
  }

  function validaQuestao(questao, indice, vistos) {
    if (!questao || typeof questao !== 'object') {
      return 'Questão na posição ' + (indice + 1) + ' não é um objeto.';
    }

    var id = ehTextoNaoVazio(questao.id) ? questao.id : '(sem id, posição ' + (indice + 1) + ')';
    if (!ehTextoNaoVazio(questao.id)) {
      return 'Questão na posição ' + (indice + 1) + ': campo "id" ausente.';
    }
    if (vistos[questao.id]) {
      return 'Questão ' + id + ': id duplicado no arquivo.';
    }
    vistos[questao.id] = true;

    if (!ehTextoNaoVazio(questao.enunciado)) {
      return 'Questão ' + id + ': enunciado ausente ou vazio.';
    }
    if (!ehTextoNaoVazio(questao.prova)) {
      return 'Questão ' + id + ': campo "prova" ausente.';
    }
    if (!ehTextoNaoVazio(questao.tema)) {
      return 'Questão ' + id + ': campo "tema" ausente.';
    }

    return validaAlternativas(questao, id) || validaResposta(questao, id);
  }

  /**
   * Valida a estrutura completa. Devolve {banco} em caso de sucesso ou {erro}.
   * Nunca lança.
   */
  function validar(dados) {
    if (!dados || typeof dados !== 'object' || Array.isArray(dados)) {
      return { erro: 'O arquivo não contém um objeto JSON na raiz.' };
    }
    if (dados.versao !== VERSAO_SUPORTADA) {
      return {
        erro: 'Versão do banco não suportada: esperado ' + VERSAO_SUPORTADA +
          ', veio ' + JSON.stringify(dados.versao) + '.'
      };
    }
    if (!Array.isArray(dados.questoes) || dados.questoes.length === 0) {
      return { erro: 'O campo "questoes" deve ser uma lista não vazia.' };
    }
    if (!Array.isArray(dados.provas) || dados.provas.length === 0) {
      return { erro: 'O campo "provas" deve ser uma lista não vazia.' };
    }

    var vistos = {};
    for (var i = 0; i < dados.questoes.length; i += 1) {
      var erro = validaQuestao(dados.questoes[i], i, vistos);
      if (erro) {
        return { erro: erro };
      }
    }

    return { banco: dados };
  }

  function analisarTexto(texto) {
    var dados;
    try {
      dados = JSON.parse(texto);
    } catch (erro) {
      return { erro: 'JSON inválido: ' + erro.message };
    }
    return validar(dados);
  }

  /** Lê o arquivo enviado e chama aoTerminar({banco} | {erro}). */
  function lerArquivo(arquivo, aoTerminar) {
    if (!arquivo) {
      aoTerminar({ erro: 'Nenhum arquivo selecionado.' });
      return;
    }
    if (arquivo.size > TAMANHO_MAXIMO_BYTES) {
      aoTerminar({ erro: 'Arquivo grande demais (limite de 20 MB).' });
      return;
    }

    var leitor = new FileReader();
    leitor.onload = function () {
      aoTerminar(analisarTexto(String(leitor.result)));
    };
    leitor.onerror = function () {
      aoTerminar({ erro: 'Não foi possível ler o arquivo.' });
    };

    try {
      leitor.readAsText(arquivo, 'utf-8');
    } catch (erro) {
      aoTerminar({ erro: 'Falha ao abrir o arquivo: ' + erro.message });
    }
  }

  return {
    validar: validar,
    analisarTexto: analisarTexto,
    lerArquivo: lerArquivo
  };
})();
