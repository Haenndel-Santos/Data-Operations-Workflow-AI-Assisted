from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import duckdb
import yaml

from data_ops_lab.analytics_query_plan import run_analytics_query_plan
from data_ops_lab.cli import build_parser


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def build_fixture(tmp_path: Path, *, approve_join: bool = True) -> tuple[Path, Path, Path, Path]:
    database_path = tmp_path / "analytics.duckdb"
    request_path = tmp_path / "request.yml"
    relationships_path = tmp_path / "relationships.yml"
    output_dir = tmp_path / "plan"
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            "create table orders(order_id integer, customer_name varchar, status varchar, order_date date)"
        )
        connection.execute(
            "insert into orders values "
            "(1, 'Alice', 'open', date '2026-01-10'), "
            "(2, 'Bob', 'closed', date '2026-02-10')"
        )
        connection.execute(
            "create table order_lines(line_id integer, order_id integer, amount decimal(10, 2))"
        )
        connection.execute(
            "insert into order_lines values (10, 1, 12.50), (11, 1, 2.50), (12, 2, 8.00)"
        )
    relationships = []
    if approve_join:
        relationships.append(
            {
                "source_table": "orders",
                "source_column": "order_id",
                "target_table": "order_lines",
                "target_column": "order_id",
            }
        )
    write_yaml(relationships_path, {"approved_relationships": relationships})
    return database_path, request_path, relationships_path, output_dir


def cross_table_request() -> dict:
    return {
        "version": 1,
        "question": "PRIVATE QUESTION about open customer orders",
        "from": "orders",
        "joins": [
            {
                "source_table": "orders",
                "source_column": "order_id",
                "target_table": "order_lines",
                "target_column": "order_id",
                "kind": "left",
            }
        ],
        "dimensions": [{"column": "orders.customer_name", "alias": "customer"}],
        "metrics": [
            {"function": "sum", "column": "order_lines.amount", "alias": "total_amount"}
        ],
        "filters": [{"column": "orders.status", "operator": "eq", "value": "open"}],
        "order_by": [{"field": "total_amount", "direction": "desc"}],
        "limit": 20,
    }


def test_query_plan_compiles_private_parameterized_join_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database_path, request_path, relationships_path, output_dir = build_fixture(tmp_path)
    write_yaml(request_path, cross_table_request())
    protected = {
        path: path.read_bytes() for path in (database_path, request_path, relationships_path)
    }

    first = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )
    first_outputs = {path.name: path.read_bytes() for path in output_dir.iterdir()}
    second = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )

    assert first.status == "ready_for_execution_review"
    assert first.blocker_count == 0
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert first.compiled is not None
    assert first.compiled.parameters == ("open",)
    assert "LEFT JOIN" in first.compiled.sql
    assert '"orders"."status" = ?' in first.compiled.sql
    assert first_outputs == {path.name: path.read_bytes() for path in output_dir.iterdir()}
    assert all(path.read_bytes() == content for path, content in protected.items())

    plan_text = first.plan_path.read_text(encoding="utf-8")
    plan = yaml.safe_load(plan_text)
    assert plan["query"]["parameter_values_included"] is False
    assert plan["approval"]["execution_authorized"] is False
    assert "PRIVATE QUESTION" not in plan_text
    assert "open" not in plan["query"]["sql"]

    with duckdb.connect(str(database_path), read_only=True) as connection:
        rows = connection.execute(first.compiled.sql, first.compiled.parameters).fetchall()
    assert rows == [("Alice", 15.0)]


def test_query_plan_blocks_unapproved_cross_table_join(tmp_path: Path) -> None:
    database_path, request_path, relationships_path, output_dir = build_fixture(
        tmp_path,
        approve_join=False,
    )
    write_yaml(request_path, cross_table_request())

    result = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        blockers = list(csv.DictReader(handle))

    assert result.status == "blocked"
    assert result.compiled is None
    assert "relationship_not_approved" in {row["blocker_type"] for row in blockers}
    assert yaml.safe_load(result.plan_path.read_text(encoding="utf-8"))["query"]["sql"] == ""


def test_query_plan_accepts_typed_date_filter_without_exposing_value(tmp_path: Path) -> None:
    database_path, request_path, relationships_path, output_dir = build_fixture(tmp_path)
    write_yaml(
        request_path,
        {
            "version": 1,
            "from": "orders",
            "dimensions": ["customer_name"],
            "filters": [
                {"column": "order_date", "operator": "gte", "value": date(2026, 2, 1)}
            ],
            "limit": 10,
        },
    )

    result = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )

    assert result.status == "ready_for_execution_review"
    assert result.compiled is not None
    assert result.compiled.parameter_types == ("date",)
    assert "2026-02-01" not in result.plan_path.read_text(encoding="utf-8")


def test_query_plan_rejects_raw_sql_unknown_columns_and_unbounded_limit(tmp_path: Path) -> None:
    database_path, request_path, relationships_path, output_dir = build_fixture(tmp_path)
    write_yaml(
        request_path,
        {
            "version": 1,
            "from": "orders",
            "sql": "delete from orders",
            "dimensions": ["missing_column"],
            "metrics": [{"function": "count", "column": "*", "alias": "rows"}],
            "limit": 50_000,
        },
    )

    result = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        blocker_types = {row["blocker_type"] for row in csv.DictReader(handle)}

    assert result.status == "blocked"
    assert result.compiled is None
    assert {
        "unsupported_request_field",
        "unknown_column",
        "invalid_limit",
    } <= blocker_types


def test_query_plan_blocks_empty_request(tmp_path: Path) -> None:
    database_path, request_path, relationships_path, output_dir = build_fixture(tmp_path)
    write_yaml(request_path, {})

    result = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        blocker_types = {row["blocker_type"] for row in csv.DictReader(handle)}

    assert result.status == "blocked"
    assert result.compiled is None
    assert "unsupported_request_version" in blocker_types
    assert "invalid_table" in blocker_types


def test_query_plan_refuses_different_existing_outputs(tmp_path: Path) -> None:
    database_path, request_path, relationships_path, output_dir = build_fixture(tmp_path)
    request = cross_table_request()
    write_yaml(request_path, request)
    first = run_analytics_query_plan(
        request_path,
        database_path,
        relationships_path,
        output_dir,
    )
    request["limit"] = 5
    write_yaml(request_path, request)

    try:
        run_analytics_query_plan(
            request_path,
            database_path,
            relationships_path,
            output_dir,
        )
    except ValueError as error:
        assert "existing generated evidence was not overwritten" in str(error)
    else:
        raise AssertionError("Different query-plan outputs must be refused.")
    assert first.plan_path.is_file()


def test_analytics_query_plan_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "analytics-query-plan",
            "--request",
            "request.yml",
            "--database",
            "analytics.duckdb",
            "--relationships",
            "relationships.yml",
            "--output",
            "query-plan",
        ]
    )

    assert args.command == "analytics-query-plan"
    assert args.request == Path("request.yml")
    assert args.database == Path("analytics.duckdb")
    assert args.relationships == Path("relationships.yml")
    assert args.output == Path("query-plan")
