from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from data_ops_lab.analytics_semantic_approval import run_analytics_semantic_approval
from data_ops_lab.analytics_semantic_review import run_analytics_semantic_review
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def compiled_catalog() -> dict[str, object]:
    sales_table = {"kind": "table", "id": "sales_orders", "name": "Sales"}
    sales_measure = {"kind": "measure", "id": "total_amount", "name": "Total Sales"}
    return {
        "version": 1,
        "status": "ready_for_semantic_review",
        "source": {
            "semantic_catalog_sha256": "candidate-hash",
            "relationships_sha256": "relationships-hash",
            "catalog_sha256": "physical-catalog-hash",
            "database_size_bytes": 1,
            "database_modified_ns": 2,
        },
        "dataset": {
            "id": "sales_dataset",
            "name": "Sales Dataset",
            "description": "Synthetic sales data.",
            "synonyms": [],
        },
        "catalog": {
            "physical_tables": 2,
            "physical_columns": 4,
            "semantic_tables": 2,
            "dimensions": 1,
            "measures": 1,
            "relationship_paths": 1,
            "terms": 2,
            "ambiguities": 1,
        },
        "tables": [
            {
                "id": "sales_orders",
                "source_table": "orders",
                "name": "Sales",
                "description": "",
                "synonyms": [],
            },
            {
                "id": "customers",
                "source_table": "customers",
                "name": "Customers",
                "description": "",
                "synonyms": [],
            },
        ],
        "dimensions": [
            {
                "id": "customer",
                "table_id": "customers",
                "source_table": "customers",
                "source_column": "name",
                "source_type": "VARCHAR",
                "name": "Customer",
                "description": "",
                "synonyms": [],
            }
        ],
        "measures": [
            {
                "id": "total_amount",
                "table_id": "sales_orders",
                "source_table": "orders",
                "source_column": "amount",
                "source_type": "DECIMAL(12,2)",
                "function": "sum",
                "name": "Total Sales",
                "description": "",
                "synonyms": ["sales"],
            }
        ],
        "relationship_paths": [
            {
                "id": "sales_to_customers",
                "name": "Sales Customers",
                "description": "",
                "synonyms": [],
                "hops": [
                    {
                        "source_table_id": "sales_orders",
                        "source_table": "orders",
                        "source_column": "customer_id",
                        "target_table_id": "customers",
                        "target_table": "customers",
                        "target_column": "id",
                        "kind": "left",
                    }
                ],
            }
        ],
        "term_index": [
            {
                "term": "customer",
                "status": "resolved",
                "candidate_count": 1,
                "ambiguity_score": 0.0,
                "requires_clarification": False,
                "targets": [{"kind": "dimension", "id": "customer", "name": "Customer"}],
            },
            {
                "term": "sales",
                "status": "ambiguous",
                "candidate_count": 2,
                "ambiguity_score": 0.5,
                "requires_clarification": True,
                "targets": [sales_measure, sales_table],
            },
        ],
        "ambiguities": ["sales"],
        "approval": {
            "semantic_definitions_approved": False,
            "adapter_use_authorized": False,
            "candidate_relationships_accepted": False,
            "requires_human_semantic_review": True,
        },
        "blockers": [],
    }


def build_review(tmp_path: Path) -> tuple[Path, Path, Path]:
    catalog_path = tmp_path / "compiled.yml"
    review_path = tmp_path / "review.yml"
    write_yaml(catalog_path, compiled_catalog())
    result = run_analytics_semantic_review(catalog_path, review_path)
    assert result.entity_count == 6
    assert result.ambiguity_count == 1
    return catalog_path, review_path, tmp_path / "config"


def complete_review(review_path: Path, *, ambiguity_decision: str = "requires_clarification") -> dict:
    review = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    review["status"] = "completed_human_review"
    review["review"]["reviewer"] = "synthetic-reviewer"
    review["review"]["reviewed_at"] = "2026-07-14T12:00:00+00:00"
    for row in review["review"]["entity_decisions"]:
        row["decision"] = "approved"
        row["notes"] = "Validated against the synthetic business definition."
    ambiguity = review["review"]["ambiguity_decisions"][0]
    ambiguity["decision"] = ambiguity_decision
    ambiguity["notes"] = "The user must clarify this term."
    if ambiguity_decision == "approved_target":
        ambiguity["selected_target"] = ambiguity["candidate_targets"][0]
    write_yaml(review_path, review)
    return review


def blocker_types(path: Path) -> set[str]:
    rows = path.read_text(encoding="utf-8").splitlines()[1:]
    return {row.split(",", 3)[1] for row in rows if row}


def test_review_template_is_hash_bound_pending_and_non_overwriting(tmp_path: Path) -> None:
    catalog_path, review_path, _ = build_review(tmp_path)
    initial = review_path.read_bytes()
    second = run_analytics_semantic_review(catalog_path, review_path)
    review = yaml.safe_load(review_path.read_text(encoding="utf-8"))

    assert second.output_changed is False
    assert review_path.read_bytes() == initial
    assert review["status"] == "pending_human_review"
    assert review["source"]["semantic_catalog_sha256"] == file_sha256(catalog_path)
    assert {row["decision"] for row in review["review"]["entity_decisions"]} == {"pending"}

    review["review"]["reviewer"] = "human"
    write_yaml(review_path, review)
    with pytest.raises(ValueError, match="human review evidence was not overwritten"):
        run_analytics_semantic_review(catalog_path, review_path)


