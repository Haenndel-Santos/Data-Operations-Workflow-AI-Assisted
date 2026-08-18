from __future__ import annotations

import csv
import io
import math
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb
import yaml

from .analytics_nl_translation import (
    MAX_PROVIDER_RESPONSE_BYTES,
    RecordedSemanticIntentProvider,
    run_analytics_nl_translation,
    validate_provider_response,
)
from .analytics_query_execution import AnalyticsExecutionLimits, run_analytics_query_execution
from .analytics_query_plan import (
    ALLOWED_TOP_LEVEL_FIELDS,
    add_blocker,
    quote_identifier,
    read_yaml_mapping,
    run_analytics_query_plan,
)
from .analytics_semantic_adapter import MAX_QUESTION_LENGTH, validate_approved_state
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_answer_evaluation.yml"
CASES_NAME = "analytics_answer_evaluation_cases.csv"
BLOCKERS_NAME = "analytics_answer_evaluation_blockers.csv"
REPORT_NAME = "analytics_answer_evaluation_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, CASES_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_PACK_FILE_BYTES = 2_000_000
MAX_CASES = 50
MAX_TABLES = 8
MAX_COLUMNS_PER_TABLE = 64
MAX_RELATIONSHIPS = 64
MAX_SYNTHETIC_ROWS = 1_000
MAX_EXPECTED_ROWS = 10_000
MAX_CELL_TEXT_LENGTH = 4_000
IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
REQUIRED_CATEGORIES = {
    "approved_join",
    "grouped_aggregate",
    "filtered_aggregate",
    "no_rows",
    "null_filter",
}
EXPECTED_CATEGORY_STATUS = {
    "approved_join": "completed",
    "grouped_aggregate": "completed",
    "filtered_aggregate": "completed",
    "no_rows": "completed_no_rows",
    "null_filter": "completed",
}
TYPE_SQL = {
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "varchar": "VARCHAR",
    "boolean": "BOOLEAN",
    "decimal_18_2": "DECIMAL(18, 2)",
}
EVALUATION_LIMITS = AnalyticsExecutionLimits(
    max_rows=1_000,
    max_result_bytes=1_000_000,
    max_runtime_seconds=10,
    memory_limit_mb=128,
    threads=1,
    max_temp_mb=64,
)


@dataclass(frozen=True)
class AnalyticsAnswerEvaluationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    cases_path: Path
    blockers_path: Path
    report_path: Path
    case_count: int
    passed_count: int
    failed_count: int
    blocker_count: int
    outputs_changed: bool


def _valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER_PATTERN.fullmatch(value))


