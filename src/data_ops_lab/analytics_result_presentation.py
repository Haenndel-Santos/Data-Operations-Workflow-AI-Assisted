from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .analytics_query_plan import add_blocker, read_yaml_mapping
from .analytics_semantic_adapter import MAX_QUESTION_LENGTH
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_result_presentation.yml"
FACTS_NAME = "analytics_result_facts.yml"
PRESENTATION_NAME = "analytics_result_presentation.md"
BLOCKERS_NAME = "analytics_result_presentation_blockers.csv"
OUTPUT_NAMES = {MANIFEST_NAME, FACTS_NAME, PRESENTATION_NAME, BLOCKERS_NAME}
MAX_RESULT_BYTES = 50_000_000
MAX_PREVIEW_ROWS = 100
MAX_PREVIEW_COLUMNS = 20
MAX_PREVIEW_CELLS = 2_000


@dataclass(frozen=True)
class AnalyticsResultPresentationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    facts_path: Path | None
    presentation_path: Path
    blockers_path: Path
    blocker_count: int
    row_count: int
    preview_row_count: int
    preview_column_count: int
    outputs_changed: bool


def canonical_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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


def integer_field(
    payload: dict[str, Any],
    name: str,
    blockers: list[dict[str, str]],
    *,
    minimum: int = 0,
) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        add_blocker(
            blockers,
            "invalid_execution_manifest",
            f"Execution result field {name} must be an integer of at least {minimum}.",
            field=f"execution_manifest.result.{name}",
        )
        return 0
    return value


def validate_request(
    request: dict[str, Any],
    request_path: Path,
    execution_manifest: dict[str, Any],
    blockers: list[dict[str, str]],
) -> str:
    if request.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_request_version",
            "Only a version-1 Stage 5A request can be presented.",
            field="request.version",
        )
    question = request.get("question", "")
    if not isinstance(question, str) or len(question.strip()) > MAX_QUESTION_LENGTH:
        add_blocker(
            blockers,
            "invalid_question",
            f"The optional question must be text of at most {MAX_QUESTION_LENGTH} characters.",
            field="request.question",
        )
        question = ""
    source = execution_manifest.get("source", {})
    expected_hash = source.get("request_sha256", "") if isinstance(source, dict) else ""
    if request_path.is_file() and expected_hash != file_sha256(request_path):
        add_blocker(
            blockers,
            "request_hash_mismatch",
            "The request does not match the request executed by Stage 5B.",
            field="request",
        )
    return question.strip()


