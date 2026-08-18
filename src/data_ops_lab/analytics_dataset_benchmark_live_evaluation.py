from __future__ import annotations

import csv
import ctypes
import io
import math
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from .analytics_dataset_benchmark import run_analytics_dataset_benchmark_validation
from .analytics_dataset_benchmark_evaluation import (
    EVALUATION_LIMITS,
    DatasetBenchmarkAuthorityDrift,
    _controls_match,
    _copy_validation_blockers,
    _hashes_match,
    _result_matches,
    _source_paths,
)
from .analytics_nl_translation import (
    MAX_PROVIDER_TIMEOUT_SECONDS,
    SemanticIntentProvider,
    run_analytics_nl_translation,
)
from .analytics_query_execution import run_analytics_query_execution
from .analytics_query_plan import add_blocker, read_yaml_mapping, run_analytics_query_plan
from .contracts.atomic_publish import (
    DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
    AtomicPublishTargetAppearedError,
    publish_new_directory,
)
from .ollama_provider import validate_loopback_endpoint
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_dataset_benchmark_live_evaluation.yml"
CASES_NAME = "analytics_dataset_benchmark_live_evaluation_cases.csv"
BLOCKERS_NAME = "analytics_dataset_benchmark_live_evaluation_blockers.csv"
REPORT_NAME = "analytics_dataset_benchmark_live_evaluation_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, CASES_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_AUTHORIZATION_BYTES = 64_000
OUTPUT_PUBLISH_RETRY_DELAYS_SECONDS = (
    DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS
)

LIVE_DECISIONS = {
    "local_loopback_provider_evaluation_approved": True,
    "local_read_only_answer_evaluation_approved": True,
    "external_provider_approved": False,
    "external_upload_approved": False,
    "model_training_approved": False,
    "narration_approved": False,
    "publication_approved": False,
}


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkLiveEvaluationResult:
    output_dir: Path
    status: str
    mode: str
    manifest_path: Path
    cases_path: Path
    blockers_path: Path
    report_path: Path
    case_count: int
    passed_count: int
    failed_count: int
    blocker_count: int
    provider_call_count: int
    outputs_changed: bool


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
                "unsupported_live_evaluation_authorization_field",
                "The live-evaluation authorization contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def _timezone_aware(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _read_authorization(
    path: Path,
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(
            blockers,
            "live_evaluation_authorization_missing",
            "A separate completed live-evaluation authorization is required.",
            field="live_authorization",
        )
        return {}
    if path.stat().st_size > MAX_AUTHORIZATION_BYTES:
        add_blocker(
            blockers,
            "live_evaluation_authorization_too_large",
            f"The live-evaluation authorization must be at most {MAX_AUTHORIZATION_BYTES} bytes.",
            field="live_authorization",
        )
        return {}
    return read_yaml_mapping(path, blockers, "live_authorization")


def _provider_config(
    provider: SemanticIntentProvider,
    timeout_seconds: int,
) -> dict[str, Any]:
    return {
        "name": getattr(provider, "name", ""),
        "mode": getattr(provider, "mode", ""),
        "endpoint": getattr(provider, "endpoint", ""),
        "model": getattr(provider, "model", ""),
        "context_tokens": getattr(provider, "context_tokens", None),
        "max_output_tokens": getattr(provider, "max_output_tokens", None),
        "timeout_seconds": timeout_seconds,
        "prompt_contract_version": getattr(provider, "prompt_contract_version", ""),
    }