def test_pending_review_produces_blocked_dry_run_without_state(tmp_path: Path) -> None:
    catalog_path, review_path, config_dir = build_review(tmp_path)
    result = run_analytics_semantic_approval(
        catalog_path, review_path, tmp_path / "approval", config_dir
    )

    assert result.status == "blocked"
    assert result.dry_run is True
    assert result.state_path.exists() is False
    assert {
        "review_not_completed",
        "missing_reviewer",
        "invalid_reviewed_at",
        "pending_entity_decision",
        "missing_decision_notes",
        "pending_ambiguity_decision",
        "missing_ambiguity_notes",
    } <= blocker_types(result.blockers_path)


def test_completed_review_dry_run_is_ready_without_writing_state(tmp_path: Path) -> None:
    catalog_path, review_path, config_dir = build_review(tmp_path)
    complete_review(review_path)
    result = run_analytics_semantic_approval(
        catalog_path, review_path, tmp_path / "approval", config_dir
    )
    plan = yaml.safe_load(result.plan_path.read_text(encoding="utf-8"))

    assert result.status == "ready_for_apply"
    assert result.blocker_count == 0
    assert result.state_path.exists() is False
    assert plan["proposed_state"]["approval"]["adapter_use_authorized"] is True
    assert plan["proposed_state"]["ambiguities"] == ["sales"]
    assert "Validated against" not in result.plan_path.read_text(encoding="utf-8")


def test_apply_writes_idempotent_approved_state_and_preserves_inputs(tmp_path: Path) -> None:
    catalog_path, review_path, config_dir = build_review(tmp_path)
    complete_review(review_path, ambiguity_decision="approved_target")
    protected = {catalog_path: file_sha256(catalog_path), review_path: file_sha256(review_path)}
    output_dir = tmp_path / "apply"

    first = run_analytics_semantic_approval(
        catalog_path, review_path, output_dir, config_dir, apply=True
    )
    second = run_analytics_semantic_approval(
        catalog_path, review_path, output_dir, config_dir, apply=True
    )
    state = yaml.safe_load(first.state_path.read_text(encoding="utf-8"))
    sales = next(row for row in state["term_index"] if row["term"] == "sales")

    assert first.state_changed is True
    assert second.state_changed is False
    assert second.outputs_changed is False
    assert state["status"] == "approved"
    assert state["approval"]["semantic_definitions_approved"] is True
    assert state["approval"]["candidate_relationships_accepted"] is False
    assert state["approval"]["requires_clarification"] is False
    assert sales["status"] == "resolved"
    assert sales["resolution_authority"] == "human_approval"
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_catalog_drift_and_invalid_ambiguity_target_block_apply(tmp_path: Path) -> None:
    catalog_path, review_path, config_dir = build_review(tmp_path)
    review = complete_review(review_path, ambiguity_decision="approved_target")
    review["review"]["ambiguity_decisions"][0]["selected_target"] = {
        "kind": "measure",
        "id": "invented",
        "name": "Invented",
    }
    review["source"]["semantic_catalog_sha256"] = "stale"
    write_yaml(review_path, review)
    result = run_analytics_semantic_approval(
        catalog_path, review_path, tmp_path / "blocked", config_dir, apply=True
    )

    assert result.status == "blocked"
    assert result.state_path.exists() is False
    assert {"semantic_catalog_drift", "invalid_selected_target"} <= blocker_types(result.blockers_path)


def test_rejected_or_missing_entity_decisions_block_apply(tmp_path: Path) -> None:
    catalog_path, review_path, config_dir = build_review(tmp_path)
    review = complete_review(review_path)
    review["review"]["entity_decisions"][0]["decision"] = "rejected"
    review["review"]["entity_decisions"].pop()
    write_yaml(review_path, review)
    result = run_analytics_semantic_approval(
        catalog_path, review_path, tmp_path / "blocked", config_dir, apply=True
    )

    assert result.state_path.exists() is False
    assert {"rejected_semantic_entity", "missing_entity_decision"} <= blocker_types(result.blockers_path)


def test_different_existing_state_requires_explicit_replacement(tmp_path: Path) -> None:
    catalog_path, review_path, config_dir = build_review(tmp_path)
    complete_review(review_path)
    first = run_analytics_semantic_approval(
        catalog_path, review_path, tmp_path / "first", config_dir, apply=True
    )
    original = first.state_path.read_bytes()

    review = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    review["review"]["entity_decisions"][0]["notes"] = "Updated approval evidence."
    write_yaml(review_path, review)
    with pytest.raises(ValueError, match="different approved semantic state"):
        run_analytics_semantic_approval(
            catalog_path, review_path, tmp_path / "second", config_dir, apply=True
        )
    assert first.state_path.read_bytes() == original

    replaced = run_analytics_semantic_approval(
        catalog_path,
        review_path,
        tmp_path / "replacement",
        config_dir,
        apply=True,
        replace_existing=True,
    )
    assert replaced.state_changed is True
    assert len(list((config_dir / "history").glob("approved_semantic_catalog_*.yml"))) == 1


def test_semantic_review_and_approval_cli_contracts() -> None:
    review = build_parser().parse_args(
        ["analytics-semantic-review", "--catalog", "compiled.yml", "--output", "review.yml"]
    )
    approval = build_parser().parse_args(
        [
            "analytics-semantic-approval",
            "--catalog",
            "compiled.yml",
            "--review",
            "review.yml",
            "--output",
            "approval",
            "--config",
            "config/analytics",
            "--apply",
            "--replace-existing",
        ]
    )

    assert review.command == "analytics-semantic-review"
    assert review.catalog == Path("compiled.yml")
    assert approval.command == "analytics-semantic-approval"
    assert approval.apply is True
    assert approval.replace_existing is True
