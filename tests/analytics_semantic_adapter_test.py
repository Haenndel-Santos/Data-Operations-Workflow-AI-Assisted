from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import pytest
import yaml

from data_ops_lab.analytics_query_plan import run_analytics_query_plan
from data_ops_lab.analytics_semantic_adapter import run_analytics_semantic_adapter
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def target(kind: str, semantic_id: str, name: str) -> dict[str, str]:
    return {"kind": kind, "id": semantic_id, "name": name}


def term(term_value: str, target_value: dict[str, str]) -> dict[str, object]:
    return {
        "term": term_value,
        "status": "resolved",
        "candidate_count": 1,
        "ambiguity_score": 0.0,
        "requires_clarification": False,
        "targets": [target_value],
    }


def approved_state() -> dict[str, object]:
    orders_target = target("table", "sales_orders", "Sales Orders")
    total_target = target("measure", "total_amount", "Total Sales")
    return {
        "version": 1,
        "status": "approved",
        "source": {
            "compiled_semantic_catalog_sha256": "compiled-hash",
            "candidate_semantic_catalog_sha256": "candidate-hash",
            "relationships_sha256": "relationships-hash",
            "physical_catalog_sha256": "catalog-hash",
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
            "description": "Synthetic metadata only.",
            "synonyms": [],
        },
        "catalog": {
            "physical_tables": 2,
            "physical_columns": 6,
            "semantic_tables": 2,
            "dimensions": 2,
            "measures": 2,
            "relationship_paths": 1,
            "terms": 8,
            "ambiguities": 1,
        },
        "tables": [
            {
                "id": "sales_orders",
                "source_table": "orders",
                "name": "Sales Orders",
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
            },
            {
                "id": "order_status",
                "table_id": "sales_orders",
                "source_table": "orders",
                "source_column": "status",
                "source_type": "VARCHAR",
                "name": "Order Status",
                "description": "",
                "synonyms": [],
            },
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
            },
            {
                "id": "order_count",
                "table_id": "sales_orders",
                "source_table": "orders",
                "source_column": "*",
                "source_type": "ROW_COUNT",
                "function": "count",
                "name": "Order Count",
                "description": "",
                "synonyms": [],
            },
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
            term("customer", target("dimension", "customer", "Customer")),
            term("customers", target("table", "customers", "Customers")),
            term("order count", target("measure", "order_count", "Order Count")),
            term("order status", target("dimension", "order_status", "Order Status")),
            term("sales customers", target("relationship_path", "sales_to_customers", "Sales Customers")),
            term("sales dataset", target("dataset", "sales_dataset", "Sales Dataset")),
            term("sales orders", orders_target),
            {
                "term": "sales",
                "status": "ambiguous",
                "candidate_count": 2,
                "ambiguity_score": 0.5,
                "requires_clarification": True,
                "targets": [total_target, orders_target],
            },
            term("total sales", total_target),
        ],
        "ambiguities": ["sales"],
        "ambiguity_decisions": [
            {"term": "sales", "decision": "requires_clarification", "selected_target": None}
        ],
        "entity_decisions": [],
    }


def successful_intent() -> dict[str, object]:
    return {
        "version": 1,
        "question": "Which customers have the highest open sales value?",
        "from": "sales orders",
        "relationship_paths": ["sales customers"],
        "dimensions": [{"term": "customer", "alias": "customer"}],
        "metrics": [{"term": "total sales", "alias": "total_sales"}],
        "filters": [{"term": "order status", "operator": "eq", "value": "open"}],
        "order_by": [{"field": "total_sales", "direction": "desc"}],
        "limit": 25,
    }


def build_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    intent_path = tmp_path / "intent.yml"
    state_path = tmp_path / "approved_semantic_catalog.yml"
    output_dir = tmp_path / "adapter"
    write_yaml(intent_path, successful_intent())
    write_yaml(state_path, approved_state())
    return intent_path, state_path, output_dir


