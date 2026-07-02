from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from data_ops_lab.serial_rules import (
    detected_prefix,
    parse_serial_format,
    run_serial_rules,
    validate_ref_pattern,
)


def create_serials(path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "Module": "verkoop opdracht",
                "First linked company": "EDS",
                "Format": "OCYY99999",
                "Ref. nr.": 1661,
                "Generate on": "Creation",
                "document sett.": "",
                "Sort order": "",
            },
            {
                "Module": "klant project",
                "First linked company": "EDS",
                "Format": "CPYY9999",
                "Ref. nr.": 1780,
                "Generate on": "Creation",
                "document sett.": "",
                "Sort order": "",
            },
            {
                "Module": "Inkoopopdrachten",
                "First linked company": "EDS",
                "Format": "ONYY99999",
                "Ref. nr.": 2758,
                "Generate on": "Creation",
                "document sett.": "",
                "Sort order": "",
            },
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Export_Serials", index=False)


def test_parse_serial_format_to_regex() -> None:
    assert parse_serial_format("CPYY9999") == {
        "format_original": "CPYY9999",
        "prefix": "CP",
        "year_token": "YY",
        "sequence_token": "9999",
        "expected_regex": r"^CP[0-9]{2}[0-9]{4}$",
    }
    assert parse_serial_format("OCYY99999")["expected_regex"] == r"^OC[0-9]{2}[0-9]{5}$"
    assert parse_serial_format("ONYY99999")["prefix"] == "ON"


def test_detected_prefix_and_ref_validation() -> None:
    df = pd.DataFrame({"ref_nr": ["OC2601661", "OC2601660", "XX2600001", None]})
    result = validate_ref_pattern(df, "ref_nr", "OC", r"^OC[0-9]{2}[0-9]{5}$")

    assert detected_prefix("OC2601661") == "OC"
    assert result["total_rows"] == 4
    assert result["non_null_ref_count"] == 3
    assert result["prefix_match_rate"] == 66.67
    assert result["regex_match_rate"] == 66.67
    assert result["invalid_ref_count"] == 1
    assert result["multiple_prefixes_detected"] is True


def test_run_serial_rules_generates_outputs_and_preserves_approved_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "originaldatabase"
    serials = data_dir / "Serials.xlsx"
    create_serials(serials)
    pd.DataFrame(
        [
            {"Ref. nr.": "OC2601661", "Amount": 1},
            {"Ref. nr.": "OC2601660", "Amount": 2},
        ]
    ).to_csv(data_dir / "SalesOrder.csv", index=False)

    step3_dir = tmp_path / "outputs" / "originaldatabase_analysis" / "step3_modeling"
    step3_dir.mkdir(parents=True)
    pd.DataFrame(
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
            }
        ]
    ).to_csv(step3_dir / "key_candidates.csv", index=False)

    config_dir = tmp_path / "config" / "data_model"
    config_dir.mkdir(parents=True)
    approved_keys = config_dir / "approved_keys.yml"
    approved_relationships = config_dir / "approved_relationships.yml"
    approved_keys.write_text("approved_keys: []\n", encoding="utf-8")
    approved_relationships.write_text("approved_relationships: []\n", encoding="utf-8")
    keys_before = approved_keys.read_text(encoding="utf-8")
    relationships_before = approved_relationships.read_text(encoding="utf-8")

    output_dir = tmp_path / "outputs" / "originaldatabase_analysis" / "step3c_serial_reference_rules"
    result = run_serial_rules(serials, data_dir, output_dir, config_dir, step3_dir)

    assert result.rules_count == 3
    assert (config_dir / "reference_serial_rules.yml").exists()
    assert (config_dir / "reference_translation_map.yml").exists()
    assert (config_dir / "semantic_ref_mapping.yml").exists()
    assert (output_dir / "ref_pattern_validation.csv").exists()
    assert (output_dir / "ref_pattern_validation_report.md").exists()
    assert (output_dir / "key_candidate_serial_enrichment.csv").exists()
    assert approved_keys.read_text(encoding="utf-8") == keys_before
    assert approved_relationships.read_text(encoding="utf-8") == relationships_before

    rules = yaml.safe_load((config_dir / "reference_serial_rules.yml").read_text(encoding="utf-8"))
    assert rules["rules"][0]["status"] == "pending_review"