def _validate_live_authorization(
    authorization_path: Path,
    expected_source: dict[str, str],
    dataset_id: str,
    pack_id: str,
    case_ids: list[str],
    provider: SemanticIntentProvider,
    timeout_seconds: int,
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    authorization = _read_authorization(authorization_path, blockers)
    if not authorization:
        return {}
    _reject_unknown_fields(
        authorization,
        {
            "version",
            "status",
            "dataset_id",
            "pack_id",
            "source",
            "provider",
            "execution",
            "decision",
            "authorized_by",
            "authorized_at",
            "notes",
        },
        blockers,
        "live_authorization",
    )
    if authorization.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_live_evaluation_authorization_version",
            "Live-evaluation authorization version must be 1.",
            field="live_authorization.version",
        )
    if authorization.get("status") != "approved_live_evaluation":
        add_blocker(
            blockers,
            "live_evaluation_not_approved",
            "Live-evaluation authorization status must be approved_live_evaluation.",
            field="live_authorization.status",
        )
    if authorization.get("dataset_id") != dataset_id or authorization.get("pack_id") != pack_id:
        add_blocker(
            blockers,
            "live_evaluation_identity_mismatch",
            "Live-evaluation authorization must identify the exact validated dataset and pack.",
            field="live_authorization.identity",
        )

    source = authorization.get("source")
    if not isinstance(source, dict) or source != expected_source:
        add_blocker(
            blockers,
            "live_evaluation_source_mismatch",
            "Live-evaluation authorization must bind every validated benchmark source hash exactly.",
            field="live_authorization.source",
        )

    expected_provider = _provider_config(provider, timeout_seconds)
    provider_payload = authorization.get("provider")
    if isinstance(provider_payload, dict):
        _reject_unknown_fields(
            provider_payload,
            set(expected_provider),
            blockers,
            "live_authorization.provider",
        )
    if provider_payload != expected_provider:
        add_blocker(
            blockers,
            "live_evaluation_provider_mismatch",
            "The provider configuration must exactly match the completed live-evaluation authorization.",
            field="live_authorization.provider",
        )
    if getattr(provider, "network_access_required", None) is not True:
        add_blocker(
            blockers,
            "live_evaluation_provider_not_network_gated",
            "The authorized live provider must require explicit per-invocation network opt-in.",
            field="provider.network_access_required",
        )
    provider_endpoint = getattr(provider, "endpoint", "")
    provider_model = getattr(provider, "model", "")
    try:
        normalized_endpoint = validate_loopback_endpoint(provider_endpoint)
    except ValueError:
        normalized_endpoint = ""
    if (
        getattr(provider, "mode", "") != "local_live"
        or not isinstance(provider_model, str)
        or getattr(provider, "name", "") != f"ollama:{provider_model}"
        or normalized_endpoint != provider_endpoint
    ):
        add_blocker(
            blockers,
            "live_evaluation_provider_not_loopback_ollama",
            "Version 1 live evaluation accepts only the exact literal-loopback Ollama provider boundary.",
            field="provider",
        )
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or not 1 <= timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS
    ):
        add_blocker(
            blockers,
            "live_evaluation_timeout_invalid",
            f"Provider timeout must be between 1 and {MAX_PROVIDER_TIMEOUT_SECONDS} seconds.",
            field="provider.timeout_seconds",
        )

    expected_execution = {
        "case_ids": case_ids,
        "max_cases": len(case_ids),
        "sequential": True,
        "expected_request_gate": True,
        "read_only_stage_5b": True,
        "continue_after_case_mismatch": True,
        "alias_normalization": "reviewed_expected_aliases_only_after_non_alias_request_match",
    }
    execution = authorization.get("execution")
    if isinstance(execution, dict):
        _reject_unknown_fields(
            execution,
            set(expected_execution),
            blockers,
            "live_authorization.execution",
        )
    if execution != expected_execution:
        add_blocker(
            blockers,
            "live_evaluation_execution_scope_mismatch",
            "Live-evaluation authorization must bind the exact ordered cases and fixed execution controls.",
            field="live_authorization.execution",
        )

    decision = authorization.get("decision")
    if isinstance(decision, dict):
        _reject_unknown_fields(
            decision,
            set(LIVE_DECISIONS),
            blockers,
            "live_authorization.decision",
        )
    if decision != LIVE_DECISIONS:
        add_blocker(
            blockers,
            "live_evaluation_scope_not_bounded",
            "Live evaluation must be approved locally while external provider, upload, training, narration, and publication remain disabled.",
            field="live_authorization.decision",
        )

    if not isinstance(authorization.get("authorized_by"), str) or not authorization["authorized_by"].strip():
        add_blocker(
            blockers,
            "live_evaluation_authorizer_missing",
            "A human authorizer identity is required.",
            field="live_authorization.authorized_by",
        )
    if not _timezone_aware(authorization.get("authorized_at")):
        add_blocker(
            blockers,
            "live_evaluation_authorized_at_invalid",
            "authorized_at must be an ISO-8601 timestamp with a timezone.",
            field="live_authorization.authorized_at",
        )
    if not isinstance(authorization.get("notes"), str) or not authorization["notes"].strip():
        add_blocker(
            blockers,
            "live_evaluation_authorization_notes_missing",
            "Live-evaluation authorization requires non-empty human notes.",
            field="live_authorization.notes",
        )
    return authorization


def _semantic_response_signature(payload: dict[str, Any]) -> dict[str, Any]:
    dimensions = payload.get("dimensions", [])
    metrics = payload.get("metrics", [])
    alias_to_term: dict[str, str] = {}
    dimension_terms: list[str] = []
    metric_terms: list[str] = []
    for rows, target in ((dimensions, dimension_terms), (metrics, metric_terms)):
        if not isinstance(rows, list):
            return {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("term"), str):
                return {}
            term = row["term"]
            target.append(term)
            alias = row.get("alias")
            if isinstance(alias, str):
                alias_to_term[alias] = term
    order_signature: list[dict[str, str]] = []
    order_by = payload.get("order_by", [])
    if not isinstance(order_by, list):
        return {}
    for row in order_by:
        if not isinstance(row, dict):
            return {}
        field = row.get("field")
        direction = row.get("direction")
        if not isinstance(field, str) or not isinstance(direction, str):
            return {}
        order_signature.append(
            {
                "term": alias_to_term.get(field, field),
                "direction": direction,
            }
        )
    return {
        "version": payload.get("version"),
        "from": payload.get("from"),
        "relationship_paths": payload.get("relationship_paths", []),
        "dimensions": dimension_terms,
        "metrics": metric_terms,
        "filters": payload.get("filters", []),
        "order_by": order_signature,
        "limit": payload.get("limit"),
    }


