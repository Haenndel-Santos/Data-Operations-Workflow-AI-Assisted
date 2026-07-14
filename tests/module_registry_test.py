from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from data_ops_lab.cli import build_parser
from data_ops_lab.module_registry import run_module_registry_validation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "config" / "orchestrator" / "analytics_module_registry.yml"


def load_registry() -> dict[str, object]:
    payload = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def write_registry(path: Path, payload: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def blocker_types(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["blocker_type"] for row in csv.DictReader(handle)}


def validate(path: Path, output: Path):
    return run_module_registry_validation(path, output, project_root=PROJECT_ROOT)


def test_versioned_registry_is_valid_static_and_idempotent(tmp_path: Path) -> None:
    registry_before = REGISTRY_PATH.read_bytes()
    result = validate(REGISTRY_PATH, tmp_path / "evidence")

    assert result.status == "valid"
    assert result.blocker_count == 0
    assert result.module_count == 8
    assert result.workflow_count == 2
    assert result.stage_count == 5
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["controls"]["entrypoints_inspected_statically"] is True
    assert manifest["controls"]["entrypoint_modules_imported"] is False
    assert manifest["controls"]["entrypoints_called"] is False
    assert manifest["controls"]["database_access"] is False
    assert REGISTRY_PATH.read_bytes() == registry_before

    repeated = validate(REGISTRY_PATH, tmp_path / "evidence")
    assert repeated.outputs_changed is False


def test_malformed_contracts_fail_closed_as_blockers(tmp_path: Path) -> None:
    payload = load_registry()
    payload["controls"]["dynamic_execution_enabled"] = True  # type: ignore[index]
    payload["modules"][0]["dependencies"] = [{"unsafe": "shape"}]  # type: ignore[index]
    payload["workflows"][0]["coordinator"] = []  # type: ignore[index]
    payload["workflows"][1]["gates"][0]["before_stage"] = []  # type: ignore[index]
    registry = tmp_path / "malformed.yml"
    write_registry(registry, payload)

    result = validate(registry, tmp_path / "evidence")

    assert result.status == "blocked"
    types = blocker_types(result.blockers_path)
    assert "unsafe_registry_controls" in types
    assert "invalid_string_list" in types
    assert "invalid_workflow_coordinator" in types
    assert "unsafe_workflow_gate" in types
    assert "missing_human_review_gate" in types


def test_entrypoint_signature_tests_and_dependency_cycles_are_validated(
    tmp_path: Path,
) -> None:
    payload = load_registry()
    payload["modules"][0]["inputs"] = ["wrong_parameter"]  # type: ignore[index]
    payload["modules"][0]["tests"] = ["tests/not_present.py"]  # type: ignore[index]
    payload["modules"][0]["dependencies"] = ["analytics_semantic_adapter"]  # type: ignore[index]
    registry = tmp_path / "drifted.yml"
    write_registry(registry, payload)

    result = validate(registry, tmp_path / "evidence")

    assert result.status == "blocked"
    types = blocker_types(result.blockers_path)
    assert "entrypoint_input_mismatch" in types
    assert "test_file_missing" in types
    assert "invalid_module_dependency" in types
    assert "module_dependency_cycle" in types


def test_workflow_order_and_execution_review_gate_are_mandatory(tmp_path: Path) -> None:
    payload = load_registry()
    payload["workflows"][0]["stages"][1]["depends_on"] = ["future_stage"]  # type: ignore[index]
    payload["workflows"][1]["gates"] = []  # type: ignore[index]
    registry = tmp_path / "unsafe_workflow.yml"
    write_registry(registry, payload)

    result = validate(registry, tmp_path / "evidence")

    assert result.status == "blocked"
    types = blocker_types(result.blockers_path)
    assert "invalid_stage_order" in types
    assert "missing_human_review_gate" in types


def test_divergent_registry_evidence_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    result = validate(REGISTRY_PATH, output)
    result.report_path.write_text("changed evidence\n", encoding="utf-8")

    with pytest.raises(ValueError, match="was not overwritten"):
        validate(REGISTRY_PATH, output)

    assert result.report_path.read_text(encoding="utf-8") == "changed evidence\n"


def test_registry_cli_exposes_validation_only() -> None:
    args = build_parser().parse_args(["analytics-module-registry-validate"])

    assert args.command == "analytics-module-registry-validate"
    assert args.registry == Path("config/orchestrator/analytics_module_registry.yml")
    assert args.project_root == Path(".")
    assert not hasattr(args, "execute")
    assert not hasattr(args, "allow_network")
    assert not hasattr(args, "apply")
