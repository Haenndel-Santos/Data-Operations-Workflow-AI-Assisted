from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

from .contracts.hashing import file_sha256
from .io_utils import ensure_dir, normalize_columns, read_table, slugify, table_name_from_path


STEP3_OUTPUT_DIR = Path("outputs/originaldatabase_analysis/step3_modeling")
DATA_MODEL_DIR = Path("config/data_model")
PENDING_REVIEW = "pending_review"
HEADER_LINE_PAIRS = [
    ("SalesOpportunityLine", "SalesOpportunity"),
    ("SalesQuotationLine", "SalesQuotation"),
    ("SalesOrderLine", "SalesOrder"),
    ("DeliveryNoteLine", "DeliveryNote"),
    ("SalesInvoiceLine", "SalesInvoice"),
    ("PurchaseQuotationLine", "PurchaseQuotation"),
    ("PurchaseOrderLine", "PurchaseOrder"),
    ("GoodsReceptionLine", "GoodsReception"),
    ("PurchaseInvoiceLine", "PurchaseInvoice"),
]
DOCUMENT_FLOW_PAIRS = [
    ("SalesOpportunity", "SalesQuotation"),
    ("SalesQuotation", "SalesOrder"),
    ("SalesOrder", "DeliveryNote"),
    ("DeliveryNote", "SalesInvoice"),
    ("SalesOrder", "PurchaseOrder"),
    ("PurchaseOrder", "GoodsReception"),
    ("GoodsReception", "PurchaseInvoice"),
    ("PurchaseOrder", "PurchaseInvoice"),
]
BRIDGE_COLUMN_GROUPS = [
    ("sales_order_ref", "purchase_order_ref"),
    ("sales_order_ref", "delivery_note_ref"),
    ("delivery_note_ref", "invoice_ref"),
    ("purchase_order_ref", "goods_reception_ref"),
    ("purchase_order_ref", "purchase_invoice_ref"),
    ("product_code", "supplier_code"),
    ("customer_ref", "project_ref"),
    ("project_ref", "sales_order_ref"),
]


@dataclass(frozen=True)
class TableObservation:
    source_id: str
    source_file: str
    source_path: str
    sheet_name: str
    table_name: str
    file_hash: str
    file_type: str
    df: pd.DataFrame

    @property
    def row_count(self) -> int:
        return len(self.df)

    @property
    def column_count(self) -> int:
        return len(self.df.columns)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def backup_existing(path: Path, run_id: str) -> None:
    if not path.exists():
        return
    history_dir = ensure_dir(path.parent / "history")
    backup_path = history_dir / f"{path.stem}_{run_id}{path.suffix}"
    shutil.copy2(path, backup_path)


def write_yaml(path: Path, data: Any, run_id: str, preserve_previous: bool = True) -> None:
    ensure_dir(path.parent)
    if preserve_previous:
        backup_existing(path, run_id)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str], run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, run_id)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str, run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, run_id)
    path.write_text(text, encoding="utf-8")


def ensure_review_files(config_dir: Path) -> None:
    ensure_dir(config_dir)
    review_files = {
        "approved_keys.yml": {"approved_keys": []},
        "approved_relationships.yml": {"approved_relationships": []},
        "rejected_candidates.yml": {"rejected_candidates": []},
    }
    for file_name, payload in review_files.items():
        path = config_dir / file_name
        if not path.exists():
            path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def list_source_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".xlsx", ".xls"}
    )


def source_id_for(path: Path, sheet_name: str | None = None) -> str:
    base = slugify(path.stem)
    if sheet_name:
        return slugify(f"{base}_{sheet_name}")
    return base


def inspect_sources(input_dir: Path) -> list[TableObservation]:
    observations: list[TableObservation] = []
    for path in list_source_files(input_dir):
        file_hash = file_sha256(path)
        file_type = path.suffix.lower().lstrip(".")
        if path.suffix.lower() == ".csv":
            df = normalize_columns(read_table(path))
            observations.append(
                TableObservation(
                    source_id=source_id_for(path),
                    source_file=path.name,
                    source_path=str(path),
                    sheet_name="",
                    table_name=table_name_from_path(path),
                    file_hash=file_hash,
                    file_type=file_type,
                    df=df,
                )
            )
            continue

        workbook = pd.ExcelFile(path)
        for sheet_name in workbook.sheet_names:
            df = normalize_columns(read_table(path, sheet_name=sheet_name))
            observations.append(
                TableObservation(
                    source_id=source_id_for(path, sheet_name),
                    source_file=path.name,
                    source_path=str(path),
                    sheet_name=sheet_name,
                    table_name=table_name_from_path(path, sheet_name),
                    file_hash=file_hash,
                    file_type=file_type,
                    df=df,
                )
            )
    return observations


