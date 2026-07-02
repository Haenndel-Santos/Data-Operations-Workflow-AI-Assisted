from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .io_utils import ensure_dir, normalize_columns


BLANK_VALUES = {"", " ", "na", "n/a", "none", "null", "-", "--"}


def _looks_like_date(column_name: str) -> bool:
    return bool(re.search(r"(^|_)(date|dt|created|updated|closed|opened)($|_)", column_name))


def _looks_like_number(series: pd.Series) -> bool:
    if series.dropna().empty:
        return False
    text = series.dropna().astype(str).str.replace(",", "", regex=False).str.strip()
    converted = pd.to_numeric(text, errors="coerce")
    return float(converted.notna().mean()) >= 0.9


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip()
    sample = text.dropna().head(20)
    iso_like = not sample.empty and sample.str.match(r"^\d{4}-\d{2}-\d{2}").mean() >= 0.8
    return pd.to_datetime(text, errors="coerce", dayfirst=not iso_like)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = normalize_columns(df)

    for column in cleaned.columns:
        series = cleaned[column]
        if series.dtype == "object":
            text = series.astype("string").str.strip()
            text = text.mask(text.str.lower().isin(BLANK_VALUES), pd.NA)
            cleaned[column] = text

        if _looks_like_date(column):
            parsed = _parse_dates(cleaned[column])
            if parsed.notna().sum() > 0:
                cleaned[column] = parsed.dt.date
            continue

        if cleaned[column].dtype == "object" or str(cleaned[column].dtype) == "string":
            if _looks_like_number(cleaned[column]):
                cleaned[column] = pd.to_numeric(
                    cleaned[column].astype("string").str.replace(",", "", regex=False),
                    errors="coerce",
                )

    return cleaned


def clean_parquet_directory(input_dir: Path, output_dir: Path) -> dict[str, Path]:
    ensure_dir(output_dir)
    outputs: dict[str, Path] = {}
    for path in sorted(input_dir.glob("*.parquet")):
        cleaned = clean_dataframe(pd.read_parquet(path))
        output_path = output_dir / f"{path.stem}.parquet"
        cleaned.to_parquet(output_path, index=False)
        cleaned.to_csv(output_dir / f"{path.stem}.csv", index=False)
        outputs[path.stem] = output_path
    return outputs
