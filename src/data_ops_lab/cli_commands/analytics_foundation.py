from __future__ import annotations

import argparse
from pathlib import Path


def register_analytics_foundation_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register local analytics contract validation and performance commands."""

    analytics_module_registry = subparsers.add_parser(
        "analytics-module-registry-validate",
        help="Validate analytics module contracts and workflow dependencies without executing them.",
    )
    analytics_module_registry.add_argument(
        "--registry",
        type=Path,
        default=Path("config/orchestrator/analytics_module_registry.yml"),
        help="Version-1 declarative analytics module registry YAML.",
    )
    analytics_module_registry.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root used only to validate declared test-file paths.",
    )
    analytics_module_registry.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_module_registry_validation"),
        help="New or byte-identical directory for dry-run registry validation evidence.",
    )

    pipeline_performance_baseline = subparsers.add_parser(
        "pipeline-performance-baseline",
        help="Measure Pandas-heavy pipeline stages with generated synthetic Parquet only.",
    )
    pipeline_performance_baseline.add_argument(
        "--rows-per-table",
        type=int,
        default=50_000,
    )
    pipeline_performance_baseline.add_argument(
        "--table-count",
        type=int,
        default=3,
    )
    pipeline_performance_baseline.add_argument(
        "--stage-timeout-seconds",
        type=int,
        default=120,
    )
    pipeline_performance_baseline.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/pipeline_performance_baseline"),
        help="New or empty directory for run-specific synthetic measurement evidence.",
    )
