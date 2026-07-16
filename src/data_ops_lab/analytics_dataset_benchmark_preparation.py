from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .analytics_dataset_benchmark import (
    EXPECTED_TYPES,
    MAX_CONTROL_FILE_BYTES,
    MAX_TOLERANCES,
    NUMERIC_TYPES,
    validate_dataset_manifest_contract,
)
from .analytics_nl_translation import (
    MAX_PROVIDER_RESPONSE_BYTES,
    validate_provider_response,
)
from .analytics_query_plan import (
    IDENTIFIER_PATTERN as OUTPUT_IDENTIFIER_PATTERN,
    add_blocker,
    approved_relationships,
    read_yaml_mapping,
)
from .analytics_semantic_adapter import MAX_QUESTION_LENGTH, validate_approved_state
from .analytics_session import (
    blockers_csv,
    canonical_yaml,
    database_identity,
    run_analytics_session_prepare,
    write_outputs,
)
from .contracts.source_bindings import declared_file_sha256_bindings
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_dataset_benchmark_preparation.yml"
BLOCKERS_NAME = "analytics_dataset_benchmark_preparation_blockers.csv"
REPORT_NAME = "analytics_dataset_benchmark_preparation_report.md"
REVIEW_NAME = "analytics_dataset_benchmark_execution_review.yml"
OUTPUT_NAMES = {MANIFEST_NAME, BLOCKERS_NAME, REPORT_NAME, REVIEW_NAME}
MAX_DESIGN_CASES = 25
STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
COVERAGE_VALUES = {
    "table_selection",
    "dimension_selection",
    "measure_selection",
    "filter_selection",
    "order_selection",
    "relationship_selection",
    "exact_answer",
    "tolerance_answer",
    "null_filter",
    "no_rows",
}
RESULT_SHAPES = {"single_row", "ordered_rows"}
SCOPE_DECISIONS = (
    "local_read_only_answer_collection",
    "live_provider_use",
    "external_upload",
    "model_training",
    "publication",
)


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkPreparationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    review_path: Path | None
    blockers_path: Path
    report_path: Path
    case_count: int
    ready_case_count: int
    blocker_count: int
    outputs_changed: bool


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(STABLE_ID_PATTERN.fullmatch(value))


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
                "unsupported_benchmark_preparation_field",
                "The benchmark answer design contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def _read_design(path: Path, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if path.is_file() and path.stat().st_size > MAX_CONTROL_FILE_BYTES:
        add_blocker(
            blockers,
            "benchmark_answer_design_too_large",
            f"The benchmark answer design must be at most {MAX_CONTROL_FILE_BYTES} bytes.",
            field="design",
        )
        return {}
    return read_yaml_mapping(path, blockers, "design")


def _copy_provider_blockers(
    source: list[dict[str, str]],
    target: list[dict[str, str]],
    field: str,
) -> None:
    for row in source:
        nested = row.get("field", "")
        if nested.startswith("provider_response."):
            nested = nested.removeprefix("provider_response.")
        add_blocker(
            target,
            row.get("blocker_type", "invalid_dataset_provider_response"),
            row.get("explanation", "The recorded provider response is invalid."),
            field=f"{field}.{nested}" if nested else field,
        )


def _validate_expected_columns(
    payload: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, str]:
    if not isinstance(payload, list) or not payload:
        add_blocker(
            blockers,
            "invalid_benchmark_design_columns",
            "Every answer-design case requires at least one typed expected output column.",
            field=field,
        )
        return {}
    columns: dict[str, str] = {}
    folded: set[str] = set()
    for index, row in enumerate(payload):
        row_field = f"{field}[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_benchmark_design_column",
                "Expected output columns must be name/type mappings.",
                field=row_field,
            )
            continue
        _reject_unknown_fields(row, {"name", "type"}, blockers, row_field)
        name = row.get("name")
        type_name = row.get("type")
        if not isinstance(name, str) or not OUTPUT_IDENTIFIER_PATTERN.fullmatch(name):
            add_blocker(
                blockers,
                "invalid_benchmark_design_column",
                "Expected output names must follow the Stage 5A alias grammar.",
                field=f"{row_field}.name",
            )
            continue
        if name.casefold() in folded:
            add_blocker(
                blockers,
                "duplicate_benchmark_design_column",
                "Expected output columns must be unique case-insensitively.",
                field=f"{row_field}.name",
            )
        folded.add(name.casefold())
        if type_name not in EXPECTED_TYPES:
            add_blocker(
                blockers,
                "unsupported_benchmark_design_type",
                "Expected output columns must use a dataset-benchmark comparison type.",
                field=f"{row_field}.type",
            )
            continue
        columns[name] = type_name
    return columns


