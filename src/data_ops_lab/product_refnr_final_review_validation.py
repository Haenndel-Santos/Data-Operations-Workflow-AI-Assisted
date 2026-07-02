from __future__ import annotations

import csv
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .product_reference_audit import OUTPUT_DIR, clean_value
from .product_refnr_decision_validation import ALLOWED_DECISIONS, PENDING_DECISION, inconsistency, rows_from_sheet
from .product_refnr_final_review_spreadsheet import XLSX_NAME
from .source_onboarding import backup_existing, ensure_dir


REPORT_NAME = "product_refnr_final_review_validation_report.md"
SUMMARY_NAME = "product_refnr_final_review_validation_summary.csv"
VALIDATED_WORKBOOK_NAME = "product_refnr_human_review_shortlist_validated.xlsx"
FINAL_REVIEW_SHEETS = ["Required Review", "Missing Notes", "Inconsistencies", "All Product Exceptions"]
APPROVED_OR_CONTEXT_DECISIONS = {
    "approved_use_corrected_product_ref_nr",
    "approved_keep_original_part_nr_sku_only",
    "approved_create_technical_product_id_only",
    "merge_duplicate_records",
    "keep_as_separate_products",
    "needs_business_context",
    "rejected",
}


@dataclass(frozen=True)
class ProductRefnrFinalReviewValidationResult:
    output_dir: Path
    report_path: Path
    summary_csv_path: Path
    validated_workbook_path: Path | None
    total_decisions: int
    valid_decisions: int
    empty_decisions: int
    pending_decisions: int
    invalid_decisions: int
    missing_notes: int
    inconsistencies: int
    ready_for_apply: bool


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalized_final_decision(row: dict[str, Any]) -> str:
    return clean_value(row.get("final_human_decision", "")).casefold()


def final_note(row: dict[str, Any]) -> str:
    return clean_value(row.get("final_human_notes", ""))


def issue_key(row: dict[str, Any], sheet_name: str, fallback: int) -> str:
    review_id = clean_value(row.get("review_id", ""))
    if review_id:
        return review_id
    issue_id = clean_value(row.get("issue_id", ""))
    original_sheet = clean_value(row.get("original_sheet", ""))
    original_excel_row = clean_value(row.get("original_excel_row", ""))
    if issue_id or original_sheet or original_excel_row:
        return "|".join([issue_id, original_sheet, original_excel_row])
    return f"{sheet_name}|row_{fallback}"


def merge_review_rows(existing: dict[str, Any], candidate: dict[str, Any], sheet_name: str) -> dict[str, Any]:
    merged = dict(existing)
    source_sheets = set(clean_value(merged.get("_source_sheets", "")).split(";")) if merged.get("_source_sheets") else set()
    source_sheets.add(sheet_name)
    merged["_source_sheets"] = ";".join(sorted(source_sheets))
    for field in ("final_human_decision", "final_human_notes"):
        candidate_value = clean_value(candidate.get(field, ""))
        existing_value = clean_value(merged.get(field, ""))
        if candidate_value and (not existing_value or len(candidate_value) > len(existing_value)):
            merged[field] = candidate_value
    for key, value in candidate.items():
        if key not in merged or clean_value(merged.get(key, "")) == "":
            merged[key] = value
    return merged


def consolidated_rows(workbook) -> list[dict[str, Any]]:
    rows_by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for sheet_name in FINAL_REVIEW_SHEETS:
        for index, row in enumerate(rows_from_sheet(workbook, sheet_name), start=2):
            key = issue_key(row, sheet_name, index)
            row["_source_sheets"] = sheet_name
            if key not in rows_by_key:
                rows_by_key[key] = row
                order.append(key)
            else:
                rows_by_key[key] = merge_review_rows(rows_by_key[key], row, sheet_name)
    return [rows_by_key[key] for key in order]


def row_for_existing_rules(row: dict[str, Any]) -> dict[str, Any]:
    translated = dict(row)
    translated["human_decision"] = normalized_final_decision(row)
    translated["human_notes"] = final_note(row)
    return translated


def missing_final_note(row: dict[str, Any]) -> bool:
    decision = normalized_final_decision(row)
    return decision in APPROVED_OR_CONTEXT_DECISIONS and not final_note(row)


