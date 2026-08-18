from __future__ import annotations

import csv
import hashlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
import yaml

import data_ops_lab.analytics_dataset_benchmark_evaluation as dataset_evaluation
import data_ops_lab.analytics_dataset_benchmark_live_evaluation as live_evaluation
import data_ops_lab.analytics_ollama_soak as ollama_soak
from data_ops_lab.analytics_dataset_benchmark import (
    AnalyticsDatasetBenchmarkResult,
    inspect_analytics_dataset_benchmark_candidate,
    run_analytics_dataset_benchmark_validation,
)
from data_ops_lab.analytics_dataset_benchmark_evaluation import (
    AnalyticsDatasetBenchmarkEvaluationResult,
    run_analytics_dataset_benchmark_evaluation,
)
from data_ops_lab.analytics_dataset_benchmark_live_evaluation import (
    AnalyticsDatasetBenchmarkLiveEvaluationResult,
    run_analytics_dataset_benchmark_live_evaluation,
)
from data_ops_lab.analytics_dataset_benchmark_review import (
    CASE_REVIEW_FIELDS,
    run_analytics_dataset_benchmark_approval,
    run_analytics_dataset_benchmark_review,
)
from data_ops_lab.analytics_ollama_soak import run_analytics_ollama_soak
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
        "review_evidence": {
            "review_sha256": hashlib.sha256(b"synthetic benchmark review").hexdigest(),
            "decision_digest": hashlib.sha256(b"synthetic benchmark decisions").hexdigest(),
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
            "create table synthetic_orders("
            "order_id integer, order_amount decimal(18,2), order_status varchar)"
        )
        connection.execute(
            "insert into synthetic_orders values "
            "(1, 10.50, 'open'), (2, 27.25, 'closed')"
        )
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


def test_candidate_accepts_hash_bound_governed_relationship_registry(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    original = read_yaml(paths["relationships"])
    write_yaml(
        paths["relationships"],
        {
            "version": 1,
            "status": "approved",
            "dataset": "synthetic",
            "authority": {
                "source_manifest_sha256": "1" * 64,
                "relationship_candidates_sha256": "2" * 64,
                "completed_review_sha256": "3" * 64,
                "derived_from_completed_human_review": True,
                "automatic_approval": False,
                "scope": "local_offline_relationship_use",
            },
            "approved_relationships": original["approved_relationships"],
            "rejected_relationship_ids": [],
            "non_authorizations": [
                "external_upload",
                "model_parameter_training",
                "publication",
            ],
        },
    )
    relationships_hash = file_sha256(paths["relationships"])
    manifest = read_yaml(paths["manifest"])
    manifest["bindings"]["approved_relationships_sha256"] = relationships_hash
    write_yaml(paths["manifest"], manifest)
    pack = read_yaml(paths["pack"])
    pack["bindings"]["approved_relationships_sha256"] = relationships_hash
    pack["bindings"]["dataset_manifest_sha256"] = file_sha256(paths["manifest"])
    write_yaml(paths["pack"], pack)

    candidate = inspect_analytics_dataset_benchmark_candidate(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
    )

    assert candidate.blockers == ()
    assert candidate.relationship_count == 1


def blocker_types(result: AnalyticsDatasetBenchmarkResult) -> set[str]:
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def output_bytes(output_dir: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }


def prepare_benchmark_review(paths: dict[str, Path], review_path: Path) -> Path:
    result = run_analytics_dataset_benchmark_review(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
    )
    assert result.case_count == len(read_yaml(paths["pack"])["cases"])
    return result.review_path


def complete_benchmark_review(review_path: Path) -> dict:
    review = read_yaml(review_path)
    review["status"] = "completed_human_review"
    review["review"]["reviewer"] = "synthetic-reviewer"
    review["review"]["reviewed_at"] = "2026-07-14T19:00:00+00:00"
    for row in review["review"]["scope_decisions"]:
        row["decision"] = (
            "approved" if row["scope"] == "local_offline_evaluation" else "not_authorized"
        )
        row["notes"] = "Reviewed synthetic scope."
    for row in review["review"]["case_decisions"]:
        for field in CASE_REVIEW_FIELDS:
            row[field] = "approved"
        row["notes"] = "Reviewed against the exact synthetic pack."
    write_yaml(review_path, review)
    return review


def generate_benchmark_approval(paths: dict[str, Path], root: Path) -> Path:
    review_path = prepare_benchmark_review(paths, root / "review.yml")
    complete_benchmark_review(review_path)
    approval_path = root / "generated_approval.yml"
    result = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        root / "approval_evidence",
        approval_path,
        apply=True,
    )
    assert result.status == "ready_for_apply"
    assert result.approval_changed is True
    return approval_path


def add_no_rows_case(paths: dict[str, Path]) -> None:
    pack = read_yaml(paths["pack"])
    pack["cases"].append(
        {
            "id": "missing_status_no_rows",
            "question": "Which missing synthetic statuses have orders?",
            "provider_response": {
                "version": 1,
                "from": "sales orders",
                "dimensions": [{"term": "order status", "alias": "status"}],
                "metrics": [{"term": "order count", "alias": "orders"}],
                "filters": [
                    {"term": "order status", "operator": "eq", "value": "missing"}
                ],
                "order_by": [{"field": "status", "direction": "asc"}],
                "limit": 20,
            },
            "expected_request": {
                "version": 1,
                "question": "Which missing synthetic statuses have orders?",
                "from": "synthetic_orders",
                "joins": [],
                "dimensions": [
                    {"column": "synthetic_orders.order_status", "alias": "status"}
                ],
                "metrics": [{"function": "count", "column": "*", "alias": "orders"}],
                "filters": [
                    {
                        "column": "synthetic_orders.order_status",
                        "operator": "eq",
                        "value": "missing",
                    }
                ],
                "order_by": [{"field": "status", "direction": "asc"}],
                "limit": 20,
            },
            "expected_result": {
                "status": "completed_no_rows",
                "columns": [
                    {"name": "status", "type": "string"},
                    {"name": "orders", "type": "integer"},
                ],
                "rows": [],
                "row_count": 0,
                "column_count": 2,
                "null_cells": 0,
            },
            "comparison": {"mode": "exact", "tolerances": []},
        }
    )
    write_yaml(paths["pack"], pack)


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


