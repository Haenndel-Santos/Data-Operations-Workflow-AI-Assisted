from __future__ import annotations

import argparse
import json
import os
import platform
import time
import tracemalloc
from pathlib import Path
from typing import Any

from .cleaner import clean_parquet_directory
from .profiler import profile_parquet_directory
from .schema import write_schema_outputs
from .validator import validate_relationships


STAGES = ("profile", "clean", "schema", "relationships")


def directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def peak_process_memory_bytes() -> tuple[int, str]:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("page_fault_count", wintypes.DWORD),
                ("peak_working_set_size", ctypes.c_size_t),
                ("working_set_size", ctypes.c_size_t),
                ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                ("quota_paged_pool_usage", ctypes.c_size_t),
                ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
                ("quota_non_paged_pool_usage", ctypes.c_size_t),
                ("pagefile_usage", ctypes.c_size_t),
                ("peak_pagefile_usage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        succeeded = psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        if not succeeded:
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.peak_working_set_size), "windows_peak_working_set"

    import resource

    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    multiplier = 1 if platform.system() == "Darwin" else 1024
    return maximum * multiplier, "posix_ru_maxrss"


def relationship_contract(table_count: int) -> dict[str, Any]:
    return {
        "foreign_keys": [
            {
                "from_table": f"table_{index:02d}",
                "from_column": "parent_id",
                "to_table": "table_00",
                "to_column": "record_id",
            }
            for index in range(1, table_count)
        ]
    }


def run_stage(stage: str, input_dir: Path, output_dir: Path, table_count: int) -> None:
    if stage == "profile":
        profile_parquet_directory(input_dir, output_dir)
        return
    if stage == "clean":
        clean_parquet_directory(input_dir, output_dir)
        return
    if stage == "schema":
        write_schema_outputs(input_dir, output_dir)
        return
    if stage == "relationships":
        output_dir.mkdir(parents=True, exist_ok=True)
        results = validate_relationships(input_dir, relationship_contract(table_count))
        (output_dir / "relationships.json").write_text(
            json.dumps(results, indent=2),
            encoding="utf-8",
        )
        return
    raise ValueError(f"Unsupported stage: {stage}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal synthetic performance worker.")
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--temp", type=Path, required=True)
    parser.add_argument("--table-count", type=int, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(args.temp)
    os.environ["TMP"] = str(args.temp)
    os.environ["TMPDIR"] = str(args.temp)

    input_bytes = directory_bytes(args.input)
    tracemalloc.start()
    started = time.perf_counter()
    status = "completed"
    error_type = ""
    try:
        run_stage(args.stage, args.input, args.output, args.table_count)
    except Exception as error:  # pragma: no cover - exercised through parent failure evidence
        status = "blocked"
        error_type = type(error).__name__
    runtime_seconds = time.perf_counter() - started
    _, peak_python_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_memory_bytes, memory_method = peak_process_memory_bytes()

    result = {
        "stage": args.stage,
        "status": status,
        "runtime_seconds": round(runtime_seconds, 6),
        "peak_process_memory_bytes": peak_memory_bytes,
        "process_memory_method": memory_method,
        "peak_python_allocation_bytes": int(peak_python_bytes),
        "input_bytes": input_bytes,
        "scanned_bytes": input_bytes,
        "output_bytes": directory_bytes(args.output),
        "temporary_storage_bytes": directory_bytes(args.temp),
        "error_type": error_type,
    }
    print(json.dumps(result, sort_keys=True))
    if status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
