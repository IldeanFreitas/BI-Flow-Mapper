import { afterEach, describe, expect, it, vi } from "vitest";
import { loadApp } from "./setup.js";

afterEach(() => {
  vi.unstubAllGlobals();
  delete window.pywebview;
});

describe("exportação HTML", () => {
  it("aciona o endpoint HTML e salva a resposta com a extensão correta", async () => {
    const app = await loadApp();
    app.state.lastPbixFile = new File(["pbix"], "Modelo Financeiro.pbix");
    document.getElementById("exportHtmlButton").disabled = false;

    const saveFile = vi.fn().mockResolvedValue({ ok: true });
    window.pywebview = { api: { save_file: saveFile } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["<!doctype html>"], { type: "text/html" })),
      headers: { get: () => 'attachment; filename="modelo.html"' },
    }));

    await app.exportHtmlDocumentation();

    expect(fetch).toHaveBeenCalledWith("/api/export-html", expect.objectContaining({ method: "POST" }));
    expect(saveFile).toHaveBeenCalledWith(expect.any(String), "modelo.html", "text/html");
    expect(document.getElementById("exportHtmlButton").disabled).toBe(false);
  });
});
