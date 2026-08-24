// G8 — alvo de toque minimo para os botoes de idioma. Simular layout real
// (box model calculado) exige um motor de renderizacao que o jsdom nao tem;
// aqui validamos que a regra CSS que garante a altura minima existe de fato
// no arquivo fonte, lendo a regra `.lang-btn` como texto.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const CSS = readFileSync(path.join(ROOT, "styles.css"), "utf-8");

describe("G8 — .lang-btn tem altura minima de alvo de toque", () => {
  it("a regra .lang-btn declara min-height: 24px", () => {
    const match = CSS.match(/\.lang-btn\s*\{([^}]*)\}/);
    expect(match, ".lang-btn rule not found in styles.css").toBeTruthy();
    const ruleBody = match[1];
    expect(ruleBody).toMatch(/min-height:\s*24px/);
  });
});

describe("G34 — tipografia nao depende de rede externa", () => {
  it("usa uma pilha de fonte local definida como token", () => {
    expect(CSS).not.toMatch(/@import\s+url\(/i);
    expect(CSS).not.toMatch(/fonts\.googleapis\.com|fonts\.gstatic\.com/i);
    expect(CSS).toMatch(/--font-ui:\s*'Segoe UI Variable'/);
    expect(CSS).toMatch(/font-family:\s*var\(--font-ui\)/);
  });
});
