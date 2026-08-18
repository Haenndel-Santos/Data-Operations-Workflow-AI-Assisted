from __future__ import annotations

import importlib.util
from pathlib import Path

from data_ops_lab.contracts.error_taxonomy import (
    APPROVAL_PROJECTION_PROVENANCE,
    AUTHORITY_BOUNDARY_PROVENANCE,
    BLOCKER_RECORD_FORMAT_PROVENANCE,
    CONTROL_TEXT_PROVENANCE,
    DIRECT_BLOCKER_CONSTRUCTION_PROVENANCE,
    DIRECT_BLOCKER_REUSE_PROVENANCE,
    DYNAMIC_ERROR_CODE_PROVENANCE,
    ERROR_CLASSIFICATION_REGISTRY,
    EXCEPTION_FALLBACK_PROVENANCE,
    PROVIDER_EXCEPTION_TRANSLATION_PROVENANCE,
    REGISTERED_ERROR_CONSUMER_FILES,
    STANDARD_BLOCKER_FLOW_PROVENANCE,
    TEXT_STATUS_PROVENANCE,
    DynamicCodeSurface,
    ErrorCategory,
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
    assert product.disposition is TaxonomyDisposition.REGISTERED


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


def test_result_presentation_narration_is_a_complete_registered_family():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES[
        "result_presentation_narration"
    ]
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
            "analytics_result_narration.py",
            "analytics_result_presentation.py",
        }
    )
    assert len(family_codes) == 41
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)

    expected_flow_lines = {
        "src/data_ops_lab/analytics_result_presentation.py:520": (
            '    request = read_yaml_mapping(request_path, blockers, "request")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_result_presentation.py:521": (
            "    execution_manifest = read_yaml_mapping(",
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_result_narration.py:459": (
            "    presentation_manifest = read_yaml_mapping(",
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_result_narration.py:464": (
            '    facts_bundle = read_yaml_mapping(facts_path, blockers, "facts")',
            "standard_analytics",
        ),
    }
    family_flows = {
        location: provenance
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "result_presentation_narration"
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


def test_result_presentation_narration_exceptions_and_statuses_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/analytics_result_presentation.py:269": (
            "    except (OSError, UnicodeError, csv.Error):",
            ("OSError", "UnicodeError", "csv.Error"),
            "invalid_result_csv",
        ),
        "src/data_ops_lab/analytics_result_narration.py:514": (
            "        except TimeoutError:",
            ("TimeoutError",),
            "provider_timeout",
        ),
        "src/data_ops_lab/analytics_result_narration.py:516": (
            "        except Exception:",
            ("Exception",),
            "provider_failure",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "result_presentation_narration"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, expected in expected_exceptions.items():
        expected_line, caught_exceptions, output_value = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught_exceptions
        assert provenance.output_surface == "standard_blocker"
        assert provenance.output_field == "blocker_type"
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE
        assert output_value in ERROR_CLASSIFICATION_REGISTRY

    expected_statuses = {
        "src/data_ops_lab/analytics_result_presentation.py:369": (
            '        "status": "ready_for_recorded_narration",',
            "facts.status",
            ("ready_for_recorded_narration",),
        ),
        "src/data_ops_lab/analytics_result_presentation.py:544": (
            '    status = "blocked" if blockers else "ready_for_recorded_narration"',
            "status",
            ("blocked", "ready_for_recorded_narration"),
        ),
        "src/data_ops_lab/analytics_result_narration.py:535": (
            '    status = "blocked" if blockers else "ready_for_user"',
            "status",
            ("blocked", "ready_for_user"),
        ),
    }
    for location, (expected_line, output_field, status_values) in expected_statuses.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = TEXT_STATUS_PROVENANCE[location]

        assert source_line == expected_line
        assert provenance.consumer_family == "result_presentation_narration"
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)


