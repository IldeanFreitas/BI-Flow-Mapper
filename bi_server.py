"""G12: servidor HTTP (roteamento, allowlist estatico G6, validacao de
Origin/Content-Length G5) + bootstrap do processo (find_port/write_port_file/
main). Extraido de backend.py na modularizacao G12.

`Handler.do_POST` precisa de analyze_pbix() (pbix_analysis.py) e de
build_documentation_docx()/build_documentation_html()/normalize_doc_locale()
(doc_export.py). analyze_pbix e importado normalmente (`from pbix_analysis
import analyze_pbix`) porque pbix_analysis.py NAO depende de bi_server.py --
sem risco de ciclo.

doc_export.py, porem, precisa de `ROOT` (daqui) para achar o logo em
add_cover() -- e este modulo precisa de build_documentation_docx/
build_documentation_html/normalize_doc_locale (de la). Para quebrar esse
ciclo, este modulo faz `import doc_export` (nao `from doc_export import
build_documentation_docx`, que exigiria doc_export.py JA estar 100% carregado
no momento do import, o que nao e garantido em nenhuma das duas ordens de
carregamento possiveis) e usa `doc_export.build_documentation_docx(...)`/
`doc_export.build_documentation_html(...)`/`doc_export.normalize_doc_locale(...)`
qualificados dentro dos METODOS do Handler -- acesso adiado para o momento da
chamada, quando doc_export.py ja terminou de carregar havia muito tempo.
Import circular seguro exige que ROOT/HOST/etc. (usados por doc_export.py)
estejam definidos ANTES da linha `import doc_export` no codigo abaixo -- nao
reordene sem entender esta nota.
"""
from __future__ import annotations

import json
import posixpath
import re
import socket
import sys
import tempfile
import threading
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import urlopen

from logging_setup import logger


# Pasta dos assets empacotados (index.html, src/*.js, styles.css...)
if getattr(sys, 'frozen', False):
    ASSETS_DIR = Path(sys._MEIPASS)          # onde o PyInstaller extrai os arquivos
    RUNTIME_DIR = Path(sys.executable).parent # onde o .exe está (para o port file)
else:
    ASSETS_DIR = Path(__file__).resolve().parent
    RUNTIME_DIR = ASSETS_DIR

ROOT = ASSETS_DIR
PORT_FILE = RUNTIME_DIR / "bi-flow-mapper.port"
# LOG_FILE nao vive aqui -- logging_setup.py e a UNICA fonte de verdade (ver
# docstring deste modulo / logging_setup.py sobre por que RUNTIME_DIR e
# recalculado la de forma independente, em vez de importado daqui).
HOST = "127.0.0.1"
DEFAULT_PORT = 4173


# G5 (hardening): tamanho maximo aceito para upload de .pbix, checado ANTES
# de ler o corpo da requisicao (self.rfile.read), para nao deixar um cliente
# malicioso/errado forcar o processo a alocar um corpo arbitrariamente grande.
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


# G6 (hardening): allowlist explicito de arquivos estaticos servidos por GET.
# Qualquer caminho fora desta lista retorna 404 em vez de cair no
# SimpleHTTPRequestHandler padrao, que serviria QUALQUER arquivo sob ROOT
# (incluindo o proprio backend.py/connector_catalog.py).
STATIC_ALLOWLIST_EXACT = {"/", "/index.html", "/styles.css"}
STATIC_ALLOWLIST_PREFIXES = ("/image/", "/assets/", "/src/")


