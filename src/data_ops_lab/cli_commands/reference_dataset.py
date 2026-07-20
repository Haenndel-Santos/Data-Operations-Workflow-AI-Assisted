from __future__ import annotations

import argparse
from pathlib import Path


def register_reference_dataset_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register local reference-dataset conversion and validation commands."""

    benchmark_convert_sql = subparsers.add_parser(
        "benchmark-convert-sql",
        help="Safely materialize local T-SQL sample tables and rows as DuckDB and Parquet.",
    )
    benchmark_convert_sql.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Local T-SQL sample script containing CREATE TABLE and INSERT statements.",
    )
    benchmark_convert_sql.add_argument(
        "--dataset",
        required=True,
        help="Stable dataset name used for normalized derived artifacts.",
    )
    benchmark_convert_sql.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New or verified-identical local derived dataset directory.",
    )

    reference_dataset_validate = subparsers.add_parser(
        "reference-dataset-validate",
        help="Validate provenance, reproducibility, schema, keys, and relationship-review state for a local reference dataset.",
    )
    reference_dataset_validate.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Versioned reference-dataset onboarding manifest.",
    )
    reference_dataset_validate.add_argument(
        "--review",
        type=Path,
        help="Optional completed relationship review bound to the exact manifest and candidates.",
    )
    reference_dataset_validate.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New or verified-identical local validation evidence directory.",
    )
