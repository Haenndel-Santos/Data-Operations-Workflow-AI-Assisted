from __future__ import annotations

import csv
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from .performance_worker import STAGES
from .source_onboarding import file_sha256


MANIFEST_NAME = "pipeline_performance_baseline.yml"
METRICS_NAME = "pipeline_performance_metrics.csv"
REPORT_NAME = "pipeline_performance_report.md"
MIN_ROWS_PER_TABLE = 100
MAX_ROWS_PER_TABLE = 1_000_000
MIN_TABLE_COUNT = 2
MAX_TABLE_COUNT = 12
MIN_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class PerformanceBaselineResult:
    output_dir: Path
    status: str
    manifest_path: Path
    metrics_path: Path
    report_path: Path
    stage_count: int
    completed_stage_count: int
    highest_memory_stage: str | None
    outputs_changed: bool


def bounded_int(value: int, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def generate_synthetic_parquet(
    target_dir: Path,
    *,
    rows_per_table: int,
    table_count: int,
) -> list[dict[str, Any]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for table_index in range(table_count):
        row_numbers = list(range(rows_per_table))
        table = pa.table(
            {
                "record_id": pa.array(row_numbers, type=pa.int64()),
                "parent_id": pa.array(row_numbers, type=pa.int64()),
                "status": pa.array(
                    ["open", "closed", "pending", "cancelled"]
                    * (rows_per_table // 4)
                    + ["open"] * (rows_per_table % 4),
                    type=pa.string(),
                ),
                "amount": pa.array(
                    [float((value * 17 + table_index) % 100_000) / 100 for value in row_numbers],
                    type=pa.float64(),
                ),
                "event_date": pa.array(
                    [f"2026-01-{(value % 28) + 1:02d}" for value in row_numbers],
                    type=pa.string(),
                ),
                "description": pa.array(
                    [f"synthetic-{table_index:02d}-{value % 1000:04d}" for value in row_numbers],
                    type=pa.string(),
                ),
            }
        )
        path = target_dir / f"table_{table_index:02d}.parquet"
        pq.write_table(table, path, compression="zstd", use_dictionary=True)
        files.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return files


def worker_environment() -> dict[str, str]:
    environment = os.environ.copy()
    source_root = str(Path(__file__).resolve().parents[1])
    current = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = source_root + (os.pathsep + current if current else "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_worker(
    stage: str,
    input_dir: Path,
    output_dir: Path,
    temp_dir: Path,
    table_count: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "data_ops_lab.performance_worker",
        "--stage",
        stage,
        "--input",
        str(input_dir),
        "--output",
        str(output_dir),
        "--temp",
        str(temp_dir),
        "--table-count",
        str(table_count),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=worker_environment(),
        )
    except subprocess.TimeoutExpired:
        return {
            "stage": stage,
            "status": "blocked",
            "runtime_seconds": float(timeout_seconds),
            "peak_process_memory_bytes": 0,
            "process_memory_method": "unavailable",
            "peak_python_allocation_bytes": 0,
            "input_bytes": directory_bytes(input_dir),
            "scanned_bytes": 0,
            "output_bytes": directory_bytes(output_dir),
            "temporary_storage_bytes": directory_bytes(temp_dir),
            "error_type": "TimeoutExpired",
        }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return {
            "stage": stage,
            "status": "blocked",
            "runtime_seconds": 0.0,
            "peak_process_memory_bytes": 0,
            "process_memory_method": "unavailable",
            "peak_python_allocation_bytes": 0,
            "input_bytes": directory_bytes(input_dir),
            "scanned_bytes": 0,
            "output_bytes": directory_bytes(output_dir),
            "temporary_storage_bytes": directory_bytes(temp_dir),
            "error_type": "WorkerProtocolError",
        }
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError:
        result = {}
    required = {
        "stage",
        "status",
        "runtime_seconds",
        "peak_process_memory_bytes",
        "process_memory_method",
        "peak_python_allocation_bytes",
        "input_bytes",
        "scanned_bytes",
        "output_bytes",
        "temporary_storage_bytes",
        "error_type",
    }
    if not isinstance(result, dict) or set(result) != required:
        return {
            "stage": stage,
            "status": "blocked",
            "runtime_seconds": 0.0,
            "peak_process_memory_bytes": 0,
            "process_memory_method": "unavailable",
            "peak_python_allocation_bytes": 0,
            "input_bytes": directory_bytes(input_dir),
            "scanned_bytes": 0,
            "output_bytes": directory_bytes(output_dir),
            "temporary_storage_bytes": directory_bytes(temp_dir),
            "error_type": "WorkerProtocolError",
        }
    if completed.returncode != 0:
        result["status"] = "blocked"
    return result


def metrics_csv(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "stage",
            "status",
            "runtime_seconds",
            "peak_process_memory_bytes",
            "process_memory_method",
            "peak_python_allocation_bytes",
            "input_bytes",
            "scanned_bytes",
            "output_bytes",
            "temporary_storage_bytes",
            "error_type",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def render_report(
    status: str,
    rows_per_table: int,
    table_count: int,
    metrics: list[dict[str, Any]],
) -> str:
    completed = [row for row in metrics if row["status"] == "completed"]
    ranked = sorted(completed, key=lambda row: row["peak_process_memory_bytes"], reverse=True)
    lines = [
        "# Synthetic Pipeline Performance Baseline",
        "",
        f"- Status: `{status}`",
        f"- Rows per table: {rows_per_table}",
        f"- Tables: {table_count}",
        f"- Stages completed: {len(completed)}/{len(metrics)}",
        "",
        "## Peak-Memory Ranking",
        "",
        "| Rank | Stage | Peak process bytes | Runtime seconds | Input/scanned bytes | Output bytes |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(ranked, start=1):
        lines.append(
            f"| {rank} | `{row['stage']}` | {row['peak_process_memory_bytes']} | "
            f"{row['runtime_seconds']} | {row['scanned_bytes']} | {row['output_bytes']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Input is generated synthetic Parquet and is deleted after measurement.",
            "- Each stage runs in a fresh local child process.",
            "- Scanned bytes record the unique full-input footprint inspected by each stage, not repeated physical reads.",
            "- No EDS, benchmark dataset, provider, network, external database, approval, upload, or training is used.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Performance baseline output is not a directory: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"Performance baseline output directory is not empty: {output_dir}. "
            "Measurements are run-specific and existing evidence was not overwritten."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")


def run_performance_baseline(
    output_dir: Path,
    *,
    rows_per_table: int = 50_000,
    table_count: int = 3,
    stage_timeout_seconds: int = 120,
) -> PerformanceBaselineResult:
    rows_per_table = bounded_int(
        rows_per_table,
        MIN_ROWS_PER_TABLE,
        MAX_ROWS_PER_TABLE,
        "rows_per_table",
    )
    table_count = bounded_int(table_count, MIN_TABLE_COUNT, MAX_TABLE_COUNT, "table_count")
    stage_timeout_seconds = bounded_int(
        stage_timeout_seconds,
        MIN_TIMEOUT_SECONDS,
        MAX_TIMEOUT_SECONDS,
        "stage_timeout_seconds",
    )
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError(
            f"Performance baseline output must be a new or empty directory: {output_dir}"
        )

    with tempfile.TemporaryDirectory(prefix="dataops_synthetic_performance_") as temporary:
        work_dir = Path(temporary)
        input_dir = work_dir / "input"
        files = generate_synthetic_parquet(
            input_dir,
            rows_per_table=rows_per_table,
            table_count=table_count,
        )
        metrics = [
            run_worker(
                stage,
                input_dir,
                work_dir / "stages" / stage,
                work_dir / "temp" / stage,
                table_count,
                stage_timeout_seconds,
            )
            for stage in STAGES
        ]

    completed = [row for row in metrics if row["status"] == "completed"]
    ranked = sorted(completed, key=lambda row: row["peak_process_memory_bytes"], reverse=True)
    status = "completed" if len(completed) == len(STAGES) else "blocked"
    manifest = {
        "version": 1,
        "status": status,
        "workload": {
            "type": "generated_synthetic_parquet",
            "rows_per_table": rows_per_table,
            "table_count": table_count,
            "columns_per_table": 6,
            "input_bytes": sum(item["bytes"] for item in files),
            "scanned_bytes_method": "unique_full_input_footprint",
            "files": files,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
        },
        "summary": {
            "stage_count": len(STAGES),
            "completed_stage_count": len(completed),
            "highest_memory_stage": ranked[0]["stage"] if ranked else None,
        },
        "controls": {
            "synthetic_only": True,
            "isolated_child_processes": True,
            "external_data_access": False,
            "external_database_access": False,
            "network_access": False,
            "provider_access": False,
            "approved_state_changes": False,
            "input_rows_persisted": False,
        },
    }
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        METRICS_NAME: metrics_csv(metrics),
        REPORT_NAME: render_report(status, rows_per_table, table_count, metrics),
    }
    write_outputs(output_dir, contents)
    return PerformanceBaselineResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        metrics_path=output_dir / METRICS_NAME,
        report_path=output_dir / REPORT_NAME,
        stage_count=len(STAGES),
        completed_stage_count=len(completed),
        highest_memory_stage=ranked[0]["stage"] if ranked else None,
        outputs_changed=True,
    )