def _intent_matches(
    translation: Any,
    expected_response: dict[str, Any],
) -> tuple[bool, bool]:
    intent_path = translation.intent_path
    if intent_path is None or not intent_path.is_file():
        return False, False
    intent = yaml.safe_load(intent_path.read_text(encoding="utf-8")) or {}
    if not isinstance(intent, dict):
        return False, False
    intent.pop("question", None)
    return (
        intent == expected_response,
        _semantic_response_signature(intent) == _semantic_response_signature(expected_response),
    )


def _canonicalize_request_aliases(
    actual: dict[str, Any] | None,
    expected: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, dict[str, bool]]:
    semantic_components = {
        "dimensions_semantic_match": False,
        "metrics_semantic_match": False,
        "order_by_semantic_match": False,
    }
    if not isinstance(actual, dict):
        return False, None, semantic_components
    canonical = deepcopy(actual)
    alias_map: dict[str, str] = {}
    for name, identity_fields, metric_name in (
        ("dimensions", ("column",), "dimensions_semantic_match"),
        ("metrics", ("function", "column"), "metrics_semantic_match"),
    ):
        actual_rows = canonical.get(name)
        expected_rows = expected.get(name)
        if not isinstance(actual_rows, list) or not isinstance(expected_rows, list):
            return False, None, semantic_components
        if len(actual_rows) != len(expected_rows):
            return False, None, semantic_components
        identities_match = True
        for actual_row, expected_row in zip(actual_rows, expected_rows, strict=True):
            if not isinstance(actual_row, dict) or not isinstance(expected_row, dict):
                return False, None, semantic_components
            if any(actual_row.get(field) != expected_row.get(field) for field in identity_fields):
                identities_match = False
                continue
            actual_alias = actual_row.get("alias")
            expected_alias = expected_row.get("alias")
            if not isinstance(actual_alias, str) or not isinstance(expected_alias, str):
                return False, None, semantic_components
            alias_map[actual_alias] = expected_alias
            actual_row["alias"] = expected_alias
        semantic_components[metric_name] = identities_match
    actual_order = canonical.get("order_by")
    expected_order = expected.get("order_by")
    if not isinstance(actual_order, list) or not isinstance(expected_order, list):
        return False, None, semantic_components
    for row in actual_order:
        if not isinstance(row, dict) or not isinstance(row.get("field"), str):
            return False, None, semantic_components
        row["field"] = alias_map.get(row["field"], row["field"])
    semantic_components["order_by_semantic_match"] = actual_order == expected_order
    return canonical == expected, canonical, semantic_components


def _component_matches(
    actual: dict[str, Any] | None,
    expected: dict[str, Any],
) -> dict[str, bool]:
    if not isinstance(actual, dict):
        return {
            "from_match": False,
            "joins_match": False,
            "dimensions_match": False,
            "metrics_match": False,
            "filters_match": False,
            "order_by_match": False,
            "limit_match": False,
        }
    return {
        "from_match": actual.get("from") == expected.get("from"),
        "joins_match": actual.get("joins") == expected.get("joins"),
        "dimensions_match": actual.get("dimensions") == expected.get("dimensions"),
        "metrics_match": actual.get("metrics") == expected.get("metrics"),
        "filters_match": actual.get("filters") == expected.get("filters"),
        "order_by_match": actual.get("order_by") == expected.get("order_by"),
        "limit_match": actual.get("limit") == expected.get("limit"),
    }


def _provider_outcome(translation: Any) -> str:
    if translation.status == "ready_for_query_plan":
        return "accepted"
    if translation.status == "clarification_required":
        return "clarification"
    blocker_types: set[str] = set()
    if translation.blockers_path.is_file():
        with translation.blockers_path.open(newline="", encoding="utf-8") as handle:
            blocker_types = {row.get("blocker_type", "") for row in csv.DictReader(handle)}
    if "provider_timeout" in blocker_types:
        return "timeout"
    if "provider_failure" in blocker_types:
        return "provider_failure"
    return "rejected"


def _safe_provider_metrics(provider: SemanticIntentProvider) -> dict[str, Any]:
    raw = getattr(provider, "last_metrics", {})
    if not isinstance(raw, dict):
        return {}
    allowed = {
        "request_bytes",
        "prompt_tokens",
        "completion_tokens",
        "total_duration_ms",
        "load_duration_ms",
        "prompt_eval_duration_ms",
        "eval_duration_ms",
    }
    return {key: raw.get(key) for key in allowed}


