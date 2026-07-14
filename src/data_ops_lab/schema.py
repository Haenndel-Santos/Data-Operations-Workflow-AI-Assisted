from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

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


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def valid_value_expression(column: str, arrow_type: pa.DataType) -> str:
    quoted = quote_identifier(column)
    if pa.types.is_floating(arrow_type):
        return f"{quoted} is not null and not isnan({quoted})"
    return f"{quoted} is not null"


def comparable_text_expression(column: str, arrow_type: pa.DataType) -> str:
    quoted = quote_identifier(column)
    if pa.types.is_boolean(arrow_type):
        return f"case when {quoted} then 'True' else 'False' end"
    return f"cast({quoted} as varchar)"


def parquet_table_stats(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
) -> dict[str, Any]:
    arrow_schema = pq.read_schema(path)
    empty_frame = arrow_schema.empty_table().to_pandas()
    expressions = ["count(*)"]
    for field in arrow_schema:
        valid = valid_value_expression(field.name, field.type)
        quoted = quote_identifier(field.name)
        expressions.extend(
            [
                f"count(*) filter (where {valid})",
                f"count(distinct {quoted}) filter (where {valid})",
            ]
        )
    row = connection.execute(
        f"select {', '.join(expressions)} from read_parquet(?)",
        [str(path)],
    ).fetchone()
    if row is None:
        raise ValueError(f"Unable to profile Parquet metadata: {path}")
    row_count = int(row[0])
    columns: dict[str, dict[str, Any]] = {}
    offset = 1
    for field in arrow_schema:
        non_null_count = int(row[offset])
        unique_count = int(row[offset + 1])
        columns[field.name] = {
            "physical_type": str(empty_frame[field.name].dtype),
            "arrow_type": field.type,
            "non_null_count": non_null_count,
            "null_count": row_count - non_null_count,
            "unique_count": unique_count,
        }
        offset += 2
    return {"path": path, "row_count": row_count, "columns": columns}


def infer_semantic_type_from_stats(
    column_name: str,
    physical_type: str,
    unique_count: int,
    row_count: int,
) -> str:
    name = column_name.lower()
    if name.endswith("_id") or name == "id" or any(
        name.endswith(f"_{hint}") for hint in ID_HINTS
    ):
        return "identifier"
    if "date" in name or "created" in name or "updated" in name:
        return "date"
    dtype = pd.api.types.pandas_dtype(physical_type)
    if pd.api.types.is_numeric_dtype(dtype):
        if any(token in name for token in ("amount", "price", "cost", "revenue", "sales", "total")):
            return "currency"
        return "number"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "date"
    unique_ratio = unique_count / max(row_count, 1)
    if unique_ratio < 0.2:
        return "category"
    return "text"


def detect_schema_from_stats(stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    for table_name, table in stats.items():
        row_count = table["row_count"]
        schema[table_name] = {
            "columns": [
                {
                    "name": column_name,
                    "physical_type": column["physical_type"],
                    "semantic_type": infer_semantic_type_from_stats(
                        column_name,
                        column["physical_type"],
                        column["unique_count"],
                        row_count,
                    ),
                    "nullable": column["null_count"] > 0,
                }
                for column_name, column in table["columns"].items()
            ]
        }
    return schema


def identify_primary_keys_from_stats(
    stats: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    primary_keys: dict[str, list[str]] = {}
    for table_name, table in stats.items():
        candidates: list[dict[str, str | float]] = []
        for column_name, column in table["columns"].items():
            if (
                column["non_null_count"] == table["row_count"]
                and column["unique_count"] == table["row_count"]
            ):
                score = 0.5
                if column_name == "id" or column_name.endswith("_id"):
                    score = 2.0
                elif any(column_name.endswith(f"_{hint}") for hint in ("key", "code", "number")):
                    score = 1.5
                candidates.append({"column": column_name, "score": score})
        strong_candidates = [item for item in candidates if item["score"] >= 1.5]
        selected = strong_candidates or candidates[:1]
        primary_keys[table_name] = [
            str(item["column"])
            for item in sorted(selected, key=lambda item: float(item["score"]), reverse=True)[:3]
        ]
    return primary_keys


def distinct_overlap_count(
    connection: duckdb.DuckDBPyConnection,
    left: dict[str, Any],
    left_column: str,
    right: dict[str, Any],
    right_column: str,
) -> int:
    left_metadata = left["columns"][left_column]
    right_metadata = right["columns"][right_column]
    left_valid = valid_value_expression(left_column, left_metadata["arrow_type"])
    right_valid = valid_value_expression(right_column, right_metadata["arrow_type"])
    left_value = comparable_text_expression(left_column, left_metadata["arrow_type"])
    right_value = comparable_text_expression(right_column, right_metadata["arrow_type"])
    query = f"""
        with left_values as (
            select distinct {left_value} as value
            from read_parquet(?)
            where {left_valid}
        ),
        right_values as (
            select distinct {right_value} as value
            from read_parquet(?)
            where {right_valid}
        )
        select count(*)
        from left_values as left_value
        semi join right_values as right_value
          on left_value.value = right_value.value
    """
    row = connection.execute(query, [str(left["path"]), str(right["path"])]).fetchone()
    return int(row[0]) if row else 0


def identify_keys_from_stats(
    connection: duckdb.DuckDBPyConnection,
    stats: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    primary_keys = identify_primary_keys_from_stats(stats)
    foreign_keys: list[dict[str, str | int | float]] = []
    for left_name, left in stats.items():
        for left_column, left_metadata in left["columns"].items():
            left_unique_count = left_metadata["unique_count"]
            if not left_unique_count:
                continue
            for right_name, right in stats.items():
                if left_name == right_name:
                    continue
                for right_column in primary_keys.get(right_name, []):
                    right_unique_count = right["columns"][right_column]["unique_count"]
                    if not right_unique_count:
                        continue
                    name_match = (
                        left_column == right_column
                        or left_column == f"{right_name.rstrip('s')}_id"
                    )
                    if not (name_match or left_column.endswith("_id")):
                        continue
                    overlap = distinct_overlap_count(
                        connection,
                        left,
                        left_column,
                        right,
                        right_column,
                    ) / left_unique_count
                    if overlap >= 0.8:
                        foreign_keys.append(
                            {
                                "from_table": left_name,
                                "from_column": left_column,
                                "to_table": right_name,
                                "to_column": right_column,
                                "coverage_pct": round(overlap * 100, 2),
                            }
                        )
    return {"primary_keys": primary_keys, "foreign_keys": foreign_keys}


def analyze_parquet_directory(parquet_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = sorted(parquet_dir.glob("*.parquet"))
    with duckdb.connect(":memory:") as connection:
        connection.execute("set threads = 1")
        stats = {path.stem: parquet_table_stats(connection, path) for path in paths}
        schema = detect_schema_from_stats(stats)
        keys = identify_keys_from_stats(connection, stats)
    return schema, keys


def write_schema_outputs(parquet_dir: Path, output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_dir(output_dir)
    schema, keys = analyze_parquet_directory(parquet_dir)
    (output_dir / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (output_dir / "keys.json").write_text(json.dumps(keys, indent=2), encoding="utf-8")
    return schema, keys
