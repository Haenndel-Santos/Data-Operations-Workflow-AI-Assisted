from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_INPUTS = {".csv", ".xlsx", ".xls"}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "field"


def unique_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        base = slugify(name)
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result


def table_name_from_path(path: Path, sheet_name: str | None = None) -> str:
    base = slugify(path.stem)
    if sheet_name:
        return slugify(f"{base}_{sheet_name}")
    return base


def read_table(path: Path, sheet_name: str | None = None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_flexible(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path}")


def _parse_double_quoted_tab_text(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    row: list[str] = []
    field: list[str] = []
    i = 0
    in_field = False
    length = len(text)

    while i < length:
        if not in_field:
            if text.startswith('""', i):
                in_field = True
                i += 2
                continue
            if text[i] == "\t":
                row.append("")
                i += 1
                continue
            if text[i] in "\r\n":
                if row:
                    rows.append(row)
                    row = []
                if text[i] == "\r" and i + 1 < length and text[i + 1] == "\n":
                    i += 2
                else:
                    i += 1
                continue

            # Fallback for malformed unquoted fragments.
            in_field = True
            continue

        if text.startswith('""', i):
            next_char = text[i + 2] if i + 2 < length else ""
            if next_char in {"\t", "\r", "\n", ""}:
                row.append("".join(field))
                field = []
                in_field = False
                i += 2
                if next_char == "\t":
                    i += 1
                elif next_char in {"\r", "\n"}:
                    rows.append(row)
                    row = []
                    if next_char == "\r" and i + 1 < length and text[i + 1] == "\n":
                        i += 2
                    else:
                        i += 1
                continue
            field.append('"')
            i += 2
            continue

        field.append(text[i])
        i += 1

    if in_field or field:
        row.append("".join(field))
    if row:
        rows.append(row)

    return rows


def _rows_to_dataframe(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    header = [str(value).replace("\r", " ").replace("\n", " ").strip() for value in rows[0]]
    width = len(header)
    normalized_rows: list[list[Any]] = []
    for row in rows[1:]:
        if len(row) < width:
            row = row + [None] * (width - len(row))
        elif len(row) > width:
            row = row[: width - 1] + ["\t".join(row[width - 1 :])]
        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=header)


def read_csv_flexible(path: Path) -> pd.DataFrame:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    if sample.lstrip().startswith('""') and "\t" in sample:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        return _rows_to_dataframe(_parse_double_quoted_tab_text(text))

    try:
        df = pd.read_csv(path)
        if len(df.columns) > 1:
            return df
    except pd.errors.ParserError:
        pass

    try:
        df = pd.read_csv(path, sep="\t", engine="python", quoting=3)
        if len(df.columns) > 1:
            df.columns = [str(column).strip().strip('"') for column in df.columns]
            return df.map(lambda value: value.strip().strip('"') if isinstance(value, str) else value)
    except pd.errors.ParserError:
        pass

    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return _rows_to_dataframe(_parse_double_quoted_tab_text(text))


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = unique_names([str(column) for column in cleaned.columns])
    return cleaned


def discover_input_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_INPUTS
    )