def validate_execution_manifest(
    manifest: dict[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    if manifest.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_execution_manifest_version",
            "Only a version-1 Stage 5B execution manifest can be presented.",
            field="execution_manifest.version",
        )
    status = manifest.get("status")
    if status not in {"completed", "completed_no_rows"}:
        add_blocker(
            blockers,
            "execution_not_presentable",
            "Stage 5B must have completed without blockers before presentation.",
            field="execution_manifest.status",
        )
    if manifest.get("blockers") != []:
        add_blocker(
            blockers,
            "execution_has_blockers",
            "Stage 5B blocker evidence prevents result presentation.",
            field="execution_manifest.blockers",
        )

    query = manifest.get("query", {})
    execution = manifest.get("execution", {})
    approval = manifest.get("approval", {})
    required = {
        "query.parameter_values_included": (query, "parameter_values_included", False),
        "query.raw_sql_accepted": (query, "raw_sql_accepted", False),
        "execution.database_mode": (execution, "database_mode", "read_only"),
        "execution.external_access": (execution, "external_access", False),
        "execution.extension_autoload": (execution, "extension_autoload", False),
        "approval.reviewed_plan_required": (approval, "reviewed_plan_required", True),
        "approval.request_and_relationships_revalidated": (
            approval,
            "request_and_relationships_revalidated",
            True,
        ),
        "approval.relationship_candidates_accepted": (
            approval,
            "relationship_candidates_accepted",
            False,
        ),
    }
    for field, (section, key, expected) in required.items():
        if not isinstance(section, dict) or section.get(key) != expected:
            add_blocker(
                blockers,
                "unsafe_execution_evidence",
                f"Required Stage 5B control {field} is not satisfied.",
                field=f"execution_manifest.{field}",
            )
    result = manifest.get("result", {})
    if not isinstance(result, dict):
        add_blocker(
            blockers,
            "invalid_execution_manifest",
            "The Stage 5B result section must be a mapping.",
            field="execution_manifest.result",
        )
        return {}
    if result.get("truncated") is not False:
        add_blocker(
            blockers,
            "truncated_result_not_allowed",
            "A truncated Stage 5B result cannot be presented as complete evidence.",
            field="execution_manifest.result.truncated",
        )
    return result


def read_and_validate_result(
    result_path: Path,
    result_metadata: dict[str, Any],
    execution_manifest: dict[str, Any],
    blockers: list[dict[str, str]],
) -> tuple[list[str], list[list[str]], int, int, int]:
    expected_rows = integer_field(result_metadata, "rows", blockers)
    expected_columns = integer_field(result_metadata, "columns", blockers)
    null_cells = integer_field(result_metadata, "null_cells", blockers)
    column_names = result_metadata.get("column_names", [])
    column_types = result_metadata.get("column_types", [])
    if (
        not isinstance(column_names, list)
        or not all(isinstance(value, str) for value in column_names)
        or len(column_names) != expected_columns
        or not isinstance(column_types, list)
        or len(column_types) != expected_columns
        or not all(isinstance(value, str) for value in column_types)
    ):
        add_blocker(
            blockers,
            "invalid_execution_columns",
            "Stage 5B column names and types must match the declared column count.",
            field="execution_manifest.result.column_names",
        )

    if not result_path.is_file():
        add_blocker(
            blockers,
            "result_missing",
            "The Stage 5B result CSV is missing.",
            field="result",
        )
        return [], [], expected_rows, expected_columns, null_cells
    execution = execution_manifest.get("execution", {})
    declared_limit = execution.get("max_result_bytes", 0) if isinstance(execution, dict) else 0
    if (
        isinstance(declared_limit, bool)
        or not isinstance(declared_limit, int)
        or not 1_024 <= declared_limit <= MAX_RESULT_BYTES
        or result_path.stat().st_size > declared_limit
    ):
        add_blocker(
            blockers,
            "result_size_invalid",
            "The result does not satisfy the bounded Stage 5B byte limit.",
            field="result",
        )
        return [], [], expected_rows, expected_columns, null_cells
    if result_metadata.get("artifact") != result_path.name:
        add_blocker(
            blockers,
            "result_artifact_mismatch",
            "The supplied result filename does not match Stage 5B evidence.",
            field="result",
        )
    if result_metadata.get("sha256") != file_sha256(result_path):
        add_blocker(
            blockers,
            "result_hash_mismatch",
            "The result does not match the SHA-256 recorded by Stage 5B.",
            field="result",
        )
        return [], [], expected_rows, expected_columns, null_cells
    header: list[str] = []
    preview_rows: list[list[str]] = []
    actual_rows = 0
    invalid_row_shape = False
    try:
        with result_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            for row in reader:
                actual_rows += 1
                invalid_row_shape = invalid_row_shape or len(row) != expected_columns
                if len(preview_rows) < MAX_PREVIEW_ROWS:
                    preview_rows.append(row)
    except (OSError, UnicodeError, csv.Error):
        add_blocker(
            blockers,
            "invalid_result_csv",
            "The Stage 5B result must be readable UTF-8 CSV.",
            field="result",
        )
        return [], [], expected_rows, expected_columns, null_cells
    if header != column_names or actual_rows != expected_rows or invalid_row_shape:
        add_blocker(
            blockers,
            "result_controls_mismatch",
            "CSV shape or header does not match Stage 5B control totals.",
            field="result",
        )
    expected_no_rows = execution_manifest.get("status") == "completed_no_rows"
    if result_metadata.get("no_rows") is not expected_no_rows or (expected_rows == 0) is not expected_no_rows:
        add_blocker(
            blockers,
            "no_rows_control_mismatch",
            "The no-row state does not match Stage 5B status and row controls.",
            field="execution_manifest.result.no_rows",
        )
    if null_cells > expected_rows * expected_columns:
        add_blocker(
            blockers,
            "invalid_null_control",
            "The null-cell count exceeds the result shape.",
            field="execution_manifest.result.null_cells",
        )
    return header, preview_rows, expected_rows, expected_columns, null_cells


def fact(
    fact_id: str,
    fact_type: str,
    value: str,
    *,
    required_citation: bool = False,
    row: int | None = None,
    column: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": fact_id,
        "type": fact_type,
        "value": value,
        "required_citation": required_citation,
    }
    if row is not None:
        item["row"] = row
        item["column"] = column
    return item


def build_facts(
    question: str,
    request_sha256: str,
    execution_manifest_sha256: str,
    result_sha256: str,
    header: list[str],
    rows: list[list[str]],
    row_count: int,
    column_count: int,
    null_cells: int,
) -> tuple[dict[str, Any], int, int, bool]:
    preview_column_count = min(column_count, MAX_PREVIEW_COLUMNS)
    preview_row_limit = min(MAX_PREVIEW_ROWS, MAX_PREVIEW_CELLS // max(preview_column_count, 1))
    preview_rows = rows[:preview_row_limit]
    preview_columns = header[:preview_column_count]
    truncated = len(preview_rows) < row_count or preview_column_count < column_count
    facts = [
        fact("result.row_count", "integer", str(row_count), required_citation=True),
        fact("result.column_count", "integer", str(column_count)),
        fact("result.null_cells", "integer", str(null_cells)),
        fact(
            "result.no_rows",
            "boolean",
            str(row_count == 0).lower(),
            required_citation=True,
        ),
        fact(
            "control.preview_truncated",
            "boolean",
            str(truncated).lower(),
            required_citation=True,
        ),
    ]
    for row_index, row in enumerate(preview_rows, start=1):
        for column_index, value in enumerate(row[:preview_column_count], start=1):
            facts.append(
                fact(
                    f"cell.r{row_index:03d}.c{column_index:03d}",
                    "csv_text",
                    value,
                    row=row_index,
                    column=preview_columns[column_index - 1],
                )
            )
    payload = {
        "version": 1,
        "status": "ready_for_recorded_narration",
        "source": {
            "request_sha256": request_sha256,
            "execution_manifest_sha256": execution_manifest_sha256,
            "result_sha256": result_sha256,
        },
        "question": question,
        "preview": {
            "rows_shown": len(preview_rows),
            "columns_shown": preview_column_count,
            "rows_total": row_count,
            "columns_total": column_count,
            "truncated": truncated,
        },
        "facts": facts,
        "caveats": [
            "The Stage 5B CSV and hashes are authoritative; narration is not.",
            "The local preview is bounded and may omit rows or columns.",
            "Empty CSV text does not distinguish a database NULL from an empty string.",
        ],
    }
    return payload, len(preview_rows), preview_column_count, truncated


def markdown_cell(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", "")
        .replace("\n", "<br>")
    )


def render_presentation(
    facts: dict[str, Any],
    header: list[str],
    rows: list[list[str]],
    null_cells: int,
) -> str:
    preview = facts["preview"]
    source = facts["source"]
    question = facts["question"] or "Structured analytics request"
    lines = [
        "# Analytics Result",
        "",
        f"**Question:** {markdown_cell(question)}",
        "",
        "## Controls",
        "",
        f"- Rows: {preview['rows_total']} `[result.row_count]`",
        f"- Columns: {preview['columns_total']} `[result.column_count]`",
        f"- Null cells: {null_cells} `[result.null_cells]`",
        f"- No rows: {str(preview['rows_total'] == 0).lower()} `[result.no_rows]`",
        f"- Preview truncated: {str(preview['truncated']).lower()} `[control.preview_truncated]`",
        "",
        "## Result Preview",
        "",
    ]
    shown_header = header[: preview["columns_shown"]]
    shown_rows = rows[: preview["rows_shown"]]
    if not shown_rows:
        lines.append("The query completed successfully and returned no rows.")
    else:
        lines.append("| " + " | ".join(markdown_cell(value) for value in shown_header) + " |")
        lines.append("| " + " | ".join("---" for _ in shown_header) + " |")
        for row in shown_rows:
            lines.append(
                "| "
                + " | ".join(markdown_cell(value) for value in row[: preview["columns_shown"]])
                + " |"
            )
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Request SHA-256: `{source['request_sha256']}`",
            f"- Execution manifest SHA-256: `{source['execution_manifest_sha256']}`",
            f"- Result SHA-256: `{source['result_sha256']}`",
            "",
            "## Caveats",
            "",
            *[f"- {value}" for value in facts["caveats"]],
        ]
    )
    return "\n".join(lines) + "\n"