def test_analytics_session_is_a_complete_registered_family():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["analytics_session"]
    family_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset({"analytics_session.py"})
    assert len(family_codes) == 23
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)

    expected_flow_lines = {
        "src/data_ops_lab/analytics_session.py:460": (
            '    prepare = read_yaml_mapping(prepare_manifest_path, blockers, "prepare_manifest")',
            "standard_analytics",
        ),
        "src/data_ops_lab/analytics_session.py:620": (
            '    review = read_yaml_mapping(review_path, blockers, "review")',
            "standard_analytics",
        ),
    }
    family_flows = {
        location: provenance
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "analytics_session"
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


def test_analytics_session_exceptions_and_statuses_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/analytics_session.py:108": (
            "    except ValueError:",
            ("ValueError",),
            "artifact_metadata",
            "path",
            "",
        ),
        "src/data_ops_lab/analytics_session.py:443": (
            "    except ValueError:",
            ("ValueError",),
            "standard_blocker",
            "blocker_type",
            "invalid_execution_review_time",
        ),
        "src/data_ops_lab/analytics_session.py:574": (
            "    except (OSError, UnicodeError, yaml.YAMLError) as error:",
            ("OSError", "UnicodeError", "yaml.YAMLError"),
            "exception",
            "exception_type",
            "ValueError",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "analytics_session"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, expected in expected_exceptions.items():
        expected_line, caught, output_surface, output_field, output_value = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught
        assert provenance.output_surface == output_surface
        assert provenance.output_field == output_field
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE

    assert "invalid_execution_review_time" in ERROR_CLASSIFICATION_REGISTRY
    assert "ValueError" not in ERROR_CLASSIFICATION_REGISTRY

    expected_statuses = {
        "src/data_ops_lab/analytics_session.py:188": (
            '        "status": "pending_review",',
            "review_template.status",
            ("pending_review",),
        ),
        "src/data_ops_lab/analytics_session.py:196": (
            '            "decision": "pending",',
            "review_template.review.decision",
            ("pending",),
        ),
        "src/data_ops_lab/analytics_session.py:271": (
            '        status = "clarification_required"',
            "prepare.status",
            ("awaiting_execution_review", "blocked", "clarification_required"),
        ),
        "src/data_ops_lab/analytics_session.py:298": (
            '                "status": translation_result.status,',
            "prepare.stages.translation.status",
            ("blocked", "clarification_required", "ready_for_query_plan"),
        ),
        "src/data_ops_lab/analytics_session.py:302": (
            '                "status": plan_result.status if plan_result else "not_started",',
            "prepare.stages.query_plan.status",
            ("blocked", "not_started", "ready_for_execution_review"),
        ),
        "src/data_ops_lab/analytics_session.py:305": (
            '            "query_execution": {"status": "not_authorized"},',
            "prepare.stages.query_execution.status",
            ("not_authorized",),
        ),
        "src/data_ops_lab/analytics_session.py:306": (
            '            "result_presentation": {"status": "not_started"},',
            "prepare.stages.result_presentation.status",
            ("not_started",),
        ),
        "src/data_ops_lab/analytics_session.py:307": (
            '            "result_narration": {"status": "not_started"},',
            "prepare.stages.result_narration.status",
            ("not_started",),
        ),
        "src/data_ops_lab/analytics_session.py:635": (
            '    last_valid_checkpoint = "execution_review" '
            'if review_validated else "prepare"',
            "last_valid_checkpoint",
            (
                "execution_review",
                "prepare",
                "query_execution",
                "result_narration",
                "result_presentation",
            ),
        ),
        "src/data_ops_lab/analytics_session.py:699": (
            '    status = "completed" if not blockers else "blocked"',
            "resume.status",
            ("blocked", "completed"),
        ),
        "src/data_ops_lab/analytics_session.py:702": (
            '        "execution_review": '
            '{"status": "approved" if review_validated else "blocked"},',
            "resume.stages.execution_review.status",
            ("approved", "blocked"),
        ),
        "src/data_ops_lab/analytics_session.py:704": (
            '            "status": execution_result.status '
            'if execution_result else "not_started",',
            "resume.stages.query_execution.status",
            ("blocked", "completed", "completed_no_rows", "not_started"),
        ),
        "src/data_ops_lab/analytics_session.py:708": (
            '            "status": presentation_result.status '
            'if presentation_result else "not_started",',
            "resume.stages.result_presentation.status",
            ("blocked", "not_started", "ready_for_recorded_narration"),
        ),
        "src/data_ops_lab/analytics_session.py:714": (
            '            "status": narration_result.status '
            'if narration_result else "not_started",',
            "resume.stages.result_narration.status",
            ("blocked", "not_started", "ready_for_user"),
        ),
    }
    family_statuses = {
        location: provenance
        for location, provenance in TEXT_STATUS_PROVENANCE.items()
        if provenance.consumer_family == "analytics_session"
    }
    assert set(family_statuses) == set(expected_statuses)
    for location, (expected_line, output_field, status_values) in expected_statuses.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_statuses[location]

        assert source_line == expected_line
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)


def test_module_registry_is_a_complete_registered_family():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["module_registry"]
    family_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset({"module_registry.py"})
    assert len(family_codes) == 49
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)
    assert not {
        location
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "module_registry"
    }


