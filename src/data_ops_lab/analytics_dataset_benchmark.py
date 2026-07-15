from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from .analytics_nl_translation import MAX_PROVIDER_RESPONSE_BYTES, validate_provider_response
from .analytics_query_plan import (
    ALLOWED_TOP_LEVEL_FIELDS,
    IDENTIFIER_PATTERN as OUTPUT_IDENTIFIER_PATTERN,
    add_blocker,
    approved_relationships,
    read_yaml_mapping,
)
from .analytics_semantic_adapter import MAX_QUESTION_LENGTH, validate_approved_state
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_dataset_benchmark_validation.yml"
BLOCKERS_NAME = "analytics_dataset_benchmark_blockers.csv"
REPORT_NAME = "analytics_dataset_benchmark_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_CONTROL_FILE_BYTES = 2_000_000
MAX_CASES = 100
MAX_EXPECTED_ROWS = 10_000
MAX_RESULT_COLUMNS = 128
MAX_CELL_TEXT_LENGTH = 4_000
MAX_TOLERANCES = 64
STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_TYPES = {"string", "integer", "decimal", "float", "boolean"}
NUMERIC_TYPES = {"integer", "decimal", "float"}


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkResult:
    output_dir: Path
    status: str
    manifest_path: Path
    blockers_path: Path
    report_path: Path
    blocker_count: int
    case_count: int
    exact_case_count: int
    tolerance_case_count: int
    relationship_count: int
    outputs_changed: bool


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkCandidate:
    dataset_id: str
    pack_id: str
    source: dict[str, str]
    case_ids: tuple[str, ...]
    case_count: int
    exact_case_count: int
    tolerance_case_count: int
    relationship_count: int
    blockers: tuple[dict[str, str], ...]


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(STABLE_ID_PATTERN.fullmatch(value))


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_PATTERN.fullmatch(value))


def _valid_approval_timestamp(value: Any) -> bool:
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
    for key in payload:
        if key not in allowed:
            add_blocker(
                blockers,
                "unsupported_dataset_benchmark_field",
                "The dataset benchmark input contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def _read_control_mapping(
    path: Path,
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, Any]:
    if path.is_file() and path.stat().st_size > MAX_CONTROL_FILE_BYTES:
        add_blocker(
            blockers,
            "dataset_benchmark_control_too_large",
            f"Control YAML files must be at most {MAX_CONTROL_FILE_BYTES} bytes.",
            field=field,
        )
        return {}
    return read_yaml_mapping(path, blockers, field)


