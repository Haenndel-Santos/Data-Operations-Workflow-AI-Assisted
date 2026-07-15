from __future__ import annotations

import csv
import hashlib
import math
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from .analytics_dataset_benchmark import (
    EXPECTED_TYPES,
    MAX_CONTROL_FILE_BYTES,
    inspect_analytics_dataset_benchmark_candidate,
)
from .analytics_query_execution import (
    AnalyticsExecutionLimits,
    run_analytics_query_execution,
)
from .analytics_query_plan import add_blocker, read_yaml_mapping
from .analytics_session import blockers_csv, canonical_yaml, write_outputs
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_dataset_benchmark_materialization.yml"
CASES_NAME = "analytics_dataset_benchmark_materialization_cases.csv"
BLOCKERS_NAME = "analytics_dataset_benchmark_materialization_blockers.csv"
REPORT_NAME = "analytics_dataset_benchmark_materialization_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, CASES_NAME, BLOCKERS_NAME, REPORT_NAME}

COLLECTION_LIMITS = AnalyticsExecutionLimits(
    max_rows=10_000,
    max_result_bytes=10_000_000,
    max_runtime_seconds=30,
    memory_limit_mb=512,
    threads=1,
    max_temp_mb=256,
)

REQUIRED_SCOPES = {
    "local_read_only_answer_collection": "approved",
    "live_provider_use": "not_authorized",
    "external_upload": "not_authorized",
    "model_training": "not_authorized",
    "publication": "not_authorized",
}


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkMaterializationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    cases_path: Path
    blockers_path: Path
    report_path: Path
    pack_path: Path | None
    case_count: int
    completed_count: int
    blocker_count: int
    outputs_changed: bool
    pack_changed: bool