def test_approval_requires_hash_bound_review_evidence(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    approval = read_yaml(paths["approval"])
    approval.pop("review_evidence")
    write_yaml(paths["approval"], approval)

    result = run_validation(paths)

    assert result.status == "blocked"
    assert "invalid_benchmark_review_evidence" in blocker_types(result)


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


def test_review_template_is_hash_bound_pending_and_non_overwriting(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    review_path = tmp_path / "benchmark_review.yml"
    first = run_analytics_dataset_benchmark_review(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
    )
    initial = review_path.read_bytes()
    second = run_analytics_dataset_benchmark_review(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
    )
    review = read_yaml(review_path)

    assert first.case_count == 2
    assert second.output_changed is False
    assert review_path.read_bytes() == initial
    assert review["status"] == "pending_human_review"
    assert review["source"]["benchmark_pack_sha256"] == file_sha256(paths["pack"])
    assert {row["case_id"] for row in review["review"]["case_decisions"]} == {
        "exact_order_count",
        "tolerant_total_amount",
    }
    assert {row["decision"] for row in review["review"]["scope_decisions"]} == {
        "pending"
    }
    assert "How many synthetic orders exist?" not in review_path.read_text(encoding="utf-8")

    review["review"]["reviewer"] = "human"
    write_yaml(review_path, review)
    with pytest.raises(ValueError, match="human authority was not overwritten"):
        run_analytics_dataset_benchmark_review(
            paths["manifest"],
            paths["database"],
            paths["semantic"],
            paths["relationships"],
            paths["pack"],
            review_path,
        )


def test_pending_benchmark_review_blocks_dry_run_without_approval(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    approval_path = tmp_path / "generated_approval.yml"
    result = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        tmp_path / "approval_evidence",
        approval_path,
    )

    assert result.status == "blocked"
    assert result.dry_run is True
    assert approval_path.exists() is False
    assert {
        "benchmark_review_not_completed",
        "missing_benchmark_reviewer",
        "invalid_benchmark_reviewed_at",
        "benchmark_scope_not_approved",
        "benchmark_case_review_not_approved",
    } <= blocker_types(result)


def test_completed_benchmark_review_dry_run_is_ready_without_writing_approval(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    complete_benchmark_review(review_path)
    approval_path = tmp_path / "generated_approval.yml"
    result = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        tmp_path / "approval_evidence",
        approval_path,
    )
    plan = read_yaml(result.plan_path)

    assert result.status == "ready_for_apply"
    assert result.blocker_count == 0
    assert result.dry_run is True
    assert approval_path.exists() is False
    assert plan["proposed_approval"]["decision"]["local_offline_evaluation_approved"] is True
    assert plan["proposed_approval"]["decision"]["external_upload_approved"] is False
    assert len(plan["proposed_approval"]["review_evidence"]["decision_digest"]) == 64
    persisted = result.plan_path.read_text(encoding="utf-8")
    assert "How many synthetic orders exist?" not in persisted
    assert "Reviewed against the exact synthetic pack." not in persisted


def test_apply_writes_idempotent_approval_consumed_by_final_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    complete_benchmark_review(review_path)
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("review workflow attempted a DuckDB connection"),
    )
    approval_path = tmp_path / "generated_approval.yml"
    evidence_dir = tmp_path / "approval_evidence"
    protected = {
        path: file_sha256(path)
        for path in (
            paths["manifest"],
            paths["database"],
            paths["semantic"],
            paths["relationships"],
            paths["pack"],
            review_path,
        )
    }

    first = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        evidence_dir,
        approval_path,
        apply=True,
    )
    second = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        evidence_dir,
        approval_path,
        apply=True,
    )
    validation = run_analytics_dataset_benchmark_validation(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        approval_path,
        tmp_path / "final_validation",
    )

    assert first.approval_changed is True
    assert second.approval_changed is False
    assert second.outputs_changed is False
    assert validation.status == "ready_for_offline_evaluation"
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_candidate_drift_after_review_blocks_approval(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    complete_benchmark_review(review_path)
    paths["semantic"].write_text(
        paths["semantic"].read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    result = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        tmp_path / "approval_evidence",
        tmp_path / "generated_approval.yml",
        apply=True,
    )

    assert result.status == "blocked"
    assert result.approval_path.exists() is False
    assert "benchmark_review_source_drift" in blocker_types(result)


def test_rejected_missing_and_duplicate_case_decisions_block_approval(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    review = complete_benchmark_review(review_path)
    review["review"]["case_decisions"][0]["expected_result"] = "rejected"
    review["review"]["case_decisions"].append(review["review"]["case_decisions"][0].copy())
    review["review"]["case_decisions"] = review["review"]["case_decisions"][:-2] + [
        review["review"]["case_decisions"][-1]
    ]
    write_yaml(review_path, review)
    result = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        tmp_path / "approval_evidence",
        tmp_path / "generated_approval.yml",
        apply=True,
    )

    assert result.status == "blocked"
    assert {
        "benchmark_case_review_not_approved",
        "duplicate_benchmark_case_decision",
        "missing_benchmark_case_decision",
    } <= blocker_types(result)


def test_review_cannot_expand_live_provider_scope(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    review = complete_benchmark_review(review_path)
    live_scope = next(
        row
        for row in review["review"]["scope_decisions"]
        if row["scope"] == "live_provider_use"
    )
    live_scope["decision"] = "approved"
    write_yaml(review_path, review)
    result = run_analytics_dataset_benchmark_approval(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        review_path,
        tmp_path / "approval_evidence",
        tmp_path / "generated_approval.yml",
        apply=True,
    )

    assert result.status == "blocked"
    assert "benchmark_scope_expansion_not_allowed" in blocker_types(result)


def test_different_existing_approval_is_not_overwritten(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    review_path = prepare_benchmark_review(paths, tmp_path / "review.yml")
    complete_benchmark_review(review_path)
    approval_path = tmp_path / "generated_approval.yml"
    approval_path.write_text("different: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="human authority was not overwritten"):
        run_analytics_dataset_benchmark_approval(
            paths["manifest"],
            paths["database"],
            paths["semantic"],
            paths["relationships"],
            paths["pack"],
            review_path,
            tmp_path / "approval_evidence",
            approval_path,
            apply=True,
        )
    assert approval_path.read_text(encoding="utf-8") == "different: true\n"
    assert (tmp_path / "approval_evidence").exists() is False


def test_benchmark_review_and_approval_cli_contracts() -> None:
    review = build_parser().parse_args(
        [
            "analytics-dataset-benchmark-review",
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
            "--output",
            "review.yml",
        ]
    )
    approval = build_parser().parse_args(
        [
            "analytics-dataset-benchmark-approval",
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
            "--review",
            "review.yml",
            "--approval-output",
            "approval.yml",
            "--output",
            "evidence",
            "--apply",
        ]
    )

    assert review.command == "analytics-dataset-benchmark-review"
    assert approval.command == "analytics-dataset-benchmark-approval"
    assert approval.apply is True
    assert approval.approval_output == Path("approval.yml")
    assert not hasattr(review, "allow_network")
    assert not hasattr(approval, "replace_existing")


def run_dataset_evaluation(
    paths: dict[str, Path],
    approval_path: Path,
    output_dir: Path,
) -> AnalyticsDatasetBenchmarkEvaluationResult:
    return run_analytics_dataset_benchmark_evaluation(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        approval_path,
        output_dir,
    )


def test_approved_dataset_evaluation_passes_exact_tolerance_and_no_rows_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    add_no_rows_case(paths)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    protected = {
        path: file_sha256(path)
        for path in (
            paths["manifest"],
            paths["database"],
            paths["semantic"],
            paths["relationships"],
            paths["pack"],
            approval_path,
        )
    }
    original_connect = duckdb.connect
    connections: list[bool] = []

    def guarded_connect(*args: object, **kwargs: object) -> duckdb.DuckDBPyConnection:
        connections.append(kwargs.get("read_only") is True)
        assert kwargs.get("read_only") is True
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", guarded_connect)
    output_dir = tmp_path / "evaluation"
    first = run_dataset_evaluation(paths, approval_path, output_dir)
    initial = output_bytes(output_dir)
    second = run_dataset_evaluation(paths, approval_path, output_dir)
    manifest = read_yaml(first.manifest_path)
    cases = list(csv.DictReader(first.cases_path.open(newline="", encoding="utf-8")))
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )

    assert first.status == "passed"
    assert first.case_count == 3
    assert first.passed_count == 3
    assert first.blocker_count == 0
    assert second.outputs_changed is False
    assert initial == output_bytes(output_dir)
    assert connections and all(connections)
    assert {row["comparison_mode"] for row in cases} == {"exact", "numeric_tolerance"}
    assert {row["execution_status"] for row in cases} == {
        "completed",
        "completed_no_rows",
    }
    assert all(row["authority_rechecked"] == "True" for row in cases)
    assert manifest["controls"]["database_mode"] == "read_only"
    assert manifest["metrics"]["numeric_tolerance_accuracy"]["rate"] == 1.0
    assert "Which missing synthetic statuses have orders?" not in persisted
    assert "37.75" not in persisted
    assert "select " not in persisted.lower()
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_invalid_approval_blocks_before_any_database_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval = read_yaml(paths["approval"])
    approval.pop("review_evidence")
    write_yaml(paths["approval"], approval)
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("blocked authority opened DuckDB"),
    )

    result = run_dataset_evaluation(paths, paths["approval"], tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert "invalid_benchmark_review_evidence" in blocker_types(result)


def test_dataset_evaluation_reports_expectation_failure_without_contract_blocker(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    pack = read_yaml(paths["pack"])
    pack["cases"][0]["expected_result"]["rows"] = [[3]]
    pack["cases"][1]["expected_result"]["rows"] = [["37.76"]]
    write_yaml(paths["pack"], pack)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")

    result = run_dataset_evaluation(paths, approval_path, tmp_path / "evaluation")
    cases = {
        row["case_id"]: row
        for row in csv.DictReader(result.cases_path.open(newline="", encoding="utf-8"))
    }

    assert result.status == "failed"
    assert result.blocker_count == 0
    assert result.passed_count == 1
    assert cases["exact_order_count"]["result_match"] == "False"
    assert cases["tolerant_total_amount"]["result_match"] == "True"


def test_dataset_evaluation_rejects_value_outside_reviewed_tolerance(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    pack = read_yaml(paths["pack"])
    pack["cases"][1]["expected_result"]["rows"] = [["37.77"]]
    write_yaml(paths["pack"], pack)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")

    result = run_dataset_evaluation(paths, approval_path, tmp_path / "evaluation")
    cases = {
        row["case_id"]: row
        for row in csv.DictReader(result.cases_path.open(newline="", encoding="utf-8"))
    }

    assert result.status == "failed"
    assert result.blocker_count == 0
    assert cases["exact_order_count"]["result_match"] == "True"
    assert cases["tolerant_total_amount"]["result_match"] == "False"


def test_authority_drift_after_planning_blocks_stage_5b_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    real_hash = dataset_evaluation.file_sha256
    calls = 0

    def drifting_hash(path: Path) -> str:
        nonlocal calls
        calls += 1
        if calls == 7:
            paths["pack"].write_text(
                paths["pack"].read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
        return real_hash(path)

    monkeypatch.setattr(dataset_evaluation, "file_sha256", drifting_hash)
    monkeypatch.setattr(
        dataset_evaluation,
        "run_analytics_query_execution",
        lambda *args, **kwargs: pytest.fail("authority drift reached Stage 5B"),
    )

    result = run_dataset_evaluation(paths, approval_path, tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert "dataset_benchmark_authority_changed_before_query" in blocker_types(result)


def test_different_dataset_evaluation_evidence_is_not_overwritten(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    output_dir = tmp_path / "evaluation"
    first = run_dataset_evaluation(paths, approval_path, output_dir)
    first.report_path.write_text("different\n", encoding="utf-8")
    protected = output_bytes(output_dir)

    with pytest.raises(ValueError, match="existing evidence was not overwritten"):
        run_dataset_evaluation(paths, approval_path, output_dir)

    assert protected == output_bytes(output_dir)


def test_dataset_benchmark_evaluation_cli_has_fixed_offline_boundary() -> None:
    args = build_parser().parse_args(
        [
            "analytics-dataset-benchmark-evaluate",
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

    assert args.command == "analytics-dataset-benchmark-evaluate"
    assert args.approval == Path("approval.yml")
    assert args.output == Path("evidence")
    for name in (
        "provider",
        "allow_network",
        "sql",
        "max_rows",
        "memory_limit_mb",
        "threads",
    ):
        assert not hasattr(args, name)


class FakeLiveProvider:
    name = "ollama:synthetic-test-model"
    mode = "local_live"
    network_access_required = True
    endpoint = "http://127.0.0.1:11434"
    model = "synthetic-test-model"
    context_tokens = 8192
    max_output_tokens = 1024
    prompt_contract_version = "ollama_semantic_intent_v2"

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.last_metrics: dict[str, int | float | None] = {}

    def translate(self, prompt: object, *, timeout_seconds: int) -> dict:
        assert timeout_seconds == 120
        question = prompt.question
        self.calls.append(question)
        self.last_metrics = {
            "request_bytes": 2048,
            "prompt_tokens": 400,
            "completion_tokens": 40,
            "total_duration_ms": 1500.0,
            "load_duration_ms": 100.0,
            "prompt_eval_duration_ms": 900.0,
            "eval_duration_ms": 500.0,
        }
        return self.responses[question]


def fake_live_provider(paths: dict[str, Path]) -> FakeLiveProvider:
    pack = read_yaml(paths["pack"])
    return FakeLiveProvider(
        {case["question"]: case["provider_response"] for case in pack["cases"]}
    )


def live_authorization_payload(
    paths: dict[str, Path],
    approval_path: Path,
    provider: FakeLiveProvider,
) -> dict:
    pack = read_yaml(paths["pack"])
    return {
        "version": 1,
        "status": "approved_live_evaluation",
        "dataset_id": "synthetic_dataset_package",
        "pack_id": "synthetic_dataset_pack_v1",
        "source": {
            "dataset_manifest_sha256": file_sha256(paths["manifest"]),
            "database_sha256": file_sha256(paths["database"]),
            "approved_semantic_state_sha256": file_sha256(paths["semantic"]),
            "approved_relationships_sha256": file_sha256(paths["relationships"]),
            "benchmark_pack_sha256": file_sha256(paths["pack"]),
            "benchmark_approval_sha256": file_sha256(approval_path),
        },
        "provider": {
            "name": provider.name,
            "mode": provider.mode,
            "endpoint": provider.endpoint,
            "model": provider.model,
            "context_tokens": provider.context_tokens,
            "max_output_tokens": provider.max_output_tokens,
            "timeout_seconds": 120,
            "prompt_contract_version": provider.prompt_contract_version,
        },
        "execution": {
            "case_ids": [case["id"] for case in pack["cases"]],
            "max_cases": len(pack["cases"]),
            "sequential": True,
            "expected_request_gate": True,
            "read_only_stage_5b": True,
            "continue_after_case_mismatch": True,
            "alias_normalization": "reviewed_expected_aliases_only_after_non_alias_request_match",
        },
        "decision": live_evaluation.LIVE_DECISIONS,
        "authorized_by": "synthetic-reviewer",
        "authorized_at": "2026-07-15T16:30:00+02:00",
        "notes": "Approved only for the bounded synthetic loopback live evaluation test.",
    }


def prepare_live_authorization(
    paths: dict[str, Path],
    approval_path: Path,
    provider: FakeLiveProvider,
    path: Path,
) -> Path:
    write_yaml(path, live_authorization_payload(paths, approval_path, provider))
    return path


def run_live_evaluation(
    paths: dict[str, Path],
    approval_path: Path,
    authorization_path: Path,
    output_dir: Path,
    provider: FakeLiveProvider,
    *,
    execute: bool,
    allow_network: bool,
    resource_sampler: object = None,
) -> AnalyticsDatasetBenchmarkLiveEvaluationResult:
    return run_analytics_dataset_benchmark_live_evaluation(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        approval_path,
        authorization_path,
        output_dir,
        provider,
        timeout_seconds=120,
        execute=execute,
        allow_network=allow_network,
        resource_sampler=resource_sampler,
    )


def test_live_dataset_evaluation_preflight_is_offline_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("live preflight opened DuckDB"),
    )
    output_dir = tmp_path / "live_preflight"

    first = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        output_dir,
        provider,
        execute=False,
        allow_network=False,
    )
    second = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        output_dir,
        provider,
        execute=False,
        allow_network=False,
    )
    manifest = read_yaml(first.manifest_path)

    assert first.status == "ready_for_live_evaluation"
    assert first.mode == "dry-run"
    assert first.case_count == 0
    assert first.provider_call_count == 0
    assert second.outputs_changed is False
    assert provider.calls == []
    assert manifest["controls"]["network_accessed"] is False
    assert manifest["controls"]["live_provider_used"] is False


def test_live_dataset_evaluation_passes_full_fake_pipeline_with_safe_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    protected = {
        path: file_sha256(path)
        for path in (
            paths["manifest"],
            paths["database"],
            paths["semantic"],
            paths["relationships"],
            paths["pack"],
            approval_path,
            authorization,
        )
    }
    original_connect = duckdb.connect
    connections: list[bool] = []

    def guarded_connect(*args: object, **kwargs: object) -> duckdb.DuckDBPyConnection:
        connections.append(kwargs.get("read_only") is True)
        assert kwargs.get("read_only") is True
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", guarded_connect)
    resource_samples = iter(
        [
            {
                "system_total_memory_mb": 32000.0,
                "system_available_memory_mb": 12000.0,
                "gpu_total_memory_mb": 8192,
                "gpu_used_memory_mb": 1000,
            },
            {
                "system_available_memory_mb": 10000.0,
                "gpu_used_memory_mb": 7000,
            },
            {
                "system_available_memory_mb": 9500.0,
                "gpu_used_memory_mb": 7200,
            },
        ]
    )
    output_dir = tmp_path / "live_evaluation"
    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        output_dir,
        provider,
        execute=True,
        allow_network=True,
        resource_sampler=lambda: next(resource_samples),
    )
    manifest = read_yaml(result.manifest_path)
    cases = list(csv.DictReader(result.cases_path.open(newline="", encoding="utf-8")))
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )

    assert result.status == "passed"
    assert result.case_count == 2
    assert result.passed_count == 2
    assert result.provider_call_count == 2
    assert connections and all(connections)
    assert all(row["semantic_intent_match"] == "True" for row in cases)
    assert all(row["request_match"] == "True" for row in cases)
    assert manifest["metrics"]["overall"]["rate"] == 1.0
    assert manifest["metrics"]["semantic_intent_accuracy"]["rate"] == 1.0
    assert manifest["telemetry"]["tokens"]["total_tokens"] == 880
    assert manifest["telemetry"]["resources"]["maximum_gpu_used_after_case_mb"] == 7200
    assert manifest["telemetry"]["hosted_api_cost_usd"] == 0.0
    assert "How many synthetic orders exist?" not in persisted
    assert "37.75" not in persisted
    assert "select " not in persisted.lower()
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_live_dataset_evaluation_conservatively_records_unexpected_provider_boundary_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    monkeypatch.setattr(
        live_evaluation,
        "run_analytics_query_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )

    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        tmp_path / "live_evaluation",
        provider,
        execute=True,
        allow_network=True,
    )
    manifest = read_yaml(result.manifest_path)
    cases = list(csv.DictReader(result.cases_path.open(newline="", encoding="utf-8")))

    assert result.status == "failed"
    assert result.provider_call_count == 2
    assert all(row["provider_outcome"] == "evaluation_error" for row in cases)
    assert all(row["provider_called"] == "True" for row in cases)
    assert manifest["controls"]["network_accessed"] is True
    assert manifest["telemetry"]["tokens"]["total_tokens"] == 880


def test_live_dataset_evaluation_rejects_preexisting_unknown_output(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    output_dir = tmp_path / "live_evaluation"
    output_dir.mkdir()
    unknown = output_dir / "human-notes.txt"
    unknown.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(ValueError, match="existing evidence was not overwritten"):
        run_live_evaluation(
            paths,
            approval_path,
            authorization,
            output_dir,
            provider,
            execute=False,
            allow_network=False,
        )

    assert unknown.read_text(encoding="utf-8") == "preserve me\n"


def test_live_dataset_output_publish_retries_transient_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "live_evaluation"
    contents = {name: f"{name}\n" for name in live_evaluation.OUTPUT_NAMES}
    original_replace = Path.replace
    attempts = 0
    delays: list[float] = []

    def transient_replace(path: Path, target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("synthetic transient lock")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", transient_replace)
    monkeypatch.setattr(live_evaluation.time, "sleep", delays.append)

    changed = live_evaluation._write_outputs(output_dir, contents)

    assert changed is True
    assert attempts == 2
    assert delays == [live_evaluation.OUTPUT_PUBLISH_RETRY_DELAYS_SECONDS[0]]
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
    } == contents
    assert not list(tmp_path.glob(".live_evaluation.*"))


def test_live_dataset_output_publish_never_overwrites_target_that_appears_during_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "live_evaluation"
    contents = {name: f"{name}\n" for name in live_evaluation.OUTPUT_NAMES}

    def colliding_replace(path: Path, target: Path) -> Path:
        target_path = Path(target)
        target_path.mkdir()
        (target_path / "human-notes.txt").write_text("preserve me\n", encoding="utf-8")
        raise PermissionError("synthetic target race")

    monkeypatch.setattr(Path, "replace", colliding_replace)

    with pytest.raises(ValueError, match="appeared during atomic publication"):
        live_evaluation._write_outputs(output_dir, contents)

    assert (output_dir / "human-notes.txt").read_text(encoding="utf-8") == "preserve me\n"
    assert not list(tmp_path.glob(".live_evaluation.*"))


def test_live_dataset_request_mismatch_fails_without_query_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    pack = read_yaml(paths["pack"])
    provider.responses[pack["cases"][0]["question"]] = pack["cases"][1]["provider_response"]
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    original_plan = live_evaluation.run_analytics_query_plan
    planned_questions: list[str] = []

    def guarded_plan(request_path: Path, *args: object, **kwargs: object):
        request = read_yaml(request_path)
        planned_questions.append(request["question"])
        return original_plan(request_path, *args, **kwargs)

    monkeypatch.setattr(live_evaluation, "run_analytics_query_plan", guarded_plan)
    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        tmp_path / "live_evaluation",
        provider,
        execute=True,
        allow_network=True,
    )
    cases = {
        row["case_id"]: row
        for row in csv.DictReader(result.cases_path.open(newline="", encoding="utf-8"))
    }

    assert result.status == "failed"
    assert result.passed_count == 1
    assert result.provider_call_count == 2
    assert cases["exact_order_count"]["request_match"] == "False"
    assert cases["exact_order_count"]["planning_status"] == "not_run"
    assert cases["tolerant_total_amount"]["passed"] == "True"
    assert planned_questions == ["What is the synthetic total amount?"]


def test_live_dataset_normalizes_alias_only_differences_before_execution(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    pack = read_yaml(paths["pack"])
    first_question = pack["cases"][0]["question"]
    provider.responses[first_question] = deepcopy(provider.responses[first_question])
    provider.responses[first_question]["metrics"][0]["alias"] = "count"
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )

    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        tmp_path / "live_evaluation",
        provider,
        execute=True,
        allow_network=True,
    )
    cases = {
        row["case_id"]: row
        for row in csv.DictReader(result.cases_path.open(newline="", encoding="utf-8"))
    }
    manifest = read_yaml(result.manifest_path)

    assert result.status == "passed"
    assert result.passed_count == 2
    assert cases["exact_order_count"]["semantic_intent_exact_match"] == "False"
    assert cases["exact_order_count"]["semantic_intent_match"] == "True"
    assert cases["exact_order_count"]["request_exact_match"] == "False"
    assert cases["exact_order_count"]["request_match"] == "True"
    assert cases["exact_order_count"]["passed"] == "True"
    assert manifest["metrics"]["request_accuracy"]["rate"] == 1.0
    assert manifest["metrics"]["request_exact_accuracy"]["rate"] == 0.5


def test_live_dataset_case_guard_stops_before_the_next_provider_call(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    guard_results = iter([None, "gpu_temperature_limit_reached"])

    result = run_analytics_dataset_benchmark_live_evaluation(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        approval_path,
        authorization,
        tmp_path / "live_evaluation",
        provider,
        timeout_seconds=120,
        execute=True,
        allow_network=True,
        case_guard=lambda: next(guard_results),
    )
    cases = list(csv.DictReader(result.cases_path.open(newline="", encoding="utf-8")))

    assert result.status == "failed"
    assert result.provider_call_count == 1
    assert cases[0]["passed"] == "True"
    assert cases[1]["provider_outcome"] == "skipped_after_case_guard"


@pytest.mark.parametrize(
    ("mutator", "allow_network", "expected_blocker"),
    [
        (
            lambda payload: payload["provider"].update({"model": "different-model"}),
            True,
            "live_evaluation_provider_mismatch",
        ),
        (
            lambda payload: None,
            False,
            "live_evaluation_network_not_authorized_for_invocation",
        ),
    ],
)
def test_live_dataset_evaluation_blocks_invalid_authority_before_provider_or_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator: object,
    allow_network: bool,
    expected_blocker: str,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = tmp_path / "live_authorization.yml"
    payload = live_authorization_payload(paths, approval_path, provider)
    mutator(payload)
    write_yaml(authorization, payload)
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("blocked live evaluation opened DuckDB"),
    )

    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        tmp_path / "live_evaluation",
        provider,
        execute=True,
        allow_network=allow_network,
    )

    assert result.status == "blocked"
    assert result.provider_call_count == 0
    assert expected_blocker in blocker_types(result)
    assert provider.calls == []


def test_live_dataset_evaluation_rejects_non_loopback_provider_even_when_authorized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    provider.endpoint = "http://192.168.1.10:11434"
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("non-loopback provider opened DuckDB"),
    )

    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        tmp_path / "live_preflight",
        provider,
        execute=False,
        allow_network=False,
    )

    assert result.status == "blocked"
    assert result.provider_call_count == 0
    assert "live_evaluation_provider_not_loopback_ollama" in blocker_types(result)


def test_live_authority_drift_after_provider_blocks_stage_5b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    real_match = live_evaluation._hashes_match
    calls = 0

    def drifting_match(expected: dict[str, str], source_paths: dict[str, Path]) -> bool:
        nonlocal calls
        calls += 1
        return False if calls == 3 else real_match(expected, source_paths)

    monkeypatch.setattr(live_evaluation, "_hashes_match", drifting_match)
    monkeypatch.setattr(
        live_evaluation,
        "run_analytics_query_execution",
        lambda *args, **kwargs: pytest.fail("authority drift reached Stage 5B"),
    )

    result = run_live_evaluation(
        paths,
        approval_path,
        authorization,
        tmp_path / "live_evaluation",
        provider,
        execute=True,
        allow_network=True,
    )

    assert result.status == "blocked"
    assert result.case_count == 0
    assert result.provider_call_count == 0
    assert "dataset_benchmark_authority_changed_before_live_query" in blocker_types(result)


def test_live_dataset_benchmark_cli_requires_separate_execute_and_loopback_flags() -> None:
    args = build_parser().parse_args(
        [
            "analytics-dataset-benchmark-evaluate-ollama",
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
            "--live-authorization",
            "live.yml",
            "--output",
            "evidence",
            "--execute",
            "--allow-network",
        ]
    )

    assert args.command == "analytics-dataset-benchmark-evaluate-ollama"
    assert args.execute is True
    assert args.allow_network is True
    assert args.live_authorization == Path("live.yml")
    for name in ("sql", "max_rows", "memory_limit_mb", "threads", "replace_existing"):
        assert not hasattr(args, name)


def soak_authorization_payload(
    paths: dict[str, Path],
    approval_path: Path,
    live_authorization_path: Path,
    provider: FakeLiveProvider,
    *,
    cooldown_seconds: int = 0,
) -> dict:
    return {
        "version": 1,
        "status": "approved_local_ollama_soak",
        "source": {
            "dataset_manifest_sha256": file_sha256(paths["manifest"]),
            "database_sha256": file_sha256(paths["database"]),
            "approved_semantic_state_sha256": file_sha256(paths["semantic"]),
            "approved_relationships_sha256": file_sha256(paths["relationships"]),
            "benchmark_pack_sha256": file_sha256(paths["pack"]),
            "benchmark_approval_sha256": file_sha256(approval_path),
            "live_authorization_sha256": file_sha256(live_authorization_path),
        },
        "provider": {
            "name": provider.name,
            "mode": provider.mode,
            "endpoint": provider.endpoint,
            "model": provider.model,
            "context_tokens": provider.context_tokens,
            "max_output_tokens": provider.max_output_tokens,
            "timeout_seconds": 120,
            "prompt_contract_version": provider.prompt_contract_version,
        },
        "execution": {
            "duration_seconds": 60,
            "max_cycles": 2,
            "cooldown_seconds": cooldown_seconds,
            "max_consecutive_cycle_errors": 2,
            "provider_concurrency": 1,
            "sequential_cycles": True,
            "stop_file_name": "STOP",
        },
        "resource_limits": {
            "max_gpu_temperature_c": 78,
            "min_available_system_memory_mb": 6144,
            "min_free_disk_mb": 20480,
        },
        "decision": ollama_soak.SOAK_DECISIONS,
        "authorized_by": "synthetic-reviewer",
        "authorized_at": "2026-07-15T17:07:00+02:00",
        "notes": "Approved only for the bounded synthetic local soak test.",
    }


def prepare_soak_fixture(
    tmp_path: Path,
    *,
    cooldown_seconds: int = 0,
) -> tuple[dict[str, Path], Path, Path, Path, FakeLiveProvider]:
    paths = build_fixture(tmp_path)
    approval_path = generate_benchmark_approval(paths, tmp_path / "authority")
    provider = fake_live_provider(paths)
    live_authorization = prepare_live_authorization(
        paths, approval_path, provider, tmp_path / "live_authorization.yml"
    )
    soak_authorization = tmp_path / "soak_authorization.yml"
    write_yaml(
        soak_authorization,
        soak_authorization_payload(
            paths,
            approval_path,
            live_authorization,
            provider,
            cooldown_seconds=cooldown_seconds,
        ),
    )
    return paths, approval_path, live_authorization, soak_authorization, provider


def good_soak_sample() -> dict[str, int | float | str]:
    return {
        "observed_at": "2026-07-15T17:07:00+00:00",
        "system_total_memory_mb": 32000.0,
        "system_available_memory_mb": 12000.0,
        "gpu_total_memory_mb": 8192,
        "gpu_used_memory_mb": 7000,
        "gpu_temperature_c": 65,
        "gpu_utilization_percent": 95,
        "gpu_power_w": 220.0,
        "disk_free_mb": 500000.0,
        "soak_process_working_set_mb": 140.0,
        "soak_process_private_memory_mb": 800.0,
        "ollama_process_count": 2,
        "ollama_process_working_set_mb": 13000.0,
        "ollama_process_private_memory_mb": 15000.0,
    }


def test_ollama_soak_resource_sampler_attributes_process_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ollama_soak,
        "sample_local_resources",
        lambda: {
            "system_total_memory_mb": 32000.0,
            "system_available_memory_mb": 12000.0,
            "gpu_total_memory_mb": 8192,
            "gpu_used_memory_mb": 7000,
        },
    )
    monkeypatch.setattr(
        ollama_soak,
        "_process_memory_samples",
        lambda: {
            "soak_process_working_set_mb": 140.0,
            "soak_process_private_memory_mb": 800.0,
            "ollama_process_count": 2,
            "ollama_process_working_set_mb": 13000.0,
            "ollama_process_private_memory_mb": 15000.0,
        },
    )
    monkeypatch.setattr(
        ollama_soak.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="65, 95, 220\n",
        ),
    )
    monkeypatch.setattr(
        ollama_soak.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=500000 * 1_048_576),
    )

    sample = ollama_soak.sample_ollama_soak_resources(tmp_path / "soak")

    assert sample["soak_process_working_set_mb"] == 140.0
    assert sample["soak_process_private_memory_mb"] == 800.0
    assert sample["ollama_process_count"] == 2
    assert sample["ollama_process_working_set_mb"] == 13000.0
    assert sample["ollama_process_private_memory_mb"] == 15000.0
    assert sample["gpu_temperature_c"] == 65.0
    assert sample["disk_free_mb"] == 500000.0