def canonical_name(value: str) -> str:
    text = slugify(value)
    if "_export_" in text:
        text = text.split("_export_")[-1]
    elif text.startswith("export_"):
        text = text.removeprefix("export_")
    text = text.replace("_3", "")
    return text


def classify_source(obs: TableObservation, known_sources: dict[str, dict[str, Any]], observations: list[TableObservation]) -> tuple[str, str, str, float]:
    previous = known_sources.get(source_id_for(Path(obs.source_file)))
    status = "new"
    if previous and previous.get("file_hash") == obs.file_hash:
        status = "known"
    elif previous:
        status = "modified"

    best_match = ""
    best_overlap = 0.0
    columns = set(obs.df.columns)
    for other in observations:
        if other.source_id == obs.source_id:
            continue
        other_columns = set(other.df.columns)
        union = len(columns | other_columns)
        overlap = len(columns & other_columns) / union if union else 0.0
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = other.table_name

    same_canonical = [
        other
        for other in observations
        if other.source_id != obs.source_id and canonical_name(other.table_name) == canonical_name(obs.table_name)
    ]
    if status == "known":
        classification = "duplicate_or_already_loaded"
    elif same_canonical and best_overlap >= 0.85:
        classification = "replacement_candidate"
    elif "line" in canonical_name(obs.table_name) and len(find_bridge_columns(obs.df.columns)) >= 2:
        classification = "bridge_table_candidate"
    elif best_overlap >= 0.6:
        classification = "enrichment_table"
    elif obs.row_count > 0 and obs.column_count > 0:
        classification = "new_table"
    else:
        classification = "unclear"

    return status, classification, best_match, round(best_overlap * 100, 2)


def confidence_from_rates(non_null_rate: float, uniqueness_rate: float, duplicate_count: int) -> str:
    if non_null_rate >= 0.99 and uniqueness_rate >= 0.995 and duplicate_count == 0:
        return "high"
    if non_null_rate >= 0.95 and uniqueness_rate >= 0.98:
        return "medium"
    if non_null_rate >= 0.8 and uniqueness_rate >= 0.8:
        return "low"
    return "needs_review"


def key_stats(df: pd.DataFrame, columns: list[str]) -> tuple[float, float, int]:
    if not columns or df.empty:
        return 0.0, 0.0, 0
    con = duckdb.connect()
    con.register("candidate_table", df)
    quoted = [f'"{column}"' for column in columns]
    not_null_predicate = " and ".join(f"{column} is not null" for column in quoted)
    concat_expr = " || '|' || ".join(f"coalesce(cast({column} as varchar), '')" for column in quoted)
    row_count, non_null_count, unique_count = con.execute(
        f"""
        select
          count(*) as row_count,
          count(*) filter (where {not_null_predicate}) as non_null_count,
          count(distinct {concat_expr}) as unique_count
        from candidate_table
        """
    ).fetchone()
    duplicate_count = int(row_count - unique_count)
    return (
        round(float(non_null_count / row_count * 100), 2) if row_count else 0.0,
        round(float(unique_count / row_count * 100), 2) if row_count else 0.0,
        duplicate_count,
    )


def natural_key_columns(df: pd.DataFrame, is_line_table: bool) -> list[list[str]]:
    columns = list(df.columns)
    column_set = set(columns)
    preferred_tokens = ("ref_nr", "id", "number", "code", "document_no", "order_no", "debtor_no", "creditor_no", "product_code", "sku", "name")
    candidates = [[column] for column in columns if any(token in column for token in preferred_tokens)]

    if is_line_table:
        candidates = [candidate for candidate in candidates if candidate != ["ref_nr"]]
        line_patterns = [
            ["ref_nr", "line_nr"],
            ["ref_nr", "product_code"],
            ["ref_nr", "part_nr_sku"],
            ["ref_nr", "suppl_part_nr_sku"],
            ["ref_nr", "comm_description", "tot"],
            ["ref_nr", "product_description", "tot"],
            ["ref_nr", "part_nr_sku", "tot"],
            ["ref_nr", "suppl_part_nr_sku", "tot"],
            ["ref_nr", "part_nr_sku", "tot", "tot_sal_ex_vat"],
            ["ref_nr", "suppl_part_nr_sku", "tot", "tot_pur_excl_vat"],
        ]
        for pattern in line_patterns:
            if all(column in column_set for column in pattern):
                candidates.insert(0, pattern)
        if "ref_nr" in column_set:
            df["row_position"] = range(1, len(df) + 1)
            candidates.append(["ref_nr", "row_position"])

    deduped: list[list[str]] = []
    seen = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key not in seen and all(column in df.columns for column in candidate):
            seen.add(key)
            deduped.append(candidate)
    return deduped[:25]


