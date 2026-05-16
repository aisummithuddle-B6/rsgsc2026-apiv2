import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CREATE_TABLE_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+(?P<schema>\w+)\.(?P<table>\[[^\]]+\]|\w+)\s*\("
    r"(?P<body>.*?)\n\s*\);\s*GO",
    re.IGNORECASE | re.DOTALL,
)

CONSTRAINT_NAME_PATTERN = re.compile(r"CONSTRAINT\s+(\S+)", re.IGNORECASE)
FOREIGN_KEY_PATTERN = re.compile(
    r"CONSTRAINT\s+(?P<name>\S+)\s+FOREIGN\s+KEY\s+\((?P<columns>[^)]+)\)\s+"
    r"REFERENCES\s+(?P<schema>\w+)\.(?P<table>\[[^\]]+\]|\w+)\s+\((?P<referenced_columns>[^)]+)\)",
    re.IGNORECASE,
)
UNIQUE_PATTERN = re.compile(
    r"CONSTRAINT\s+(?P<name>\S+)\s+UNIQUE\s+\((?P<columns>[^)]+)\)",
    re.IGNORECASE,
)
PRIMARY_KEY_PATTERN = re.compile(r"PRIMARY\s+KEY(?:\s+\((?P<columns>[^)]+)\))?", re.IGNORECASE)


def build_entity_schema_documents(sql_text: str, source_file: str) -> list[dict[str, Any]]:
    generated_at = datetime.now(UTC).isoformat()
    documents: list[dict[str, Any]] = []

    for match in CREATE_TABLE_PATTERN.finditer(sql_text):
        schema_name = _clean_identifier(match.group("schema"))
        entity_name = _clean_identifier(match.group("table"))
        body = match.group("body")

        columns: list[dict[str, Any]] = []
        primary_key_columns: list[str] = []
        foreign_keys: list[dict[str, Any]] = []
        unique_constraints: list[dict[str, Any]] = []

        for raw_line in body.splitlines():
            line = _normalize_line(raw_line)
            if not line:
                continue

            upper_line = line.upper()
            if upper_line.startswith("CONSTRAINT"):
                foreign_key = _parse_foreign_key(line)
                if foreign_key is not None:
                    foreign_keys.append(foreign_key)
                    continue

                unique_constraint = _parse_unique_constraint(line)
                if unique_constraint is not None:
                    unique_constraints.append(unique_constraint)
                    continue

                table_primary_keys = _parse_primary_key_columns(line)
                if table_primary_keys:
                    primary_key_columns.extend(table_primary_keys)
                    continue

            column = _parse_column(line)
            if column is None:
                continue

            columns.append(column)
            if "PRIMARY KEY" in upper_line:
                primary_key_columns.append(column["name"])

        primary_key_columns = _dedupe(primary_key_columns)
        documents.append(
            {
                "_id": f"{schema_name}.{entity_name}",
                "schemaName": schema_name,
                "entityName": entity_name,
                "tableName": f"{schema_name}.{entity_name}",
                "primaryKey": primary_key_columns[0] if primary_key_columns else None,
                "primaryKeyColumns": primary_key_columns,
                "columns": columns,
                "foreignKeys": foreign_keys,
                "uniqueConstraints": unique_constraints,
                "sourceFile": source_file,
                "generatedAt": generated_at,
            }
        )

    return documents


def build_entity_schema_documents_from_file(path: Path) -> list[dict[str, Any]]:
    return build_entity_schema_documents(path.read_text(encoding="utf-8"), path.name)


def _parse_column(line: str) -> dict[str, Any] | None:
    match = re.match(
        r"(?P<name>\[[^\]]+\]|\w+)\s+(?P<type>[A-Z0-9]+(?:\([^)]+\))?)(?=\s|$)(?P<rest>.*)",
        line,
        re.IGNORECASE,
    )
    if match is None:
        return None

    rest = match.group("rest").upper()
    return {
        "name": _clean_identifier(match.group("name")),
        "type": match.group("type").upper(),
        "nullable": "NOT NULL" not in rest,
    }


def _parse_foreign_key(line: str) -> dict[str, Any] | None:
    match = FOREIGN_KEY_PATTERN.search(line)
    if match is None:
        return None

    return {
        "name": _clean_identifier(match.group("name")),
        "columns": _parse_identifier_list(match.group("columns")),
        "referencedTable": (
            f"{_clean_identifier(match.group('schema'))}."
            f"{_clean_identifier(match.group('table'))}"
        ),
        "referencedColumns": _parse_identifier_list(match.group("referenced_columns")),
    }


def _parse_unique_constraint(line: str) -> dict[str, Any] | None:
    match = UNIQUE_PATTERN.search(line)
    if match is None:
        return None

    return {
        "name": _clean_identifier(match.group("name")),
        "columns": _parse_identifier_list(match.group("columns")),
    }


def _parse_primary_key_columns(line: str) -> list[str]:
    match = PRIMARY_KEY_PATTERN.search(line)
    if match is None or match.group("columns") is None:
        return []

    return _parse_identifier_list(match.group("columns"))


def _parse_identifier_list(value: str) -> list[str]:
    return [_clean_identifier(item) for item in value.split(",")]


def _normalize_line(line: str) -> str:
    return line.strip().rstrip(",")


def _clean_identifier(value: str) -> str:
    return value.strip().strip("[]")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped
