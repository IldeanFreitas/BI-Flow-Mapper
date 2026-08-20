"""Testes de split_multipart()/derive_tmdl_model_name() (G17, funcoes puras
novas em bi_server.py) + regressao de read_upload() (fluxo .pbix antigo)
apos o refactor para reusar split_multipart().

`read_upload()` ja e exercitado indiretamente pela suite existente
(test_server_integration.py, test_storage_diagnostics.py etc.) mas SEMPRE
via corpo bruto (`data=...`, sem multipart) -- nenhum teste anterior batia
no ramo multipart/form-data (campo "pbix" + filename) que e exatamente o
codigo que passou a reusar split_multipart(). Este arquivo fecha essa
lacuna.
"""
from __future__ import annotations

import io
import zipfile

import pytest
import requests

from backend import derive_tmdl_model_name, split_multipart

from _pbix_fixtures import make_fake_pbixray_class


# ---------------------------------------------------------------------------
# split_multipart(): isolada, sem servidor
# ---------------------------------------------------------------------------
class TestSplitMultipart:
    def test_single_part_is_split_into_headers_and_payload(self):
        body = (
            b'--BOUND\r\n'
            b'Content-Disposition: form-data; name="pbix"; filename="my file.pbix"\r\n'
            b'Content-Type: application/octet-stream\r\n\r\n'
            b'FAKE-PBIX-BYTES'
            b'\r\n--BOUND--\r\n'
        )
        parts = split_multipart("multipart/form-data; boundary=BOUND", body)

        assert len(parts) == 1
        headers, payload = parts[0]
        assert b'name="pbix"' in headers
        assert b'filename="my file.pbix"' in headers
        assert payload == b"FAKE-PBIX-BYTES"

    def test_multiple_parts_with_same_field_name_are_all_returned(self):
        # G17: campo "tmdl_files" repetido, um por arquivo .tmdl -- o mesmo
        # shape que read_tmdl_uploads() precisa iterar por completo.
        body = (
            b'--BOUND\r\n'
            b'Content-Disposition: form-data; name="tmdl_files"; filename="a.tmdl"\r\n\r\n'
            b'CONTENT-A'
            b'\r\n--BOUND\r\n'
            b'Content-Disposition: form-data; name="tmdl_files"; filename="b.tmdl"\r\n\r\n'
            b'CONTENT-B'
            b'\r\n--BOUND--\r\n'
        )
        parts = split_multipart("multipart/form-data; boundary=BOUND", body)

        assert len(parts) == 2
        assert parts[0][1] == b"CONTENT-A"
        assert parts[1][1] == b"CONTENT-B"

    def test_boundary_with_quotes_is_stripped(self):
        body = b'--BOUND\r\nContent-Disposition: form-data; name="x"\r\n\r\nY\r\n--BOUND--\r\n'
        parts = split_multipart('multipart/form-data; boundary="BOUND"', body)
        assert len(parts) == 1
        assert parts[0][1] == b"Y"

    def test_missing_boundary_raises_value_error(self):
        with pytest.raises(ValueError):
            split_multipart("multipart/form-data", b"whatever")

    def test_part_without_double_crlf_separator_is_skipped(self):
        # Parte malformada (sem a linha em branco headers/payload) --
        # split_multipart deve pular em vez de quebrar tentando indexar algo
        # que nao existe.
        body = b'--BOUND\r\nno-header-body-separator-here\r\n--BOUND--\r\n'
        parts = split_multipart("multipart/form-data; boundary=BOUND", body)
        assert parts == []

    def test_empty_body_returns_no_parts(self):
        assert split_multipart("multipart/form-data; boundary=BOUND", b"") == []


# ---------------------------------------------------------------------------
# derive_tmdl_model_name(): isolada, sem servidor
# ---------------------------------------------------------------------------
class TestDeriveTmdlModelName:
    def test_semantic_model_suffix_is_stripped(self):
        paths = iter(["MeuModelo.SemanticModel/definition/tables/Sales.tmdl"])
        assert derive_tmdl_model_name(paths) == "MeuModelo"

    def test_pbip_suffix_is_stripped(self):
        paths = iter(["Vendas.pbip/definition.tmdl"])
        assert derive_tmdl_model_name(paths) == "Vendas"

    def test_report_suffix_is_stripped(self):
        paths = iter(["Relatorio.Report/definition.tmdl"])
        assert derive_tmdl_model_name(paths) == "Relatorio"

    def test_no_recognized_suffix_returns_first_segment_verbatim(self):
        paths = iter(["justfile.tmdl"])
        assert derive_tmdl_model_name(paths) == "justfile.tmdl"

    def test_empty_iterable_returns_default_placeholder(self):
        assert derive_tmdl_model_name(iter([])) == "Modelo TMDL"

    def test_only_first_path_is_consulted(self):
        # Um generator "preguicoso" -- confirma que a funcao nao itera o
        # resto da sequencia (nem precisaria, o nome vem so do 1o path).
        def paths():
            yield "Primeiro.SemanticModel/definition/a.tmdl"
            raise AssertionError("nao deveria consumir alem do primeiro item")

        assert derive_tmdl_model_name(paths()) == "Primeiro"


# ---------------------------------------------------------------------------
# Regressao: read_upload() (fluxo .pbix) via multipart real, apos o refactor
# para reusar split_multipart() -- servidor real (live_server), sem mock de
# Handler. PBIXRay e trocado pela fake class (mesmo padrao de
# _pbix_fixtures.py) so para nao depender de um .pbix binario real; o que
# este teste protege e especificamente a extracao de filename do multipart,
# nao o parsing do pbixray em si (ja coberto em outros arquivos).
# ---------------------------------------------------------------------------
def make_empty_pbix_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("placeholder.txt", "valid zip container, not a real pbix")
    return buffer.getvalue()


class TestReadUploadMultipartRegression:
    def test_pbix_field_with_filename_is_read_correctly_via_multipart(self, live_server, monkeypatch):
        import backend

        fake_class = make_fake_pbixray_class({})
        monkeypatch.setattr(backend, "PBIXRay", fake_class)
        monkeypatch.setattr(backend, "_PBIXRAY_IMPORT_ATTEMPTED", True)

        response = requests.post(
            f"{live_server}/api/analyze",
            files={"pbix": ("Relatorio Comercial 2026.pbix", make_empty_pbix_zip_bytes(), "application/octet-stream")},
            headers={"Origin": live_server},
            timeout=15,
        )

        assert response.status_code == 200, response.text
        body = response.json()
        # filename extraido do multipart (Content-Disposition) e ecoado de
        # volta como fileName -- prova que split_multipart()/read_upload()
        # continuam encontrando o campo "pbix" e o filename certo depois do
        # refactor.
        assert body["fileName"] == "Relatorio Comercial 2026.pbix"

    def test_missing_pbix_field_in_multipart_falls_through_to_500(self, live_server, monkeypatch):
        import backend

        fake_class = make_fake_pbixray_class({})
        monkeypatch.setattr(backend, "PBIXRay", fake_class)
        monkeypatch.setattr(backend, "_PBIXRAY_IMPORT_ATTEMPTED", True)

        response = requests.post(
            f"{live_server}/api/analyze",
            files={"not-pbix": ("whatever.txt", b"x", "text/plain")},
            headers={"Origin": live_server},
            timeout=15,
        )
        # read_upload() levanta ValueError ("Campo de upload 'pbix' nao
        # encontrado.") -- cai no except Exception generico de do_POST, 500.
        assert response.status_code == 500