def unresolved_inconsistency(row: dict[str, Any]) -> str:
    direct_problem = inconsistency(row_for_existing_rules(row))
    if direct_problem:
        return direct_problem

    original_problem_type = clean_value(row.get("problem_type", "")).casefold()
    if "inconsistency" not in original_problem_type:
        return ""

    decision = normalized_final_decision(row)
    current_decision = clean_value(row.get("current_human_decision", "")).casefold()
    issue_type = clean_value(row.get("issue_type", ""))
    if (
        issue_type == "duplicate_refnr_review"
        and decision == "approved_use_corrected_product_ref_nr"
        and final_note(row)
    ):
        return ""
    if decision and decision == current_decision:
        return "original_inconsistency_not_changed"
    return ""


def validate_final_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary_by_issue_type: dict[str, Counter[str]] = defaultdict(Counter)
    empty_entries: list[dict[str, str]] = []
    invalid_entries: list[dict[str, str]] = []
    pending_entries: list[dict[str, str]] = []
    missing_note_entries: list[dict[str, str]] = []
    inconsistency_entries: list[dict[str, str]] = []
    valid_decisions = 0

    for index, row in enumerate(rows, start=1):
        issue_type = clean_value(row.get("issue_type", "")) or "unknown"
        issue_id = clean_value(row.get("issue_id", "")) or clean_value(row.get("review_id", "")) or f"row_{index}"
        decision = normalized_final_decision(row)
        counter = summary_by_issue_type[issue_type]
        counter["total_rows"] += 1

        if decision in ALLOWED_DECISIONS:
            valid_decisions += 1
            if decision == PENDING_DECISION:
                counter["pending_count"] += 1
                pending_entries.append({"issue_type": issue_type, "issue_id": issue_id, "decision": decision})
            elif decision == "needs_business_context":
                counter["needs_context_count"] += 1
            elif decision == "rejected":
                counter["rejected_count"] += 1
            else:
                counter["approved_count"] += 1
        elif not decision:
            counter["empty_decision_count"] += 1
            empty_entries.append({"issue_type": issue_type, "issue_id": issue_id, "decision": ""})
        else:
            counter["invalid_decision_count"] += 1
            invalid_entries.append({"issue_type": issue_type, "issue_id": issue_id, "decision": decision})

        if missing_final_note(row):
            counter["missing_notes_count"] += 1
            missing_note_entries.append({"issue_type": issue_type, "issue_id": issue_id, "decision": decision})

        problem = unresolved_inconsistency(row)
        if problem:
            counter["inconsistency_count"] += 1
            inconsistency_entries.append({"issue_type": issue_type, "issue_id": issue_id, "decision": decision, "problem": problem})

    ready_for_apply = not (
        empty_entries or invalid_entries or pending_entries or missing_note_entries or inconsistency_entries
    )
    return {
        "summary_by_issue_type": summary_by_issue_type,
        "empty_entries": empty_entries,
        "invalid_entries": invalid_entries,
        "pending_entries": pending_entries,
        "missing_note_entries": missing_note_entries,
        "inconsistency_entries": inconsistency_entries,
        "total_decisions": len(rows),
        "valid_decisions": valid_decisions,
        "empty_decisions": len(empty_entries),
        "pending_decisions": len(pending_entries),
        "invalid_decisions": len(invalid_entries),
        "missing_notes": len(missing_note_entries),
        "inconsistencies": len(inconsistency_entries),
        "ready_for_apply": ready_for_apply,
    }


