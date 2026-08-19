"""G12: deteccao/normalizacao de conectores Power Query, extraido de
backend.py.

Isolado de pbix_analysis.py de proposito -- "que conector e esse
texto/keyword" e uma responsabilidade de matching de texto, testavel sem o
resto do pipeline de analise. Depende so de connector_catalog.py (catalogo
de conectores conhecidos) e graph_utils.py (helpers puros); pbix_analysis.py
importa DESTE modulo, nunca o contrario.
"""
from __future__ import annotations

import re

from connector_catalog import POWER_QUERY_CONNECTORS
from graph_utils import initials, record_text, slug


CONNECTORS = POWER_QUERY_CONNECTORS
CANONICAL_CONNECTOR_NAMES = {
    "Azure Database for PostgreSQL": "PostgreSQL",
    "PostgreSQL database": "PostgreSQL",
    "Azure SQL Database": "SQL Server",
    "Azure Synapse Analytics (SQL Data Warehouse)": "SQL Server",
    "SQL Server database": "SQL Server",
    "Excel Workbook": "Excel",
    "Text/CSV": "CSV",
    "JSON": "JSON",
    "SharePoint Folder": "SharePoint",
    "SharePoint Online List": "SharePoint",
    "OData feed": "OData",
    "Oracle database": "Oracle",
    "MySQL database": "MySQL",
    "IBM Db2 database": "IBM Db2",
    "Informix database": "Informix",
    "Sybase database": "Sybase",
    "Teradata database": "Teradata",
}
PREFERRED_PATTERN_CONNECTORS = {
    "Access.Database": "Access Database",
    "ActiveDirectory.Domains": "Active Directory",
    "AdobeAnalytics.Cubes": "Adobe Analytics",
    "AmazonRedshift.Database": "Amazon Redshift",
    "AnalysisServices.Database": "Analysis Services",
    "AzureDataExplorer.Contents": "Azure Data Explorer (Kusto)",
    "Kusto.Contents": "Azure Data Explorer (Kusto)",
    "AzureDataLakeStorage.Contents": "Azure Data Lake Storage Gen1",
    "AzureStorage.Blobs": "Azure Blob Storage",
    "AzureStorage.DataLake": "Azure Data Lake Storage Gen2",
    "AzureStorage.Tables": "Azure Table Storage",
    "CommonDataService.Database": "Dataverse",
    "Dataverse.Contents": "Dataverse",
    "Csv.Document": "CSV",
    "Databricks.Catalogs": "Databricks",
    "Databricks.Query": "Databricks",
    "Excel.Workbook": "Excel",
    "Folder.Files": "Folder",
    "Folder.Contents": "Folder",
    "GoogleAnalytics.Accounts": "Google Analytics",
    "GoogleBigQuery.Database": "Google BigQuery",
    "Hdfs.Files": "Hadoop File (HDFS)",
    "Hdfs.Contents": "Hadoop File (HDFS)",
    "DB2.Database": "IBM Db2 database",
    "Impala.Database": "Impala",
    "Informix.Database": "Informix database",
    "Json.Document": "JSON",
    "MySQL.Database": "MySQL database",
    "OData.Feed": "OData feed",
    "Odbc.DataSource": "ODBC",
    "Odbc.Query": "ODBC",
    "OleDb.DataSource": "OLE DB",
    "OleDb.Query": "OLE DB",
    "Oracle.Database": "Oracle database",
    "Parquet.Document": "Parquet",
    "Pdf.Tables": "PDF",
    "PostgreSQL.Database": "PostgreSQL",
    "PowerPlatform.Dataflows": "Power Platform Dataflows",
    "Salesforce.Data": "Salesforce Objects",
    "Salesforce.Objects": "Salesforce Objects",
    "Salesforce.Reports": "Salesforce Reports",
    "SapBusinessWarehouse.Cubes": "SAP Business Warehouse Application Server",
    "SharePoint.Files": "SharePoint",
    "SharePoint.Contents": "SharePoint",
    "SharePoint.Tables": "SharePoint Online List",
    "Snowflake.Databases": "Snowflake",
    "Sql.Database": "SQL Server",
    "Sql.Databases": "SQL Server",
    "Sybase.Database": "Sybase database",
    "Teradata.Database": "Teradata database",
    "Vertica.Database": "Vertica",
    "Web.Contents": "Web",
    "Web.BrowserContents": "Web",
    "Xml.Tables": "XML",
    "Xml.Document": "XML",
}


