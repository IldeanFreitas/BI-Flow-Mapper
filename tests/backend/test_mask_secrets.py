"""Testes unitarios de mask_secrets() (G7).

Funcao pura -- import direto de backend, sem servidor. O valor de teste
aqui e garantir que toda connection string/expressao M/DAX que entra no
DOCX/HTML exportado (build_source_rows, build_datasource_rows,
build_query_rows, add_power_query_evidence, build_expression_rows,
build_column_rows -- todos chamam mask_secrets antes de escrever a linha)
tenha credenciais literais redigidas, sem apagar o resto do texto legivel.
"""
from __future__ import annotations

from backend import mask_secrets


class TestKnownKeyPatterns:
    def test_pwd_in_ado_connection_string_is_masked(self):
        text = "Server=myserver;Database=Sales;Pwd=Sup3rSecret!;Uid=admin;"
        masked = mask_secrets(text)
        assert "Sup3rSecret!" not in masked
        assert "Pwd=***MASKED***" in masked
        # Resto da connection string continua legivel.
        assert "Server=myserver" in masked
        assert "Database=Sales" in masked
        assert "Uid=admin" in masked

    def test_password_key_is_masked(self):
        text = "Provider=SQLNCLI;Data Source=host;Password=my pass with spaces;"
        masked = mask_secrets(text)
        assert "my pass with spaces" not in masked
        assert "Password=***MASKED***" in masked

    def test_api_key_followed_by_ampersand_is_masked(self):
        # api_key=... dentro de uma query string, com outro parametro logo
        # depois separado por '&' -- o valor mascarado nao deve "comer" o
        # parametro seguinte.
        text = 'Web.Contents("https://api.example.com/data?api_key=AKIA1234567890XYZ&region=us-east-1")'
        masked = mask_secrets(text)
        assert "AKIA1234567890XYZ" not in masked
        assert "api_key=***MASKED***" in masked
        assert "region=us-east-1" in masked

    def test_apikey_no_underscore_variant_is_masked(self):
        text = "apikey=abcDEF123456"
        masked = mask_secrets(text)
        assert "abcDEF123456" not in masked
        assert "apikey=***MASKED***" in masked

    def test_authorization_header_in_m_expression_is_masked(self):
        # Padrao comum: Headers=[Authorization="Bearer <token>"] dentro de
        # Web.Contents em codigo M.
        text = (
            'let\n'
            '  Source = Web.Contents("https://api.example.com/v1/data",\n'
            '    [Headers=[Authorization="Bearer eyJhbGciOiJIUzI1NiJ9.secretpayload.sig"]])\n'
            'in\n'
            '  Source'
        )
        masked = mask_secrets(text)
        assert "eyJhbGciOiJIUzI1NiJ9.secretpayload.sig" not in masked
        assert "Bearer" not in masked  # esquema tambem faz parte do valor capturado
        assert 'Authorization="***MASKED***"' in masked
        assert "Web.Contents" in masked  # resto do codigo M continua legivel

    def test_authorization_with_colon_separator_is_masked(self):
        text = "Authorization: Bearer sometoken1234567890abcdef"
        masked = mask_secrets(text)
        assert "sometoken1234567890abcdef" not in masked
        assert "Authorization: ***MASKED***" in masked


class TestLongTokenCatchAll:
    def test_long_contiguous_alphanumeric_token_is_masked(self):
        # 20+ caracteres alfanumericos contiguos sem separador -- padrao
        # comum de API key/token/hash que nao caiu em nenhum padrao nomeado
        # (sem prefixo "key=", "token=" etc.).
        token = "aZ9bC8dE7fG6hH5iJ4kL3m"  # 22 chars
        text = f"X-Custom-Secret {token} rest-of-the-string"
        masked = mask_secrets(text)
        assert token not in masked
        assert "***MASKED***" in masked
        assert "rest-of-the-string" in masked

    def test_token_just_under_20_chars_is_not_masked(self):
        # Limite exato: 19 caracteres contiguos NAO deve disparar o
        # catch-all (o padrao exige 20+).
        token = "aZ9bC8dE7fG6hH5iJ4k"  # 19 chars
        text = f"value={token};"
        masked = mask_secrets(text)
        assert masked == text


class TestNegativeCases:
    def test_normal_connection_string_without_secrets_is_unchanged(self):
        text = "Server=myserver.database.windows.net;Database=SalesDB;Encrypt=True;"
        masked = mask_secrets(text)
        assert masked == text

    def test_hostname_with_dots_is_not_confused_with_a_long_token(self):
        # Cada rotulo do hostname (separado por '.') tem menos de 20 chars
        # -- o catch-all de token so olha para sequencias CONTIGUAS de
        # alfanumericos, entao um dominio com pontos nao deveria disparar
        # falso positivo mesmo sendo "comprido" no total.
        text = "Data Source=reporting-server-01.database.windows.net;Initial Catalog=Sales;"
        masked = mask_secrets(text)
        assert masked == text

    def test_empty_and_none_values_return_falsy_without_error(self):
        assert mask_secrets("") == ""
        assert mask_secrets(None) == ""

    def test_masking_is_idempotent_key_preserved(self):
        # Mascarar duas vezes nao deve degradar ainda mais o texto (o valor
        # ja virou "***MASKED***", que tem menos de 20 chars contiguos --
        # nao deve ser re-mascarado por engano pelo catch-all).
        text = "Pwd=hunter2;"
        once = mask_secrets(text)
        twice = mask_secrets(once)
        assert once == twice