def _read_mapping(
    path: Path,
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, Any]:
    if path.is_file() and path.stat().st_size > MAX_CONTROL_FILE_BYTES:
        add_blocker(
            blockers,
            "benchmark_materialization_control_too_large",
            f"Control YAML files must be at most {MAX_CONTROL_FILE_BYTES} bytes.",
            field=field,
        )
        return {}
    return read_yaml_mapping(path, blockers, field)


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _reject_unknown_fields(
    payload: dict[str, Any],
    allowed: set[str],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    for name in payload:
        if name not in allowed:
            add_blocker(
                blockers,
                "unsupported_answer_materialization_field",
                "The answer materialization authority contains a field outside the version-1 contract.",
                field=f"{field}.{name}",
            )


def _source_paths(
    design_path: Path,
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    preparation_manifest_path: Path,
    execution_review_path: Path,
) -> dict[str, Path]:
    return {
        "design_sha256": design_path,
        "dataset_manifest_sha256": dataset_manifest_path,
        "database_sha256": database_path,
        "approved_semantic_state_sha256": semantic_state_path,
        "approved_relationships_sha256": relationships_path,
        "preparation_manifest_sha256": preparation_manifest_path,
        "execution_review_sha256": execution_review_path,
    }


def _current_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {
        name: file_sha256(path) if path.is_file() else ""
        for name, path in paths.items()
    }


def _hashes_match(expected: dict[str, str], paths: dict[str, Path]) -> bool:
    return _current_hashes(paths) == expected


def _validate_preparation(
    preparation: dict[str, Any],
    design: dict[str, Any],
    hashes: dict[str, str],
    blockers: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if preparation.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_benchmark_preparation_version",
            "Answer materialization requires a version-1 preparation manifest.",
            field="preparation.version",
        )
    if (
        preparation.get("status") != "awaiting_execution_review"
        or preparation.get("workflow") != "dataset_benchmark_answer_preparation"
    ):
        add_blocker(
            blockers,
            "benchmark_preparation_not_review_ready",
            "The preparation manifest must be awaiting exact execution review.",
            field="preparation.status",
        )
    identity = preparation.get("identity")
    expected_identity = {
        "dataset_id": design.get("dataset_id", ""),
        "design_id": design.get("design_id", ""),
        "pack_id": design.get("pack_id", ""),
    }
    if identity != expected_identity:
        add_blocker(
            blockers,
            "benchmark_preparation_identity_mismatch",
            "Preparation identity must match the bound answer design.",
            field="preparation.identity",
        )
        identity = expected_identity
    source = preparation.get("source")
    expected_source = {
        name: hashes[name]
        for name in (
            "design_sha256",
            "dataset_manifest_sha256",
            "database_sha256",
            "approved_semantic_state_sha256",
            "approved_relationships_sha256",
        )
    }
    if not isinstance(source, dict) or any(
        source.get(name) != digest for name, digest in expected_source.items()
    ):
        add_blocker(
            blockers,
            "benchmark_preparation_source_drift",
            "Preparation source hashes no longer match the supplied immutable inputs.",
            field="preparation.source",
        )
    controls = preparation.get("controls")
    if not isinstance(controls, dict) or any(
        (
            controls.get("recorded_semantic_intents_only") is not True,
            controls.get("network_access") is not False,
            controls.get("database_catalog_read_only") is not True,
            controls.get("table_rows_read") is not False,
            controls.get("query_execution_authorized") is not False,
            controls.get("human_plan_review_required") is not True,
            controls.get("final_expected_answers_approved") is not False,
            controls.get("live_provider_authorized") is not False,
        )
    ):
        add_blocker(
            blockers,
            "invalid_benchmark_preparation_controls",
            "Preparation safety controls do not match the pre-execution contract.",
            field="preparation.controls",
        )
    cases = preparation.get("cases")
    if not isinstance(cases, list) or not cases:
        add_blocker(
            blockers,
            "invalid_benchmark_preparation_cases",
            "Preparation evidence must contain at least one review-ready case.",
            field="preparation.cases",
        )
        cases = []
    design_cases = design.get("cases")
    design_ids = (
        [row.get("id") for row in design_cases if isinstance(row, dict)]
        if isinstance(design_cases, list)
        else []
    )
    preparation_ids = [
        row.get("case_id") for row in cases if isinstance(row, dict)
    ]
    if preparation_ids != design_ids or len(preparation_ids) != len(cases):
        add_blocker(
            blockers,
            "benchmark_preparation_case_mismatch",
            "Preparation cases must exactly match the answer design in order.",
            field="preparation.cases",
        )
    for index, row in enumerate(cases):
        if not isinstance(row, dict) or (
            row.get("translation_status") != "ready_for_query_plan"
            or row.get("plan_status") != "ready_for_execution_review"
        ):
            add_blocker(
                blockers,
                "benchmark_case_not_execution_ready",
                "Every materialized case requires a recorded request and exact review-ready plan.",
                field=f"preparation.cases[{index}]",
            )
    return {key: str(value) for key, value in expected_identity.items()}, cases


def _validate_scope_decisions(
    payload: Any,
    blockers: list[dict[str, str]],
) -> None:
    if not isinstance(payload, list):
        add_blocker(
            blockers,
            "invalid_answer_collection_scope_decisions",
            "The completed execution review requires explicit scope decisions.",
            field="execution_review.review.scope_decisions",
        )
        return
    seen: set[str] = set()
    for index, row in enumerate(payload):
        field = f"execution_review.review.scope_decisions[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_answer_collection_scope_decision",
                "Every scope decision must be a mapping.",
                field=field,
            )
            continue
        _reject_unknown_fields(
            row, {"scope", "decision", "notes"}, blockers, field
        )
        scope = row.get("scope")
        if scope not in REQUIRED_SCOPES:
            add_blocker(
                blockers,
                "unknown_answer_collection_scope",
                "The execution review contains an unknown scope.",
                field=f"{field}.scope",
            )
            continue
        if scope in seen:
            add_blocker(
                blockers,
                "duplicate_answer_collection_scope",
                "Every execution scope must be decided exactly once.",
                field=f"{field}.scope",
            )
            continue
        seen.add(scope)
        if row.get("decision") != REQUIRED_SCOPES[scope]:
            blocker_type = (
                "answer_collection_scope_expansion_not_allowed"
                if scope != "local_read_only_answer_collection"
                and row.get("decision") == "approved"
                else "answer_collection_scope_not_approved"
            )
            add_blocker(
                blockers,
                blocker_type,
                f"Scope {scope} must be {REQUIRED_SCOPES[scope]}.",
                field=f"{field}.decision",
            )
        if not isinstance(row.get("notes"), str) or not row["notes"].strip():
            add_blocker(
                blockers,
                "missing_answer_collection_scope_notes",
                "Every execution scope decision requires human notes.",
                field=f"{field}.notes",
            )
    for scope in set(REQUIRED_SCOPES) - seen:
        add_blocker(
            blockers,
            "missing_answer_collection_scope",
            "Every execution scope must be decided exactly once.",
            field=f"execution_review.review.scope_decisions.{scope}",
        )


