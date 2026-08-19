// G8 (acessibilidade) — WCAG 3.1.1 "Language of Page": <html lang> precisa
// acompanhar o idioma ativo, tanto ao trocar de idioma quanto no carregamento
// inicial (quando ha um locale persistido de sessao anterior).
import { describe, expect, it } from "vitest";
import { loadApp } from "./setup.js";

describe("G8 — <html lang> segue o locale ativo", () => {
  it('setLocale("pt") resulta em document.documentElement.lang === "pt"', async () => {
    const app = await loadApp();
    app.setLocale("pt");
    expect(document.documentElement.lang).toBe("pt");
  });

  it('setLocale("en") resulta em document.documentElement.lang === "en"', async () => {
    const app = await loadApp();
    app.setLocale("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("os botoes reais de idioma (data-lang) tambem atualizam o <html lang>", async () => {
    await loadApp();
    const ptButton = document.querySelector('.lang-btn[data-lang="pt-BR"]');
    ptButton.dispatchEvent(new Event("click", { bubbles: true }));
    expect(document.documentElement.lang).toBe("pt-BR");

    const enButton = document.querySelector('.lang-btn[data-lang="en-US"]');
    enButton.dispatchEvent(new Event("click", { bubbles: true }));
    expect(document.documentElement.lang).toBe("en-US");
  });

  it("no carregamento inicial, <html lang> ja reflete um locale persistido de sessao anterior (fora de setLocale)", async () => {
    await loadApp({ locale: "pt-BR" });
    // Nenhuma chamada a setLocale() foi feita aqui — a linha de sincronizacao
    // que roda no topo de src/i18n.js (fora da funcao setLocale) e quem
    // precisa refletir o valor salvo em localStorage.
    expect(document.documentElement.lang).toBe("pt-BR");
  });
});