def has_connector_call(text, pattern):
    if not text or not pattern:
        return False
    escaped = re.escape(pattern)
    return re.search(rf"(?<![A-Za-z0-9_]){escaped}\s*\(", text, flags=re.IGNORECASE) is not None


def datasource_matches(text, keyword):
    normalized = str(text).lower()
    keyword = keyword.lower()

    file_extension_keywords = {".xlsx", ".xls", ".xlsb", ".xlsm", ".csv", ".json"}
    if keyword in file_extension_keywords:
        return keyword in normalized

    if keyword in {"sql", "sql server", "microsoft sql", "sql.database", "sql.databases"}:
        sql_server_markers = [
            "sql server",
            "microsoft sql",
            "sql.database",
            "sql.databases",
            "provider=sqlncli",
            "provider=sqloledb",
        ]
        excluded = ["postgresql", "postgre", "mysql", "snowflake", "sqlite"]
        return any(marker in normalized for marker in sql_server_markers) and not any(item in normalized for item in excluded)

    return keyword in normalized


def datasource_match_score(text, keyword, connector):
    normalized = str(text).lower()
    connector_name = connector["name"].lower()
    score = len(keyword)
    if connector_name in normalized:
        score += 100
    if connector_name.replace(" database", "") in normalized:
        score += 35
    if "azure" in normalized and connector_name.startswith("azure"):
        score += 50
    if connector["name"] in {"PostgreSQL", "SQL Server", "Excel", "CSV", "SharePoint"}:
        score += 20
    if connector["name"] == "Excel" and re.search(r"\.xls[xbm]?\b", normalized):
        score += 90
    if connector["name"] == "CSV" and ".csv" in normalized:
        score += 90
    if connector["name"] == "JSON" and ".json" in normalized:
        score += 90
    if connector_name.endswith(" database") and connector_name.replace(" database", "") not in normalized:
        score -= 10
    return score


def source_matches_query(source, query_text):
    pattern = source.get("meta", {}).get("pattern", "")
    label = source.get("label", "")

    if pattern:
        if has_connector_call(query_text, pattern):
            return True
        if datasource_matches(query_text, pattern):
            return True

    if label and datasource_matches(query_text, label):
        return True

    return False


def source_node_from_connector(connector, matched_by):
    display_name = canonical_connector_name(connector["name"])
    return source_node(
        display_name,
        connector.get("icon", initials(connector["name"])),
        matched_by,
        icon_url=connector.get("iconUrl", ""),
        doc=connector.get("doc", ""),
        image=connector.get("image", ""),
    )


def canonical_connector_name(name):
    return CANONICAL_CONNECTOR_NAMES.get(name, name)


def source_node(name, icon, pattern, icon_url="", doc="", image=""):
    return {
        "id": f"source:{slug(name)}",
        "type": "source",
        "label": name,
        "icon": icon,
        "iconUrl": icon_url,
        "meta": {"pattern": pattern, "doc": doc, "image": image},
    }


def detect_connector_nodes(power_query, datasources):
    detected = {}
    expressions = "\n".join(record_text(row) for row in power_query)

    for connector in CONNECTORS:
        for pattern in connector.get("patterns", []):
            preferred = PREFERRED_PATTERN_CONNECTORS.get(pattern)
            if preferred and connector["name"] != preferred:
                continue
            if has_connector_call(expressions, pattern):
                detected[canonical_connector_name(connector["name"])] = source_node_from_connector(connector, pattern)
                break

        if connector["name"] in detected:
            continue

        for keyword in connector.get("keywords", []):
            if datasource_matches(expressions, keyword):
                detected[canonical_connector_name(connector["name"])] = source_node_from_connector(connector, keyword)
                break

    for source in datasources:
        source_text = " ".join(str(value) for value in source.values() if value)
        matches = []
        for connector in CONNECTORS:
            for keyword in connector.get("keywords", []):
                if not datasource_matches(source_text, keyword):
                    continue
                matches.append((datasource_match_score(source_text, keyword, connector), connector, keyword))
        if matches:
            _, connector, keyword = max(matches, key=lambda item: item[0])
            node = source_node_from_connector(connector, keyword)
            node["meta"]["datasource"] = source
            detected[canonical_connector_name(connector["name"])] = node

    return list(detected.values())
