from __future__ import annotations

import importlib.util
from pathlib import Path

from data_ops_lab.contracts.error_taxonomy import ERROR_CLASSIFICATION_REGISTRY


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "inventory_failure_labels.py"
SPEC = importlib.util.spec_from_file_location("inventory_failure_labels", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_inventory_finds_literals_conditionals_and_dynamic_calls(tmp_path):
    source = tmp_path / "src" / "data_ops_lab"
    source.mkdir(parents=True)
    (source / "sample.py").write_text(
        """
add_blocker(rows, "contract_invalid", "explanation")
_add_blocker(rows, "authority_drift" if drift else "approval_required", "explanation")
add_blocker(rows, selected_label, "explanation")
""".lstrip(),
        encoding="utf-8",
    )

    labels, dynamic = MODULE.inventory(source)

    assert set(labels) == {"approval_required", "authority_drift", "contract_invalid"}
    assert dynamic == ["src/data_ops_lab/sample.py:3"]
    assert labels["contract_invalid"] == {"src/data_ops_lab/sample.py:1"}


def test_initial_registry_covers_the_standard_blocker_consumers():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = {
        "analytics_query_execution.py",
        "analytics_query_plan.py",
        "analytics_semantic_approval.py",
        "analytics_semantic_catalog.py",
    }
    consumer_labels = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert set(ERROR_CLASSIFICATION_REGISTRY) == consumer_labels