def _sample_resources(
    resource_sampler: Callable[[], dict[str, Any]] | None,
) -> dict[str, Any]:
    if resource_sampler is None:
        return {}
    try:
        sample = resource_sampler()
    except Exception:
        return {}
    return sample if isinstance(sample, dict) else {}


def _empty_case_row(case: dict[str, Any], outcome: str) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "comparison_mode": case["comparison"]["mode"],
        "provider_outcome": outcome,
        "provider_called": False,
        "translation_status": "not_run",
        "semantic_intent_exact_match": False,
        "semantic_intent_match": False,
        "from_match": False,
        "joins_match": False,
        "dimensions_match": False,
        "dimensions_semantic_match": False,
        "metrics_match": False,
        "metrics_semantic_match": False,
        "filters_match": False,
        "order_by_match": False,
        "order_by_semantic_match": False,
        "limit_match": False,
        "request_exact_match": False,
        "request_match": False,
        "planning_status": "not_run",
        "authority_rechecked": False,
        "execution_status": "not_run",
        "pipeline_match": False,
        "result_match": False,
        "controls_match": False,
        "passed": False,
        "provider_wall_duration_ms": None,
        "case_wall_duration_ms": None,
        "request_bytes": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_total_duration_ms": None,
        "provider_load_duration_ms": None,
        "provider_prompt_eval_duration_ms": None,
        "provider_eval_duration_ms": None,
        "system_available_memory_mb": None,
        "gpu_used_memory_mb": None,
    }


def _evaluation_error_case_row(
    case: dict[str, Any],
    provider: SemanticIntentProvider,
    resource_sampler: Callable[[], dict[str, Any]] | None,
) -> dict[str, Any]:
    row = _empty_case_row(case, "evaluation_error")
    provider_metrics = _safe_provider_metrics(provider)
    resource_metrics = _sample_resources(resource_sampler)
    row.update(
        {
            # Once the provider boundary is entered, evidence is conservative: an
            # unexpected failure must never under-report a possible network call.
            "provider_called": True,
            "request_bytes": provider_metrics.get("request_bytes"),
            "prompt_tokens": provider_metrics.get("prompt_tokens"),
            "completion_tokens": provider_metrics.get("completion_tokens"),
            "provider_total_duration_ms": provider_metrics.get("total_duration_ms"),
            "provider_load_duration_ms": provider_metrics.get("load_duration_ms"),
            "provider_prompt_eval_duration_ms": provider_metrics.get("prompt_eval_duration_ms"),
            "provider_eval_duration_ms": provider_metrics.get("eval_duration_ms"),
            "system_available_memory_mb": resource_metrics.get("system_available_memory_mb"),
            "gpu_used_memory_mb": resource_metrics.get("gpu_used_memory_mb"),
        }
    )
    return row


