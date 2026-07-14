from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import yaml

from data_ops_lab.analytics_semantic_catalog import (
    resolve_semantic_term,
    run_analytics_semantic_catalog,
)
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def semantic_payload() -> dict:
    return {
        "version": 1,
        "dataset": {
            "id": "sales_operations",
            "name": "Sales Operations",
            "description": "Synthetic sales semantics.",
            "synonyms": ["commercial operations"],
        },
        "tables": [
            {
                "id": "sales_orders",
                "source_table": "orders",
                "name": "Sales Orders",
                "synonyms": ["orders", "sales"],
            },
            {
                "id": "sales_order_lines",
                "source_table": "order_lines",
                "name": "Sales Order Lines",
                "synonyms": ["order items"],
            },
            {
                "id": "line_notes",
                "source_table": "line_notes",
                "name": "Line Notes",
                "synonyms": ["item notes"],
            },
        ],
        "dimensions": [
            {
                "id": "customer",
                "table_id": "sales_orders",
                "source_column": "customer_name",
                "name": "Customer",
                "synonyms": ["client", "buyer"],
            },
            {
                "id": "order_status",
                "table_id": "sales_orders",
                "source_column": "status",
                "name": "Order Status",
                "synonyms": ["state"],
            },
        ],
        "measures": [
            {
                "id": "total_amount",
                "table_id": "sales_order_lines",
                "source_column": "amount",
                "function": "sum",
                "name": "Total Amount",
                "synonyms": ["revenue", "sales"],
            },
            {
                "id": "order_count",
                "table_id": "sales_orders",
                "source_column": "*",
                "function": "count",
                "name": "Order Count",
                "synonyms": ["number of orders"],
            },
        ],
        "relationship_paths": [
            {
                "id": "orders_to_lines",
                "name": "Orders to Lines",
                "synonyms": ["order details"],
                "hops": [
                    {
                        "source_table_id": "sales_orders",
                        "source_column": "order_id",
                        "target_table_id": "sales_order_lines",
                        "target_column": "order_id",
                        "kind": "left",
                    },
                    {
                        "source_table_id": "sales_order_lines",
                        "source_column": "line_id",
                        "target_table_id": "line_notes",
                        "target_column": "line_id",
                        "kind": "left",
                    }
                ],
            }
        ],
    }


def build_fixture(tmp_path: Path, *, approve_relationship: bool = True) -> dict[str, Path]:
    paths = {
        "database": tmp_path / "semantic.duckdb",
        "source": tmp_path / "semantic.yml",
        "relationships": tmp_path / "relationships.yml",
        "output": tmp_path / "compiled",
    }
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute(
            "create table orders(order_id integer, customer_name varchar, status varchar)"
        )
        connection.execute(
            "create table order_lines(line_id integer, order_id integer, amount decimal(10, 2))"
        )
        connection.execute("create table line_notes(line_id integer, note varchar)")
    write_yaml(paths["source"], semantic_payload())
    relationships = []
    if approve_relationship:
        relationships.append(
            {
                "source_table": "orders",
                "source_column": "order_id",
                "target_table": "order_lines",
                "target_column": "order_id",
            }
        )
        relationships.append(
            {
                "source_table": "order_lines",
                "source_column": "line_id",
                "target_table": "line_notes",
                "target_column": "line_id",
            }
        )
    write_yaml(paths["relationships"], {"approved_relationships": relationships})
    return paths