import doc_export  # noqa: E402  (ver docstring do modulo -- ordem importa)
from pbix_analysis import analyze_pbix  # noqa: E402

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        request_path = parsed_url.path
        if request_path not in {"/api/analyze", "/api/export-docx", "/api/export-html"}:
            self.send_json({"error": "Not found"}, status=404)
            return

        # G5: rejeita requisicoes cross-origin (uma pagina em outra origem
        # tentando usar o navegador da vitima para bater neste servidor
        # local). Requisicoes sem Origin/Referer/Sec-Fetch-Site (curl,
        # scripts locais) continuam permitidas -- este servidor nao tem
        # autenticacao por design.
        if self.is_cross_origin_request():
            self.send_json({"error": "Origem nao permitida."}, status=403)
            return

        # G5: capa o tamanho do corpo ANTES de ler (self.rfile.read), para
        # nao deixar um cliente forcar o processo a alocar um corpo
        # arbitrariamente grande em memoria.
        content_length_header = self.headers.get("Content-Length")
        try:
            content_length = int(content_length_header) if content_length_header is not None else 0
        except ValueError:
            self.send_json({"error": "Content-Length invalido."}, status=400)
            return
        if content_length > MAX_UPLOAD_BYTES:
            self.send_json(
                {"error": f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."},
                status=413,
            )
            return

        try:
            file_name, payload = self.read_upload()
            with tempfile.TemporaryDirectory(prefix="bi-flow-mapper-") as temp_dir:
                safe_name = re.sub(r"[^A-Za-z0-9_. -]+", "_", file_name or "upload.pbix")
                pbix_path = Path(temp_dir) / safe_name
                pbix_path.write_bytes(payload)

                if request_path == "/api/export-docx":
                    locale = self.headers.get("X-BIFM-Locale") or parse_qs(parsed_url.query).get("locale", ["pt-BR"])[0]
                    doc_locale = doc_export.normalize_doc_locale(locale)
                    data = doc_export.build_documentation_docx(pbix_path, file_name, doc_locale)
                    suffix = "documentacao" if doc_locale == "pt-BR" else "documentation"
                    docx_name = f"{Path(file_name or 'power-bi').stem}_{suffix}.docx"
                    self.send_binary(
                        data,
                        docx_name,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                    return

                if request_path == "/api/export-html":
                    # G20: mesma validacao de Origin/Content-Length de
                    # /api/export-docx (feita mais acima, antes do try, para
                    # os dois endpoints igualmente); so muda o formato de
                    # saida (HTML autocontido em vez de .docx).
                    locale = self.headers.get("X-BIFM-Locale") or parse_qs(parsed_url.query).get("locale", ["pt-BR"])[0]
                    doc_locale = doc_export.normalize_doc_locale(locale)
                    data = doc_export.build_documentation_html(pbix_path, file_name, doc_locale)
                    suffix = "documentacao" if doc_locale == "pt-BR" else "documentation"
                    html_name = f"{Path(file_name or 'power-bi').stem}_{suffix}.html"
                    self.send_binary(data, html_name, "text/html; charset=utf-8")
                    return

                graph = analyze_pbix(pbix_path)
                graph["fileName"] = file_name
                self.send_json(graph)
        except Exception as error:
            traceback.print_exc()
            logger.exception("Falha ao processar POST %s", request_path)
            # Detalhe completo (que pode incluir path local/nome de arquivo
            # do cliente) fica so no log server-side; a resposta HTTP leva
            # so uma mensagem generica, ja que qualquer processo local pode
            # bater neste endpoint sem autenticacao.
            self.send_json({"error": "Falha ao processar o arquivo. Veja bi-flow-mapper.log para detalhes."}, status=500)

    def do_GET(self):
        if self.path == "/api/health":
            self.send_json({"ok": True, "app": "BI Flow Mapper"})
            return
        # G6: allowlist explicito -- qualquer caminho fora dele vira 404 em
        # vez de cair no SimpleHTTPRequestHandler padrao (que serviria
        # QUALQUER arquivo sob ROOT, incluindo backend.py/connector_catalog.py).
        if not self.is_allowed_static_path():
            self.send_error(404, "Not Found")
            return
        super().do_GET()

    def is_cross_origin_request(self):
        """True se a requisicao tiver uma origem diferente deste servidor.

        Origin/Referer sao anexados pelo navegador e nao podem ser
        falsificados via JavaScript; se vierem presentes apontando para um
        host diferente, tratamos como tentativa de CSRF/DNS-rebinding vinda
        de outra pagina. Ausencia de todos esses headers (curl, scripts,
        ferramentas locais legitimas) continua permitida.
        """
        # Fixo, derivado do bind real do servidor -- NUNCA inclua o header
        # Host da propria requisicao aqui. Um atacante controla o dominio
        # que o navegador resolve via DNS rebinding para 127.0.0.1, entao
        # Host/Origin sempre "batem" um com o outro do ponto de vista do
        # navegador; se Host entrar no conjunto esperado, o ataque passa.
        server_host, server_port = self.server.server_address[:2]
        expected_hosts = {f"{server_host}:{server_port}", f"localhost:{server_port}"}

        sec_fetch_site = self.headers.get("Sec-Fetch-Site")
        if sec_fetch_site and sec_fetch_site not in ("same-origin", "none"):
            return True

        for header_name in ("Origin", "Referer"):
            value = self.headers.get(header_name)
            if not value:
                continue
            netloc = urlparse(value).netloc
            if netloc and netloc not in expected_hosts:
                return True

        return False

    def is_allowed_static_path(self):
        """True se o path do GET estiver na allowlist de arquivos estaticos.

        Normaliza o path (resolvendo '..') antes de comparar, para que um
        caminho como '/image/../backend.py' seja avaliado pelo destino real
        ('/backend.py') e nao pelo prefixo aparente ('/image/').
        """
        request_path = unquote(urlparse(self.path).path)
        if "\\" in request_path:
            # posixpath.normpath so entende '/' como separador; uma barra
            # invertida crua ou percent-encoded sobreviveria a normalizacao
            # e poderia escapar do allowlist em runtimes onde o handler
            # padrao tambem trate '\' como separador de diretorio.
            return False
        normalized = posixpath.normpath(request_path)
        if normalized == "/" or normalized in STATIC_ALLOWLIST_EXACT:
            return True
        return normalized.startswith(STATIC_ALLOWLIST_PREFIXES)

    def read_upload(self):
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        if "multipart/form-data" not in content_type:
            return "upload.pbix", body

        boundary_match = re.search(r"boundary=([^;]+)", content_type)
        if not boundary_match:
            raise ValueError("Upload multipart sem boundary.")

        boundary = ("--" + boundary_match.group(1).strip('"')).encode()
        for part in body.split(boundary):
            if b"\r\n\r\n" not in part:
                continue
            headers, payload = part.split(b"\r\n\r\n", 1)
            if b'name="pbix"' not in headers:
                continue
            payload = payload.rstrip(b"\r\n-")
            filename_match = re.search(rb'filename="([^"]+)"', headers)
            filename = "upload.pbix"
            if filename_match:
                filename = unquote(filename_match.group(1).decode("utf-8", errors="replace"))
            return filename, payload

        raise ValueError("Campo de upload 'pbix' nao encontrado.")

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_binary(self, data, file_name, content_type, status=200):
        safe_name = re.sub(r'["\r\n]+', "", file_name or "download.bin")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.end_headers()
        self.wfile.write(data)


def is_port_open(port):
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def is_healthy(port):
    try:
        with urlopen(f"http://{HOST}:{port}/api/health", timeout=0.8) as response:
            return response.status == 200
    except Exception:
        # Esperado sempre que nao ha outra instancia rodando nesta porta --
        # nao eh um erro, so controle de fluxo do startup single-instance.
        logger.debug("is_healthy(%s): nenhuma instancia respondendo", port, exc_info=True)
        return False


def find_port(start_port):
    for port in range(start_port, start_port + 20):
        if not is_port_open(port):
            return port
    raise RuntimeError("Nenhuma porta local livre encontrada entre 4173 e 4192.")


def requested_port():
    for index, arg in enumerate(sys.argv):
        if arg == "--port" and index + 1 < len(sys.argv):
            return int(sys.argv[index + 1])
        if arg.startswith("--port="):
            return int(arg.split("=", 1)[1])
    return DEFAULT_PORT


def open_browser(port):
    webbrowser.open(f"http://{HOST}:{port}")


def write_port_file(port):
    PORT_FILE.write_text(f"http://{HOST}:{port}", encoding="utf-8")


def main():
    should_open = "--open" in sys.argv
    start_port = requested_port()

    if is_healthy(start_port):
        write_port_file(start_port)
        if should_open:
            open_browser(start_port)
        print(f"BI Flow Mapper already running at http://{HOST}:{start_port}")
        return

    port = find_port(start_port)
    server = ThreadingHTTPServer((HOST, port), Handler)
    write_port_file(port)

    if should_open:
        threading.Timer(0.4, open_browser, args=(port,)).start()

    print(f"BI Flow Mapper running at http://{HOST}:{port}")
    server.serve_forever()
