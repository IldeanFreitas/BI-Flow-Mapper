"""Helper de socket cru para os poucos testes que precisam mentir sobre
Content-Length (G5).

`requests` recalcula Content-Length a partir do corpo real sempre que ha um
corpo (`data=...`), mesmo se o chamador ja passou um Content-Length explicito
em `headers=` -- entao nao da pra usar `requests` para simular um cliente que
declara um tamanho e manda outro. Para esse caso especifico, falamos HTTP/1.1
diretamente no socket.
"""
from __future__ import annotations

import json
import socket
from urllib.parse import urlsplit


def raw_http_post(base_url: str, path: str, headers: dict, body: bytes, timeout: float = 10.0) -> bytes:
    parts = urlsplit(base_url)
    host, port = parts.hostname, parts.port

    header_lines = [f"POST {path} HTTP/1.1", f"Host: {host}:{port}", "Connection: close"]
    for key, value in headers.items():
        header_lines.append(f"{key}: {value}")
    request = ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii") + body

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(request)
        chunks = []
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            pass
    return b"".join(chunks)


def status_and_json_of(raw_response: bytes):
    header_bytes, _, body_bytes = raw_response.partition(b"\r\n\r\n")
    status_line = header_bytes.split(b"\r\n", 1)[0]
    status = int(status_line.split(b" ")[1])
    try:
        body = json.loads(body_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        body = None
    return status, body
