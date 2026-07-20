from __future__ import annotations

import hashlib
import os

import pytest
from data_ops_lab import (
    analytics_query_execution,
    analytics_query_plan,
    analytics_semantic_approval,
    analytics_semantic_catalog,
    product_refnr_application,
    reference_dataset_validation,
    source_onboarding,
)
from data_ops_lab.contracts.atomic_publish import (
    DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
    DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
    AtomicPublishTargetAppearedError,
    atomic_write_text,
    publish_new_directory,
)
from data_ops_lab.contracts.blockers import (
    STANDARD_BLOCKER_FIELDS,
    add_blocker,
)
from data_ops_lab.contracts.hashing import FILE_HASH_CHUNK_SIZE, file_sha256
from data_ops_lab.contracts.error_taxonomy import (
    ERROR_CLASSIFICATION_REGISTRY,
    ErrorCategory,
    classify_error,
)
from data_ops_lab.contracts.source_bindings import (
    declared_file_sha256_bindings,
    existing_file_sha256_bindings,
)


def test_file_sha256_preserves_legacy_exports_and_digest(tmp_path):
    content = b"phase-two-contract\n" * ((FILE_HASH_CHUNK_SIZE // 19) + 10)
    source = tmp_path / "source.bin"
    source.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()

    assert file_sha256(source) == expected
    assert source_onboarding.file_sha256 is file_sha256
    assert product_refnr_application.file_sha256 is file_sha256
    assert reference_dataset_validation.file_sha256 is file_sha256


def test_standard_blocker_preserves_legacy_exports_and_shape():
    blockers: list[dict[str, str]] = []

    add_blocker(
        blockers,
        "required_input_missing",
        "A required local input is missing.",
        field="dataset_manifest",
    )
    add_blocker(
        blockers,
        "invalid_yaml",
        "The required local input is not valid UTF-8 YAML.",
    )

    assert blockers == [
        {
            "blocker_id": "BLOCKER_001",
            "blocker_type": "required_input_missing",
            "field": "dataset_manifest",
            "explanation": "A required local input is missing.",
        },
        {
            "blocker_id": "BLOCKER_002",
            "blocker_type": "invalid_yaml",
            "field": "",
            "explanation": "The required local input is not valid UTF-8 YAML.",
        },
    ]
    assert tuple(blockers[0]) == STANDARD_BLOCKER_FIELDS
    assert analytics_query_plan.add_blocker is add_blocker
    assert analytics_query_execution.add_blocker is add_blocker
    assert analytics_semantic_approval.add_blocker is add_blocker
    assert analytics_semantic_catalog.add_blocker is add_blocker


def test_error_taxonomy_is_additive_and_preserves_codes():
    authority = classify_error("database_changed_during_execution")
    approval = classify_error("semantic_adapter_not_authorized")
    contract = classify_error("invalid_measure")
    execution_limit = classify_error("query_timeout")
    unknown = classify_error("future_module_specific_failure")
    reviewed_without_category = classify_error("query_execution_failed")

    assert authority.code == "database_changed_during_execution"
    assert authority.category is ErrorCategory.AUTHORITY
    assert authority.registered is True
    assert approval.category is ErrorCategory.APPROVAL
    assert contract.category is ErrorCategory.CONTRACT
    assert execution_limit.category is ErrorCategory.EXECUTION_LIMIT
    assert unknown.code == "future_module_specific_failure"
    assert unknown.category is ErrorCategory.UNCLASSIFIED
    assert unknown.registered is False
    assert reviewed_without_category.category is ErrorCategory.UNCLASSIFIED
    assert reviewed_without_category.registered is True
    assert len(ERROR_CLASSIFICATION_REGISTRY) == len(set(ERROR_CLASSIFICATION_REGISTRY))


def test_dataset_benchmark_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "benchmark_hash_binding_mismatch": ErrorCategory.AUTHORITY,
        "benchmark_case_review_not_approved": ErrorCategory.APPROVAL,
        "benchmark_answer_design_too_large": ErrorCategory.EXECUTION_LIMIT,
        "live_evaluation_provider_mismatch": ErrorCategory.PROVIDER,
        "benchmark_review_unreadable": ErrorCategory.FILESYSTEM,
        "materialized_answer_schema_mismatch": ErrorCategory.EXPECTED_RESULT,
        "invalid_benchmark_pack_id": ErrorCategory.CONTRACT,
        "benchmark_answer_result_integrity_failed": ErrorCategory.UNCLASSIFIED,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("accepted").registered is False
    assert classify_error("timeout").registered is False


def test_translation_provider_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "invalid_evaluation_case": ErrorCategory.CONTRACT,
        "network_provider_not_authorized": ErrorCategory.APPROVAL,
        "question_file_too_large": ErrorCategory.EXECUTION_LIMIT,
        "provider_timeout": ErrorCategory.PROVIDER,
        "question_file_missing": ErrorCategory.FILESYSTEM,
        "evaluation_category_status_mismatch": ErrorCategory.EXPECTED_RESULT,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("ready_for_query_plan").registered is False
    assert classify_error("evaluation_error").registered is False


def test_synthetic_answer_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "invalid_synthetic_table": ErrorCategory.CONTRACT,
        "expected_question_mismatch": ErrorCategory.AUTHORITY,
        "synthetic_row_limit_exceeded": ErrorCategory.EXECUTION_LIMIT,
        "invalid_answer_provider_response": ErrorCategory.PROVIDER,
        "expected_row_count_mismatch": ErrorCategory.EXPECTED_RESULT,
        "synthetic_dataset_materialization_failed": ErrorCategory.UNCLASSIFIED,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("not_run").registered is False
    assert classify_error("completed").registered is False


def test_result_presentation_narration_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "invalid_execution_manifest": ErrorCategory.CONTRACT,
        "result_hash_mismatch": ErrorCategory.AUTHORITY,
        "result_size_invalid": ErrorCategory.EXECUTION_LIMIT,
        "invalid_claim_text": ErrorCategory.PROVIDER,
        "result_missing": ErrorCategory.FILESYSTEM,
        "result_controls_mismatch": ErrorCategory.EXPECTED_RESULT,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("ready_for_recorded_narration").registered is False
    assert classify_error("ready_for_user").registered is False


def test_analytics_session_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "invalid_execution_review": ErrorCategory.CONTRACT,
        "session_authority_changed": ErrorCategory.AUTHORITY,
        "execution_review_incomplete": ErrorCategory.APPROVAL,
        "narration_response_missing": ErrorCategory.FILESYSTEM,
        "query_execution_blocked": ErrorCategory.UNCLASSIFIED,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("awaiting_execution_review").registered is False
    assert classify_error("result_narration").registered is False


def test_module_registry_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "invalid_module_contract": ErrorCategory.CONTRACT,
        "registry_changed_during_validation": ErrorCategory.AUTHORITY,
        "missing_human_review_gate": ErrorCategory.APPROVAL,
        "registry_too_large": ErrorCategory.EXECUTION_LIMIT,
        "registry_missing": ErrorCategory.FILESYSTEM,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("valid").registered is False
    assert classify_error("active").registered is False
    assert classify_error("implemented").registered is False


def test_ollama_soak_taxonomy_keeps_failure_surfaces_distinct():
    expected = {
        "ollama_soak_authorization_invalid": ErrorCategory.CONTRACT,
        "ollama_soak_source_mismatch": ErrorCategory.AUTHORITY,
        "ollama_soak_not_approved": ErrorCategory.APPROVAL,
        "ollama_soak_authorization_too_large": ErrorCategory.EXECUTION_LIMIT,
        "ollama_soak_provider_not_loopback": ErrorCategory.PROVIDER,
        "ollama_soak_authorization_missing": ErrorCategory.FILESYSTEM,
        "ollama_soak_live_authority_preflight_failed": ErrorCategory.UNCLASSIFIED,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("ready_for_overnight_soak").registered is False
    assert classify_error("stopped_resource_guard").registered is False
    assert classify_error("stop_file_detected").registered is False


def test_reference_dataset_taxonomy_keeps_authority_and_review_state_distinct():
    expected = {
        "invalid_conversion_table": ErrorCategory.CONTRACT,
        "review_manifest_drift": ErrorCategory.AUTHORITY,
        "local_scope_not_approved": ErrorCategory.APPROVAL,
        "missing_file": ErrorCategory.FILESYSTEM,
        "invalid_relationship_data": ErrorCategory.EXPECTED_RESULT,
        "invalid_relationship_review": ErrorCategory.UNCLASSIFIED,
    }

    assert {
        code: classify_error(code).category for code in expected
    } == expected
    assert all(classify_error(code).registered for code in expected)
    assert classify_error("ready_for_relationship_review").registered is False
    assert classify_error("ready_for_semantic_modeling").registered is False
    assert classify_error("pending_review").registered is False
    assert classify_error("cleanup_staging_and_reraise").registered is False


def test_atomic_write_text_retries_and_cleans_temporary_file(tmp_path):
    path = tmp_path / "checkpoint.yml"
    path.write_text("old\n", encoding="utf-8")
    attempts = 0
    delays: list[float] = []

    def transient_replace(source: object, target: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("synthetic transient lock")
        os.replace(source, target)

    atomic_write_text(
        path,
        "new\n",
        retry_delays=DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
        sleep_fn=delays.append,
        replace_fn=transient_replace,
    )

    assert attempts == 2
    assert delays == [DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS[0]]
    assert path.read_text(encoding="utf-8") == "new\n"
    assert not list(tmp_path.glob(".checkpoint.yml.*.tmp"))


def test_atomic_write_text_cleans_temporary_file_after_retry_exhaustion(tmp_path):
    path = tmp_path / "checkpoint.yml"
    delays: list[float] = []

    def locked_replace(source: object, target: object) -> None:
        raise PermissionError("synthetic persistent lock")

    with pytest.raises(PermissionError, match="synthetic persistent lock"):
        atomic_write_text(
            path,
            "new\n",
            retry_delays=(0.01, 0.02),
            sleep_fn=delays.append,
            replace_fn=locked_replace,
        )

    assert delays == [0.01, 0.02]
    assert not path.exists()
    assert not list(tmp_path.glob(".checkpoint.yml.*.tmp"))


def test_publish_new_directory_preserves_target_that_appears_and_cleans_staging(
    tmp_path,
):
    staging = tmp_path / ".evidence.staging"
    staging.mkdir()
    (staging / "manifest.yml").write_text("version: 1\n", encoding="utf-8")
    output = tmp_path / "evidence"

    def colliding_replace(source, target):
        target.mkdir()
        (target / "human-notes.txt").write_text("preserve me\n", encoding="utf-8")
        raise PermissionError("synthetic target race")

    with pytest.raises(AtomicPublishTargetAppearedError) as error:
        publish_new_directory(
            staging,
            output,
            retry_delays=DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
            replace_fn=colliding_replace,
        )

    assert error.value.target == output
    assert (output / "human-notes.txt").read_text(encoding="utf-8") == "preserve me\n"
    assert not staging.exists()


def test_existing_file_sha256_bindings_preserves_order_and_omits_missing(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    missing = tmp_path / "missing.txt"
    directory = tmp_path / "directory"
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    directory.mkdir()

    bindings = existing_file_sha256_bindings(
        {
            "second_sha256": second,
            "missing_sha256": missing,
            "directory_sha256": directory,
            "first_sha256": first,
        }
    )

    assert list(bindings) == ["second_sha256", "first_sha256"]
    assert bindings == {
        "second_sha256": file_sha256(second),
        "first_sha256": file_sha256(first),
    }


def test_declared_file_sha256_bindings_preserves_all_keys(tmp_path):
    existing = tmp_path / "existing.txt"
    missing = tmp_path / "missing.txt"
    directory = tmp_path / "directory"
    existing.write_text("existing\n", encoding="utf-8")
    directory.mkdir()

    bindings = declared_file_sha256_bindings(
        {
            "existing_sha256": existing,
            "missing_sha256": missing,
            "directory_sha256": directory,
        }
    )

    assert list(bindings) == [
        "existing_sha256",
        "missing_sha256",
        "directory_sha256",
    ]
    assert bindings == {
        "existing_sha256": file_sha256(existing),
        "missing_sha256": "",
        "directory_sha256": "",
    }
