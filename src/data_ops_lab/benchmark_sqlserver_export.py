from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Iterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from .benchmark_sql_conversion import MANIFEST_NAME, RELATIONSHIPS_NAME, REPORT_NAME
from .contracts.atomic_publish import publish_new_directory
from .contracts.hashing import file_sha256
from .io_utils import slugify


EXPORTER_VERSION = 1
SCHEMA_NAME = "schema_candidates.yml"
LOCAL_SERVERS = {".", "(local)", "localhost", "127.0.0.1"}
DEFAULT_DRIVER = "ODBC Driver 18 for SQL Server"
ALLOWED_DRIVERS = {
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 18 for SQL Server",
}
DEFAULT_BATCH_SIZE = 10_000
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 50_000
DATABASE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}")
NORMALIZED_IDENTIFIER_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,62}")
ODBC_SQL_MODE_READ_ONLY = 1


@dataclass(frozen=True)
class SqlServerColumn:
    source_name: str
    name: str
    source_type: str
    system_type: str
    duckdb_type: str
    arrow_type: pa.DataType
    nullable: bool
    identity: bool
    identity_start: int | None
    identity_increment: int | None


@dataclass(frozen=True)
class SqlServerTable:
    source_schema: str
    source_name: str
    name: str
    columns: tuple[SqlServerColumn, ...]
    primary_key: tuple[str, ...]


@dataclass(frozen=True)
class SqlServerRelationship:
    constraint_name: str
    source_table: str
    source_columns: tuple[str, ...]
    target_table: str
    target_columns: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkSqlServerExportResult:
    output_dir: Path
    status: str
    database_path: Path
    manifest_path: Path
    relationships_path: Path
    schema_path: Path
    report_path: Path
    blocker_count: int
    table_count: int
    row_count: int
    relationship_count: int
    outputs_changed: bool


class SqlServerExportSource(Protocol):
    def database_evidence(self) -> dict[str, Any]: ...

    def tables(self) -> list[SqlServerTable]: ...

    def relationships(
        self, tables: Sequence[SqlServerTable]
    ) -> list[SqlServerRelationship]: ...

    def iter_batches(
        self, table: SqlServerTable, batch_size: int
    ) -> Iterator[Sequence[Sequence[Any]]]: ...

    def close(self) -> None: ...


SourceFactory = Callable[[str, str, str], SqlServerExportSource]


def quote_sqlserver_identifier(value: str) -> str:
    return f"[{value.replace(']', ']]')}]"


def quote_duckdb_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def normalized_table_name(schema: str, table: str) -> str:
    value = slugify(f"{schema}_{table}")
    if not value:
        raise ValueError("SQL Server table name cannot normalize to an empty name.")
    return value


def normalized_column_name(column: str) -> str:
    value = slugify(column)
    if not value:
        raise ValueError("SQL Server column name cannot normalize to an empty name.")
    return value


def _column_type(
    declared_type: str,
    system_type: str,
    precision: int,
    scale: int,
) -> tuple[str, pa.DataType]:
    source_type = system_type.casefold()
    special_type = declared_type.casefold()
    if special_type in {"hierarchyid"}:
        return "VARCHAR", pa.string()
    if special_type in {"geography", "geometry"}:
        return "BLOB", pa.binary()
    if source_type == "bigint":
        return "BIGINT", pa.int64()
    if source_type == "int":
        return "INTEGER", pa.int32()
    if source_type == "smallint":
        return "SMALLINT", pa.int16()
    if source_type == "tinyint":
        return "SMALLINT", pa.int16()
    if source_type == "bit":
        return "BOOLEAN", pa.bool_()
    if source_type in {"decimal", "numeric"}:
        if not 1 <= precision <= 38 or not 0 <= scale <= precision:
            raise ValueError(
                f"Unsupported SQL Server decimal definition: ({precision}, {scale})."
            )
        return f"DECIMAL({precision},{scale})", pa.decimal128(precision, scale)
    if source_type == "money":
        return "DECIMAL(19,4)", pa.decimal128(19, 4)
    if source_type == "smallmoney":
        return "DECIMAL(10,4)", pa.decimal128(10, 4)
    if source_type == "float":
        return "DOUBLE", pa.float64()
    if source_type == "real":
        return "FLOAT", pa.float32()
    if source_type == "date":
        return "DATE", pa.date32()
    if source_type == "time":
        return "TIME", pa.time64("us")
    if source_type in {"datetime", "datetime2", "smalldatetime"}:
        return "TIMESTAMP", pa.timestamp("us")
    if source_type == "datetimeoffset":
        return "VARCHAR", pa.string()
    if source_type in {
        "char",
        "nchar",
        "varchar",
        "nvarchar",
        "text",
        "ntext",
        "xml",
        "uniqueidentifier",
    }:
        return "VARCHAR", pa.string()
    if source_type in {
        "binary",
        "varbinary",
        "image",
        "timestamp",
        "rowversion",
    }:
        return "BLOB", pa.binary()
    raise ValueError(
        f"Unsupported SQL Server type {declared_type!r} (system type {system_type!r})."
    )


