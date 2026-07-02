from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .source_onboarding import backup_existing, ensure_dir, inspect_sources


STEP3_DIR = Path("outputs/originaldatabase_analysis/step3_modeling")
STEP3C_DIR = Path("outputs/originaldatabase_analysis/step3c_serial_reference_rules")
STEP3D_DIR = Path("outputs/originaldatabase_analysis/step3d_serial_aware_review")
CONFIG_DIR = Path("config/data_model")
DATA_DIR = Path("originaldatabase")
PENDING_REVIEW = "pending_review"
NEEDS_CONTEXT = "needs_business_context"
REJECTED_PROPOSAL = "rejected_proposal"
APPROVE_RECOMMENDED = "approve_recommended"


@dataclass(frozen=True)
class SerialAwareReviewResult:
    output_dir: Path
    config_dir: Path
    key_review_count: int
    relationship_review_count: int
    conflict_count: int
    template_decision_count: int


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def pct(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def int_value(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def load_mapping(config_dir: Path) -> dict[str, dict[str, str]]:
    payload = yaml.safe_load((config_dir / "semantic_ref_mapping.yml").read_text(encoding="utf-8")) or {}
    return payload.get("table_ref_mapping", {})


def table_type(table_name: str) -> str:
    lower = table_name.lower()
    if "line" in lower:
        return "line"
    if any(token in lower for token in ["debtor", "creditor", "product", "organisation"]):
        return "master"
    if any(
        token in lower
        for token in [
            "salesorder",
            "salesquotation",
            "salesinvoice",
            "salesopportunity",
            "deliverynote",
            "purchaseorder",
            "purchasequotation",
            "purchaseinvoice",
            "goodsreception",
            "customerproject",
        ]
    ):
        return "header"
    return "unclear"


def serial_confidence(prefix_match_rate: float, regex_match_rate: float, namespace: str) -> str:
    if namespace in {"", NEEDS_CONTEXT}:
        return NEEDS_CONTEXT
    if prefix_match_rate == 100 and regex_match_rate == 100:
        return "high"
    if prefix_match_rate >= 95 and regex_match_rate >= 95:
        return "medium"
    return NEEDS_CONTEXT


def technical_confidence(non_null_rate: float, uniqueness_rate: float, duplicate_count: int) -> str:
    if non_null_rate == 100 and uniqueness_rate == 100 and duplicate_count == 0:
        return "high"
    if non_null_rate >= 95 and uniqueness_rate >= 98:
        return "medium"
    return NEEDS_CONTEXT


def key_recommendation(row: dict[str, str], validation: dict[str, str], mapping: dict[str, str]) -> tuple[str, str, str]:
    current_table_type = table_type(row["table_name"])
    non_null = pct(row["non_null_rate"])
    unique = pct(row["uniqueness_rate"])
    duplicates = int_value(row["duplicate_count"])
    prefix_match = pct(validation.get("prefix_match_rate"))
    regex_match = pct(validation.get("regex_match_rate"))
    namespace = mapping.get("semantic_namespace", NEEDS_CONTEXT)
    tech_conf = technical_confidence(non_null, unique, duplicates)
    ser_conf = serial_confidence(prefix_match, regex_match, namespace)

    if current_table_type == "line":
        if "row_position" in row["candidate_key"] and tech_conf == "high":
            return "high", "approve_as_technical_key_only", PENDING_REVIEW
        if row["candidate_key"] == "ref_nr":
            return NEEDS_CONTEXT, "use_as_foreign_document_reference_only", NEEDS_CONTEXT
        return tech_conf, "needs_business_context", NEEDS_CONTEXT

    if current_table_type == "header" and row["candidate_key"] == "ref_nr":
        if non_null == 100 and unique == 100 and prefix_match == 100 and regex_match == 100 and namespace != NEEDS_CONTEXT:
            return "high", "approve_as_semantic_primary_key", PENDING_REVIEW
        return NEEDS_CONTEXT, "needs_business_context", NEEDS_CONTEXT

    if current_table_type == "master" and row["candidate_key"] == "ref_nr":
        if prefix_match == 100 and regex_match == 100 and namespace != NEEDS_CONTEXT:
            return "medium", "approve_as_semantic_master_reference_candidate", PENDING_REVIEW
        return NEEDS_CONTEXT, "needs_business_context", NEEDS_CONTEXT

    return NEEDS_CONTEXT, "needs_business_context", NEEDS_CONTEXT


def build_serial_aware_key_review(
    key_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    enrichment_rows: list[dict[str, str]],
    mapping: dict[str, dict[str, str]],
    observations: list[Any],
) -> list[dict[str, Any]]:
    validation_lookup = {row["table_name"]: row for row in validation_rows}
    enrichment_lookup = {(row["table_name"], row["candidate_key"]): row for row in enrichment_rows}
    observations_by_table = {obs.table_name: obs for obs in observations}
    rows: list[dict[str, Any]] = []

    for key in key_rows:
        table = key["table_name"]
        validation = validation_lookup.get(table, {})
        map_row = mapping.get(table, {})
        enrichment = enrichment_lookup.get((table, key["candidate_key"]), {})
        combined, recommendation, status = key_recommendation(key, validation, map_row)
        rows.append(
            {
                "table_name": table,
                "table_type": table_type(table),
                "source_file": key["source_file"],
                "candidate_key": key["candidate_key"],
                "key_type": key["key_type"],
                "non_null_rate": key["non_null_rate"],
                "uniqueness_rate": key["uniqueness_rate"],
                "duplicate_count": key["duplicate_count"],
                "expected_prefix": validation.get("expected_prefix", ""),
                "prefix_match_rate": validation.get("prefix_match_rate", ""),
                "regex_match_rate": validation.get("regex_match_rate", ""),
                "semantic_namespace": map_row.get("semantic_namespace", NEEDS_CONTEXT),
                "semantic_ref_name": map_row.get("semantic_ref_name", "needs_business_context_ref_nr"),
                "serial_validation_status": validation.get("status", NEEDS_CONTEXT),
                "technical_confidence": technical_confidence(pct(key["non_null_rate"]), pct(key["uniqueness_rate"]), int_value(key["duplicate_count"])),
                "serial_confidence": enrichment.get("new_confidence_suggestion")
                or serial_confidence(pct(validation.get("prefix_match_rate")), pct(validation.get("regex_match_rate")), map_row.get("semantic_namespace", NEEDS_CONTEXT)),
                "combined_confidence": combined,
                "recommended_human_decision": recommendation,
                "status": status,
                "notes": "Serial-aware recommendation only. No approval applied.",
            }
        )

    product_obs = [obs for obs in observations if table_type(obs.table_name) == "master" and "product" in obs.table_name.lower()]
    for obs in product_obs:
        existing = {row["candidate_key"] for row in rows if row["table_name"] == obs.table_name}
        for candidate in ["part_nr_sku", "product_code", "sku", "item_code"]:
            if candidate not in obs.df.columns or candidate in existing:
                continue
            values = obs.df[candidate].astype("string").dropna()
            regex_match = round(values.str.match(r"^PD[0-9]{2}[0-9]{5}$").mean() * 100, 2) if len(values) else 0.0
            rows.append(
                {
                    "table_name": obs.table_name,
                    "table_type": "master",
                    "source_file": obs.source_file,
                    "candidate_key": candidate,
                    "key_type": "natural",
                    "non_null_rate": round(len(values) / max(len(obs.df), 1) * 100, 2),
                    "uniqueness_rate": round(values.nunique() / max(len(obs.df), 1) * 100, 2),
                    "duplicate_count": int(len(obs.df) - values.nunique()),
                    "expected_prefix": "PD",
                    "prefix_match_rate": regex_match,
                    "regex_match_rate": regex_match,
                    "semantic_namespace": "product",
                    "semantic_ref_name": "pd_ref_nr",
                    "serial_validation_status": NEEDS_CONTEXT,
                    "technical_confidence": NEEDS_CONTEXT,
                    "serial_confidence": "high" if regex_match == 100 else NEEDS_CONTEXT,
                    "combined_confidence": "high" if regex_match == 100 else NEEDS_CONTEXT,
                    "recommended_human_decision": "approve_as_semantic_master_reference_candidate" if regex_match == 100 else "needs_business_context",
                    "status": PENDING_REVIEW if regex_match == 100 else NEEDS_CONTEXT,
                    "notes": "Product PD rule tested against candidate product code column. No approval applied.",
                }
            )
    return rows


def prefix_consistency(source_table: str, target_table: str, validation_lookup: dict[str, dict[str, str]]) -> str:
    source = validation_lookup.get(source_table, {})
    target = validation_lookup.get(target_table, {})
    if not source or not target:
        return NEEDS_CONTEXT
    source_prefixes = source.get("detected_prefixes", "")
    target_prefix = target.get("expected_prefix", "")
    return "consistent" if target_prefix and target_prefix in source_prefixes else "inconsistent"


def relationship_recommendation(row: dict[str, str], consistency: str) -> tuple[str, str, str]:
    match_rate = pct(row["match_rate"])
    target_duplicates = int_value(row["target_duplicate_count"])
    if (
        row["relationship_type"] == "header_line"
        and match_rate == 100
        and target_duplicates == 0
        and row["join_risk"] == "low"
        and consistency == "consistent"
    ):
        return "high", "approve_header_line_relationship", PENDING_REVIEW
    if row["join_risk"] == "high" or target_duplicates > 0:
        return NEEDS_CONTEXT, "needs_business_context", NEEDS_CONTEXT
    if match_rate < 80:
        return NEEDS_CONTEXT, "do_not_approve_yet", REJECTED_PROPOSAL
    return "medium", "needs_business_context", NEEDS_CONTEXT


def build_serial_aware_relationship_review(
    relationship_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    mapping: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    validation_lookup = {row["table_name"]: row for row in validation_rows}
    rows: list[dict[str, Any]] = []
    for rel in relationship_rows:
        source_map = mapping.get(rel["source_table"], {})
        target_map = mapping.get(rel["target_table"], {})
        consistency = prefix_consistency(rel["source_table"], rel["target_table"], validation_lookup)
        combined, recommendation, status = relationship_recommendation(rel, consistency)
        rows.append(
            {
                "source_table": rel["source_table"],
                "source_column": rel["source_column"],
                "target_table": rel["target_table"],
                "target_column": rel["target_column"],
                "relationship_type": rel["relationship_type"],
                "source_semantic_namespace": source_map.get("semantic_namespace", NEEDS_CONTEXT),
                "target_semantic_namespace": target_map.get("semantic_namespace", NEEDS_CONTEXT),
                "expected_prefix": validation_lookup.get(rel["target_table"], {}).get("expected_prefix", ""),
                "match_rate": rel["match_rate"],
                "unmatched_count": rel["unmatched_count"],
                "target_duplicate_count": rel["target_duplicate_count"],
                "join_risk": rel["join_risk"],
                "prefix_consistency": consistency,
                "combined_confidence": combined,
                "recommended_human_decision": recommendation,
                "status": status,
                "notes": "Serial-aware relationship recommendation only. No approval applied.",
            }
        )
    return rows


def column_overlap(left: set[str], right: set[str]) -> float:
    return round(len(left & right) / max(len(left | right), 1) * 100, 2)


def render_conflict_investigation(
    conflict_tables: list[str],
    observations: list[Any],
    validation_rows: list[dict[str, str]],
) -> str:
    observations_by_table = {obs.table_name: obs for obs in observations}
    validation_lookup = {row["table_name"]: row for row in validation_rows}
    lines = [
        "# Step 3D Conflict Investigation",
        "",
        "No table is renamed or reclassified here. These are technical conflict notes for human review.",
        "",
    ]
    for table in conflict_tables:
        obs = observations_by_table.get(table)
        validation = validation_lookup.get(table, {})
        if not obs:
            continue
        similar = [
            other
            for other in observations
            if other.table_name != table and table.replace("2_", "_").replace("3_", "_").split("_export_")[-1] in other.table_name
        ]
        lines.extend(
            [
                f"## {table}",
                "",
                f"- Source file: {obs.source_file}",
                f"- Columns available: {', '.join(obs.df.columns)}",
                f"- Row count: {len(obs.df)}",
                f"- Ref nr detected prefixes: {validation.get('detected_prefixes', '')}",
                f"- Expected prefix: {validation.get('expected_prefix', '')}",
                f"- Detected prefix: {validation.get('detected_prefixes', '')}",
                "- Possible related tables:",
            ]
        )
        for other in similar[:8]:
            overlap = column_overlap(set(obs.df.columns), set(other.df.columns))
            lines.append(f"  - {other.table_name} ({other.source_file}), column_overlap={overlap}%")
        lines.extend(
            [
                "- Technical hypothesis: observed prefix does not match the current semantic mapping for this table name.",
                "- Risk: high for automatic relationship/key approval.",
                "- Question for human review: should this table be reinterpreted as another document/domain, kept separate, or excluded from approvals?",
                "- recommended_human_decision: needs_business_context",
                "",
            ]
        )
    return "\n".join(lines)


def render_shortlist(key_rows: list[dict[str, Any]], relationship_rows: list[dict[str, Any]], conflict_tables: list[str]) -> str:
    sections = {
        "A. Recommended for approval as semantic primary key": [
            f"- {row['table_name']}.{row['candidate_key']}: non_null={row['non_null_rate']}%, unique={row['uniqueness_rate']}%, prefix={row['prefix_match_rate']}%, regex={row['regex_match_rate']}%; decision pending"
            for row in key_rows
            if row["recommended_human_decision"] == "approve_as_semantic_primary_key"
        ],
        "B. Recommended for approval as header-line relationship": [
            f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']}: match={row['match_rate']}%, risk={row['join_risk']}, prefix={row['prefix_consistency']}; decision pending"
            for row in relationship_rows
            if row["recommended_human_decision"] == "approve_header_line_relationship"
        ],
        "C. Recommended as technical line key only": [
            f"- {row['table_name']}.{row['candidate_key']}: unique={row['uniqueness_rate']}%, duplicates={row['duplicate_count']}; decision pending"
            for row in key_rows
            if row["recommended_human_decision"] == "approve_as_technical_key_only"
        ],
        "D. Needs business context": [
            f"- {row['table_name']}.{row['candidate_key']}: {row['recommended_human_decision']}; decision pending"
            for row in key_rows
            if row["status"] == NEEDS_CONTEXT
        ][:40]
        + [
            f"- {row['source_table']} -> {row['target_table']}: {row['recommended_human_decision']}; decision pending"
            for row in relationship_rows
            if row["status"] == NEEDS_CONTEXT
        ][:40],
        "E. Do not approve yet": [f"- {table}: conflict investigation required; decision pending" for table in conflict_tables],
    }
    lines = ["# Step 3D Human Decision Shortlist", "", "No item is approved in this shortlist.", ""]
    for title, items in sections.items():
        lines.extend([f"## {title}", ""])
        lines.extend(items or ["- None"])
        lines.append("")
    return "\n".join(lines)


def build_template(key_rows: list[dict[str, Any]], relationship_rows: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for row in key_rows:
        if row["recommended_human_decision"] not in {"approve_as_semantic_primary_key", "approve_as_technical_key_only", "approve_as_semantic_master_reference_candidate"}:
            continue
        decisions.append(
            {
                "decision_id": f"KEY_{row['table_name'].upper()}_{row['candidate_key'].upper().replace(' + ', '_').replace(' ', '_')}",
                "decision_type": "technical_key" if row["recommended_human_decision"] == "approve_as_technical_key_only" else "primary_key",
                "table_name": row["table_name"],
                "candidate": row["candidate_key"],
                "semantic_ref_name": row["semantic_ref_name"],
                "semantic_namespace": row["semantic_namespace"],
                "evidence": {
                    "uniqueness_rate": row["uniqueness_rate"],
                    "non_null_rate": row["non_null_rate"],
                    "prefix_match_rate": row["prefix_match_rate"],
                    "regex_match_rate": row["regex_match_rate"],
                },
                "recommended_decision": row["recommended_human_decision"],
                "human_decision": "pending",
                "human_notes": "",
            }
        )
    for row in relationship_rows:
        if row["recommended_human_decision"] != "approve_header_line_relationship":
            continue
        decisions.append(
            {
                "decision_id": f"REL_{row['source_table'].upper()}_{row['target_table'].upper()}",
                "decision_type": "relationship",
                "source_table": row["source_table"],
                "source_column": row["source_column"],
                "target_table": row["target_table"],
                "target_column": row["target_column"],
                "source_semantic_namespace": row["source_semantic_namespace"],
                "target_semantic_namespace": row["target_semantic_namespace"],
                "evidence": {
                    "match_rate": row["match_rate"],
                    "target_duplicate_count": row["target_duplicate_count"],
                    "join_risk": row["join_risk"],
                    "prefix_consistency": row["prefix_consistency"],
                },
                "recommended_decision": row["recommended_human_decision"],
                "human_decision": "pending",
                "human_notes": "",
            }
        )
    return {
        "generated_at": now_iso(),
        "instructions": "Serial-aware recommendations only. Edit human_decision manually; no approval is applied by this file.",
        "decisions": decisions,
    }


def run_serial_aware_review(
    step3_dir: Path = STEP3_DIR,
    step3c_dir: Path = STEP3C_DIR,
    config_dir: Path = CONFIG_DIR,
    output_dir: Path = STEP3D_DIR,
    data_dir: Path = DATA_DIR,
) -> SerialAwareReviewResult:
    current_run_id = run_id()
    key_candidates = read_csv_rows(step3_dir / "key_candidates.csv")
    relationships = read_csv_rows(step3_dir / "relationship_candidates.csv")
    ref_validation = read_csv_rows(step3c_dir / "ref_pattern_validation.csv")
    key_enrichment = read_csv_rows(step3c_dir / "key_candidate_serial_enrichment.csv")
    mapping = load_mapping(config_dir)
    observations = inspect_sources(data_dir)

    key_review = build_serial_aware_key_review(key_candidates, ref_validation, key_enrichment, mapping, observations)
    relationship_review = build_serial_aware_relationship_review(relationships, ref_validation, mapping)
    conflict_tables = [
        "purchaseorderline2_export_purchaseorderline",
        "purchaseorderline3_export_purchaseorderline",
        "salesorderline2_export_salesorderline",
    ]
    conflict_tables = [table for table in conflict_tables if any(row["table_name"] == table for row in ref_validation)]

    key_fields = [
        "table_name",
        "table_type",
        "source_file",
        "candidate_key",
        "key_type",
        "non_null_rate",
        "uniqueness_rate",
        "duplicate_count",
        "expected_prefix",
        "prefix_match_rate",
        "regex_match_rate",
        "semantic_namespace",
        "semantic_ref_name",
        "serial_validation_status",
        "technical_confidence",
        "serial_confidence",
        "combined_confidence",
        "recommended_human_decision",
        "status",
        "notes",
    ]
    relationship_fields = [
        "source_table",
        "source_column",
        "target_table",
        "target_column",
        "relationship_type",
        "source_semantic_namespace",
        "target_semantic_namespace",
        "expected_prefix",
        "match_rate",
        "unmatched_count",
        "target_duplicate_count",
        "join_risk",
        "prefix_consistency",
        "combined_confidence",
        "recommended_human_decision",
        "status",
        "notes",
    ]
    write_csv_rows(output_dir / "serial_aware_key_review.csv", key_review, key_fields, current_run_id)
    write_csv_rows(output_dir / "serial_aware_relationship_review.csv", relationship_review, relationship_fields, current_run_id)
    write_text(output_dir / "conflict_investigation.md", render_conflict_investigation(conflict_tables, observations, ref_validation), current_run_id)
    write_text(output_dir / "human_decision_shortlist.md", render_shortlist(key_review, relationship_review, conflict_tables), current_run_id)
    template = build_template(key_review, relationship_review)
    write_yaml(config_dir / "human_approval_template_serial_aware.yml", template, current_run_id)

    forbidden_statuses = {"approved"}
    if any(row["status"] in forbidden_statuses for row in key_review + relationship_review):
        raise ValueError("Serial-aware review attempted to create an approved status.")

    return SerialAwareReviewResult(
        output_dir=output_dir,
        config_dir=config_dir,
        key_review_count=len(key_review),
        relationship_review_count=len(relationship_review),
        conflict_count=len(conflict_tables),
        template_decision_count=len(template["decisions"]),
    )
