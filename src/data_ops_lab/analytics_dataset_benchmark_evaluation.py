from __future__ import annotations

import csv
import io
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from .analytics_dataset_benchmark import run_analytics_dataset_benchmark_validation
from .analytics_nl_translation import RecordedSemanticIntentProvider, run_analytics_nl_translation
from .analytics_query_execution import AnalyticsExecutionLimits, run_analytics_query_execution
from .analytics_query_plan import add_blocker, run_analytics_query_plan
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_dataset_benchmark_evaluation.yml"
CASES_NAME = "analytics_dataset_benchmark_evaluation_cases.csv"
BLOCKERS_NAME = "analytics_dataset_benchmark_evaluation_blockers.csv"
REPORT_NAME = "analytics_dataset_benchmark_evaluation_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, CASES_NAME, BLOCKERS_NAME, REPORT_NAME}

EVALUATION_LIMITS = AnalyticsExecutionLimits(
    max_rows=10_000,
    max_result_bytes=10_000_000,
    max_runtime_seconds=30,
    memory_limit_mb=512,
    threads=1,
    max_temp_mb=256,
)


class DatasetBenchmarkAuthorityDrift(RuntimeError):
    pass


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkEvaluationResult:
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


def _source_paths(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    benchmark_approval_path: Path,
) -> dict[str, Path]:
    return {
        "dataset_manifest_sha256": dataset_manifest_path,
        "database_sha256": database_path,
        "approved_semantic_state_sha256": semantic_state_path,
        "approved_relationships_sha256": relationships_path,
        "benchmark_pack_sha256": benchmark_pack_path,
        "benchmark_approval_sha256": benchmark_approval_path,
    }


def _hashes_match(expected: dict[str, str], paths: dict[str, Path]) -> bool:
    return all(
        path.is_file() and expected.get(name) == file_sha256(path)
        for name, path in paths.items()
    )


def _copy_validation_blockers(path: Path, blockers: list[dict[str, str]]) -> None:
    if not path.is_file():
        add_blocker(
            blockers,
            "dataset_benchmark_validation_evidence_missing",
            "The prerequisite dataset benchmark validation did not produce blocker evidence.",
            field="authority",
        )
        return
    initial_count = len(blockers)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            add_blocker(
                blockers,
                row.get("blocker_type", "dataset_benchmark_authority_blocked"),
                row.get("explanation", "Dataset benchmark authority validation failed."),
                field=row.get("field", "authority"),
            )
    if len(blockers) == initial_count:
        add_blocker(
            blockers,
            "dataset_benchmark_authority_blocked",
            "Dataset benchmark authority validation did not reach ready status.",
            field="authority",
        )


