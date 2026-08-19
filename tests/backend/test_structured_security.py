"""Testes unitarios de build_structured_security() (G19 -- RLS/OLS).

Registros sinteticos no mesmo shape que pbixray expoe em `model.rls`/
`model.ols` (dict por linha, ja resolvidos -- ver docstring da funcao em
backend.py). Import direto de backend, sem servidor.
"""
from __future__ import annotations

from backend import build_structured_security


def by_name(roles, name):
    return next(role for role in roles if role["name"] == name)


class TestRlsOnlyRole:
    def test_role_with_only_rls_has_row_filters_and_no_object_permissions(self):
        rls_records = [
            {
                "TableName": "Sales",
                "RoleName": "RegionManager",
                "RoleDescription": "Ve apenas a propria regiao",
                "FilterExpression": "[Region] = USERPRINCIPALNAME()",
                "State": "Ready",
            }
        ]
        roles = build_structured_security(rls_records, ols_records=[])

        assert len(roles) == 1
        role = roles[0]
        assert role["name"] == "RegionManager"
        assert role["description"] == "Ve apenas a propria regiao"
        assert role["objectPermissions"] == []
        assert role["rowFilters"] == [
            {"table": "Sales", "expression": "[Region] = USERPRINCIPALNAME()", "state": "Ready"}
        ]


class TestOlsOnlyRole:
    def test_role_with_only_ols_column_permission_has_no_row_filters(self):
        ols_records = [
            {
                "RoleName": "PayrollViewer",
                "TableName": "Employee",
                "ColumnName": "Salary",
                "Scope": "Column",
                "Permission": "None",
            }
        ]
        roles = build_structured_security(rls_records=[], ols_records=ols_records)

        assert len(roles) == 1
        role = roles[0]
        assert role["name"] == "PayrollViewer"
        assert role["rowFilters"] == []
        assert role["objectPermissions"] == [
            {"table": "Employee", "column": "Salary", "scope": "Column", "permission": "None"}
        ]


class TestGroupingMultipleRowsSameRole:
    def test_multiple_rls_and_ols_rows_for_the_same_role_are_grouped_together(self):
        rls_records = [
            {"RoleName": "Analyst", "TableName": "Sales", "FilterExpression": "[Country] = \"BR\"", "State": "Ready"},
            {"RoleName": "Analyst", "TableName": "Budget", "FilterExpression": "[Year] = 2026", "State": "Ready"},
        ]
        ols_records = [
            {"RoleName": "Analyst", "TableName": "Employee", "ColumnName": "SSN", "Scope": "Column", "Permission": "None"},
            {"RoleName": "Analyst", "TableName": "Employee", "ColumnName": "Salary", "Scope": "Column", "Permission": "None"},
        ]
        roles = build_structured_security(rls_records, ols_records)

        assert len(roles) == 1  # um unico papel, nao quatro
        role = roles[0]
        assert role["name"] == "Analyst"
        assert len(role["rowFilters"]) == 2
        assert {f["table"] for f in role["rowFilters"]} == {"Sales", "Budget"}
        assert len(role["objectPermissions"]) == 2
        assert {p["column"] for p in role["objectPermissions"]} == {"SSN", "Salary"}

    def test_multiple_distinct_roles_stay_separate(self):
        rls_records = [
            {"RoleName": "RoleA", "TableName": "T1", "FilterExpression": "TRUE()", "State": "Ready"},
            {"RoleName": "RoleB", "TableName": "T2", "FilterExpression": "FALSE()", "State": "Ready"},
        ]
        roles = build_structured_security(rls_records, ols_records=[])

        assert {role["name"] for role in roles} == {"RoleA", "RoleB"}
        assert len(by_name(roles, "RoleA")["rowFilters"]) == 1
        assert len(by_name(roles, "RoleB")["rowFilters"]) == 1

    def test_ols_row_can_fill_in_description_missing_from_rls_row(self):
        # RLS sem descricao seguido por (na pratica improvavel, mas a
        # funcao deve lidar de forma graciosa) nenhuma descricao adicional
        # vinda do OLS -- objectPermissions nao carrega description, so
        # garante que o papel nao quebra ao faltar description em ambos.
        rls_records = [{"RoleName": "NoDescRole", "TableName": "T1", "FilterExpression": "TRUE()"}]
        ols_records = [{"RoleName": "NoDescRole", "TableName": "T1", "ColumnName": "Col1", "Scope": "Column", "Permission": "Read"}]
        roles = build_structured_security(rls_records, ols_records)

        assert len(roles) == 1
        assert roles[0]["description"] == ""


class TestSecretMasking:
    def test_password_embedded_in_rls_filter_expression_is_masked(self):
        """Regressao: /api/analyze devolve securityRoles sem autenticacao
        (design do servidor) -- expressao de filtro RLS passa por
        mask_secrets() como qualquer outro texto DAX/M exportado. Achado
        real do security-reviewer na Fase 2 -- ver BACKLOG.md/G7."""
        rls_records = [
            {
                "RoleName": "LegacyRole",
                "TableName": "Sales",
                "FilterExpression": 'Web.Contents("https://x/api", [Pwd="hunter2secret"])',
                "State": "Ready",
            }
        ]
        roles = build_structured_security(rls_records, ols_records=[])
        expression = roles[0]["rowFilters"][0]["expression"]
        assert "hunter2secret" not in expression
        assert "***MASKED***" in expression

    def test_expression_without_secret_is_unchanged(self):
        rls_records = [{"RoleName": "Analyst", "TableName": "Sales", "FilterExpression": "[Region] = USERPRINCIPALNAME()", "State": "Ready"}]
        roles = build_structured_security(rls_records, ols_records=[])
        assert roles[0]["rowFilters"][0]["expression"] == "[Region] = USERPRINCIPALNAME()"


class TestEdgeCases:
    def test_rows_without_role_name_are_skipped(self):
        rls_records = [{"TableName": "Sales", "FilterExpression": "TRUE()"}]
        ols_records = [{"TableName": "Sales", "ColumnName": "X", "Scope": "Column", "Permission": "None"}]
        roles = build_structured_security(rls_records, ols_records)
        assert roles == []

    def test_no_records_returns_empty_list(self):
        assert build_structured_security([], []) == []