def _validate_case_decisions(
    payload: Any,
    preparation_cases: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> None:
    expected = {
        row.get("case_id"): row.get("plan_sha256")
        for row in preparation_cases
        if isinstance(row, dict)
    }
    if not isinstance(payload, list):
        add_blocker(
            blockers,
            "invalid_answer_collection_case_decisions",
            "The completed execution review requires per-case decisions.",
            field="execution_review.review.case_decisions",
        )
        return
    seen: set[str] = set()
    for index, row in enumerate(payload):
        field = f"execution_review.review.case_decisions[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_answer_collection_case_decision",
                "Every case decision must be a mapping.",
                field=field,
            )
            continue
        _reject_unknown_fields(
            row,
            {"case_id", "reviewed_plan_sha256", "decision", "notes"},
            blockers,
            field,
        )
        case_id = row.get("case_id")
        if case_id not in expected:
            add_blocker(
                blockers,
                "unknown_answer_collection_case",
                "The execution review contains an unknown case.",
                field=f"{field}.case_id",
            )
            continue
        if case_id in seen:
            add_blocker(
                blockers,
                "duplicate_answer_collection_case",
                "Every exact plan must be reviewed once.",
                field=f"{field}.case_id",
            )
            continue
        seen.add(case_id)
        if row.get("reviewed_plan_sha256") != expected[case_id]:
            add_blocker(
                blockers,
                "reviewed_answer_plan_hash_mismatch",
                "The case decision does not bind the exact prepared plan.",
                field=f"{field}.reviewed_plan_sha256",
            )
        if row.get("decision") != "approved":
            add_blocker(
                blockers,
                "answer_collection_case_not_approved",
                "Every exact plan must be explicitly approved before Stage 5B.",
                field=f"{field}.decision",
            )
        if not isinstance(row.get("notes"), str) or not row["notes"].strip():
            add_blocker(
                blockers,
                "missing_answer_collection_case_notes",
                "Every exact-plan decision requires human notes.",
                field=f"{field}.notes",
            )
    for case_id in set(expected) - seen:
        add_blocker(
            blockers,
            "missing_answer_collection_case",
            "Every exact plan must be reviewed once.",
            field=f"execution_review.review.case_decisions.{case_id}",
        )


def _validate_execution_review(
    review: dict[str, Any],
    identity: dict[str, str],
    preparation_cases: list[dict[str, Any]],
    hashes: dict[str, str],
    blockers: list[dict[str, str]],
) -> None:
    _reject_unknown_fields(
        review,
        {"version", "status", "source", "identity", "review"},
        blockers,
        "execution_review",
    )
    if review.get("version") != 1 or review.get("status") != "completed_human_review":
        add_blocker(
            blockers,
            "answer_collection_review_not_completed",
            "Stage 5B answer collection requires a completed version-1 human review.",
            field="execution_review.status",
        )
    expected_source = {
        name: hashes[name]
        for name in (
            "preparation_manifest_sha256",
            "design_sha256",
            "dataset_manifest_sha256",
            "database_sha256",
            "approved_semantic_state_sha256",
            "approved_relationships_sha256",
        )
    }
    source = review.get("source")
    if not isinstance(source, dict) or source != expected_source:
        add_blocker(
            blockers,
            "answer_collection_review_source_drift",
            "The completed review no longer matches the exact preparation authority.",
            field="execution_review.source",
        )
    if review.get("identity") != identity:
        add_blocker(
            blockers,
            "answer_collection_review_identity_mismatch",
            "The completed review identity must match the exact answer design.",
            field="execution_review.identity",
        )
    decision = review.get("review")
    if not isinstance(decision, dict):
        add_blocker(
            blockers,
            "invalid_answer_collection_review",
            "The completed review must contain human decisions.",
            field="execution_review.review",
        )
        return
    _reject_unknown_fields(
        decision,
        {"reviewer", "reviewed_at", "scope_decisions", "case_decisions"},
        blockers,
        "execution_review.review",
    )
    if not isinstance(decision.get("reviewer"), str) or not decision["reviewer"].strip():
        add_blocker(
            blockers,
            "missing_answer_collection_reviewer",
            "The execution review requires a human reviewer identity.",
            field="execution_review.review.reviewer",
        )
    if not _valid_timestamp(decision.get("reviewed_at")):
        add_blocker(
            blockers,
            "invalid_answer_collection_review_time",
            "The execution review requires an ISO-8601 timestamp with timezone.",
            field="execution_review.review.reviewed_at",
        )
    _validate_scope_decisions(decision.get("scope_decisions"), blockers)
    _validate_case_decisions(
        decision.get("case_decisions"), preparation_cases, blockers
    )


