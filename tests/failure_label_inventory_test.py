from __future__ import annotations

import importlib.util
from pathlib import Path

from data_ops_lab.contracts.error_taxonomy import (
    DIRECT_BLOCKER_REUSE_PROVENANCE,
    DYNAMIC_ERROR_CODE_PROVENANCE,
    ERROR_CLASSIFICATION_REGISTRY,
    EXCEPTION_FALLBACK_PROVENANCE,
    PROVIDER_EXCEPTION_TRANSLATION_PROVENANCE,
    REGISTERED_ERROR_CONSUMER_FILES,
    STANDARD_BLOCKER_FLOW_PROVENANCE,
    TEXT_STATUS_PROVENANCE,
    DynamicCodeSurface,
    TaxonomyDisposition,
)


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
blockers = list(candidate.blockers)
""".lstrip(),
        encoding="utf-8",
    )

    labels, dynamic = MODULE.inventory(source)

    assert set(labels) == {"approval_required", "authority_drift", "contract_invalid"}
    assert dynamic == ["src/data_ops_lab/sample.py:3"]
    assert labels["contract_invalid"] == {"src/data_ops_lab/sample.py:1"}
    assert MODULE.inventory_direct_blocker_reuses(source) == [
        "src/data_ops_lab/sample.py:4"
    ]


def test_dynamic_callsite_provenance_covers_the_inventory_exactly():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    _, dynamic = MODULE.inventory(root)

    assert set(DYNAMIC_ERROR_CODE_PROVENANCE) == set(dynamic)
    assert len(dynamic) == 10
    assert all(
        row.value_source and len(row.possible_codes) == len(set(row.possible_codes))
        for row in DYNAMIC_ERROR_CODE_PROVENANCE.values()
    )

    execution = DYNAMIC_ERROR_CODE_PROVENANCE[
        "src/data_ops_lab/analytics_query_execution.py:444"
    ]
    product = DYNAMIC_ERROR_CODE_PROVENANCE[
        "src/data_ops_lab/product_canonical_promotion.py:332"
    ]
    assert execution.surface is DynamicCodeSurface.EXCEPTION_CODE
    assert execution.disposition is TaxonomyDisposition.REGISTERED
    assert product.surface is DynamicCodeSurface.MODULE_SPECIFIC_BLOCKER
    assert product.disposition is TaxonomyDisposition.SEPARATE_RECORD_FORMAT


def test_direct_blocker_reuse_provenance_covers_the_inventory_exactly():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    direct_reuses = MODULE.inventory_direct_blocker_reuses(root)

    assert set(DIRECT_BLOCKER_REUSE_PROVENANCE) == set(direct_reuses)
    assert len(direct_reuses) == 2
    assert all(
        row.consumer_family == "dataset_benchmark"
        and row.record_format == "standard_blocker"
        and row.disposition is TaxonomyDisposition.REGISTERED
        for row in DIRECT_BLOCKER_REUSE_PROVENANCE.values()
    )


def test_live_provider_outcome_remains_a_separate_text_status_surface():
    location = "src/data_ops_lab/analytics_dataset_benchmark_live_evaluation.py:467"
    provenance = TEXT_STATUS_PROVENANCE[location]
    relative, line_text = location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == "def _provider_outcome(translation: Any) -> str:"
    assert provenance.consumer_family == "dataset_benchmark"
    assert provenance.output_field == "provider_outcome"
    assert provenance.status_values == (
        "accepted",
        "clarification",
        "provider_failure",
        "rejected",
        "timeout",
    )
    assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS


def test_translation_provider_exceptions_map_to_sanitized_blockers_separately():
    expected_lines = {
        "src/data_ops_lab/analytics_nl_translation.py:425": "        except TimeoutError:",
        "src/data_ops_lab/analytics_nl_translation.py:432": "        except Exception:",
    }

    assert set(PROVIDER_EXCEPTION_TRANSLATION_PROVENANCE) == set(expected_lines)
    for location, expected_line in expected_lines.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = PROVIDER_EXCEPTION_TRANSLATION_PROVENANCE[location]

        assert source_line == expected_line
        assert provenance.consumer_family == "natural_language_translation"
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE
        assert (
            ERROR_CLASSIFICATION_REGISTRY[provenance.persisted_blocker_code].value
            == "provider"
        )


def test_translation_family_contains_only_complete_standard_blocker_consumers():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["natural_language_translation"]
    family_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset(
        {
            "analytics_nl_translation.py",
            "analytics_translation_evaluation.py",
        }
    )
    assert "ollama_provider.py" not in consumer_files
    assert len(family_codes) == 46
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)

    expected_flow_lines = {
        "src/data_ops_lab/analytics_nl_translation.py:374": (
            '    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_nl_translation.py:375": (
            "    validate_approved_state(state, blockers)",
            "semantic_adapter",
        ),
        "src/data_ops_lab/analytics_nl_translation.py:445": (
            "        blockers.extend(adapter_blockers)",
            "semantic_adapter",
        ),
        "src/data_ops_lab/analytics_translation_evaluation.py:628": (
            '        pack = read_yaml_mapping(pack_path, blockers, "evaluation_pack")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_translation_evaluation.py:630": (
            '    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_translation_evaluation.py:631": (
            "    validate_approved_state(state, blockers)",
            "semantic_adapter",
        ),
    }
    translation_flows = {
        location: provenance
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "natural_language_translation"
    }
    assert set(translation_flows) == set(expected_flow_lines)
    for location, (expected_line, producer_family) in expected_flow_lines.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = translation_flows[location]

        assert source_line == expected_line
        assert provenance.consumer_family == "natural_language_translation"
        assert provenance.producer_family == producer_family
        assert producer_family in REGISTERED_ERROR_CONSUMER_FILES
        assert provenance.record_format == "standard_blocker"
        assert provenance.disposition is TaxonomyDisposition.REGISTERED


def test_translation_text_statuses_remain_separate_from_blocker_codes():
    expected = {
        "src/data_ops_lab/analytics_nl_translation.py:449": (
            "    status = (",
            "status",
            ("blocked", "clarification_required", "ready_for_query_plan"),
        ),
        "src/data_ops_lab/analytics_translation_evaluation.py:468": (
            '        observed_status = "evaluation_error"',
            "observed_status",
            (
                "blocked",
                "clarification_required",
                "evaluation_error",
                "ready_for_query_plan",
            ),
        ),
        "src/data_ops_lab/analytics_translation_evaluation.py:634": (
            '    status = "blocked" if blockers else "passed" '
            'if all(row["passed"] for row in rows) else "failed"',
            "status",
            ("blocked", "failed", "passed"),
        ),
    }

    for location, (expected_line, output_field, status_values) in expected.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = TEXT_STATUS_PROVENANCE[location]

        assert source_line == expected_line
        assert provenance.consumer_family == "natural_language_translation"
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)


def test_synthetic_answer_evaluation_is_a_complete_registered_consumer():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["synthetic_answer_evaluation"]
    family_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset({"analytics_answer_evaluation.py"})
    assert len(family_codes) == 49
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)

    expected_flow_lines = {
        "src/data_ops_lab/analytics_answer_evaluation.py:909": (
            '        pack = read_yaml_mapping(pack_path, blockers, "answer_pack")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_answer_evaluation.py:911": (
            '    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_answer_evaluation.py:912": (
            "    validate_approved_state(state, blockers)",
            "semantic_adapter",
        ),
    }
    family_flows = {
        location: provenance
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "synthetic_answer_evaluation"
    }
    assert set(family_flows) == set(expected_flow_lines)
    for location, (expected_line, producer_family) in expected_flow_lines.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_flows[location]

        assert source_line == expected_line
        assert provenance.producer_family == producer_family
        assert producer_family in REGISTERED_ERROR_CONSUMER_FILES
        assert provenance.record_format == "standard_blocker"
        assert provenance.disposition is TaxonomyDisposition.REGISTERED


def test_answer_evaluation_exceptions_and_statuses_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/analytics_answer_evaluation.py:931": (
            "            except (duckdb.Error, OSError, ValueError):",
            ("duckdb.Error", "OSError", "ValueError"),
            "standard_blocker",
            "blocker_type",
            "synthetic_dataset_materialization_failed",
        ),
        "src/data_ops_lab/analytics_answer_evaluation.py:952": (
            "                    except Exception:",
            ("Exception",),
            "text_status",
            "translation_status",
            "evaluation_error",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "synthetic_answer_evaluation"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, expected in expected_exceptions.items():
        expected_line, caught_exceptions, output_surface, output_field, output_value = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught_exceptions
        assert provenance.output_surface == output_surface
        assert provenance.output_field == output_field
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE

    assert ERROR_CLASSIFICATION_REGISTRY[
        "synthetic_dataset_materialization_failed"
    ].value == "unclassified"
    assert "evaluation_error" not in ERROR_CLASSIFICATION_REGISTRY

    expected_statuses = {
        "src/data_ops_lab/analytics_answer_evaluation.py:704": (
            "    translation_status = translation.status",
            "translation_status",
            ("blocked", "clarification_required", "evaluation_error", "ready_for_query_plan"),
        ),
        "src/data_ops_lab/analytics_answer_evaluation.py:707": (
            '    planning_status = "not_run"',
            "planning_status",
            ("blocked", "not_run", "ready_for_execution_review"),
        ),
        "src/data_ops_lab/analytics_answer_evaluation.py:708": (
            '    execution_status = "not_run"',
            "execution_status",
            ("blocked", "completed", "completed_no_rows", "not_run"),
        ),
        "src/data_ops_lab/analytics_answer_evaluation.py:968": (
            '    status = "blocked" if blockers else "passed" '
            'if all(row["passed"] for row in rows) else "failed"',
            "status",
            ("blocked", "failed", "passed"),
        ),
    }
    for location, (expected_line, output_field, status_values) in expected_statuses.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = TEXT_STATUS_PROVENANCE[location]

        assert source_line == expected_line
        assert provenance.consumer_family == "synthetic_answer_evaluation"
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)


def test_registry_covers_only_complete_registered_consumer_families():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    expected_codes: set[str] = set()

    for family, consumer_files in REGISTERED_ERROR_CONSUMER_FILES.items():
        family_codes = {
            label
            for label, locations in labels.items()
            if any(
                any(f"/{filename}:" in location for filename in consumer_files)
                for location in locations
            )
        }
        family_codes.update(
            code
            for row in DYNAMIC_ERROR_CODE_PROVENANCE.values()
            if row.consumer_family == family
            and row.disposition is TaxonomyDisposition.REGISTERED
            for code in row.possible_codes
        )
        expected_codes.update(family_codes)

    assert set(ERROR_CLASSIFICATION_REGISTRY) == expected_codes
    assert len(ERROR_CLASSIFICATION_REGISTRY) == 438
