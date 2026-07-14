from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from data_ops_lab.analytics_translation_evaluation import (
    CASES_NAME,
    AnalyticsTranslationEvaluationResult,
    run_analytics_translation_evaluation,
)
from data_ops_lab.cli import build_parser
from data_ops_lab.source_onboarding import file_sha256


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "analytics_translation"
PACK_PATH = FIXTURE_DIR / "translation_evaluation_pack.yml"
STATE_PATH = FIXTURE_DIR / "approved_semantic_catalog.yml"


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: object) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def blocker_types(result: AnalyticsTranslationEvaluationResult) -> set[str]:
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def output_bytes(output_dir: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }


def test_synthetic_pack_passes_offline_without_persisting_sensitive_content(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evaluation"
    protected = {PACK_PATH: file_sha256(PACK_PATH), STATE_PATH: file_sha256(STATE_PATH)}

    first = run_analytics_translation_evaluation(PACK_PATH, STATE_PATH, output_dir)
    first_outputs = output_bytes(output_dir)
    second = run_analytics_translation_evaluation(PACK_PATH, STATE_PATH, output_dir)
    manifest = read_yaml(first.manifest_path)
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )

    assert first.status == "passed"
    assert first.case_count == 7
    assert first.passed_count == 7
    assert first.failed_count == 0
    assert first.blocker_count == 0
    assert manifest["metrics"] == {
        "overall": {"passed": 7, "evaluated": 7, "rate": 1.0},
        "status_accuracy": {"passed": 7, "evaluated": 7, "rate": 1.0},
        "semantic_intent_acceptance": {"passed": 3, "evaluated": 3, "rate": 1.0},
        "blocker_accuracy": {"passed": 7, "evaluated": 7, "rate": 1.0},
        "clarification_accuracy": {"passed": 7, "evaluated": 7, "rate": 1.0},
    }
    assert manifest["controls"] == {
        "network_accessed": False,
        "model_api_used": False,
        "database_accessed": False,
        "questions_persisted": False,
        "provider_responses_persisted": False,
        "physical_mappings_persisted": False,
    }
    assert "How many open orders exist by status?" not in persisted
    assert "SELECT COUNT(*)" not in persisted
    assert "physical_orders_private" not in persisted
    assert "private_status_column" not in persisted
    assert "synthetic provider details" not in persisted
    assert second.outputs_changed is False
    assert first_outputs == output_bytes(output_dir)
    assert all(file_sha256(path) == digest for path, digest in protected.items())


def test_semantic_expectation_mismatch_reports_failed_without_contract_blocker(
    tmp_path: Path,
) -> None:
    pack = read_yaml(PACK_PATH)
    equivalent = next(case for case in pack["cases"] if case["id"] == "equivalent_ready")
    accepted_intents = deepcopy(equivalent["expected"]["accepted_intents"])
    for intent in accepted_intents:
        intent["limit"] = 99
    equivalent["expected"]["accepted_intents"] = accepted_intents
    pack_path = tmp_path / "mismatched_pack.yml"
    write_yaml(pack_path, pack)

    result = run_analytics_translation_evaluation(pack_path, STATE_PATH, tmp_path / "evaluation")
    with result.cases_path.open(newline="", encoding="utf-8") as handle:
        rows = {row["case_id"]: row for row in csv.DictReader(handle)}

    assert result.status == "failed"
    assert result.case_count == 7
    assert result.passed_count == 6
    assert result.failed_count == 1
    assert result.blocker_count == 0
    assert rows["equivalent_ready"]["intent_match"] == "False"
    assert rows["equivalent_ready"]["passed"] == "False"


def test_invalid_pack_is_blocked_before_any_case_runs(tmp_path: Path) -> None:
    pack = read_yaml(PACK_PATH)
    pack["cases"][1]["id"] = pack["cases"][0]["id"]
    pack_path = tmp_path / "invalid_pack.yml"
    write_yaml(pack_path, pack)

    result = run_analytics_translation_evaluation(pack_path, STATE_PATH, tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert result.blocker_count == 1
    assert blocker_types(result) == {"duplicate_evaluation_case_id"}
    assert result.cases_path.read_text(encoding="utf-8").count("\n") == 1


def test_unapproved_semantic_state_blocks_pack_before_case_execution(tmp_path: Path) -> None:
    state = read_yaml(STATE_PATH)
    state["approval"]["adapter_use_authorized"] = False
    state_path = tmp_path / "unapproved_state.yml"
    write_yaml(state_path, state)

    result = run_analytics_translation_evaluation(PACK_PATH, state_path, tmp_path / "evaluation")

    assert result.status == "blocked"
    assert result.case_count == 0
    assert "semantic_adapter_not_authorized" in blocker_types(result)


def test_different_existing_evidence_is_not_overwritten(tmp_path: Path) -> None:
    output_dir = tmp_path / "evaluation"
    run_analytics_translation_evaluation(PACK_PATH, STATE_PATH, output_dir)
    protected = output_bytes(output_dir)
    (output_dir / CASES_NAME).write_text("different\n", encoding="utf-8")
    diverged = output_bytes(output_dir)

    with pytest.raises(ValueError, match="existing generated evidence was not overwritten"):
        run_analytics_translation_evaluation(PACK_PATH, STATE_PATH, output_dir)

    assert diverged == output_bytes(output_dir)
    assert diverged != protected


def test_cli_exposes_only_local_pack_state_and_output_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "analytics-translation-evaluate",
            "--pack",
            "pack.yml",
            "--semantic-state",
            "state.yml",
            "--output",
            "evidence",
        ]
    )

    assert args.command == "analytics-translation-evaluate"
    assert args.pack == Path("pack.yml")
    assert args.semantic_state == Path("state.yml")
    assert args.output == Path("evidence")
    assert not hasattr(args, "allow_network")
    assert not hasattr(args, "provider")