def _resolve_preparation_artifact(
    preparation_manifest_path: Path,
    relative_value: Any,
    expected_hash: Any,
    field: str,
    blockers: list[dict[str, str]],
) -> Path | None:
    if not isinstance(relative_value, str) or not relative_value:
        add_blocker(
            blockers,
            "missing_benchmark_preparation_artifact",
            "A required prepared request or plan path is missing.",
            field=field,
        )
        return None
    relative = Path(relative_value)
    root = preparation_manifest_path.parent.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        add_blocker(
            blockers,
            "unsafe_benchmark_preparation_artifact_path",
            "Prepared artifact paths must remain inside the preparation directory.",
            field=field,
        )
        return None
    if relative.is_absolute() or not candidate.is_file():
        add_blocker(
            blockers,
            "benchmark_preparation_artifact_missing",
            "A required prepared request or plan file is unavailable.",
            field=field,
        )
        return None
    if not isinstance(expected_hash, str) or file_sha256(candidate) != expected_hash:
        add_blocker(
            blockers,
            "benchmark_preparation_artifact_drift",
            "A prepared request or plan no longer matches its recorded SHA-256.",
            field=field,
        )
        return None
    return candidate


def _duckdb_type_matches(actual: str, expected: str) -> bool:
    normalized = actual.upper()
    if expected == "string":
        return normalized in {"VARCHAR", "CHAR", "TEXT"} or normalized.startswith("VARCHAR")
    if expected == "integer":
        return "INT" in normalized and not normalized.startswith("INTERVAL")
    if expected == "decimal":
        return normalized.startswith("DECIMAL") or normalized.startswith("NUMERIC")
    if expected == "float":
        return normalized in {"FLOAT", "DOUBLE", "REAL"}
    if expected == "boolean":
        return normalized == "BOOLEAN"
    return False


def _parse_nonempty_cell(value: str, type_name: str) -> Any:
    if type_name == "string":
        return value
    if type_name == "integer":
        return int(value)
    if type_name == "decimal":
        try:
            parsed_decimal = Decimal(value)
        except InvalidOperation as error:
            raise ValueError from error
        if not parsed_decimal.is_finite():
            raise ValueError
        return value
    if type_name == "float":
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError
        return parsed
    if type_name == "boolean":
        normalized = value.casefold()
        if normalized not in {"true", "false"}:
            raise ValueError
        return normalized == "true"
    raise ValueError