def _select_expression(column: SqlServerColumn) -> str:
    identifier = quote_sqlserver_identifier(column.source_name)
    declared = column.source_type.casefold()
    system = column.system_type.casefold()
    if declared == "hierarchyid":
        return f"{identifier}.ToString()"
    if declared in {"geography", "geometry"}:
        return f"{identifier}.STAsBinary()"
    if system == "xml":
        return f"CONVERT(nvarchar(max), {identifier})"
    if system == "uniqueidentifier":
        return f"CONVERT(char(36), {identifier})"
    if system == "datetimeoffset":
        return f"CONVERT(nvarchar(50), {identifier}, 127)"
    return identifier


def _integer_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _tables_from_catalog(
    column_rows: Sequence[Sequence[Any]],
    primary_key_rows: Sequence[Sequence[Any]],
) -> list[SqlServerTable]:
    keys: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for schema, table, ordinal, column in primary_key_rows:
        keys.setdefault((str(schema), str(table)), []).append(
            (int(ordinal), str(column))
        )
    grouped: dict[tuple[str, str], list[SqlServerColumn]] = {}
    normalized_tables: dict[str, tuple[str, str]] = {}
    normalized_columns: dict[tuple[str, str], set[str]] = {}
    for row in column_rows:
        (
            schema,
            table,
            _ordinal,
            source_column,
            declared_type,
            system_type,
            _max_length,
            precision,
            scale,
            nullable,
            identity,
            identity_start,
            identity_increment,
        ) = row
        source_key = (str(schema), str(table))
        table_name = normalized_table_name(*source_key)
        previous = normalized_tables.setdefault(table_name, source_key)
        if previous != source_key:
            raise ValueError(
                f"Normalized SQL Server table collision: {previous!r} and {source_key!r}."
            )
        column_name = normalized_column_name(str(source_column))
        seen_columns = normalized_columns.setdefault(source_key, set())
        if column_name in seen_columns:
            raise ValueError(
                f"Normalized SQL Server column collision in {source_key!r}: {column_name!r}."
            )
        seen_columns.add(column_name)
        duckdb_type, arrow_type = _column_type(
            str(declared_type), str(system_type), int(precision), int(scale)
        )
        grouped.setdefault(source_key, []).append(
            SqlServerColumn(
                source_name=str(source_column),
                name=column_name,
                source_type=str(declared_type),
                system_type=str(system_type),
                duckdb_type=duckdb_type,
                arrow_type=arrow_type,
                nullable=bool(nullable),
                identity=bool(identity),
                identity_start=_integer_or_none(identity_start),
                identity_increment=_integer_or_none(identity_increment),
            )
        )
    tables: list[SqlServerTable] = []
    for (schema, source_table), columns in sorted(
        grouped.items(), key=lambda item: normalized_table_name(*item[0])
    ):
        key_rows = sorted(keys.get((schema, source_table), []))
        if not key_rows:
            raise ValueError(
                f"Deterministic export requires a source-declared primary key: {schema}.{source_table}."
            )
        source_to_normalized = {column.source_name: column.name for column in columns}
        primary_key = tuple(
            source_to_normalized[source_column] for _, source_column in key_rows
        )
        tables.append(
            SqlServerTable(
                source_schema=schema,
                source_name=source_table,
                name=normalized_table_name(schema, source_table),
                columns=tuple(columns),
                primary_key=primary_key,
            )
        )
    if not tables:
        raise ValueError("SQL Server export found no user tables.")
    return tables


