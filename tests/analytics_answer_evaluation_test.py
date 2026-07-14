from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from data_ops_lab.analytics_answer_evaluation import (
    CASES_NAME,
    AnalyticsAnswerEvaluationResult,
    run_analytics_answer_evaluation,
)
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "analytics_answer_evaluation"
PACK_PATH = FIXTURE_DIR / "answer_evaluation_pack.yml"
STATE_PATH = FIXTURE_DIR / "approved_semantic_catalog.yml"


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: object) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def output_bytes(output_dir: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }


def blocker_types(result: AnalyticsAnswerEvaluationResult) -> set[str]:
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def case_rows(result: AnalyticsAnswerEvaluationResult) -> dict[str, dict[str, str]]:
    with result.cases_path.open(newline="", encoding="utf-8") as handle:
        return {row["case_id"]: row for row in csv.DictReader(handle)}


def test_synthetic_answer_pack_passes_end_to_end_without_persisting_case_content(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evaluation"
    protected = {PACK_PATH: file_sha256(PACK_PATH), STATE_PATH: file_sha256(STATE_PATH)}

    first = run_analytics_answer_evaluation(PACK_PATH, STATE_PATH, output_dir)
    first_outputs = output_bytes(output_dir)
    second = run_analytics_answer_evaluation(PACK_PATH, STATE_PATH, output_dir)
    manifest = read_yaml(first.manifest_path)
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )

    assert first.status == "passed"
    assert first.case_count == 5
    assert first.passed_count == 5
    assert first.failed_count == 0
    assert first.blocker_count == 0
    assert manifest["metrics"] == {
        "overall": {"passed": 5, "evaluated": 5, "rate": 1.0},
        "pipeline_accuracy": {"passed": 5, "evaluated": 5, "rate": 1.0},
        "request_accuracy": {"passed": 5, "evaluated": 5, "rate": 1.0},
        "result_exact_accuracy": {"passed": 5, "evaluated": 5, "rate": 1.0},
        "control_accuracy": {"passed": 5, "evaluated": 5, "rate": 1.0},
    }
    assert manifest["controls"]["database_setup_sql_accepted"] is False
    assert manifest["controls"]["expected_request_gate_required"] is True
    assert manifest["controls"]["stage_5b_revalidation_required"] is True
    assert "How many orders are in each status?" not in persisted
    assert "unavailable" not in persisted
    assert "30.50" not in persisted
    assert "synthetic_orders" not in persisted
    assert "provider_response" not in persisted
    assert not list(output_dir.rglob("*.duckdb"))
    assert second.outputs_changed is False
    assert first_outputs == output_bytes(output_dir)
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_expected_result_mismatch_reports_failed_without_contract_blocker(
    tmp_path: Path,
) -> None:
    pack = read_yaml(PACK_PATH)
    target = next(case for case in pack["cases"] if case["id"] == "filtered_total_amount")
    target["expected_result"]["rows"] = [["30.51"]]
    pack_path = tmp_path / "mismatched_answer.yml"
    write_yaml(pack_path, pack)

    result = run_analytics_answer_evaluation(pack_path, STATE_PATH, tmp_path / "evaluation")
    rows = case_rows(result)

    assert result.status == "failed"
    assert result.passed_count == 4
    assert result.failed_count == 1
    assert result.blocker_count == 0
    assert rows["filtered_total_amount"]["pipeline_match"] == "True"
    assert rows["filtered_total_amount"]["result_match"] == "False"
    assert rows["filtered_total_amount"]["passed"] == "False"


def test_request_mismatch_stops_before_planning_and_execution(tmp_path: Path) -> None:
    pack = read_yaml(PACK_PATH)
    target = next(case for case in pack["cases"] if case["id"] == "null_status_count")
    target["provider_response"] = deepcopy(target["provider_response"])
    target["provider_response"]["metrics"][0]["alias"] = "different_orders"
    pack_path = tmp_path / "request_mismatch.yml"
    write_yaml(pack_path, pack)

    result = run_analytics_answer_evaluation(pack_path, STATE_PATH, tmp_path / "evaluation")
    row = case_rows(result)["null_status_count"]

    assert result.status == "failed"
    assert row["translation_status"] == "ready_for_query_plan"
    assert row["request_match"] == "False"
    assert row["planning_status"] == "not_run"
    assert row["execution_status"] == "not_run"
    assert row["passed"] == "False"


def test_database_setup_sql_field_is_blocked_before_cases_run(tmp_path: Path) -> None:
    pack = read_yaml(PACK_PATH)
    pack["dataset"]["tables"][0]["sql"] = "DROP TABLE synthetic_orders"
    pack_path = tmp_path / "unsafe_setup.yml"
    write_yaml(pack_path, pack)

    result = run_analytics_answer_evaluation(pack_path, STATE_PATH, tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert "unsupported_answer_evaluation_field" in blocker_types(result)
    assert "DROP TABLE" not in result.report_path.read_text(encoding="utf-8")


def test_non_allowlisted_database_type_is_blocked_before_materialization(tmp_path: Path) -> None:
    pack = read_yaml(PACK_PATH)
    pack["dataset"]["tables"][0]["columns"][0]["type"] = "INTEGER); DROP TABLE x; --"
    pack_path = tmp_path / "unsafe_type.yml"
    write_yaml(pack_path, pack)

    result = run_analytics_answer_evaluation(pack_path, STATE_PATH, tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert "unsupported_synthetic_type" in blocker_types(result)


def test_unapproved_semantic_state_blocks_before_database_materialization(tmp_path: Path) -> None:
    state = read_yaml(STATE_PATH)
    state["approval"]["adapter_use_authorized"] = False
    state_path = tmp_path / "unapproved_state.yml"
    write_yaml(state_path, state)

    result = run_analytics_answer_evaluation(PACK_PATH, state_path, tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert "semantic_adapter_not_authorized" in blocker_types(result)


def test_different_existing_evidence_is_not_overwritten(tmp_path: Path) -> None:
    output_dir = tmp_path / "evaluation"
    run_analytics_answer_evaluation(PACK_PATH, STATE_PATH, output_dir)
    (output_dir / CASES_NAME).write_text("different\n", encoding="utf-8")
    protected = output_bytes(output_dir)

    with pytest.raises(ValueError, match="existing generated evidence was not overwritten"):
        run_analytics_answer_evaluation(PACK_PATH, STATE_PATH, output_dir)

    assert protected == output_bytes(output_dir)


def test_cli_exposes_only_pack_semantic_state_and_output_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "analytics-answer-evaluate",
            "--pack",
            "answer-pack.yml",
            "--semantic-state",
            "state.yml",
            "--output",
            "evidence",
        ]
    )

    assert args.command == "analytics-answer-evaluate"
    assert args.pack == Path("answer-pack.yml")
    assert args.semantic_state == Path("state.yml")
    assert args.output == Path("evidence")
    assert not hasattr(args, "database")
    assert not hasattr(args, "allow_network")
    assert not hasattr(args, "provider")