def _expected_result(
    execution_manifest_path: Path,
    result_path: Path,
    expected_columns: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, Any] | None:
    manifest = _read_mapping(execution_manifest_path, blockers, f"{field}.manifest")
    status = manifest.get("status")
    result = manifest.get("result")
    if status not in {"completed", "completed_no_rows"} or not isinstance(result, dict):
        add_blocker(
            blockers,
            "benchmark_answer_execution_incomplete",
            "Every approved query must complete before a candidate answer is recorded.",
            field=field,
        )
        return None
    if result.get("truncated") is not False or result.get("sha256") != file_sha256(result_path):
        add_blocker(
            blockers,
            "benchmark_answer_result_integrity_failed",
            "The bounded Stage 5B result is truncated or does not match its manifest hash.",
            field=field,
        )
        return None
    if not isinstance(expected_columns, list) or any(
        not isinstance(row, dict) or row.get("type") not in EXPECTED_TYPES
        for row in expected_columns
    ):
        add_blocker(
            blockers,
            "invalid_materialized_answer_columns",
            "Designed expected columns must use the benchmark comparison contract.",
            field=f"{field}.expected_columns",
        )
        return None
    names = [str(row.get("name", "")) for row in expected_columns]
    types = [str(row.get("type", "")) for row in expected_columns]
    actual_types = result.get("column_types")
    if (
        result.get("column_names") != names
        or not isinstance(actual_types, list)
        or len(actual_types) != len(types)
        or any(
            not _duckdb_type_matches(str(actual), expected)
            for actual, expected in zip(actual_types, types, strict=True)
        )
    ):
        add_blocker(
            blockers,
            "materialized_answer_schema_mismatch",
            "Stage 5B columns or DuckDB types do not match the reviewed answer design.",
            field=field,
        )
        return None
    try:
        with result_path.open(encoding="utf-8", newline="") as handle:
            parsed = list(csv.reader(handle))
    except (OSError, UnicodeError, csv.Error):
        parsed = []
    if not parsed or parsed[0] != names:
        add_blocker(
            blockers,
            "materialized_answer_csv_invalid",
            "The Stage 5B CSV header does not match the reviewed answer design.",
            field=field,
        )
        return None
    rows: list[list[Any]] = []
    string_empty_positions: list[tuple[int, int]] = []
    explicit_nulls = 0
    try:
        for row_index, row in enumerate(parsed[1:]):
            if len(row) != len(types):
                raise ValueError
            converted: list[Any] = []
            for column_index, (value, type_name) in enumerate(
                zip(row, types, strict=True)
            ):
                if value == "" and type_name == "string":
                    converted.append("")
                    string_empty_positions.append((row_index, column_index))
                elif value == "":
                    converted.append(None)
                    explicit_nulls += 1
                else:
                    converted.append(_parse_nonempty_cell(value, type_name))
            rows.append(converted)
    except (ValueError, OverflowError):
        add_blocker(
            blockers,
            "materialized_answer_value_invalid",
            "A Stage 5B CSV value cannot be represented by its reviewed comparison type.",
            field=field,
        )
        return None
    declared_nulls = result.get("null_cells")
    remaining_nulls = (
        declared_nulls - explicit_nulls
        if isinstance(declared_nulls, int) and not isinstance(declared_nulls, bool)
        else -1
    )
    if remaining_nulls == len(string_empty_positions):
        for row_index, column_index in string_empty_positions:
            rows[row_index][column_index] = None
    elif remaining_nulls != 0:
        add_blocker(
            blockers,
            "ambiguous_materialized_string_null",
            "CSV cannot safely distinguish a mixed empty string and NULL result.",
            field=field,
        )
        return None
    if (
        result.get("rows") != len(rows)
        or result.get("columns") != len(names)
        or result.get("null_cells")
        != sum(value is None for row in rows for value in row)
        or result.get("no_rows") is not (status == "completed_no_rows")
        or (status == "completed" and not rows)
        or (status == "completed_no_rows" and rows)
    ):
        add_blocker(
            blockers,
            "materialized_answer_control_mismatch",
            "Stage 5B result rows do not match their execution control totals.",
            field=field,
        )
        return None
    return {
        "status": status,
        "columns": expected_columns,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(names),
        "null_cells": result["null_cells"],
    }


