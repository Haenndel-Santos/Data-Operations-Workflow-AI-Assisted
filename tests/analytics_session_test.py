from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import duckdb
import pytest
import yaml

from data_ops_lab.analytics_session import (
    run_analytics_session_prepare,
    run_analytics_session_resume,
)
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def resolved_term(term: str, kind: str, semantic_id: str, name: str) -> dict[str, Any]:
    return {
        "term": term,
        "status": "resolved",
        "candidate_count": 1,
        "ambiguity_score": 0.0,
        "requires_clarification": False,
        "targets": [{"kind": kind, "id": semantic_id, "name": name}],
    }


def approved_state() -> dict[str, Any]:
    return {
        "version": 1,
        "status": "approved",
        "source": {
            "compiled_semantic_catalog_sha256": "compiled-hash",
            "candidate_semantic_catalog_sha256": "candidate-hash",
            "relationships_sha256": "relationships-hash",
            "physical_catalog_sha256": "physical-hash",
            "review_sha256": "review-hash",
            "decision_digest": "decision-hash",
        },
        "approval": {
            "semantic_definitions_approved": True,
            "adapter_use_authorized": True,
            "candidate_relationships_accepted": False,
            "approved_by": "synthetic-reviewer",
            "approved_at": "2026-07-14T12:00:00+00:00",
            "requires_clarification": True,
        },
        "dataset": {
            "id": "sales_dataset",
            "name": "Sales Dataset",
            "description": "Synthetic metadata.",
            "synonyms": [],
        },
        "catalog": {},
        "tables": [
            {
                "id": "sales_orders",
                "source_table": "physical_orders_private",
                "name": "Sales Orders",
                "description": "Commercial documents.",
                "synonyms": ["orders"],
            }
        ],
        "dimensions": [
            {
                "id": "order_status",
                "table_id": "sales_orders",
                "source_table": "physical_orders_private",
                "source_column": "private_status_column",
                "source_type": "VARCHAR",
                "name": "Order Status",
                "description": "Current business status.",
                "synonyms": ["status"],
            }
        ],
        "measures": [
            {
                "id": "order_count",
                "table_id": "sales_orders",
                "source_table": "physical_orders_private",
                "source_column": "*",
                "source_type": "ROW_COUNT",
                "function": "count",
                "name": "Order Count",
                "description": "Number of orders.",
                "synonyms": ["orders count"],
            }
        ],
        "relationship_paths": [],
        "term_index": [
            resolved_term("order count", "measure", "order_count", "Order Count"),
            resolved_term("order status", "dimension", "order_status", "Order Status"),
            resolved_term("sales orders", "table", "sales_orders", "Sales Orders"),
            {
                "term": "sales",
                "status": "ambiguous",
                "candidate_count": 2,
                "ambiguity_score": 0.5,
                "requires_clarification": True,
                "targets": [
                    {"kind": "table", "id": "sales_orders", "name": "Sales Orders"},
                    {"kind": "measure", "id": "order_count", "name": "Order Count"},
                ],
            },
        ],
        "ambiguities": ["sales"],
        "ambiguity_decisions": [
            {"term": "sales", "decision": "requires_clarification", "selected_target": None}
        ],
        "entity_decisions": [],
    }


def translation_response() -> dict[str, Any]:
    return {
        "version": 1,
        "from": "sales orders",
        "relationship_paths": [],
        "dimensions": [{"term": "order status", "alias": "status"}],
        "metrics": [{"term": "order count", "alias": "orders"}],
        "filters": [{"term": "order status", "operator": "eq", "value": "open"}],
        "order_by": [{"field": "orders", "direction": "desc"}],
        "limit": 20,
    }