def _validate_hash_bindings(
    payload: Any,
    expected: dict[str, str],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    if not isinstance(payload, dict):
        add_blocker(
            blockers,
            "invalid_benchmark_hash_bindings",
            "Hash bindings must be a mapping.",
            field=field,
        )
        return
    _reject_unknown_fields(payload, set(expected), blockers, field)
    for name, expected_hash in expected.items():
        value = payload.get(name)
        if not _valid_sha256(value) or value != expected_hash:
            add_blocker(
                blockers,
                "benchmark_hash_binding_mismatch",
                "A benchmark hash binding does not match the supplied immutable input.",
                field=f"{field}.{name}",
            )


def validate_dataset_manifest_contract(
    manifest: dict[str, Any],
    database_exists: bool,
    actual_size: int,
    actual_hash: str,
    semantic_hash: str,
    relationships_hash: str,
    blockers: list[dict[str, str]],
) -> str:
    _reject_unknown_fields(
        manifest,
        {"version", "status", "dataset", "artifact", "provenance", "license", "bindings"},
        blockers,
        "dataset_manifest",
    )
    if isinstance(manifest.get("version"), bool) or manifest.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_dataset_manifest_version",
            "The immutable dataset manifest must use version 1.",
            field="dataset_manifest.version",
        )
    if manifest.get("status") != "verified_dataset_package":
        add_blocker(
            blockers,
            "dataset_package_not_verified",
            "The dataset package must be verified before benchmark approval.",
            field="dataset_manifest.status",
        )
    dataset = manifest.get("dataset")
    dataset_id = ""
    if not isinstance(dataset, dict):
        add_blocker(
            blockers,
            "invalid_dataset_identity",
            "The dataset manifest requires a dataset mapping.",
            field="dataset_manifest.dataset",
        )
    else:
        _reject_unknown_fields(dataset, {"id", "classification", "format"}, blockers, "dataset_manifest.dataset")
        dataset_id = dataset.get("id", "")
        if not _valid_id(dataset_id):
            add_blocker(
                blockers,
                "invalid_dataset_identity",
                "Dataset IDs must be lowercase stable identifiers.",
                field="dataset_manifest.dataset.id",
            )
        if dataset.get("classification") not in {"synthetic", "public"}:
            add_blocker(
                blockers,
                "unsupported_benchmark_data_classification",
                "Version 1 permits only synthetic or public benchmark datasets.",
                field="dataset_manifest.dataset.classification",
            )
        if dataset.get("format") != "duckdb":
            add_blocker(
                blockers,
                "unsupported_benchmark_dataset_format",
                "Version 1 dataset-backed evaluation requires one local DuckDB artifact.",
                field="dataset_manifest.dataset.format",
            )

    artifact = manifest.get("artifact")
    if not database_exists:
        add_blocker(
            blockers,
            "benchmark_database_missing",
            "The local immutable DuckDB artifact is required.",
            field="database",
        )
    if not isinstance(artifact, dict):
        add_blocker(
            blockers,
            "invalid_dataset_artifact",
            "The dataset manifest requires artifact size and SHA-256.",
            field="dataset_manifest.artifact",
        )
    else:
        _reject_unknown_fields(artifact, {"bytes", "sha256"}, blockers, "dataset_manifest.artifact")
        if (
            isinstance(artifact.get("bytes"), bool)
            or not isinstance(artifact.get("bytes"), int)
            or artifact.get("bytes") <= 0
            or artifact.get("bytes") != actual_size
        ):
            add_blocker(
                blockers,
                "dataset_artifact_size_mismatch",
                "The dataset artifact size does not match its immutable manifest.",
                field="dataset_manifest.artifact.bytes",
            )
        if not _valid_sha256(artifact.get("sha256")) or artifact.get("sha256") != actual_hash:
            add_blocker(
                blockers,
                "dataset_artifact_hash_mismatch",
                "The dataset artifact SHA-256 does not match its immutable manifest.",
                field="dataset_manifest.artifact.sha256",
            )

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        add_blocker(
            blockers,
            "benchmark_provenance_not_verified",
            "The dataset manifest requires verified provenance.",
            field="dataset_manifest.provenance",
        )
    else:
        _reject_unknown_fields(provenance, {"status", "source"}, blockers, "dataset_manifest.provenance")
        if provenance.get("status") != "verified" or not isinstance(provenance.get("source"), str) or not provenance["source"].strip():
            add_blocker(
                blockers,
                "benchmark_provenance_not_verified",
                "Benchmark provenance must be verified with a non-empty source reference.",
                field="dataset_manifest.provenance",
            )

    license_payload = manifest.get("license")
    if not isinstance(license_payload, dict):
        add_blocker(
            blockers,
            "benchmark_license_not_verified",
            "The dataset manifest requires verified license metadata.",
            field="dataset_manifest.license",
        )
    else:
        _reject_unknown_fields(license_payload, {"status", "identifier"}, blockers, "dataset_manifest.license")
        if (
            license_payload.get("status") != "verified"
            or not isinstance(license_payload.get("identifier"), str)
            or not license_payload["identifier"].strip()
        ):
            add_blocker(
                blockers,
                "benchmark_license_not_verified",
                "Benchmark license status and identifier must be verified.",
                field="dataset_manifest.license",
            )
    _validate_hash_bindings(
        manifest.get("bindings"),
        {
            "approved_semantic_state_sha256": semantic_hash,
            "approved_relationships_sha256": relationships_hash,
        },
        blockers,
        "dataset_manifest.bindings",
    )
    return dataset_id


def _expected_cell_valid(value: Any, type_name: str) -> bool:
    if value is None:
        return True
    if type_name == "string":
        return isinstance(value, str) and len(value) <= MAX_CELL_TEXT_LENGTH
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "decimal":
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return False
        try:
            return Decimal(str(value)).is_finite()
        except InvalidOperation:
            return False
    return False