def _case_evidence_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "case_id",
        "plan_sha256",
        "execution_status",
        "row_count",
        "column_count",
        "null_cells",
        "result_sha256",
        "execution_manifest_sha256",
        "authority_rechecked",
    ]
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _report(
    status: str,
    identity: dict[str, str],
    rows: list[dict[str, Any]],
    blockers: list[dict[str, str]],
    pack_path: Path | None,
) -> str:
    return "\n".join(
        [
            "# Dataset Benchmark Answer Materialization Report",
            "",
            f"- Status: `{status}`",
            f"- Dataset: `{identity.get('dataset_id') or 'invalid'}`",
            f"- Pack: `{identity.get('pack_id') or 'invalid'}`",
            f"- Approved cases completed: {len(rows)}",
            f"- Blockers: {len(blockers)}",
            f"- Candidate pack: `{pack_path.as_posix() if pack_path else 'not written'}`",
            "",
            "## Boundaries",
            "",
            "- The completed human review must bind every exact Stage 5A plan by SHA-256.",
            "- Stage 5B queries run sequentially against the bound local DuckDB in read-only mode.",
            "- Immutable authority is rechecked before every query and after collection.",
            "- Limits are fixed; no raw SQL, network, live provider, upload, training, narration, or publication is authorized.",
            "- Collected values remain candidate expected answers until a separate per-case human review and approval.",
        ]
    ) + "\n"


def _write_exact_file(path: Path, content: str, label: str) -> bool:
    if path.exists():
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            return False
        raise ValueError(
            f"A different {label} already exists at {path}. Existing evidence was not overwritten."
        )
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="")
    return True