def narration_response(*, valid: bool = True) -> dict[str, Any]:
    return {
        "version": 1,
        "headline": "Open order result",
        "claims": [
            {
                "text": "The result contains 1 row and the no-row control is false.",
                "citations": ["result.row_count", "result.no_rows"],
            },
            {
                "text": "The bounded preview is not truncated.",
                "citations": ["control.preview_truncated"],
            },
            {
                "text": f"There are {'2' if valid else '3'} open orders.",
                "citations": ["cell.r001.c001", "cell.r001.c002"],
            },
        ],
    }


def build_fixture(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths = {
        "question": tmp_path / "question.txt",
        "semantic": tmp_path / "semantic.yml",
        "translation_response": tmp_path / "translation_response.yml",
        "database": tmp_path / "analytics.duckdb",
        "relationships": tmp_path / "relationships.yml",
        "prepare": tmp_path / "prepare",
        "resume": tmp_path / "resume",
        "narration_response": tmp_path / "narration_response.yml",
        "review": tmp_path / "completed_review.yml",
    }
    paths["question"].write_text("PRIVATE QUESTION: How many open orders exist?\n", encoding="utf-8")
    write_yaml(paths["semantic"], approved_state())
    write_yaml(paths["translation_response"], translation_response())
    write_yaml(paths["relationships"], {"approved_relationships": []})
    write_yaml(paths["narration_response"], narration_response())
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute(
            "create table physical_orders_private(private_status_column varchar)"
        )
        connection.execute("insert into physical_orders_private values ('open'), ('open'), ('closed')")
    return paths


def prepare(paths: dict[str, Path]):
    return run_analytics_session_prepare(
        paths["question"],
        paths["semantic"],
        paths["translation_response"],
        paths["database"],
        paths["relationships"],
        paths["prepare"],
    )


def complete_review(paths: dict[str, Path], prepared) -> None:
    review = yaml.safe_load(prepared.review_template_path.read_text(encoding="utf-8"))
    review["status"] = "completed"
    review["review"] = {
        "decision": "approved",
        "reviewed_by": "synthetic-human-reviewer",
        "reviewed_at": "2026-07-14T14:00:00+00:00",
        "notes": "Synthetic plan reviewed for offline contract testing.",
    }
    write_yaml(paths["review"], review)


def resume(paths: dict[str, Path], prepared):
    return run_analytics_session_resume(
        prepared.manifest_path,
        paths["review"],
        paths["database"],
        paths["relationships"],
        paths["narration_response"],
        paths["resume"],
    )


def blocker_types(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def test_prepare_stops_for_exact_review_is_private_and_idempotent(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    protected = {path: file_sha256(path) for path in paths.values() if path.is_file()}

    first = prepare(paths)
    second = prepare(paths)

    assert first.status == "awaiting_execution_review"
    assert first.review_template_path is not None
    assert first.plan_result.status == "ready_for_execution_review"
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert not (paths["prepare"] / "query_execution").exists()
    assert all(file_sha256(path) == digest for path, digest in protected.items())
    manifest = first.manifest_path.read_text(encoding="utf-8")
    assert "PRIVATE QUESTION" not in manifest
    assert "open" not in manifest
    review = yaml.safe_load(first.review_template_path.read_text(encoding="utf-8"))
    assert review["status"] == "pending_review"
    assert review["review"]["decision"] == "pending"


def test_prepare_preserves_clarification_without_query_plan(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    response = translation_response()
    response["metrics"] = [{"term": "sales", "alias": "sales"}]
    response["order_by"] = [{"field": "sales", "direction": "desc"}]
    write_yaml(paths["translation_response"], response)

    result = prepare(paths)

    assert result.status == "clarification_required"
    assert result.plan_result is None
    assert result.review_template_path is None
    assert not (paths["prepare"] / "query_plan").exists()


def test_resume_blocks_pending_review_before_execution(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    prepared = prepare(paths)
    paths["review"].write_bytes(prepared.review_template_path.read_bytes())

    result = resume(paths, prepared)

    assert result.status == "blocked"
    assert result.execution_result is None
    assert result.last_valid_checkpoint == "prepare"
    assert "execution_review_incomplete" in blocker_types(result.blockers_path)
    assert not (paths["resume"] / "query_execution").exists()


def test_reviewed_resume_completes_all_stages_and_is_idempotent(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    prepared = prepare(paths)
    complete_review(paths, prepared)
    protected = {
        path: file_sha256(path)
        for path in (
            paths["database"],
            paths["relationships"],
            paths["review"],
            prepared.manifest_path,
        )
    }

    first = resume(paths, prepared)
    second = resume(paths, prepared)

    assert first.status == "completed"
    assert first.last_valid_checkpoint == "result_narration"
    assert first.execution_result.status == "completed"
    assert first.presentation_result.status == "ready_for_recorded_narration"
    assert first.narration_result.status == "ready_for_user"
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert all(file_sha256(path) == digest for path, digest in protected.items())
    assert first.execution_result.result_path.read_text(encoding="utf-8") == "status,orders\nopen,2\n"
    manifest = first.manifest_path.read_text(encoding="utf-8")
    assert "PRIVATE QUESTION" not in manifest and "open,2" not in manifest


def test_resume_rejects_plan_review_mismatch_and_source_drift(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    prepared = prepare(paths)
    complete_review(paths, prepared)
    review = yaml.safe_load(paths["review"].read_text(encoding="utf-8"))
    review["source"]["reviewed_plan_sha256"] = "0" * 64
    write_yaml(paths["review"], review)

    mismatch = resume(paths, prepared)

    assert mismatch.execution_result is None
    assert "reviewed_plan_hash_mismatch" in blocker_types(mismatch.blockers_path)

    drift_paths = build_fixture(tmp_path / "drift")
    drift_prepared = prepare(drift_paths)
    complete_review(drift_paths, drift_prepared)
    write_yaml(drift_paths["relationships"], {"approved_relationships": [], "changed": True})
    drift = resume(drift_paths, drift_prepared)
    assert drift.execution_result is None
    assert "relationships_changed_after_prepare" in blocker_types(drift.blockers_path)


def test_invalid_narration_preserves_result_presentation_checkpoint(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    prepared = prepare(paths)
    complete_review(paths, prepared)
    write_yaml(paths["narration_response"], narration_response(valid=False))

    result = resume(paths, prepared)

    assert result.status == "blocked"
    assert result.last_valid_checkpoint == "result_presentation"
    assert result.execution_result.status == "completed"
    assert result.presentation_result.status == "ready_for_recorded_narration"
    assert result.narration_result.status == "blocked"
    assert "result_narration_blocked" in blocker_types(result.blockers_path)


def test_changed_review_is_rejected_before_dependent_stages_in_existing_output(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    prepared = prepare(paths)
    paths["review"].write_bytes(prepared.review_template_path.read_bytes())
    blocked = resume(paths, prepared)
    assert blocked.execution_result is None
    complete_review(paths, prepared)

    with pytest.raises(ValueError, match="no dependent stage was started"):
        resume(paths, prepared)

    assert not (paths["resume"] / "query_execution").exists()


def test_session_cli_exposes_no_review_bypass_or_network_flag() -> None:
    parser = build_parser()
    prepare_args = parser.parse_args(
        [
            "analytics-session-prepare-recorded",
            "--question-file", "question.txt",
            "--semantic-state", "semantic.yml",
            "--translation-response", "translation.yml",
            "--database", "data.duckdb",
            "--relationships", "relationships.yml",
        ]
    )
    resume_args = parser.parse_args(
        [
            "analytics-session-resume-recorded",
            "--prepare-manifest", "prepare.yml",
            "--review", "review.yml",
            "--database", "data.duckdb",
            "--relationships", "relationships.yml",
            "--narration-response", "narration.yml",
        ]
    )

    assert prepare_args.command == "analytics-session-prepare-recorded"
    assert resume_args.command == "analytics-session-resume-recorded"
    assert not hasattr(prepare_args, "execute")
    assert not hasattr(resume_args, "allow_network")
