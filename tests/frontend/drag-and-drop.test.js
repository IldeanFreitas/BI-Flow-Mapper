// G9 — drag-and-drop na .upload-zone (#uploadZone) reaproveita o mesmo
// caminho de carregamento do <input type="file"> clicado (loadPbix(), em
// src/upload.js).
import { describe, expect, it, vi } from "vitest";
import { loadApp } from "./setup.js";

// jsdom nao implementa DragEvent/DataTransfer nativamente; src/upload.js so
// acessa `event.dataTransfer.files`, entao um Event comum com essa
// propriedade anexada manualmente e suficiente para exercitar o listener real.
function makeDropEvent({ files = [] } = {}) {
  const event = new Event("drop", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: { files } });
  return event;
}

function makeDragEvent(type) {
  return new Event(type, { bubbles: true, cancelable: true });
}

describe("G9 — drop em #uploadZone chama loadPbix() com o arquivo solto", () => {
  it("dispara loadPbix(file) com o File mockado em event.dataTransfer.files[0]", async () => {
    const app = await loadApp();
    const uploadZone = document.getElementById("uploadZone");

    // hooks.loadPbix (src/upload.js) e o ponto de indireção que o listener
    // de "drop" chama internamente (`await hooks.loadPbix(file)`) em vez do
    // identificador `loadPbix` direto — substituir a propriedade do objeto
    // ANTES do dispatch é suficiente para interceptar a chamada feita pelo
    // handler real registrado em bindUploadEvents() (mesma técnica usada
    // antes com `dom.window.loadPbix`, agora sem depender de script clássico).
    const loadPbixSpy = vi.fn().mockResolvedValue(undefined);
    app.uploadHooks.loadPbix = loadPbixSpy;

    const file = new File(["conteudo"], "relatorio.pbix", {
      type: "application/octet-stream"
    });
    const dropEvent = makeDropEvent({ files: [file] });

    uploadZone.dispatchEvent(dropEvent);

    expect(loadPbixSpy).toHaveBeenCalledTimes(1);
    expect(loadPbixSpy).toHaveBeenCalledWith(file);
  });

  it("nao chama loadPbix() quando o drop nao carrega nenhum arquivo", async () => {
    const app = await loadApp();
    const uploadZone = document.getElementById("uploadZone");

    const loadPbixSpy = vi.fn().mockResolvedValue(undefined);
    app.uploadHooks.loadPbix = loadPbixSpy;

    uploadZone.dispatchEvent(makeDropEvent({ files: [] }));

    expect(loadPbixSpy).not.toHaveBeenCalled();
  });

  it("dragover chama preventDefault no evento", async () => {
    await loadApp();
    const uploadZone = document.getElementById("uploadZone");

    const event = makeDragEvent("dragover");
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    uploadZone.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
  });

  it("dragenter chama preventDefault e adiciona a classe dragover", async () => {
    await loadApp();
    const uploadZone = document.getElementById("uploadZone");

    const event = makeDragEvent("dragenter");
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    uploadZone.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(uploadZone.classList.contains("dragover")).toBe(true);
  });

  it("drop chama preventDefault no evento e remove a classe dragover", async () => {
    const app = await loadApp();
    const uploadZone = document.getElementById("uploadZone");
    app.uploadHooks.loadPbix = vi.fn().mockResolvedValue(undefined);

    // simula o estado deixado por um dragover anterior
    uploadZone.classList.add("dragover");

    const file = new File(["x"], "a.pbix");
    const event = makeDropEvent({ files: [file] });
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    uploadZone.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(uploadZone.classList.contains("dragover")).toBe(false);
  });

  it("dragleave remove a classe dragover ao sair de fato do #uploadZone", async () => {
    await loadApp();
    const uploadZone = document.getElementById("uploadZone");
    uploadZone.classList.add("dragover");

    const event = new Event("dragleave", { bubbles: true, cancelable: true });
    // relatedTarget = null simula o cursor saindo para fora da janela/documento
    Object.defineProperty(event, "relatedTarget", { value: null });

    uploadZone.dispatchEvent(event);

    expect(uploadZone.classList.contains("dragover")).toBe(false);
  });

  it("dragleave disparado por um filho (bubbling) NAO remove a classe dragover", async () => {
    await loadApp();
    const uploadZone = document.getElementById("uploadZone");
    uploadZone.classList.add("dragover");

    const leftChild = uploadZone.querySelector(".upload-title");
    const enteredChild = uploadZone.querySelector("#pbixInput");
    expect(leftChild).toBeTruthy();
    expect(enteredChild).toBeTruthy();

    // simula o cursor saindo de um filho (leftChild) e entrando em outro
    // filho (enteredChild) — ambos ainda dentro de #uploadZone.
    const event = new Event("dragleave", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "target", { value: leftChild });
    Object.defineProperty(event, "relatedTarget", { value: enteredChild });

    uploadZone.dispatchEvent(event);

    expect(uploadZone.classList.contains("dragover")).toBe(true);
  });
});
