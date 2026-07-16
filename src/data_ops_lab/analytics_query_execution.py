from __future__ import annotations

import csv
import hashlib
import io
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Timer
from typing import Any

import duckdb
import yaml

from .analytics_query_plan import (
    MAX_LIMIT,
    CompiledAnalyticsQuery,
    build_plan,
    plan_content,
)
from .contracts.blockers import add_blocker
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_query_execution.yml"
BLOCKERS_NAME = "analytics_query_execution_blockers.csv"
REPORT_NAME = "analytics_query_execution_report.md"
RESULT_NAME = "analytics_query_result.csv"
OUTPUT_NAMES = {MANIFEST_NAME, BLOCKERS_NAME, REPORT_NAME, RESULT_NAME}
MAX_RESULT_BYTES = 50_000_000
MAX_RUNTIME_SECONDS = 300
MAX_MEMORY_MB = 8_192
MAX_THREADS = 16
MAX_TEMP_MB = 8_192
FETCH_BATCH_SIZE = 256


@dataclass(frozen=True)
class AnalyticsExecutionLimits:
    max_rows: int = MAX_LIMIT
    max_result_bytes: int = 10_000_000
    max_runtime_seconds: int = 30
    memory_limit_mb: int = 512
    threads: int = 2
    max_temp_mb: int = 1_024


@dataclass(frozen=True)
class AnalyticsQueryExecutionResult:
    output_dir: Path
    status: str
    manifest_path: Path
    blockers_path: Path
    report_path: Path
    result_path: Path | None
    blocker_count: int
    row_count: int
    outputs_changed: bool
    elapsed_seconds: float


class ExecutionLimitExceeded(Exception):
    def __init__(self, blocker_type: str, explanation: str) -> None:
        super().__init__(explanation)
        self.blocker_type = blocker_type
        self.explanation = explanation


def validate_limits(
    limits: AnalyticsExecutionLimits,
    blockers: list[dict[str, str]],
) -> None:
    ranges = (
        ("max_rows", limits.max_rows, 1, MAX_LIMIT),
        ("max_result_bytes", limits.max_result_bytes, 1_024, MAX_RESULT_BYTES),
        ("max_runtime_seconds", limits.max_runtime_seconds, 1, MAX_RUNTIME_SECONDS),
        ("memory_limit_mb", limits.memory_limit_mb, 64, MAX_MEMORY_MB),
        ("threads", limits.threads, 1, MAX_THREADS),
        ("max_temp_mb", limits.max_temp_mb, 64, MAX_TEMP_MB),
    )
    for field, value, minimum, maximum in ranges:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            add_blocker(
                blockers,
                "invalid_execution_limit",
                f"{field} must be an integer between {minimum} and {maximum}.",
                field=field,
            )


def revalidate_plan(
    request_path: Path,
    database_path: Path,
    relationships_path: Path,
    reviewed_plan_path: Path,
    blockers: list[dict[str, str]],
) -> tuple[dict[str, Any], CompiledAnalyticsQuery | None, str]:
    current_plan, planning_blockers, compiled = build_plan(
        request_path,
        database_path,
        relationships_path,
    )
    if planning_blockers or compiled is None:
        add_blocker(
            blockers,
            "plan_revalidation_failed",
            "The structured request no longer produces an execution-ready plan.",
            field="plan",
        )
        return current_plan, None, ""
    if not reviewed_plan_path.is_file():
        add_blocker(
            blockers,
            "reviewed_plan_missing",
            "The exact reviewed Stage 5A plan is required before execution.",
            field="plan",
        )
        return current_plan, None, ""
    try:
        reviewed_bytes = reviewed_plan_path.read_bytes()
        reviewed_content = reviewed_bytes.decode("utf-8")
    except (OSError, UnicodeError):
        add_blocker(
            blockers,
            "reviewed_plan_unreadable",
            "The reviewed plan is not readable UTF-8 text.",
            field="plan",
        )
        return current_plan, None, ""
    reviewed_sha256 = hashlib.sha256(reviewed_bytes).hexdigest()
    if reviewed_content != plan_content(current_plan):
        add_blocker(
            blockers,
            "reviewed_plan_mismatch",
            "The reviewed plan does not exactly match the current request, catalog, and approvals.",
            field="plan",
        )
        return current_plan, None, reviewed_sha256
    return current_plan, compiled, reviewed_sha256


