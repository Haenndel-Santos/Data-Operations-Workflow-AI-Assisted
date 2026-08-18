from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
import io
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from .analytics_dataset_benchmark_live_evaluation import (
    AnalyticsDatasetBenchmarkLiveEvaluationResult,
    run_analytics_dataset_benchmark_live_evaluation,
    sample_local_resources,
)
from .analytics_nl_translation import SemanticIntentProvider
from .contracts.atomic_publish import (
    DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
    atomic_write_text,
)
from .contracts.source_bindings import existing_file_sha256_bindings
from .ollama_provider import validate_loopback_endpoint
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_ollama_soak.yml"
CYCLES_NAME = "analytics_ollama_soak_cycles.csv"
CASES_NAME = "analytics_ollama_soak_case_stability.csv"
REPORT_NAME = "analytics_ollama_soak_report.md"
STOP_FILE_NAME = "STOP"
OUTPUT_NAMES = {MANIFEST_NAME, CYCLES_NAME, CASES_NAME, REPORT_NAME}
MAX_AUTHORIZATION_BYTES = 64_000
CHECKPOINT_PUBLISH_RETRY_DELAYS_SECONDS = DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS
SOAK_DECISIONS = {
    "local_loopback_overnight_soak_approved": True,
    "local_read_only_benchmark_queries_approved": True,
    "repeat_approved_development_pack_approved": True,
    "parallel_provider_requests_approved": False,
    "external_provider_approved": False,
    "external_upload_approved": False,
    "model_training_approved": False,
    "narration_approved": False,
    "publication_approved": False,
    "production_use_approved": False,
}
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MAX_PROCESS_PATH = 260


@dataclass(frozen=True)
class OllamaSoakPolicy:
    duration_seconds: int
    max_cycles: int
    cooldown_seconds: int
    max_consecutive_cycle_errors: int
    provider_concurrency: int
    sequential_cycles: bool
    stop_file_name: str
    max_gpu_temperature_c: int
    min_available_system_memory_mb: int
    min_free_disk_mb: int


@dataclass(frozen=True)
class AnalyticsOllamaSoakResult:
    output_dir: Path
    status: str
    mode: str
    manifest_path: Path
    cycles_path: Path
    cases_path: Path
    report_path: Path
    cycle_count: int
    provider_call_count: int
    blocker_count: int
    stop_reason: str
    outputs_changed: bool


class _ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PROCESS_PATH),
    ]


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _add_blocker(
    blockers: list[dict[str, str]],
    blocker_type: str,
    explanation: str,
    *,
    field: str,
) -> None:
    blockers.append(
        {
            "blocker_id": f"blocker_{len(blockers) + 1:03d}",
            "blocker_type": blocker_type,
            "field": field,
            "explanation": explanation,
        }
    )


