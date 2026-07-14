from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import pytest
import yaml

from data_ops_lab.analytics_query_execution import run_analytics_query_execution
from data_ops_lab.analytics_query_plan import run_analytics_query_plan
from data_ops_lab.analytics_result_narration import (
    RecordedResultNarrationProvider,
    ResultNarrationPrompt,
    run_analytics_result_narration,
)
from data_ops_lab.analytics_result_presentation import run_analytics_result_presentation
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


def build_executed_fixture(
    tmp_path: Path,
    *,
    filter_value: str = "FILTER_VALUE_9Z",
    extra_rows: int = 0,
) -> dict[str, Path]:
    paths = {
        "database": tmp_path / "analytics.duckdb",
        "request": tmp_path / "request.yml",
        "relationships": tmp_path / "relationships.yml",
        "plan_dir": tmp_path / "plan",
        "execution_dir": tmp_path / "execution",
        "presentation_dir": tmp_path / "presentation",
        "narration_dir": tmp_path / "narration",
    }
    with duckdb.connect(str(paths["database"])) as connection:
        connection.execute(
            "create table orders(order_id integer, customer_name varchar, status varchar)"
        )
        connection.execute(
            "insert into orders values (1, 'Alice', 'FILTER_VALUE_9Z'), (2, 'Bob', 'closed')"
        )
        connection.execute(
            "create table order_lines(line_id integer, order_id integer, amount decimal(10, 2))"
        )
        connection.execute(
            "insert into order_lines values (10, 1, 12.50), (11, 1, 2.50), (12, 2, 8.00)"
        )
        if extra_rows:
            connection.executemany(
                "insert into orders values (?, ?, 'FILTER_VALUE_9Z')",
                [(index, f"Customer {index}") for index in range(3, 3 + extra_rows)],
            )
            connection.executemany(
                "insert into order_lines values (?, ?, 1.00)",
                [(1_000 + index, index) for index in range(3, 3 + extra_rows)],
            )
    write_yaml(paths["request"], request(filter_value, limit=max(20, extra_rows + 2)))
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
    execution = run_analytics_query_execution(
        paths["request"],
        paths["database"],
        paths["relationships"],
        plan.plan_path,
        paths["execution_dir"],
    )
    assert execution.result_path is not None
    paths["execution_manifest"] = execution.manifest_path
    paths["result"] = execution.result_path
    return paths


def present(paths: dict[str, Path]):
    return run_analytics_result_presentation(
        paths["request"],
        paths["execution_manifest"],
        paths["result"],
        paths["presentation_dir"],
    )


def blocker_types(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def valid_response() -> dict:
    return {
        "version": 1,
        "headline": "Open customer order result",
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
                "text": "Alice has a total amount of 15.00.",
                "citations": ["cell.r001.c001", "cell.r001.c002"],
            },
        ],
    }