def test_module_registry_exceptions_and_status_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/module_registry.py:114": (
            "    except OSError:",
            ("OSError",),
            "registry_unreadable",
        ),
        "src/data_ops_lab/module_registry.py:127": (
            "    except (OSError, UnicodeError, yaml.YAMLError):",
            ("OSError", "UnicodeError", "yaml.YAMLError"),
            "invalid_registry_yaml",
        ),
        "src/data_ops_lab/module_registry.py:208": (
            "    except (ImportError, AttributeError, ModuleNotFoundError, ValueError):",
            ("ImportError", "AttributeError", "ModuleNotFoundError", "ValueError"),
            "entrypoint_not_resolvable",
        ),
        "src/data_ops_lab/module_registry.py:223": (
            "    except (OSError, UnicodeError, SyntaxError):",
            ("OSError", "UnicodeError", "SyntaxError"),
            "entrypoint_source_unreadable",
        ),
        "src/data_ops_lab/module_registry.py:736": (
            "    except OSError:",
            ("OSError",),
            "registry_unreadable",
        ),
        "src/data_ops_lab/module_registry.py:772": (
            "    except OSError:",
            ("OSError",),
            "registry_changed_during_validation",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "module_registry"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, (expected_line, caught, output_value) in expected_exceptions.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught
        assert provenance.output_surface == "standard_blocker"
        assert provenance.output_field == "blocker_type"
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE
        assert output_value in ERROR_CLASSIFICATION_REGISTRY

    status_location = "src/data_ops_lab/module_registry.py:781"
    status = TEXT_STATUS_PROVENANCE[status_location]
    relative, line_text = status_location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == '    status = "valid" if not blockers else "blocked"'
    assert status.consumer_family == "module_registry"
    assert status.output_field == "status"
    assert status.status_values == ("blocked", "valid")
    assert status.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
    assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status.status_values)


def test_ollama_soak_is_a_complete_family_with_a_separate_record_format():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["ollama_soak"]
    family_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset({"analytics_ollama_soak.py"})
    assert len(family_codes) == 21
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)
    assert not {
        location
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "ollama_soak"
    }

    location = "src/data_ops_lab/analytics_ollama_soak.py:132"
    provenance = BLOCKER_RECORD_FORMAT_PROVENANCE[location]
    relative, line_text = location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == "    blockers.append("
    assert provenance.consumer_family == "ollama_soak"
    assert provenance.output_surface == "manifest.contract_blockers"
    assert provenance.record_format == "ollama_soak_embedded_blocker_v1"
    assert provenance.record_fields == (
        "blocker_id",
        "blocker_type",
        "field",
        "explanation",
    )
    assert provenance.identifier_format == "blocker_{ordinal:03d}"
    assert provenance.disposition is TaxonomyDisposition.SEPARATE_RECORD_FORMAT


def test_ollama_soak_exceptions_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/analytics_ollama_soak.py:161": (
            "    except (OSError, UnicodeError, yaml.YAMLError):",
            ("OSError", "UnicodeError", "yaml.YAMLError"),
            "authorization_payload",
            "mapping",
            "empty_mapping",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:195": (
            "    except ValueError:",
            ("ValueError",),
            "module_specific_blocker",
            "blocker_type",
            "ollama_soak_authorized_at_invalid",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:296": (
            "    except KeyError:",
            ("KeyError",),
            "module_specific_blocker",
            "blocker_type",
            "ollama_soak_policy_incomplete",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:395": (
            "    except ValueError:",
            ("ValueError",),
            "module_specific_blocker",
            "blocker_type",
            "ollama_soak_provider_not_loopback",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:530": (
            "    except (AttributeError, OSError, ValueError):",
            ("AttributeError", "OSError", "ValueError"),
            "resource_sample",
            "process_memory",
            "partial_unavailable_process_memory",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:572": (
            "    except (FileNotFoundError, OSError, subprocess.SubprocessError, ValueError):",
            ("FileNotFoundError", "OSError", "subprocess.SubprocessError", "ValueError"),
            "resource_sample",
            "gpu_telemetry",
            "unavailable_gpu_telemetry",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:577": (
            "    except OSError:",
            ("OSError",),
            "resource_sample",
            "disk_free_mb",
            "unavailable_disk_free_mb",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:630": (
            "    except (OSError, UnicodeError, yaml.YAMLError):",
            ("OSError", "UnicodeError", "yaml.YAMLError"),
            "cycle_summary",
            "manifest",
            "empty_mapping",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:641": (
            "    except (OSError, UnicodeError):",
            ("OSError", "UnicodeError"),
            "cycle_summary",
            "cases",
            "empty_list",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:1209": (
            "            except Exception as error:",
            ("Exception",),
            "cycle_text",
            "failure_type",
            "<exception_class_name>",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "ollama_soak"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, expected in expected_exceptions.items():
        expected_line, caught, output_surface, output_field, output_value = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught
        assert provenance.output_surface == output_surface
        assert provenance.output_field == output_field
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE
        if output_field == "blocker_type":
            assert output_value in ERROR_CLASSIFICATION_REGISTRY

    assert "<exception_class_name>" not in ERROR_CLASSIFICATION_REGISTRY