def _relationships_from_catalog(
    rows: Sequence[Sequence[Any]],
    tables: Sequence[SqlServerTable],
) -> list[SqlServerRelationship]:
    table_lookup = {
        (table.source_schema, table.source_name): table for table in tables
    }
    grouped: dict[
        tuple[int, str, str, str, str, str],
        list[tuple[int, str, str]],
    ] = {}
    for row in rows:
        (
            object_id,
            constraint,
            source_schema,
            source_table,
            target_schema,
            target_table,
            ordinal,
            source_column,
            target_column,
        ) = row
        key = (
            int(object_id),
            str(constraint),
            str(source_schema),
            str(source_table),
            str(target_schema),
            str(target_table),
        )
        grouped.setdefault(key, []).append(
            (int(ordinal), str(source_column), str(target_column))
        )
    relationships: list[SqlServerRelationship] = []
    for key, columns in grouped.items():
        _, constraint, source_schema, source_table, target_schema, target_table = key
        source = table_lookup.get((source_schema, source_table))
        target = table_lookup.get((target_schema, target_table))
        if source is None or target is None:
            raise ValueError(f"Foreign key {constraint!r} references an unknown user table.")
        source_lookup = {
            column.source_name: column.name for column in source.columns
        }
        target_lookup = {
            column.source_name: column.name for column in target.columns
        }
        ordered = sorted(columns)
        relationships.append(
            SqlServerRelationship(
                constraint_name=constraint,
                source_table=source.name,
                source_columns=tuple(source_lookup[row[1]] for row in ordered),
                target_table=target.name,
                target_columns=tuple(target_lookup[row[2]] for row in ordered),
            )
        )
    return sorted(
        relationships,
        key=lambda row: (
            row.source_table,
            row.source_columns,
            row.target_table,
            row.target_columns,
            row.constraint_name,
        ),
    )


def _validate_export_contract(
    tables: Sequence[SqlServerTable],
    relationships: Sequence[SqlServerRelationship],
) -> None:
    if not tables:
        raise ValueError("SQL Server export found no user tables.")
    table_lookup: dict[str, SqlServerTable] = {}
    for table in tables:
        if not NORMALIZED_IDENTIFIER_PATTERN.fullmatch(table.name):
            raise ValueError(f"Unsafe normalized SQL Server table name: {table.name!r}.")
        if table.name in table_lookup:
            raise ValueError(f"Duplicate normalized SQL Server table: {table.name!r}.")
        if not table.columns:
            raise ValueError(f"SQL Server table {table.name!r} has no columns.")
        column_names = [column.name for column in table.columns]
        if any(
            not NORMALIZED_IDENTIFIER_PATTERN.fullmatch(column)
            for column in column_names
        ):
            raise ValueError(f"Unsafe normalized column in SQL Server table {table.name!r}.")
        if len(column_names) != len(set(column_names)):
            raise ValueError(f"Duplicate normalized column in SQL Server table {table.name!r}.")
        if not table.primary_key or any(
            column not in column_names for column in table.primary_key
        ):
            raise ValueError(
                f"Deterministic export requires a valid source-declared primary key: {table.name}."
            )
        if len(table.primary_key) != len(set(table.primary_key)):
            raise ValueError(f"Duplicate primary-key column in SQL Server table {table.name!r}.")
        table_lookup[table.name] = table

    seen_relationships: set[
        tuple[str, tuple[str, ...], str, tuple[str, ...]]
    ] = set()
    for relationship in relationships:
        source = table_lookup.get(relationship.source_table)
        target = table_lookup.get(relationship.target_table)
        if source is None or target is None:
            raise ValueError(
                f"Foreign key {relationship.constraint_name!r} references an unknown table."
            )
        if (
            not relationship.source_columns
            or len(relationship.source_columns) != len(relationship.target_columns)
            or len(relationship.source_columns) != len(set(relationship.source_columns))
            or len(relationship.target_columns) != len(set(relationship.target_columns))
        ):
            raise ValueError(
                f"Foreign key {relationship.constraint_name!r} has invalid column cardinality."
            )
        source_columns = {column.name for column in source.columns}
        target_columns = {column.name for column in target.columns}
        if any(column not in source_columns for column in relationship.source_columns):
            raise ValueError(
                f"Foreign key {relationship.constraint_name!r} has an unknown source column."
            )
        if any(column not in target_columns for column in relationship.target_columns):
            raise ValueError(
                f"Foreign key {relationship.constraint_name!r} has an unknown target column."
            )
        identity = (
            relationship.source_table,
            relationship.source_columns,
            relationship.target_table,
            relationship.target_columns,
        )
        if identity in seen_relationships:
            raise ValueError(f"Duplicate SQL Server foreign key candidate: {identity!r}.")
        seen_relationships.add(identity)