def _validate_expected_result(
    expected: Any,
    expected_request: dict[str, Any],
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, str]:
    if not isinstance(expected, dict):
        add_blocker(
            blockers,
            "invalid_dataset_expected_result",
            "Every benchmark case requires an expected result mapping.",
            field=field,
        )
        return {}
    _reject_unknown_fields(
        expected,
        {"status", "columns", "rows", "row_count", "column_count", "null_cells"},
        blockers,
        field,
    )
    status = expected.get("status")
    if status not in {"completed", "completed_no_rows"}:
        add_blocker(
            blockers,
            "invalid_dataset_expected_status",
            "Expected execution status must be completed or completed_no_rows.",
            field=f"{field}.status",
        )
    columns = expected.get("columns")
    column_types: dict[str, str] = {}
    if not isinstance(columns, list) or not 1 <= len(columns) <= MAX_RESULT_COLUMNS:
        add_blocker(
            blockers,
            "invalid_dataset_expected_columns",
            f"Expected results require between 1 and {MAX_RESULT_COLUMNS} columns.",
            field=f"{field}.columns",
        )
        columns = []
    for index, column in enumerate(columns):
        column_field = f"{field}.columns[{index}]"
        if not isinstance(column, dict):
            add_blocker(
                blockers,
                "invalid_dataset_expected_column",
                "Expected result columns must be name/type mappings.",
                field=column_field,
            )
            continue
        _reject_unknown_fields(column, {"name", "type"}, blockers, column_field)
        name = column.get("name")
        type_name = column.get("type")
        if not isinstance(name, str) or not OUTPUT_IDENTIFIER_PATTERN.fullmatch(name):
            add_blocker(
                blockers,
                "invalid_dataset_expected_column",
                "Expected column names must follow the Stage 5A alias grammar.",
                field=f"{column_field}.name",
            )
            continue
        if name.casefold() in {key.casefold() for key in column_types}:
            add_blocker(
                blockers,
                "duplicate_dataset_expected_column",
                "Expected result columns must be unique case-insensitively.",
                field=f"{column_field}.name",
            )
        if type_name not in EXPECTED_TYPES:
            add_blocker(
                blockers,
                "unsupported_dataset_expected_type",
                "Expected columns must use an allowlisted comparison type.",
                field=f"{column_field}.type",
            )
            continue
        column_types[name] = type_name
    rows = expected.get("rows")
    if not isinstance(rows, list) or len(rows) > MAX_EXPECTED_ROWS:
        add_blocker(
            blockers,
            "invalid_dataset_expected_rows",
            f"Expected rows must be a list of at most {MAX_EXPECTED_ROWS} rows.",
            field=f"{field}.rows",
        )
        rows = []
    column_names = list(column_types)
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(column_names):
            add_blocker(
                blockers,
                "invalid_dataset_expected_row",
                "Expected rows must contain exactly one value per declared column.",
                field=f"{field}.rows[{row_index}]",
            )
            continue
        for value_index, value in enumerate(row):
            if not _expected_cell_valid(value, column_types[column_names[value_index]]):
                add_blocker(
                    blockers,
                    "invalid_dataset_expected_value",
                    "Expected values must match their declared comparison type.",
                    field=f"{field}.rows[{row_index}][{value_index}]",
                )
    null_cells = sum(value is None for row in rows if isinstance(row, list) for value in row)
    if expected.get("row_count") != len(rows):
        add_blocker(blockers, "dataset_expected_row_count_mismatch", "Expected row_count must match the rows list.", field=f"{field}.row_count")
    if expected.get("column_count") != len(columns):
        add_blocker(blockers, "dataset_expected_column_count_mismatch", "Expected column_count must match the columns list.", field=f"{field}.column_count")
    if expected.get("null_cells") != null_cells:
        add_blocker(blockers, "dataset_expected_null_count_mismatch", "Expected null_cells must match explicit null values.", field=f"{field}.null_cells")
    if status == "completed_no_rows" and rows:
        add_blocker(blockers, "dataset_no_row_expectation_mismatch", "completed_no_rows cannot contain expected rows.", field=f"{field}.rows")
    if status == "completed" and not rows:
        add_blocker(blockers, "dataset_completed_requires_rows", "completed cases require at least one expected row.", field=f"{field}.rows")
    if len(rows) > 1 and not expected_request.get("order_by"):
        add_blocker(blockers, "dataset_deterministic_order_required", "Multi-row benchmark answers require explicit order_by.", field="expected_request.order_by")
    return column_types