def _valid_tolerance_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _validate_comparison(
    payload: Any,
    columns: dict[str, str],
    blockers: list[dict[str, str]],
    field: str,
) -> str:
    if not isinstance(payload, dict):
        add_blocker(
            blockers,
            "invalid_benchmark_design_comparison",
            "Every answer-design case requires a comparison policy.",
            field=field,
        )
        return ""
    _reject_unknown_fields(payload, {"mode", "tolerances"}, blockers, field)
    mode = payload.get("mode")
    tolerances = payload.get("tolerances", [])
    if mode not in {"exact", "numeric_tolerance"}:
        add_blocker(
            blockers,
            "invalid_benchmark_design_comparison",
            "Comparison mode must be exact or numeric_tolerance.",
            field=f"{field}.mode",
        )
        return ""
    if not isinstance(tolerances, list) or len(tolerances) > MAX_TOLERANCES:
        add_blocker(
            blockers,
            "invalid_benchmark_design_tolerances",
            f"Tolerances must be a list of at most {MAX_TOLERANCES} entries.",
            field=f"{field}.tolerances",
        )
        return str(mode)
    if mode == "exact" and tolerances:
        add_blocker(
            blockers,
            "exact_benchmark_design_tolerance_not_allowed",
            "Exact comparison cannot declare tolerances.",
            field=f"{field}.tolerances",
        )
    if mode == "numeric_tolerance" and not tolerances:
        add_blocker(
            blockers,
            "benchmark_design_tolerance_required",
            "numeric_tolerance requires at least one typed column tolerance.",
            field=f"{field}.tolerances",
        )
    seen: set[str] = set()
    for index, row in enumerate(tolerances):
        row_field = f"{field}.tolerances[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_benchmark_design_tolerance",
                "Every tolerance must be a mapping.",
                field=row_field,
            )
            continue
        _reject_unknown_fields(row, {"column", "absolute", "relative"}, blockers, row_field)
        column = row.get("column")
        absolute = row.get("absolute")
        relative = row.get("relative")
        if (
            not isinstance(column, str)
            or column not in columns
            or columns.get(column) not in NUMERIC_TYPES
        ):
            add_blocker(
                blockers,
                "invalid_benchmark_design_tolerance_column",
                "Tolerance may target only a declared numeric expected column.",
                field=f"{row_field}.column",
            )
        elif column.casefold() in seen:
            add_blocker(
                blockers,
                "duplicate_benchmark_design_tolerance",
                "Each expected column may declare one tolerance.",
                field=f"{row_field}.column",
            )
        else:
            seen.add(column.casefold())
        if (
            not _valid_tolerance_number(absolute)
            or not _valid_tolerance_number(relative)
            or relative > 1
            or (absolute == 0 and relative == 0)
        ):
            add_blocker(
                blockers,
                "invalid_benchmark_design_tolerance_value",
                "Tolerance values must be finite, non-negative, not both zero, and relative at most 1.",
                field=row_field,
            )
    return str(mode)