class PyodbcSqlServerSource:
    def __init__(self, server: str, database: str, driver: str) -> None:
        try:
            import pyodbc
        except ImportError as error:
            raise RuntimeError(
                "SQL Server export requires the optional 'sqlserver' dependency. "
                "Install the project with .[sqlserver] before an authorized export."
            ) from error
        self._pyodbc = pyodbc
        connection_string = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
            "ApplicationIntent=ReadOnly;"
        )
        try:
            self._connection = pyodbc.connect(
                connection_string,
                autocommit=False,
                attrs_before={
                    pyodbc.SQL_ATTR_ACCESS_MODE: ODBC_SQL_MODE_READ_ONLY,
                },
                timeout=10,
            )
        except pyodbc.Error as error:
            raise RuntimeError(
                "Could not open the authorized local SQL Server database through read-only ODBC."
            ) from error
        self._server = server
        self._database = database
        self._driver = driver
        cursor = self._connection.cursor()
        try:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        finally:
            cursor.close()

    def _all(self, query: str) -> list[tuple[Any, ...]]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(query)
            return [tuple(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def database_evidence(self) -> dict[str, Any]:
        rows = self._all(
            """
            SELECT
                DB_NAME(),
                d.state_desc,
                d.is_read_only,
                d.compatibility_level,
                CONVERT(nvarchar(128), SERVERPROPERTY('Edition')),
                CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion'))
            FROM sys.databases AS d
            WHERE d.name = DB_NAME()
            """
        )
        if len(rows) != 1:
            raise ValueError("SQL Server database preflight returned no exact database.")
        name, state, read_only, compatibility, edition, version = rows[0]
        return {
            "server": self._server,
            "database": str(name),
            "state": str(state),
            "read_only": bool(read_only),
            "compatibility_level": int(compatibility),
            "server_edition": str(edition),
            "server_version": str(version),
            "odbc_driver": self._driver,
            "pyodbc_version": str(self._pyodbc.version),
            "integrated_authentication": True,
            "application_intent": "ReadOnly",
        }

    def tables(self) -> list[SqlServerTable]:
        columns = self._all(
            """
            SELECT
                s.name,
                t.name,
                c.column_id,
                c.name,
                declared.name,
                COALESCE(base.name, declared.name),
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable,
                c.is_identity,
                identity_column.seed_value,
                identity_column.increment_value
            FROM sys.tables AS t
            JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            JOIN sys.columns AS c ON c.object_id = t.object_id
            JOIN sys.types AS declared ON declared.user_type_id = c.user_type_id
            LEFT JOIN sys.types AS base
                ON base.user_type_id = c.system_type_id
                AND base.user_type_id = base.system_type_id
            LEFT JOIN sys.identity_columns AS identity_column
                ON identity_column.object_id = c.object_id
                AND identity_column.column_id = c.column_id
            WHERE t.is_ms_shipped = 0
            ORDER BY s.name, t.name, c.column_id
            """
        )
        primary_keys = self._all(
            """
            SELECT s.name, t.name, ic.key_ordinal, c.name
            FROM sys.tables AS t
            JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            JOIN sys.indexes AS i
                ON i.object_id = t.object_id AND i.is_primary_key = 1
            JOIN sys.index_columns AS ic
                ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            JOIN sys.columns AS c
                ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE t.is_ms_shipped = 0
            ORDER BY s.name, t.name, ic.key_ordinal
            """
        )
        return _tables_from_catalog(columns, primary_keys)

    def relationships(
        self, tables: Sequence[SqlServerTable]
    ) -> list[SqlServerRelationship]:
        rows = self._all(
            """
            SELECT
                fk.object_id,
                fk.name,
                source_schema.name,
                source_table.name,
                target_schema.name,
                target_table.name,
                fkc.constraint_column_id,
                source_column.name,
                target_column.name
            FROM sys.foreign_keys AS fk
            JOIN sys.foreign_key_columns AS fkc
                ON fkc.constraint_object_id = fk.object_id
            JOIN sys.tables AS source_table
                ON source_table.object_id = fk.parent_object_id
            JOIN sys.schemas AS source_schema
                ON source_schema.schema_id = source_table.schema_id
            JOIN sys.columns AS source_column
                ON source_column.object_id = fkc.parent_object_id
                AND source_column.column_id = fkc.parent_column_id
            JOIN sys.tables AS target_table
                ON target_table.object_id = fk.referenced_object_id
            JOIN sys.schemas AS target_schema
                ON target_schema.schema_id = target_table.schema_id
            JOIN sys.columns AS target_column
                ON target_column.object_id = fkc.referenced_object_id
                AND target_column.column_id = fkc.referenced_column_id
            WHERE source_table.is_ms_shipped = 0
              AND target_table.is_ms_shipped = 0
            ORDER BY fk.object_id, fkc.constraint_column_id
            """
        )
        return _relationships_from_catalog(rows, tables)

    def iter_batches(
        self, table: SqlServerTable, batch_size: int
    ) -> Iterator[Sequence[Sequence[Any]]]:
        projections = ", ".join(_select_expression(column) for column in table.columns)
        source_columns = {column.name: column.source_name for column in table.columns}
        ordering = ", ".join(
            quote_sqlserver_identifier(source_columns[column])
            for column in table.primary_key
        )
        table_name = (
            f"{quote_sqlserver_identifier(table.source_schema)}."
            f"{quote_sqlserver_identifier(table.source_name)}"
        )
        cursor = self._connection.cursor()
        cursor.arraysize = batch_size
        try:
            cursor.execute(f"SELECT {projections} FROM {table_name} ORDER BY {ordering}")
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield [tuple(row) for row in rows]
        finally:
            cursor.close()

    def close(self) -> None:
        try:
            self._connection.rollback()
        finally:
            self._connection.close()


def open_pyodbc_source(
    server: str, database: str, driver: str
) -> SqlServerExportSource:
    return PyodbcSqlServerSource(server, database, driver)


def _coerce_value(value: Any, arrow_type: pa.DataType) -> Any:
    if value is None:
        return None
    if pa.types.is_binary(arrow_type):
        return bytes(value)
    if pa.types.is_string(arrow_type):
        return str(value)
    if pa.types.is_decimal(arrow_type) and not isinstance(value, Decimal):
        return Decimal(str(value))
    return value


def _write_table_parquet(
    source: SqlServerExportSource,
    table: SqlServerTable,
    parquet_path: Path,
    batch_size: int,
) -> int:
    schema = pa.schema(
        [
            pa.field(column.name, column.arrow_type, nullable=column.nullable)
            for column in table.columns
        ]
    )
    writer = pq.ParquetWriter(
        parquet_path,
        schema,
        compression="zstd",
        use_dictionary=False,
        version="2.6",
        write_statistics=True,
    )
    row_count = 0
    try:
        for rows in source.iter_batches(table, batch_size):
            columns = list(zip(*rows, strict=True)) if rows else []
            arrays = [
                pa.array(
                    [_coerce_value(value, column.arrow_type) for value in values],
                    type=column.arrow_type,
                )
                for column, values in zip(table.columns, columns, strict=True)
            ]
            if any(
                not column.nullable and array.null_count
                for column, array in zip(table.columns, arrays, strict=True)
            ):
                raise ValueError(
                    f"SQL Server table {table.name!r} returned NULL for a non-nullable column."
                )
            batch = pa.Table.from_arrays(arrays, schema=schema)
            writer.write_table(batch, row_group_size=batch_size)
            row_count += batch.num_rows
        if row_count == 0:
            writer.write_table(
                pa.Table.from_arrays(
                    [pa.array([], type=column.arrow_type) for column in table.columns],
                    schema=schema,
                )
            )
    finally:
        writer.close()
    return row_count


def _relationship_payload(
    relationships: Sequence[SqlServerRelationship],
) -> dict[str, Any]:
    return {
        "version": 2,
        "status": "pending_review",
        "relationship_candidates": [
            {
                "constraint_name": relationship.constraint_name,
                "source_table": relationship.source_table,
                "source_columns": list(relationship.source_columns),
                "target_table": relationship.target_table,
                "target_columns": list(relationship.target_columns),
                "evidence": "source_declared_foreign_key",
                "status": "pending_review",
            }
            for relationship in relationships
        ],
    }


def _schema_payload(dataset: str, tables: Sequence[SqlServerTable]) -> dict[str, Any]:
    return {
        "version": 1,
        "dataset": dataset,
        "status": "pending_review",
        "authority_rule": "source_declaration_is_technical_evidence_not_human_approval",
        "primary_keys": [
            {
                "table": table.name,
                "columns": list(table.primary_key),
                "evidence": "source_declared_primary_key",
                "status": "pending_review",
            }
            for table in tables
        ],
    }


def _report(
    dataset: str,
    tables: Sequence[dict[str, Any]],
    relationships: Sequence[SqlServerRelationship],
    database_evidence: dict[str, Any],
) -> str:
    lines = [
        f"# {dataset} SQL Server Export Report",
        "",
        "- Status: `ready_for_local_benchmark`",
        f"- Source database: `{database_evidence['database']}`",
        f"- Source state: `{database_evidence['state']}`",
        f"- Source read-only: `{str(database_evidence['read_only']).lower()}`",
        f"- Tables: {len(tables)}",
        f"- Rows: {sum(int(row['rows']) for row in tables)}",
        f"- Source-declared relationship candidates: {len(relationships)}",
        "",
        "## Tables",
        "",
    ]
    lines.extend(f"- `{row['name']}`: {row['rows']} rows" for row in tables)
    lines.extend(
        [
            "",
            "## Export Boundary",
            "",
            "- The source backup SHA-256 was verified before and after export.",
            "- The connection used integrated authentication, ODBC read-only access,",
            "  and `ApplicationIntent=ReadOnly` against an already read-only database.",
            "- User tables were ordered by source-declared primary keys and streamed",
            "  in bounded batches to Zstandard Parquet.",
            "- DuckDB tables were materialized only from the generated Parquet files.",
            "- Foreign keys remain pending candidates and were not enforced or approved.",
            "- No source row content is included in this report or the manifest.",
        ]
    )
    return "\n".join(lines) + "\n"


def _existing_result(
    source_path: Path,
    dataset: str,
    database_name: str,
    server: str,
    driver: str,
    batch_size: int,
    output_dir: Path,
) -> BenchmarkSqlServerExportResult | None:
    if not output_dir.exists():
        return None
    manifest_path = output_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(f"Existing SQL Server export output is incomplete: {output_dir}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(manifest, dict):
        raise ValueError("Existing SQL Server export manifest must be a mapping.")
    conversion = manifest.get("conversion", {})
    if not isinstance(conversion, dict):
        conversion = {}
    source_database = conversion.get("source_database", {})
    if not isinstance(source_database, dict):
        source_database = {}
    if (
        manifest.get("status") != "ready_for_local_benchmark"
        or manifest.get("dataset") != dataset
        or conversion.get("exporter_version") != EXPORTER_VERSION
        or conversion.get("batch_size") != batch_size
        or source_database.get("database") != database_name
        or str(source_database.get("server", "")).casefold() != server.casefold()
        or source_database.get("odbc_driver") != driver
        or manifest.get("source", {}).get("sha256") != file_sha256(source_path)
    ):
        raise ValueError(
            f"Different SQL Server export outputs already exist in {output_dir}. "
            "Use a new output directory; existing derived data was not overwritten."
        )
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("Existing SQL Server export manifest has invalid artifacts.")
    artifact_rows = [artifacts.get("database", {})]
    parquet_artifacts = artifacts.get("parquet", [])
    if not isinstance(parquet_artifacts, list):
        raise ValueError("Existing SQL Server export manifest has invalid Parquet artifacts.")
    artifact_rows.extend(parquet_artifacts)
    artifact_rows.extend(
        [
            artifacts.get("relationships", {}),
            artifacts.get("schema", {}),
            artifacts.get("report", {}),
        ]
    )
    for artifact in artifact_rows:
        if not isinstance(artifact, dict):
            raise ValueError("Existing SQL Server export manifest has an invalid artifact.")
        artifact_name = artifact.get("path")
        if not isinstance(artifact_name, str) or not artifact_name:
            raise ValueError("Existing SQL Server export manifest has an invalid artifact path.")
        path = (output_dir / artifact_name).resolve()
        if not path.is_relative_to(output_dir.resolve()):
            raise ValueError("Existing SQL Server export artifact path escapes its output directory.")
        if not path.is_file() or file_sha256(path) != artifact.get("sha256"):
            raise ValueError(
                "Existing SQL Server export artifacts do not match their manifest hashes."
            )
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("Existing SQL Server export manifest has invalid counts.")
    return BenchmarkSqlServerExportResult(
        output_dir=output_dir,
        status=manifest["status"],
        database_path=output_dir / artifacts["database"]["path"],
        manifest_path=manifest_path,
        relationships_path=output_dir / artifacts["relationships"]["path"],
        schema_path=output_dir / artifacts["schema"]["path"],
        report_path=output_dir / artifacts["report"]["path"],
        blocker_count=0,
        table_count=int(counts["tables"]),
        row_count=int(counts["rows"]),
        relationship_count=int(counts["relationship_candidates"]),
        outputs_changed=False,
    )


def run_benchmark_sqlserver_export(
    source_backup_path: Path,
    dataset_name: str,
    database_name: str,
    output_dir: Path,
    *,
    server: str = "localhost",
    driver: str = DEFAULT_DRIVER,
    batch_size: int = DEFAULT_BATCH_SIZE,
    execute: bool = False,
    source_factory: SourceFactory | None = None,
) -> BenchmarkSqlServerExportResult:
    if not source_backup_path.is_file() or source_backup_path.suffix.casefold() != ".bak":
        raise ValueError("SQL Server export requires an existing local .bak source.")
    dataset = slugify(dataset_name)
    if not dataset:
        raise ValueError("SQL Server export requires a stable dataset name.")
    server = server.strip()
    if server.casefold() not in LOCAL_SERVERS:
        raise ValueError("SQL Server export accepts only the authorized local default instance.")
    if not DATABASE_PATTERN.fullmatch(database_name):
        raise ValueError("SQL Server export requires a safe local database name.")
    if driver not in ALLOWED_DRIVERS:
        raise ValueError(
            "SQL Server export requires an explicitly allowed Microsoft ODBC Driver 17 or 18."
        )
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE
    ):
        raise ValueError(
            f"SQL Server export batch size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}."
        )
    existing = _existing_result(
        source_backup_path,
        dataset,
        database_name,
        server,
        driver,
        batch_size,
        output_dir,
    )
    if existing is not None:
        return existing
    if not execute:
        raise ValueError(
            "SQL Server export requires explicit execute=True after separate local export authorization."
        )

    source_hash = file_sha256(source_backup_path)
    source_bytes = source_backup_path.stat().st_size
    factory = source_factory or open_pyodbc_source
    source = factory(server, database_name, driver)
    staging_dir = output_dir.with_name(f"{output_dir.name}.building")
    staging_created = False
    database_path = staging_dir / f"{dataset}.duckdb"
    try:
        if staging_dir.exists():
            raise ValueError(f"Stale SQL Server export staging directory exists: {staging_dir}")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir()
        staging_created = True
        parquet_dir = staging_dir / "parquet"
        parquet_dir.mkdir()
        database_evidence = source.database_evidence()
        if database_evidence.get("database") != database_name:
            raise ValueError("SQL Server export connected to an unexpected database.")
        if database_evidence.get("state") != "ONLINE":
            raise ValueError("SQL Server export requires the source database to be ONLINE.")
        if database_evidence.get("read_only") is not True:
            raise ValueError("SQL Server export refuses a source database that is not READ_ONLY.")
        if (
            str(database_evidence.get("server", "")).casefold() != server.casefold()
            or database_evidence.get("odbc_driver") != driver
            or database_evidence.get("integrated_authentication") is not True
            or database_evidence.get("application_intent") != "ReadOnly"
        ):
            raise ValueError("SQL Server export connection evidence violates the authorized boundary.")
        tables = sorted(source.tables(), key=lambda table: table.name)
        relationships = source.relationships(tables)
        relationships = sorted(
            relationships,
            key=lambda row: (
                row.source_table,
                row.source_columns,
                row.target_table,
                row.target_columns,
                row.constraint_name,
            ),
        )
        _validate_export_contract(tables, relationships)
        table_rows: list[dict[str, Any]] = []
        parquet_artifacts: list[dict[str, Any]] = []
        with duckdb.connect(str(database_path)) as connection:
            for table in tables:
                parquet_path = parquet_dir / f"{table.name}.parquet"
                rows = _write_table_parquet(source, table, parquet_path, batch_size)
                connection.execute(
                    f"CREATE TABLE {quote_duckdb_identifier(table.name)} AS "
                    "SELECT * FROM read_parquet(?)",
                    [str(parquet_path)],
                )
                columns = [
                    {
                        "source_name": column.source_name,
                        "name": column.name,
                        "source_type": column.source_type,
                        "system_type": column.system_type,
                        "duckdb_type": column.duckdb_type,
                        "nullable": column.nullable,
                        "identity": column.identity,
                        "identity_start": column.identity_start,
                        "identity_increment": column.identity_increment,
                    }
                    for column in table.columns
                ]
                table_rows.append(
                    {
                        "source_schema": table.source_schema,
                        "source_name": table.source_name,
                        "name": table.name,
                        "rows": rows,
                        "primary_key": list(table.primary_key),
                        "columns": columns,
                    }
                )
                parquet_artifacts.append(
                    {
                        "table": table.name,
                        "path": f"parquet/{table.name}.parquet",
                        "rows": rows,
                        "sha256": file_sha256(parquet_path),
                    }
                )

        relationships_path = staging_dir / RELATIONSHIPS_NAME
        relationships_path.write_text(
            yaml.safe_dump(
                _relationship_payload(relationships),
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        schema_path = staging_dir / SCHEMA_NAME
        schema_path.write_text(
            yaml.safe_dump(
                _schema_payload(dataset, tables),
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        report_path = staging_dir / REPORT_NAME
        report_path.write_text(
            _report(dataset, table_rows, relationships, database_evidence),
            encoding="utf-8",
        )
        manifest = {
            "version": 1,
            "status": "ready_for_local_benchmark",
            "dataset": dataset,
            "source": {
                "filename": source_backup_path.name,
                "bytes": source_bytes,
                "sha256": source_hash,
                "format": "sql_server_backup",
            },
            "conversion": {
                "exporter_version": EXPORTER_VERSION,
                "source_engine": "sql_server",
                "source_database": database_evidence,
                "transport": "pyodbc",
                "target_engine": "duckdb",
                "parquet_writer": "pyarrow",
                "parquet_version": "2.6",
                "parquet_compression": "zstd",
                "batch_size": batch_size,
                "deterministic_order": "source_declared_primary_key",
                "database_read_only_required": True,
                "integrated_authentication_required": True,
                "local_server_only": True,
            },
            "counts": {
                "tables": len(table_rows),
                "rows": sum(int(row["rows"]) for row in table_rows),
                "relationship_candidates": len(relationships),
            },
            "tables": table_rows,
            "artifacts": {
                "database": {
                    "path": database_path.name,
                    "sha256": file_sha256(database_path),
                },
                "parquet": parquet_artifacts,
                "relationships": {
                    "path": RELATIONSHIPS_NAME,
                    "sha256": file_sha256(relationships_path),
                },
                "schema": {
                    "path": SCHEMA_NAME,
                    "sha256": file_sha256(schema_path),
                },
                "report": {
                    "path": REPORT_NAME,
                    "sha256": file_sha256(report_path),
                },
            },
            "approval": {
                "local_export_approved": True,
                "benchmark_use_approved": False,
                "relationship_candidates_approved": False,
                "model_training_approved": False,
                "external_upload_approved": False,
                "publication_approved": False,
            },
        }
        manifest_path = staging_dir / MANIFEST_NAME
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        if (
            source_backup_path.stat().st_size != source_bytes
            or file_sha256(source_backup_path) != source_hash
        ):
            raise ValueError("Source backup changed during SQL Server export.")
        closing_source = source
        source = None
        closing_source.close()
        publish_new_directory(staging_dir, output_dir)
    except Exception:
        if source is not None:
            with suppress(Exception):
                source.close()
        if staging_created and staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise

    return BenchmarkSqlServerExportResult(
        output_dir=output_dir,
        status="ready_for_local_benchmark",
        database_path=output_dir / database_path.name,
        manifest_path=output_dir / MANIFEST_NAME,
        relationships_path=output_dir / RELATIONSHIPS_NAME,
        schema_path=output_dir / SCHEMA_NAME,
        report_path=output_dir / REPORT_NAME,
        blocker_count=0,
        table_count=len(table_rows),
        row_count=sum(int(row["rows"]) for row in table_rows),
        relationship_count=len(relationships),
        outputs_changed=True,
    )
