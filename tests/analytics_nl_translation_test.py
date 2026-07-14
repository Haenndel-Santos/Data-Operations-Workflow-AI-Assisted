from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
import yaml

from data_ops_lab.analytics_nl_translation import (
    RecordedSemanticIntentProvider,
    SemanticTranslationPrompt,
    run_analytics_nl_translation,
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
    table_target = {"kind": "table", "id": "sales_orders", "name": "Sales Orders"}
    measure_target = {"kind": "measure", "id": "order_count", "name": "Order Count"}
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
            resolved_term("sales dataset", "dataset", "sales_dataset", "Sales Dataset"),
            resolved_term("sales orders", "table", "sales_orders", "Sales Orders"),
            {
                "term": "sales",
                "status": "ambiguous",
                "candidate_count": 2,
                "ambiguity_score": 0.5,
                "requires_clarification": True,
                "targets": [measure_target, table_target],
            },
        ],
        "ambiguities": ["sales"],
        "ambiguity_decisions": [
            {"term": "sales", "decision": "requires_clarification", "selected_target": None}
        ],
        "entity_decisions": [],
    }


def provider_response() -> dict[str, Any]:
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


def build_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    question_path = tmp_path / "question.txt"
    state_path = tmp_path / "approved_semantic_catalog.yml"
    response_path = tmp_path / "provider_response.yml"
    output_dir = tmp_path / "translation"
    question_path.write_text("How many open orders exist by status?\n", encoding="utf-8")
    write_yaml(state_path, approved_state())
    write_yaml(response_path, provider_response())
    return question_path, state_path, response_path, output_dir