def _read_mapping(path: Path, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        _add_blocker(
            blockers,
            "ollama_soak_authorization_missing",
            "A separate completed overnight-soak authorization is required.",
            field="soak_authorization",
        )
        return {}
    if path.stat().st_size > MAX_AUTHORIZATION_BYTES:
        _add_blocker(
            blockers,
            "ollama_soak_authorization_too_large",
            f"The overnight-soak authorization must be at most {MAX_AUTHORIZATION_BYTES} bytes.",
            field="soak_authorization",
        )
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        payload = {}
    if not isinstance(payload, dict):
        _add_blocker(
            blockers,
            "ollama_soak_authorization_invalid",
            "The overnight-soak authorization must be a YAML mapping.",
            field="soak_authorization",
        )
        return {}
    return payload


def _reject_unknown_fields(
    payload: dict[str, Any],
    allowed: set[str],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    for key in payload:
        if key not in allowed:
            _add_blocker(
                blockers,
                "unsupported_ollama_soak_authorization_field",
                "The overnight-soak authorization contains a field outside the version-1 contract.",
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


def _source_hashes(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    benchmark_approval_path: Path,
    live_authorization_path: Path,
) -> dict[str, str]:
    paths = {
        "dataset_manifest_sha256": dataset_manifest_path,
        "database_sha256": database_path,
        "approved_semantic_state_sha256": semantic_state_path,
        "approved_relationships_sha256": relationships_path,
        "benchmark_pack_sha256": benchmark_pack_path,
        "benchmark_approval_sha256": benchmark_approval_path,
        "live_authorization_sha256": live_authorization_path,
    }
    return existing_file_sha256_bindings(paths)


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


def _policy_from_authorization(
    authorization: dict[str, Any],
    blockers: list[dict[str, str]],
) -> OllamaSoakPolicy | None:
    execution = authorization.get("execution")
    resources = authorization.get("resource_limits")
    if not isinstance(execution, dict):
        _add_blocker(
            blockers,
            "ollama_soak_execution_policy_missing",
            "The overnight-soak execution policy is required.",
            field="soak_authorization.execution",
        )
        return None
    if not isinstance(resources, dict):
        _add_blocker(
            blockers,
            "ollama_soak_resource_policy_missing",
            "The overnight-soak resource policy is required.",
            field="soak_authorization.resource_limits",
        )
        return None
    _reject_unknown_fields(
        execution,
        {
            "duration_seconds",
            "max_cycles",
            "cooldown_seconds",
            "max_consecutive_cycle_errors",
            "provider_concurrency",
            "sequential_cycles",
            "stop_file_name",
        },
        blockers,
        "soak_authorization.execution",
    )
    _reject_unknown_fields(
        resources,
        {
            "max_gpu_temperature_c",
            "min_available_system_memory_mb",
            "min_free_disk_mb",
        },
        blockers,
        "soak_authorization.resource_limits",
    )
    try:
        policy = OllamaSoakPolicy(
            duration_seconds=execution["duration_seconds"],
            max_cycles=execution["max_cycles"],
            cooldown_seconds=execution["cooldown_seconds"],
            max_consecutive_cycle_errors=execution["max_consecutive_cycle_errors"],
            provider_concurrency=execution["provider_concurrency"],
            sequential_cycles=execution["sequential_cycles"],
            stop_file_name=execution["stop_file_name"],
            max_gpu_temperature_c=resources["max_gpu_temperature_c"],
            min_available_system_memory_mb=resources["min_available_system_memory_mb"],
            min_free_disk_mb=resources["min_free_disk_mb"],
        )
    except KeyError:
        _add_blocker(
            blockers,
            "ollama_soak_policy_incomplete",
            "Every version-1 execution and resource field is required.",
            field="soak_authorization",
        )
        return None
    numeric = (
        ("duration_seconds", policy.duration_seconds, 60, 86_400),
        ("max_cycles", policy.max_cycles, 1, 256),
        ("cooldown_seconds", policy.cooldown_seconds, 0, 600),
        ("max_consecutive_cycle_errors", policy.max_consecutive_cycle_errors, 1, 10),
        ("max_gpu_temperature_c", policy.max_gpu_temperature_c, 50, 85),
        ("min_available_system_memory_mb", policy.min_available_system_memory_mb, 2_048, 65_536),
        ("min_free_disk_mb", policy.min_free_disk_mb, 1_024, 1_000_000),
    )
    for name, value, minimum, maximum in numeric:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            _add_blocker(
                blockers,
                "ollama_soak_policy_value_invalid",
                f"{name} must be an integer between {minimum} and {maximum}.",
                field=f"soak_authorization.{name}",
            )
    if (
        isinstance(policy.provider_concurrency, bool)
        or policy.provider_concurrency != 1
        or policy.sequential_cycles is not True
        or policy.stop_file_name != STOP_FILE_NAME
    ):
        _add_blocker(
            blockers,
            "ollama_soak_parallel_or_stop_policy_invalid",
            "Version 1 requires sequential cycles, one provider call at a time, and the exact STOP filename.",
            field="soak_authorization.execution",
        )
    return policy


def _validate_authorization(
    authorization_path: Path,
    expected_source: dict[str, str],
    provider: SemanticIntentProvider,
    timeout_seconds: int,
    blockers: list[dict[str, str]],
) -> tuple[dict[str, Any], OllamaSoakPolicy | None]:
    authorization = _read_mapping(authorization_path, blockers)
    if not authorization:
        return {}, None
    _reject_unknown_fields(
        authorization,
        {
            "version",
            "status",
            "source",
            "provider",
            "execution",
            "resource_limits",
            "decision",
            "authorized_by",
            "authorized_at",
            "notes",
        },
        blockers,
        "soak_authorization",
    )
    if authorization.get("version") != 1:
        _add_blocker(
            blockers,
            "unsupported_ollama_soak_authorization_version",
            "Overnight-soak authorization version must be 1.",
            field="soak_authorization.version",
        )
    if authorization.get("status") != "approved_local_ollama_soak":
        _add_blocker(
            blockers,
            "ollama_soak_not_approved",
            "Overnight-soak authorization status must be approved_local_ollama_soak.",
            field="soak_authorization.status",
        )
    if authorization.get("source") != expected_source:
        _add_blocker(
            blockers,
            "ollama_soak_source_mismatch",
            "The overnight-soak authorization must bind every source and live authority hash exactly.",
            field="soak_authorization.source",
        )
    expected_provider = _provider_config(provider, timeout_seconds)
    if authorization.get("provider") != expected_provider:
        _add_blocker(
            blockers,
            "ollama_soak_provider_mismatch",
            "The provider configuration must exactly match the overnight-soak authorization.",
            field="soak_authorization.provider",
        )
    endpoint = getattr(provider, "endpoint", "")
    try:
        normalized_endpoint = validate_loopback_endpoint(endpoint)
    except ValueError:
        normalized_endpoint = ""
    if (
        normalized_endpoint != endpoint
        or getattr(provider, "mode", "") != "local_live"
        or getattr(provider, "network_access_required", None) is not True
    ):
        _add_blocker(
            blockers,
            "ollama_soak_provider_not_loopback",
            "The overnight soak accepts only the explicit local-live literal-loopback provider boundary.",
            field="provider",
        )
    if authorization.get("decision") != SOAK_DECISIONS:
        _add_blocker(
            blockers,
            "ollama_soak_scope_not_bounded",
            "The soak may repeat only the approved local development pack; parallel/external/training scopes remain disabled.",
            field="soak_authorization.decision",
        )
    if not isinstance(authorization.get("authorized_by"), str) or not authorization["authorized_by"].strip():
        _add_blocker(
            blockers,
            "ollama_soak_authorizer_missing",
            "A human authorizer identity is required.",
            field="soak_authorization.authorized_by",
        )
    if not _timezone_aware(authorization.get("authorized_at")):
        _add_blocker(
            blockers,
            "ollama_soak_authorized_at_invalid",
            "authorized_at must be an ISO-8601 timestamp with a timezone.",
            field="soak_authorization.authorized_at",
        )
    if not isinstance(authorization.get("notes"), str) or not authorization["notes"].strip():
        _add_blocker(
            blockers,
            "ollama_soak_notes_missing",
            "The overnight-soak authorization requires non-empty human notes.",
            field="soak_authorization.notes",
        )
    return authorization, _policy_from_authorization(authorization, blockers)


def _process_memory_samples() -> dict[str, Any]:
    result: dict[str, Any] = {
        "soak_process_working_set_mb": None,
        "soak_process_private_memory_mb": None,
        "ollama_process_count": 0,
        "ollama_process_working_set_mb": None,
        "ollama_process_private_memory_mb": None,
    }
    if os.name != "nt":
        return result
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        create_snapshot = kernel32.CreateToolhelp32Snapshot
        create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        create_snapshot.restype = wintypes.HANDLE
        process_first = kernel32.Process32FirstW
        process_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry32W)]
        process_first.restype = wintypes.BOOL
        process_next = kernel32.Process32NextW
        process_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry32W)]
        process_next.restype = wintypes.BOOL
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        get_process_memory = psapi.GetProcessMemoryInfo
        get_process_memory.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessMemoryCountersEx),
            wintypes.DWORD,
        ]
        get_process_memory.restype = wintypes.BOOL
        snapshot = create_snapshot(TH32CS_SNAPPROCESS, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or snapshot == invalid_handle:
            return result
        try:
            entry = _ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(_ProcessEntry32W)
            has_entry = bool(process_first(snapshot, ctypes.byref(entry)))
            ollama_working_set = 0
            ollama_private = 0
            ollama_count = 0
            while has_entry:
                process_id = int(entry.th32ProcessID)
                executable = entry.szExeFile.casefold()
                selected = process_id == os.getpid() or executable.startswith("ollama")
                if selected:
                    process = open_process(
                        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                        False,
                        process_id,
                    )
                    if process:
                        try:
                            counters = _ProcessMemoryCountersEx()
                            counters.cb = ctypes.sizeof(_ProcessMemoryCountersEx)
                            if get_process_memory(
                                process,
                                ctypes.byref(counters),
                                counters.cb,
                            ):
                                working_set_mb = counters.WorkingSetSize / 1_048_576
                                private_mb = counters.PrivateUsage / 1_048_576
                                if process_id == os.getpid():
                                    result["soak_process_working_set_mb"] = round(
                                        working_set_mb, 1
                                    )
                                    result["soak_process_private_memory_mb"] = round(
                                        private_mb, 1
                                    )
                                if executable.startswith("ollama"):
                                    ollama_count += 1
                                    ollama_working_set += counters.WorkingSetSize
                                    ollama_private += counters.PrivateUsage
                        finally:
                            close_handle(process)
                has_entry = bool(process_next(snapshot, ctypes.byref(entry)))
            result["ollama_process_count"] = ollama_count
            if ollama_count:
                result["ollama_process_working_set_mb"] = round(
                    ollama_working_set / 1_048_576, 1
                )
                result["ollama_process_private_memory_mb"] = round(
                    ollama_private / 1_048_576, 1
                )
        finally:
            close_handle(snapshot)
    except (AttributeError, OSError, ValueError):
        return result
    return result


def sample_ollama_soak_resources(output_dir: Path) -> dict[str, Any]:
    sample = sample_local_resources()
    sample.update(
        {
            "observed_at": _utc_now(),
            "gpu_temperature_c": None,
            "gpu_utilization_percent": None,
            "gpu_power_w": None,
            "disk_free_mb": None,
            "soak_process_working_set_mb": None,
            "soak_process_private_memory_mb": None,
            "ollama_process_count": 0,
            "ollama_process_working_set_mb": None,
            "ollama_process_private_memory_mb": None,
        }
    )
    sample.update(_process_memory_samples())
    try:
        completed = subprocess.run(
            [  # noqa: S607 - fixed literal argv; telemetry only, no shell and no user input
                "nvidia-smi",
                "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
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
            values = [tuple(float(value.strip()) for value in row.split(",")) for row in rows]
            if values:
                sample["gpu_temperature_c"] = max(value[0] for value in values)
                sample["gpu_utilization_percent"] = max(value[1] for value in values)
                sample["gpu_power_w"] = round(sum(value[2] for value in values), 3)
    except (FileNotFoundError, OSError, subprocess.SubprocessError, ValueError):
        pass
    try:
        usage = shutil.disk_usage(output_dir.parent.resolve())
        sample["disk_free_mb"] = round(usage.free / 1_048_576, 1)
    except OSError:
        pass
    return sample


def _resource_stop_reasons(
    sample: dict[str, Any],
    policy: OllamaSoakPolicy,
) -> list[str]:
    checks = (
        (
            "gpu_temperature_unavailable",
            sample.get("gpu_temperature_c"),
            lambda value: value >= policy.max_gpu_temperature_c,
            "gpu_temperature_limit_reached",
        ),
        (
            "system_memory_unavailable",
            sample.get("system_available_memory_mb"),
            lambda value: value < policy.min_available_system_memory_mb,
            "available_system_memory_below_limit",
        ),
        (
            "disk_space_unavailable",
            sample.get("disk_free_mb"),
            lambda value: value < policy.min_free_disk_mb,
            "free_disk_space_below_limit",
        ),
    )
    reasons: list[str] = []
    for unavailable, value, predicate, exceeded in checks:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            reasons.append(unavailable)
        elif predicate(value):
            reasons.append(exceeded)
    return reasons


def _number_summary(samples: list[dict[str, Any]], key: str, mode: str) -> int | float | None:
    values = [
        sample[key]
        for sample in samples
        if isinstance(sample.get(key), (int, float)) and not isinstance(sample.get(key), bool)
    ]
    if not values:
        return None
    value = min(values) if mode == "min" else max(values)
    return round(value, 3) if isinstance(value, float) else value


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_cycle_cases(
    result: AnalyticsDatasetBenchmarkLiveEvaluationResult,
) -> list[dict[str, str]]:
    try:
        with result.cases_path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeError):
        return []


def _cycle_row(
    index: int,
    result: AnalyticsDatasetBenchmarkLiveEvaluationResult | None,
    samples: list[dict[str, Any]],
    started_at: str,
    completed_at: str,
    elapsed_seconds: float,
    failure_type: str = "",
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = _read_yaml(result.manifest_path) if result is not None else {}
    cases = _read_cycle_cases(result) if result is not None else []
    telemetry = manifest.get("telemetry", {}) if isinstance(manifest.get("telemetry"), dict) else {}
    tokens = telemetry.get("tokens", {}) if isinstance(telemetry.get("tokens"), dict) else {}
    wall = (
        telemetry.get("provider_wall_duration_ms", {})
        if isinstance(telemetry.get("provider_wall_duration_ms"), dict)
        else {}
    )
    timeout_detected = any(row.get("provider_outcome") == "timeout" for row in cases)
    row = {
        "cycle": index,
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "status": result.status if result is not None else "evaluation_error",
        "failure_type": failure_type,
        "case_count": result.case_count if result is not None else 0,
        "passed_count": result.passed_count if result is not None else 0,
        "failed_count": result.failed_count if result is not None else 0,
        "provider_calls": result.provider_call_count if result is not None else 0,
        "contract_blockers": result.blocker_count if result is not None else 0,
        "provider_timeout": timeout_detected,
        "prompt_tokens": tokens.get("prompt_tokens", 0),
        "completion_tokens": tokens.get("completion_tokens", 0),
        "provider_wall_duration_ms": wall.get("total"),
        "max_gpu_temperature_c": _number_summary(samples, "gpu_temperature_c", "max"),
        "max_gpu_used_memory_mb": _number_summary(samples, "gpu_used_memory_mb", "max"),
        "max_gpu_utilization_percent": _number_summary(samples, "gpu_utilization_percent", "max"),
        "max_gpu_power_w": _number_summary(samples, "gpu_power_w", "max"),
        "max_soak_process_working_set_mb": _number_summary(
            samples, "soak_process_working_set_mb", "max"
        ),
        "max_soak_process_private_memory_mb": _number_summary(
            samples, "soak_process_private_memory_mb", "max"
        ),
        "max_ollama_process_count": _number_summary(
            samples, "ollama_process_count", "max"
        ),
        "max_ollama_process_working_set_mb": _number_summary(
            samples, "ollama_process_working_set_mb", "max"
        ),
        "max_ollama_process_private_memory_mb": _number_summary(
            samples, "ollama_process_private_memory_mb", "max"
        ),
        "min_available_system_memory_mb": _number_summary(
            samples, "system_available_memory_mb", "min"
        ),
        "min_free_disk_mb": _number_summary(samples, "disk_free_mb", "min"),
    }
    return row, cases


def _case_stability_rows(case_observations: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    return [
        {"case_id": case_id, **values}
        for case_id, values in sorted(case_observations.items())
    ]


def _update_case_observations(
    observations: dict[str, dict[str, int]],
    rows: list[dict[str, str]],
) -> None:
    fields = {
        "passed": "passed",
        "provider_accepted": "provider_outcome",
        "request_matched": "request_match",
        "result_matched": "result_match",
        "provider_timeouts": "provider_outcome",
    }
    for row in rows:
        case_id = row.get("case_id", "")
        if not case_id:
            continue
        target = observations.setdefault(
            case_id,
            {
                "observations": 0,
                "passed": 0,
                "provider_accepted": 0,
                "request_matched": 0,
                "result_matched": 0,
                "provider_timeouts": 0,
            },
        )
        target["observations"] += 1
        for output, source in fields.items():
            value = row.get(source)
            matched = (
                value == "accepted"
                if output == "provider_accepted"
                else value == "timeout"
                if output == "provider_timeouts"
                else value == "True"
            )
            target[output] += int(matched)


def _csv_text(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _aggregate(
    cycle_rows: list[dict[str, Any]],
    all_samples: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "cycles_completed": len(cycle_rows),
        "cycles_with_all_cases_passed": sum(row["status"] == "passed" for row in cycle_rows),
        "cycles_with_quality_failures": sum(row["status"] == "failed" for row in cycle_rows),
        "cycles_with_technical_errors": sum(
            bool(row["failure_type"]) or bool(row["contract_blockers"])
            for row in cycle_rows
        ),
        "cases_evaluated": sum(int(row["case_count"]) for row in cycle_rows),
        "cases_passed": sum(int(row["passed_count"]) for row in cycle_rows),
        "provider_calls": sum(int(row["provider_calls"]) for row in cycle_rows),
        "prompt_tokens": sum(int(row["prompt_tokens"] or 0) for row in cycle_rows),
        "completion_tokens": sum(int(row["completion_tokens"] or 0) for row in cycle_rows),
        "provider_wall_duration_ms": round(
            sum(float(row["provider_wall_duration_ms"] or 0) for row in cycle_rows), 3
        ),
        "max_gpu_temperature_c": _number_summary(all_samples, "gpu_temperature_c", "max"),
        "max_gpu_used_memory_mb": _number_summary(all_samples, "gpu_used_memory_mb", "max"),
        "max_gpu_utilization_percent": _number_summary(
            all_samples, "gpu_utilization_percent", "max"
        ),
        "max_gpu_power_w": _number_summary(all_samples, "gpu_power_w", "max"),
        "max_soak_process_working_set_mb": _number_summary(
            all_samples, "soak_process_working_set_mb", "max"
        ),
        "max_soak_process_private_memory_mb": _number_summary(
            all_samples, "soak_process_private_memory_mb", "max"
        ),
        "max_ollama_process_count": _number_summary(
            all_samples, "ollama_process_count", "max"
        ),
        "max_ollama_process_working_set_mb": _number_summary(
            all_samples, "ollama_process_working_set_mb", "max"
        ),
        "max_ollama_process_private_memory_mb": _number_summary(
            all_samples, "ollama_process_private_memory_mb", "max"
        ),
        "min_available_system_memory_mb": _number_summary(
            all_samples, "system_available_memory_mb", "min"
        ),
        "min_free_disk_mb": _number_summary(all_samples, "disk_free_mb", "min"),
        "hosted_api_cost_usd": 0.0,
    }


def _manifest(
    *,
    status: str,
    mode: str,
    source: dict[str, str],
    authorization_sha256: str,
    provider: SemanticIntentProvider,
    timeout_seconds: int,
    policy: OllamaSoakPolicy | None,
    blockers: list[dict[str, str]],
    cycle_rows: list[dict[str, Any]],
    all_samples: list[dict[str, Any]],
    stop_reason: str,
    started_at: str | None,
    heartbeat_at: str | None,
    completed_at: str | None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "status": status,
        "mode": mode,
        "source": {**source, "soak_authorization_sha256": authorization_sha256},
        "provider": _provider_config(provider, timeout_seconds),
        "policy": asdict(policy) if policy is not None else {},
        "controls": {
            "separate_soak_authorization_required": True,
            "explicit_execute_required": True,
            "explicit_loopback_network_authorization_required": True,
            "provider_concurrency": 1,
            "parallel_provider_requests": False,
            "sequential_cycles": True,
            "default_offline_suite_unchanged": True,
            "local_ollama_runtime_only": True,
            "codex_or_hosted_model_api_used_by_runtime": False,
            "database_mode": "read_only",
            "case_content_persisted_in_soak_evidence": False,
            "external_provider_authorized": False,
            "external_upload_authorized": False,
            "model_training_authorized": False,
            "narration_authorized": False,
            "publication_authorized": False,
            "production_use_authorized": False,
        },
        "runtime": {
            "process_id": os.getpid(),
            "started_at": started_at,
            "last_heartbeat_at": heartbeat_at,
            "completed_at": completed_at,
            "stop_reason": stop_reason,
            "stop_file": policy.stop_file_name if policy is not None else STOP_FILE_NAME,
        },
        "counts": _aggregate(cycle_rows, all_samples),
        "contract_blockers": blockers,
    }


def _render_report(manifest: dict[str, Any]) -> str:
    counts = manifest["counts"]
    runtime = manifest["runtime"]
    return "\n".join(
        [
            "# Local Ollama Overnight Soak Report",
            "",
            f"- Status: `{manifest['status']}`",
            f"- Mode: `{manifest['mode']}`",
            f"- Cycles completed: {counts['cycles_completed']}",
            f"- Cases evaluated: {counts['cases_evaluated']}",
            f"- Cases passed: {counts['cases_passed']}",
            f"- Provider calls: {counts['provider_calls']}",
            f"- Prompt tokens: {counts['prompt_tokens']}",
            f"- Completion tokens: {counts['completion_tokens']}",
            f"- Maximum GPU temperature: {counts['max_gpu_temperature_c']}",
            f"- Maximum GPU memory used: {counts['max_gpu_used_memory_mb']}",
            f"- Maximum soak-process working set: {counts['max_soak_process_working_set_mb']}",
            f"- Maximum Ollama working set: {counts['max_ollama_process_working_set_mb']}",
            f"- Maximum Ollama private memory: {counts['max_ollama_process_private_memory_mb']}",
            f"- Minimum available system memory: {counts['min_available_system_memory_mb']}",
            f"- Stop reason: `{runtime['stop_reason'] or 'none'}`",
            "",
            "## Boundaries",
            "",
            "- One loopback Ollama request at a time; model-call parallelism is disabled.",
            "- Eligible requests use the existing governed Stage 5D, Stage 5A, and read-only Stage 5B path.",
            "- Resource limits, STOP-file handling, timeout circuit breaking, and technical-error limits fail closed.",
            "- The local runtime uses no Codex or hosted-model API and incurs no hosted token charge.",
            "- Questions, provider responses, SQL, parameters, filter values, and result rows are not copied into soak summaries.",
        ]
    ) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    atomic_write_text(
        path,
        content,
        retry_delays=CHECKPOINT_PUBLISH_RETRY_DELAYS_SECONDS,
        sleep_fn=time.sleep,
        replace_fn=os.replace,
    )


def _write_state(
    output_dir: Path,
    manifest: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    case_observations: dict[str, dict[str, int]],
) -> None:
    cycle_fields = [
        "cycle",
        "started_at",
        "completed_at",
        "elapsed_seconds",
        "status",
        "failure_type",
        "case_count",
        "passed_count",
        "failed_count",
        "provider_calls",
        "contract_blockers",
        "provider_timeout",
        "prompt_tokens",
        "completion_tokens",
        "provider_wall_duration_ms",
        "max_gpu_temperature_c",
        "max_gpu_used_memory_mb",
        "max_gpu_utilization_percent",
        "max_gpu_power_w",
        "max_soak_process_working_set_mb",
        "max_soak_process_private_memory_mb",
        "max_ollama_process_count",
        "max_ollama_process_working_set_mb",
        "max_ollama_process_private_memory_mb",
        "min_available_system_memory_mb",
        "min_free_disk_mb",
    ]
    case_fields = [
        "case_id",
        "observations",
        "passed",
        "provider_accepted",
        "request_matched",
        "result_matched",
        "provider_timeouts",
    ]
    _atomic_write(
        output_dir / MANIFEST_NAME,
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
    )
    _atomic_write(output_dir / CYCLES_NAME, _csv_text(cycle_rows, cycle_fields))
    _atomic_write(
        output_dir / CASES_NAME,
        _csv_text(_case_stability_rows(case_observations), case_fields),
    )
    _atomic_write(output_dir / REPORT_NAME, _render_report(manifest))


def _prepare_output(output_dir: Path) -> None:
    if output_dir.exists():
        entries = list(output_dir.iterdir()) if output_dir.is_dir() else []
        if not output_dir.is_dir() or entries:
            raise ValueError(
                f"Use a new empty path for overnight-soak evidence: {output_dir}. "
                "Existing evidence was not overwritten."
            )
    ensure_dir(output_dir)


def _cooldown(
    output_dir: Path,
    policy: OllamaSoakPolicy,
    resource_sampler: Callable[[], dict[str, Any]],
    sleep_fn: Callable[[float], None],
    all_samples: list[dict[str, Any]],
) -> tuple[str, str]:
    remaining = float(policy.cooldown_seconds)
    while remaining > 0:
        if (output_dir / policy.stop_file_name).exists():
            return "stopped_by_request", "stop_file_detected"
        sample = resource_sampler()
        all_samples.append(sample)
        reasons = _resource_stop_reasons(sample, policy)
        if reasons:
            return "stopped_resource_guard", ",".join(reasons)
        interval = min(5.0, remaining)
        sleep_fn(interval)
        remaining -= interval
    return "running", ""


def run_analytics_ollama_soak(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    benchmark_approval_path: Path,
    live_authorization_path: Path,
    soak_authorization_path: Path,
    output_dir: Path,
    provider: SemanticIntentProvider,
    *,
    timeout_seconds: int = 120,
    execute: bool = False,
    allow_network: bool = False,
    resource_sampler: Callable[[], dict[str, Any]] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> AnalyticsOllamaSoakResult:
    blockers: list[dict[str, str]] = []
    mode = "live" if execute else "dry-run"
    source = _source_hashes(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
        benchmark_approval_path,
        live_authorization_path,
    )
    _authorization, policy = _validate_authorization(
        soak_authorization_path,
        source,
        provider,
        timeout_seconds,
        blockers,
    )
    if execute and not allow_network:
        _add_blocker(
            blockers,
            "ollama_soak_network_not_authorized_for_invocation",
            "Live soak mode requires explicit loopback-network authorization.",
            field="allow_network",
        )
    if not execute and allow_network:
        _add_blocker(
            blockers,
            "ollama_soak_network_flag_not_allowed_in_dry_run",
            "Dry-run must not receive network authorization.",
            field="allow_network",
        )

    with tempfile.TemporaryDirectory(prefix="dataops_ollama_soak_preflight_") as temp_name:
        preflight = run_analytics_dataset_benchmark_live_evaluation(
            dataset_manifest_path,
            database_path,
            semantic_state_path,
            relationships_path,
            benchmark_pack_path,
            benchmark_approval_path,
            live_authorization_path,
            Path(temp_name) / "live_preflight",
            provider,
            timeout_seconds=timeout_seconds,
            execute=False,
            allow_network=False,
        )
    if preflight.status != "ready_for_live_evaluation":
        _add_blocker(
            blockers,
            "ollama_soak_live_authority_preflight_failed",
            "The underlying live benchmark package and authorization must pass offline preflight.",
            field="live_authorization",
        )

    authorization_hash = (
        file_sha256(soak_authorization_path) if soak_authorization_path.is_file() else ""
    )
    _prepare_output(output_dir)
    cycle_rows: list[dict[str, Any]] = []
    case_observations: dict[str, dict[str, int]] = {}
    all_samples: list[dict[str, Any]] = []
    started_at: str | None = None
    heartbeat_at: str | None = None
    completed_at: str | None = None
    stop_reason = ""
    outputs_changed = True

    if blockers or policy is None:
        status = "blocked"
        manifest = _manifest(
            status=status,
            mode=mode,
            source=source,
            authorization_sha256=authorization_hash,
            provider=provider,
            timeout_seconds=timeout_seconds,
            policy=policy,
            blockers=blockers,
            cycle_rows=cycle_rows,
            all_samples=all_samples,
            stop_reason="contract_blocked",
            started_at=None,
            heartbeat_at=None,
            completed_at=_utc_now(),
        )
        _write_state(output_dir, manifest, cycle_rows, case_observations)
    elif not execute:
        status = "ready_for_overnight_soak"
        manifest = _manifest(
            status=status,
            mode=mode,
            source=source,
            authorization_sha256=authorization_hash,
            provider=provider,
            timeout_seconds=timeout_seconds,
            policy=policy,
            blockers=blockers,
            cycle_rows=cycle_rows,
            all_samples=all_samples,
            stop_reason="",
            started_at=None,
            heartbeat_at=None,
            completed_at=None,
        )
        _write_state(output_dir, manifest, cycle_rows, case_observations)
    else:
        sampler = resource_sampler or (lambda: sample_ollama_soak_resources(output_dir))
        status = "running"
        started_at = _utc_now()
        heartbeat_at = started_at
        started_tick = monotonic_fn()
        consecutive_errors = 0
        manifest = _manifest(
            status=status,
            mode=mode,
            source=source,
            authorization_sha256=authorization_hash,
            provider=provider,
            timeout_seconds=timeout_seconds,
            policy=policy,
            blockers=blockers,
            cycle_rows=cycle_rows,
            all_samples=all_samples,
            stop_reason=stop_reason,
            started_at=started_at,
            heartbeat_at=heartbeat_at,
            completed_at=None,
        )
        _write_state(output_dir, manifest, cycle_rows, case_observations)

        while len(cycle_rows) < policy.max_cycles:
            if monotonic_fn() - started_tick >= policy.duration_seconds:
                stop_reason = "duration_reached"
                status = "completed"
                break
            if (output_dir / policy.stop_file_name).exists():
                stop_reason = "stop_file_detected"
                status = "stopped_by_request"
                break
            initial_sample = sampler()
            all_samples.append(initial_sample)
            reasons = _resource_stop_reasons(initial_sample, policy)
            if reasons:
                stop_reason = ",".join(reasons)
                status = "stopped_resource_guard"
                break

            cycle_index = len(cycle_rows) + 1
            cycle_samples = [initial_sample]

            def tracked_sampler() -> dict[str, Any]:
                sample = sampler()
                cycle_samples.append(sample)  # noqa: B023 - consumed inside the same iteration; never escapes the loop
                all_samples.append(sample)
                return sample

            cycle_started_at = _utc_now()
            cycle_started_tick = monotonic_fn()
            result: AnalyticsDatasetBenchmarkLiveEvaluationResult | None = None
            failure_type = ""
            cycle_guard_reasons: list[str] = []

            def case_guard() -> str | None:
                if (output_dir / policy.stop_file_name).exists():
                    cycle_guard_reasons.append("stop_file_detected")  # noqa: B023 - consumed inside the same iteration; never escapes the loop
                    return "stop_file_detected"
                sample = tracked_sampler()
                reasons = _resource_stop_reasons(sample, policy)
                if reasons:
                    cycle_guard_reasons.extend(reasons)  # noqa: B023 - consumed inside the same iteration; never escapes the loop
                    return reasons[0]
                return None

            try:
                result = run_analytics_dataset_benchmark_live_evaluation(
                    dataset_manifest_path,
                    database_path,
                    semantic_state_path,
                    relationships_path,
                    benchmark_pack_path,
                    benchmark_approval_path,
                    live_authorization_path,
                    output_dir / "cycles" / f"cycle-{cycle_index:04d}",
                    provider,
                    timeout_seconds=timeout_seconds,
                    execute=True,
                    allow_network=True,
                    resource_sampler=tracked_sampler,
                    case_guard=case_guard,
                )
            except Exception as error:
                failure_type = type(error).__name__
            cycle_completed_at = _utc_now()
            row, case_rows = _cycle_row(
                cycle_index,
                result,
                cycle_samples,
                cycle_started_at,
                cycle_completed_at,
                monotonic_fn() - cycle_started_tick,
                failure_type,
            )
            cycle_rows.append(row)
            _update_case_observations(case_observations, case_rows)
            heartbeat_at = cycle_completed_at

            technical_error = bool(failure_type) or result is None or result.blocker_count > 0
            consecutive_errors = consecutive_errors + 1 if technical_error else 0
            if "stop_file_detected" in cycle_guard_reasons:
                status = "stopped_by_request"
                stop_reason = "stop_file_detected"
            elif cycle_guard_reasons:
                status = "stopped_resource_guard"
                stop_reason = sorted(set(cycle_guard_reasons))[0]
            elif row["provider_timeout"]:
                status = "stopped_provider_timeout"
                stop_reason = "provider_timeout_detected"
            else:
                post_reasons = [
                    reason
                    for sample in cycle_samples
                    for reason in _resource_stop_reasons(sample, policy)
                ]
                if post_reasons:
                    status = "stopped_resource_guard"
                    stop_reason = sorted(set(post_reasons))[0]
                elif consecutive_errors >= policy.max_consecutive_cycle_errors:
                    status = "stopped_error_limit"
                    stop_reason = "consecutive_technical_error_limit_reached"

            manifest = _manifest(
                status=status,
                mode=mode,
                source=source,
                authorization_sha256=authorization_hash,
                provider=provider,
                timeout_seconds=timeout_seconds,
                policy=policy,
                blockers=blockers,
                cycle_rows=cycle_rows,
                all_samples=all_samples,
                stop_reason=stop_reason,
                started_at=started_at,
                heartbeat_at=heartbeat_at,
                completed_at=None,
            )
            _write_state(output_dir, manifest, cycle_rows, case_observations)
            if status != "running":
                break
            if len(cycle_rows) >= policy.max_cycles:
                status = "completed"
                stop_reason = "maximum_cycles_reached"
                break
            status, stop_reason = _cooldown(
                output_dir,
                policy,
                sampler,
                sleep_fn,
                all_samples,
            )
            if status != "running":
                break

        if status == "running":
            status = "completed"
            stop_reason = "maximum_cycles_reached"
        completed_at = _utc_now()
        heartbeat_at = completed_at
        manifest = _manifest(
            status=status,
            mode=mode,
            source=source,
            authorization_sha256=authorization_hash,
            provider=provider,
            timeout_seconds=timeout_seconds,
            policy=policy,
            blockers=blockers,
            cycle_rows=cycle_rows,
            all_samples=all_samples,
            stop_reason=stop_reason,
            started_at=started_at,
            heartbeat_at=heartbeat_at,
            completed_at=completed_at,
        )
        _write_state(output_dir, manifest, cycle_rows, case_observations)

    return AnalyticsOllamaSoakResult(
        output_dir=output_dir,
        status=status,
        mode=mode,
        manifest_path=output_dir / MANIFEST_NAME,
        cycles_path=output_dir / CYCLES_NAME,
        cases_path=output_dir / CASES_NAME,
        report_path=output_dir / REPORT_NAME,
        cycle_count=len(cycle_rows),
        provider_call_count=sum(int(row["provider_calls"]) for row in cycle_rows),
        blocker_count=len(blockers),
        stop_reason=stop_reason,
        outputs_changed=outputs_changed,
    )
