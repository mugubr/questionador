/**
 * Wrapper de localStorage. Toda leitura e escrita em try/catch: em aba anônima
 * ou com armazenamento bloqueado o acesso lança, e o app precisa seguir
 * funcionando — apenas exigindo upload a cada sessão.
 */
var Storage = (function () {
  'use strict';

  var CHAVE_BANCO = 'quiz.bank.v1';
  var CHAVE_SESSAO = 'quiz.session.v1';

  function disponivel() {
    try {
      var teste = '__quiz_probe__';
      window.localStorage.setItem(teste, '1');
      window.localStorage.removeItem(teste);
      return true;
    } catch (erro) {
      return false;
    }
  }

  function ler(chave) {
    try {
      var bruto = window.localStorage.getItem(chave);
      return bruto ? JSON.parse(bruto) : null;
    } catch (erro) {
      return null;
    }
  }

  function gravar(chave, valor) {
    try {
      window.localStorage.setItem(chave, JSON.stringify(valor));
      return true;
    } catch (erro) {
      return false;
    }
  }

  function remover(chave) {
    try {
      window.localStorage.removeItem(chave);
    } catch (erro) {
      /* sem armazenamento não há o que remover */
    }
  }

  return {
    disponivel: disponivel,
    lerBanco: function () { return ler(CHAVE_BANCO); },
    gravarBanco: function (banco) { return gravar(CHAVE_BANCO, banco); },
    lerSessao: function () { return ler(CHAVE_SESSAO); },
    gravarSessao: function (sessao) { return gravar(CHAVE_SESSAO, sessao); },
    limparSessao: function () { remover(CHAVE_SESSAO); }
  };
})();