def blocker_types(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


class CaptureProvider:
    name = "capture_fake"
    mode = "offline_fake"
    network_access_required = False

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.prompt: SemanticTranslationPrompt | None = None
        self.timeout_seconds = 0
        self.calls = 0

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.calls += 1
        self.prompt = prompt
        self.timeout_seconds = timeout_seconds
        return self.response


class NetworkProvider(CaptureProvider):
    name = "network_fake"
    mode = "network_fake"
    network_access_required = True


class FailingProvider(CaptureProvider):
    def __init__(self, error: Exception) -> None:
        super().__init__({})
        self.error = error

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.calls += 1
        raise self.error


def test_recorded_translation_runs_full_offline_adapter_pipeline(tmp_path: Path) -> None:
    question_path, state_path, response_path, output_dir = build_fixture(tmp_path)
    protected = {
        question_path: file_sha256(question_path),
        state_path: file_sha256(state_path),
        response_path: file_sha256(response_path),
    }
    provider = RecordedSemanticIntentProvider(response_path)
    first = run_analytics_nl_translation(question_path, state_path, output_dir, provider)
    first_outputs = {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    second = run_analytics_nl_translation(question_path, state_path, output_dir, provider)
    intent = yaml.safe_load(first.intent_path.read_text(encoding="utf-8"))

    assert first.status == "ready_for_query_plan"
    assert first.provider_called is True
    assert first.adapter_result is not None
    assert first.adapter_result.request == {
        "version": 1,
        "question": "How many open orders exist by status?",
        "from": "physical_orders_private",
        "joins": [],
        "dimensions": [{"column": "physical_orders_private.private_status_column", "alias": "status"}],
        "metrics": [{"function": "count", "column": "*", "alias": "orders"}],
        "filters": [
            {
                "column": "physical_orders_private.private_status_column",
                "operator": "eq",
                "value": "open",
            }
        ],
        "order_by": [{"field": "orders", "direction": "desc"}],
        "limit": 20,
    }
    assert intent["question"] == "How many open orders exist by status?"
    assert second.outputs_changed is False
    assert first_outputs == {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_prompt_context_is_minimized_and_control_evidence_is_private(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    provider = CaptureProvider(provider_response())
    result = run_analytics_nl_translation(
        question_path,
        state_path,
        output_dir,
        provider,
        timeout_seconds=17,
    )
    assert result.status == "ready_for_query_plan"
    assert provider.prompt is not None
    assert provider.timeout_seconds == 17
    context = yaml.safe_dump(provider.prompt.semantic_context, sort_keys=True)
    assert "source_table" not in context
    assert "source_column" not in context
    assert "source_type" not in context
    assert "physical_orders_private" not in context
    assert "private_status_column" not in context
    assert "synthetic-reviewer" not in context
    assert "review-hash" not in context
    assert "sql" in provider.prompt.response_schema["forbidden"]

    for control_path in (result.manifest_path, result.blockers_path, result.report_path):
        control_text = control_path.read_text(encoding="utf-8")
        assert "How many open orders" not in control_text
        assert "open" not in control_text


def test_network_provider_requires_explicit_opt_in_and_is_not_called(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    provider = NetworkProvider(provider_response())
    result = run_analytics_nl_translation(question_path, state_path, output_dir, provider)

    assert result.status == "blocked"
    assert result.provider_called is False
    assert provider.calls == 0
    assert "network_provider_not_authorized" in blocker_types(result.blockers_path)


def test_explicit_network_opt_in_is_passed_only_to_injected_fake_provider(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    provider = NetworkProvider(provider_response())
    result = run_analytics_nl_translation(
        question_path,
        state_path,
        output_dir,
        provider,
        allow_network=True,
    )

    assert result.status == "ready_for_query_plan"
    assert provider.calls == 1
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["provider"]["network_authorized"] is True


@pytest.mark.parametrize(
    ("error", "expected_blocker"),
    [
        (TimeoutError("private timeout details"), "provider_timeout"),
        (RuntimeError("private provider details"), "provider_failure"),
    ],
)
def test_provider_failures_are_sanitized(
    tmp_path: Path,
    error: Exception,
    expected_blocker: str,
) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    result = run_analytics_nl_translation(
        question_path,
        state_path,
        output_dir,
        FailingProvider(error),
    )

    assert result.status == "blocked"
    assert result.intent_path is None
    assert expected_blocker in blocker_types(result.blockers_path)
    assert "private" not in result.blockers_path.read_text(encoding="utf-8")


def test_provider_cannot_replace_question_or_supply_sql_and_joins(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    response = provider_response()
    response["question"] = "Replace the local question"
    response["sql"] = "select * from private_table"
    response["joins"] = [{"source_table": "private_table"}]
    result = run_analytics_nl_translation(
        question_path,
        state_path,
        output_dir,
        CaptureProvider(response),
    )

    assert result.status == "blocked"
    assert result.intent_path is None
    assert {
        "provider_question_not_allowed",
        "provider_sql_not_allowed",
        "provider_physical_join_not_allowed",
    } <= blocker_types(result.blockers_path)
    assert "private_table" not in result.blockers_path.read_text(encoding="utf-8")


def test_ambiguous_provider_term_flows_to_adapter_clarification(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    response = provider_response()
    response["metrics"] = [{"term": "sales", "alias": "sales"}]
    response["order_by"] = [{"field": "sales", "direction": "desc"}]
    result = run_analytics_nl_translation(
        question_path,
        state_path,
        output_dir,
        CaptureProvider(response),
    )

    assert result.status == "clarification_required"
    assert result.blocker_count == 0
    assert result.clarification_count == 1
    assert result.intent_path is not None
    assert result.adapter_result is not None
    assert result.adapter_result.request_path is None
    assert result.adapter_result.clarifications_path.is_file()


def test_unapproved_state_blocks_before_provider_call(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    state = approved_state()
    state["approval"]["adapter_use_authorized"] = False
    write_yaml(state_path, state)
    provider = CaptureProvider(provider_response())
    result = run_analytics_nl_translation(question_path, state_path, output_dir, provider)

    assert result.status == "blocked"
    assert provider.calls == 0
    assert "semantic_adapter_not_authorized" in blocker_types(result.blockers_path)


def test_boolean_contract_version_is_rejected(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    response = provider_response()
    response["version"] = True
    result = run_analytics_nl_translation(
        question_path,
        state_path,
        output_dir,
        CaptureProvider(response),
    )

    assert result.status == "blocked"
    assert "unsupported_provider_response_version" in blocker_types(result.blockers_path)


def test_oversized_question_blocks_before_provider_call(tmp_path: Path) -> None:
    question_path, state_path, _, output_dir = build_fixture(tmp_path)
    question_path.write_text("x" * 20_000, encoding="utf-8")
    provider = CaptureProvider(provider_response())
    result = run_analytics_nl_translation(question_path, state_path, output_dir, provider)

    assert result.status == "blocked"
    assert provider.calls == 0
    assert "question_file_too_large" in blocker_types(result.blockers_path)


def test_translation_refuses_divergent_evidence_and_exposes_cli_contract(tmp_path: Path) -> None:
    question_path, state_path, response_path, output_dir = build_fixture(tmp_path)
    provider = RecordedSemanticIntentProvider(response_path)
    first = run_analytics_nl_translation(question_path, state_path, output_dir, provider)
    response = provider_response()
    response["limit"] = 5
    write_yaml(response_path, response)

    with pytest.raises(ValueError, match="existing generated evidence was not overwritten"):
        run_analytics_nl_translation(question_path, state_path, output_dir, provider)
    assert first.intent_path.is_file()

    args = build_parser().parse_args(
        [
            "analytics-nl-translate-recorded",
            "--question-file",
            "question.txt",
            "--semantic-state",
            "approved.yml",
            "--provider-response",
            "response.yml",
            "--output",
            "translation",
            "--timeout-seconds",
            "15",
        ]
    )
    assert args.command == "analytics-nl-translate-recorded"
    assert args.question_file == Path("question.txt")
    assert args.semantic_state == Path("approved.yml")
    assert args.provider_response == Path("response.yml")
    assert args.timeout_seconds == 15
