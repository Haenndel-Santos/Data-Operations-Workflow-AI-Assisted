from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io_utils import ensure_dir


def export_for_tableau(cleaned_dir: Path, output_dir: Path) -> dict[str, Path]:
    csv_dir = ensure_dir(output_dir / "csv")
    parquet_dir = ensure_dir(output_dir / "parquet")
    outputs: dict[str, Path] = {}

    for path in sorted(cleaned_dir.glob("*.parquet")):
        df = pd.read_parquet(path)
        csv_path = csv_dir / f"{path.stem}.csv"
        parquet_path = parquet_dir / f"{path.stem}.parquet"
        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False)
        outputs[path.stem] = csv_path

    (output_dir / "README_TABLEAU.md").write_text(
        "# Tableau Export Layer\n\n"
        "Use the CSV files in `csv/` for maximum compatibility with Tableau Public, "
        "or the Parquet files in `parquet/` when your Tableau environment supports them.\n\n"
        "Recommended validation before dashboarding:\n"
        "- Compare row counts against `metadata/data_profile.json`.\n"
        "- Compare key relationships against `metadata/relationship_validation.csv`.\n"
        "- Use numeric control totals from `metadata/sql_suggestions.md`.\n",
        encoding="utf-8",
    )
    return outputs
