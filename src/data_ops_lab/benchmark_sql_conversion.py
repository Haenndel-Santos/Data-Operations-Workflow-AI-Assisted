from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import duckdb
import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

from .io_utils import slugify, unique_names
from .source_onboarding import file_sha256


MANIFEST_NAME = "conversion_manifest.yml"
RELATIONSHIPS_NAME = "relationship_candidates.yml"
REPORT_NAME = "conversion_report.md"
CONVERTER_VERSION = 1
SQL_START_PATTERN = re.compile(r"(?im)^\s*CREATE\s+TABLE\b")
INSERT_START_PATTERN = re.compile(r"(?i)^\s*insert\s+")
INSERT_STOP_PATTERN = re.compile(
    r"(?i)^\s*(?:GO\s*$|raiserror|set\s+identity_insert|alter\s+table|"
    r"update\s+statistics|dbcc|create\s+|declare\s+|use\s+)"
)
BRACKETED_TYPES = (
    "int",
    "bigint",
    "smallint",
    "tinyint",
    "bit",
    "datetime",
    "smalldatetime",
    "date",
    "time",
    "nvarchar",
    "nchar",
    "ntext",
    "varchar",
    "char",
    "text",
    "image",
    "binary",
    "varbinary",
    "money",
    "smallmoney",
    "decimal",
    "numeric",
    "float",
    "real",
    "uniqueidentifier",
)
CUSTOM_TYPES = {
    "id": "varchar(11)",
    "tid": "varchar(6)",
    "empid": "char(9)",
}
TYPE_MAP = {
    "BIGINT": "BIGINT",
    "BINARY": "BLOB",
    "BIT": "BOOLEAN",
    "CHAR": "VARCHAR",
    "DATE": "DATE",
    "DATETIME": "TIMESTAMP",
    "DATETIME2": "TIMESTAMP",
    "FLOAT": "DOUBLE",
    "IMAGE": "BLOB",
    "INT": "INTEGER",
    "MONEY": "DECIMAL(19,4)",
    "NCHAR": "VARCHAR",
    "NTEXT": "VARCHAR",
    "NVARCHAR": "VARCHAR",
    "REAL": "REAL",
    "SMALLDATETIME": "TIMESTAMP",
    "SMALLINT": "SMALLINT",
    "SMALLMONEY": "DECIMAL(19,4)",
    "TEXT": "VARCHAR",
    "TIME": "TIME",
    "TIMESTAMP": "BLOB",
    "TINYINT": "UTINYINT",
    "UNIQUEIDENTIFIER": "UUID",
    "UTINYINT": "UTINYINT",
    "VARBINARY": "BLOB",
    "VARCHAR": "VARCHAR",
}
DATE_TYPES = {"DATE", "DATETIME", "DATETIME2", "SMALLDATETIME"}
MONEY_TYPES = {"MONEY", "SMALLMONEY"}


@dataclass(frozen=True)
class BenchmarkColumn:
    source_name: str
    name: str
    source_type: str
    duckdb_type: str
    identity: bool
    identity_start: int | None
    identity_increment: int | None


@dataclass(frozen=True)
class BenchmarkTable:
    source_name: str
    name: str
    columns: tuple[BenchmarkColumn, ...]
    expression: exp.Create


@dataclass(frozen=True)
class BenchmarkSqlConversionResult:
    output_dir: Path
    status: str
    database_path: Path
    manifest_path: Path
    relationships_path: Path
    report_path: Path
    table_count: int
    row_count: int
    relationship_count: int
    outputs_changed: bool


def benchmark_slug(value: str) -> str:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    return slugify(separated)


def quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def read_source(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"SQL source is neither UTF-8 nor Windows-1252: {path}")


def strip_sql_comments(text: str) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"(?m)--.*$", "", without_blocks)


def extract_create_table_statements(text: str) -> Iterator[str]:
    searchable = strip_sql_comments(text)
    for match in SQL_START_PATTERN.finditer(searchable):
        opening = searchable.find("(", match.end())
        if opening < 0:
            raise ValueError("CREATE TABLE statement has no opening parenthesis.")
        depth = 0
        in_string = False
        in_bracket = False
        index = opening
        while index < len(searchable):
            character = searchable[index]
            if in_string:
                escaped_quote = (
                    character == "'"
                    and index + 1 < len(searchable)
                    and searchable[index + 1] == "'"
                )
                if escaped_quote:
                    index += 2
                    continue
                if character == "'":
                    in_string = False
            elif in_bracket:
                if character == "]":
                    in_bracket = False
            elif character == "'":
                in_string = True
            elif character == "[":
                in_bracket = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    yield searchable[match.start() : index + 1]
                    break
            index += 1
        else:
            raise ValueError("CREATE TABLE statement has unbalanced parentheses.")


