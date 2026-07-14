from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data_ops_lab.schema import (
    detect_schema,
    identify_keys,
    load_tables,
    write_schema_outputs,
)
from data_ops_lab.source_onboarding import file_sha256


def write_table(path: Path, payload: dict[str, list[object]], schema: pa.Schema) -> None:
    table = pa.Table.from_pydict(payload, schema=schema)
    pq.write_table(table, path, compression="zstd")


def build_fixture(path: Path) -> None:
    path.mkdir(parents=True)
    write_table(
        path / "parents.parquet",
        {
            "parent_id": ["P1", "P2", "P3", "P4"],
            "parent_code": ["A", "B", "C", "D"],
            "category": ["retail", "retail", "trade", "trade"],
            "amount": [10.0, 20.0, float("nan"), 40.0],
            "optional_note": ["one", None, "three", None],
        },
        pa.schema(
            [
                ("parent_id", pa.string()),
                ("parent_code", pa.string()),
                ("category", pa.string()),
                ("amount", pa.float64()),
                ("optional_note", pa.string()),
            ]
        ),
    )
    write_table(
        path / "parent_lines.parquet",
        {
            "line_id": [1, 2, 3, 4, 5],
            "parent_id": ["P1", "P1", "P2", "P3", "P4"],
            "ref_nr": ["OC1", "OC1", "OC2", "OC3", "OC4"],
            "quantity": [1, 2, 3, 4, 5],
        },
        pa.schema(
            [
                ("line_id", pa.int64()),
                ("parent_id", pa.string()),
                ("ref_nr", pa.string()),
                ("quantity", pa.int64()),
            ]
        ),
    )
    write_table(
        path / "empty_table.parquet",
        {"empty_id": [], "label": []},
        pa.schema([("empty_id", pa.int64()), ("label", pa.string())]),
    )


def test_duckdb_pushdown_preserves_pandas_schema_and_key_contract(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "parquet"
    output_dir = tmp_path / "metadata"
    build_fixture(parquet_dir)
    before = {path.name: file_sha256(path) for path in parquet_dir.glob("*.parquet")}
    tables = load_tables(parquet_dir)
    expected_schema = detect_schema(tables)
    expected_keys = identify_keys(tables)

    actual_schema, actual_keys = write_schema_outputs(parquet_dir, output_dir)

    assert actual_schema == expected_schema
    assert actual_keys == expected_keys
    assert actual_keys["primary_keys"]["parent_lines"] == ["line_id"]
    assert "ref_nr" not in actual_keys["primary_keys"]["parent_lines"]
    assert {
        "from_table": "parent_lines",
        "from_column": "parent_id",
        "to_table": "parents",
        "to_column": "parent_id",
        "coverage_pct": 100.0,
    } in actual_keys["foreign_keys"]
    assert {path.name: file_sha256(path) for path in parquet_dir.glob("*.parquet")} == before


def test_schema_output_no_longer_calls_pandas_read_parquet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parquet_dir = tmp_path / "parquet"
    build_fixture(parquet_dir)

    def reject_full_table_read(*args, **kwargs):
        raise AssertionError("full-table pandas read is not allowed")

    monkeypatch.setattr(pd, "read_parquet", reject_full_table_read)
    schema, keys = write_schema_outputs(parquet_dir, tmp_path / "metadata")

    assert schema
    assert keys