def _expected_csv(expected: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([column["name"] for column in expected["columns"]])
    writer.writerows(expected["rows"])
    return buffer.getvalue()


def _csv_cell(value: Any) -> str:
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerow([value])
    return next(csv.reader(io.StringIO(buffer.getvalue())))[0]


def _decimal(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _numeric_cell_matches(
    actual: str,
    expected: Any,
    absolute: Any,
    relative: Any,
) -> bool:
    if expected is None:
        return actual == ""
    actual_decimal = _decimal(actual)
    expected_decimal = _decimal(expected)
    absolute_decimal = _decimal(absolute)
    relative_decimal = _decimal(relative)
    if None in (actual_decimal, expected_decimal, absolute_decimal, relative_decimal):
        return False
    assert actual_decimal is not None
    assert expected_decimal is not None
    assert absolute_decimal is not None
    assert relative_decimal is not None
    difference = abs(actual_decimal - expected_decimal)
    allowed = max(absolute_decimal, relative_decimal * abs(expected_decimal))
    return difference <= allowed


def _numeric_tolerance_match(
    actual_csv: str,
    expected: dict[str, Any],
    comparison: dict[str, Any],
) -> bool:
    parsed = list(csv.reader(io.StringIO(actual_csv)))
    if not parsed:
        return False
    column_names = [column["name"] for column in expected["columns"]]
    if parsed[0] != column_names or len(parsed[1:]) != len(expected["rows"]):
        return False
    tolerances = {row["column"]: row for row in comparison["tolerances"]}
    for actual_row, expected_row in zip(parsed[1:], expected["rows"], strict=True):
        if len(actual_row) != len(column_names):
            return False
        for index, (actual, expected_value) in enumerate(
            zip(actual_row, expected_row, strict=True)
        ):
            tolerance = tolerances.get(column_names[index])
            if tolerance:
                if not _numeric_cell_matches(
                    actual,
                    expected_value,
                    tolerance["absolute"],
                    tolerance["relative"],
                ):
                    return False
            elif actual != _csv_cell(expected_value):
                return False
    return True


def _result_matches(
    result_path: Path | None,
    expected: dict[str, Any],
    comparison: dict[str, Any],
) -> bool:
    if result_path is None or not result_path.is_file():
        return False
    actual_csv = result_path.read_text(encoding="utf-8")
    if comparison["mode"] == "exact":
        return actual_csv == _expected_csv(expected)
    return _numeric_tolerance_match(actual_csv, expected, comparison)


def _controls_match(execution_manifest_path: Path, expected: dict[str, Any]) -> bool:
    manifest = yaml.safe_load(execution_manifest_path.read_text(encoding="utf-8")) or {}
    result = manifest.get("result", {})
    return all(
        (
            result.get("rows") == expected["row_count"],
            result.get("columns") == expected["column_count"],
            result.get("column_names") == [column["name"] for column in expected["columns"]],
            result.get("null_cells") == expected["null_cells"],
            result.get("no_rows") == (expected["status"] == "completed_no_rows"),
            result.get("truncated") is False,
        )
    )


def _case_row(
    case: dict[str, Any],
    semantic_state_path: Path,
    database_path: Path,
    relationships_path: Path,
    case_dir: Path,
    expected_hashes: dict[str, str],
    source_paths: dict[str, Path],
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
    authority_rechecked = False

    if translation_status == "ready_for_query_plan" and request_match:
        assert translation.adapter_result is not None
        assert translation.adapter_result.request_path is not None
        plan = run_analytics_query_plan(
            translation.adapter_result.request_path,
            database_path,
            relationships_path,
            case_dir / "plan",
        )
        planning_status = plan.status
        if planning_status == "ready_for_execution_review":
            authority_rechecked = True
            if not _hashes_match(expected_hashes, source_paths):
                raise DatasetBenchmarkAuthorityDrift
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
            result_match = _result_matches(
                execution.result_path,
                expected,
                case["comparison"],
            )
            controls_match = _controls_match(execution.manifest_path, expected)

    pipeline_match = (
        translation_status == "ready_for_query_plan"
        and request_match
        and planning_status == "ready_for_execution_review"
        and execution_status == case["expected_result"]["status"]
    )
    passed = pipeline_match and result_match and controls_match
    return {
        "case_id": case["id"],
        "comparison_mode": case["comparison"]["mode"],
        "translation_status": translation_status,
        "request_match": request_match,
        "planning_status": planning_status,
        "authority_rechecked": authority_rechecked,
        "execution_status": execution_status,
        "pipeline_match": pipeline_match,
        "result_match": result_match,
        "controls_match": controls_match,
        "passed": passed,
    }


def _failed_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "comparison_mode": case["comparison"]["mode"],
        "translation_status": "evaluation_error",
        "request_match": False,
        "planning_status": "not_run",
        "authority_rechecked": False,
        "execution_status": "not_run",
        "pipeline_match": False,
        "result_match": False,
        "controls_match": False,
        "passed": False,
    }


def _metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    passed = sum(bool(row[field]) for row in rows)
    count = len(rows)
    return {
        "passed": passed,
        "evaluated": count,
        "rate": round(passed / count, 6) if count else None,
    }


def _mode_metric(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    selected = [row for row in rows if row["comparison_mode"] == mode]
    return _metric(selected, "result_match")


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall": _metric(rows, "passed"),
        "pipeline_accuracy": _metric(rows, "pipeline_match"),
        "request_accuracy": _metric(rows, "request_match"),
        "result_accuracy": _metric(rows, "result_match"),
        "control_accuracy": _metric(rows, "controls_match"),
        "exact_result_accuracy": _mode_metric(rows, "exact"),
        "numeric_tolerance_accuracy": _mode_metric(rows, "numeric_tolerance"),
    }


def _cases_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "case_id",
        "comparison_mode",
        "translation_status",
        "request_match",
        "planning_status",
        "authority_rechecked",
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
    dataset_id: str,
    pack_id: str,
    rows: list[dict[str, Any]],
    blockers: list[dict[str, str]],
    metrics: dict[str, Any],
) -> str:
    lines = [
        "# Analytics Dataset Benchmark Evaluation Report",
        "",
        f"- Status: `{status}`",
        f"- Dataset: `{dataset_id or 'invalid'}`",
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
            f"- {name.replace('_', ' ').title()}: "
            f"{metric['passed']}/{metric['evaluated']} ({rate})"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Full dataset, semantic, relationship, pack, and approval authority is validated before evaluation.",
            "- Every execution-ready case rechecks all immutable SHA-256 bindings before Stage 5B.",
            "- Recorded Stage 5D responses are used offline; no live provider or network is available.",
            "- Exact Stage 5A requests gate planning and Stage 5B revalidates plans before read-only queries.",
            "- Exact comparison is default; numeric tolerance applies only to explicitly reviewed columns.",
            "- Runtime questions, responses, requests, plans, results, and case directories are temporary.",
            "- Persistent evidence omits questions, responses, expected rows, actual rows, SQL, and parameters.",
            "- This evaluation does not authorize upload, model training, narration, or a live provider.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Dataset benchmark evaluation output is not a directory: {output_dir}")
    existing = ({path.name: path for path in output_dir.iterdir() if path.is_file() and path.name in OUTPUT_NAMES} if output_dir.exists() else {})
    if existing:
        exact = set(existing) == set(contents) and all(existing[name].read_text(encoding="utf-8") == content for name, content in contents.items())
        if exact:
            return False
        raise ValueError(f"Different dataset benchmark evaluation evidence already exists in {output_dir}. Use a new output directory; existing evidence was not overwritten.")
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_dataset_benchmark_evaluation(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    benchmark_approval_path: Path,
    output_dir: Path,
) -> AnalyticsDatasetBenchmarkEvaluationResult:
    blockers: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    source: dict[str, str] = {}
    dataset_id = ""
    pack_id = ""
    paths = _source_paths(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
        benchmark_approval_path,
    )
    with tempfile.TemporaryDirectory(prefix="dataops_dataset_benchmark_") as temp_name:
        temp_dir = Path(temp_name)
        validation = run_analytics_dataset_benchmark_validation(
            dataset_manifest_path,
            database_path,
            semantic_state_path,
            relationships_path,
            benchmark_pack_path,
            benchmark_approval_path,
            temp_dir / "authority_validation",
        )
        validation_manifest = yaml.safe_load(
            validation.manifest_path.read_text(encoding="utf-8")
        ) or {}
        source = validation_manifest.get("source", {})
        dataset_id = validation_manifest.get("dataset_id", "")
        pack_id = validation_manifest.get("pack_id", "")
        if validation.status != "ready_for_offline_evaluation":
            _copy_validation_blockers(validation.blockers_path, blockers)
        elif not _hashes_match(source, paths):
            add_blocker(
                blockers,
                "dataset_benchmark_authority_changed_before_evaluation",
                "An immutable benchmark input changed after authority validation.",
                field="authority",
            )
        else:
            pack = yaml.safe_load(benchmark_pack_path.read_text(encoding="utf-8")) or {}
            for index, case in enumerate(pack["cases"]):
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
                            source,
                            paths,
                        )
                    )
                except DatasetBenchmarkAuthorityDrift:
                    add_blocker(
                        blockers,
                        "dataset_benchmark_authority_changed_before_query",
                        "An immutable benchmark input changed after planning; query execution was blocked.",
                        field=f"case.{case['id']}",
                    )
                    rows = []
                    break
                except Exception:
                    rows.append(_failed_case(case))
            if not blockers and not _hashes_match(source, paths):
                add_blocker(
                    blockers,
                    "dataset_benchmark_inputs_changed_during_evaluation",
                    "An immutable benchmark input changed during evaluation; case evidence was discarded.",
                    field="authority",
                )
                rows = []

    status = "blocked" if blockers else "passed" if all(row["passed"] for row in rows) else "failed"
    metrics = _metrics(rows)
    passed_count = sum(bool(row["passed"]) for row in rows)
    manifest = {
        "version": 1,
        "status": status,
        "dataset_id": dataset_id,
        "pack_id": pack_id,
        "source": source,
        "controls": {
            "generated_approval_required": True,
            "immutable_hash_recheck_before_query": True,
            "recorded_provider_only": True,
            "expected_request_gate_required": True,
            "stage_5a_plan_required": True,
            "stage_5b_revalidation_required": True,
            "database_mode": "read_only",
            "network_accessed": False,
            "live_provider_used": False,
            "external_upload_authorized": False,
            "model_training_authorized": False,
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
        REPORT_NAME: _render_report(status, dataset_id, pack_id, rows, blockers, metrics),
    }
    outputs_changed = _write_outputs(output_dir, contents)
    return AnalyticsDatasetBenchmarkEvaluationResult(
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
