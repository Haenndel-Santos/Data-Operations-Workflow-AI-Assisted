from __future__ import annotations

import csv
from pathlib import Path

import yaml

from data_ops_lab.human_review import run_human_review, validate_approval_template


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def seed_step3(step3_dir: Path, config_dir: Path) -> None:
    write_csv(
        step3_dir / "source_onboarding_candidates.csv",
        [
            {
                "file_name": "SalesOrderLine.csv",
                "sheet_name": "",
                "proposed_table_name": "salesorderline",
                "classification": "replacement_candidate",
                "matching_existing_table": "salesorderline_export_salesorderline",
                "column_overlap_pct": "100.0",
                "row_count": "2",
                "column_count": "3",
                "possible_primary_keys": "ref_nr + row_position",
                "possible_foreign_keys": "ref_nr->salesorder.ref_nr",
                "possible_bridge_columns": "",
                "confidence_level": "medium",
                "recommended_action": "manual_review",
                "status": "pending_review",
                "notes": "candidate only",
            },
            {
                "file_name": "SalesOrderLine.xlsx",
                "sheet_name": "Export_SalesOrderLine",
                "proposed_table_name": "salesorderline_export_salesorderline",
                "classification": "replacement_candidate",
                "matching_existing_table": "salesorderline",
                "column_overlap_pct": "100.0",
                "row_count": "2",
                "column_count": "3",
                "possible_primary_keys": "ref_nr + row_position",
                "possible_foreign_keys": "ref_nr->salesorder.ref_nr",
                "possible_bridge_columns": "",
                "confidence_level": "medium",
                "recommended_action": "manual_review",
                "status": "pending_review",
                "notes": "candidate only",
            },
        ],
    )
    write_csv(
        step3_dir / "key_candidates.csv",
        [
            {
                "table_name": "salesorder",
                "source_file": "SalesOrder.csv",
                "candidate_key": "ref_nr",
                "key_type": "natural",
                "non_null_rate": "100.0",
                "uniqueness_rate": "100.0",
                "duplicate_count": "0",
                "confidence_level": "high",
                "reason": "measured",
                "status": "pending_review",
            },
            {
                "table_name": "salesorderline",
                "source_file": "SalesOrderLine.csv",
                "candidate_key": "ref_nr + row_position",
                "key_type": "composite",
                "non_null_rate": "100.0",
                "uniqueness_rate": "100.0",
                "duplicate_count": "0",
                "confidence_level": "high",
                "reason": "measured",
                "status": "pending_review",
            },
        ],
    )
    write_csv(
        step3_dir / "relationship_candidates.csv",
        [
            {
                "source_table": "salesorderline",
                "source_column": "ref_nr",
                "target_table": "salesorder",
                "target_column": "ref_nr",
                "relationship_type": "header_line",
                "match_rate": "100.0",
                "unmatched_count": "0",
                "target_duplicate_count": "0",
                "join_risk": "low",
                "confidence_level": "high",
                "reason": "measured",
                "status": "pending_review",
                "notes": "candidate only",
            }
        ],
    )
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "table_registry.yml").write_text(
        yaml.safe_dump(
            {
                "tables": [
                    {
                        "table_name": "salesorderline",
                        "source_file": "SalesOrderLine.csv",
                        "columns": ["ref_nr", "part_nr_sku", "quantity"],
                    },
                    {
                        "table_name": "salesorderline_export_salesorderline",
                        "source_file": "SalesOrderLine.xlsx",
                        "columns": ["ref_nr", "part_nr_sku", "quantity"],
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_human_review_generates_required_files(tmp_path: Path) -> None:
    step3_dir = tmp_path / "step3_modeling"
    output_dir = tmp_path / "step3b_human_review"
    config_dir = tmp_path / "config" / "data_model"
    seed_step3(step3_dir, config_dir)

    result = run_human_review(step3_dir, output_dir, config_dir)

    assert result.decision_count == 4
    assert (output_dir / "approval_decision_matrix.csv").exists()
    assert (output_dir / "source_canonical_decisions.md").exists()
    assert (output_dir / "key_approval_candidates.md").exists()
    assert (output_dir / "relationship_approval_candidates.md").exists()
    assert (output_dir / "duplicate_investigation_request.md").exists()
    assert (config_dir / "human_approval_template.yml").exists()


def test_human_review_does_not_modify_approved_files(tmp_path: Path) -> None:
    step3_dir = tmp_path / "step3_modeling"
    output_dir = tmp_path / "step3b_human_review"
    config_dir = tmp_path / "config" / "data_model"
    seed_step3(step3_dir, config_dir)
    approved_keys = config_dir / "approved_keys.yml"
    approved_relationships = config_dir / "approved_relationships.yml"
    approved_keys.write_text("approved_keys:\n- keep: true\n", encoding="utf-8")
    approved_relationships.write_text("approved_relationships:\n- keep: true\n", encoding="utf-8")
    keys_before = approved_keys.read_text(encoding="utf-8")
    relationships_before = approved_relationships.read_text(encoding="utf-8")

    run_human_review(step3_dir, output_dir, config_dir)

    assert approved_keys.read_text(encoding="utf-8") == keys_before
    assert approved_relationships.read_text(encoding="utf-8") == relationships_before


def test_apply_approvals_command_logic_only_validates_template(tmp_path: Path) -> None:
    step3_dir = tmp_path / "step3_modeling"
    output_dir = tmp_path / "step3b_human_review"
    config_dir = tmp_path / "config" / "data_model"
    seed_step3(step3_dir, config_dir)
    run_human_review(step3_dir, output_dir, config_dir)

    counts = validate_approval_template(config_dir / "human_approval_template.yml")

    assert counts == {"pending": 4}
