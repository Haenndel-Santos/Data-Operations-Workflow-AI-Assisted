from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .io_utils import normalize_columns, read_table
from .source_onboarding import backup_existing, ensure_dir


DATA_DIR = Path("originaldatabase")
OUTPUT_DIR = Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet")

PD_PATTERN = re.compile(r"^PD[0-9]{2}[0-9]{5}$")
ALT_REFERENCE_COLUMNS = {"suppl_part_nr_sku", "product_barcode_ce", "product_code", "sku", "item_code"}
IDENTITY_HINTS = (
    "name",
    "description",
    "creditor",
    "supplier",
    "group",
    "status",
    "price",
    "sales",
    "cost",
    "date",
    "barcode",
    "sku",
    "hour_type",
)


@dataclass(frozen=True)
class ProductReferenceAuditResult:
    output_dir: Path
    report_path: Path
    total_products: int
    duplicate_group_count: int
    duplicate_occurrence_count: int
    empty_reference_count: int
    product_status: str


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def masked_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def product_dataframe(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "Product.xlsx"
    workbook = pd.ExcelFile(path)
    return normalize_columns(read_table(path, sheet_name=workbook.sheet_names[0]))


def clean_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalized_value(value: Any) -> str:
    return clean_value(value).casefold()


def reference_series(df: pd.DataFrame) -> pd.Series:
    if "part_nr_sku" not in df.columns:
        raise ValueError("Product data must contain part_nr_sku / Part. nr. (SKU).")
    return df["part_nr_sku"].map(clean_value)


def comparable_columns(df: pd.DataFrame) -> list[str]:
    columns = []
    for column in df.columns:
        if column == "part_nr_sku":
            continue
        lowered = column.lower()
        if any(hint in lowered for hint in IDENTITY_HINTS):
            columns.append(column)
    return columns or [column for column in df.columns if column != "part_nr_sku"]


def field_comparison(rows: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    comparisons = []
    for column in columns:
        values = [normalized_value(value) for value in rows[column].tolist()]
        filled_values = [value for value in values if value]
        unique_values = sorted(set(filled_values))
        if not filled_values:
            status = "all_empty"
        elif len(unique_values) == 1:
            status = "same"
        else:
            status = "different"
        comparisons.append(
            {
                "field": column,
                "status": status,
                "filled_count": len(filled_values),
                "unique_count": len(unique_values),
            }
        )
    return comparisons


def classify_duplicate_group(rows: pd.DataFrame, comparisons: list[dict[str, Any]]) -> str:
    meaningful = [comparison for comparison in comparisons if comparison["status"] != "all_empty"]
    if not meaningful:
        return "insufficient_information"
    different_fields = [comparison for comparison in meaningful if comparison["status"] == "different"]
    same_fields = [comparison for comparison in meaningful if comparison["status"] == "same"]

    if not different_fields and same_fields:
        return "likely_same_product_duplicate_record"

    high_signal_differences = [
        comparison
        for comparison in different_fields
        if any(hint in comparison["field"] for hint in ("name", "description", "creditor", "supplier", "group", "barcode", "sku"))
    ]
    if high_signal_differences:
        return "likely_distinct_products_sharing_reference"

    if len(different_fields) >= 2:
        return "likely_distinct_products_sharing_reference"

    exact_duplicate_rows = int(rows.duplicated().sum())
    if exact_duplicate_rows:
        return "likely_same_product_duplicate_record"
    return "insufficient_information"


def duplicate_group_audit(df: pd.DataFrame) -> list[dict[str, Any]]:
    refs = reference_series(df)
    non_empty = refs[refs != ""]
    duplicate_values = non_empty.value_counts()
    duplicate_values = duplicate_values[duplicate_values > 1]
    columns = comparable_columns(df)

    groups = []
    for idx, (value, count) in enumerate(duplicate_values.items(), start=1):
        rows = df[refs == value]
        comparisons = field_comparison(rows, columns)
        different_fields = [item["field"] for item in comparisons if item["status"] == "different"]
        same_fields = [item["field"] for item in comparisons if item["status"] == "same"]
        empty_fields = [item["field"] for item in comparisons if item["status"] == "all_empty"]
        groups.append(
            {
                "group_id": f"product_dup_{idx:03d}_{masked_hash(value)}",
                "row_count": int(count),
                "pd_pattern_match": bool(PD_PATTERN.match(value)),
                "classification": classify_duplicate_group(rows, comparisons),
                "exact_duplicate_rows": int(rows.duplicated().sum()),
                "same_fields": same_fields,
                "different_fields": different_fields,
                "empty_fields": empty_fields,
            }
        )
    return groups


def classify_empty_reference(row: pd.Series) -> tuple[str, list[str]]:
    filled_fields = [column for column, value in row.items() if column != "part_nr_sku" and clean_value(value)]
    repair_signals = sorted(set(filled_fields) & ALT_REFERENCE_COLUMNS)
    if not filled_fields:
        return "can_be_excluded", []
    if repair_signals:
        return "repair_candidate", repair_signals
    return "requires_human_review", filled_fields


def empty_reference_audit(df: pd.DataFrame) -> list[dict[str, Any]]:
    refs = reference_series(df)
    empty_rows = df[refs == ""]
    rows = []
    for position, (_, row) in enumerate(empty_rows.iterrows(), start=1):
        classification, evidence_fields = classify_empty_reference(row)
        stable_basis = "|".join(clean_value(value) for value in row.tolist())
        rows.append(
            {
                "row_id": f"product_empty_{position:03d}_{masked_hash(stable_basis)}",
                "classification": classification,
                "filled_context_field_count": len([value for value in row.tolist() if clean_value(value)]),
                "evidence_fields": evidence_fields[:8],
            }
        )
    return rows


def audit_stats(df: pd.DataFrame, duplicates: list[dict[str, Any]], empty_rows: list[dict[str, Any]]) -> dict[str, Any]:
    refs = reference_series(df)
    non_empty = refs[refs != ""]
    pd_matches = non_empty.map(lambda value: bool(PD_PATTERN.match(value)))
    return {
        "total_products": int(len(df)),
        "part_nr_sku_filled": int(len(non_empty)),
        "part_nr_sku_empty": int(len(df) - len(non_empty)),
        "part_nr_sku_pd_pattern_count": int(pd_matches.sum()),
        "part_nr_sku_non_pd_pattern_count": int((~pd_matches).sum()),
        "duplicate_group_count": len(duplicates),
        "duplicate_occurrence_count": int(sum(group["row_count"] - 1 for group in duplicates)),
        "empty_reference_count": len(empty_rows),
    }


def format_fields(fields: list[str]) -> str:
    if not fields:
        return "none"
    return ", ".join(f"`{field}`" for field in fields)


def render_report(stats: dict[str, Any], duplicates: list[dict[str, Any]], empty_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Product Duplicate Audit",
        "",
        "This audit keeps `product_export_product.part_nr_sku` pending human validation. Raw duplicate `part_nr_sku` values are not exposed in this report.",
        "",
        "## Summary",
        "",
        f"- Total products: {stats['total_products']}",
        f"- `part_nr_sku` filled: {stats['part_nr_sku_filled']}",
        f"- `part_nr_sku` empty: {stats['part_nr_sku_empty']}",
        f"- `part_nr_sku` matching `PDYY99999`: {stats['part_nr_sku_pd_pattern_count']}",
        f"- `part_nr_sku` outside PD pattern: {stats['part_nr_sku_non_pd_pattern_count']}",
        f"- Duplicate occurrence count: {stats['duplicate_occurrence_count']}",
        f"- Duplicate group count: {stats['duplicate_group_count']}",
        "",
        "## Duplicate Groups",
        "",
    ]
    if not duplicates:
        lines.append("- No duplicate `part_nr_sku` groups found.")
    else:
        for group in duplicates:
            lines.extend(
                [
                    f"### {group['group_id']}",
                    "",
                    f"- Row count: {group['row_count']}",
                    f"- Matches `PDYY99999`: {group['pd_pattern_match']}",
                    f"- Classification: `{group['classification']}`",
                    f"- Exact duplicate rows: {group['exact_duplicate_rows']}",
                    f"- Same fields: {format_fields(group['same_fields'])}",
                    f"- Different fields: {format_fields(group['different_fields'])}",
                    f"- Empty comparison fields: {format_fields(group['empty_fields'])}",
                    "",
                ]
            )
    lines.extend(["## Empty `part_nr_sku` Rows", ""])
    if not empty_rows:
        lines.append("- No empty `part_nr_sku` rows found.")
    else:
        for row in empty_rows:
            lines.append(
                f"- {row['row_id']}: classification=`{row['classification']}`, filled_context_field_count={row['filled_context_field_count']}, evidence_fields={format_fields(row['evidence_fields'])}"
            )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- Do not approve `product_export_product.part_nr_sku` as final primary key yet.",
            "- Keep Product status as `manually_confirmed_pending_duplicate_validation`.",
            "- Review masked duplicate groups and empty-reference rows with a human data owner before applying approvals.",
            "- Keep `pd_ref_nr` optional and derive it only when `part_nr_sku` matches `PDYY99999`.",
        ]
    )
    return "\n".join(lines)


def run_product_reference_audit(
    data_dir: Path = DATA_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> ProductReferenceAuditResult:
    current_run_id = run_id()
    df = product_dataframe(data_dir)
    duplicates = duplicate_group_audit(df)
    empty_rows = empty_reference_audit(df)
    stats = audit_stats(df, duplicates, empty_rows)

    ensure_dir(output_dir)
    report_path = output_dir / "product_duplicate_audit.md"
    backup_existing(report_path, current_run_id)
    report_path.write_text(render_report(stats, duplicates, empty_rows), encoding="utf-8")

    return ProductReferenceAuditResult(
        output_dir=output_dir,
        report_path=report_path,
        total_products=stats["total_products"],
        duplicate_group_count=stats["duplicate_group_count"],
        duplicate_occurrence_count=stats["duplicate_occurrence_count"],
        empty_reference_count=stats["empty_reference_count"],
        product_status="manually_confirmed_pending_duplicate_validation",
    )
