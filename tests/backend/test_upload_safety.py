"""Cobertura G32 para o limite, staging e capacidade dos uploads locais."""
from __future__ import annotations

import io
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from pathlib import Path

import pytest
import requests

import bi_server
from backend import Handler, UploadValidationError, validate_pbix_archive
from _pbix_fixtures import make_empty_pbix_bytes


def _handler_for_body(body: bytes, declared_length: int):
    """Constroi apenas os atributos que spooled_request_body consome."""
    handler = Handler.__new__(Handler)
    handler.rfile = io.BytesIO(body)
    headers = Message()
    headers["Content-Length"] = str(declared_length)
    handler.headers = headers
    return handler


def test_request_body_spools_after_memory_threshold(monkeypatch):
    monkeypatch.setattr(bi_server, "MAX_UPLOAD_BYTES", 32)
    monkeypatch.setattr(bi_server, "SPOOL_MAX_MEMORY_BYTES", 4)
    monkeypatch.setattr(bi_server, "UPLOAD_READ_CHUNK_BYTES", 3)
    handler = _handler_for_body(b"123456789", declared_length=9)

    with handler.spooled_request_body() as body:
        assert body.read() == b"123456789"
        assert body._rolled is True  # arquivo temporario, nao buffer RAM ilimitado


def test_interrupted_body_is_rejected_before_any_analysis(monkeypatch):
    monkeypatch.setattr(bi_server, "MAX_UPLOAD_BYTES", 32)
    handler = _handler_for_body(b"123", declared_length=4)

    with pytest.raises(UploadValidationError, match="interrompido"):
        with handler.spooled_request_body():
            pass


def test_non_zip_pbix_is_rejected_with_clear_client_error(live_server):
    response = requests.post(
        f"{live_server}/api/analyze",
        data=b"not-a-zip",
        headers={"Origin": live_server},
        timeout=5,
    )

    assert response.status_code == 400
    assert response.json() == {"error": "O arquivo enviado nao e um PBIX (ZIP) valido."}


def test_zip_with_excessive_compression_ratio_is_rejected(tmp_path, monkeypatch):
    archive_path = tmp_path / "high-ratio.pbix"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Report/Layout", b"0" * 20_000)
    monkeypatch.setattr(bi_server, "MAX_ZIP_COMPRESSION_RATIO", 2)

    with pytest.raises(UploadValidationError, match="razao de compressao"):
        validate_pbix_archive(archive_path)


def test_analysis_temp_directory_is_removed_after_success(live_server, monkeypatch, tmp_path):
    original_temporary_directory = bi_server.tempfile.TemporaryDirectory
    created_paths = []

    class TrackingTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            kwargs["dir"] = tmp_path
            self._directory = original_temporary_directory(*args, **kwargs)

        def __enter__(self):
            path = self._directory.__enter__()
            created_paths.append(Path(path))
            return path

        def __exit__(self, *args):
            return self._directory.__exit__(*args)

    monkeypatch.setattr(bi_server.tempfile, "TemporaryDirectory", TrackingTemporaryDirectory)
    monkeypatch.setattr(bi_server, "analyze_pbix", lambda _path: {"nodes": [], "edges": []})

    response = requests.post(
        f"{live_server}/api/analyze",
        data=make_empty_pbix_bytes(),
        headers={"Origin": live_server},
        timeout=5,
    )

    assert response.status_code == 200, response.text
    assert created_paths
    # A resposta pode chegar ao cliente alguns milissegundos antes de a
    # thread do handler sair do bloco `with TemporaryDirectory`.
    deadline = time.monotonic() + 1
    while any(path.exists() for path in created_paths) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert all(not path.exists() for path in created_paths)


def test_second_simultaneous_analysis_times_out_instead_of_accumulating(live_server, monkeypatch):
    entered_analysis = threading.Event()
    release_analysis = threading.Event()

    def blocked_analysis(_path):
        entered_analysis.set()
        assert release_analysis.wait(timeout=5)
        return {"nodes": [], "edges": []}

    monkeypatch.setattr(bi_server, "ANALYSIS_SEMAPHORE", threading.BoundedSemaphore(1))
    monkeypatch.setattr(bi_server, "ANALYSIS_ACQUIRE_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(bi_server, "analyze_pbix", blocked_analysis)

    def post_valid_pbix():
        return requests.post(
            f"{live_server}/api/analyze",
            data=make_empty_pbix_bytes(),
            headers={"Origin": live_server},
            timeout=5,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_request = executor.submit(post_valid_pbix)
        assert entered_analysis.wait(timeout=2)
        rejected_request = post_valid_pbix()
        release_analysis.set()
        first_response = first_request.result(timeout=5)

    assert rejected_request.status_code == 429
    assert first_response.status_code == 200