def test_ollama_soak_checkpoint_publish_retries_transient_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "analytics_ollama_soak.yml"
    original_replace = ollama_soak.os.replace
    attempts = 0
    delays: list[float] = []

    def transient_replace(source: object, target: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("synthetic checkpoint lock")
        original_replace(source, target)

    monkeypatch.setattr(ollama_soak.os, "replace", transient_replace)
    monkeypatch.setattr(ollama_soak.time, "sleep", delays.append)

    ollama_soak._atomic_write(path, "version: 1\n")

    assert attempts == 2
    assert delays == [ollama_soak.CHECKPOINT_PUBLISH_RETRY_DELAYS_SECONDS[0]]
    assert path.read_text(encoding="utf-8") == "version: 1\n"
    assert not list(tmp_path.glob(".analytics_ollama_soak.yml.*.tmp"))


def run_soak_fixture(
    paths: dict[str, Path],
    approval_path: Path,
    live_authorization: Path,
    soak_authorization: Path,
    output_dir: Path,
    provider: FakeLiveProvider,
    *,
    execute: bool,
    allow_network: bool,
    resource_sampler: object = None,
    sleep_fn: object = None,
):
    kwargs = {}
    if resource_sampler is not None:
        kwargs["resource_sampler"] = resource_sampler
    if sleep_fn is not None:
        kwargs["sleep_fn"] = sleep_fn
    return run_analytics_ollama_soak(
        paths["manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        approval_path,
        live_authorization,
        soak_authorization,
        output_dir,
        provider,
        timeout_seconds=120,
        execute=execute,
        allow_network=allow_network,
        **kwargs,
    )


def test_ollama_soak_preflight_is_offline_and_does_not_open_duckdb(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, approval, live_auth, soak_auth, provider = prepare_soak_fixture(tmp_path)
    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: pytest.fail("soak preflight opened DuckDB"),
    )

    result = run_soak_fixture(
        paths,
        approval,
        live_auth,
        soak_auth,
        tmp_path / "soak_preflight",
        provider,
        execute=False,
        allow_network=False,
    )
    manifest = read_yaml(result.manifest_path)

    assert result.status == "ready_for_overnight_soak"
    assert result.provider_call_count == 0
    assert provider.calls == []
    assert manifest["controls"]["provider_concurrency"] == 1
    assert manifest["controls"]["codex_or_hosted_model_api_used_by_runtime"] is False


def test_ollama_soak_runs_two_sequential_cycles_and_aggregates_safe_evidence(
    tmp_path: Path,
) -> None:
    paths, approval, live_auth, soak_auth, provider = prepare_soak_fixture(tmp_path)

    result = run_soak_fixture(
        paths,
        approval,
        live_auth,
        soak_auth,
        tmp_path / "soak",
        provider,
        execute=True,
        allow_network=True,
        resource_sampler=good_soak_sample,
    )
    manifest = read_yaml(result.manifest_path)
    cycles = list(csv.DictReader(result.cycles_path.open(newline="", encoding="utf-8")))
    stability = list(csv.DictReader(result.cases_path.open(newline="", encoding="utf-8")))
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.output_dir.rglob("*")
        if path.is_file()
    )

    assert result.status == "completed"
    assert result.stop_reason == "maximum_cycles_reached"
    assert result.cycle_count == 2
    assert result.provider_call_count == 4
    assert [row["status"] for row in cycles] == ["passed", "passed"]
    assert manifest["counts"]["cases_evaluated"] == 4
    assert manifest["counts"]["prompt_tokens"] == 1600
    assert manifest["counts"]["max_gpu_temperature_c"] == 65
    assert manifest["counts"]["max_soak_process_working_set_mb"] == 140.0
    assert manifest["counts"]["max_ollama_process_working_set_mb"] == 13000.0
    assert manifest["counts"]["max_ollama_process_private_memory_mb"] == 15000.0
    assert len(stability) == 2
    assert all(row["observations"] == "2" for row in stability)
    assert all(row["passed"] == "2" for row in stability)
    assert "How many synthetic orders exist?" not in persisted
    assert "select " not in persisted.lower()


def test_ollama_soak_resource_guard_stops_before_provider(
    tmp_path: Path,
) -> None:
    paths, approval, live_auth, soak_auth, provider = prepare_soak_fixture(tmp_path)

    def hot_sample() -> dict[str, int | float | str]:
        return {**good_soak_sample(), "gpu_temperature_c": 79}

    result = run_soak_fixture(
        paths,
        approval,
        live_auth,
        soak_auth,
        tmp_path / "soak",
        provider,
        execute=True,
        allow_network=True,
        resource_sampler=hot_sample,
    )

    assert result.status == "stopped_resource_guard"
    assert result.stop_reason == "gpu_temperature_limit_reached"
    assert result.cycle_count == 0
    assert result.provider_call_count == 0
    assert provider.calls == []


def test_ollama_soak_stop_file_is_checked_during_cooldown(tmp_path: Path) -> None:
    paths, approval, live_auth, soak_auth, provider = prepare_soak_fixture(
        tmp_path, cooldown_seconds=5
    )
    output_dir = tmp_path / "soak"

    def request_stop(_: float) -> None:
        (output_dir / "STOP").touch()

    result = run_soak_fixture(
        paths,
        approval,
        live_auth,
        soak_auth,
        output_dir,
        provider,
        execute=True,
        allow_network=True,
        resource_sampler=good_soak_sample,
        sleep_fn=request_stop,
    )

    assert result.status == "stopped_by_request"
    assert result.stop_reason == "stop_file_detected"
    assert result.cycle_count == 1
    assert result.provider_call_count == 2


def test_ollama_soak_rejects_scope_drift_before_provider(
    tmp_path: Path,
) -> None:
    paths, approval, live_auth, soak_auth, provider = prepare_soak_fixture(tmp_path)
    payload = read_yaml(soak_auth)
    payload["execution"]["provider_concurrency"] = 2
    write_yaml(soak_auth, payload)

    result = run_soak_fixture(
        paths,
        approval,
        live_auth,
        soak_auth,
        tmp_path / "soak",
        provider,
        execute=True,
        allow_network=True,
        resource_sampler=good_soak_sample,
    )
    manifest = read_yaml(result.manifest_path)
    blocker_types = {row["blocker_type"] for row in manifest["contract_blockers"]}

    assert result.status == "blocked"
    assert result.provider_call_count == 0
    assert "ollama_soak_parallel_or_stop_policy_invalid" in blocker_types
    assert provider.calls == []


def test_ollama_soak_cli_has_no_parallelism_or_resource_bypass_flags() -> None:
    args = build_parser().parse_args(
        [
            "analytics-ollama-soak",
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
            "--live-authorization",
            "live.yml",
            "--soak-authorization",
            "soak.yml",
            "--output",
            "evidence",
            "--execute",
            "--allow-network",
        ]
    )

    assert args.command == "analytics-ollama-soak"
    assert args.execute is True
    assert args.allow_network is True
    for name in (
        "provider_concurrency",
        "duration_seconds",
        "max_gpu_temperature_c",
        "min_available_system_memory_mb",
        "replace_existing",
    ):
        assert not hasattr(args, name)