def preprocess_create_statement(statement: str) -> str:
    prepared = re.sub(r"(?i)\b(?:NON)?CLUSTERED\b", "", statement)
    for source_type in BRACKETED_TYPES:
        prepared = re.sub(
            rf"(?i)\[{re.escape(source_type)}\]",
            source_type,
            prepared,
        )
    for source_type, replacement in CUSTOM_TYPES.items():
        prepared = re.sub(
            rf"(?im)^(\s*[A-Za-z_][A-Za-z0-9_]*\s+){source_type}\b",
            rf"\1{replacement}",
            prepared,
        )
    return prepared


def source_type_name(data_type: exp.DataType) -> str:
    return str(data_type.this).split(".")[-1]


def duckdb_type(data_type: exp.DataType) -> str:
    source_type = source_type_name(data_type)
    if source_type in {"DECIMAL", "NUMERIC"}:
        return data_type.sql(dialect="duckdb")
    mapped = TYPE_MAP.get(source_type)
    if not mapped:
        raise ValueError(f"Unsupported T-SQL data type: {source_type}")
    return mapped


def identity_spec(column: exp.ColumnDef) -> tuple[int | None, int | None]:
    for constraint in column.args.get("constraints", []):
        kind = constraint.args.get("kind")
        if not isinstance(kind, exp.GeneratedAsIdentityColumnConstraint):
            continue
        start = kind.args.get("start")
        increment = kind.args.get("increment")
        return (
            int(start.this) if isinstance(start, exp.Literal) else 1,
            int(increment.this) if isinstance(increment, exp.Literal) else 1,
        )
    return None, None


def parse_tables(text: str) -> list[BenchmarkTable]:
    raw_statements = list(extract_create_table_statements(text))
    expected = len(SQL_START_PATTERN.findall(strip_sql_comments(text)))
    if len(raw_statements) != expected:
        raise ValueError(
            f"Expected {expected} CREATE TABLE statements but extracted {len(raw_statements)}."
        )
    parsed: list[tuple[str, exp.Create, list[exp.ColumnDef]]] = []
    source_table_names: list[str] = []
    for statement in raw_statements:
        try:
            expression = sqlglot.parse_one(preprocess_create_statement(statement), read="tsql")
        except (ParseError, TokenError) as error:
            raise ValueError(f"Unable to parse CREATE TABLE statement: {error}") from error
        if not isinstance(expression, exp.Create) or not isinstance(expression.this, exp.Schema):
            raise ValueError("Only parsed CREATE TABLE expressions are accepted.")
        table_name = expression.this.this.name
        columns = [
            item for item in expression.this.expressions if isinstance(item, exp.ColumnDef)
        ]
        if not columns:
            raise ValueError(f"Table {table_name} has no parsed columns.")
        parsed.append((table_name, expression, columns))
        source_table_names.append(table_name)

    normalized_tables = unique_names([benchmark_slug(name) for name in source_table_names])
    if len({name.casefold() for name in source_table_names}) != len(source_table_names):
        raise ValueError("Source table names are ambiguous when compared case-insensitively.")
    tables: list[BenchmarkTable] = []
    for (table_name, expression, columns), normalized_table in zip(
        parsed,
        normalized_tables,
        strict=True,
    ):
        normalized_columns = unique_names([benchmark_slug(column.name) for column in columns])
        table_columns_list = []
        for column, normalized_name in zip(columns, normalized_columns, strict=True):
            identity_start, identity_increment = identity_spec(column)
            table_columns_list.append(
                BenchmarkColumn(
                    source_name=column.name,
                    name=normalized_name,
                    source_type=source_type_name(column.args["kind"]),
                    duckdb_type=duckdb_type(column.args["kind"]),
                    identity=identity_start is not None,
                    identity_start=identity_start,
                    identity_increment=identity_increment,
                )
            )
        table_columns = tuple(table_columns_list)
        tables.append(
            BenchmarkTable(
                source_name=table_name,
                name=normalized_table,
                columns=table_columns,
                expression=expression,
            )
        )
    return tables


