from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import pytest
import yaml

from data_ops_lab.analytics_dataset_benchmark import (
    AnalyticsDatasetBenchmarkResult,
    run_analytics_dataset_benchmark_validation,
)
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


SEMANTIC_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "analytics_answer_evaluation"
    / "approved_semantic_catalog.yml"
)


def write_yaml(path: Path, payload: object) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def approval_payload(paths: dict[str, Path]) -> dict:
    return {
        "version": 1,
        "status": "approved",
        "dataset_id": "synthetic_dataset_package",
        "pack_id": "synthetic_dataset_pack_v1",
        "source": {
            "dataset_manifest_sha256": file_sha256(paths["manifest"]),
            "database_sha256": file_sha256(paths["database"]),
            "approved_semantic_state_sha256": file_sha256(paths["semantic"]),
            "approved_relationships_sha256": file_sha256(paths["relationships"]),
            "benchmark_pack_sha256": file_sha256(paths["pack"]),
        },
        "decision": {
            "local_offline_evaluation_approved": True,
            "recorded_provider_responses_reviewed": True,
            "expected_requests_reviewed": True,
            "expected_results_reviewed": True,
            "comparison_policy_reviewed": True,
            "live_provider_use_approved": False,
            "external_upload_approved": False,
            "model_training_approved": False,
        },
        "approved_by": "synthetic-reviewer",
        "approved_at": "2026-07-14T18:00:00+00:00",
    }


def build_fixture(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "database": tmp_path / "synthetic.duckdb",
        "semantic": tmp_path / "approved_semantic_catalog.yml",
        "relationships": tmp_path / "approved_relationships.yml",
        "manifest": tmp_path / "dataset_manifest.yml",
        "pack": tmp_path / "benchmark_pack.yml",
        "approval": tmp_path / "benchmark_approval.yml",
        "output": tmp_path / "validation",
    }
    paths["semantic"].write_bytes(SEMANTIC_FIXTURE.read_bytes())
    write_yaml(
        paths["relationships"],
        {
            "approved_relationships": [
                {
                    "source_table": "synthetic_orders",
                    "source_column": "order_id",
                    "target_table": "synthetic_order_lines",
                    "target_column": "order_id",
                }
            ]
        },
    )
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute(
            "create table synthetic_orders(order_id integer, order_amount decimal(18,2))"
        )
        connection.execute("insert into synthetic_orders values (1, 10.50), (2, 27.25)")
    semantic_hash = file_sha256(paths["semantic"])
    relationships_hash = file_sha256(paths["relationships"])
    database_hash = file_sha256(paths["database"])
    write_yaml(
        paths["manifest"],
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
                "sha256": database_hash,
            },
            "provenance": {
                "status": "verified",
                "source": "pytest generated synthetic package",
            },
            "license": {"status": "verified", "identifier": "synthetic-test-data"},
            "bindings": {
                "approved_semantic_state_sha256": semantic_hash,
                "approved_relationships_sha256": relationships_hash,
            },
        },
    )
    write_yaml(
        paths["pack"],
        {
            "version": 1,
            "status": "candidate_for_review",
            "pack_id": "synthetic_dataset_pack_v1",
            "dataset_id": "synthetic_dataset_package",
            "bindings": {
                "dataset_manifest_sha256": file_sha256(paths["manifest"]),
                "database_sha256": database_hash,
                "approved_semantic_state_sha256": semantic_hash,
                "approved_relationships_sha256": relationships_hash,
            },
            "cases": [
                {
                    "id": "exact_order_count",
                    "question": "How many synthetic orders exist?",
                    "provider_response": {
                        "version": 1,
                        "from": "sales orders",
                        "metrics": [{"term": "order count", "alias": "orders"}],
                        "limit": 20,
                    },
                    "expected_request": {
                        "version": 1,
                        "question": "How many synthetic orders exist?",
                        "from": "synthetic_orders",
                        "joins": [],
                        "dimensions": [],
                        "metrics": [{"function": "count", "column": "*", "alias": "orders"}],
                        "filters": [],
                        "order_by": [],
                        "limit": 20,
                    },
                    "expected_result": {
                        "status": "completed",
                        "columns": [{"name": "orders", "type": "integer"}],
                        "rows": [[2]],
                        "row_count": 1,
                        "column_count": 1,
                        "null_cells": 0,
                    },
                    "comparison": {"mode": "exact", "tolerances": []},
                },
                {
                    "id": "tolerant_total_amount",
                    "question": "What is the synthetic total amount?",
                    "provider_response": {
                        "version": 1,
                        "from": "sales orders",
                        "metrics": [
                            {"term": "total order amount", "alias": "total_amount"}
                        ],
                        "limit": 20,
                    },
                    "expected_request": {
                        "version": 1,
                        "question": "What is the synthetic total amount?",
                        "from": "synthetic_orders",
                        "joins": [],
                        "dimensions": [],
                        "metrics": [
                            {
                                "function": "sum",
                                "column": "synthetic_orders.order_amount",
                                "alias": "total_amount",
                            }
                        ],
                        "filters": [],
                        "order_by": [],
                        "limit": 20,
                    },
                    "expected_result": {
                        "status": "completed",
                        "columns": [{"name": "total_amount", "type": "decimal"}],
                        "rows": [["37.75"]],
                        "row_count": 1,
                        "column_count": 1,
                        "null_cells": 0,
                    },
                    "comparison": {
                        "mode": "numeric_tolerance",
                        "tolerances": [
                            {"column": "total_amount", "absolute": 0.01, "relative": 0.0}
                        ],
                    },
                },
            ],
        },
    )
    write_yaml(paths["approval"], approval_payload(paths))
    return paths


