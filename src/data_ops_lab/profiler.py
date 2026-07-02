from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .io_utils import ensure_dir


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def profile_dataframe(df: pd.DataFrame, table_name: str) -> dict[str, Any]:
    row_count = len(df)
    duplicate_rows = int(df.duplicated().sum()) if row_count else 0
    columns = []

    for column in df.columns:
        series = df[column]
        non_null = int(series.notna().sum())
        unique_count = int(series.nunique(dropna=True))
        examples = [_json_safe(value) for value in series.dropna().head(5).tolist()]
        columns.append(
            {
                "name": str(column),
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "null_pct": round(float(series.isna().mean() * 100), 2) if row_count else 0,
                "unique_count": unique_count,
                "unique_pct": round(float(unique_count / row_count * 100), 2) if row_count else 0,
                "non_null_count": non_null,
                "examples": examples,
            }
        )

    return {
        "table": table_name,
        "row_count": row_count,
        "column_count": len(df.columns),
        "duplicate_rows": duplicate_rows,
        "columns": columns,
    }


def profile_parquet_directory(parquet_dir: Path, output_dir: Path) -> dict[str, Any]:
    ensure_dir(output_dir)
    profiles: dict[str, Any] = {}
    for path in sorted(parquet_dir.glob("*.parquet")):
        table_name = path.stem
        profiles[table_name] = profile_dataframe(pd.read_parquet(path), table_name)

    output_path = output_dir / "data_profile.json"
    output_path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    return profiles