def test_ollama_soak_status_and_control_text_remain_separate():
    expected_statuses = {
        "src/data_ops_lab/analytics_ollama_soak.py:669": (
            '        "status": result.status if result is not None else "evaluation_error",',
            "cycle.status",
            ("blocked", "evaluation_error", "failed", "passed"),
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:829": (
            '        "status": status,',
            "status",
            (
                "blocked",
                "completed",
                "ready_for_overnight_soak",
                "running",
                "stopped_by_request",
                "stopped_error_limit",
                "stopped_provider_timeout",
                "stopped_resource_guard",
            ),
        ),
    }
    family_statuses = {
        location: provenance
        for location, provenance in TEXT_STATUS_PROVENANCE.items()
        if provenance.consumer_family == "ollama_soak"
    }
    assert set(family_statuses) == set(expected_statuses)
    for location, (expected_line, output_field, status_values) in expected_statuses.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_statuses[location]

        assert source_line == expected_line
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)

    expected_controls = {
        "src/data_ops_lab/analytics_ollama_soak.py:830": (
            '        "mode": mode,',
            "mode",
        ),
        "src/data_ops_lab/analytics_ollama_soak.py:858": (
            '            "stop_reason": stop_reason,',
            "runtime.stop_reason",
        ),
    }
    family_controls = {
        location: provenance
        for location, provenance in CONTROL_TEXT_PROVENANCE.items()
        if provenance.consumer_family == "ollama_soak"
    }
    assert set(family_controls) == set(expected_controls)
    for location, (expected_line, output_field) in expected_controls.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_controls[location]

        assert source_line == expected_line
        assert provenance.output_field == output_field
        assert provenance.value_domain
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_CONTROL_TEXT

    assert all(
        value not in ERROR_CLASSIFICATION_REGISTRY
        for value in (
            "dry-run",
            "live",
            "stop_file_detected",
            "gpu_temperature_limit_reached",
        )
    )


def test_reference_dataset_validation_is_a_complete_family_with_a_local_format():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, dynamic = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES[
        "reference_dataset_validation"
    ]
    family_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset({"reference_dataset_validation.py"})
    assert len(family_codes) == 79
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)
    assert not [
        location
        for location in dynamic
        if "/reference_dataset_validation.py:" in location
    ]
    assert not {
        location
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "reference_dataset_validation"
    }

    location = "src/data_ops_lab/reference_dataset_validation.py:67"
    provenance = BLOCKER_RECORD_FORMAT_PROVENANCE[location]
    relative, line_text = location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == (
        '    blockers.append({"code": code, "message": message, "field": field})'
    )
    assert provenance.consumer_family == "reference_dataset_validation"
    assert provenance.output_surface == "manifest.blockers"
    assert provenance.record_format == "reference_dataset_blocker_v1"
    assert provenance.record_fields == ("code", "message", "field")
    assert provenance.identifier_format is None
    assert provenance.disposition is TaxonomyDisposition.SEPARATE_RECORD_FORMAT


