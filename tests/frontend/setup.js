// Helper compartilhado para carregar o app real (index.html + módulos ES em
// src/) dentro do ambiente jsdom global do Vitest. `environment: "jsdom"` em
// vitest.config.js já injeta `document`/`window`/`localStorage` como globals
// do processo de teste — não precisamos mais montar um JSDOM manual nem do
// truque `vm.runInContext` que existia aqui quando app.js era um script
// clássico sem `import`/`export` (ver G12 em BACKLOG.md).
//
// src/main.js roda `init()` como efeito colateral do próprio import (mesma
// semântica do antigo `init();` no fim de app.js) — por isso cada teste
// precisa de uma instância FRESCA do DOM e do grafo de módulos:
//   1. o conteúdo de <head>/<body> é substituído a partir do index.html real
//      antes de qualquer import, para que dom-refs.js (que consulta
//      document.getElementById(...) na própria avaliação do módulo) monte
//      `els` a partir dos elementos certos;
//   2. vi.resetModules() limpa o cache do Vitest antes do próximo
//      `import()` dinâmico, para que `state`/`els`/os objetos `hooks` de
//      cada módulo sejam recriados do zero — sem vazar estado de um teste
//      para o outro dentro do mesmo arquivo.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { vi } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const INDEX_HTML = readFileSync(path.join(ROOT, "index.html"), "utf-8");

/**
 * Carrega o app real (index.html + src/main.js) com um DOM e um grafo de
 * módulos frescos, e devolve o namespace exportado por src/main.js.
 *
 * @param {object} [options]
 * @param {string} [options.locale] - se passado, grava em localStorage antes
 *   de src/main.js rodar, simulando um locale persistido de sessão anterior
 *   (cobre `document.documentElement.lang = locale` fora de setLocale(),
 *   que roda no topo de src/i18n.js).
 * @returns {Promise<object>} o namespace de src/main.js — `state`, `els`,
 *   `setLocale`, `selectNode`, os objetos `*Hooks` usados para interceptar
 *   chamadas internas em spies, etc. (ver a lista de reexportações no fim de
 *   src/main.js). `document`/`window`/`localStorage` continuam sendo os
 *   globals injetados pelo ambiente jsdom do Vitest — não fazem parte do
 *   valor de retorno.
 */
export async function loadApp({ locale } = {}) {
  localStorage.clear();

  const parsed = new DOMParser().parseFromString(INDEX_HTML, "text/html");
  document.head.innerHTML = parsed.head.innerHTML;
  document.body.innerHTML = parsed.body.innerHTML;

  if (locale) {
    localStorage.setItem("bifm-locale", locale);
  }

  // Reseta o cache de módulos do Vitest para que o próximo import() reavalie
  // TODO o grafo de módulos (main.js + tudo que ele importa) do zero —
  // equivalente a "recarregar a página" entre testes.
  vi.resetModules();
  return import("../../src/main.js");
}
