from __future__ import annotations

import csv
from pathlib import Path
from threading import Event

import duckdb
import yaml

from data_ops_lab.analytics_query_execution import (
    AnalyticsExecutionLimits,
    ExecutionLimitExceeded,
    execute_compiled_query,
    run_analytics_query_execution,
)
from data_ops_lab.analytics_query_plan import CompiledAnalyticsQuery, run_analytics_query_plan
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def request(filter_value: str = "FILTER_VALUE_9Z", limit: int = 20) -> dict:
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
        "filters": [{"column": "orders.status", "operator": "eq", "value": filter_value}],
        "order_by": [{"field": "total_amount", "direction": "desc"}],
        "limit": limit,
    }


def build_fixture(
    tmp_path: Path,
    *,
    request_payload: dict | None = None,
    alice_name: str = "Alice",
) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths = {
        "database": tmp_path / "analytics.duckdb",
        "request": tmp_path / "request.yml",
        "relationships": tmp_path / "relationships.yml",
        "plan_dir": tmp_path / "plan",
        "execution_dir": tmp_path / "execution",
    }
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute(
            "create table orders(order_id integer, customer_name varchar, status varchar)"
        )
        connection.execute(
            "insert into orders values (1, ?, 'FILTER_VALUE_9Z'), (2, 'Bob', 'closed')",
            [alice_name],
        )
        connection.execute(
            "create table order_lines(line_id integer, order_id integer, amount decimal(10, 2))"
        )
        connection.execute(
            "insert into order_lines values (10, 1, 12.50), (11, 1, 2.50), (12, 2, 8.00)"
        )
    write_yaml(paths["request"], request_payload or request())
    write_yaml(
        paths["relationships"],
        {
            "approved_relationships": [
                {
                    "source_table": "orders",
                    "source_column": "order_id",
                    "target_table": "order_lines",
                    "target_column": "order_id",
                }
            ]
        },
    )
    plan = run_analytics_query_plan(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan_dir"],
    )
    paths["plan"] = plan.plan_path
    return paths


def blocker_types(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def test_controlled_execution_is_read_only_private_and_idempotent(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    protected = {
        path: file_sha256(path)
        for path in (
            paths["database"],
            paths["request"],
            paths["relationships"],
            paths["plan"],
        )
    }

    first = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
    )
    first_outputs = {path.name: path.read_bytes() for path in paths["execution_dir"].iterdir()}
    second = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
    )

    assert first.status == "completed"
    assert first.row_count == 1
    assert first.blocker_count == 0
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert first.result_path is not None
    assert first.result_path.read_text(encoding="utf-8") == "customer,total_amount\nAlice,15.00\n"
    assert first_outputs == {path.name: path.read_bytes() for path in paths["execution_dir"].iterdir()}
    assert all(file_sha256(path) == digest for path, digest in protected.items())

    manifest_text = first.manifest_path.read_text(encoding="utf-8")
    report_text = first.report_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(manifest_text)
    assert manifest["execution"]["database_mode"] == "read_only"
    assert manifest["execution"]["external_access"] is False
    assert manifest["query"]["parameter_values_included"] is False
    assert manifest["query"]["raw_sql_accepted"] is False
    assert "PRIVATE QUESTION" not in manifest_text + report_text
    assert "FILTER_VALUE_9Z" not in manifest_text + report_text


def test_execution_rejects_request_drift_from_reviewed_plan(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    write_yaml(paths["request"], request(filter_value="closed"))

    result = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
    )

    assert result.status == "blocked"
    assert result.result_path is None
    assert "reviewed_plan_mismatch" in blocker_types(result.blockers_path)
    assert not (paths["execution_dir"] / "analytics_query_result.csv").exists()


def test_execution_rejects_database_drift_from_reviewed_plan(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute("update orders set customer_name = 'Changed' where order_id = 1")

    result = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
    )

    assert result.status == "blocked"
    assert result.result_path is None
    assert "reviewed_plan_mismatch" in blocker_types(result.blockers_path)