def test_reference_dataset_validation_exceptions_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/reference_dataset_validation.py:76": (
            "    except (OSError, UnicodeError, yaml.YAMLError):",
            ("OSError", "UnicodeError", "yaml.YAMLError"),
            "module_specific_blocker",
            "code",
            "invalid_yaml",
        ),
        "src/data_ops_lab/reference_dataset_validation.py:293": (
            "    except ValueError:",
            ("ValueError",),
            "module_specific_blocker",
            "code",
            "invalid_benchmark_approval_time",
        ),
        "src/data_ops_lab/reference_dataset_validation.py:582": (
            "    except duckdb.Error:",
            ("duckdb.Error",),
            "module_specific_blocker",
            "code",
            "database_unreadable",
        ),
        "src/data_ops_lab/reference_dataset_validation.py:640": (
            "        except ValueError:",
            ("ValueError",),
            "module_specific_blocker",
            "code",
            "invalid_review_time",
        ),
        "src/data_ops_lab/reference_dataset_validation.py:837": (
            "    except Exception:",
            ("Exception",),
            "exception",
            "failure_policy",
            "cleanup_staging_and_reraise",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "reference_dataset_validation"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, expected in expected_exceptions.items():
        expected_line, caught, output_surface, output_field, output_value = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught
        assert provenance.output_surface == output_surface
        assert provenance.output_field == output_field
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE
        if output_field == "code":
            assert output_value in ERROR_CLASSIFICATION_REGISTRY

    assert "cleanup_staging_and_reraise" not in ERROR_CLASSIFICATION_REGISTRY


def test_reference_dataset_statuses_and_approval_projection_remain_separate():
    expected_statuses = {
        "src/data_ops_lab/reference_dataset_validation.py:222": (
            "def conversion_projection(manifest: dict[str, Any]) -> dict[str, Any]:",
            "conversion_projection.status",
            ("ready_for_local_benchmark",),
        ),
        "src/data_ops_lab/reference_dataset_validation.py:590": (
            "def validate_completed_review(",
            "relationships.review_status",
            ("completed", "incomplete", "invalid", "pending_review"),
        ),
        "src/data_ops_lab/reference_dataset_validation.py:705": (
            '        "status": "pending_review",',
            "relationship_review.status",
            ("pending_review",),
        ),
        "src/data_ops_lab/reference_dataset_validation.py:694": (
            '                "decision": "pending",',
            "relationship_review.decisions[].decision",
            ("accepted", "pending", "rejected"),
        ),
        "src/data_ops_lab/reference_dataset_validation.py:768": (
            '        "status": "approved" if authority_complete else "pending_review",',
            "approved_relationships.status",
            ("approved", "pending_review"),
        ),
        "src/data_ops_lab/reference_dataset_validation.py:914": (
            '        "status": status,',
            "status",
            (
                "blocked",
                "ready_for_relationship_review",
                "ready_for_semantic_modeling",
            ),
        ),
    }
    family_statuses = {
        location: provenance
        for location, provenance in TEXT_STATUS_PROVENANCE.items()
        if provenance.consumer_family == "reference_dataset_validation"
    }
    assert set(family_statuses) == set(expected_statuses)
    for location, (expected_line, output_field, status_values) in expected_statuses.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_statuses[location]

        assert source_line == expected_line
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)

    location = "src/data_ops_lab/reference_dataset_validation.py:734"
    projection = APPROVAL_PROJECTION_PROVENANCE[location]
    relative, line_text = location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == (
        '    authority_complete = status == "ready_for_semantic_modeling"'
    )
    assert projection.consumer_family == "reference_dataset_validation"
    assert projection.output_surface == "approved_relationships.yml"
    assert projection.authority_gate == "status == 'ready_for_semantic_modeling'"
    assert projection.decision_domain == ("accepted", "rejected")
    assert projection.projected_fields == (
        "status",
        "authority.completed_review_sha256",
        "authority.derived_from_completed_human_review",
        "authority.automatic_approval",
        "authority.scope",
        "approved_relationships",
        "rejected_relationship_ids",
    )
    assert projection.disposition is TaxonomyDisposition.SEPARATE_APPROVAL_PROJECTION


def test_product_canonical_promotion_is_a_complete_family_with_artifact_blockers():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, _ = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES[
        "product_canonical_promotion"
    ]
    literal_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }
    dynamic = DYNAMIC_ERROR_CODE_PROVENANCE[
        "src/data_ops_lab/product_canonical_promotion.py:332"
    ]
    family_codes = literal_codes | set(dynamic.possible_codes)

    assert consumer_files == frozenset({"product_canonical_promotion.py"})
    assert len(literal_codes) == 19
    assert len(family_codes) == 24
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)
    assert dynamic.consumer_family == "product_canonical_promotion"
    assert dynamic.surface is DynamicCodeSurface.MODULE_SPECIFIC_BLOCKER
    assert dynamic.disposition is TaxonomyDisposition.REGISTERED
    assert not {
        location
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "product_canonical_promotion"
    }

    location = "src/data_ops_lab/product_canonical_promotion.py:83"
    provenance = BLOCKER_RECORD_FORMAT_PROVENANCE[location]
    relative, line_text = location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == "    blockers.append("
    assert provenance.consumer_family == "product_canonical_promotion"
    assert provenance.output_surface == (
        "plan.blockers + product_canonical_promotion_blockers.csv"
    )
    assert provenance.record_format == (
        "product_canonical_promotion_artifact_blocker_v1"
    )
    assert provenance.record_fields == (
        "blocker_id",
        "blocker_type",
        "artifact",
        "explanation",
    )
    assert provenance.identifier_format == "BLOCKER_{ordinal:03d}"
    assert provenance.disposition is TaxonomyDisposition.SEPARATE_RECORD_FORMAT


