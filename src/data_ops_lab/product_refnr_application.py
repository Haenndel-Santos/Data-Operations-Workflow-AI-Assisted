from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from openpyxl import load_workbook

from .product_reference_audit import clean_value
from .product_refnr_final_review_validation import (
    consolidated_rows,
    final_note,
    normalized_final_decision,
    validate_final_rows,
)
from .source_onboarding import backup_existing, ensure_dir


REPORT_NAME = "product_refnr_application_report.md"
PLAN_NAME = "product_refnr_application_plan.csv"
STATE_NAME = "product_reconciliation_state.yml"

DECISION_ACTIONS = {
    "approved_use_corrected_product_ref_nr": "apply_corrected_product_ref_nr",
    "approved_keep_original_part_nr_sku_only": "keep_original_part_nr_sku",
    "approved_create_technical_product_id_only": "create_technical_product_id",
    "merge_duplicate_records": "merge_duplicate_records",
    "keep_as_separate_products": "keep_separate_products",
    "rejected": "exclude_from_target_product_model",
}


@dataclass(frozen=True)
class ProductRefnrApplicationResult:
    output_dir: Path
    report_path: Path
    plan_csv_path: Path
    state_path: Path
    decision_digest: str
    total_decisions: int
    approved_decisions: int
    rejected_decisions: int
    dry_run: bool
    state_changed: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def application_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    output = []
    for index, row in enumerate(rows, start=1):
        decision = normalized_final_decision(row)
        if decision == "needs_business_context":
            issue_id = clean_value(row.get("issue_id", "")) or f"row_{index}"
            raise ValueError(f"Decision {issue_id} still needs business context and cannot be applied.")
        action = DECISION_ACTIONS.get(decision)
        if action is None:
            issue_id = clean_value(row.get("issue_id", "")) or f"row_{index}"
            raise ValueError(f"Decision {issue_id} has no Step 3E.4 application mapping: {decision or '<empty>'}.")
        output.append(
            {
                "review_id": clean_value(row.get("review_id", "")) or f"REVIEW_{index:03d}",
                "issue_id": clean_value(row.get("issue_id", "")) or f"row_{index}",
                "issue_type": clean_value(row.get("issue_type", "")) or "unknown",
                "decision": decision,
                "action": action,
                "source_sheets": clean_value(row.get("_source_sheets", "")),
                "final_human_notes": final_note(row),
            }
        )
    return output


def decision_digest(rows: list[dict[str, str]]) -> str:
    digest_rows = [
        {
            "review_id": row["review_id"],
            "issue_id": row["issue_id"],
            "issue_type": row["issue_type"],
            "decision": row["decision"],
            "action": row["action"],
        }
        for row in rows
    ]
    payload = json.dumps(digest_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_state(workbook_path: Path, rows: list[dict[str, str]], digest: str) -> dict[str, Any]:
    rejected = sum(row["decision"] == "rejected" for row in rows)
    return {
        "version": 1,
        "status": "applied",
        "source": {
            "workbook_sha256": file_sha256(workbook_path),
            "decision_digest": digest,
        },
        "model_contract": {
            "table": "product",
            "primary_key": "product_id",
            "primary_key_strategy": "generated_technical",
            "business_reference": "part_nr_sku",
            "corrected_reference": "product_ref_nr",
            "optional_serial_reference": "pd_ref_nr",
            "rejected_action": "exclude_from_target_product_model",
        },
        "counts": {
            "total": len(rows),
            "approved": len(rows) - rejected,
            "rejected": rejected,
        },
        "decisions": [
            {
                "review_id": row["review_id"],
                "issue_id": row["issue_id"],
                "issue_type": row["issue_type"],
                "decision": row["decision"],
                "action": row["action"],
            }
            for row in rows
        ],
    }


def write_plan(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    columns = [
        "review_id",
        "issue_id",
        "issue_type",
        "decision",
        "action",
        "source_sheets",
        "final_human_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def render_report(
    workbook_path: Path,
    state_path: Path,
    digest: str,
    rows: list[dict[str, str]],
    dry_run: bool,
    state_changed: bool,
) -> str:
    rejected = [row for row in rows if row["decision"] == "rejected"]
    mode = "dry-run" if dry_run else "apply"
    state_result = "not written" if dry_run else ("written" if state_changed else "already current")
    lines = [
        "# Product RefNr Application Report",
        "",
        "## Execution",
        "",
        f"- Mode: `{mode}`",
        f"- Input workbook: `{workbook_path}`",
        f"- Decision digest: `{digest}`",
        f"- Target state: `{state_path}`",
        f"- Target state result: {state_result}",
        "",
        "## Decision Summary",
        "",
        f"- Total decisions: {len(rows)}",
        f"- Approved decisions: {len(rows) - len(rejected)}",
        f"- Rejected decisions: {len(rejected)}",
        f"- Target-model exclusions: {len(rejected)}",
        "",
        "## Rejected Items",
        "",
    ]
    lines.extend(
        f"- `{row['issue_id']}` -> `exclude_from_target_product_model`" for row in rejected
    )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Raw Product sources were read only and were not modified.",
            "- The review workbook was read only and was not modified.",
            "- `approved_keys.yml` and `approved_relationships.yml` were not modified.",
            "- No database, migration, import, synchronization, or external-system operation was performed.",
        ]
    )
    return "\n".join(lines) + "\n"


