from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .source_onboarding import backup_existing, canonical_name, ensure_dir


STEP3_DIR = Path("outputs/originaldatabase_analysis/step3_modeling")
STEP3B_DIR = Path("outputs/originaldatabase_analysis/step3b_human_review")
DATA_MODEL_DIR = Path("config/data_model")
PENDING = "pending_review"
NEEDS_CONTEXT = "needs_business_context"
REJECTED_PROPOSAL = "rejected_proposal"


@dataclass(frozen=True)
class HumanReviewResult:
    output_dir: Path
    config_dir: Path
    decision_count: int
    source_decision_count: int
    key_decision_count: int
    relationship_decision_count: int


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fields: list[str], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str, current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    path.write_text(text, encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_table_registry(config_dir: Path) -> dict[str, dict[str, Any]]:
    path = config_dir / "table_registry.yml"
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {row["table_name"]: row for row in payload.get("tables", [])}


def pct(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def int_value(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def is_line_table(table_name: str) -> bool:
    return "line" in canonical_name(table_name)


def key_risk(row: dict[str, str]) -> str:
    duplicate_count = int_value(row.get("duplicate_count", "0"))
    non_null = pct(row.get("non_null_rate", "0"))
    uniqueness = pct(row.get("uniqueness_rate", "0"))
    if duplicate_count == 0 and non_null >= 99 and uniqueness >= 99.5:
        return "low"
    if duplicate_count > 0 or non_null < 95 or uniqueness < 98:
        return "high"
    return "medium"


def key_group(row: dict[str, str]) -> str:
    table = row["table_name"]
    candidate = row["candidate_key"]
    risk = key_risk(row)
    if row["key_type"] == "technical" or "row_position" in candidate:
        return "B. Line table technical key candidates"
    if is_line_table(table) and risk != "low":
        return "D. Rejected or unsafe key candidates"
    if row["confidence_level"] == "high" and not is_line_table(table):
        return "A. Strong header primary key candidates"
    if duplicate_count(row) > 0:
        return "E. Candidates requiring duplicate inspection"
    return "C. Master data key candidates needing business context"


def duplicate_count(row: dict[str, str]) -> int:
    return int_value(row.get("duplicate_count", "0"))


def key_recommendation(row: dict[str, str]) -> tuple[str, str, str]:
    risk = key_risk(row)
    if row["key_type"] == "technical" or "row_position" in row["candidate_key"]:
        return "approve_as_technical_key_only", PENDING, risk
    if risk == "low" and row["confidence_level"] == "high":
        return "approve", PENDING, risk
    if risk == "high":
        return "needs_business_context", NEEDS_CONTEXT, risk
    if row["confidence_level"] == "needs_review":
        return "reject_or_request_more_context", REJECTED_PROPOSAL, risk
    return "needs_business_context", NEEDS_CONTEXT, risk


def relationship_group(row: dict[str, str]) -> str:
    if row["join_risk"] == "high":
        return "E. High-risk joins that should not be approved yet"
    if row["relationship_type"] == "header_line" and row["confidence_level"] == "high":
        return "A. Strong header-line relationships"
    if row["relationship_type"] == "header_line":
        return "B. Header-line relationships with risk"
    if row["relationship_type"] == "master_detail":
        return "C. Master-detail relationships"
    if row["relationship_type"] == "document_flow":
        return "D. Document-flow candidates"
    return "E. High-risk joins that should not be approved yet"


def relationship_recommendation(row: dict[str, str]) -> tuple[str, str, str]:
    risk = row["join_risk"] or "needs_review"
    if risk == "low" and row["confidence_level"] == "high":
        return "approve", PENDING, risk
    if risk == "high":
        return "needs_business_context", NEEDS_CONTEXT, risk
    if row["confidence_level"] == "needs_review" or pct(row.get("match_rate", "0")) < 80:
        return "reject_or_request_more_context", REJECTED_PROPOSAL, risk
    return "needs_business_context", NEEDS_CONTEXT, risk


def decision_type_for_key(row: dict[str, str]) -> str:
    if row["key_type"] == "technical" or "row_position" in row["candidate_key"]:
        return "technical_key"
    recommendation, current_status, _ = key_recommendation(row)
    if current_status == REJECTED_PROPOSAL:
        return "rejected_candidate"
    if current_status == NEEDS_CONTEXT:
        return "needs_business_context"
    return "primary_key"


def decision_type_for_relationship(row: dict[str, str]) -> str:
    recommendation, current_status, _ = relationship_recommendation(row)
    if current_status == REJECTED_PROPOSAL:
        return "rejected_candidate"
    if row["relationship_type"] == "document_flow":
        return "document_flow"
    if current_status == NEEDS_CONTEXT:
        return "needs_business_context"
    if row["relationship_type"] == "header_line":
        return "foreign_key"
    return "relationship"


def evidence_for_key(row: dict[str, str]) -> str:
    return (
        f"non_null_rate={row['non_null_rate']}%; uniqueness_rate={row['uniqueness_rate']}%; "
        f"duplicate_count={row['duplicate_count']}; confidence={row['confidence_level']}"
    )


def evidence_for_relationship(row: dict[str, str]) -> str:
    return (
        f"match_rate={row['match_rate']}%; unmatched_count={row['unmatched_count']}; "
        f"target_duplicate_count={row['target_duplicate_count']}; join_risk={row['join_risk']}; "
        f"confidence={row['confidence_level']}"
    )


def table_columns(table_registry: dict[str, dict[str, Any]], table_name: str) -> set[str]:
    return set(table_registry.get(table_name, {}).get("columns", []))


def source_groups(source_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        groups[canonical_name(row["proposed_table_name"])].append(row)
    return {name: rows for name, rows in groups.items() if len(rows) > 1}


def source_recommendation(rows: list[dict[str, str]]) -> str:
    row_counts = {row["row_count"] for row in rows}
    col_counts = {row["column_count"] for row in rows}
    if len(row_counts) == 1 and len(col_counts) == 1:
        return "choose_one_canonical_source"
    return "needs_business_context"


def build_decision_matrix(
    source_rows: list[dict[str, str]],
    key_rows: list[dict[str, str]],
    relationship_rows: list[dict[str, str]],
    table_registry: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    counter = 1

    for group_name, rows in sorted(source_groups(source_rows).items()):
        candidate = " vs ".join(row["proposed_table_name"] for row in rows)
        evidence = "; ".join(f"{row['proposed_table_name']}: rows={row['row_count']}, columns={row['column_count']}" for row in rows)
        status = PENDING if source_recommendation(rows) == "choose_one_canonical_source" else NEEDS_CONTEXT
        decisions.append(
            {
                "decision_id": f"SRC_{counter:03d}",
                "decision_type": "source_canonical",
                "table_name": group_name,
                "source_file": "; ".join(row["file_name"] for row in rows),
                "candidate": candidate,
                "candidate_type": "source_group",
                "evidence_summary": evidence,
                "risk_level": "medium" if status == PENDING else "high",
                "recommended_human_decision": source_recommendation(rows),
                "available_options": "choose_csv; choose_xlsx; choose_enriched_version; keep_multiple; reject_group",
                "current_status": status,
                "human_decision": "pending",
                "human_notes": "",
            }
        )
        counter += 1

    for row in key_rows:
        recommendation, status, risk = key_recommendation(row)
        decisions.append(
            {
                "decision_id": f"KEY_{counter:03d}",
                "decision_type": decision_type_for_key(row),
                "table_name": row["table_name"],
                "source_file": row["source_file"],
                "candidate": row["candidate_key"],
                "candidate_type": row["key_type"],
                "evidence_summary": evidence_for_key(row),
                "risk_level": risk,
                "recommended_human_decision": recommendation,
                "available_options": "approved; rejected; needs_business_context; approved_as_technical_key_only",
                "current_status": status,
                "human_decision": "pending",
                "human_notes": "",
            }
        )
        counter += 1

    for row in relationship_rows:
        recommendation, status, risk = relationship_recommendation(row)
        decisions.append(
            {
                "decision_id": f"REL_{counter:03d}",
                "decision_type": decision_type_for_relationship(row),
                "table_name": row["source_table"],
                "source_file": "",
                "candidate": f"{row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']}",
                "candidate_type": row["relationship_type"],
                "evidence_summary": evidence_for_relationship(row),
                "risk_level": risk,
                "recommended_human_decision": recommendation,
                "available_options": "approved; rejected; needs_business_context",
                "current_status": status,
                "human_decision": "pending",
                "human_notes": "",
            }
        )
        counter += 1

    return decisions


def render_source_canonical_decisions(source_rows: list[dict[str, str]], table_registry: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# Source Canonical Decisions",
        "",
        "All source canonical decisions are pending human review. No source is selected automatically.",
        "",
    ]
    for group_name, rows in sorted(source_groups(source_rows).items()):
        lines.extend([f"## {group_name}", ""])
        for row in rows:
            lines.append(f"- {row['file_name']} / {row['proposed_table_name']}: rows={row['row_count']}, columns={row['column_count']}")
        lines.append("")
        all_columns = {row["proposed_table_name"]: table_columns(table_registry, row["proposed_table_name"]) for row in rows}
        for left in rows:
            for right in rows:
                if left["proposed_table_name"] >= right["proposed_table_name"]:
                    continue
                left_cols = all_columns[left["proposed_table_name"]]
                right_cols = all_columns[right["proposed_table_name"]]
                union = left_cols | right_cols
                overlap = round(len(left_cols & right_cols) / max(len(union), 1) * 100, 2)
                lines.append(f"- Column overlap: {left['proposed_table_name']} vs {right['proposed_table_name']} = {overlap}%")
                lines.append(f"- Exclusive to {left['proposed_table_name']}: {', '.join(sorted(left_cols - right_cols)) or 'None'}")
                lines.append(f"- Exclusive to {right['proposed_table_name']}: {', '.join(sorted(right_cols - left_cols)) or 'None'}")
        lines.extend(
            [
                f"- Technical recommendation: {source_recommendation(rows)}",
                "- Status: pending_review",
                "- Human decision question: Which source should be canonical, or should multiple versions remain separate pending context?",
                "",
            ]
        )
    return "\n".join(lines)


def render_key_approval_candidates(key_rows: list[dict[str, str]]) -> str:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in key_rows:
        groups[key_group(row)].append(row)

    lines = ["# Key Approval Candidates", "", "No key is approved in this file.", ""]
    for group_name in [
        "A. Strong header primary key candidates",
        "B. Line table technical key candidates",
        "C. Master data key candidates needing business context",
        "D. Rejected or unsafe key candidates",
        "E. Candidates requiring duplicate inspection",
    ]:
        lines.extend([f"## {group_name}", ""])
        for row in groups.get(group_name, []):
            recommendation, status, risk = key_recommendation(row)
            lines.append(
                f"- {row['table_name']} | {row['candidate_key']} | non_null={row['non_null_rate']}% | "
                f"unique={row['uniqueness_rate']}% | duplicates={row['duplicate_count']} | "
                f"confidence={row['confidence_level']} | risk={risk} | recommendation={recommendation} | "
                f"status={status} | question=Approve, reject, or request business context?"
            )
        lines.append("")
    return "\n".join(lines)


def render_relationship_approval_candidates(relationship_rows: list[dict[str, str]]) -> str:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in relationship_rows:
        groups[relationship_group(row)].append(row)

    lines = ["# Relationship Approval Candidates", "", "No relationship is approved in this file.", ""]
    for group_name in [
        "A. Strong header-line relationships",
        "B. Header-line relationships with risk",
        "C. Master-detail relationships",
        "D. Document-flow candidates",
        "E. High-risk joins that should not be approved yet",
    ]:
        lines.extend([f"## {group_name}", ""])
        for row in groups.get(group_name, []):
            recommendation, status, risk = relationship_recommendation(row)
            lines.append(
                f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']} | "
                f"match={row['match_rate']}% | unmatched={row['unmatched_count']} | target_duplicates={row['target_duplicate_count']} | "
                f"join_risk={row['join_risk']} | confidence={row['confidence_level']} | risk={risk} | "
                f"recommendation={recommendation} | status={status} | question=Approve, reject, or request business context?"
            )
        lines.append("")
    return "\n".join(lines)


def render_duplicate_investigation_request(key_rows: list[dict[str, str]], relationship_rows: list[dict[str, str]]) -> str:
    lines = [
        "# Duplicate Investigation Request",
        "",
        "These cases need duplicate inspection before approval. No duplicate case is resolved here.",
        "",
        "## Key Candidates With Duplicates",
        "",
    ]
    for row in key_rows:
        duplicates = duplicate_count(row)
        if duplicates <= 0:
            continue
        risk = key_risk(row)
        duplicate_pct = round(100 - pct(row["uniqueness_rate"]), 2)
        lines.append(
            f"- {row['table_name']} | {row['candidate_key']} | duplicate_count={duplicates} | "
            f"duplicate_pct={duplicate_pct}% | risk={risk} | question=Are duplicates valid for this grain? | "
            "next_validation=inspect duplicate keys and confirm business grain"
        )

    lines.extend(["", "## Relationships With Target Duplicates", ""])
    for row in relationship_rows:
        target_duplicates = int_value(row.get("target_duplicate_count", "0"))
        if target_duplicates <= 0:
            continue
        lines.append(
            f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']} | "
            f"target_duplicate_count={target_duplicates} | risk={row['join_risk']} | "
            "question=Can target duplicates create join fanout? | next_validation=confirm target table grain"
        )
    return "\n".join(lines)


def build_human_approval_template(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "instructions": "Edit human_decision manually. This template does not apply approvals by itself.",
        "allowed_human_decisions": ["pending", "approved", "rejected", "needs_business_context", "approved_as_technical_key_only"],
        "decisions": [
            {
                "decision_id": row["decision_id"],
                "decision_type": row["decision_type"],
                "table_name": row["table_name"],
                "candidate": row["candidate"],
                "current_status": row["current_status"],
                "recommended_decision": row["recommended_human_decision"],
                "human_decision": "pending",
                "human_notes": "",
            }
            for row in decisions
        ],
    }


def run_human_review(
    step3_dir: Path = STEP3_DIR,
    output_dir: Path = STEP3B_DIR,
    config_dir: Path = DATA_MODEL_DIR,
) -> HumanReviewResult:
    current_run_id = run_id()
    ensure_dir(output_dir)
    source_rows = read_csv_rows(step3_dir / "source_onboarding_candidates.csv")
    key_rows = read_csv_rows(step3_dir / "key_candidates.csv")
    relationship_rows = read_csv_rows(step3_dir / "relationship_candidates.csv")
    table_registry = load_table_registry(config_dir)

    decisions = build_decision_matrix(source_rows, key_rows, relationship_rows, table_registry)
    fields = [
        "decision_id",
        "decision_type",
        "table_name",
        "source_file",
        "candidate",
        "candidate_type",
        "evidence_summary",
        "risk_level",
        "recommended_human_decision",
        "available_options",
        "current_status",
        "human_decision",
        "human_notes",
    ]
    write_csv_rows(output_dir / "approval_decision_matrix.csv", decisions, fields, current_run_id)
    write_text(output_dir / "source_canonical_decisions.md", render_source_canonical_decisions(source_rows, table_registry), current_run_id)
    write_text(output_dir / "key_approval_candidates.md", render_key_approval_candidates(key_rows), current_run_id)
    write_text(output_dir / "relationship_approval_candidates.md", render_relationship_approval_candidates(relationship_rows), current_run_id)
    write_text(output_dir / "duplicate_investigation_request.md", render_duplicate_investigation_request(key_rows, relationship_rows), current_run_id)
    write_yaml(config_dir / "human_approval_template.yml", build_human_approval_template(decisions), current_run_id)

    return HumanReviewResult(
        output_dir=output_dir,
        config_dir=config_dir,
        decision_count=len(decisions),
        source_decision_count=len(source_groups(source_rows)),
        key_decision_count=len(key_rows),
        relationship_decision_count=len(relationship_rows),
    )


def validate_approval_template(input_path: Path) -> dict[str, int]:
    payload = yaml.safe_load(input_path.read_text(encoding="utf-8")) or {}
    allowed = {"pending", "approved", "rejected", "needs_business_context", "approved_as_technical_key_only"}
    decisions = payload.get("decisions", [])
    invalid = [row for row in decisions if row.get("human_decision") not in allowed]
    if invalid:
        raise ValueError(f"Invalid human_decision values found: {len(invalid)}")
    counts: dict[str, int] = defaultdict(int)
    for row in decisions:
        counts[row.get("human_decision", "missing")] += 1
    return dict(counts)