def test_product_canonical_promotion_exceptions_remain_separate():
    expected_exceptions = {
        "src/data_ops_lab/product_canonical_promotion.py:108": (
            "    except yaml.YAMLError:",
            ("yaml.YAMLError",),
            "module_specific_blocker",
            "blocker_type",
            "invalid_yaml",
        ),
        "src/data_ops_lab/product_canonical_promotion.py:135": (
            "    except (ValueError, AttributeError):",
            ("ValueError", "AttributeError"),
            "integrity_predicate",
            "valid_uuid5",
            "false",
        ),
        "src/data_ops_lab/product_canonical_promotion.py:145": (
            "    except (TypeError, ValueError):",
            ("TypeError", "ValueError"),
            "manifest_count_parser",
            "integer_value",
            "none",
        ),
        "src/data_ops_lab/product_canonical_promotion.py:276": (
            "        except (csv.Error, OSError, UnicodeError):",
            ("csv.Error", "OSError", "UnicodeError"),
            "module_specific_blocker",
            "blocker_type",
            "invalid_csv",
        ),
    }
    family_exceptions = {
        location: provenance
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "product_canonical_promotion"
    }
    assert set(family_exceptions) == set(expected_exceptions)
    for location, expected in expected_exceptions.items():
        expected_line, caught, output_surface, output_field, output_value = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_exceptions[location]

        assert source_line == expected_line
        assert provenance.value_source
        assert provenance.caught_exceptions == caught
        assert provenance.output_surface == output_surface
        assert provenance.output_field == output_field
        assert provenance.output_value == output_value
        assert provenance.exception_message_persisted is False
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE
        if output_field == "blocker_type":
            assert output_value in ERROR_CLASSIFICATION_REGISTRY

    assert "false" not in ERROR_CLASSIFICATION_REGISTRY
    assert "none" not in ERROR_CLASSIFICATION_REGISTRY


def test_product_canonical_status_and_apply_authority_remain_separate():
    expected_statuses = {
        "src/data_ops_lab/product_canonical_promotion.py:212": (
            '    if state.get("status") != "applied":',
            "product_reconciliation_state.status",
            ("applied",),
        ),
        "src/data_ops_lab/product_canonical_promotion.py:227": (
            '    if manifest.get("status") != "ready_for_local_preview":',
            "materialization_manifest.status",
            ("ready_for_local_preview",),
        ),
        "src/data_ops_lab/product_canonical_promotion.py:397": (
            '    status = "blocked" if blockers else "ready_for_canonical_state_review"',
            "plan.status",
            ("blocked", "ready_for_canonical_state_review"),
        ),
    }
    family_statuses = {
        location: provenance
        for location, provenance in TEXT_STATUS_PROVENANCE.items()
        if provenance.consumer_family == "product_canonical_promotion"
    }
    assert set(family_statuses) == set(expected_statuses)
    for location, (expected_line, output_field, status_values) in expected_statuses.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_statuses[location]

        assert source_line == expected_line
        assert provenance.output_field == output_field
        assert provenance.status_values == status_values
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status_values)

    location = "src/data_ops_lab/product_canonical_promotion.py:444"
    authority = AUTHORITY_BOUNDARY_PROVENANCE[location]
    relative, line_text = location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]

    assert source_line == '        "approval": {'
    assert authority.consumer_family == "product_canonical_promotion"
    assert authority.output_surface == "plan.approval"
    assert authority.authority_values == (
        "canonical_state_applied=false",
        "database_operation_authorized=false",
        "requires_explicit_apply_contract=true",
    )
    assert authority.required_next_authority == (
        "a separate explicit canonical-state apply contract"
    )
    assert authority.disposition is TaxonomyDisposition.SEPARATE_AUTHORITY_BOUNDARY