def read_existing_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    state = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    return state if isinstance(state, dict) else {}


def run_product_refnr_application(
    workbook_path: Path,
    output_dir: Path,
    config_dir: Path = Path("config/data_model"),
    *,
    apply: bool = False,
    replace_existing: bool = False,
) -> ProductRefnrApplicationResult:
    if not workbook_path.exists():
        raise FileNotFoundError(f"Product final review workbook not found: {workbook_path}")
    if replace_existing and not apply:
        raise ValueError("--replace-existing requires --apply.")

    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    rows = consolidated_rows(workbook)
    workbook.close()
    validation = validate_final_rows(rows)
    if not validation["ready_for_apply"]:
        raise ValueError(
            "Product final review is not ready for apply: "
            f"empty={validation['empty_decisions']}, pending={validation['pending_decisions']}, "
            f"invalid={validation['invalid_decisions']}, missing_notes={validation['missing_notes']}, "
            f"inconsistencies={validation['inconsistencies']}."
        )

    plan_rows = application_rows(rows)
    digest = decision_digest(plan_rows)
    state_path = config_dir / STATE_NAME
    state = build_state(workbook_path, plan_rows, digest)
    current_state = read_existing_state(state_path)
    state_changed = False
    current_run_id = run_id()

    if apply:
        if state_path.exists() and current_state != state and not replace_existing:
            raise ValueError(
                f"A different Product reconciliation state already exists at {state_path}. "
                "Review it and use --replace-existing only with explicit authorization."
            )
        if current_state != state:
            ensure_dir(state_path.parent)
            if state_path.exists():
                backup_existing(state_path, current_run_id)
            state_path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=False), encoding="utf-8")
            state_changed = True

    ensure_dir(output_dir)
    plan_path = output_dir / PLAN_NAME
    report_path = output_dir / REPORT_NAME
    backup_existing(plan_path, current_run_id)
    backup_existing(report_path, current_run_id)
    write_plan(plan_path, plan_rows)
    report_path.write_text(
        render_report(workbook_path, state_path, digest, plan_rows, not apply, state_changed),
        encoding="utf-8",
    )

    rejected = sum(row["decision"] == "rejected" for row in plan_rows)
    return ProductRefnrApplicationResult(
        output_dir=output_dir,
        report_path=report_path,
        plan_csv_path=plan_path,
        state_path=state_path,
        decision_digest=digest,
        total_decisions=len(plan_rows),
        approved_decisions=len(plan_rows) - rejected,
        rejected_decisions=rejected,
        dry_run=not apply,
        state_changed=state_changed,
    )