def extract_insert_statements(text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            statements.append("\n".join(current).strip())
            current.clear()

    for line in text.splitlines():
        if INSERT_START_PATTERN.match(line):
            flush()
            current.append(line)
        elif current:
            if INSERT_STOP_PATTERN.match(line):
                flush()
            else:
                current.append(line)
    flush()
    expected = len(re.findall(r"(?im)^\s*insert\s+", text))
    if len(statements) != expected:
        raise ValueError(f"Expected {expected} INSERT statements but extracted {len(statements)}.")
    return statements


def parse_source_datetime(value: str) -> str:
    for date_format in (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, date_format).isoformat(sep=" ")  # noqa: DTZ007 - source T-SQL literals carry no zone; naive is the exact value
        except ValueError:
            continue
    raise ValueError(f"Unsupported source date literal: {value}")


def table_lookup(tables: list[BenchmarkTable]) -> dict[str, BenchmarkTable]:
    return {table.source_name.casefold(): table for table in tables}


def transform_insert(
    statement: str,
    tables: dict[str, BenchmarkTable],
    identity_counters: dict[tuple[str, str], int],
) -> str:
    try:
        expression = sqlglot.parse_one(statement, read="tsql")
    except (ParseError, TokenError) as error:
        raise ValueError(f"Unable to parse INSERT statement: {error}") from error
    if not isinstance(expression, exp.Insert):
        raise ValueError("Only parsed INSERT expressions are accepted for row materialization.")

    schema = expression.this if isinstance(expression.this, exp.Schema) else None
    target = schema.this if schema else expression.this
    source_key = target.name.casefold()
    table = tables.get(source_key)
    if not table:
        raise ValueError(f"INSERT targets unknown table: {target.name}")
    target.set("this", exp.to_identifier(table.name, quoted=True))
    target.set("db", None)
    target.set("catalog", None)
    column_lookup = {column.source_name.casefold(): column for column in table.columns}

    def next_identity(column: BenchmarkColumn) -> exp.Literal:
        counter_key = (source_key, column.source_name.casefold())
        current = identity_counters[counter_key]
        identity_counters[counter_key] = current + int(column.identity_increment or 1)
        return exp.Literal.number(current)

    if schema:
        source_columns = [identifier.name.casefold() for identifier in schema.expressions]
        for identifier in schema.expressions:
            column = column_lookup.get(identifier.name.casefold())
            if not column:
                raise ValueError(
                    f"INSERT references unknown column {identifier.name} in {table.source_name}."
                )
            identifier.set("this", column.name)
            identifier.set("quoted", True)
        missing_identity = [
            column
            for column in table.columns
            if column.identity and column.source_name.casefold() not in source_columns
        ]
        for column in missing_identity:
            schema.set(
                "expressions",
                [*schema.expressions, exp.to_identifier(column.name, quoted=True)],
            )
            source_columns.append(column.source_name.casefold())
            for row in expression.expression.expressions:
                row.set("expressions", [*row.expressions, next_identity(column)])
    else:
        source_columns = [column.source_name.casefold() for column in table.columns]
        rows = expression.expression.expressions
        row_widths = {len(row.expressions) for row in rows}
        if row_widths != {len(table.columns)}:
            non_identity = [column for column in table.columns if not column.identity]
            if row_widths != {len(non_identity)}:
                raise ValueError(
                    f"INSERT width does not match table {table.source_name} columns."
                )
            for row in rows:
                source_values = iter(row.expressions)
                expanded_values = []
                for column in table.columns:
                    if column.identity:
                        expanded_values.append(next_identity(column))
                    else:
                        expanded_values.append(next(source_values))
                row.set("expressions", expanded_values)

    for row in expression.expression.expressions:
        values = list(row.expressions)
        for index, value in enumerate(values):
            column = column_lookup[source_columns[index]]
            if (
                column.source_type in DATE_TYPES
                and isinstance(value, exp.Literal)
                and value.is_string
            ):
                value.set("this", parse_source_datetime(value.this))
            if (
                column.source_type in MONEY_TYPES
                and isinstance(value, exp.Column)
                and value.table.startswith("$")
                and isinstance(value.this, exp.Literal)
            ):
                values[index] = exp.Literal.number(f"{value.table[1:]}.{value.this.this}")
            if column.identity and isinstance(value, exp.Literal) and not value.is_string:
                counter_key = (source_key, column.source_name.casefold())
                increment = int(column.identity_increment or 1)
                following = int(value.this) + increment
                current = identity_counters[counter_key]
                identity_counters[counter_key] = (
                    max(current, following) if increment > 0 else min(current, following)
                )
        row.set("expressions", values)
    return expression.sql(dialect="duckdb")


def reference_target(reference: exp.Reference) -> tuple[str, list[str]]:
    schema = reference.this
    if not isinstance(schema, exp.Schema) or not isinstance(schema.this, exp.Table):
        raise ValueError("Unsupported foreign-key reference shape.")
    return schema.this.name, [identifier.name for identifier in schema.expressions]


def normalized_relationship(
    source_table: str,
    source_columns: list[str],
    target_table: str,
    target_columns: list[str],
    tables: dict[str, BenchmarkTable],
) -> list[dict[str, str]]:
    if len(source_columns) != len(target_columns):
        raise ValueError("Foreign-key source and target widths differ.")
    source = tables.get(source_table.casefold())
    target = tables.get(target_table.casefold())
    if not source or not target:
        raise ValueError("Foreign key references a table outside the converted dataset.")
    source_lookup = {column.source_name.casefold(): column.name for column in source.columns}
    target_lookup = {column.source_name.casefold(): column.name for column in target.columns}
    relationships = []
    for source_column, target_column in zip(source_columns, target_columns, strict=True):
        source_missing = source_column.casefold() not in source_lookup
        target_missing = target_column.casefold() not in target_lookup
        if source_missing or target_missing:
            raise ValueError("Foreign key references an unknown converted column.")
        relationships.append(
            {
                "source_table": source.name,
                "source_column": source_lookup[source_column.casefold()],
                "target_table": target.name,
                "target_column": target_lookup[target_column.casefold()],
                "evidence": "source_declared_foreign_key",
                "status": "pending_review",
            }
        )
    return relationships


def relationships_from_expression(
    expression: exp.Expression,
    source_table: str,
    tables: dict[str, BenchmarkTable],
) -> list[dict[str, str]]:
    relationships: list[dict[str, str]] = []
    if isinstance(expression, exp.Create) and isinstance(expression.this, exp.Schema):
        for item in expression.this.expressions:
            if isinstance(item, exp.ColumnDef):
                for reference in item.find_all(exp.Reference):
                    target_table, target_columns = reference_target(reference)
                    relationships.extend(
                        normalized_relationship(
                            source_table,
                            [item.name],
                            target_table,
                            target_columns,
                            tables,
                        )
                    )
    for foreign_key in expression.find_all(exp.ForeignKey):
        reference = foreign_key.args.get("reference")
        if not isinstance(reference, exp.Reference):
            continue
        target_table, target_columns = reference_target(reference)
        relationships.extend(
            normalized_relationship(
                source_table,
                [identifier.name for identifier in foreign_key.expressions],
                target_table,
                target_columns,
                tables,
            )
        )
    return relationships


def extract_relationships(
    text: str,
    table_definitions: list[BenchmarkTable],
) -> list[dict[str, str]]:
    tables = table_lookup(table_definitions)
    relationships: list[dict[str, str]] = []
    for table in table_definitions:
        relationships.extend(
            relationships_from_expression(table.expression, table.source_name, tables)
        )
    for batch in re.split(r"(?im)^\s*GO\s*$", text):
        if not re.match(r"(?is)^\s*ALTER\s+TABLE", batch) or "FOREIGN KEY" not in batch.upper():
            continue
        prepared = re.sub(r"(?i)\bWITH\s+NOCHECK\b", "", batch)
        try:
            expression = sqlglot.parse_one(prepared, read="tsql")
        except (ParseError, TokenError) as error:
            raise ValueError(f"Unable to parse foreign-key ALTER TABLE: {error}") from error
        if not isinstance(expression, exp.Alter) or not isinstance(expression.this, exp.Table):
            raise ValueError("Only parsed ALTER TABLE foreign keys are accepted.")
        relationships.extend(
            relationships_from_expression(expression, expression.this.name, tables)
        )
    unique = {
        (
            row["source_table"],
            row["source_column"],
            row["target_table"],
            row["target_column"],
        ): row
        for row in relationships
    }
    return [unique[key] for key in sorted(unique)]


def create_table_sql(table: BenchmarkTable) -> str:
    columns = ", ".join(
        f"{quote_identifier(column.name)} {column.duckdb_type}"
        for column in table.columns
    )
    return f"CREATE TABLE {quote_identifier(table.name)} ({columns})"


def existing_result(
    source_path: Path,
    dataset: str,
    output_dir: Path,
) -> BenchmarkSqlConversionResult | None:
    manifest_path = output_dir / MANIFEST_NAME
    if not output_dir.exists():
        return None
    if not manifest_path.is_file():
        raise ValueError(f"Existing conversion output is incomplete: {output_dir}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if (
        manifest.get("status") != "ready_for_local_benchmark"
        or manifest.get("dataset") != dataset
        or manifest.get("conversion", {}).get("converter_version")
        != CONVERTER_VERSION
        or manifest.get("source", {}).get("sha256") != file_sha256(source_path)
    ):
        raise ValueError(
            f"Different benchmark conversion outputs already exist in {output_dir}. "
            "Use a new output directory; existing derived data was not overwritten."
        )
    artifacts = manifest.get("artifacts", {})
    expected_files = [artifacts.get("database", {})]
    expected_files.extend(artifacts.get("parquet", []))
    expected_files.extend(
        [artifacts.get("relationships", {}), artifacts.get("report", {})]
    )
    for artifact in expected_files:
        if not isinstance(artifact, dict):
            raise ValueError("Existing benchmark manifest has an invalid artifact entry.")
        path = output_dir / str(artifact.get("path", ""))
        if not path.is_file() or file_sha256(path) != artifact.get("sha256"):
            raise ValueError("Existing benchmark artifacts do not match their manifest hashes.")
    counts = manifest["counts"]
    return BenchmarkSqlConversionResult(
        output_dir=output_dir,
        status=manifest["status"],
        database_path=output_dir / artifacts["database"]["path"],
        manifest_path=manifest_path,
        relationships_path=output_dir / artifacts["relationships"]["path"],
        report_path=output_dir / artifacts["report"]["path"],
        table_count=counts["tables"],
        row_count=counts["rows"],
        relationship_count=counts["relationship_candidates"],
        outputs_changed=False,
    )


def render_report(
    dataset: str,
    table_rows: list[dict[str, Any]],
    relationship_count: int,
    replacement_characters: int,
) -> str:
    lines = [
        f"# {dataset} Benchmark Conversion Report",
        "",
        "- Status: `ready_for_local_benchmark`",
        f"- Tables: {len(table_rows)}",
        f"- Rows: {sum(row['rows'] for row in table_rows)}",
        f"- Source-declared relationship candidates: {relationship_count}",
        f"- Source replacement characters preserved: {replacement_characters}",
        "",
        "## Tables",
        "",
    ]
    lines.extend(f"- `{row['name']}`: {row['rows']} rows" for row in table_rows)
    lines.extend(
        [
            "",
            "## Conversion Boundary",
            "",
            "- Only parsed CREATE TABLE definitions and INSERT rows were materialized.",
            "- DROP, ALTER execution, procedures, views, triggers, credentials,",
            "  and external operations were ignored.",
            "- Constraints were captured as relationship candidates but were not",
            "  enforced in derived tables.",
            "- The source SQL file was not modified.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_benchmark_sql_conversion(
    source_path: Path,
    dataset_name: str,
    output_dir: Path,
) -> BenchmarkSqlConversionResult:
    if not source_path.is_file() or source_path.suffix.lower() != ".sql":
        raise ValueError("Benchmark SQL conversion requires an existing local .sql file.")
    dataset = slugify(dataset_name)
    existing = existing_result(source_path, dataset, output_dir)
    if existing:
        return existing

    text, encoding = read_source(source_path)
    table_definitions = parse_tables(text)
    tables = table_lookup(table_definitions)
    inserts = extract_insert_statements(text)
    relationships = extract_relationships(text, table_definitions)
    staging_dir = output_dir.with_name(f"{output_dir.name}.building")
    if staging_dir.exists():
        raise ValueError(f"Stale benchmark conversion staging directory exists: {staging_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir()
    database_name = f"{dataset}.duckdb"
    database_path = staging_dir / database_name
    parquet_dir = staging_dir / "parquet"
    parquet_dir.mkdir()

    try:
        with duckdb.connect(str(database_path)) as connection:
            for table in table_definitions:
                connection.execute(create_table_sql(table))
            identity_counters = {
                (table.source_name.casefold(), column.source_name.casefold()): int(
                    column.identity_start or 1
                )
                for table in table_definitions
                for column in table.columns
                if column.identity
            }
            connection.execute("BEGIN TRANSACTION")
            for statement in inserts:
                connection.execute(
                    transform_insert(statement, tables, identity_counters)
                )
            connection.execute("COMMIT")
            table_rows = []
            for table in sorted(table_definitions, key=lambda item: item.name):
                rows = connection.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(table.name)}"  # noqa: S608 - identifier via quote_identifier; no user values in statement
                ).fetchone()[0]
                parquet_path = parquet_dir / f"{table.name}.parquet"
                connection.execute(
                    f"COPY {quote_identifier(table.name)} TO ? "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)",
                    [str(parquet_path)],
                )
                table_rows.append(
                    {
                        "source_name": table.source_name,
                        "name": table.name,
                        "rows": int(rows),
                        "columns": [
                            {
                                "source_name": column.source_name,
                                "name": column.name,
                                "source_type": column.source_type,
                                "duckdb_type": column.duckdb_type,
                                "identity": column.identity,
                                "identity_start": column.identity_start,
                                "identity_increment": column.identity_increment,
                            }
                            for column in table.columns
                        ],
                    }
                )

        relationships_path = staging_dir / RELATIONSHIPS_NAME
        relationships_path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "status": "pending_review",
                    "relationship_candidates": relationships,
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        replacement_characters = text.count("\ufffd")
        report_path = staging_dir / REPORT_NAME
        report_path.write_text(
            render_report(dataset, table_rows, len(relationships), replacement_characters),
            encoding="utf-8",
        )
        parquet_artifacts = [
            {
                "table": row["name"],
                "path": f"parquet/{row['name']}.parquet",
                "rows": row["rows"],
                "sha256": file_sha256(parquet_dir / f"{row['name']}.parquet"),
            }
            for row in table_rows
        ]
        manifest = {
            "version": 1,
            "status": "ready_for_local_benchmark",
            "dataset": dataset,
            "source": {
                "filename": source_path.name,
                "sha256": file_sha256(source_path),
                "encoding": encoding,
                "replacement_characters": replacement_characters,
                "create_table_statements": len(table_definitions),
                "insert_statements": len(inserts),
            },
            "conversion": {
                "converter_version": CONVERTER_VERSION,
                "parser": "sqlglot",
                "parser_version": sqlglot.__version__,
                "source_dialect": "tsql",
                "target_engine": "duckdb",
                "parquet_compression": "zstd",
                "materialized_statements": ["create_table_columns", "insert_rows"],
                "ignored_statement_classes": [
                    "drop",
                    "alter_execution",
                    "view",
                    "procedure",
                    "trigger",
                    "credential",
                    "external_operation",
                ],
            },
            "counts": {
                "tables": len(table_rows),
                "rows": sum(row["rows"] for row in table_rows),
                "relationship_candidates": len(relationships),
            },
            "tables": table_rows,
            "artifacts": {
                "database": {
                    "path": database_name,
                    "sha256": file_sha256(database_path),
                },
                "parquet": parquet_artifacts,
                "relationships": {
                    "path": RELATIONSHIPS_NAME,
                    "sha256": file_sha256(relationships_path),
                },
                "report": {
                    "path": REPORT_NAME,
                    "sha256": file_sha256(report_path),
                },
            },
            "approval": {
                "benchmark_use_approved": False,
                "relationship_candidates_approved": False,
                "model_training_approved": False,
                "external_upload_approved": False,
            },
        }
        manifest_path = staging_dir / MANIFEST_NAME
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        staging_dir.rename(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return BenchmarkSqlConversionResult(
        output_dir=output_dir,
        status="ready_for_local_benchmark",
        database_path=output_dir / database_name,
        manifest_path=output_dir / MANIFEST_NAME,
        relationships_path=output_dir / RELATIONSHIPS_NAME,
        report_path=output_dir / REPORT_NAME,
        table_count=len(table_rows),
        row_count=sum(row["rows"] for row in table_rows),
        relationship_count=len(relationships),
        outputs_changed=True,
    )
