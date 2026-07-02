from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .io_utils import ensure_dir


ID_HINTS = ("id", "key", "number", "code")


def infer_semantic_type(column_name: str, series: pd.Series) -> str:
    name = column_name.lower()
    if name.endswith("_id") or name == "id" or any(name.endswith(f"_{hint}") for hint in ID_HINTS):
        return "identifier"
    if "date" in name or "created" in name or "updated" in name:
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        if any(token in name for token in ("amount", "price", "cost", "revenue", "sales", "total")):
            return "currency"
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    unique_ratio = series.nunique(dropna=True) / max(len(series), 1)
    if unique_ratio < 0.2:
        return "category"
    return "text"


def detect_schema(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    for table_name, df in tables.items():
        schema[table_name] = {
            "columns": [
                {
                    "name": column,
                    "physical_type": str(df[column].dtype),
                    "semantic_type": infer_semantic_type(column, df[column]),
                    "nullable": bool(df[column].isna().any()),
                }
                for column in df.columns
            ]
        }
    return schema


def identify_keys(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    primary_keys: dict[str, list[str]] = {}
    foreign_keys: list[dict[str, str | int | float]] = []

    for table_name, df in tables.items():
        candidates = []
        for column in df.columns:
            series = df[column].dropna()
            if len(series) == len(df) and series.nunique() == len(df):
                score = 0.5
                if column == "id" or column.endswith("_id"):
                    score = 2.0
                elif any(column.endswith(f"_{hint}") for hint in ("key", "code", "number")):
                    score = 1.5
                candidates.append({"column": column, "score": round(score, 2)})
        strong_candidates = [item for item in candidates if item["score"] >= 1.5]
        selected = strong_candidates or candidates[:1]
        primary_keys[table_name] = [
            item["column"] for item in sorted(selected, key=lambda item: item["score"], reverse=True)[:3]
        ]

    for left_name, left_df in tables.items():
        for left_col in left_df.columns:
            left_values = set(left_df[left_col].dropna().astype(str).unique())
            if not left_values:
                continue
            for right_name, right_df in tables.items():
                if left_name == right_name:
                    continue
                for right_col in primary_keys.get(right_name, []):
                    right_values = set(right_df[right_col].dropna().astype(str).unique())
                    if not right_values:
                        continue
                    overlap = len(left_values & right_values) / len(left_values)
                    name_match = left_col == right_col or left_col == f"{right_name.rstrip('s')}_id"
                    if overlap >= 0.8 and (name_match or left_col.endswith("_id")):
                        foreign_keys.append(
                            {
                                "from_table": left_name,
                                "from_column": left_col,
                                "to_table": right_name,
                                "to_column": right_col,
                                "coverage_pct": round(overlap * 100, 2),
                            }
                        )

    return {"primary_keys": primary_keys, "foreign_keys": foreign_keys}


def load_tables(parquet_dir: Path) -> dict[str, pd.DataFrame]:
    return {path.stem: pd.read_parquet(path) for path in sorted(parquet_dir.glob("*.parquet"))}


def write_schema_outputs(parquet_dir: Path, output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_dir(output_dir)
    tables = load_tables(parquet_dir)
    schema = detect_schema(tables)
    keys = identify_keys(tables)
    (output_dir / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (output_dir / "keys.json").write_text(json.dumps(keys, indent=2), encoding="utf-8")
    return schema, keys
