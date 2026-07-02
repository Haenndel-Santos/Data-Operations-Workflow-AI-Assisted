from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .io_utils import discover_input_files, ensure_dir, normalize_columns, read_csv_flexible, table_name_from_path


@dataclass(frozen=True)
class ConvertedTable:
    table_name: str
    source_path: Path
    csv_path: Path
    parquet_path: Path
    rows: int
    columns: int


def _write_table(df: pd.DataFrame, output_dir: Path, table_name: str) -> ConvertedTable:
    csv_dir = ensure_dir(output_dir / "csv")
    parquet_dir = ensure_dir(output_dir / "parquet")
    csv_path = csv_dir / f"{table_name}.csv"
    parquet_path = parquet_dir / f"{table_name}.parquet"
    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)
    return ConvertedTable(
        table_name=table_name,
        source_path=Path(),
        csv_path=csv_path,
        parquet_path=parquet_path,
        rows=len(df),
        columns=len(df.columns),
    )


def convert_file(path: Path, output_dir: Path) -> list[ConvertedTable]:
    suffix = path.suffix.lower()
    converted: list[ConvertedTable] = []

    if suffix == ".csv":
        df = normalize_columns(read_csv_flexible(path))
        table = _write_table(df, output_dir, table_name_from_path(path))
        converted.append(table.__class__(**{**table.__dict__, "source_path": path}))
        return converted

    if suffix in {".xlsx", ".xls"}:
        workbook = pd.ExcelFile(path)
        for sheet_name in workbook.sheet_names:
            df = normalize_columns(pd.read_excel(path, sheet_name=sheet_name))
            table = _write_table(df, output_dir, table_name_from_path(path, sheet_name))
            converted.append(table.__class__(**{**table.__dict__, "source_path": path}))
        return converted

    raise ValueError(f"Unsupported input file: {path}")


def convert_directory(input_dir: Path, output_dir: Path) -> list[ConvertedTable]:
    ensure_dir(output_dir)
    tables: list[ConvertedTable] = []
    for path in discover_input_files(input_dir):
        tables.extend(convert_file(path, output_dir))
    if not tables:
        raise FileNotFoundError(f"No CSV/XLSX files found in {input_dir}")
    return tables
