from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import yaml

from data_ops_lab.analytics_dataset_benchmark import (
    inspect_analytics_dataset_benchmark_candidate,
)
from data_ops_lab.analytics_dataset_benchmark_materialization import (
    run_analytics_dataset_benchmark_materialization,
)
from data_ops_lab.analytics_dataset_benchmark_preparation import (
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
        "preparation": tmp_path / "preparation",
        "review": tmp_path / "completed_execution_review.yml",
        "pack": tmp_path / "candidate_pack.yml",
        "output": tmp_path / "materialization",
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
                "approved_relationships_sha256": file_sha256(
                    paths["relationships"]
                ),
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
                "approved_relationships_sha256": file_sha256(
                    paths["relationships"]
                ),
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


def prepare_and_complete_review(paths: dict[str, Path]) -> Path:
    preparation = run_analytics_dataset_benchmark_preparation(
        paths["design"],
        paths["dataset_manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["preparation"],
    )
    assert preparation.review_path is not None
    review = read_yaml(preparation.review_path)
    review["status"] = "completed_human_review"
    review["review"]["reviewer"] = "pytest_owner"
    review["review"]["reviewed_at"] = "2026-07-15T12:00:00+00:00"
    for row in review["review"]["scope_decisions"]:
        row["decision"] = (
            "approved"
            if row["scope"] == "local_read_only_answer_collection"
            else "not_authorized"
        )
        row["notes"] = "Explicit bounded pytest decision."
    for row in review["review"]["case_decisions"]:
        row["decision"] = "approved"
        row["notes"] = "Exact plan approved for local read-only pytest collection."
    write_yaml(paths["review"], review)
    return preparation.manifest_path


def materialize(paths: dict[str, Path], preparation_manifest: Path):
    return run_analytics_dataset_benchmark_materialization(
        paths["design"],
        paths["dataset_manifest"],
        preparation_manifest,
        paths["review"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
        paths["output"],
    )


def test_approved_plans_materialize_candidate_pack_read_only_and_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    preparation_manifest = prepare_and_complete_review(paths)
    protected = {
        path: file_sha256(path)
        for path in (
            paths["design"],
            paths["dataset_manifest"],
            paths["database"],
            paths["semantic"],
            paths["relationships"],
            paths["review"],
            preparation_manifest,
        )
    }
    original_connect = duckdb.connect
    connections: list[bool] = []

    def guarded_connect(*args: object, **kwargs: object):
        connections.append(kwargs.get("read_only") is True)
        assert kwargs.get("read_only") is True
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(
        "data_ops_lab.analytics_query_execution.duckdb.connect", guarded_connect
    )
    first = materialize(paths, preparation_manifest)
    second = materialize(paths, preparation_manifest)

    pack = read_yaml(paths["pack"])
    candidate = inspect_analytics_dataset_benchmark_candidate(
        paths["dataset_manifest"],
        paths["database"],
        paths["semantic"],
        paths["relationships"],
        paths["pack"],
    )
    assert first.status == "awaiting_final_review"
    assert first.completed_count == 1
    assert first.blocker_count == 0
    assert first.pack_changed is True
    assert second.outputs_changed is False
    assert second.pack_changed is False
    assert connections == [True, True]
    assert pack["status"] == "candidate_for_review"
    assert pack["cases"][0]["expected_result"]["rows"] == [[2]]
    assert not candidate.blockers
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_unapproved_scope_blocks_before_stage_5b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    preparation_manifest = prepare_and_complete_review(paths)
    review = read_yaml(paths["review"])
    live = next(
        row
        for row in review["review"]["scope_decisions"]
        if row["scope"] == "live_provider_use"
    )
    live["decision"] = "approved"
    write_yaml(paths["review"], review)
    monkeypatch.setattr(
        "data_ops_lab.analytics_dataset_benchmark_materialization.run_analytics_query_execution",
        lambda *args, **kwargs: pytest.fail("unapproved scope reached Stage 5B"),
    )

    result = materialize(paths, preparation_manifest)

    assert result.status == "blocked"
    assert result.pack_path is None
    assert "answer_collection_scope_expansion_not_allowed" in result.blockers_path.read_text(
        encoding="utf-8"
    )


def test_prepared_plan_drift_blocks_before_stage_5b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_fixture(tmp_path)
    preparation_manifest = prepare_and_complete_review(paths)
    preparation = read_yaml(preparation_manifest)
    plan_path = preparation_manifest.parent / preparation["cases"][0]["plan_path"]
    plan_path.write_text("different: plan\n", encoding="utf-8")
    monkeypatch.setattr(
        "data_ops_lab.analytics_dataset_benchmark_materialization.run_analytics_query_execution",
        lambda *args, **kwargs: pytest.fail("drifted plan reached Stage 5B"),
    )

    result = materialize(paths, preparation_manifest)

    assert result.status == "blocked"
    assert result.pack_path is None
    assert "benchmark_preparation_artifact_drift" in result.blockers_path.read_text(
        encoding="utf-8"
    )


def test_materialization_cli_has_no_network_or_limit_bypass() -> None:
    args = build_parser().parse_args(
        [
            "analytics-dataset-benchmark-answer-materialize",
            "--design",
            "design.yml",
            "--dataset-manifest",
            "dataset.yml",
            "--preparation-manifest",
            "preparation.yml",
            "--execution-review",
            "execution-review.yml",
            "--database",
            "dataset.duckdb",
            "--semantic-state",
            "semantic.yml",
            "--relationships",
            "relationships.yml",
            "--pack-output",
            "candidate-pack.yml",
            "--output",
            "materialization",
        ]
    )

    assert args.command == "analytics-dataset-benchmark-answer-materialize"
    assert args.pack_output == Path("candidate-pack.yml")
    assert not hasattr(args, "allow_network")
    assert not hasattr(args, "threads")
    assert not hasattr(args, "apply")


def test_tampered_materialization_evidence_is_not_reused(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    preparation_manifest = prepare_and_complete_review(paths)
    first = materialize(paths, preparation_manifest)
    first.cases_path.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="evidence integrity failed"):
        materialize(paths, preparation_manifest)

    assert first.cases_path.read_text(encoding="utf-8") == "tampered\n"


def test_exact_existing_pack_can_receive_new_evidence_run(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    preparation_manifest = prepare_and_complete_review(paths)
    first = materialize(paths, preparation_manifest)
    paths["output"] = tmp_path / "materialization_v2"

    second = materialize(paths, preparation_manifest)

    assert first.pack_changed is True
    assert second.status == "awaiting_final_review"
    assert second.outputs_changed is True
    assert second.pack_changed is False