def blocker_types(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def test_semantic_catalog_validates_metadata_resolves_terms_and_is_idempotent(
    tmp_path: Path,
) -> None:
    paths = build_fixture(tmp_path)
    protected = {
        path: file_sha256(path)
        for path in (paths["database"], paths["source"], paths["relationships"])
    }

    first = run_analytics_semantic_catalog(
        paths["source"], paths["database"], paths["relationships"], paths["output"]
    )
    first_outputs = {path.name: path.read_bytes() for path in paths["output"].iterdir()}
    second = run_analytics_semantic_catalog(
        paths["source"], paths["database"], paths["relationships"], paths["output"]
    )

    assert first.status == "ready_for_semantic_review"
    assert first.blocker_count == 0
    assert first.ambiguity_count == 1
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert first_outputs == {path.name: path.read_bytes() for path in paths["output"].iterdir()}
    assert all(file_sha256(path) == digest for path, digest in protected.items())
    assert first.catalog["approval"]["semantic_definitions_approved"] is False
    assert first.catalog["approval"]["adapter_use_authorized"] is False
    assert len(first.catalog["relationship_paths"][0]["hops"]) == 2

    resolved = resolve_semantic_term(first.catalog, "CLÍENT")
    ambiguous = resolve_semantic_term(first.catalog, "sales")
    unknown = resolve_semantic_term(first.catalog, "missing concept")
    assert resolved.status == "resolved"
    assert resolved.targets[0]["kind"] == "dimension"
    assert resolved.targets[0]["id"] == "customer"
    assert ambiguous.status == "ambiguous"
    assert {(target["kind"], target["id"]) for target in ambiguous.targets} == {
        ("measure", "total_amount"),
        ("table", "sales_orders"),
    }
    assert unknown.status == "unknown"


def test_semantic_catalog_blocks_unknown_columns_and_invalid_measure_types(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    payload = semantic_payload()
    payload["dimensions"][0]["source_column"] = "missing_column"
    payload["measures"][0]["table_id"] = "sales_orders"
    payload["measures"][0]["source_column"] = "status"
    write_yaml(paths["source"], payload)

    result = run_analytics_semantic_catalog(
        paths["source"], paths["database"], paths["relationships"], paths["output"]
    )
    types = blocker_types(result.blockers_path)

    assert result.status == "blocked"
    assert {"unknown_source_column", "incompatible_measure_type"} <= types
    assert resolve_semantic_term(result.catalog, "customer").status == "catalog_blocked"


def test_semantic_catalog_blocks_unapproved_relationship_paths(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path, approve_relationship=False)

    result = run_analytics_semantic_catalog(
        paths["source"], paths["database"], paths["relationships"], paths["output"]
    )

    assert result.status == "blocked"
    assert "relationship_not_approved" in blocker_types(result.blockers_path)
    assert result.catalog["relationship_paths"] == []


def test_semantic_catalog_blocks_schema_typos_and_duplicate_ids(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    payload = semantic_payload()
    payload["unexpected"] = True
    payload["dimensions"][1]["id"] = "customer"
    payload["tables"][0]["unknown_option"] = "ignored"
    write_yaml(paths["source"], payload)

    result = run_analytics_semantic_catalog(
        paths["source"], paths["database"], paths["relationships"], paths["output"]
    )
    types = blocker_types(result.blockers_path)

    assert result.status == "blocked"
    assert {"unsupported_semantic_field", "duplicate_semantic_id"} <= types


def test_semantic_catalog_refuses_different_existing_evidence(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    first = run_analytics_semantic_catalog(
        paths["source"], paths["database"], paths["relationships"], paths["output"]
    )
    payload = semantic_payload()
    payload["dataset"]["name"] = "Changed Name"
    write_yaml(paths["source"], payload)

    try:
        run_analytics_semantic_catalog(
            paths["source"], paths["database"], paths["relationships"], paths["output"]
        )
    except ValueError as error:
        assert "existing generated evidence was not overwritten" in str(error)
    else:
        raise AssertionError("Different semantic evidence must be refused.")
    assert first.catalog_path.is_file()


def test_analytics_semantic_catalog_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "analytics-semantic-catalog",
            "--catalog",
            "semantic.yml",
            "--database",
            "analytics.duckdb",
            "--relationships",
            "relationships.yml",
            "--output",
            "compiled",
        ]
    )

    assert args.command == "analytics-semantic-catalog"
    assert args.catalog == Path("semantic.yml")
    assert args.database == Path("analytics.duckdb")
    assert args.relationships == Path("relationships.yml")
    assert args.output == Path("compiled")