def _validate_comparison(
    comparison: Any,
    column_types: dict[str, str],
    blockers: list[dict[str, str]],
    field: str,
) -> str:
    if not isinstance(comparison, dict):
        add_blocker(blockers, "invalid_dataset_comparison", "Every case requires a comparison mapping.", field=field)
        return ""
    _reject_unknown_fields(comparison, {"mode", "tolerances"}, blockers, field)
    mode = comparison.get("mode")
    tolerances = comparison.get("tolerances", [])
    if mode not in {"exact", "numeric_tolerance"}:
        add_blocker(blockers, "invalid_dataset_comparison_mode", "Comparison mode must be exact or numeric_tolerance.", field=f"{field}.mode")
        return ""
    if not isinstance(tolerances, list) or len(tolerances) > MAX_TOLERANCES:
        add_blocker(blockers, "invalid_dataset_tolerances", f"Tolerances must be a list of at most {MAX_TOLERANCES} rows.", field=f"{field}.tolerances")
        return mode
    if mode == "exact" and tolerances:
        add_blocker(blockers, "exact_comparison_tolerance_not_allowed", "Exact comparison cannot declare tolerances.", field=f"{field}.tolerances")
    if mode == "numeric_tolerance" and not tolerances:
        add_blocker(blockers, "numeric_tolerance_required", "numeric_tolerance mode requires at least one reviewed column tolerance.", field=f"{field}.tolerances")
    seen: set[str] = set()
    for index, row in enumerate(tolerances):
        tolerance_field = f"{field}.tolerances[{index}]"
        if not isinstance(row, dict):
            add_blocker(blockers, "invalid_dataset_tolerance", "Every tolerance must be a mapping.", field=tolerance_field)
            continue
        _reject_unknown_fields(row, {"column", "absolute", "relative"}, blockers, tolerance_field)
        column = row.get("column")
        absolute = row.get("absolute")
        relative = row.get("relative")
        if not isinstance(column, str) or column not in column_types or column_types.get(column) not in NUMERIC_TYPES:
            add_blocker(blockers, "invalid_dataset_tolerance_column", "Tolerances may reference only declared numeric result columns.", field=f"{tolerance_field}.column")
        elif column.casefold() in seen:
            add_blocker(blockers, "duplicate_dataset_tolerance", "Each result column may declare one tolerance.", field=f"{tolerance_field}.column")
        else:
            seen.add(column.casefold())
        values_valid = all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and value >= 0
            for value in (absolute, relative)
        )
        if not values_valid or relative > 1 or (absolute == 0 and relative == 0):
            add_blocker(blockers, "invalid_dataset_tolerance_value", "Tolerance values must be finite, non-negative, not both zero, and relative must be at most 1.", field=tolerance_field)
    return mode