def _validate_cases(
    payload: Any,
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not 1 <= len(payload) <= MAX_DESIGN_CASES:
        add_blocker(
            blockers,
            "invalid_benchmark_answer_design_cases",
            f"The answer design requires between 1 and {MAX_DESIGN_CASES} cases.",
            field="design.cases",
        )
        return []
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, case in enumerate(payload):
        field = f"design.cases[{index}]"
        if not isinstance(case, dict):
            add_blocker(
                blockers,
                "invalid_benchmark_answer_design_case",
                "Every answer-design case must be a mapping.",
                field=field,
            )
            continue
        _reject_unknown_fields(
            case,
            {
                "id",
                "coverage",
                "question",
                "provider_response",
                "result_shape",
                "expected_columns",
                "comparison",
            },
            blockers,
            field,
        )
        case_id = case.get("id")
        if not _valid_id(case_id):
            add_blocker(
                blockers,
                "invalid_benchmark_answer_design_case_id",
                "Case IDs must be lowercase stable identifiers.",
                field=f"{field}.id",
            )
        elif case_id in seen:
            add_blocker(
                blockers,
                "duplicate_benchmark_answer_design_case_id",
                "Case IDs must be unique.",
                field=f"{field}.id",
            )
        else:
            seen.add(case_id)
        coverage = case.get("coverage")
        if (
            not isinstance(coverage, list)
            or not coverage
            or any(item not in COVERAGE_VALUES for item in coverage)
            or len(set(coverage)) != len(coverage)
        ):
            add_blocker(
                blockers,
                "invalid_benchmark_answer_design_coverage",
                "Coverage must be a non-empty unique list of version-1 capability labels.",
                field=f"{field}.coverage",
            )
        question = case.get("question")
        if (
            not isinstance(question, str)
            or not question.strip()
            or question != question.strip()
            or len(question) > MAX_QUESTION_LENGTH
        ):
            add_blocker(
                blockers,
                "invalid_benchmark_answer_design_question",
                f"Questions must be trimmed non-empty text of at most {MAX_QUESTION_LENGTH} characters.",
                field=f"{field}.question",
            )
        provider_response = case.get("provider_response")
        provider_blockers: list[dict[str, str]] = []
        validate_provider_response(provider_response, provider_blockers)
        if (
            provider_blockers
            or len(yaml.safe_dump(provider_response).encode("utf-8"))
            > MAX_PROVIDER_RESPONSE_BYTES
        ):
            _copy_provider_blockers(
                provider_blockers,
                blockers,
                f"{field}.provider_response",
            )
            if not provider_blockers:
                add_blocker(
                    blockers,
                    "benchmark_answer_design_provider_response_too_large",
                    "The recorded provider response exceeds the bounded provider contract.",
                    field=f"{field}.provider_response",
                )
        result_shape = case.get("result_shape")
        if result_shape not in RESULT_SHAPES:
            add_blocker(
                blockers,
                "invalid_benchmark_answer_design_result_shape",
                "Result shape must be single_row or ordered_rows.",
                field=f"{field}.result_shape",
            )
        columns = _validate_expected_columns(
            case.get("expected_columns"), blockers, f"{field}.expected_columns"
        )
        mode = _validate_comparison(
            case.get("comparison"), columns, blockers, f"{field}.comparison"
        )
        normalized_coverage = list(coverage) if isinstance(coverage, list) else []
        if mode == "exact" and "exact_answer" not in normalized_coverage:
            add_blocker(
                blockers,
                "benchmark_answer_design_coverage_mismatch",
                "Exact comparison cases must declare exact_answer coverage.",
                field=f"{field}.coverage",
            )
        if mode == "numeric_tolerance" and "tolerance_answer" not in normalized_coverage:
            add_blocker(
                blockers,
                "benchmark_answer_design_coverage_mismatch",
                "Tolerance cases must declare tolerance_answer coverage.",
                field=f"{field}.coverage",
            )
        cases.append(case)
    return cases


def _validate_design_identity(
    design: dict[str, Any],
    dataset_id: str,
    expected_bindings: dict[str, str],
    blockers: list[dict[str, str]],
) -> tuple[str, str]:
    _reject_unknown_fields(
        design,
        {"version", "status", "design_id", "pack_id", "dataset_id", "bindings", "cases"},
        blockers,
        "design",
    )
    if design.get("version") != 1 or isinstance(design.get("version"), bool):
        add_blocker(
            blockers,
            "unsupported_benchmark_answer_design_version",
            "The benchmark answer design must use version 1.",
            field="design.version",
        )
    if design.get("status") != "candidate_for_execution_review":
        add_blocker(
            blockers,
            "invalid_benchmark_answer_design_status",
            "The design must remain candidate_for_execution_review until exact plans are reviewed.",
            field="design.status",
        )
    design_id = design.get("design_id", "")
    pack_id = design.get("pack_id", "")
    for name, value in (("design_id", design_id), ("pack_id", pack_id)):
        if not _valid_id(value):
            add_blocker(
                blockers,
                "invalid_benchmark_answer_design_id",
                "Design and future pack IDs must be lowercase stable identifiers.",
                field=f"design.{name}",
            )
    if design.get("dataset_id") != dataset_id:
        add_blocker(
            blockers,
            "benchmark_answer_design_dataset_mismatch",
            "The answer design dataset must match the verified dataset package.",
            field="design.dataset_id",
        )
    bindings = design.get("bindings")
    if not isinstance(bindings, dict):
        add_blocker(
            blockers,
            "invalid_benchmark_answer_design_bindings",
            "The answer design requires exact source hash bindings.",
            field="design.bindings",
        )
    else:
        _reject_unknown_fields(bindings, set(expected_bindings), blockers, "design.bindings")
        for name, expected in expected_bindings.items():
            if bindings.get(name) != expected:
                add_blocker(
                    blockers,
                    "benchmark_answer_design_binding_mismatch",
                    "An answer-design binding does not match the supplied immutable source.",
                    field=f"design.bindings.{name}",
                )
    return str(design_id), str(pack_id)


def _write_exact(path: Path, content: str, label: str) -> bool:
    if path.exists():
        if not path.is_file():
            raise ValueError(f"{label} is not a file: {path}")
        if path.read_text(encoding="utf-8") == content:
            return False
        raise ValueError(
            f"A different {label} already exists at {path}. Existing evidence was not overwritten."
        )
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="")
    return True


