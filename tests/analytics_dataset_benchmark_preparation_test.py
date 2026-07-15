from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import yaml

from data_ops_lab.analytics_dataset_benchmark_preparation import (
    REVIEW_NAME,
    run_analytics_dataset_benchmark_preparation,
)
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


SEMANTIC_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "analytics_translation"
    / "approved_semantic_catalog.yml"
)


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_fixture(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "database": tmp_path / "synthetic.duckdb",
        "semantic": tmp_path / "approved_semantic_catalog.yml",
        "relationships": tmp_path / "approved_relationships.yml",
        "dataset_manifest": tmp_path / "dataset_manifest.yml",
        "design": tmp_path / "answer_design.yml",
        "output": tmp_path / "preparation",
    }
    paths["semantic"].write_bytes(SEMANTIC_FIXTURE.read_bytes())
    write_yaml(paths["relationships"], {"approved_relationships": []})
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute(
            "create table physical_orders_private(order_id integer, private_status_column varchar)"
        )
        connection.execute(
            "insert into physical_orders_private values (1, 'open'), (2, 'closed')"
        )
    write_yaml(
        paths["dataset_manifest"],
        {
            "version": 1,
            "status": "verified_dataset_package",
            "dataset": {
                "id": "synthetic_dataset_package",
                "classification": "synthetic",
                "format": "duckdb",
            },
            "artifact": {
                "bytes": paths["database"].stat().st_size,
                "sha256": file_sha256(paths["database"]),
            },
            "provenance": {
                "status": "verified",
                "source": "pytest generated synthetic package",
            },
            "license": {"status": "verified", "identifier": "synthetic-test-data"},
            "bindings": {
                "approved_semantic_state_sha256": file_sha256(paths["semantic"]),
                "approved_relationships_sha256": file_sha256(paths["relationships"]),
            },
        },
    )
    write_yaml(
        paths["design"],
        {
            "version": 1,
            "status": "candidate_for_execution_review",
            "design_id": "synthetic_answer_design_v1",
            "pack_id": "synthetic_dataset_pack_v1",
            "dataset_id": "synthetic_dataset_package",
            "bindings": {
                "dataset_manifest_sha256": file_sha256(paths["dataset_manifest"]),
                "database_sha256": file_sha256(paths["database"]),
                "approved_semantic_state_sha256": file_sha256(paths["semantic"]),
                "approved_relationships_sha256": file_sha256(paths["relationships"]),
            },
            "cases": [
                {
                    "id": "order_count",
                    "coverage": [
                        "table_selection",
                        "measure_selection",
                        "exact_answer",
                    ],
                    "question": "How many synthetic orders exist?",
                    "provider_response": {
                        "version": 1,
                        "from": "sales_orders",
                        "metrics": [{"term": "order_count", "alias": "orders"}],
                        "limit": 20,
                    },
                    "result_shape": "single_row",
                    "expected_columns": [{"name": "orders", "type": "integer"}],
                    "comparison": {"mode": "exact", "tolerances": []},
                }
            ],
        },
    )
    return paths


def run_preparation(paths: dict[str, Path]):
    return run_analytics_dataset_benchmark_preparation(
        paths["design"],
        paths["dataset_manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["output"],
    )


def test_preparation_builds_exact_plans_and_stops_before_stage_5b(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)

    first = run_preparation(paths)
    second = run_preparation(paths)

    manifest = read_yaml(first.manifest_path)
    review = read_yaml(first.review_path)
    row = manifest["cases"][0]
    assert first.status == "awaiting_execution_review"
    assert first.case_count == 1
    assert first.ready_case_count == 1
    assert first.blocker_count == 0
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert manifest["controls"]["table_rows_read"] is False
    assert manifest["controls"]["query_execution_authorized"] is False
    assert manifest["controls"]["network_access"] is False
    assert row["translation_status"] == "ready_for_query_plan"
    assert row["plan_status"] == "ready_for_execution_review"
    assert row["expected_columns"] == [{"name": "orders", "type": "integer"}]
    assert review["status"] == "pending_human_review"
    assert review["source"]["preparation_manifest_sha256"] == file_sha256(
        first.manifest_path
    )
    assert review["review"]["case_decisions"] == [
        {
            "case_id": "order_count",
            "reviewed_plan_sha256": row["plan_sha256"],
            "decision": "pending",
            "notes": "",
        }
    ]
    assert not list(paths["output"].rglob("analytics_query_result.csv"))


def test_invalid_provider_response_blocks_before_catalog_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = build_fixture(tmp_path)
    design = read_yaml(paths["design"])
    design["cases"][0]["provider_response"]["sql"] = "select * from private"
    write_yaml(paths["design"], design)

    monkeypatch.setattr(
        "data_ops_lab.analytics_query_plan.duckdb.connect",
        lambda *args, **kwargs: pytest.fail("invalid design reached DuckDB catalog"),
    )
    result = run_preparation(paths)

    assert result.status == "blocked"
    assert result.ready_case_count == 0
    assert result.review_path is None
    assert not (paths["output"] / REVIEW_NAME).exists()
    assert "provider_sql_not_allowed" in result.blockers_path.read_text(
        encoding="utf-8"
    )


def test_binding_drift_blocks_before_case_materialization(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    design = read_yaml(paths["design"])
    design["bindings"]["database_sha256"] = "0" * 64
    write_yaml(paths["design"], design)

    result = run_preparation(paths)

    assert result.status == "blocked"
    assert result.case_count == 0
    assert not (paths["output"] / "cases").exists()
    assert "benchmark_answer_design_binding_mismatch" in result.blockers_path.read_text(
        encoding="utf-8"
    )


def test_output_alias_mismatch_blocks_aggregate_review(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    design = read_yaml(paths["design"])
    design["cases"][0]["expected_columns"][0]["name"] = "wrong_alias"
    write_yaml(paths["design"], design)

    result = run_preparation(paths)

    assert result.status == "blocked"
    assert result.ready_case_count == 1
    assert result.review_path is None
    assert "benchmark_answer_design_output_mismatch" in result.blockers_path.read_text(
        encoding="utf-8"
    )
    assert not list(paths["output"].rglob("analytics_query_result.csv"))


def test_different_case_evidence_is_not_overwritten(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    first = run_preparation(paths)
    question_path = next(paths["output"].rglob("question.txt"))
    original = question_path.read_bytes()
    design = read_yaml(paths["design"])
    design["cases"][0]["question"] = "How many orders are present?"
    write_yaml(paths["design"], design)

    with pytest.raises(ValueError, match="Existing evidence was not overwritten"):
        run_preparation(paths)

    assert first.status == "awaiting_execution_review"
    assert question_path.read_bytes() == original


def test_cli_exposes_only_preparation_inputs_and_no_execution_bypass() -> None:
    args = build_parser().parse_args(
        [
            "analytics-dataset-benchmark-answer-prepare",
            "--design",
            "design.yml",
            "--dataset-manifest",
            "dataset.yml",
            "--database",
            "benchmark.duckdb",
            "--semantic-state",
            "semantic.yml",
            "--relationships",
            "relationships.yml",
            "--output",
            "preparation",
        ]
    )

    assert args.command == "analytics-dataset-benchmark-answer-prepare"
    assert args.design == Path("design.yml")
    assert not hasattr(args, "allow_network")
    assert not hasattr(args, "apply")
    assert not hasattr(args, "plan")