def _existing_result(
    output_dir: Path,
    pack_output_path: Path,
    hashes: dict[str, str],
) -> AnalyticsDatasetBenchmarkMaterializationResult | None:
    existing = [output_dir / name for name in OUTPUT_NAMES if (output_dir / name).exists()]
    if not existing:
        if (output_dir / "cases").exists():
            raise ValueError(
                "Partial benchmark answer materialization evidence already exists. Use a new output directory."
            )
        return None
    if len(existing) != len(OUTPUT_NAMES) or not pack_output_path.is_file():
        raise ValueError(
            "Incomplete benchmark answer materialization evidence exists. Existing evidence was not overwritten."
        )
    manifest = yaml.safe_load(
        (output_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    ) or {}
    if (
        manifest.get("status") != "awaiting_final_review"
        or manifest.get("source") != hashes
        or manifest.get("candidate_pack_sha256") != file_sha256(pack_output_path)
    ):
        raise ValueError(
            "Different benchmark answer materialization evidence already exists. Use a new output directory."
        )
    artifact_hashes = manifest.get("artifacts")
    expected_artifacts = {
        "cases_sha256": output_dir / CASES_NAME,
        "blockers_sha256": output_dir / BLOCKERS_NAME,
        "report_sha256": output_dir / REPORT_NAME,
    }
    if not isinstance(artifact_hashes, dict) or any(
        artifact_hashes.get(name) != file_sha256(path)
        for name, path in expected_artifacts.items()
    ):
        raise ValueError(
            "Benchmark answer materialization evidence integrity failed. Existing evidence was not reused."
        )
    counts = manifest.get("counts", {})
    return AnalyticsDatasetBenchmarkMaterializationResult(
        output_dir=output_dir,
        status="awaiting_final_review",
        manifest_path=output_dir / MANIFEST_NAME,
        cases_path=output_dir / CASES_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        pack_path=pack_output_path,
        case_count=int(counts.get("cases", 0)),
        completed_count=int(counts.get("completed", 0)),
        blocker_count=0,
        outputs_changed=False,
        pack_changed=False,
    )


def run_analytics_dataset_benchmark_materialization(
    design_path: Path,
    dataset_manifest_path: Path,
    preparation_manifest_path: Path,
    execution_review_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    pack_output_path: Path,
    output_dir: Path,
) -> AnalyticsDatasetBenchmarkMaterializationResult:
    blockers: list[dict[str, str]] = []
    source_paths = _source_paths(
        design_path,
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        preparation_manifest_path,
        execution_review_path,
    )
    hashes = _current_hashes(source_paths)
    existing = _existing_result(output_dir, pack_output_path, hashes)
    if existing is not None:
        return existing

    design = _read_mapping(design_path, blockers, "design")
    preparation = _read_mapping(
        preparation_manifest_path, blockers, "preparation_manifest"
    )
    review = _read_mapping(execution_review_path, blockers, "execution_review")
    identity, preparation_cases = _validate_preparation(
        preparation, design, hashes, blockers
    )
    _validate_execution_review(
        review, identity, preparation_cases, hashes, blockers
    )

    design_cases = design.get("cases") if isinstance(design.get("cases"), list) else []
    prepared: list[tuple[dict[str, Any], dict[str, Any], Path, Path]] = []
    if not blockers:
        for index, (design_case, preparation_case) in enumerate(
            zip(design_cases, preparation_cases, strict=True)
        ):
            request_path = _resolve_preparation_artifact(
                preparation_manifest_path,
                preparation_case.get("request_path"),
                preparation_case.get("request_sha256"),
                f"preparation.cases[{index}].request_path",
                blockers,
            )
            plan_path = _resolve_preparation_artifact(
                preparation_manifest_path,
                preparation_case.get("plan_path"),
                preparation_case.get("plan_sha256"),
                f"preparation.cases[{index}].plan_path",
                blockers,
            )
            if request_path is not None and plan_path is not None:
                request = _read_mapping(
                    request_path, blockers, f"preparation.cases[{index}].request"
                )
                if request.get("question") != design_case.get("question"):
                    add_blocker(
                        blockers,
                        "materialization_question_mismatch",
                        "The prepared Stage 5A request must preserve the reviewed design question.",
                        field=f"preparation.cases[{index}].request.question",
                    )
                prepared.append(
                    (design_case, preparation_case, request_path, plan_path)
                )

    evidence_rows: list[dict[str, Any]] = []
    pack_cases: list[dict[str, Any]] = []
    if not blockers:
        for index, (design_case, preparation_case, request_path, plan_path) in enumerate(
            prepared
        ):
            if (
                not _hashes_match(hashes, source_paths)
                or file_sha256(request_path) != preparation_case["request_sha256"]
                or file_sha256(plan_path) != preparation_case["plan_sha256"]
            ):
                add_blocker(
                    blockers,
                    "benchmark_materialization_authority_changed_before_query",
                    "Immutable authority changed after review; Stage 5B was blocked.",
                    field=f"cases.{design_case['id']}",
                )
                break
            execution = run_analytics_query_execution(
                request_path,
                database_path,
                relationships_path,
                plan_path,
                output_dir
                / "cases"
                / f"case_{index + 1:03d}_{design_case['id']}"
                / "execution",
                COLLECTION_LIMITS,
            )
            if (
                not _hashes_match(hashes, source_paths)
                or file_sha256(request_path) != preparation_case["request_sha256"]
                or file_sha256(plan_path) != preparation_case["plan_sha256"]
            ):
                add_blocker(
                    blockers,
                    "benchmark_materialization_authority_changed_during_query",
                    "Immutable authority changed during Stage 5B; candidate answers were discarded.",
                    field=f"cases.{design_case['id']}",
                )
                pack_cases = []
                break
            expected = (
                _expected_result(
                    execution.manifest_path,
                    execution.result_path,
                    design_case.get("expected_columns"),
                    blockers,
                    f"cases.{design_case['id']}",
                )
                if execution.result_path is not None
                else None
            )
            execution_manifest = _read_mapping(
                execution.manifest_path,
                blockers,
                f"cases.{design_case['id']}.execution_manifest",
            )
            result = execution_manifest.get("result", {})
            evidence_rows.append(
                {
                    "case_id": design_case["id"],
                    "plan_sha256": preparation_case["plan_sha256"],
                    "execution_status": execution.status,
                    "row_count": result.get("rows", 0),
                    "column_count": result.get("columns", 0),
                    "null_cells": result.get("null_cells", 0),
                    "result_sha256": result.get("sha256", ""),
                    "execution_manifest_sha256": file_sha256(
                        execution.manifest_path
                    ),
                    "authority_rechecked": True,
                }
            )
            if expected is None:
                break
            pack_cases.append(
                {
                    "id": design_case["id"],
                    "question": design_case["question"],
                    "provider_response": design_case["provider_response"],
                    "expected_request": _read_mapping(
                        request_path,
                        blockers,
                        f"cases.{design_case['id']}.expected_request",
                    ),
                    "expected_result": expected,
                    "comparison": design_case["comparison"],
                }
            )

    if not blockers and not _hashes_match(hashes, source_paths):
        add_blocker(
            blockers,
            "benchmark_materialization_authority_changed_during_collection",
            "An immutable authority input changed during collection; candidate answers were discarded.",
            field="authority",
        )
        pack_cases = []

    pack_content = ""
    pack_changed = False
    pack_path: Path | None = None
    if not blockers and len(pack_cases) == len(design_cases):
        pack = {
            "version": 1,
            "status": "candidate_for_review",
            "pack_id": identity["pack_id"],
            "dataset_id": identity["dataset_id"],
            "bindings": {
                name: hashes[name]
                for name in (
                    "dataset_manifest_sha256",
                    "database_sha256",
                    "approved_semantic_state_sha256",
                    "approved_relationships_sha256",
                )
            },
            "cases": pack_cases,
        }
        pack_content = canonical_yaml(pack)
        with tempfile.TemporaryDirectory(prefix="dataops_candidate_pack_") as temp_name:
            temporary_pack = Path(temp_name) / "candidate.yml"
            temporary_pack.write_text(pack_content, encoding="utf-8", newline="")
            candidate = inspect_analytics_dataset_benchmark_candidate(
                dataset_manifest_path,
                database_path,
                semantic_state_path,
                relationships_path,
                temporary_pack,
            )
        for row in candidate.blockers:
            add_blocker(
                blockers,
                row.get("blocker_type", "invalid_materialized_candidate_pack"),
                row.get("explanation", "The materialized candidate pack is invalid."),
                field=row.get("field", "candidate_pack"),
            )
        if not blockers:
            pack_changed = _write_exact_file(
                pack_output_path, pack_content, "candidate expected-answer pack"
            )
            pack_path = pack_output_path

    status = "blocked" if blockers else "awaiting_final_review"
    pack_hash = (
        hashlib.sha256(pack_content.encode("utf-8")).hexdigest()
        if pack_path is not None
        else ""
    )
    cases_content = _case_evidence_csv(evidence_rows)
    blocker_content = blockers_csv(blockers)
    report_content = _report(status, identity, evidence_rows, blockers, pack_path)
    manifest = {
        "version": 1,
        "status": status,
        "workflow": "dataset_benchmark_answer_materialization",
        "identity": identity,
        "source": hashes,
        "candidate_pack_sha256": pack_hash,
        "artifacts": {
            "cases_sha256": hashlib.sha256(cases_content.encode("utf-8")).hexdigest(),
            "blockers_sha256": hashlib.sha256(
                blocker_content.encode("utf-8")
            ).hexdigest(),
            "report_sha256": hashlib.sha256(report_content.encode("utf-8")).hexdigest(),
        },
        "controls": {
            "completed_execution_review_required": True,
            "per_case_exact_plan_hash_required": True,
            "queries_executed_sequentially": True,
            "immutable_hash_recheck_before_each_query": True,
            "stage_5b_plan_revalidation_required": True,
            "database_mode": "read_only",
            "network_accessed": False,
            "live_provider_used": False,
            "external_upload_authorized": False,
            "model_training_authorized": False,
            "publication_authorized": False,
            "final_expected_answers_approved": False,
        },
        "execution_limits": {
            "max_rows": COLLECTION_LIMITS.max_rows,
            "max_result_bytes": COLLECTION_LIMITS.max_result_bytes,
            "max_runtime_seconds": COLLECTION_LIMITS.max_runtime_seconds,
            "memory_limit_mb": COLLECTION_LIMITS.memory_limit_mb,
            "threads": COLLECTION_LIMITS.threads,
            "max_temp_mb": COLLECTION_LIMITS.max_temp_mb,
        },
        "counts": {
            "cases": len(design_cases),
            "completed": len(pack_cases),
            "blockers": len(blockers),
        },
    }
    contents = {
        MANIFEST_NAME: canonical_yaml(manifest),
        CASES_NAME: cases_content,
        BLOCKERS_NAME: blocker_content,
        REPORT_NAME: report_content,
    }
    outputs_changed = write_outputs(
        output_dir,
        contents,
        OUTPUT_NAMES,
        "dataset benchmark answer materialization",
    )
    return AnalyticsDatasetBenchmarkMaterializationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        cases_path=output_dir / CASES_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        pack_path=pack_path,
        case_count=len(design_cases),
        completed_count=len(pack_cases),
        blocker_count=len(blockers),
        outputs_changed=outputs_changed,
        pack_changed=pack_changed,
    )