def detect_key_candidates(observations: list[TableObservation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obs in observations:
        df = obs.df.copy()
        is_line_table = "line" in canonical_name(obs.table_name)
        candidates = natural_key_columns(df, is_line_table)
        strong_candidate_found = False

        for columns in candidates:
            non_null_rate, uniqueness_rate, duplicate_count = key_stats(df, columns)
            confidence = confidence_from_rates(non_null_rate, uniqueness_rate, duplicate_count)
            if confidence in {"high", "medium"}:
                strong_candidate_found = True
            rows.append(
                {
                    "table_name": obs.table_name,
                    "source_file": obs.source_file,
                    "candidate_key": " + ".join(columns),
                    "key_type": "composite" if len(columns) > 1 else "natural",
                    "non_null_rate": non_null_rate,
                    "uniqueness_rate": uniqueness_rate,
                    "duplicate_count": duplicate_count,
                    "confidence_level": confidence,
                    "reason": "Measured non-null, uniqueness, and duplicate rates. Line tables exclude ref_nr alone.",
                    "status": PENDING_REVIEW,
                }
            )

        if is_line_table and not strong_candidate_found:
            rows.append(
                {
                    "table_name": obs.table_name,
                    "source_file": obs.source_file,
                    "candidate_key": "technical_row_id = hash(source_file + sheet_name + row_position)",
                    "key_type": "technical",
                    "non_null_rate": 100.0 if obs.row_count else 0.0,
                    "uniqueness_rate": 100.0 if obs.row_count else 0.0,
                    "duplicate_count": 0,
                    "confidence_level": "needs_review",
                    "reason": "No reliable natural/composite key reached medium confidence for this line table.",
                    "status": PENDING_REVIEW,
                }
            )
    return rows


def likely_reference_columns(df: pd.DataFrame) -> list[str]:
    tokens = ("ref", "id", "code", "number", "no", "nr", "project")
    return [column for column in df.columns if any(token in column for token in tokens)]


def relationship_stats(source: pd.DataFrame, source_column: str, target: pd.DataFrame, target_column: str) -> tuple[float, int, int]:
    if source.empty or target.empty:
        return 0.0, 0, 0
    left = source[[source_column]].dropna().drop_duplicates()
    right = target[[target_column]].dropna()
    matched = left.merge(right.drop_duplicates(), left_on=source_column, right_on=target_column, how="left", indicator=True)
    matched_count = int((matched["_merge"] == "both").sum())
    unmatched_count = int((matched["_merge"] == "left_only").sum())
    target_duplicate_count = int(right.duplicated().sum())
    match_rate = round(matched_count / max(len(left), 1) * 100, 2)
    return match_rate, unmatched_count, target_duplicate_count


def join_risk(match_rate: float, target_duplicate_count: int) -> str:
    if target_duplicate_count > 0:
        return "high"
    if match_rate < 90:
        return "medium"
    return "low"


def relationship_confidence(match_rate: float, target_duplicate_count: int, relationship_type: str) -> str:
    if match_rate >= 99 and target_duplicate_count == 0 and relationship_type == "header_line":
        return "high"
    if match_rate >= 95 and target_duplicate_count == 0:
        return "medium"
    if match_rate >= 80:
        return "low"
    return "needs_review"


def find_table_by_canonical(observations: list[TableObservation], name: str) -> list[TableObservation]:
    target = slugify(name)
    return [obs for obs in observations if canonical_name(obs.table_name) == target]


def add_relationship_candidate(rows: list[dict[str, Any]], source: TableObservation, source_column: str, target: TableObservation, target_column: str, relationship_type: str, reason: str) -> None:
    match_rate, unmatched_count, target_duplicate_count = relationship_stats(source.df, source_column, target.df, target_column)
    rows.append(
        {
            "source_table": source.table_name,
            "source_column": source_column,
            "target_table": target.table_name,
            "target_column": target_column,
            "relationship_type": relationship_type,
            "match_rate": match_rate,
            "unmatched_count": unmatched_count,
            "target_duplicate_count": target_duplicate_count,
            "join_risk": join_risk(match_rate, target_duplicate_count),
            "confidence_level": relationship_confidence(match_rate, target_duplicate_count, relationship_type),
            "reason": reason,
            "status": PENDING_REVIEW,
            "notes": "Candidate only. Requires manual approval before use.",
        }
    )


def detect_relationship_candidates(observations: list[TableObservation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()

    for line_name, header_name in HEADER_LINE_PAIRS:
        for line in find_table_by_canonical(observations, line_name):
            for header in find_table_by_canonical(observations, header_name):
                if "ref_nr" in line.df.columns and "ref_nr" in header.df.columns:
                    key = (line.table_name, "ref_nr", header.table_name, "ref_nr", "header_line")
                    if key not in seen:
                        seen.add(key)
                        add_relationship_candidate(rows, line, "ref_nr", header, "ref_nr", "header_line", "Required Step 3 header-line relationship test.")

    for source_name, target_name in DOCUMENT_FLOW_PAIRS:
        for source in find_table_by_canonical(observations, source_name):
            for target in find_table_by_canonical(observations, target_name):
                for source_col in likely_reference_columns(source.df):
                    for target_col in likely_reference_columns(target.df):
                        if source_col == target_col:
                            continue
                        sample_key = (source.table_name, source_col, target.table_name, target_col, "document_flow")
                        if sample_key in seen:
                            continue
                        match_rate, unmatched_count, target_duplicate_count = relationship_stats(source.df, source_col, target.df, target_col)
                        if match_rate >= 50:
                            seen.add(sample_key)
                            rows.append(
                                {
                                    "source_table": source.table_name,
                                    "source_column": source_col,
                                    "target_table": target.table_name,
                                    "target_column": target_col,
                                    "relationship_type": "document_flow",
                                    "match_rate": match_rate,
                                    "unmatched_count": unmatched_count,
                                    "target_duplicate_count": target_duplicate_count,
                                    "join_risk": join_risk(match_rate, target_duplicate_count),
                                    "confidence_level": relationship_confidence(match_rate, target_duplicate_count, "document_flow"),
                                    "reason": "Document-flow candidate met minimum measured match-rate threshold.",
                                    "status": PENDING_REVIEW,
                                    "notes": "Candidate only. Requires manual approval before use.",
                                }
                            )

    for obs in observations:
        bridge_cols = find_bridge_columns(obs.df.columns)
        for left, right in combinations(bridge_cols, 2):
            rows.append(
                {
                    "source_table": obs.table_name,
                    "source_column": left,
                    "target_table": obs.table_name,
                    "target_column": right,
                    "relationship_type": "bridge_table_candidate",
                    "match_rate": "",
                    "unmatched_count": "",
                    "target_duplicate_count": "",
                    "join_risk": "needs_review",
                    "confidence_level": "needs_review",
                    "reason": "Table contains multiple bridge-like reference columns.",
                    "status": PENDING_REVIEW,
                    "notes": "Bridge role requires human review of business meaning.",
                }
            )

    return rows


def find_bridge_columns(columns: Any) -> list[str]:
    normalized = set(columns)
    found: list[str] = []
    for group in BRIDGE_COLUMN_GROUPS:
        for column in group:
            if column in normalized and column not in found:
                found.append(column)
    return found


def build_manifest(observations: list[TableObservation], config_dir: Path, run_id: str) -> list[dict[str, Any]]:
    previous_payload = read_yaml(config_dir / "source_manifest.yml") or {}
    previous_sources = {item.get("source_id"): item for item in previous_payload.get("sources", [])}
    timestamp = now_iso()
    observations_by_file: dict[str, list[TableObservation]] = {}
    for obs in observations:
        observations_by_file.setdefault(obs.source_file, []).append(obs)

    manifest: list[dict[str, Any]] = []
    for file_name, file_observations in sorted(observations_by_file.items()):
        first = file_observations[0]
        previous = previous_sources.get(source_id_for(Path(file_name)))
        if previous and previous.get("file_hash") == first.file_hash:
            status = "known"
        elif previous:
            status = "modified"
        else:
            status = "new"
        detected_sheets = [
            {
                "sheet_name": obs.sheet_name,
                "proposed_table_name": obs.table_name,
                "row_count": obs.row_count,
                "column_count": obs.column_count,
                "columns": list(obs.df.columns),
            }
            for obs in file_observations
        ]
        manifest.append(
            {
                "source_id": source_id_for(Path(file_name)),
                "file_name": file_name,
                "file_path": first.source_path,
                "file_type": first.file_type,
                "file_hash": first.file_hash,
                "detected_sheets": detected_sheets,
                "row_count": sum(obs.row_count for obs in file_observations),
                "column_count": max((obs.column_count for obs in file_observations), default=0),
                "first_detected_at": previous.get("first_detected_at") if previous else timestamp,
                "last_checked_at": timestamp,
                "status": status,
                "classification": "pending_sheet_review",
                "notes": "Source observed by Step 3 onboarding. No approval implied.",
            }
        )
    return manifest


def source_candidate_rows(observations: list[TableObservation], config_dir: Path) -> list[dict[str, Any]]:
    previous_payload = read_yaml(config_dir / "source_manifest.yml") or {}
    previous_sources = {item.get("source_id"): item for item in previous_payload.get("sources", [])}
    rows = []
    for obs in observations:
        status, classification, best_match, overlap = classify_source(obs, previous_sources, observations)
        key_candidates = detect_key_candidates([obs])
        rel_candidates = [row for row in detect_relationship_candidates(observations) if row["source_table"] == obs.table_name]
        rows.append(
            {
                "file_name": obs.source_file,
                "sheet_name": obs.sheet_name,
                "proposed_table_name": obs.table_name,
                "classification": classification,
                "matching_existing_table": best_match,
                "column_overlap_pct": overlap,
                "row_count": obs.row_count,
                "column_count": obs.column_count,
                "possible_primary_keys": "; ".join(row["candidate_key"] for row in key_candidates[:5]),
                "possible_foreign_keys": "; ".join(f"{row['source_column']}->{row['target_table']}.{row['target_column']}" for row in rel_candidates[:5]),
                "possible_bridge_columns": "; ".join(find_bridge_columns(obs.df.columns)),
                "confidence_level": "needs_review" if classification in {"unclear", "bridge_table_candidate"} else "medium",
                "recommended_action": "manual_review",
                "status": PENDING_REVIEW,
                "notes": f"Source status: {status}. Candidate only; no approval implied.",
            }
        )
    return rows


def write_table_registry(observations: list[TableObservation], config_dir: Path, run_id: str) -> None:
    payload = {
        "generated_at": now_iso(),
        "status": PENDING_REVIEW,
        "tables": [
            {
                "table_name": obs.table_name,
                "source_file": obs.source_file,
                "sheet_name": obs.sheet_name,
                "row_count": obs.row_count,
                "column_count": obs.column_count,
                "columns": list(obs.df.columns),
                "status": PENDING_REVIEW,
            }
            for obs in observations
        ],
    }
    write_yaml(config_dir / "table_registry.yml", payload, run_id)


def rows_to_yaml_payload(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"generated_at": now_iso(), "status": PENDING_REVIEW, name: rows}


def render_source_onboarding_report(source_rows: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> str:
    new_files = [row for row in manifest if row["status"] == "new"]
    known_files = [row for row in manifest if row["status"] == "known"]
    modified_files = [row for row in manifest if row["status"] == "modified"]
    duplicate_like = [row for row in source_rows if row["classification"] in {"replacement_candidate", "duplicate_or_already_loaded"}]
    lines = [
        "# Step 3 Source Onboarding Report",
        "",
        "All suggestions are pending human review. No source, key, or relationship is approved by this report.",
        "",
        f"- Files checked: {len(manifest)}",
        f"- New files: {len(new_files)}",
        f"- Known files: {len(known_files)}",
        f"- Possibly changed files: {len(modified_files)}",
        f"- Duplicate/replacement-like sheets: {len(duplicate_like)}",
        "",
        "## New Files",
        *[f"- {row['file_name']} ({row['file_type']}, rows={row['row_count']}, columns={row['column_count']})" for row in new_files],
        "",
        "## Known Files",
        *[f"- {row['file_name']}" for row in known_files],
        "",
        "## Possibly Changed Files",
        *[f"- {row['file_name']} ({row['status']})" for row in modified_files],
        "",
        "## Proposed Tables",
    ]
    for row in source_rows:
        lines.append(f"- {row['proposed_table_name']}: {row['classification']}, rows={row['row_count']}, columns={row['column_count']}, status={row['status']}")
    lines.extend(
        [
            "",
            "## Risks Identified",
            "- CSV/XLSX pairs can represent duplicate exports or replacement candidates; approval is required before choosing a canonical source.",
            "- Line tables require composite or technical keys; `ref_nr` alone is not treated as a primary key.",
            "- Tables without strong natural keys need manual grain confirmation before modeling.",
            "",
            "## Questions For Human Review",
            "- Which source should be canonical when CSV and XLSX versions both exist?",
            "- Which document references are approved business keys?",
            "- Should line tables use natural composite keys or technical row identifiers?",
        ]
    )
    return "\n".join(lines)


def render_relationship_impact_report(relationship_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> str:
    high_risk = [row for row in relationship_rows if row["join_risk"] == "high"]
    bridge = [row for row in relationship_rows if row["relationship_type"] == "bridge_table_candidate"]
    high_conf = [row for row in relationship_rows if row["confidence_level"] == "high"]
    lines = [
        "# Step 3 Relationship Impact Report",
        "",
        "This report lists measured relationship candidates only. No relationship is final until manually approved.",
        "",
        f"- Relationship candidates: {len(relationship_rows)}",
        f"- High-confidence candidates: {len(high_conf)}",
        f"- Bridge-table candidates: {len(bridge)}",
        f"- High join-risk candidates: {len(high_risk)}",
        "",
        "## Candidate Relationships To Test",
    ]
    for row in relationship_rows[:80]:
        lines.append(
            f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']} "
            f"({row['relationship_type']}, match_rate={row['match_rate']}, risk={row['join_risk']}, status={row['status']})"
        )
    lines.extend(["", "## Tables That May Be Duplicates Or Substitutes"])
    for row in source_rows:
        if row["classification"] in {"replacement_candidate", "duplicate_or_already_loaded"}:
            lines.append(f"- {row['proposed_table_name']} may match {row['matching_existing_table']} ({row['column_overlap_pct']}% column overlap).")
    lines.extend(["", "## Decisions Requiring Approval", "- Approve/reject each header-line relationship.", "- Confirm whether any document-flow relationship reflects the real business process.", "- Confirm whether bridge-table candidates should become modeled relationships."])
    return "\n".join(lines)


def render_manual_review_pack(source_rows: list[dict[str, Any]], key_rows: list[dict[str, Any]], relationship_rows: list[dict[str, Any]]) -> str:
    best_keys = sorted(key_rows, key=lambda row: (row["confidence_level"] != "high", -float(row["uniqueness_rate"] or 0)))[:30]
    best_relationships = sorted(relationship_rows, key=lambda row: (row["confidence_level"] != "high", -(float(row["match_rate"]) if row["match_rate"] != "" else 0)))[:30]
    low_relationships = [row for row in relationship_rows if row["confidence_level"] in {"low", "needs_review"}][:30]
    lines = [
        "# Step 3 Manual Review Pack",
        "",
        "This pack is for human review. Every candidate has status `pending_review`.",
        "",
        "## Sources Analyzed",
        *[f"- {row['proposed_table_name']} ({row['file_name']}, classification={row['classification']})" for row in source_rows],
        "",
        "## Best Primary Key Candidates",
        *[f"- {row['table_name']}: {row['candidate_key']} ({row['key_type']}, uniqueness={row['uniqueness_rate']}%, status={row['status']})" for row in best_keys],
        "",
        "## Best Relationship Candidates",
        *[
            f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']} "
            f"({row['relationship_type']}, match={row['match_rate']}%, risk={row['join_risk']}, status={row['status']})"
            for row in best_relationships
        ],
        "",
        "## Medium/Low Confidence Or Do-Not-Use-Yet Relationships",
        *[
            f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']} "
            f"({row['confidence_level']}, match={row['match_rate']}, status={row['status']})"
            for row in low_relationships
        ],
        "",
        "## Questions For Manual Approval",
        "- Which source exports should be canonical where CSV and XLSX versions overlap?",
        "- Are exact duplicate line rows valid repeated business lines or export duplication?",
        "- Which composite keys should be approved for line tables?",
        "- Should unmatched invoice-line rows be excluded, mapped to another header source, or investigated upstream?",
        "- Which document-flow links should be modeled now versus kept pending?",
    ]
    return "\n".join(lines)


def render_data_model_v0(key_rows: list[dict[str, Any]], relationship_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Data Model v0",
        "",
        "This is a preliminary model. No key or relationship is final until manually approved.",
        "",
        "## Pending Key Candidates",
    ]
    for row in key_rows[:80]:
        lines.append(f"- {row['table_name']}: {row['candidate_key']} ({row['key_type']}, confidence={row['confidence_level']}, status={row['status']})")
    lines.extend(["", "## Pending Relationship Candidates"])
    for row in relationship_rows[:80]:
        lines.append(
            f"- {row['source_table']}.{row['source_column']} -> {row['target_table']}.{row['target_column']} "
            f"({row['relationship_type']}, confidence={row['confidence_level']}, status={row['status']})"
        )
    return "\n".join(lines)


def append_validation_notes(config_dir: Path, run_id: str, source_count: int, key_count: int, relationship_count: int) -> None:
    path = config_dir / "validation_notes.md"
    ensure_dir(path.parent)
    if not path.exists():
        path.write_text("# Validation Notes\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"## Run {run_id}\n\n"
            f"- Sources inspected: {source_count}\n"
            f"- Key candidates generated: {key_count}\n"
            f"- Relationship candidates generated: {relationship_count}\n"
            "- All generated candidates are pending_review.\n"
            "- Approved key and relationship files were not modified by the onboarding command.\n\n"
        )


def run_source_onboarding(input_dir: Path, output_dir: Path = STEP3_OUTPUT_DIR, config_dir: Path = DATA_MODEL_DIR) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ensure_review_files(config_dir)
    ensure_dir(output_dir)

    observations = inspect_sources(input_dir)
    manifest = build_manifest(observations, config_dir, run_id)
    source_rows = source_candidate_rows(observations, config_dir)
    key_rows = detect_key_candidates(observations)
    relationship_rows = detect_relationship_candidates(observations)

    write_yaml(config_dir / "source_manifest.yml", {"generated_at": now_iso(), "sources": manifest}, run_id)
    write_table_registry(observations, config_dir, run_id)
    write_yaml(config_dir / "key_candidates.yml", rows_to_yaml_payload("key_candidates", key_rows), run_id)
    write_yaml(config_dir / "relationship_candidates.yml", rows_to_yaml_payload("relationship_candidates", relationship_rows), run_id)
    append_validation_notes(config_dir, run_id, len(observations), len(key_rows), len(relationship_rows))

    source_fields = [
        "file_name",
        "sheet_name",
        "proposed_table_name",
        "classification",
        "matching_existing_table",
        "column_overlap_pct",
        "row_count",
        "column_count",
        "possible_primary_keys",
        "possible_foreign_keys",
        "possible_bridge_columns",
        "confidence_level",
        "recommended_action",
        "status",
        "notes",
    ]
    key_fields = [
        "table_name",
        "source_file",
        "candidate_key",
        "key_type",
        "non_null_rate",
        "uniqueness_rate",
        "duplicate_count",
        "confidence_level",
        "reason",
        "status",
    ]
    relationship_fields = [
        "source_table",
        "source_column",
        "target_table",
        "target_column",
        "relationship_type",
        "match_rate",
        "unmatched_count",
        "target_duplicate_count",
        "join_risk",
        "confidence_level",
        "reason",
        "status",
        "notes",
    ]
    write_csv(output_dir / "source_onboarding_candidates.csv", source_rows, source_fields, run_id)
    write_csv(output_dir / "key_candidates.csv", key_rows, key_fields, run_id)
    write_csv(output_dir / "relationship_candidates.csv", relationship_rows, relationship_fields, run_id)
    write_text(output_dir / "source_onboarding_report.md", render_source_onboarding_report(source_rows, manifest), run_id)
    write_text(output_dir / "relationship_impact_report.md", render_relationship_impact_report(relationship_rows, source_rows), run_id)
    write_text(output_dir / "manual_review_pack.md", render_manual_review_pack(source_rows, key_rows, relationship_rows), run_id)
    write_text(output_dir / "data_model_v0.md", render_data_model_v0(key_rows, relationship_rows), run_id)

    return {
        "run_id": run_id,
        "source_count": len(observations),
        "key_candidate_count": len(key_rows),
        "relationship_candidate_count": len(relationship_rows),
        "output_dir": output_dir,
        "config_dir": config_dir,
    }