def render_blocked_presentation(blockers: list[dict[str, str]]) -> str:
    lines = [
        "# Analytics Result Presentation",
        "",
        "Status: `blocked`",
        "",
        "No result values were presented because source evidence did not pass validation.",
        "",
        "## Diagnostics",
        "",
    ]
    lines.extend(
        f"- `{row['blocker_id']}` `{row['blocker_type']}`: field=`{row['field'] or 'not_available'}`"
        for row in blockers
    )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Result presentation output is not a directory: {output_dir}")
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
            f"Different result presentation evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_result_presentation(
    request_path: Path,
    execution_manifest_path: Path,
    result_path: Path,
    output_dir: Path,
) -> AnalyticsResultPresentationResult:
    blockers: list[dict[str, str]] = []
    input_paths = {
        "request": request_path,
        "execution_manifest": execution_manifest_path,
        "result": result_path,
    }
    input_hashes = {
        name: file_sha256(path) for name, path in input_paths.items() if path.is_file()
    }
    request = read_yaml_mapping(request_path, blockers, "request")
    execution_manifest = read_yaml_mapping(
        execution_manifest_path,
        blockers,
        "execution_manifest",
    )
    result_metadata = validate_execution_manifest(execution_manifest, blockers)
    question = validate_request(request, request_path, execution_manifest, blockers)
    header, rows, row_count, column_count, null_cells = read_and_validate_result(
        result_path,
        result_metadata,
        execution_manifest,
        blockers,
    )
    if not blockers:
        current_hashes = {
            name: file_sha256(path) for name, path in input_paths.items() if path.is_file()
        }
        if current_hashes != input_hashes:
            add_blocker(
                blockers,
                "presentation_inputs_changed",
                "A validated input changed during result presentation.",
                field="inputs",
            )

    status = "blocked" if blockers else "ready_for_recorded_narration"
    facts: dict[str, Any] | None = None
    facts_content = ""
    preview_rows = 0
    preview_columns = 0
    if not blockers:
        facts, preview_rows, preview_columns, _ = build_facts(
            question,
            input_hashes["request"],
            input_hashes["execution_manifest"],
            input_hashes["result"],
            header,
            rows,
            row_count,
            column_count,
            null_cells,
        )
        facts_content = canonical_yaml(facts)

    manifest = {
        "version": 1,
        "status": status,
        "source": {
            "request_sha256": input_hashes.get("request", ""),
            "execution_manifest_sha256": input_hashes.get("execution_manifest", ""),
            "result_sha256": input_hashes.get("result", ""),
        },
        "controls": {
            "stage_5b_result_is_numeric_authority": True,
            "query_execution_available": False,
            "raw_sql_accepted": False,
            "network_access": False,
            "preview_max_rows": MAX_PREVIEW_ROWS,
            "preview_max_columns": MAX_PREVIEW_COLUMNS,
            "preview_max_cells": MAX_PREVIEW_CELLS,
            "preview_rows": preview_rows,
            "preview_columns": preview_columns,
            "full_result_modified": False,
        },
        "privacy": {
            "question_or_result_values_in_manifest": False,
            "question_and_preview_values_persisted_locally": facts is not None,
        },
        "counts": {
            "rows": row_count if not blockers else 0,
            "columns": column_count if not blockers else 0,
            "blockers": len(blockers),
        },
        "facts_sha256": content_sha256(facts_content) if facts_content else "",
    }
    contents = {
        MANIFEST_NAME: canonical_yaml(manifest),
        BLOCKERS_NAME: blockers_csv(blockers),
        PRESENTATION_NAME: (
            render_presentation(facts, header, rows, null_cells)
            if facts is not None
            else render_blocked_presentation(blockers)
        ),
    }
    if facts_content:
        contents[FACTS_NAME] = facts_content
    outputs_changed = write_outputs(output_dir, contents)
    return AnalyticsResultPresentationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        facts_path=output_dir / FACTS_NAME if facts is not None else None,
        presentation_path=output_dir / PRESENTATION_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        blocker_count=len(blockers),
        row_count=row_count if not blockers else 0,
        preview_row_count=preview_rows,
        preview_column_count=preview_columns,
        outputs_changed=outputs_changed,
    )