def test_product_materialization_is_a_complete_family_with_local_blocker_formats():
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, dynamic_sites = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["product_materialization"]
    literal_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }
    direct_constructions = {
        location: provenance
        for location, provenance in DIRECT_BLOCKER_CONSTRUCTION_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }
    family_codes = literal_codes | {
        code
        for provenance in direct_constructions.values()
        for code in provenance.possible_codes
    }

    assert consumer_files == frozenset({"product_materialization.py"})
    assert len(literal_codes) == 15
    assert len(family_codes) == 16
    assert family_codes <= set(ERROR_CLASSIFICATION_REGISTRY)
    assert not {
        location
        for location in dynamic_sites
        if "/product_materialization.py:" in location
    }
    assert not {
        location
        for location, provenance in STANDARD_BLOCKER_FLOW_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }
    assert not {
        location
        for location, provenance in DIRECT_BLOCKER_REUSE_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }

    construction_location = "src/data_ops_lab/product_materialization.py:145"
    assert set(direct_constructions) == {construction_location}
    construction = direct_constructions[construction_location]
    relative, line_text = construction_location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
    assert source_line == "            blockers.append("
    assert construction.possible_codes == ("invalid_source_identifier_count",)
    assert construction.record_format == "product_materialization_candidate_blocker_v1"
    assert construction.disposition is TaxonomyDisposition.REGISTERED

    expected_formats = {
        "src/data_ops_lab/product_materialization.py:174": (
            "    blockers.append(",
            "internal materialization blocker candidates",
            "product_materialization_candidate_blocker_v1",
            ("issue_ids", "source_identifier", "blocker_type", "explanation"),
            None,
        ),
        "src/data_ops_lab/product_materialization.py:223": (
            "        normalized.append(",
            "manifest.blockers + product_materialization_blockers.csv",
            "product_materialization_blocker_v1",
            (
                "blocker_id",
                "issue_ids",
                "source_identifier",
                "blocker_type",
                "explanation",
            ),
            "BLOCKER_{ordinal:03d}",
        ),
    }
    family_formats = {
        location: provenance
        for location, provenance in BLOCKER_RECORD_FORMAT_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }
    assert set(family_formats) == set(expected_formats)
    for location, expected in expected_formats.items():
        expected_line, output_surface, record_format, record_fields, identifier = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_formats[location]

        assert source_line == expected_line
        assert provenance.output_surface == output_surface
        assert provenance.record_format == record_format
        assert provenance.record_fields == record_fields
        assert provenance.identifier_format == identifier
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_RECORD_FORMAT


def test_product_materialization_status_controls_and_authority_remain_separate():
    family_exceptions = {
        location
        for location, provenance in EXCEPTION_FALLBACK_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }
    assert not family_exceptions
    assert not {
        location
        for location, provenance in PROVIDER_EXCEPTION_TRANSLATION_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }

    status_location = "src/data_ops_lab/product_materialization.py:649"
    status = TEXT_STATUS_PROVENANCE[status_location]
    relative, line_text = status_location.rsplit(":", 1)
    source_line = (
        Path(__file__).parents[1] / relative
    ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
    assert source_line == '    status = "blocked" if blockers else "ready_for_local_preview"'
    assert status.consumer_family == "product_materialization"
    assert status.output_field == "manifest.status"
    assert status.status_values == ("blocked", "ready_for_local_preview")
    assert status.disposition is TaxonomyDisposition.SEPARATE_TEXT_STATUS
    assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in status.status_values)

    expected_controls = {
        "src/data_ops_lab/product_materialization.py:48": (
            'SUPPORTED_RETAIN_ACTION = "apply_corrected_product_ref_nr"',
            "applied_decision.action",
        ),
        "src/data_ops_lab/product_materialization.py:427": (
            '                "materialization_action": action,',
            "lineage.materialization_action",
        ),
    }
    family_controls = {
        location: provenance
        for location, provenance in CONTROL_TEXT_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }
    assert set(family_controls) == set(expected_controls)
    for location, (expected_line, output_field) in expected_controls.items():
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_controls[location]

        assert source_line == expected_line
        assert provenance.output_field == output_field
        assert provenance.value_domain
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_CONTROL_TEXT
        assert provenance.value_domain not in ERROR_CLASSIFICATION_REGISTRY

    expected_authority = {
        "src/data_ops_lab/product_materialization.py:127": (
            "    if applied_state != expected_state:",
            "materialization_preflight",
            ("applied_state_matches_validated_workbook=true",),
            "the exact applied Product reconciliation state",
        ),
        "src/data_ops_lab/product_materialization.py:662": (
            '        "contract": {',
            "manifest.contract",
            ("exclusion_precedence=true", "preview_only=true"),
            "separate canonical-promotion review and explicit apply contracts",
        ),
    }
    family_authority = {
        location: provenance
        for location, provenance in AUTHORITY_BOUNDARY_PROVENANCE.items()
        if provenance.consumer_family == "product_materialization"
    }
    assert set(family_authority) == set(expected_authority)
    for location, expected in expected_authority.items():
        expected_line, output_surface, authority_values, next_authority = expected
        relative, line_text = location.rsplit(":", 1)
        source_line = (
            Path(__file__).parents[1] / relative
        ).read_text(encoding="utf-8").splitlines()[int(line_text) - 1]
        provenance = family_authority[location]

        assert source_line == expected_line
        assert provenance.output_surface == output_surface
        assert provenance.authority_values == authority_values
        assert provenance.required_next_authority == next_authority
        assert provenance.disposition is TaxonomyDisposition.SEPARATE_AUTHORITY_BOUNDARY
        assert all(value not in ERROR_CLASSIFICATION_REGISTRY for value in authority_values)


