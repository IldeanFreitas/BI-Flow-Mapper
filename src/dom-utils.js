// ─── Utilitários de DOM compartilhados ─────────────────────────────────────
// Módulo folha: sem dependências de outros módulos do app. Qualquer `innerHTML`
// que interpole dado vindo do PBIX (nome de tabela/medida/query etc.) PRECISA
// passar por escapeHtml() antes — é a defesa contra XSS via .pbix malicioso
// (ver achado de segurança da Fase 2 em BACKLOG.md: renderDetails() vazava
// nomes de nó sem escapar).

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[char]);
}