def _validate_benchmark_pack(
    pack: dict[str, Any],
    dataset_id: str,
    expected_bindings: dict[str, str],
    blockers: list[dict[str, str]],
) -> tuple[str, int, int, int, tuple[str, ...]]:
    _reject_unknown_fields(pack, {"version", "status", "pack_id", "dataset_id", "bindings", "cases"}, blockers, "benchmark_pack")
    if isinstance(pack.get("version"), bool) or pack.get("version") != 1:
        add_blocker(blockers, "unsupported_benchmark_pack_version", "The dataset benchmark pack must use version 1.", field="benchmark_pack.version")
    if pack.get("status") != "candidate_for_review":
        add_blocker(blockers, "invalid_benchmark_pack_status", "Benchmark packs remain candidate_for_review until separate approval is validated.", field="benchmark_pack.status")
    pack_id = pack.get("pack_id", "")
    if not _valid_id(pack_id):
        add_blocker(blockers, "invalid_benchmark_pack_id", "Benchmark pack IDs must be lowercase stable identifiers.", field="benchmark_pack.pack_id")
    if pack.get("dataset_id") != dataset_id:
        add_blocker(blockers, "benchmark_dataset_id_mismatch", "The benchmark pack dataset ID must match the immutable dataset manifest.", field="benchmark_pack.dataset_id")
    _validate_hash_bindings(pack.get("bindings"), expected_bindings, blockers, "benchmark_pack.bindings")
    cases = pack.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        add_blocker(blockers, "invalid_dataset_benchmark_cases", f"A dataset benchmark pack requires between 1 and {MAX_CASES} cases.", field="benchmark_pack.cases")
        return str(pack_id), 0, 0, 0, ()
    seen_ids: set[str] = set()
    exact_count = 0
    tolerance_count = 0
    for index, case in enumerate(cases):
        field = f"benchmark_pack.cases[{index}]"
        if not isinstance(case, dict):
            add_blocker(blockers, "invalid_dataset_benchmark_case", "Every benchmark case must be a mapping.", field=field)
            continue
        _reject_unknown_fields(case, {"id", "question", "provider_response", "expected_request", "expected_result", "comparison"}, blockers, field)
        case_id = case.get("id")
        if not _valid_id(case_id):
            add_blocker(blockers, "invalid_dataset_benchmark_case_id", "Benchmark case IDs must be lowercase stable identifiers.", field=f"{field}.id")
        elif case_id in seen_ids:
            add_blocker(blockers, "duplicate_dataset_benchmark_case_id", "Benchmark case IDs must be unique.", field=f"{field}.id")
        else:
            seen_ids.add(case_id)
        question = case.get("question")
        if not isinstance(question, str) or not question.strip() or len(question.strip()) > MAX_QUESTION_LENGTH:
            add_blocker(blockers, "invalid_dataset_benchmark_question", f"Benchmark questions must contain at most {MAX_QUESTION_LENGTH} characters.", field=f"{field}.question")
        response_blockers: list[dict[str, str]] = []
        validate_provider_response(case.get("provider_response"), response_blockers)
        response = case.get("provider_response")
        if response_blockers or len(yaml.safe_dump(response).encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
            add_blocker(blockers, "invalid_dataset_provider_response", "Recorded provider responses must satisfy the bounded safe semantic contract.", field=f"{field}.provider_response")
        expected_request = case.get("expected_request")
        if not isinstance(expected_request, dict):
            add_blocker(blockers, "invalid_dataset_expected_request", "Every benchmark case requires an expected Stage 5A request.", field=f"{field}.expected_request")
            expected_request = {}
        else:
            for key in expected_request:
                if key not in ALLOWED_TOP_LEVEL_FIELDS:
                    add_blocker(blockers, "unsupported_dataset_expected_request_field", "Expected requests must use only the Stage 5A version-1 contract.", field=f"{field}.expected_request.{key}")
            if expected_request.get("version") != 1:
                add_blocker(blockers, "invalid_dataset_expected_request_version", "Expected requests must use Stage 5A version 1.", field=f"{field}.expected_request.version")
            if isinstance(question, str) and expected_request.get("question") != question.strip():
                add_blocker(blockers, "dataset_expected_question_mismatch", "Expected requests must preserve the authoritative benchmark question.", field=f"{field}.expected_request.question")
        column_types = _validate_expected_result(case.get("expected_result"), expected_request, blockers, f"{field}.expected_result")
        mode = _validate_comparison(case.get("comparison"), column_types, blockers, f"{field}.comparison")
        exact_count += mode == "exact"
        tolerance_count += mode == "numeric_tolerance"
    return str(pack_id), len(cases), exact_count, tolerance_count, tuple(sorted(seen_ids))


def _validate_approval(
    approval: dict[str, Any],
    dataset_id: str,
    pack_id: str,
    expected_source: dict[str, str],
    blockers: list[dict[str, str]],
) -> None:
    _reject_unknown_fields(approval, {"version", "status", "dataset_id", "pack_id", "source", "review_evidence", "decision", "approved_by", "approved_at"}, blockers, "benchmark_approval")
    if isinstance(approval.get("version"), bool) or approval.get("version") != 1 or approval.get("status") != "approved":
        add_blocker(blockers, "benchmark_evaluation_not_approved", "Dataset-backed evaluation requires a separate approved version-1 decision.", field="benchmark_approval.status")
    if approval.get("dataset_id") != dataset_id or approval.get("pack_id") != pack_id:
        add_blocker(blockers, "benchmark_approval_identity_mismatch", "Benchmark approval IDs must match the dataset and pack.", field="benchmark_approval")
    _validate_hash_bindings(approval.get("source"), expected_source, blockers, "benchmark_approval.source")
    review_evidence = approval.get("review_evidence")
    if not isinstance(review_evidence, dict):
        add_blocker(blockers, "invalid_benchmark_review_evidence", "Benchmark approval requires hash-bound human review evidence.", field="benchmark_approval.review_evidence")
    else:
        _reject_unknown_fields(review_evidence, {"review_sha256", "decision_digest"}, blockers, "benchmark_approval.review_evidence")
        for name in ("review_sha256", "decision_digest"):
            if not _valid_sha256(review_evidence.get(name)):
                add_blocker(blockers, "invalid_benchmark_review_evidence", "Review evidence requires SHA-256 review and decision digests.", field=f"benchmark_approval.review_evidence.{name}")
    decision = approval.get("decision")
    required_true = {
        "local_offline_evaluation_approved",
        "recorded_provider_responses_reviewed",
        "expected_requests_reviewed",
        "expected_results_reviewed",
        "comparison_policy_reviewed",
    }
    required_false = {"live_provider_use_approved", "external_upload_approved", "model_training_approved"}
    if not isinstance(decision, dict):
        add_blocker(blockers, "invalid_benchmark_approval_decision", "Benchmark approval requires explicit bounded decisions.", field="benchmark_approval.decision")
    else:
        _reject_unknown_fields(decision, required_true | required_false, blockers, "benchmark_approval.decision")
        for name in required_true:
            if decision.get(name) is not True:
                add_blocker(blockers, "benchmark_evaluation_not_approved", "All offline benchmark review gates must be explicitly approved.", field=f"benchmark_approval.decision.{name}")
        for name in required_false:
            if decision.get(name) is not False:
                add_blocker(blockers, "benchmark_approval_scope_invalid", "Offline benchmark approval cannot authorize live providers, upload, or model training.", field=f"benchmark_approval.decision.{name}")
    if not isinstance(approval.get("approved_by"), str) or not approval["approved_by"].strip():
        add_blocker(blockers, "invalid_benchmark_approval_identity", "Benchmark approval requires a human identity.", field="benchmark_approval.approved_by")
    if not _valid_approval_timestamp(approval.get("approved_at")):
        add_blocker(blockers, "invalid_benchmark_approval_time", "Benchmark approval requires an ISO-8601 timestamp with a timezone.", field="benchmark_approval.approved_at")


def _blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["blocker_id", "blocker_type", "field", "explanation"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def _render_report(status: str, dataset_id: str, pack_id: str, blockers: list[dict[str, str]], case_count: int, exact_count: int, tolerance_count: int) -> str:
    return "\n".join(
        [
            "# Analytics Dataset Benchmark Validation Report",
            "",
            f"- Status: `{status}`",
            f"- Dataset: `{dataset_id or 'invalid'}`",
            f"- Pack: `{pack_id or 'invalid'}`",
            f"- Cases: {case_count}",
            f"- Exact comparisons: {exact_count}",
            f"- Numeric-tolerance comparisons: {tolerance_count}",
            f"- Blockers: {len(blockers)}",
            "",
            "## Boundaries",
            "",
            "- The database artifact is hashed as an opaque local file and is never opened.",
            "- No catalog, table, row, query, result, provider, or network access is used.",
            "- Dataset, semantics, relationships, pack, and approval must match by SHA-256.",
            "- Provenance, license, expected answers, and offline use require explicit review.",
            "- This dry-run does not execute or authorize a live-provider benchmark.",
        ]
    ) + "\n"


def _write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Dataset benchmark output is not a directory: {output_dir}")
    existing = ({path.name: path for path in output_dir.iterdir() if path.is_file() and path.name in OUTPUT_NAMES} if output_dir.exists() else {})
    if existing:
        exact = set(existing) == set(contents) and all(existing[name].read_text(encoding="utf-8") == content for name, content in contents.items())
        if exact:
            return False
        raise ValueError(f"Different dataset benchmark evidence already exists in {output_dir}. Use a new output directory; existing generated evidence was not overwritten.")
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def inspect_analytics_dataset_benchmark_candidate(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
) -> AnalyticsDatasetBenchmarkCandidate:
    blockers: list[dict[str, str]] = []
    semantic_state = _read_control_mapping(semantic_state_path, blockers, "semantic_state")
    validate_approved_state(semantic_state, blockers)
    relationships = _read_control_mapping(relationships_path, blockers, "approved_relationships")
    _reject_unknown_fields(
        relationships,
        {"approved_relationships"},
        blockers,
        "approved_relationships",
    )
    relationship_blockers: list[dict[str, str]] = []
    approved = approved_relationships(relationships, relationship_blockers)
    if relationship_blockers:
        add_blocker(blockers, "invalid_benchmark_relationship_registry", "The approved relationship registry is invalid.", field="approved_relationships")

    database_exists = database_path.is_file()
    database_size = 0
    database_hash = ""
    if database_exists:
        before = database_path.stat()
        database_hash = file_sha256(database_path)
        after = database_path.stat()
        database_size = after.st_size
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            add_blocker(
                blockers,
                "dataset_artifact_changed_during_validation",
                "The dataset artifact changed while its immutable identity was being validated.",
                field="database",
            )
    actual_hashes = {
        "database_sha256": database_hash,
        "approved_semantic_state_sha256": file_sha256(semantic_state_path) if semantic_state_path.is_file() else "",
        "approved_relationships_sha256": file_sha256(relationships_path) if relationships_path.is_file() else "",
    }
    dataset_manifest = _read_control_mapping(dataset_manifest_path, blockers, "dataset_manifest")
    dataset_id = validate_dataset_manifest_contract(
        dataset_manifest,
        database_exists,
        database_size,
        actual_hashes["database_sha256"],
        actual_hashes["approved_semantic_state_sha256"],
        actual_hashes["approved_relationships_sha256"],
        blockers,
    )
    manifest_hash = file_sha256(dataset_manifest_path) if dataset_manifest_path.is_file() else ""
    pack = _read_control_mapping(benchmark_pack_path, blockers, "benchmark_pack")
    pack_id, case_count, exact_count, tolerance_count, case_ids = _validate_benchmark_pack(
        pack,
        dataset_id,
        {"dataset_manifest_sha256": manifest_hash, **actual_hashes},
        blockers,
    )
    source = {
        "dataset_manifest_sha256": manifest_hash,
        **actual_hashes,
        "benchmark_pack_sha256": file_sha256(benchmark_pack_path) if benchmark_pack_path.is_file() else "",
    }
    return AnalyticsDatasetBenchmarkCandidate(
        dataset_id=dataset_id,
        pack_id=pack_id,
        source=source,
        case_ids=case_ids,
        case_count=case_count,
        exact_case_count=exact_count,
        tolerance_case_count=tolerance_count,
        relationship_count=len(approved),
        blockers=tuple(blockers),
    )


def run_analytics_dataset_benchmark_validation(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    benchmark_approval_path: Path,
    output_dir: Path,
) -> AnalyticsDatasetBenchmarkResult:
    candidate = inspect_analytics_dataset_benchmark_candidate(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
    )
    blockers = list(candidate.blockers)
    approval = _read_control_mapping(benchmark_approval_path, blockers, "benchmark_approval")
    _validate_approval(
        approval,
        candidate.dataset_id,
        candidate.pack_id,
        candidate.source,
        blockers,
    )
    status = "blocked" if blockers else "ready_for_offline_evaluation"
    safe_dataset_id = candidate.dataset_id if _valid_id(candidate.dataset_id) else ""
    safe_pack_id = candidate.pack_id if _valid_id(candidate.pack_id) else ""
    manifest = {
        "version": 1,
        "status": status,
        "dataset_id": safe_dataset_id,
        "pack_id": safe_pack_id,
        "source": {
            **candidate.source,
            "benchmark_approval_sha256": file_sha256(benchmark_approval_path) if benchmark_approval_path.is_file() else "",
        },
        "controls": {
            "database_hashed": database_path.is_file(),
            "database_opened": False,
            "database_rows_read": False,
            "query_executed": False,
            "network_accessed": False,
            "live_provider_used": False,
            "external_upload_authorized": False,
            "model_training_authorized": False,
        },
        "counts": {
            "cases": candidate.case_count,
            "exact_comparisons": candidate.exact_case_count,
            "numeric_tolerance_comparisons": candidate.tolerance_case_count,
            "approved_relationships": candidate.relationship_count,
            "blockers": len(blockers),
        },
    }
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: _blockers_csv(blockers),
        REPORT_NAME: _render_report(status, safe_dataset_id, safe_pack_id, blockers, candidate.case_count, candidate.exact_case_count, candidate.tolerance_case_count),
    }
    outputs_changed = _write_outputs(output_dir, contents)
    return AnalyticsDatasetBenchmarkResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        blocker_count=len(blockers),
        case_count=candidate.case_count,
        exact_case_count=candidate.exact_case_count,
        tolerance_case_count=candidate.tolerance_case_count,
        relationship_count=candidate.relationship_count,
        outputs_changed=outputs_changed,
    )