def test_governed_cleaning_is_a_complete_family_of_literal_standard_blockers():
    """The governed cleaning contract emits only literal standard blockers
    through the shared add_blocker helper: no dynamic codes, no direct dict
    construction, no reuse of foreign blocker rows, no separate text status."""
    root = Path(__file__).parents[1] / "src" / "data_ops_lab"
    labels, dynamic_sites = MODULE.inventory(root)
    consumer_files = REGISTERED_ERROR_CONSUMER_FILES["governed_cleaning"]
    literal_codes = {
        label
        for label, locations in labels.items()
        if any(
            any(f"/{filename}:" in location for filename in consumer_files)
            for location in locations
        )
    }

    assert consumer_files == frozenset({"governed_cleaning.py"})
    assert literal_codes == {
        "authority_hash_mismatch",
        "candidate_not_approved",
        "candidate_not_reviewable",
        "decision_authority_wrong_class",
        "decision_candidate_mismatch",
        "decision_hash_mismatch",
        "decision_rejected",
        "duplicate_policy_scope",
        "empty_policy",
        "empty_policy_scope",
        "illegal_review_transition",
        "inconsistent_evidence",
        "inconsistent_lineage",
        "invalid_applied_at",
        "invalid_candidate_id",
        "invalid_column_identifier",
        "invalid_configured_at",
        "invalid_dataset_identifier",
        "invalid_evidence_count",
        "invalid_evidence_metric",
        "invalid_lineage_count",
        "invalid_output_sha256",
        "invalid_reviewed_at",
        "invalid_source_sha256",
        "invalid_table_identifier",
        "missing_applied_timestamp",
        "missing_policy_author",
        "missing_review_timestamp",
        "missing_reviewer",
        "modified_decision_without_parameters",
        "non_canonical_payload",
        "operation_not_configured",
        "policy_operation_not_configurable",
        "proposed_confidence_ignored",
        "source_changed_since_review",
        "unclassified_transformation_operation",
        "unexpected_modified_parameters",
        "unknown_transformation_operation",
        "unsupported_policy_version",
    }
    assert literal_codes <= set(ERROR_CLASSIFICATION_REGISTRY)
    # Two codes are shared with older families and keep their global category.
    assert ERROR_CLASSIFICATION_REGISTRY["missing_reviewer"] is ErrorCategory.APPROVAL
    assert ERROR_CLASSIFICATION_REGISTRY["invalid_reviewed_at"] is ErrorCategory.CONTRACT
    assert not {loc for loc in dynamic_sites if "/governed_cleaning.py:" in loc}
    for provenance_table in (
        STANDARD_BLOCKER_FLOW_PROVENANCE,
        DIRECT_BLOCKER_REUSE_PROVENANCE,
        DIRECT_BLOCKER_CONSTRUCTION_PROVENANCE,
        DYNAMIC_ERROR_CODE_PROVENANCE,
        TEXT_STATUS_PROVENANCE,
    ):
        assert not {
            location
            for location, provenance in provenance_table.items()
            if provenance.consumer_family == "governed_cleaning"
        }


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
        family_codes.update(
            code
            for row in DIRECT_BLOCKER_CONSTRUCTION_PROVENANCE.values()
            if row.consumer_family == family
            and row.disposition is TaxonomyDisposition.REGISTERED
            for code in row.possible_codes
        )
        expected_codes.update(family_codes)

    assert set(ERROR_CLASSIFICATION_REGISTRY) == expected_codes
    assert len(ERROR_CLASSIFICATION_REGISTRY) == 712