def _case_row(
    case: dict[str, Any],
    semantic_state_path: Path,
    database_path: Path,
    relationships_path: Path,
    case_dir: Path,
    expected_hashes: dict[str, str],
    source_paths: dict[str, Path],
    provider: SemanticIntentProvider,
    timeout_seconds: int,
    resource_sampler: Callable[[], dict[str, Any]] | None,
) -> dict[str, Any]:
    row = _empty_case_row(case, "evaluation_error")
    question_path = case_dir / "question.txt"
    question_path.write_text(case["question"].strip() + "\n", encoding="utf-8", newline="")
    case_started = time.perf_counter_ns()
    provider_started = time.perf_counter_ns()
    translation = run_analytics_nl_translation(
        question_path,
        semantic_state_path,
        case_dir / "translation",
        provider,
        timeout_seconds=timeout_seconds,
        allow_network=True,
    )
    provider_wall_duration_ms = round((time.perf_counter_ns() - provider_started) / 1_000_000, 3)
    actual_request = translation.adapter_result.request if translation.adapter_result else None
    request_exact_match = actual_request == case["expected_request"]
    request_match, canonical_request, semantic_components = _canonicalize_request_aliases(
        actual_request,
        case["expected_request"],
    )
    component_matches = _component_matches(actual_request, case["expected_request"])
    planning_status = "not_run"
    execution_status = "not_run"
    result_match = False
    controls_match = False
    authority_rechecked = False

    if translation.status == "ready_for_query_plan" and request_match:
        assert canonical_request is not None
        canonical_request_path = case_dir / "canonical_request.yml"
        canonical_request_path.write_text(
            yaml.safe_dump(canonical_request, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
            newline="",
        )
        plan = run_analytics_query_plan(
            canonical_request_path,
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
                canonical_request_path,
                database_path,
                relationships_path,
                plan.plan_path,
                case_dir / "execution",
                EVALUATION_LIMITS,
            )
            execution_status = execution.status
            expected = case["expected_result"]
            result_match = _result_matches(execution.result_path, expected, case["comparison"])
            controls_match = _controls_match(execution.manifest_path, expected)

    pipeline_match = (
        translation.status == "ready_for_query_plan"
        and request_match
        and planning_status == "ready_for_execution_review"
        and execution_status == case["expected_result"]["status"]
    )
    provider_metrics = _safe_provider_metrics(provider)
    resource_metrics = _sample_resources(resource_sampler)
    intent_exact_match, intent_semantic_match = _intent_matches(
        translation,
        case["provider_response"],
    )
    row.update(
        {
            "provider_outcome": _provider_outcome(translation),
            "provider_called": translation.provider_called,
            "translation_status": translation.status,
            "semantic_intent_exact_match": intent_exact_match,
            "semantic_intent_match": intent_semantic_match,
            **component_matches,
            **semantic_components,
            "request_exact_match": request_exact_match,
            "request_match": request_match,
            "planning_status": planning_status,
            "authority_rechecked": authority_rechecked,
            "execution_status": execution_status,
            "pipeline_match": pipeline_match,
            "result_match": result_match,
            "controls_match": controls_match,
            "passed": pipeline_match and result_match and controls_match,
            "provider_wall_duration_ms": provider_wall_duration_ms,
            "case_wall_duration_ms": round((time.perf_counter_ns() - case_started) / 1_000_000, 3),
            "request_bytes": provider_metrics.get("request_bytes"),
            "prompt_tokens": provider_metrics.get("prompt_tokens"),
            "completion_tokens": provider_metrics.get("completion_tokens"),
            "provider_total_duration_ms": provider_metrics.get("total_duration_ms"),
            "provider_load_duration_ms": provider_metrics.get("load_duration_ms"),
            "provider_prompt_eval_duration_ms": provider_metrics.get("prompt_eval_duration_ms"),
            "provider_eval_duration_ms": provider_metrics.get("eval_duration_ms"),
            "system_available_memory_mb": resource_metrics.get("system_available_memory_mb"),
            "gpu_used_memory_mb": resource_metrics.get("gpu_used_memory_mb"),
        }
    )
    return row


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
        "provider_acceptance_accuracy": {
            "passed": sum(row["provider_outcome"] == "accepted" for row in rows),
            "evaluated": len(rows),
            "rate": (
                round(sum(row["provider_outcome"] == "accepted" for row in rows) / len(rows), 6)
                if rows
                else None
            ),
        },
        "semantic_intent_accuracy": _metric(rows, "semantic_intent_match"),
        "semantic_intent_exact_accuracy": _metric(rows, "semantic_intent_exact_match"),
        "table_accuracy": _metric(rows, "from_match"),
        "relationship_accuracy": _metric(rows, "joins_match"),
        "dimension_accuracy": _metric(rows, "dimensions_semantic_match"),
        "dimension_alias_accuracy": _metric(rows, "dimensions_match"),
        "measure_accuracy": _metric(rows, "metrics_semantic_match"),
        "measure_alias_accuracy": _metric(rows, "metrics_match"),
        "filter_accuracy": _metric(rows, "filters_match"),
        "order_accuracy": _metric(rows, "order_by_semantic_match"),
        "order_alias_accuracy": _metric(rows, "order_by_match"),
        "limit_accuracy": _metric(rows, "limit_match"),
        "request_accuracy": _metric(rows, "request_match"),
        "request_exact_accuracy": _metric(rows, "request_exact_match"),
        "pipeline_accuracy": _metric(rows, "pipeline_match"),
        "result_accuracy": _metric(rows, "result_match"),
        "control_accuracy": _metric(rows, "controls_match"),
        "exact_result_accuracy": _mode_metric(rows, "exact"),
        "numeric_tolerance_accuracy": _mode_metric(rows, "numeric_tolerance"),
    }


def _number_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if isinstance(row.get(field), (int, float))]
    if not values:
        return {"observed": 0, "minimum": None, "median": None, "p95": None, "maximum": None, "total": None}
    ordered = sorted(values)
    return {
        "observed": len(values),
        "minimum": round(ordered[0], 3),
        "median": round(statistics.median(ordered), 3),
        "p95": round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 3),
        "maximum": round(ordered[-1], 3),
        "total": round(sum(ordered), 3),
    }


def _token_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = [row["prompt_tokens"] for row in rows if isinstance(row.get("prompt_tokens"), int)]
    completion = [row["completion_tokens"] for row in rows if isinstance(row.get("completion_tokens"), int)]
    return {
        "calls_with_prompt_tokens": len(prompt),
        "prompt_tokens": sum(prompt),
        "calls_with_completion_tokens": len(completion),
        "completion_tokens": sum(completion),
        "total_tokens": sum(prompt) + sum(completion),
    }