def test_presentation_is_grounded_private_idempotent_and_preserves_inputs(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    protected = {
        path: file_sha256(path)
        for path in (
            paths["request"],
            paths["execution_manifest"],
            paths["result"],
            paths["database"],
        )
    }

    first = present(paths)
    first_outputs = {path.name: path.read_bytes() for path in paths["presentation_dir"].iterdir()}
    second = present(paths)

    assert first.status == "ready_for_recorded_narration"
    assert first.row_count == 1
    assert first.preview_row_count == 1
    assert first.preview_column_count == 2
    assert first.blocker_count == 0
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert first.facts_path is not None
    assert all(file_sha256(path) == digest for path, digest in protected.items())
    assert first_outputs == {path.name: path.read_bytes() for path in paths["presentation_dir"].iterdir()}

    presentation = first.presentation_path.read_text(encoding="utf-8")
    facts = first.facts_path.read_text(encoding="utf-8")
    manifest = first.manifest_path.read_text(encoding="utf-8")
    assert "PRIVATE QUESTION" in presentation
    assert "Alice" in presentation and "15.00" in presentation
    assert "Alice" in facts and "15.00" in facts
    assert "PRIVATE QUESTION" not in manifest
    assert "Alice" not in manifest
    assert "15.00" not in manifest
    assert "FILTER_VALUE_9Z" not in manifest
    assert "select" not in manifest.lower()


def test_presentation_reports_completed_no_rows_explicitly(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path, filter_value="missing")

    result = present(paths)

    assert result.status == "ready_for_recorded_narration"
    assert result.row_count == 0
    assert "returned no rows" in result.presentation_path.read_text(encoding="utf-8")
    facts = yaml.safe_load(result.facts_path.read_text(encoding="utf-8"))
    by_id = {item["id"]: item["value"] for item in facts["facts"]}
    assert by_id["result.row_count"] == "0"
    assert by_id["result.no_rows"] == "true"


def test_presentation_bounds_preview_without_changing_full_result(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path, extra_rows=105)
    result_hash = file_sha256(paths["result"])

    result = present(paths)

    assert result.status == "ready_for_recorded_narration"
    assert result.row_count == 106
    assert result.preview_row_count == 100
    assert result.preview_column_count == 2
    assert file_sha256(paths["result"]) == result_hash
    facts = yaml.safe_load(result.facts_path.read_text(encoding="utf-8"))
    assert facts["preview"]["truncated"] is True
    assert len(facts["facts"]) == 205


def test_presentation_blocks_tampered_result_without_persisting_values(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    paths["result"].write_text("customer,total_amount\nMallory,999.00\n", encoding="utf-8")

    result = present(paths)

    assert result.status == "blocked"
    assert result.facts_path is None
    assert "result_hash_mismatch" in blocker_types(result.blockers_path)
    output = result.presentation_path.read_text(encoding="utf-8")
    assert "Mallory" not in output and "999.00" not in output


def test_presentation_blocks_unsafe_execution_evidence(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    manifest = yaml.safe_load(paths["execution_manifest"].read_text(encoding="utf-8"))
    manifest["execution"]["database_mode"] = "read_write"
    write_yaml(paths["execution_manifest"], manifest)

    result = present(paths)

    assert result.status == "blocked"
    assert "unsafe_execution_evidence" in blocker_types(result.blockers_path)


def test_recorded_narration_requires_cited_exact_facts_and_is_idempotent(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    presentation = present(paths)
    assert presentation.facts_path is not None
    response_path = tmp_path / "response.yml"
    write_yaml(response_path, valid_response())
    facts_hash = file_sha256(presentation.facts_path)

    first = run_analytics_result_narration(
        presentation.manifest_path,
        presentation.facts_path,
        paths["narration_dir"],
        RecordedResultNarrationProvider(response_path),
    )
    second = run_analytics_result_narration(
        presentation.manifest_path,
        presentation.facts_path,
        paths["narration_dir"],
        RecordedResultNarrationProvider(response_path),
    )

    assert first.status == "ready_for_user"
    assert first.claim_count == 3
    assert first.provider_called is True
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert first.narrative_path is not None
    assert file_sha256(presentation.facts_path) == facts_hash
    narrative = first.narrative_path.read_text(encoding="utf-8")
    assert "Alice has a total amount of 15.00" in narrative
    assert "[cell.r001.c002]" in narrative
    manifest = first.manifest_path.read_text(encoding="utf-8")
    assert "Alice" not in manifest and "15.00" not in manifest


@pytest.mark.parametrize(
    ("mutator", "expected_blocker"),
    [
        (
            lambda payload: payload["claims"][2].update(
                {"text": "Alice has a total amount of 16.00."}
            ),
            "ungrounded_numeric_value",
        ),
        (
            lambda payload: payload["claims"][0].update(
                {"citations": ["result.row_count", "unknown.fact"]}
            ),
            "invalid_claim_citations",
        ),
        (
            lambda payload: payload["claims"][2].update(
                {"text": "SELECT total_amount from orders"}
            ),
            "invalid_claim_text",
        ),
    ],
)
def test_narration_blocks_numeric_mutation_unknown_citations_and_sql(
    tmp_path: Path,
    mutator,
    expected_blocker: str,
) -> None:
    paths = build_executed_fixture(tmp_path)
    presentation = present(paths)
    response = valid_response()
    mutator(response)
    response_path = tmp_path / "response.yml"
    write_yaml(response_path, response)

    result = run_analytics_result_narration(
        presentation.manifest_path,
        presentation.facts_path,
        paths["narration_dir"],
        RecordedResultNarrationProvider(response_path),
    )

    assert result.status == "blocked"
    assert result.narrative_path is None
    assert expected_blocker in blocker_types(result.blockers_path)


class NetworkProvider:
    name = "test_network"
    mode = "online"
    network_access_required = True

    def __init__(self) -> None:
        self.called = False

    def narrate(
        self,
        prompt: ResultNarrationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict:
        del prompt, timeout_seconds
        self.called = True
        return valid_response()


def test_network_narrator_is_not_called_without_explicit_opt_in(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    presentation = present(paths)
    provider = NetworkProvider()

    result = run_analytics_result_narration(
        presentation.manifest_path,
        presentation.facts_path,
        paths["narration_dir"],
        provider,
    )

    assert result.status == "blocked"
    assert result.provider_called is False
    assert provider.called is False
    assert "network_provider_not_authorized" in blocker_types(result.blockers_path)


def test_narration_blocks_facts_drift_before_calling_provider(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    presentation = present(paths)
    facts_text = presentation.facts_path.read_text(encoding="utf-8")
    presentation.facts_path.write_text(facts_text.replace("15.00", "16.00"), encoding="utf-8")
    provider = NetworkProvider()
    provider.network_access_required = False

    result = run_analytics_result_narration(
        presentation.manifest_path,
        presentation.facts_path,
        paths["narration_dir"],
        provider,
    )

    assert result.status == "blocked"
    assert provider.called is False
    assert "facts_hash_mismatch" in blocker_types(result.blockers_path)


def test_narration_refuses_divergent_existing_evidence(tmp_path: Path) -> None:
    paths = build_executed_fixture(tmp_path)
    presentation = present(paths)
    response_path = tmp_path / "response.yml"
    write_yaml(response_path, valid_response())
    run_analytics_result_narration(
        presentation.manifest_path,
        presentation.facts_path,
        paths["narration_dir"],
        RecordedResultNarrationProvider(response_path),
    )
    changed = valid_response()
    changed["headline"] = "Changed result headline"
    write_yaml(response_path, changed)

    with pytest.raises(ValueError, match="existing generated evidence was not overwritten"):
        run_analytics_result_narration(
            presentation.manifest_path,
            presentation.facts_path,
            paths["narration_dir"],
            RecordedResultNarrationProvider(response_path),
        )


def test_result_presentation_cli_is_recorded_only_and_has_no_network_switch() -> None:
    parser = build_parser()
    present_args = parser.parse_args(
        [
            "analytics-result-present",
            "--request",
            "request.yml",
            "--execution-manifest",
            "execution.yml",
            "--result",
            "result.csv",
        ]
    )
    narration_args = parser.parse_args(
        [
            "analytics-result-narrate-recorded",
            "--presentation-manifest",
            "presentation.yml",
            "--facts",
            "facts.yml",
            "--provider-response",
            "response.yml",
        ]
    )

    assert present_args.command == "analytics-result-present"
    assert narration_args.command == "analytics-result-narrate-recorded"
    assert not hasattr(narration_args, "allow_network")
