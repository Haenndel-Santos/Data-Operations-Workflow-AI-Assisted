from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


def create_duckdb_database(parquet_dir: Path, database_path: Path) -> list[str]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    created_tables: list[str] = []
    with duckdb.connect(str(database_path)) as con:
        for path in sorted(parquet_dir.glob("*.parquet")):
            table_name = path.stem
            con.execute(f"create or replace table {table_name} as select * from read_parquet(?)", [str(path)])  # noqa: S608 - table name is slugified to [a-z0-9_]; path bound as parameter
            created_tables.append(table_name)
    return created_tables


def validate_relationships(parquet_dir: Path, keys: dict[str, Any]) -> list[dict[str, Any]]:
    tables = {path.stem: pd.read_parquet(path) for path in sorted(parquet_dir.glob("*.parquet"))}
    results: list[dict[str, Any]] = []

    for relation in keys.get("foreign_keys", []):
        left_name = relation["from_table"]
        right_name = relation["to_table"]
        left_col = relation["from_column"]
        right_col = relation["to_column"]
        left = tables[left_name]
        right = tables[right_name]

        joined = left.merge(
            right[[right_col]].drop_duplicates(),
            how="left",
            left_on=left_col,
            right_on=right_col,
            indicator=True,
        )
        matched = int((joined["_merge"] == "both").sum())
        result = {
            "relationship": f"{left_name}.{left_col} -> {right_name}.{right_col}",
            "left_rows": int(len(left)),
            "right_rows": int(len(right)),
            "matched_rows": matched,
            "unmatched_rows": int(len(left) - matched),
            "match_rate_pct": round(matched / max(len(left), 1) * 100, 2),
            "right_key_duplicates": int(right[right_col].duplicated().sum()),
            "risk": "high" if int(right[right_col].duplicated().sum()) else "low",
        }
        results.append(result)

    return results