def run_validation(paths: dict[str, Path]) -> AnalyticsDatasetBenchmarkResult:
    return run_analytics_dataset_benchmark_validation(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        paths["approval"],
        paths["output"],
    )


def blocker_types(result: AnalyticsDatasetBenchmarkResult) -> set[str]:
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def output_bytes(output_dir: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }


def test_hash_bound_dataset_pack_is_ready_without_opening_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("validator attempted a DuckDB connection"),
    )
    protected = {
        path: file_sha256(path)
        for name, path in paths.items()
        if name not in {"output"}
    }

    first = run_validation(paths)
    first_outputs = output_bytes(paths["output"])
    second = run_validation(paths)
    manifest = read_yaml(first.manifest_path)
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in paths["output"].iterdir()
        if path.is_file()
    )

    assert first.status == "ready_for_offline_evaluation"
    assert first.blocker_count == 0
    assert first.case_count == 2
    assert first.exact_case_count == 1
    assert first.tolerance_case_count == 1
    assert first.relationship_count == 1
    assert manifest["controls"] == {
        "database_hashed": True,
        "database_opened": False,
        "database_rows_read": False,
        "query_executed": False,
        "network_accessed": False,
        "live_provider_used": False,
        "external_upload_authorized": False,
        "model_training_authorized": False,
    }
    assert "How many synthetic orders exist?" not in persisted
    assert "37.75" not in persisted
    assert "synthetic_orders" not in persisted
    assert second.outputs_changed is False
    assert first_outputs == output_bytes(paths["output"])
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_database_hash_drift_blocks_validation(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    with paths["database"].open("ab") as handle:
        handle.write(b"drift")

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "dataset_artifact_hash_mismatch" in blocker_types(result)
    assert "benchmark_hash_binding_mismatch" in blocker_types(result)


def test_semantic_hash_drift_blocks_all_bound_authorities(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    paths["semantic"].write_text(
        paths["semantic"].read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "benchmark_hash_binding_mismatch" in blocker_types(result)


def test_unverified_license_blocks_dataset_package(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    manifest = read_yaml(paths["manifest"])
    manifest["license"]["status"] = "pending"
    write_yaml(paths["manifest"], manifest)

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "benchmark_license_not_verified" in blocker_types(result)


def test_approval_cannot_authorize_external_upload(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    approval = read_yaml(paths["approval"])
    approval["decision"]["external_upload_approved"] = True
    write_yaml(paths["approval"], approval)

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "benchmark_approval_scope_invalid" in blocker_types(result)


def test_approval_requires_timezone_aware_iso_timestamp(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    approval = read_yaml(paths["approval"])
    approval["approved_at"] = "2026-07-14 18:00:00"
    write_yaml(paths["approval"], approval)

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "invalid_benchmark_approval_time" in blocker_types(result)


def test_tolerance_must_target_declared_numeric_column(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    pack = read_yaml(paths["pack"])
    pack["cases"][1]["comparison"]["tolerances"][0]["column"] = "missing_column"
    write_yaml(paths["pack"], pack)
    write_yaml(paths["approval"], approval_payload(paths))

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "invalid_dataset_tolerance_column" in blocker_types(result)


def test_different_existing_evidence_is_not_overwritten(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    first = run_validation(paths)
    first.report_path.write_text("different\n", encoding="utf-8")
    protected = output_bytes(paths["output"])

    with pytest.raises(ValueError, match="existing generated evidence was not overwritten"):
        run_validation(paths)

    assert protected == output_bytes(paths["output"])


def test_cli_requires_every_bound_input_and_exposes_no_execution_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "analytics-dataset-benchmark-validate",
            "--dataset-manifest",
            "manifest.yml",
            "--database",
            "dataset.duckdb",
            "--semantic-state",
            "semantic.yml",
            "--relationships",
            "relationships.yml",
            "--pack",
            "pack.yml",
            "--approval",
            "approval.yml",
            "--output",
            "evidence",
        ]
    )

    assert args.command == "analytics-dataset-benchmark-validate"
    assert args.dataset_manifest == Path("manifest.yml")
    assert args.database == Path("dataset.duckdb")
    assert args.semantic_state == Path("semantic.yml")
    assert args.relationships == Path("relationships.yml")
    assert args.pack == Path("pack.yml")
    assert args.approval == Path("approval.yml")
    assert args.output == Path("evidence")
    assert not hasattr(args, "execute")
    assert not hasattr(args, "allow_network")
    assert not hasattr(args, "provider")