def _resource_summary(
    baseline: dict[str, Any],
    rows: list[dict[str, Any]],
    sampler_used: bool,
) -> dict[str, Any]:
    available = [
        row["system_available_memory_mb"]
        for row in rows
        if isinstance(row.get("system_available_memory_mb"), (int, float))
    ]
    gpu_used = [
        row["gpu_used_memory_mb"]
        for row in rows
        if isinstance(row.get("gpu_used_memory_mb"), (int, float))
    ]
    return {
        "method": "point_in_time_before_run_and_after_each_case" if sampler_used else "not_collected",
        "system_total_memory_mb": baseline.get("system_total_memory_mb"),
        "system_available_before_mb": baseline.get("system_available_memory_mb"),
        "minimum_system_available_after_case_mb": min(available) if available else None,
        "gpu_total_memory_mb": baseline.get("gpu_total_memory_mb"),
        "gpu_used_before_mb": baseline.get("gpu_used_memory_mb"),
        "maximum_gpu_used_after_case_mb": max(gpu_used) if gpu_used else None,
        "caveat": "Point-in-time host observations are not continuous per-process peak measurements.",
    }


def _cases_csv(rows: list[dict[str, Any]]) -> str:
    fields = list(_empty_case_row({"id": "", "comparison": {"mode": ""}}, "").keys())
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
    mode: str,
    dataset_id: str,
    pack_id: str,
    provider_name: str,
    rows: list[dict[str, Any]],
    blockers: list[dict[str, str]],
    metrics: dict[str, Any],
    latency: dict[str, Any],
    tokens: dict[str, Any],
) -> str:
    lines = [
        "# Analytics Dataset Benchmark Live Evaluation Report",
        "",
        f"- Status: `{status}`",
        f"- Mode: `{mode}`",
        f"- Dataset: `{dataset_id or 'invalid'}`",
        f"- Pack: `{pack_id or 'invalid'}`",
        f"- Provider: `{provider_name or 'invalid'}`",
        f"- Cases: {len(rows)}",
        f"- Passed: {sum(bool(row['passed']) for row in rows)}",
        f"- Failed: {sum(not bool(row['passed']) for row in rows)}",
        f"- Contract blockers: {len(blockers)}",
        "",
        "## Accuracy",
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
            "## Provider Telemetry",
            "",
            f"- Provider wall time total: {latency['total'] if latency['total'] is not None else 'not observed'} ms",
            f"- Provider wall time median: {latency['median'] if latency['median'] is not None else 'not observed'} ms",
            f"- Provider wall time p95: {latency['p95'] if latency['p95'] is not None else 'not observed'} ms",
            f"- Prompt tokens: {tokens['prompt_tokens']}",
            f"- Completion tokens: {tokens['completion_tokens']}",
            "- Hosted API cost: USD 0.00; electricity and hardware cost were not measured.",
            "",
            "## Boundaries",
            "",
            "- A separate hash-bound human authorization is required in addition to offline answer approval.",
            "- Dry-run performs authority/configuration preflight and never calls the provider or opens DuckDB.",
            "- Execute mode requires both explicit execution and loopback-network flags.",
            "- Cases run sequentially; non-alias request equality plus explicitly reviewed alias-only normalization gate Stage 5A and read-only Stage 5B.",
            "- Every immutable input is rehashed before provider use, before every query, and after evaluation.",
            "- Persistent evidence omits questions, provider responses, expected/actual rows, SQL, and parameters.",
            "- External providers, upload, training, narration, publication, concurrency, and automatic dispatch remain disabled.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Live benchmark evaluation output is not a directory: {output_dir}")
    entries = list(output_dir.iterdir()) if output_dir.exists() else []
    if entries:
        existing = {path.name: path for path in entries if path.is_file()}
        exact = (
            len(entries) == len(contents)
            and set(existing) == set(contents)
            and all(
                existing[name].read_text(encoding="utf-8") == content
                for name, content in contents.items()
            )
        )
        if exact:
            return False
        raise ValueError(
            f"Different live benchmark evaluation evidence already exists in {output_dir}. "
            "Use a new output directory; existing evidence was not overwritten."
        )
    if output_dir.exists():
        raise ValueError(
            f"Live benchmark evaluation output already exists and is empty: {output_dir}. "
            "Use a new output directory so evidence can be published atomically."
        )
    ensure_dir(output_dir.parent)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    try:
        for name, content in contents.items():
            (staging_dir / name).write_text(content, encoding="utf-8", newline="")
        try:
            publish_new_directory(
                staging_dir,
                output_dir,
                retry_delays=OUTPUT_PUBLISH_RETRY_DELAYS_SECONDS,
                sleep_fn=time.sleep,
            )
        except AtomicPublishTargetAppearedError as error:
            raise ValueError(
                f"Live benchmark evaluation output appeared during atomic publication: "
                f"{output_dir}. Existing evidence was not overwritten."
            ) from error
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
    return True


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def sample_local_resources() -> dict[str, Any]:
    result: dict[str, Any] = {
        "system_total_memory_mb": None,
        "system_available_memory_mb": None,
        "gpu_total_memory_mb": None,
        "gpu_used_memory_mb": None,
    }
    if os.name == "nt":
        try:
            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                result["system_total_memory_mb"] = round(status.ullTotalPhys / 1_048_576, 1)
                result["system_available_memory_mb"] = round(status.ullAvailPhys / 1_048_576, 1)
        except (AttributeError, OSError):
            pass
    else:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_pages = os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            result["system_total_memory_mb"] = round(page_size * total_pages / 1_048_576, 1)
            result["system_available_memory_mb"] = round(page_size * available_pages / 1_048_576, 1)
        except (AttributeError, OSError, ValueError):
            pass
    try:
        completed = subprocess.run(
            [  # noqa: S607 - fixed literal argv; telemetry only, no shell and no user input
                "nvidia-smi",
                "--query-gpu=memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        if completed.returncode == 0:
            rows = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            parsed = [tuple(int(value.strip()) for value in line.split(",", 1)) for line in rows]
            if parsed:
                result["gpu_total_memory_mb"] = sum(row[0] for row in parsed)
                result["gpu_used_memory_mb"] = sum(row[1] for row in parsed)
    except (FileNotFoundError, OSError, subprocess.SubprocessError, ValueError):
        pass
    return result


def run_analytics_dataset_benchmark_live_evaluation(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    benchmark_approval_path: Path,
    live_authorization_path: Path,
    output_dir: Path,
    provider: SemanticIntentProvider,
    *,
    timeout_seconds: int = 120,
    execute: bool = False,
    allow_network: bool = False,
    resource_sampler: Callable[[], dict[str, Any]] | None = None,
    case_guard: Callable[[], str | None] | None = None,
) -> AnalyticsDatasetBenchmarkLiveEvaluationResult:
    blockers: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    source: dict[str, str] = {}
    dataset_id = ""
    pack_id = ""
    mode = "live" if execute else "dry-run"
    base_paths = _source_paths(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
        benchmark_approval_path,
    )
    with tempfile.TemporaryDirectory(prefix="dataops_dataset_live_benchmark_") as temp_name:
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
        validation_manifest = yaml.safe_load(validation.manifest_path.read_text(encoding="utf-8")) or {}
        source = validation_manifest.get("source", {})
        dataset_id = validation_manifest.get("dataset_id", "")
        pack_id = validation_manifest.get("pack_id", "")
        pack: dict[str, Any] = {}
        if validation.status != "ready_for_offline_evaluation":
            _copy_validation_blockers(validation.blockers_path, blockers)
        elif not isinstance(source, dict) or not _hashes_match(source, base_paths):
            add_blocker(
                blockers,
                "dataset_benchmark_authority_changed_before_live_preflight",
                "An immutable benchmark input changed after base authority validation.",
                field="authority",
            )
        else:
            pack = read_yaml_mapping(benchmark_pack_path, blockers, "benchmark_pack")
            cases = pack.get("cases", []) if isinstance(pack, dict) else []
            case_ids = [case.get("id", "") for case in cases if isinstance(case, dict)]
            _validate_live_authorization(
                live_authorization_path,
                source,
                dataset_id,
                pack_id,
                case_ids,
                provider,
                timeout_seconds,
                blockers,
            )
        if execute and not allow_network:
            add_blocker(
                blockers,
                "live_evaluation_network_not_authorized_for_invocation",
                "Execute mode requires explicit loopback-network authorization for this invocation.",
                field="allow_network",
            )
        if not execute and allow_network:
            add_blocker(
                blockers,
                "live_evaluation_network_flag_not_allowed_in_dry_run",
                "Dry-run must not receive network authorization because it never calls the provider.",
                field="allow_network",
            )

        if live_authorization_path.is_file():
            source = {**source, "live_authorization_sha256": file_sha256(live_authorization_path)}
        paths = {**base_paths, "live_authorization_sha256": live_authorization_path}
        baseline_resources = _sample_resources(resource_sampler) if execute and not blockers else {}
        if execute and not blockers:
            cases = pack["cases"]
            timed_out = False
            case_guard_stopped = False
            for index, case in enumerate(cases):
                if timed_out:
                    rows.append(_empty_case_row(case, "skipped_after_provider_timeout"))
                    continue
                if case_guard_stopped:
                    rows.append(_empty_case_row(case, "skipped_after_case_guard"))
                    continue
                if case_guard is not None:
                    try:
                        guard_reason = case_guard()
                    except Exception:
                        guard_reason = "case_guard_failure"
                    if guard_reason:
                        case_guard_stopped = True
                        rows.append(_empty_case_row(case, "skipped_after_case_guard"))
                        continue
                if not _hashes_match(source, paths):
                    add_blocker(
                        blockers,
                        "dataset_benchmark_authority_changed_before_live_case",
                        "An immutable live-benchmark input changed before provider invocation.",
                        field=f"case.{case['id']}",
                    )
                    rows = []
                    break
                case_dir = temp_dir / f"case_{index + 1:03d}"
                case_dir.mkdir()
                try:
                    row = _case_row(
                        case,
                        semantic_state_path,
                        database_path,
                        relationships_path,
                        case_dir,
                        source,
                        paths,
                        provider,
                        timeout_seconds,
                        resource_sampler,
                    )
                    rows.append(row)
                    timed_out = row["provider_outcome"] == "timeout"
                except DatasetBenchmarkAuthorityDrift:
                    add_blocker(
                        blockers,
                        "dataset_benchmark_authority_changed_before_live_query",
                        "An immutable live-benchmark input changed after planning; query execution was blocked.",
                        field=f"case.{case['id']}",
                    )
                    rows = []
                    break
                except Exception:
                    rows.append(_evaluation_error_case_row(case, provider, resource_sampler))
            if not blockers and not _hashes_match(source, paths):
                add_blocker(
                    blockers,
                    "dataset_benchmark_inputs_changed_during_live_evaluation",
                    "An immutable live-benchmark input changed during evaluation; case evidence was discarded.",
                    field="authority",
                )
                rows = []
        else:
            baseline_resources = {}

    status = (
        "blocked"
        if blockers
        else "ready_for_live_evaluation"
        if not execute
        else "passed"
        if rows and all(row["passed"] for row in rows)
        else "failed"
    )
    metrics = _metrics(rows)
    latency = _number_summary(rows, "provider_wall_duration_ms")
    provider_latency = _number_summary(rows, "provider_total_duration_ms")
    tokens = _token_summary(rows)
    resources = _resource_summary(baseline_resources, rows, bool(resource_sampler and execute))
    passed_count = sum(bool(row["passed"]) for row in rows)
    provider_call_count = sum(bool(row["provider_called"]) for row in rows)
    manifest = {
        "version": 1,
        "status": status,
        "mode": mode,
        "dataset_id": dataset_id,
        "pack_id": pack_id,
        "source": source,
        "provider": _provider_config(provider, timeout_seconds),
        "controls": {
            "separate_live_authorization_required": True,
            "explicit_execute_required": True,
            "explicit_loopback_network_authorization_required": True,
            "network_accessed": provider_call_count > 0,
            "live_provider_used": provider_call_count > 0,
            "sequential_cases": True,
            "immutable_hash_recheck_before_provider_and_query": True,
            "expected_request_gate_required": True,
            "stage_5a_plan_required": True,
            "stage_5b_revalidation_required": True,
            "database_mode": "read_only",
            "external_provider_authorized": False,
            "external_upload_authorized": False,
            "model_training_authorized": False,
            "narration_authorized": False,
            "publication_authorized": False,
            "case_content_persisted_in_evidence": False,
        },
        "execution_limits": {
            "provider_timeout_seconds_per_case": timeout_seconds,
            "max_rows": EVALUATION_LIMITS.max_rows,
            "max_result_bytes": EVALUATION_LIMITS.max_result_bytes,
            "max_runtime_seconds_per_query": EVALUATION_LIMITS.max_runtime_seconds,
            "memory_limit_mb_per_query": EVALUATION_LIMITS.memory_limit_mb,
            "threads_per_query": EVALUATION_LIMITS.threads,
            "max_temp_mb_per_query": EVALUATION_LIMITS.max_temp_mb,
        },
        "counts": {
            "cases": len(rows),
            "provider_calls": provider_call_count,
            "passed": passed_count,
            "failed": len(rows) - passed_count,
            "contract_blockers": len(blockers),
        },
        "metrics": metrics,
        "telemetry": {
            "provider_wall_duration_ms": latency,
            "provider_reported_duration_ms": provider_latency,
            "tokens": tokens,
            "hosted_api_cost_usd": 0.0,
            "hosted_api_cost_caveat": "Electricity and hardware depreciation are not included.",
            "resources": resources,
        },
    }
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        CASES_NAME: _cases_csv(rows),
        BLOCKERS_NAME: _blockers_csv(blockers),
        REPORT_NAME: _render_report(
            status,
            mode,
            dataset_id,
            pack_id,
            getattr(provider, "name", ""),
            rows,
            blockers,
            metrics,
            latency,
            tokens,
        ),
    }
    outputs_changed = _write_outputs(output_dir, contents)
    return AnalyticsDatasetBenchmarkLiveEvaluationResult(
        output_dir=output_dir,
        status=status,
        mode=mode,
        manifest_path=output_dir / MANIFEST_NAME,
        cases_path=output_dir / CASES_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        case_count=len(rows),
        passed_count=passed_count,
        failed_count=len(rows) - passed_count,
        blocker_count=len(blockers),
        provider_call_count=provider_call_count,
        outputs_changed=outputs_changed,
    )