def write_summary_csv(path: Path, validation: dict[str, Any], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    columns = [
        "issue_type",
        "total_rows",
        "approved_count",
        "needs_context_count",
        "rejected_count",
        "pending_count",
        "empty_decision_count",
        "invalid_decision_count",
        "missing_notes_count",
        "inconsistency_count",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for issue_type in sorted(validation["summary_by_issue_type"]):
            counts = validation["summary_by_issue_type"][issue_type]
            writer.writerow({column: issue_type if column == "issue_type" else int(counts.get(column, 0)) for column in columns})


def render_entries(title: str, entries: list[dict[str, str]], empty_text: str) -> list[str]:
    lines = ["", f"## {title}", ""]
    if not entries:
        lines.append(f"- {empty_text}")
        return lines
    for entry in entries[:50]:
        detail = f"; problem={entry['problem']}" if "problem" in entry else ""
        lines.append(f"- {entry['issue_type']} / {entry['issue_id']}: decision=`{entry['decision']}`{detail}")
    if len(entries) > 50:
        lines.append(f"- ... {len(entries) - 50} more rows not shown")
    return lines


def render_report(validation: dict[str, Any], validated_workbook_path: Path | None) -> str:
    status = "clean" if validation["ready_for_apply"] else "blocked"
    lines = [
        "# Product RefNr Final Review Validation Report",
        "",
        "This validation reads the manually completed final Product review workbook only. No Product decision is applied.",
        "",
        "## Summary",
        "",
        f"- Validation result: {status}",
        f"- Ready for apply: {str(validation['ready_for_apply']).lower()}",
        f"- Total decisions read: {validation['total_decisions']}",
        f"- Valid decisions: {validation['valid_decisions']}",
        f"- Empty final_human_decision: {validation['empty_decisions']}",
        f"- Pending decisions: {validation['pending_decisions']}",
        f"- Invalid final_human_decision: {validation['invalid_decisions']}",
        f"- Missing final_human_notes: {validation['missing_notes']}",
        f"- Unresolved inconsistencies: {validation['inconsistencies']}",
        f"- Validated workbook: {validated_workbook_path if validated_workbook_path else 'not generated'}",
        "",
        "## Decision Counts By Issue Type",
        "",
    ]
    for issue_type, counts in sorted(validation["summary_by_issue_type"].items()):
        lines.append(
            "- {issue_type}: total={total}, approved={approved}, needs_context={context}, rejected={rejected}, pending={pending}, empty={empty}, invalid={invalid}, missing_notes={missing}, inconsistencies={inconsistencies}".format(
                issue_type=issue_type,
                total=int(counts.get("total_rows", 0)),
                approved=int(counts.get("approved_count", 0)),
                context=int(counts.get("needs_context_count", 0)),
                rejected=int(counts.get("rejected_count", 0)),
                pending=int(counts.get("pending_count", 0)),
                empty=int(counts.get("empty_decision_count", 0)),
                invalid=int(counts.get("invalid_decision_count", 0)),
                missing=int(counts.get("missing_notes_count", 0)),
                inconsistencies=int(counts.get("inconsistency_count", 0)),
            )
        )
    lines.extend(render_entries("Empty Decisions", validation["empty_entries"], "No empty final decisions."))
    lines.extend(render_entries("Invalid Decisions", validation["invalid_entries"], "No invalid final decisions."))
    lines.extend(render_entries("Pending Decisions", validation["pending_entries"], "No pending decisions."))
    lines.extend(render_entries("Missing Final Notes", validation["missing_note_entries"], "No final notes are missing."))
    lines.extend(render_entries("Unresolved Inconsistencies", validation["inconsistency_entries"], "No unresolved inconsistencies detected."))
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- Next step: Step 3E.4 - Apply Product Reconciliation Decisions." if validation["ready_for_apply"] else "- Next step: do not apply final Product decisions yet; resolve the listed blockers first.",
            "- `approved_keys.yml` was not updated.",
            "- `approved_relationships.yml` was not updated.",
            "- Product final key decision was not applied.",
        ]
    )
    return "\n".join(lines)


def run_validate_product_refnr_final_review(
    output_dir: Path = OUTPUT_DIR,
    workbook_path: Path | None = None,
) -> ProductRefnrFinalReviewValidationResult:
    current_run_id = run_id()
    workbook_path = workbook_path or output_dir / XLSX_NAME
    if not workbook_path.exists():
        raise FileNotFoundError(f"Product RefNr final review workbook not found: {workbook_path}")

    workbook = load_workbook(workbook_path, data_only=True)
    rows = consolidated_rows(workbook)
    validation = validate_final_rows(rows)

    ensure_dir(output_dir)
    report_path = output_dir / REPORT_NAME
    summary_csv_path = output_dir / SUMMARY_NAME
    validated_workbook_path = output_dir / VALIDATED_WORKBOOK_NAME if validation["ready_for_apply"] else None
    if validated_workbook_path:
        backup_existing(validated_workbook_path, current_run_id)
        shutil.copy2(workbook_path, validated_workbook_path)
    backup_existing(report_path, current_run_id)
    report_path.write_text(render_report(validation, validated_workbook_path), encoding="utf-8")
    write_summary_csv(summary_csv_path, validation, current_run_id)

    return ProductRefnrFinalReviewValidationResult(
        output_dir=output_dir,
        report_path=report_path,
        summary_csv_path=summary_csv_path,
        validated_workbook_path=validated_workbook_path,
        total_decisions=validation["total_decisions"],
        valid_decisions=validation["valid_decisions"],
        empty_decisions=validation["empty_decisions"],
        pending_decisions=validation["pending_decisions"],
        invalid_decisions=validation["invalid_decisions"],
        missing_notes=validation["missing_notes"],
        inconsistencies=validation["inconsistencies"],
        ready_for_apply=validation["ready_for_apply"],
    )
