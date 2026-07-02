from __future__ import annotations

import csv
from pathlib import Path

import yaml

from data_ops_lab.source_onboarding import file_sha256, run_source_onboarding


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_source_onboarding_generates_required_outputs_and_preserves_sources(tmp_path: Path) -> None:
    input_dir = tmp_path / "originaldatabase"
    config_dir = tmp_path / "config" / "data_model"
    output_dir = tmp_path / "outputs" / "originaldatabase_analysis" / "step3_modeling"
    input_dir.mkdir()
    source_file = input_dir / "SalesOrder.csv"
    write_csv(
        source_file,
        [
            {"Ref. nr.": "SO-1", "Customer code": "C-1", "Amount": "10"},
            {"Ref. nr.": "SO-2", "Customer code": "C-2", "Amount": "20"},
        ],
    )
    before_hash = file_sha256(source_file)

    result = run_source_onboarding(input_dir, output_dir, config_dir)

    assert result["source_count"] == 1
    assert file_sha256(source_file) == before_hash
    assert (config_dir / "source_manifest.yml").exists()
    assert (output_dir / "source_onboarding_candidates.csv").exists()
    assert (output_dir / "key_candidates.csv").exists()
    assert (output_dir / "relationship_candidates.csv").exists()
    assert (output_dir / "manual_review_pack.md").exists()

    manifest = yaml.safe_load((config_dir / "source_manifest.yml").read_text(encoding="utf-8"))
    assert manifest["sources"][0]["file_hash"] == before_hash
    assert manifest["sources"][0]["status"] == "new"


def test_source_onboarding_detects_known_and_new_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "originaldatabase"
    config_dir = tmp_path / "config" / "data_model"
    output_dir = tmp_path / "outputs" / "originaldatabase_analysis" / "step3_modeling"
    input_dir.mkdir()
    write_csv(input_dir / "SalesOrder.csv", [{"Ref. nr.": "SO-1", "Amount": "10"}])

    run_source_onboarding(input_dir, output_dir, config_dir)
    write_csv(input_dir / "SalesInvoice.csv", [{"Ref. nr.": "INV-1", "Amount": "10"}])
    run_source_onboarding(input_dir, output_dir, config_dir)

    manifest = yaml.safe_load((config_dir / "source_manifest.yml").read_text(encoding="utf-8"))
    statuses = {source["file_name"]: source["status"] for source in manifest["sources"]}
    assert statuses["SalesOrder.csv"] == "known"
    assert statuses["SalesInvoice.csv"] == "new"


def test_source_onboarding_does_not_modify_approved_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "originaldatabase"
    config_dir = tmp_path / "config" / "data_model"
    output_dir = tmp_path / "outputs" / "originaldatabase_analysis" / "step3_modeling"
    input_dir.mkdir()
    config_dir.mkdir(parents=True)
    write_csv(input_dir / "SalesOrder.csv", [{"Ref. nr.": "SO-1", "Amount": "10"}])
    approved_keys = config_dir / "approved_keys.yml"
    approved_relationships = config_dir / "approved_relationships.yml"
    approved_keys.write_text("approved_keys:\n- keep_this: true\n", encoding="utf-8")
    approved_relationships.write_text("approved_relationships:\n- keep_this: true\n", encoding="utf-8")
    keys_before = approved_keys.read_text(encoding="utf-8")
    relationships_before = approved_relationships.read_text(encoding="utf-8")

    run_source_onboarding(input_dir, output_dir, config_dir)

    assert approved_keys.read_text(encoding="utf-8") == keys_before
    assert approved_relationships.read_text(encoding="utf-8") == relationships_before


def test_generated_candidates_remain_pending_review(tmp_path: Path) -> None:
    input_dir = tmp_path / "originaldatabase"
    config_dir = tmp_path / "config" / "data_model"
    output_dir = tmp_path / "outputs" / "originaldatabase_analysis" / "step3_modeling"
    input_dir.mkdir()
    write_csv(
        input_dir / "SalesOrderLine.csv",
        [
            {"Ref. nr.": "SO-1", "Part nr. (SKU)": "SKU-1", "# tot.": "1"},
            {"Ref. nr.": "SO-1", "Part nr. (SKU)": "SKU-2", "# tot.": "2"},
        ],
    )
    write_csv(input_dir / "SalesOrder.csv", [{"Ref. nr.": "SO-1", "Amount": "10"}])

    run_source_onboarding(input_dir, output_dir, config_dir)

    for file_name in ["key_candidates.csv", "relationship_candidates.csv", "source_onboarding_candidates.csv"]:
        rows = list(csv.DictReader((output_dir / file_name).open(encoding="utf-8")))
        assert rows
        assert {row["status"] for row in rows} == {"pending_review"}