def _reject_unknown_fields(
    payload: dict[str, Any],
    allowed: set[str],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    for key in payload:
        if key not in allowed:
            add_blocker(
                blockers,
                "unsupported_answer_evaluation_field",
                "The answer evaluation pack contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def _valid_typed_value(value: Any, type_name: str, nullable: bool) -> bool:
    if value is None:
        return nullable
    if type_name in {"integer", "bigint"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "double":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
    if type_name == "varchar":
        return isinstance(value, str) and len(value) <= MAX_CELL_TEXT_LENGTH
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "decimal_18_2":
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return False
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
            return False
        return decimal_value.is_finite() and decimal_value.as_tuple().exponent >= -2
    return False


def _validate_dataset(
    dataset: Any,
    blockers: list[dict[str, str]],
) -> dict[str, set[str]]:
    if not isinstance(dataset, dict):
        add_blocker(
            blockers,
            "invalid_synthetic_dataset",
            "The answer pack requires one structured synthetic dataset mapping.",
            field="pack.dataset",
        )
        return {}
    _reject_unknown_fields(dataset, {"tables"}, blockers, "pack.dataset")
    tables = dataset.get("tables")
    if not isinstance(tables, list) or not 1 <= len(tables) <= MAX_TABLES:
        add_blocker(
            blockers,
            "invalid_synthetic_tables",
            f"The synthetic dataset requires between 1 and {MAX_TABLES} tables.",
            field="pack.dataset.tables",
        )
        return {}

    catalog: dict[str, set[str]] = {}
    total_rows = 0
    for table_index, table in enumerate(tables):
        field = f"pack.dataset.tables[{table_index}]"
        if not isinstance(table, dict):
            add_blocker(
                blockers,
                "invalid_synthetic_table",
                "Every synthetic table must be a mapping.",
                field=field,
            )
            continue
        _reject_unknown_fields(table, {"name", "columns", "rows"}, blockers, field)
        name = table.get("name")
        if not _valid_identifier(name):
            add_blocker(
                blockers,
                "invalid_synthetic_table_name",
                "Synthetic table names must be lowercase simple identifiers.",
                field=f"{field}.name",
            )
            continue
        if name in catalog:
            add_blocker(
                blockers,
                "duplicate_synthetic_table",
                "Synthetic table names must be unique.",
                field=f"{field}.name",
            )
            continue

        columns = table.get("columns")
        if not isinstance(columns, list) or not 1 <= len(columns) <= MAX_COLUMNS_PER_TABLE:
            add_blocker(
                blockers,
                "invalid_synthetic_columns",
                f"Each table requires between 1 and {MAX_COLUMNS_PER_TABLE} columns.",
                field=f"{field}.columns",
            )
            continue
        column_names: set[str] = set()
        column_contracts: list[tuple[str, bool]] = []
        for column_index, column in enumerate(columns):
            column_field = f"{field}.columns[{column_index}]"
            if not isinstance(column, dict):
                add_blocker(
                    blockers,
                    "invalid_synthetic_column",
                    "Every synthetic column must be a mapping.",
                    field=column_field,
                )
                column_contracts.append(("", False))
                continue
            _reject_unknown_fields(
                column,
                {"name", "type", "nullable"},
                blockers,
                column_field,
            )
            column_name = column.get("name")
            type_name = column.get("type")
            nullable = column.get("nullable")
            if not _valid_identifier(column_name):
                add_blocker(
                    blockers,
                    "invalid_synthetic_column_name",
                    "Synthetic column names must be lowercase simple identifiers.",
                    field=f"{column_field}.name",
                )
            elif column_name in column_names:
                add_blocker(
                    blockers,
                    "duplicate_synthetic_column",
                    "Synthetic column names must be unique within a table.",
                    field=f"{column_field}.name",
                )
            else:
                column_names.add(column_name)
            if type_name not in TYPE_SQL:
                add_blocker(
                    blockers,
                    "unsupported_synthetic_type",
                    "Synthetic columns must use a version-1 allowlisted type.",
                    field=f"{column_field}.type",
                )
            if not isinstance(nullable, bool):
                add_blocker(
                    blockers,
                    "invalid_synthetic_nullability",
                    "Synthetic column nullable must be true or false.",
                    field=f"{column_field}.nullable",
                )
            column_contracts.append((str(type_name), bool(nullable)))

        rows = table.get("rows")
        if not isinstance(rows, list):
            add_blocker(
                blockers,
                "invalid_synthetic_rows",
                "Synthetic table rows must be a list.",
                field=f"{field}.rows",
            )
            rows = []
        total_rows += len(rows)
        for row_index, row in enumerate(rows):
            row_field = f"{field}.rows[{row_index}]"
            if not isinstance(row, list) or len(row) != len(columns):
                add_blocker(
                    blockers,
                    "invalid_synthetic_row",
                    "Every synthetic row must contain exactly one value per column.",
                    field=row_field,
                )
                continue
            for value_index, value in enumerate(row):
                type_name, nullable = column_contracts[value_index]
                if not _valid_typed_value(value, type_name, nullable):
                    add_blocker(
                        blockers,
                        "invalid_synthetic_value",
                        "Synthetic values must match the declared allowlisted type and nullability.",
                        field=f"{row_field}[{value_index}]",
                    )
        catalog[name] = column_names

    if total_rows > MAX_SYNTHETIC_ROWS:
        add_blocker(
            blockers,
            "synthetic_row_limit_exceeded",
            f"The synthetic dataset may contain at most {MAX_SYNTHETIC_ROWS} rows.",
            field="pack.dataset.tables",
        )
    return catalog


def _validate_relationships(
    relationships: Any,
    catalog: dict[str, set[str]],
    blockers: list[dict[str, str]],
) -> None:
    if not isinstance(relationships, list) or len(relationships) > MAX_RELATIONSHIPS:
        add_blocker(
            blockers,
            "invalid_synthetic_relationships",
            f"Synthetic approved relationships must be a list of at most {MAX_RELATIONSHIPS} rows.",
            field="pack.approved_relationships",
        )
        return
    seen: set[tuple[str, str, str, str]] = set()
    for index, row in enumerate(relationships):
        field = f"pack.approved_relationships[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_synthetic_relationship",
                "Every synthetic relationship must be a mapping.",
                field=field,
            )
            continue
        allowed = {"source_table", "source_column", "target_table", "target_column"}
        _reject_unknown_fields(row, allowed, blockers, field)
        values = tuple(row.get(key) for key in sorted(allowed))
        source_table = row.get("source_table")
        source_column = row.get("source_column")
        target_table = row.get("target_table")
        target_column = row.get("target_column")
        if not all(_valid_identifier(value) for value in values):
            add_blocker(
                blockers,
                "invalid_synthetic_relationship",
                "Synthetic relationships require four lowercase identifiers.",
                field=field,
            )
            continue
        relationship = (source_table, source_column, target_table, target_column)
        if relationship in seen:
            add_blocker(
                blockers,
                "duplicate_synthetic_relationship",
                "Synthetic approved relationships must be unique.",
                field=field,
            )
        seen.add(relationship)
        if (
            source_table not in catalog
            or source_column not in catalog[source_table]
            or target_table not in catalog
            or target_column not in catalog[target_table]
        ):
            add_blocker(
                blockers,
                "unknown_synthetic_relationship_reference",
                "Synthetic relationships must resolve to declared tables and columns.",
                field=field,
            )


def _valid_expected_cell(value: Any) -> bool:
    return (
        value is None
        or isinstance(value, bool)
        or (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
        or (isinstance(value, str) and len(value) <= MAX_CELL_TEXT_LENGTH)
    )


def _validate_expected_result(
    expected: Any,
    category: str,
    expected_request: dict[str, Any],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    if not isinstance(expected, dict):
        add_blocker(
            blockers,
            "invalid_expected_answer",
            "Every answer case requires an expected result mapping.",
            field=field,
        )
        return
    _reject_unknown_fields(
        expected,
        {"status", "columns", "rows", "row_count", "column_count", "null_cells"},
        blockers,
        field,
    )
    status = expected.get("status")
    if status != EXPECTED_CATEGORY_STATUS.get(category):
        add_blocker(
            blockers,
            "answer_category_status_mismatch",
            "Each Stage 5E category must retain its governed execution status.",
            field=f"{field}.status",
        )
    columns = expected.get("columns")
    if (
        not isinstance(columns, list)
        or not columns
        or any(not _valid_identifier(column) for column in columns)
        or len(columns) != len(set(columns))
    ):
        add_blocker(
            blockers,
            "invalid_expected_columns",
            "Expected result columns must be a unique list of lowercase identifiers.",
            field=f"{field}.columns",
        )
        columns = []
    rows = expected.get("rows")
    if not isinstance(rows, list) or len(rows) > MAX_EXPECTED_ROWS:
        add_blocker(
            blockers,
            "invalid_expected_rows",
            f"Expected rows must be a list of at most {MAX_EXPECTED_ROWS} rows.",
            field=f"{field}.rows",
        )
        rows = []
    for row_index, row in enumerate(rows):
        if (
            not isinstance(row, list)
            or len(row) != len(columns)
            or any(not _valid_expected_cell(value) for value in row)
        ):
            add_blocker(
                blockers,
                "invalid_expected_row",
                "Expected rows must contain one bounded scalar or null per result column.",
                field=f"{field}.rows[{row_index}]",
            )
    expected_nulls = sum(value is None for row in rows if isinstance(row, list) for value in row)
    if expected.get("row_count") != len(rows):
        add_blocker(
            blockers,
            "expected_row_count_mismatch",
            "Expected row_count must match the number of expected rows.",
            field=f"{field}.row_count",
        )
    if expected.get("column_count") != len(columns):
        add_blocker(
            blockers,
            "expected_column_count_mismatch",
            "Expected column_count must match the number of expected columns.",
            field=f"{field}.column_count",
        )
    if expected.get("null_cells") != expected_nulls:
        add_blocker(
            blockers,
            "expected_null_count_mismatch",
            "Expected null_cells must match explicit null values in expected rows.",
            field=f"{field}.null_cells",
        )
    if status == "completed_no_rows" and rows:
        add_blocker(
            blockers,
            "no_row_expectation_mismatch",
            "A completed_no_rows case cannot contain expected rows.",
            field=f"{field}.rows",
        )
    if status == "completed" and not rows:
        add_blocker(
            blockers,
            "completed_answer_requires_rows",
            "A completed answer case requires at least one expected row.",
            field=f"{field}.rows",
        )
    if len(rows) > 1 and not expected_request.get("order_by"):
        add_blocker(
            blockers,
            "deterministic_order_required",
            "Multi-row exact answers require explicit order_by rules.",
            field="expected_request.order_by",
        )


def _validate_case(
    case: Any,
    index: int,
    seen_ids: set[str],
    categories: set[str],
    blockers: list[dict[str, str]],
) -> None:
    field = f"pack.cases[{index}]"
    if not isinstance(case, dict):
        add_blocker(
            blockers,
            "invalid_answer_case",
            "Every Stage 5E answer case must be a mapping.",
            field=field,
        )
        return
    _reject_unknown_fields(
        case,
        {"id", "category", "question", "provider_response", "expected_request", "expected_result"},
        blockers,
        field,
    )
    case_id = case.get("id")
    if not _valid_identifier(case_id):
        add_blocker(
            blockers,
            "invalid_answer_case_id",
            "Answer case IDs must be lowercase stable identifiers.",
            field=f"{field}.id",
        )
    elif case_id in seen_ids:
        add_blocker(
            blockers,
            "duplicate_answer_case_id",
            "Answer case IDs must be unique.",
            field=f"{field}.id",
        )
    else:
        seen_ids.add(case_id)
    category = case.get("category")
    if category not in REQUIRED_CATEGORIES:
        add_blocker(
            blockers,
            "invalid_answer_category",
            "Answer case category is outside the required version-1 set.",
            field=f"{field}.category",
        )
    else:
        categories.add(category)
    question = case.get("question")
    if not isinstance(question, str) or not question.strip() or len(question.strip()) > MAX_QUESTION_LENGTH:
        add_blocker(
            blockers,
            "invalid_answer_question",
            f"Each synthetic question must contain at most {MAX_QUESTION_LENGTH} characters.",
            field=f"{field}.question",
        )
    response = case.get("provider_response")
    response_blockers: list[dict[str, str]] = []
    validate_provider_response(response, response_blockers)
    if response_blockers:
        add_blocker(
            blockers,
            "invalid_answer_provider_response",
            "Stage 5E provider responses must satisfy the safe semantic response contract.",
            field=f"{field}.provider_response",
        )
    elif len(yaml.safe_dump(response).encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
        add_blocker(
            blockers,
            "answer_provider_response_too_large",
            "Stage 5E provider response exceeds the translation boundary limit.",
            field=f"{field}.provider_response",
        )
    expected_request = case.get("expected_request")
    if not isinstance(expected_request, dict):
        add_blocker(
            blockers,
            "invalid_expected_request",
            "Each answer case requires one exact expected Stage 5A request mapping.",
            field=f"{field}.expected_request",
        )
        expected_request = {}
    else:
        for key in expected_request:
            if key not in ALLOWED_TOP_LEVEL_FIELDS:
                add_blocker(
                    blockers,
                    "unsupported_expected_request_field",
                    "Expected requests must use only the Stage 5A version-1 contract.",
                    field=f"{field}.expected_request.{key}",
                )
        if expected_request.get("version") != 1:
            add_blocker(
                blockers,
                "invalid_expected_request_version",
                "Expected requests must use Stage 5A contract version 1.",
                field=f"{field}.expected_request.version",
            )
        if isinstance(question, str) and expected_request.get("question") != question.strip():
            add_blocker(
                blockers,
                "expected_question_mismatch",
                "The expected request must preserve the authoritative synthetic question.",
                field=f"{field}.expected_request.question",
            )
    if isinstance(category, str):
        _validate_expected_result(
            case.get("expected_result"),
            category,
            expected_request,
            blockers,
            f"{field}.expected_result",
        )


def validate_answer_pack(
    pack: dict[str, Any],
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    _reject_unknown_fields(
        pack,
        {"version", "pack_id", "description", "dataset", "approved_relationships", "cases"},
        blockers,
        "pack",
    )
    if isinstance(pack.get("version"), bool) or pack.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_answer_pack_version",
            "The Stage 5E answer pack must use version 1.",
            field="pack.version",
        )
    if not _valid_identifier(pack.get("pack_id")):
        add_blocker(
            blockers,
            "invalid_answer_pack_id",
            "The answer pack ID must be a lowercase stable identifier.",
            field="pack.pack_id",
        )
    if not isinstance(pack.get("description"), str) or not pack["description"].strip():
        add_blocker(
            blockers,
            "invalid_answer_pack_description",
            "The answer pack requires a non-empty description.",
            field="pack.description",
        )
    catalog = _validate_dataset(pack.get("dataset"), blockers)
    _validate_relationships(pack.get("approved_relationships"), catalog, blockers)
    cases = pack.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        add_blocker(
            blockers,
            "invalid_answer_cases",
            f"The answer pack requires between 1 and {MAX_CASES} cases.",
            field="pack.cases",
        )
        return []
    seen_ids: set[str] = set()
    categories: set[str] = set()
    for index, case in enumerate(cases):
        _validate_case(case, index, seen_ids, categories, blockers)
    if REQUIRED_CATEGORIES - categories:
        add_blocker(
            blockers,
            "answer_coverage_incomplete",
            "The pack must cover approved-join, grouped, filtered, no-row, and null-filter answers.",
            field="pack.cases",
        )
    return [case for case in cases if isinstance(case, dict)]


def _materialize_dataset(dataset: dict[str, Any], database_path: Path) -> None:
    with duckdb.connect(str(database_path)) as connection:
        for table in dataset["tables"]:
            definitions = []
            for column in table["columns"]:
                definition = f"{quote_identifier(column['name'])} {TYPE_SQL[column['type']]}"
                if not column["nullable"]:
                    definition += " NOT NULL"
                definitions.append(definition)
            connection.execute(
                f"CREATE TABLE {quote_identifier(table['name'])} ({', '.join(definitions)})"
            )
            if table["rows"]:
                placeholders = ", ".join("?" for _ in table["columns"])
                connection.executemany(
                    f"INSERT INTO {quote_identifier(table['name'])} VALUES ({placeholders})",  # noqa: S608 - identifier via quote_identifier; values bound via executemany
                    table["rows"],
                )


def _expected_csv(expected: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(expected["columns"])
    writer.writerows(expected["rows"])
    return buffer.getvalue()


def _case_row(
    case: dict[str, Any],
    semantic_state_path: Path,
    database_path: Path,
    relationships_path: Path,
    case_dir: Path,
) -> dict[str, Any]:
    question_path = case_dir / "question.txt"
    response_path = case_dir / "provider_response.yml"
    question_path.write_text(case["question"].strip() + "\n", encoding="utf-8", newline="")
    response_path.write_text(
        yaml.safe_dump(case["provider_response"], sort_keys=False, allow_unicode=False),
        encoding="utf-8",
        newline="",
    )
    translation = run_analytics_nl_translation(
        question_path,
        semantic_state_path,
        case_dir / "translation",
        RecordedSemanticIntentProvider(response_path),
    )
    translation_status = translation.status
    actual_request = translation.adapter_result.request if translation.adapter_result else None
    request_match = actual_request == case["expected_request"]
    planning_status = "not_run"
    execution_status = "not_run"
    result_match = False
    controls_match = False

    if translation_status == "ready_for_query_plan" and request_match:
        assert translation.adapter_result is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
        assert translation.adapter_result.request_path is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
        plan = run_analytics_query_plan(
            translation.adapter_result.request_path,
            database_path,
            relationships_path,
            case_dir / "plan",
        )
        planning_status = plan.status
        if planning_status == "ready_for_execution_review":
            execution = run_analytics_query_execution(
                translation.adapter_result.request_path,
                database_path,
                relationships_path,
                plan.plan_path,
                case_dir / "execution",
                EVALUATION_LIMITS,
            )
            execution_status = execution.status
            expected = case["expected_result"]
            if execution.result_path is not None:
                result_match = (
                    execution.result_path.read_text(encoding="utf-8") == _expected_csv(expected)
                )
            manifest = yaml.safe_load(execution.manifest_path.read_text(encoding="utf-8")) or {}
            result_controls = manifest.get("result", {})
            controls_match = all(
                (
                    result_controls.get("rows") == expected["row_count"],
                    result_controls.get("columns") == expected["column_count"],
                    result_controls.get("column_names") == expected["columns"],
                    result_controls.get("null_cells") == expected["null_cells"],
                    result_controls.get("no_rows")
                    == (expected["status"] == "completed_no_rows"),
                )
            )

    pipeline_match = (
        translation_status == "ready_for_query_plan"
        and request_match
        and planning_status == "ready_for_execution_review"
        and execution_status == case["expected_result"]["status"]
    )
    passed = pipeline_match and result_match and controls_match
    return {
        "case_id": case["id"],
        "category": case["category"],
        "translation_status": translation_status,
        "request_match": request_match,
        "planning_status": planning_status,
        "execution_status": execution_status,
        "pipeline_match": pipeline_match,
        "result_match": result_match,
        "controls_match": controls_match,
        "passed": passed,
    }


def _metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    passed = sum(bool(row[field]) for row in rows)
    count = len(rows)
    return {
        "passed": passed,
        "evaluated": count,
        "rate": round(passed / count, 6) if count else None,
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall": _metric(rows, "passed"),
        "pipeline_accuracy": _metric(rows, "pipeline_match"),
        "request_accuracy": _metric(rows, "request_match"),
        "result_exact_accuracy": _metric(rows, "result_match"),
        "control_accuracy": _metric(rows, "controls_match"),
    }


def _cases_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "case_id",
        "category",
        "translation_status",
        "request_match",
        "planning_status",
        "execution_status",
        "pipeline_match",
        "result_match",
        "controls_match",
        "passed",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["blocker_id", "blocker_type", "field", "explanation"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def _render_report(
    status: str,
    pack_id: str,
    rows: list[dict[str, Any]],
    blockers: list[dict[str, str]],
    metrics: dict[str, Any],
) -> str:
    lines = [
        "# Analytics Expected-Answer Evaluation Report",
        "",
        f"- Status: `{status}`",
        f"- Pack: `{pack_id or 'invalid'}`",
        f"- Cases: {len(rows)}",
        f"- Passed: {sum(bool(row['passed']) for row in rows)}",
        f"- Failed: {sum(not bool(row['passed']) for row in rows)}",
        f"- Contract blockers: {len(blockers)}",
        "",
        "## Metrics",
        "",
    ]
    for name, metric in metrics.items():
        rate = "not evaluated" if metric["rate"] is None else f"{metric['rate']:.6f}"
        lines.append(
            f"- {name.replace('_', ' ').title()}: {metric['passed']}/{metric['evaluated']} ({rate})"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- The versioned expected request is an exact synthetic execution gate.",
            "- Stage 5A builds the plan and Stage 5B revalidates it before read-only execution.",
            "- Database setup accepts structured allowlisted types and values, never source SQL.",
            "- Runtime questions, responses, requests, plans, databases, and results are temporary.",
            "- Persistent evaluation evidence omits the synthetic case content stored in the input pack.",
            "- No live model, network, external database, migration, import, or synchronization is used.",
            "- This synthetic pack is contract evidence, not real-dataset or live-model quality evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Answer evaluation output is not a directory: {output_dir}")
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
            f"Different answer evaluation evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_answer_evaluation(
    pack_path: Path,
    semantic_state_path: Path,
    output_dir: Path,
) -> AnalyticsAnswerEvaluationResult:
    blockers: list[dict[str, str]] = []
    if pack_path.is_file() and pack_path.stat().st_size > MAX_PACK_FILE_BYTES:
        add_blocker(
            blockers,
            "answer_pack_too_large",
            f"The Stage 5E answer pack must be at most {MAX_PACK_FILE_BYTES} bytes.",
            field="pack",
        )
        pack: dict[str, Any] = {}
    else:
        pack = read_yaml_mapping(pack_path, blockers, "answer_pack")
    cases = validate_answer_pack(pack, blockers) if pack else []
    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")
    validate_approved_state(state, blockers)

    rows: list[dict[str, Any]] = []
    if not blockers:
        with tempfile.TemporaryDirectory(prefix="dataops_answer_evaluation_") as temp_name:
            temp_dir = Path(temp_name)
            database_path = temp_dir / "synthetic.duckdb"
            relationships_path = temp_dir / "approved_relationships.yml"
            try:
                _materialize_dataset(pack["dataset"], database_path)
                relationships_path.write_text(
                    yaml.safe_dump(
                        {"approved_relationships": pack["approved_relationships"]},
                        sort_keys=False,
                        allow_unicode=False,
                    ),
                    encoding="utf-8",
                    newline="",
                )
            except (duckdb.Error, OSError, ValueError):
                add_blocker(
                    blockers,
                    "synthetic_dataset_materialization_failed",
                    "The validated synthetic dataset could not be materialized locally.",
                    field="pack.dataset",
                )
            if not blockers:
                for index, case in enumerate(cases):
                    case_dir = temp_dir / f"case_{index + 1:03d}"
                    case_dir.mkdir()
                    try:
                        rows.append(
                            _case_row(
                                case,
                                semantic_state_path,
                                database_path,
                                relationships_path,
                                case_dir,
                            )
                        )
                    except Exception:
                        rows.append(
                            {
                                "case_id": case["id"],
                                "category": case["category"],
                                "translation_status": "evaluation_error",
                                "request_match": False,
                                "planning_status": "not_run",
                                "execution_status": "not_run",
                                "pipeline_match": False,
                                "result_match": False,
                                "controls_match": False,
                                "passed": False,
                            }
                        )

    status = "blocked" if blockers else "passed" if all(row["passed"] for row in rows) else "failed"
    metrics = _metrics(rows)
    passed_count = sum(bool(row["passed"]) for row in rows)
    pack_id = pack.get("pack_id", "") if isinstance(pack, dict) else ""
    if not _valid_identifier(pack_id):
        pack_id = ""
    manifest = {
        "version": 1,
        "status": status,
        "pack_id": pack_id,
        "source": {
            "answer_pack_sha256": file_sha256(pack_path) if pack_path.is_file() else "",
            "approved_semantic_state_sha256": (
                file_sha256(semantic_state_path) if semantic_state_path.is_file() else ""
            ),
        },
        "controls": {
            "synthetic_database_temporary": True,
            "database_setup_sql_accepted": False,
            "expected_request_gate_required": True,
            "stage_5a_plan_required": True,
            "stage_5b_revalidation_required": True,
            "network_accessed": False,
            "model_api_used": False,
            "external_database_accessed": False,
            "case_content_persisted_in_evidence": False,
        },
        "execution_limits": {
            "max_rows": EVALUATION_LIMITS.max_rows,
            "max_result_bytes": EVALUATION_LIMITS.max_result_bytes,
            "max_runtime_seconds": EVALUATION_LIMITS.max_runtime_seconds,
            "memory_limit_mb": EVALUATION_LIMITS.memory_limit_mb,
            "threads": EVALUATION_LIMITS.threads,
            "max_temp_mb": EVALUATION_LIMITS.max_temp_mb,
        },
        "counts": {
            "cases": len(rows),
            "passed": passed_count,
            "failed": len(rows) - passed_count,
            "contract_blockers": len(blockers),
        },
        "metrics": metrics,
    }
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        CASES_NAME: _cases_csv(rows),
        BLOCKERS_NAME: _blockers_csv(blockers),
        REPORT_NAME: _render_report(status, pack_id, rows, blockers, metrics),
    }
    outputs_changed = _write_outputs(output_dir, contents)
    return AnalyticsAnswerEvaluationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        cases_path=output_dir / CASES_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        case_count=len(rows),
        passed_count=passed_count,
        failed_count=len(rows) - passed_count,
        blocker_count=len(blockers),
        outputs_changed=outputs_changed,
    )