def _relative(output_dir: Path, path: Path) -> str:
    return path.relative_to(output_dir).as_posix()


def _expected_aliases(request: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for collection in (request.get("dimensions", []), request.get("metrics", [])):
        if isinstance(collection, list):
            for row in collection:
                if isinstance(row, dict) and isinstance(row.get("alias"), str):
                    aliases.append(row["alias"])
    return aliases


def _validate_request_shape(
    case: dict[str, Any],
    request: dict[str, Any],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    expected_names = [row["name"] for row in case["expected_columns"]]
    aliases = _expected_aliases(request)
    if aliases != expected_names:
        add_blocker(
            blockers,
            "benchmark_answer_design_output_mismatch",
            "The deterministic Stage 5D request aliases do not match the designed output columns in order.",
            field=f"{field}.expected_columns",
        )
    dimensions = request.get("dimensions", [])
    order_by = request.get("order_by", [])
    if case.get("result_shape") == "single_row" and dimensions:
        add_blocker(
            blockers,
            "benchmark_answer_design_shape_mismatch",
            "single_row cases cannot group by dimensions.",
            field=f"{field}.result_shape",
        )
    if case.get("result_shape") == "ordered_rows" and (
        not isinstance(dimensions, list)
        or not dimensions
        or not isinstance(order_by, list)
        or not order_by
    ):
        add_blocker(
            blockers,
            "benchmark_answer_design_order_required",
            "ordered_rows cases require at least one dimension and explicit Stage 5A order_by.",
            field=f"{field}.result_shape",
        )


def _render_report(
    status: str,
    design_id: str,
    rows: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> str:
    lines = [
        "# Dataset Benchmark Answer Preparation Report",
        "",
        f"- Status: `{status}`",
        f"- Design: `{design_id or 'invalid'}`",
        f"- Cases: {len(rows)}",
        f"- Review-ready plans: {sum(row.get('plan_status') == 'ready_for_execution_review' for row in rows)}",
        f"- Blockers: {len(blockers)}",
        "",
        "## Cases",
        "",
        "| Case | Translation | Plan | Exact plan evidence |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['case_id']}` | `{row['translation_status']}` | "
            f"`{row['plan_status']}` | `{row.get('plan_path', '')}` |"
        )
    if not rows:
        lines.append("| none | not started | not started | |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Preparation uses recorded English semantic intents and the approved semantic registry.",
            "- Stage 5A opens only the bound local DuckDB catalog read-only to compile exact plans.",
            "- Stage 5B is not called; no table rows, query results, live provider, or network are used.",
            "- The pending review binds the complete preparation manifest and every exact plan hash.",
            "- Approval of answer collection will not approve the final expected answers or benchmark evaluation.",
        ]
    )
    return "\n".join(lines) + "\n"


def _review_template(
    manifest_content: str,
    identity: dict[str, str],
    source: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "pending_human_review",
        "source": {
            "preparation_manifest_sha256": hashlib.sha256(
                manifest_content.encode("utf-8")
            ).hexdigest(),
            "design_sha256": source["design_sha256"],
            "dataset_manifest_sha256": source["dataset_manifest_sha256"],
            "database_sha256": source["database_sha256"],
            "approved_semantic_state_sha256": source[
                "approved_semantic_state_sha256"
            ],
            "approved_relationships_sha256": source[
                "approved_relationships_sha256"
            ],
        },
        "identity": identity,
        "review": {
            "reviewer": "",
            "reviewed_at": "",
            "scope_decisions": [
                {"scope": scope, "decision": "pending", "notes": ""}
                for scope in SCOPE_DECISIONS
            ],
            "case_decisions": [
                {
                    "case_id": row["case_id"],
                    "reviewed_plan_sha256": row["plan_sha256"],
                    "decision": "pending",
                    "notes": "",
                }
                for row in rows
            ],
        },
    }


def run_analytics_dataset_benchmark_preparation(
    design_path: Path,
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    output_dir: Path,
) -> AnalyticsDatasetBenchmarkPreparationResult:
    blockers: list[dict[str, str]] = []
    source_paths = {
        "design_sha256": design_path,
        "dataset_manifest_sha256": dataset_manifest_path,
        "approved_semantic_state_sha256": semantic_state_path,
        "approved_relationships_sha256": relationships_path,
    }
    source_hashes = declared_file_sha256_bindings(source_paths)
    database_before = database_identity(database_path)
    database_hash = ""
    database_size = 0
    if database_path.is_file():
        before = database_path.stat()
        database_hash = file_sha256(database_path)
        after = database_path.stat()
        database_size = after.st_size
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            add_blocker(
                blockers,
                "benchmark_database_changed_during_preparation",
                "The benchmark database changed while its immutable identity was being hashed.",
                field="database",
            )

    semantic_state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")
    validate_approved_state(semantic_state, blockers)
    relationships = read_yaml_mapping(relationships_path, blockers, "approved_relationships")
    relationship_blockers: list[dict[str, str]] = []
    approved_relationships(relationships, relationship_blockers)
    if relationship_blockers:
        add_blocker(
            blockers,
            "invalid_benchmark_preparation_relationships",
            "The approved relationship registry is invalid.",
            field="approved_relationships",
        )
    dataset_manifest = read_yaml_mapping(
        dataset_manifest_path, blockers, "dataset_manifest"
    )
    dataset_id = validate_dataset_manifest_contract(
        dataset_manifest,
        database_path.is_file(),
        database_size,
        database_hash,
        source_hashes["approved_semantic_state_sha256"],
        source_hashes["approved_relationships_sha256"],
        blockers,
    )
    design = _read_design(design_path, blockers)
    expected_bindings = {
        "dataset_manifest_sha256": source_hashes["dataset_manifest_sha256"],
        "database_sha256": database_hash,
        "approved_semantic_state_sha256": source_hashes[
            "approved_semantic_state_sha256"
        ],
        "approved_relationships_sha256": source_hashes[
            "approved_relationships_sha256"
        ],
    }
    design_id, pack_id = _validate_design_identity(
        design, dataset_id, expected_bindings, blockers
    )
    cases = _validate_cases(design.get("cases"), blockers) if design else []

    rows: list[dict[str, Any]] = []
    nested_changed = False
    if not blockers:
        for index, case in enumerate(cases):
            case_dir = output_dir / "cases" / f"case_{index + 1:03d}_{case['id']}"
            question_path = case_dir / "question.txt"
            response_path = case_dir / "recorded_semantic_intent.yml"
            nested_changed |= _write_exact(
                question_path, f"{case['question']}\n", "benchmark question evidence"
            )
            nested_changed |= _write_exact(
                response_path,
                yaml.safe_dump(
                    case["provider_response"], sort_keys=False, allow_unicode=False
                ),
                "recorded semantic intent evidence",
            )
            session = run_analytics_session_prepare(
                question_path,
                semantic_state_path,
                response_path,
                database_path,
                relationships_path,
                case_dir / "session_prepare",
            )
            nested_changed |= session.outputs_changed
            request_path = (
                session.translation_result.adapter_result.request_path
                if session.translation_result.adapter_result is not None
                else None
            )
            plan_path = session.plan_result.plan_path if session.plan_result else None
            request: dict[str, Any] = {}
            if request_path is not None and request_path.is_file():
                request = read_yaml_mapping(request_path, blockers, f"cases.{case['id']}.request")
                _validate_request_shape(case, request, blockers, f"cases.{case['id']}")
            if session.status != "awaiting_execution_review" or plan_path is None:
                add_blocker(
                    blockers,
                    "benchmark_answer_case_not_review_ready",
                    "Every answer-design case must produce an exact Stage 5A plan before aggregate review.",
                    field=f"cases.{case['id']}",
                )
            rows.append(
                {
                    "case_id": case["id"],
                    "coverage": list(case["coverage"]),
                    "result_shape": case["result_shape"],
                    "expected_columns": list(case["expected_columns"]),
                    "comparison": case["comparison"],
                    "translation_status": session.translation_result.status,
                    "plan_status": session.plan_result.status if session.plan_result else "not_started",
                    "session_manifest_path": _relative(output_dir, session.manifest_path),
                    "session_manifest_sha256": file_sha256(session.manifest_path),
                    "request_path": _relative(output_dir, request_path) if request_path else "",
                    "request_sha256": file_sha256(request_path) if request_path and request_path.is_file() else "",
                    "plan_path": _relative(output_dir, plan_path) if plan_path else "",
                    "plan_sha256": file_sha256(plan_path) if plan_path and plan_path.is_file() else "",
                }
            )

    current_source_hashes = declared_file_sha256_bindings(source_paths)
    current_database = database_identity(database_path)
    current_database_hash = file_sha256(database_path) if database_path.is_file() else ""
    if (
        current_source_hashes != source_hashes
        or current_database != database_before
        or current_database_hash != database_hash
    ):
        add_blocker(
            blockers,
            "benchmark_preparation_source_drift",
            "A benchmark preparation authority input changed during planning.",
            field="source",
        )

    status = "blocked" if blockers else "awaiting_execution_review"
    coverage_counts = {
        label: sum(label in row.get("coverage", []) for row in rows)
        for label in sorted(COVERAGE_VALUES)
    }
    source = {
        **source_hashes,
        "database_sha256": database_hash,
        "database": database_before,
    }
    identity = {
        "dataset_id": dataset_id,
        "design_id": design_id,
        "pack_id": pack_id,
    }
    manifest = {
        "version": 1,
        "status": status,
        "workflow": "dataset_benchmark_answer_preparation",
        "identity": identity,
        "source": source,
        "cases": rows,
        "controls": {
            "recorded_semantic_intents_only": True,
            "network_access": False,
            "database_catalog_read_only": True,
            "table_rows_read": False,
            "query_execution_authorized": False,
            "human_plan_review_required": True,
            "final_expected_answers_approved": False,
            "live_provider_authorized": False,
        },
        "counts": {
            "cases": len(rows),
            "review_ready_plans": sum(
                row.get("plan_status") == "ready_for_execution_review" for row in rows
            ),
            "blockers": len(blockers),
            "coverage": coverage_counts,
        },
        "review_template": REVIEW_NAME if status == "awaiting_execution_review" else "",
    }
    manifest_content = canonical_yaml(manifest)
    contents = {
        MANIFEST_NAME: manifest_content,
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: _render_report(status, design_id, rows, blockers),
    }
    review_path: Path | None = None
    if status == "awaiting_execution_review":
        contents[REVIEW_NAME] = canonical_yaml(
            _review_template(manifest_content, identity, source, rows)
        )
        review_path = output_dir / REVIEW_NAME
    root_changed = write_outputs(
        output_dir,
        contents,
        OUTPUT_NAMES,
        "dataset benchmark answer preparation",
    )
    ready_count = sum(
        row.get("plan_status") == "ready_for_execution_review" for row in rows
    )
    return AnalyticsDatasetBenchmarkPreparationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        review_path=review_path,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        case_count=len(rows),
        ready_case_count=ready_count,
        blocker_count=len(blockers),
        outputs_changed=root_changed or nested_changed,
    )
