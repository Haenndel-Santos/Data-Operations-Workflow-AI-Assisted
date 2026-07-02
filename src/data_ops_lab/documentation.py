from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir
from .sql_assistant import SuggestedQuery, render_queries_markdown


def write_relationship_validation(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / "relationship_validation.csv"
    if not rows:
        path.write_text("relationship,left_rows,right_rows,matched_rows,unmatched_rows,match_rate_pct,right_key_duplicates,risk\n", encoding="utf-8")
        return path

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_sql_suggestions(queries: list[SuggestedQuery], output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / "sql_suggestions.md"
    path.write_text(render_queries_markdown(queries), encoding="utf-8")
    return path


def write_data_dictionary(schema: dict[str, Any], profiles: dict[str, Any], keys: dict[str, Any], output_dir: Path) -> Path:
    ensure_dir(output_dir)
    lines = ["# Data Dictionary", ""]

    for table_name, table_schema in schema.items():
        profile = profiles.get(table_name, {})
        lines.extend(
            [
                f"## {table_name}",
                "",
                f"- Rows: {profile.get('row_count', 0)}",
                f"- Columns: {profile.get('column_count', 0)}",
                f"- Primary key candidates: {', '.join(keys.get('primary_keys', {}).get(table_name, [])) or 'None detected'}",
                "",
                "| Column | Physical type | Semantic type | Nullable | Null % | Unique % |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        profile_columns = {column["name"]: column for column in profile.get("columns", [])}
        for column in table_schema["columns"]:
            stats = profile_columns.get(column["name"], {})
            lines.append(
                "| {name} | {physical} | {semantic} | {nullable} | {null_pct} | {unique_pct} |".format(
                    name=column["name"],
                    physical=column["physical_type"],
                    semantic=column["semantic_type"],
                    nullable=column["nullable"],
                    null_pct=stats.get("null_pct", ""),
                    unique_pct=stats.get("unique_pct", ""),
                )
            )
        lines.append("")

    lines.extend(["## Detected Relationships", ""])
    relationships = keys.get("foreign_keys", [])
    if not relationships:
        lines.append("No foreign key relationships were detected.")
    else:
        for relation in relationships:
            lines.append(
                "- {from_table}.{from_column} -> {to_table}.{to_column} ({coverage_pct}% coverage)".format(**relation)
            )

    path = output_dir / "data_dictionary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