def blocker_types(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def build_database_and_relationships(tmp_path: Path) -> tuple[Path, Path]:
    database_path = tmp_path / "analytics.duckdb"
    connection = duckdb.connect(str(database_path))
    connection.execute(
        "create table orders (customer_id integer, status varchar, amount decimal(12,2))"
    )
    connection.execute("create table customers (id integer, name varchar)")
    connection.close()
    relationships_path = tmp_path / "approved_relationships.yml"
    write_yaml(
        relationships_path,
        {
            "approved_relationships": [
                {
                    "source_table": "orders",
                    "source_column": "customer_id",
                    "target_table": "customers",
                    "target_column": "id",
                }
            ]
        },
    )
    return database_path, relationships_path


def test_adapter_generates_stage5a_request_and_reuses_exact_outputs(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    protected = {intent_path: file_sha256(intent_path), state_path: file_sha256(state_path)}
    first = run_analytics_semantic_adapter(intent_path, state_path, output_dir)
    first_outputs = {path.name: path.read_bytes() for path in output_dir.iterdir()}
    second = run_analytics_semantic_adapter(intent_path, state_path, output_dir)

    assert first.status == "ready_for_query_plan"
    assert first.blocker_count == 0
    assert first.clarification_count == 0
    assert first.request == {
        "version": 1,
        "question": "Which customers have the highest open sales value?",
        "from": "orders",
        "joins": [
            {
                "source_table": "orders",
                "source_column": "customer_id",
                "target_table": "customers",
                "target_column": "id",
                "kind": "left",
            }
        ],
        "dimensions": [{"column": "customers.name", "alias": "customer"}],
        "metrics": [
            {"function": "sum", "column": "orders.amount", "alias": "total_sales"}
        ],
        "filters": [{"column": "orders.status", "operator": "eq", "value": "open"}],
        "order_by": [{"field": "total_sales", "direction": "desc"}],
        "limit": 25,
    }
    assert second.outputs_changed is False
    assert first_outputs == {path.name: path.read_bytes() for path in output_dir.iterdir()}
    assert all(file_sha256(path) == digest for path, digest in protected.items())
    for control_path in (first.manifest_path, first.blockers_path, first.report_path):
        control_text = control_path.read_text(encoding="utf-8")
        assert "Which customers" not in control_text
        assert "open" not in control_text

    database_path, relationships_path = build_database_and_relationships(tmp_path)
    plan = run_analytics_query_plan(
        first.request_path,
        database_path,
        relationships_path,
        tmp_path / "query_plan",
    )
    assert plan.status == "ready_for_execution_review"
    assert plan.compiled is not None


def test_adapter_preserves_ambiguous_term_for_clarification(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    intent = successful_intent()
    intent["from"] = "sales"
    write_yaml(intent_path, intent)
    result = run_analytics_semantic_adapter(intent_path, state_path, output_dir)
    clarification = yaml.safe_load(result.clarifications_path.read_text(encoding="utf-8"))

    assert result.status == "clarification_required"
    assert result.blocker_count == 0
    assert result.clarification_count == 1
    assert result.request_path is None
    assert clarification["clarifications"][0]["expected_kind"] == "table"
    assert {
        (row["kind"], row["id"])
        for row in clarification["clarifications"][0]["candidates"]
    } == {("table", "sales_orders"), ("measure", "total_amount")}


def test_adapter_respects_exact_human_ambiguity_resolution(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    state = approved_state()
    sales = next(row for row in state["term_index"] if row["term"] == "sales")
    sales["status"] = "resolved"
    sales["candidate_count"] = 1
    sales["ambiguity_score"] = 0.0
    sales["requires_clarification"] = False
    sales["targets"] = [target("measure", "total_amount", "Total Sales")]
    sales["resolution_authority"] = "human_approval"
    state["ambiguities"] = []
    state["approval"]["requires_clarification"] = False
    write_yaml(state_path, state)
    intent = successful_intent()
    intent["metrics"] = [{"term": "sales", "alias": "approved_sales"}]
    intent["order_by"] = [{"field": "approved_sales", "direction": "desc"}]
    write_yaml(intent_path, intent)
    result = run_analytics_semantic_adapter(intent_path, state_path, output_dir)

    assert result.status == "ready_for_query_plan"
    assert result.request["metrics"][0] == {
        "function": "sum",
        "column": "orders.amount",
        "alias": "approved_sales",
    }


def test_adapter_blocks_unapproved_or_unauthorized_semantic_state(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    state = approved_state()
    state["status"] = "ready_for_semantic_review"
    state["approval"]["semantic_definitions_approved"] = False
    state["approval"]["adapter_use_authorized"] = False
    write_yaml(state_path, state)
    result = run_analytics_semantic_adapter(intent_path, state_path, output_dir)

    assert result.status == "blocked"
    assert result.request_path is None
    assert {
        "semantic_state_not_approved",
        "semantic_definitions_not_approved",
        "semantic_adapter_not_authorized",
    } <= blocker_types(result.blockers_path)


def test_adapter_rejects_raw_sql_physical_joins_and_unknown_terms(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    intent = successful_intent()
    intent["sql"] = "select * from orders"
    intent["joins"] = [{"source_table": "orders", "target_table": "customers"}]
    intent["dimensions"] = [{"term": "invented concept", "alias": "invented"}]
    write_yaml(intent_path, intent)
    result = run_analytics_semantic_adapter(intent_path, state_path, output_dir)

    assert result.status == "blocked"
    assert result.request_path is None
    assert {
        "raw_sql_not_allowed",
        "physical_join_not_allowed",
        "unknown_semantic_term",
    } <= blocker_types(result.blockers_path)
    assert "select *" not in result.report_path.read_text(encoding="utf-8")


def test_adapter_blocks_missing_path_invalid_filter_and_order_alias(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    intent = successful_intent()
    intent["relationship_paths"] = []
    intent["filters"] = [{"term": "order status", "operator": "in", "value": []}]
    intent["order_by"] = [{"field": "missing_alias", "direction": "sideways"}]
    write_yaml(intent_path, intent)
    result = run_analytics_semantic_adapter(intent_path, state_path, output_dir)

    assert result.status == "blocked"
    assert {
        "invalid_in_filter",
        "invalid_order_direction",
    } <= blocker_types(result.blockers_path)

    intent["filters"] = []
    intent["order_by"] = []
    write_yaml(intent_path, intent)
    no_path = run_analytics_semantic_adapter(
        intent_path,
        state_path,
        tmp_path / "no_path",
    )
    assert "semantic_table_not_selected" in blocker_types(no_path.blockers_path)


def test_adapter_refuses_divergent_existing_evidence(tmp_path: Path) -> None:
    intent_path, state_path, output_dir = build_fixture(tmp_path)
    first = run_analytics_semantic_adapter(intent_path, state_path, output_dir)
    intent = successful_intent()
    intent["limit"] = 10
    write_yaml(intent_path, intent)

    with pytest.raises(ValueError, match="existing generated evidence was not overwritten"):
        run_analytics_semantic_adapter(intent_path, state_path, output_dir)
    assert first.request_path.is_file()


def test_analytics_semantic_adapter_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "analytics-semantic-adapter",
            "--intent",
            "intent.yml",
            "--semantic-state",
            "approved.yml",
            "--output",
            "adapter",
        ]
    )

    assert args.command == "analytics-semantic-adapter"
    assert args.intent == Path("intent.yml")
    assert args.semantic_state == Path("approved.yml")
    assert args.output == Path("adapter")