def test_execution_fails_closed_when_result_exceeds_row_or_byte_limit(tmp_path: Path) -> None:
    paths = build_fixture(
        tmp_path,
        request_payload={
            "version": 1,
            "from": "orders",
            "dimensions": ["customer_name", "status"],
            "limit": 20,
        },
    )

    row_limited = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
        AnalyticsExecutionLimits(max_rows=1),
    )
    assert row_limited.status == "blocked"
    assert "result_row_limit_exceeded" in blocker_types(row_limited.blockers_path)
    assert row_limited.result_path is None

    byte_paths = build_fixture(
        tmp_path / "large-result",
        alice_name="A" * 2_000,
    )
    byte_limited = run_analytics_query_execution(
        byte_paths["request"],
        byte_paths["database"],
        byte_paths["relationships"],
        byte_paths["plan"],
        byte_paths["execution_dir"],
        AnalyticsExecutionLimits(max_result_bytes=1_024),
    )
    assert byte_limited.status == "blocked"
    assert "result_size_limit_exceeded" in blocker_types(byte_limited.blockers_path)
    assert byte_limited.result_path is None

    tiny_dir = tmp_path / "invalid-byte-limit"
    invalid_limit = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        tiny_dir,
        AnalyticsExecutionLimits(max_result_bytes=100),
    )
    assert invalid_limit.status == "blocked"
    assert "invalid_execution_limit" in blocker_types(invalid_limit.blockers_path)


def test_execution_records_successful_no_row_diagnostic(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path, request_payload=request(filter_value="missing"))

    result = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
    )

    assert result.status == "completed_no_rows"
    assert result.row_count == 0
    assert result.result_path is not None
    assert result.result_path.read_text(encoding="utf-8") == "customer,total_amount\n"
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["result"]["no_rows"] is True
    assert "returned no rows" in result.report_path.read_text(encoding="utf-8")


def test_execution_refuses_different_existing_evidence(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    first = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        paths["plan"],
        paths["execution_dir"],
    )

    try:
        run_analytics_query_execution(
            paths["request"],
            paths["database"],
            paths["relationships"],
            paths["plan"],
            paths["execution_dir"],
            AnalyticsExecutionLimits(max_rows=500),
        )
    except ValueError as error:
        assert "existing generated evidence was not overwritten" in str(error)
    else:
        raise AssertionError("Different execution evidence must be refused.")
    assert first.result_path is not None and first.result_path.is_file()


def test_execution_interrupts_query_after_runtime_limit(monkeypatch) -> None:
    class SlowConnection:
        def __init__(self) -> None:
            self.interrupted = Event()

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def execute(self, sql, _parameters=None):
            if str(sql).startswith("SET "):
                return self
            self.interrupted.wait(timeout=2)
            raise duckdb.Error("simulated interrupted query")

        def interrupt(self) -> None:
            self.interrupted.set()

    connection = SlowConnection()
    monkeypatch.setattr(
        "data_ops_lab.analytics_query_execution.duckdb.connect",
        lambda *_args, **_kwargs: connection,
    )

    try:
        execute_compiled_query(
            Path("synthetic.duckdb"),
            CompiledAnalyticsQuery("SELECT 1;", (), ()),
            AnalyticsExecutionLimits(max_runtime_seconds=1),
        )
    except ExecutionLimitExceeded as error:
        assert error.blocker_type == "query_timeout"
    else:
        raise AssertionError("The runtime limit must interrupt the query.")
    assert connection.interrupted.is_set()


def test_analytics_query_execution_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "analytics-query-execute",
            "--request",
            "request.yml",
            "--database",
            "analytics.duckdb",
            "--relationships",
            "relationships.yml",
            "--plan",
            "plan.yml",
            "--output",
            "execution",
            "--max-rows",
            "500",
            "--max-runtime-seconds",
            "5",
        ]
    )

    assert args.command == "analytics-query-execute"
    assert args.plan == Path("plan.yml")
    assert args.max_rows == 500
    assert args.max_runtime_seconds == 5