def csv_row(values: list[Any] | tuple[Any, ...]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(values)
    return buffer.getvalue()


def collect_result(
    connection: duckdb.DuckDBPyConnection,
    limits: AnalyticsExecutionLimits,
    timed_out: Event,
) -> tuple[str, list[str], list[str], int, int]:
    description = connection.description or []
    columns = [str(column[0]) for column in description]
    column_types = [str(column[1]) for column in description]
    output = io.StringIO(newline="")
    header = csv_row(columns)
    encoded_bytes = len(header.encode("utf-8"))
    if encoded_bytes > limits.max_result_bytes:
        raise ExecutionLimitExceeded(
            "result_size_limit_exceeded",
            "The result header exceeds the configured byte limit.",
        )
    output.write(header)
    row_count = 0
    null_cells = 0
    while True:
        if timed_out.is_set():
            raise ExecutionLimitExceeded(
                "query_timeout",
                "The query exceeded the configured runtime limit.",
            )
        remaining = limits.max_rows - row_count
        batch = connection.fetchmany(min(FETCH_BATCH_SIZE, remaining + 1))
        if not batch:
            break
        for row in batch:
            row_count += 1
            if row_count > limits.max_rows:
                raise ExecutionLimitExceeded(
                    "result_row_limit_exceeded",
                    "The query result exceeds the configured row limit.",
                )
            null_cells += sum(value is None for value in row)
            line = csv_row(row)
            encoded_bytes += len(line.encode("utf-8"))
            if encoded_bytes > limits.max_result_bytes:
                raise ExecutionLimitExceeded(
                    "result_size_limit_exceeded",
                    "The query result exceeds the configured byte limit.",
                )
            output.write(line)
    return output.getvalue(), columns, column_types, row_count, null_cells


def configure_connection(
    connection: duckdb.DuckDBPyConnection,
    limits: AnalyticsExecutionLimits,
    temp_dir: str,
) -> None:
    settings: tuple[tuple[str, Any], ...] = (
        ("temp_directory", temp_dir),
        ("max_temp_directory_size", f"{limits.max_temp_mb}MB"),
        ("memory_limit", f"{limits.memory_limit_mb}MB"),
        ("threads", limits.threads),
        ("autoinstall_known_extensions", False),
        ("autoload_known_extensions", False),
        ("allow_unsigned_extensions", False),
        ("enable_external_access", False),
    )
    for name, value in settings:
        connection.execute(f"SET {name} = ?", [value])


def execute_compiled_query(
    database_path: Path,
    compiled: CompiledAnalyticsQuery,
    limits: AnalyticsExecutionLimits,
) -> tuple[str, list[str], list[str], int, int, float]:
    started = time.perf_counter()
    timed_out = Event()
    finished = Event()
    with tempfile.TemporaryDirectory(prefix="data_ops_query_") as temp_dir:
        with duckdb.connect(str(database_path), read_only=True) as connection:
            configure_connection(connection, limits, temp_dir)

            def interrupt_query() -> None:
                if not finished.is_set():
                    timed_out.set()
                    connection.interrupt()

            timer = Timer(limits.max_runtime_seconds, interrupt_query)
            timer.daemon = True
            timer.start()
            try:
                connection.execute(compiled.sql, compiled.parameters)
                result = collect_result(connection, limits, timed_out)
                if timed_out.is_set():
                    raise ExecutionLimitExceeded(
                        "query_timeout",
                        "The query exceeded the configured runtime limit.",
                    )
            except duckdb.Error as error:
                if timed_out.is_set():
                    raise ExecutionLimitExceeded(
                        "query_timeout",
                        "The query exceeded the configured runtime limit.",
                    ) from error
                raise
            finally:
                finished.set()
                timer.cancel()
                timer.join()
    return (*result, time.perf_counter() - started)


def blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["blocker_id", "blocker_type", "field", "explanation"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def build_manifest(
    status: str,
    current_plan: dict[str, Any],
    reviewed_plan_sha256: str,
    database_stat: tuple[int, int] | None,
    limits: AnalyticsExecutionLimits,
    blockers: list[dict[str, str]],
    result: dict[str, Any],
    compiled: CompiledAnalyticsQuery | None,
) -> dict[str, Any]:
    source = current_plan.get("source", {})
    return {
        "version": 1,
        "status": status,
        "source": {
            "reviewed_plan_sha256": reviewed_plan_sha256,
            "request_sha256": source.get("request_sha256", ""),
            "relationships_sha256": source.get("relationships_sha256", ""),
            "catalog_sha256": source.get("catalog_sha256", ""),
            "database_size_bytes": database_stat[0] if database_stat else 0,
            "database_modified_ns": database_stat[1] if database_stat else 0,
        },
        "query": {
            "sql_sha256": (
                hashlib.sha256(compiled.sql.encode("utf-8")).hexdigest() if compiled else ""
            ),
            "parameter_count": len(compiled.parameters) if compiled else 0,
            "parameter_types": list(compiled.parameter_types) if compiled else [],
            "parameter_values_included": False,
            "raw_sql_accepted": False,
        },
        "execution": {
            "database_mode": "read_only",
            "external_access": False,
            "extension_autoload": False,
            "max_rows": limits.max_rows,
            "max_result_bytes": limits.max_result_bytes,
            "max_runtime_seconds": limits.max_runtime_seconds,
            "memory_limit_mb": limits.memory_limit_mb,
            "threads": limits.threads,
            "max_temp_mb": limits.max_temp_mb,
        },
        "result": result,
        "approval": {
            "reviewed_plan_required": True,
            "request_and_relationships_revalidated": True,
            "relationship_candidates_accepted": False,
        },
        "blockers": blockers,
    }


def render_report(manifest: dict[str, Any]) -> str:
    result = manifest["result"]
    lines = [
        "# Analytics Query Execution Report",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Rows: {result['rows']}",
        f"- Columns: {result['columns']}",
        f"- Null cells: {result['null_cells']}",
        f"- Blockers: {len(manifest['blockers'])}",
        "",
        "## Safety Boundary",
        "",
        "- The query was recompiled from the structured request; raw SQL was not accepted.",
        "- The reviewed plan, live catalog, and approved relationships had to match exactly.",
        "- DuckDB was opened in read-only mode with external access and extension autoload disabled.",
        "- Runtime, memory, thread, temporary-storage, row, and result-byte limits were enforced.",
        "- Parameter values are not copied into the manifest, blockers, or report.",
        "",
        "## Diagnostics",
        "",
    ]
    if manifest["status"] == "completed_no_rows":
        lines.append("- The query completed successfully but returned no rows.")
    elif manifest["status"] == "completed":
        lines.append("- The query completed within all configured limits.")
    else:
        lines.extend(
            f"- `{row['blocker_id']}` `{row['blocker_type']}`: "
            f"field=`{row['field'] or 'not_available'}`"
            for row in manifest["blockers"]
        )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Analytics execution output path is not a directory: {output_dir}")
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
            f"Different analytics execution outputs already exist in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_query_execution(
    request_path: Path,
    database_path: Path,
    relationships_path: Path,
    reviewed_plan_path: Path,
    output_dir: Path,
    limits: AnalyticsExecutionLimits | None = None,
) -> AnalyticsQueryExecutionResult:
    limits = limits or AnalyticsExecutionLimits()
    blockers: list[dict[str, str]] = []
    validate_limits(limits, blockers)
    current_plan, compiled, reviewed_plan_sha256 = revalidate_plan(
        request_path,
        database_path,
        relationships_path,
        reviewed_plan_path,
        blockers,
    )
    database_stat: tuple[int, int] | None = None
    if database_path.is_file():
        stat = database_path.stat()
        database_stat = (stat.st_size, stat.st_mtime_ns)
        source = current_plan.get("source", {})
        planned_database_stat = (
            source.get("database_size_bytes", 0),
            source.get("database_modified_ns", 0),
        )
        if not blockers and database_stat != planned_database_stat:
            add_blocker(
                blockers,
                "database_changed_after_plan_revalidation",
                "The database changed immediately after plan revalidation; execution was blocked.",
                field="database",
            )

    result_csv = ""
    row_count = 0
    column_names: list[str] = []
    column_types: list[str] = []
    null_cells = 0
    elapsed_seconds = 0.0
    input_hashes = {
        "request": current_plan.get("source", {}).get("request_sha256", ""),
        "relationships": current_plan.get("source", {}).get("relationships_sha256", ""),
        "plan": reviewed_plan_sha256,
    }
    if not blockers and compiled is not None:
        try:
            (
                result_csv,
                column_names,
                column_types,
                row_count,
                null_cells,
                elapsed_seconds,
            ) = execute_compiled_query(database_path, compiled, limits)
        except ExecutionLimitExceeded as error:
            add_blocker(blockers, error.blocker_type, error.explanation, field="execution")
        except (duckdb.Error, OSError):
            add_blocker(
                blockers,
                "query_execution_failed",
                "DuckDB could not complete the query within the controlled execution boundary.",
                field="execution",
            )

    if not blockers and database_stat is not None:
        stat = database_path.stat()
        if (stat.st_size, stat.st_mtime_ns) != database_stat:
            add_blocker(
                blockers,
                "database_changed_during_execution",
                "The database file changed during execution; the result was discarded.",
                field="database",
            )
    if not blockers:
        current_hashes = {
            "request": file_sha256(request_path),
            "relationships": file_sha256(relationships_path),
            "plan": file_sha256(reviewed_plan_path),
        }
        if current_hashes != input_hashes:
            add_blocker(
                blockers,
                "execution_inputs_changed",
                "A validated input changed during execution; the result was discarded.",
                field="inputs",
            )

    if blockers:
        status = "blocked"
        result_csv = ""
        row_count = 0
        column_names = []
        column_types = []
        null_cells = 0
    else:
        status = "completed_no_rows" if row_count == 0 else "completed"

    result_metadata = {
        "artifact": RESULT_NAME if not blockers else "",
        "sha256": (
            hashlib.sha256(result_csv.encode("utf-8")).hexdigest() if not blockers else ""
        ),
        "rows": row_count,
        "columns": len(column_names),
        "column_names": column_names,
        "column_types": column_types,
        "null_cells": null_cells,
        "truncated": False,
        "no_rows": status == "completed_no_rows",
    }
    manifest = build_manifest(
        status,
        current_plan,
        reviewed_plan_sha256,
        database_stat,
        limits,
        blockers,
        result_metadata,
        compiled,
    )
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(manifest),
    }
    if not blockers:
        contents[RESULT_NAME] = result_csv
    outputs_changed = write_outputs(output_dir, contents)
    return AnalyticsQueryExecutionResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        result_path=output_dir / RESULT_NAME if not blockers else None,
        blocker_count=len(blockers),
        row_count=row_count,
        outputs_changed=outputs_changed,
        elapsed_seconds=elapsed_seconds,
    )
