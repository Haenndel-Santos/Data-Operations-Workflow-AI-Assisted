from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from .source_onboarding import ensure_dir, file_sha256


PLAN_NAME = "analytics_query_plan.yml"
BLOCKERS_NAME = "analytics_query_blockers.csv"
REPORT_NAME = "analytics_query_report.md"
OUTPUT_NAMES = {PLAN_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_JOINS = 8
MAX_DIMENSIONS = 64
MAX_METRICS = 64
MAX_FILTERS = 64
MAX_IN_VALUES = 1_000
MAX_ORDER_RULES = 64
MAX_LIMIT = 10_000
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
ALLOWED_TOP_LEVEL_FIELDS = {
    "version",
    "question",
    "from",
    "dimensions",
    "metrics",
    "joins",
    "filters",
    "order_by",
    "limit",
}
ALLOWED_AGGREGATES = {"count", "count_distinct", "sum", "avg", "min", "max"}
ALLOWED_FILTERS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "is_null", "not_null"}
FILTER_SQL = {
    "eq": "=",
    "ne": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


@dataclass(frozen=True)
class CompiledAnalyticsQuery:
    sql: str
    parameters: tuple[Any, ...]
    parameter_types: tuple[str, ...]


@dataclass(frozen=True)
class AnalyticsQueryPlanResult:
    output_dir: Path
    status: str
    plan_path: Path
    blockers_path: Path
    report_path: Path
    blocker_count: int
    outputs_changed: bool
    compiled: CompiledAnalyticsQuery | None


def add_blocker(
    blockers: list[dict[str, str]],
    blocker_type: str,
    explanation: str,
    *,
    field: str = "",
) -> None:
    blockers.append(
        {
            "blocker_id": f"BLOCKER_{len(blockers) + 1:03d}",
            "blocker_type": blocker_type,
            "field": field,
            "explanation": explanation,
        }
    )


def read_yaml_mapping(
    path: Path,
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(
            blockers,
            "required_input_missing",
            "A required local YAML input is missing.",
            field=field,
        )
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        add_blocker(
            blockers,
            "invalid_yaml",
            "The required local input is not valid UTF-8 YAML.",
            field=field,
        )
        return {}
    if not isinstance(payload, dict):
        add_blocker(
            blockers,
            "invalid_yaml_mapping",
            "The required local YAML input must contain a mapping.",
            field=field,
        )
        return {}
    return payload


def load_catalog(
    database_path: Path,
    blockers: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    if not database_path.is_file():
        add_blocker(
            blockers,
            "database_missing",
            "The local DuckDB database file does not exist.",
            field="database",
        )
        return {}
    try:
        with duckdb.connect(str(database_path), read_only=True) as connection:
            rows = connection.execute(
                """
                select table_name, column_name, data_type
                from information_schema.columns
                where table_schema = 'main'
                order by table_name, ordinal_position
                """
            ).fetchall()
    except duckdb.Error:
        add_blocker(
            blockers,
            "database_unreadable",
            "The local DuckDB database could not be opened in read-only mode.",
            field="database",
        )
        return {}
    catalog: dict[str, list[dict[str, str]]] = {}
    for table_name, column_name, data_type in rows:
        catalog.setdefault(str(table_name), []).append(
            {"name": str(column_name), "type": str(data_type)}
        )
    if not catalog:
        add_blocker(
            blockers,
            "database_catalog_empty",
            "The local DuckDB database contains no queryable tables in the main schema.",
            field="database",
        )
    return catalog


def casefold_lookup(values: list[str]) -> dict[str, str | None]:
    lookup: dict[str, str | None] = {}
    for value in values:
        key = value.casefold()
        lookup[key] = value if key not in lookup else None
    return lookup


def resolve_table(
    value: Any,
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
    field: str,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        add_blocker(blockers, "invalid_table", "A table name is required.", field=field)
        return None
    lookup = casefold_lookup(list(catalog))
    resolved = lookup.get(value.strip().casefold())
    if not resolved:
        add_blocker(
            blockers,
            "unknown_table",
            "The requested table is not present unambiguously in the local catalog.",
            field=field,
        )
        return None
    return resolved


def resolve_column(
    reference: Any,
    base_table: str,
    selected_tables: list[str],
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
    field: str,
) -> tuple[str, str] | None:
    if not isinstance(reference, str) or not reference.strip():
        add_blocker(blockers, "invalid_column", "A column reference is required.", field=field)
        return None
    value = reference.strip()
    if "." in value:
        table_value, column_value = value.split(".", 1)
        table_lookup = casefold_lookup(selected_tables)
        table = table_lookup.get(table_value.casefold())
        if not table:
            add_blocker(
                blockers,
                "column_table_not_selected",
                "The qualified column refers to a table not selected by this request.",
                field=field,
            )
            return None
    else:
        table = base_table
        column_value = value
    column_lookup = casefold_lookup([column["name"] for column in catalog.get(table, [])])
    column = column_lookup.get(column_value.casefold())
    if not column:
        add_blocker(
            blockers,
            "unknown_column",
            "The requested column is not present unambiguously in the local catalog.",
            field=field,
        )
        return None
    return table, column


def quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def quote_column(reference: tuple[str, str]) -> str:
    return f"{quote_identifier(reference[0])}.{quote_identifier(reference[1])}"


def valid_alias(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> str | None:
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        add_blocker(
            blockers,
            "invalid_output_alias",
            "Output aliases must be simple identifiers of at most 63 characters.",
            field=field,
        )
        return None
    return value


def approved_relationships(
    payload: dict[str, Any],
    blockers: list[dict[str, str]],
) -> set[tuple[str, str, str, str]]:
    rows = payload.get("approved_relationships", [])
    if not isinstance(rows, list):
        add_blocker(
            blockers,
            "invalid_relationship_registry",
            "The approved relationship registry must contain a list.",
            field="relationships",
        )
        return set()
    approved: set[tuple[str, str, str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_approved_relationship",
                "Every approved relationship must be a mapping with four identifiers.",
                field=f"relationships[{index}]",
            )
            continue
        values = (
            row.get("source_table"),
            row.get("source_column"),
            row.get("target_table"),
            row.get("target_column"),
        )
        if all(isinstance(value, str) and value for value in values):
            approved.add(tuple(value.casefold() for value in values))
        else:
            add_blocker(
                blockers,
                "invalid_approved_relationship",
                "Every approved relationship must be a mapping with four identifiers.",
                field=f"relationships[{index}]",
            )
    return approved


def relationship_is_approved(
    relationships: set[tuple[str, str, str, str]],
    source_table: str,
    source_column: str,
    target_table: str,
    target_column: str,
) -> bool:
    direct = tuple(
        value.casefold()
        for value in (source_table, source_column, target_table, target_column)
    )
    reverse = (direct[2], direct[3], direct[0], direct[1])
    return direct in relationships or reverse in relationships


def scalar_parameter_type(value: Any) -> str | None:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    return None


def compile_request(
    request: dict[str, Any],
    catalog: dict[str, list[dict[str, str]]],
    relationships_payload: dict[str, Any],
    blockers: list[dict[str, str]],
) -> CompiledAnalyticsQuery | None:
    for key in request:
        if key not in ALLOWED_TOP_LEVEL_FIELDS:
            add_blocker(
                blockers,
                "unsupported_request_field",
                "The request contains a field outside the structured analytics contract.",
                field="request",
            )
    if request.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_request_version",
            "The analytics request must use contract version 1.",
            field="version",
        )

    base_table = resolve_table(request.get("from"), catalog, blockers, "from")
    if not base_table:
        return None
    selected_tables = [base_table]
    approved = approved_relationships(relationships_payload, blockers)
    join_sql: list[str] = []
    joins = request.get("joins", [])
    if not isinstance(joins, list):
        add_blocker(blockers, "invalid_joins", "Joins must be a list.", field="joins")
        joins = []
    if len(joins) > MAX_JOINS:
        add_blocker(
            blockers,
            "join_limit_exceeded",
            f"At most {MAX_JOINS} joins are allowed in one request.",
            field="joins",
        )
    for index, join in enumerate(joins[:MAX_JOINS]):
        field = f"joins[{index}]"
        if not isinstance(join, dict):
            add_blocker(blockers, "invalid_join", "Each join must be a mapping.", field=field)
            continue
        source_table = resolve_table(join.get("source_table"), catalog, blockers, field)
        target_table = resolve_table(join.get("target_table"), catalog, blockers, field)
        if not source_table or not target_table:
            continue
        if source_table not in selected_tables or target_table in selected_tables:
            add_blocker(
                blockers,
                "invalid_join_order",
                "Each join must connect a selected source table to one new target table.",
                field=field,
            )
            continue
        source_ref = resolve_column(
            f"{source_table}.{join.get('source_column', '')}",
            base_table,
            selected_tables,
            catalog,
            blockers,
            field,
        )
        target_ref = resolve_column(
            f"{target_table}.{join.get('target_column', '')}",
            base_table,
            [*selected_tables, target_table],
            catalog,
            blockers,
            field,
        )
        if not source_ref or not target_ref:
            continue
        if not relationship_is_approved(
            approved,
            source_table,
            source_ref[1],
            target_table,
            target_ref[1],
        ):
            add_blocker(
                blockers,
                "relationship_not_approved",
                "Cross-table analysis requires an explicitly approved relationship.",
                field=field,
            )
            continue
        kind = str(join.get("kind", "left")).lower()
        if kind not in {"left", "inner"}:
            add_blocker(
                blockers,
                "unsupported_join_kind",
                "Only left and inner joins are allowed.",
                field=field,
            )
            continue
        join_sql.append(
            f"{kind.upper()} JOIN {quote_identifier(target_table)} ON "
            f"{quote_column(source_ref)} = {quote_column(target_ref)}"
        )
        selected_tables.append(target_table)

    select_sql: list[str] = []
    group_sql: list[str] = []
    output_aliases: set[str] = set()
    dimensions = request.get("dimensions", [])
    if not isinstance(dimensions, list):
        add_blocker(
            blockers,
            "invalid_dimensions",
            "Dimensions must be a list.",
            field="dimensions",
        )
        dimensions = []
    if len(dimensions) > MAX_DIMENSIONS:
        add_blocker(
            blockers,
            "dimension_limit_exceeded",
            f"At most {MAX_DIMENSIONS} dimensions are allowed in one request.",
            field="dimensions",
        )
    for index, dimension in enumerate(dimensions[:MAX_DIMENSIONS]):
        field = f"dimensions[{index}]"
        if isinstance(dimension, str):
            reference_value = dimension
            alias_value = dimension.split(".")[-1]
        elif isinstance(dimension, dict):
            reference_value = dimension.get("column")
            alias_value = dimension.get("alias") or str(reference_value).split(".")[-1]
        else:
            add_blocker(
                blockers,
                "invalid_dimension",
                "Each dimension must be a column string or mapping.",
                field=field,
            )
            continue
        reference = resolve_column(
            reference_value,
            base_table,
            selected_tables,
            catalog,
            blockers,
            field,
        )
        alias = valid_alias(alias_value, blockers, field)
        if not reference or not alias:
            continue
        if alias.casefold() in output_aliases:
            add_blocker(
                blockers,
                "duplicate_output_alias",
                "Every selected field must have a unique output alias.",
                field=field,
            )
            continue
        output_aliases.add(alias.casefold())
        expression = quote_column(reference)
        select_sql.append(f"{expression} AS {quote_identifier(alias)}")
        group_sql.append(expression)

    metrics = request.get("metrics", [])
    if not isinstance(metrics, list):
        add_blocker(blockers, "invalid_metrics", "Metrics must be a list.", field="metrics")
        metrics = []
    if len(metrics) > MAX_METRICS:
        add_blocker(
            blockers,
            "metric_limit_exceeded",
            f"At most {MAX_METRICS} metrics are allowed in one request.",
            field="metrics",
        )
    for index, metric in enumerate(metrics[:MAX_METRICS]):
        field = f"metrics[{index}]"
        if not isinstance(metric, dict):
            add_blocker(blockers, "invalid_metric", "Each metric must be a mapping.", field=field)
            continue
        function = str(metric.get("function", "")).lower()
        if function not in ALLOWED_AGGREGATES:
            add_blocker(
                blockers,
                "unsupported_aggregate",
                "The requested aggregate is not allowlisted.",
                field=field,
            )
            continue
        column_value = metric.get("column", "*")
        if function == "count" and column_value == "*":
            aggregate_sql = "COUNT(*)"
            default_alias = "row_count"
        else:
            reference = resolve_column(
                column_value,
                base_table,
                selected_tables,
                catalog,
                blockers,
                field,
            )
            if not reference:
                continue
            quoted = quote_column(reference)
            aggregate_sql = (
                f"COUNT(DISTINCT {quoted})" if function == "count_distinct"
                else f"{function.upper()}({quoted})"
            )
            default_alias = f"{function}_{reference[1]}"
        alias = valid_alias(metric.get("alias") or default_alias, blockers, field)
        if not alias:
            continue
        if alias.casefold() in output_aliases:
            add_blocker(
                blockers,
                "duplicate_output_alias",
                "Every selected field must have a unique output alias.",
                field=field,
            )
            continue
        output_aliases.add(alias.casefold())
        select_sql.append(f"{aggregate_sql} AS {quote_identifier(alias)}")

    if not select_sql:
        add_blocker(
            blockers,
            "empty_selection",
            "At least one valid dimension or metric is required.",
            field="dimensions/metrics",
        )

    parameters: list[Any] = []
    parameter_types: list[str] = []
    where_sql: list[str] = []
    filters = request.get("filters", [])
    if not isinstance(filters, list):
        add_blocker(blockers, "invalid_filters", "Filters must be a list.", field="filters")
        filters = []
    if len(filters) > MAX_FILTERS:
        add_blocker(
            blockers,
            "filter_limit_exceeded",
            f"At most {MAX_FILTERS} filters are allowed in one request.",
            field="filters",
        )
    for index, filter_item in enumerate(filters[:MAX_FILTERS]):
        field = f"filters[{index}]"
        if not isinstance(filter_item, dict):
            add_blocker(blockers, "invalid_filter", "Each filter must be a mapping.", field=field)
            continue
        reference = resolve_column(
            filter_item.get("column"),
            base_table,
            selected_tables,
            catalog,
            blockers,
            field,
        )
        operator = str(filter_item.get("operator", "")).lower()
        if operator not in ALLOWED_FILTERS:
            add_blocker(
                blockers,
                "unsupported_filter_operator",
                "The requested filter operator is not allowlisted.",
                field=field,
            )
            continue
        if not reference:
            continue
        quoted = quote_column(reference)
        if operator in {"is_null", "not_null"}:
            where_sql.append(f"{quoted} IS {'NOT ' if operator == 'not_null' else ''}NULL")
            continue
        value = filter_item.get("value")
        if operator == "in":
            if not isinstance(value, list) or not value or len(value) > MAX_IN_VALUES:
                add_blocker(
                    blockers,
                    "invalid_in_filter",
                    f"IN filters require between 1 and {MAX_IN_VALUES} scalar values.",
                    field=field,
                )
                continue
            types = [scalar_parameter_type(item) for item in value]
            if any(item is None or item == "null" for item in types):
                add_blocker(
                    blockers,
                    "invalid_filter_value",
                    "Filter values must be scalar YAML values.",
                    field=field,
                )
                continue
            where_sql.append(f"{quoted} IN ({', '.join('?' for _ in value)})")
            parameters.extend(value)
            parameter_types.extend(item for item in types if item is not None)
            continue
        value_type = scalar_parameter_type(value)
        if value_type is None or value is None:
            add_blocker(
                blockers,
                "invalid_filter_value",
                "Comparison filters require a non-null scalar YAML value.",
                field=field,
            )
            continue
        where_sql.append(f"{quoted} {FILTER_SQL[operator]} ?")
        parameters.append(value)
        parameter_types.append(value_type)

    order_sql: list[str] = []
    order_by = request.get("order_by", [])
    if not isinstance(order_by, list):
        add_blocker(blockers, "invalid_order_by", "Order rules must be a list.", field="order_by")
        order_by = []
    if len(order_by) > MAX_ORDER_RULES:
        add_blocker(
            blockers,
            "order_limit_exceeded",
            f"At most {MAX_ORDER_RULES} order rules are allowed in one request.",
            field="order_by",
        )
    for index, order in enumerate(order_by[:MAX_ORDER_RULES]):
        field = f"order_by[{index}]"
        if not isinstance(order, dict):
            add_blocker(
                blockers,
                "invalid_order_rule",
                "Each order rule must be a mapping.",
                field=field,
            )
            continue
        alias = valid_alias(order.get("field"), blockers, field)
        direction = str(order.get("direction", "asc")).lower()
        if direction not in {"asc", "desc"}:
            add_blocker(
                blockers,
                "invalid_order_direction",
                "Order direction must be asc or desc.",
                field=field,
            )
            continue
        if not alias:
            continue
        if alias.casefold() not in output_aliases:
            add_blocker(
                blockers,
                "unknown_order_field",
                "Order fields must reference a selected output alias.",
                field=field,
            )
            continue
        order_sql.append(f"{quote_identifier(alias)} {direction.upper()}")

    limit = request.get("limit", 1_000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        add_blocker(
            blockers,
            "invalid_limit",
            f"Limit must be an integer between 1 and {MAX_LIMIT}.",
            field="limit",
        )
        limit = 1_000

    if blockers:
        return None
    lines = ["SELECT", "  " + ",\n  ".join(select_sql), f"FROM {quote_identifier(base_table)}"]
    lines.extend(join_sql)
    if where_sql:
        lines.append("WHERE " + "\n  AND ".join(where_sql))
    if group_sql:
        lines.append("GROUP BY " + ", ".join(group_sql))
    if order_sql:
        lines.append("ORDER BY " + ", ".join(order_sql))
    lines.append(f"LIMIT {limit}")
    return CompiledAnalyticsQuery(
        sql="\n".join(lines) + ";",
        parameters=tuple(parameters),
        parameter_types=tuple(parameter_types),
    )


def catalog_digest(catalog: dict[str, list[dict[str, str]]]) -> str:
    payload = json.dumps(catalog, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_plan(
    request_path: Path,
    database_path: Path,
    relationships_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], CompiledAnalyticsQuery | None]:
    blockers: list[dict[str, str]] = []
    request = read_yaml_mapping(request_path, blockers, "request")
    relationships = read_yaml_mapping(relationships_path, blockers, "relationships")
    catalog = load_catalog(database_path, blockers)
    compiled = compile_request(request, catalog, relationships, blockers) if catalog else None
    database_stat = database_path.stat() if database_path.is_file() else None
    status = (
        "ready_for_execution_review"
        if compiled is not None and not blockers
        else "blocked"
    )
    plan = {
        "version": 1,
        "status": status,
        "source": {
            "request_sha256": file_sha256(request_path) if request_path.is_file() else "",
            "relationships_sha256": (
                file_sha256(relationships_path) if relationships_path.is_file() else ""
            ),
            "catalog_sha256": catalog_digest(catalog) if catalog else "",
            "database_size_bytes": database_stat.st_size if database_stat else 0,
            "database_modified_ns": database_stat.st_mtime_ns if database_stat else 0,
        },
        "catalog": {
            "tables": len(catalog),
            "columns": sum(len(columns) for columns in catalog.values()),
        },
        "query": {
            "sql": compiled.sql if compiled else "",
            "parameter_count": len(compiled.parameters) if compiled else 0,
            "parameter_types": list(compiled.parameter_types) if compiled else [],
            "parameter_values_included": False,
        },
        "approval": {
            "execution_authorized": False,
            "read_only_required": True,
            "ai_generated_sql_accepted": False,
            "requires_execution_review": True,
        },
        "blockers": blockers,
    }
    return plan, blockers, compiled


def csv_content(rows: list[dict[str, str]]) -> str:
    columns = ["blocker_id", "blocker_type", "field", "explanation"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def render_report(plan: dict[str, Any]) -> str:
    lines = [
        "# Analytics Query Plan Report",
        "",
        f"- Status: `{plan['status']}`",
        f"- Catalog tables: {plan['catalog']['tables']}",
        f"- Catalog columns: {plan['catalog']['columns']}",
        f"- Parameters: {plan['query']['parameter_count']}",
        f"- Blockers: {len(plan['blockers'])}",
        "",
        "## Safety Boundary",
        "",
        "- This command plans a structured analytical query; it does not execute SQL.",
        "- Raw SQL from a user or AI is not accepted by the contract.",
        "- Filter values are represented by placeholders and are not copied to outputs.",
        "- Cross-table joins require an explicitly approved relationship.",
        "- Database access is local and read-only.",
        "",
        "## Blockers",
        "",
    ]
    if plan["blockers"]:
        lines.extend(
            f"- `{row['blocker_id']}` `{row['blocker_type']}`: "
            f"field=`{row['field'] or 'not_available'}`"
            for row in plan["blockers"]
        )
    else:
        lines.append("- No query-planning blockers found.")
    return "\n".join(lines) + "\n"


def plan_content(plan: dict[str, Any]) -> str:
    return yaml.safe_dump(plan, sort_keys=False, allow_unicode=False)


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    existing = (
        {
            path.name: path
            for path in output_dir.iterdir()
            if path.is_file() and path.name in OUTPUT_NAMES
        }
        if output_dir.exists()
        else {}
    )
    if existing:
        exact = set(existing) == set(contents) and all(
            existing[name].read_text(encoding="utf-8") == content
            for name, content in contents.items()
        )
        if exact:
            return False
        raise ValueError(
            f"Different analytics query-plan outputs already exist in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_query_plan(
    request_path: Path,
    database_path: Path,
    relationships_path: Path,
    output_dir: Path,
) -> AnalyticsQueryPlanResult:
    plan, blockers, compiled = build_plan(request_path, database_path, relationships_path)
    contents = {
        PLAN_NAME: plan_content(plan),
        BLOCKERS_NAME: csv_content(blockers),
        REPORT_NAME: render_report(plan),
    }
    outputs_changed = write_outputs(output_dir, contents)
    return AnalyticsQueryPlanResult(
        output_dir=output_dir,
        status=plan["status"],
        plan_path=output_dir / PLAN_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        blocker_count=len(blockers),
        outputs_changed=outputs_changed,
        compiled=compiled,
    )
