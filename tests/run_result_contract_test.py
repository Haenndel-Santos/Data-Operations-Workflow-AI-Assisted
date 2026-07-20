from __future__ import annotations

import importlib
from dataclasses import dataclass, fields
from pathlib import Path

from data_ops_lab.contracts import (
    RUN_RESULT_ENVELOPE_FIELDS,
    RunResultEnvelope,
    RunResultLike,
    project_run_result,
)


COMPATIBLE_RESULT_TYPES = (
    ("data_ops_lab.analytics_answer_evaluation", "AnalyticsAnswerEvaluationResult"),
    ("data_ops_lab.analytics_dataset_benchmark", "AnalyticsDatasetBenchmarkResult"),
    (
        "data_ops_lab.analytics_dataset_benchmark_evaluation",
        "AnalyticsDatasetBenchmarkEvaluationResult",
    ),
    (
        "data_ops_lab.analytics_dataset_benchmark_live_evaluation",
        "AnalyticsDatasetBenchmarkLiveEvaluationResult",
    ),
    (
        "data_ops_lab.analytics_dataset_benchmark_materialization",
        "AnalyticsDatasetBenchmarkMaterializationResult",
    ),
    (
        "data_ops_lab.analytics_dataset_benchmark_preparation",
        "AnalyticsDatasetBenchmarkPreparationResult",
    ),
    (
        "data_ops_lab.analytics_dataset_benchmark_review",
        "AnalyticsDatasetBenchmarkApprovalResult",
    ),
    ("data_ops_lab.analytics_nl_translation", "AnalyticsNlTranslationResult"),
    ("data_ops_lab.analytics_ollama_soak", "AnalyticsOllamaSoakResult"),
    ("data_ops_lab.analytics_query_execution", "AnalyticsQueryExecutionResult"),
    ("data_ops_lab.analytics_query_plan", "AnalyticsQueryPlanResult"),
    ("data_ops_lab.analytics_result_narration", "AnalyticsResultNarrationResult"),
    (
        "data_ops_lab.analytics_result_presentation",
        "AnalyticsResultPresentationResult",
    ),
    ("data_ops_lab.analytics_semantic_adapter", "AnalyticsSemanticAdapterResult"),
    ("data_ops_lab.analytics_semantic_approval", "AnalyticsSemanticApprovalResult"),
    ("data_ops_lab.analytics_semantic_catalog", "AnalyticsSemanticCatalogResult"),
    ("data_ops_lab.analytics_session", "AnalyticsSessionPrepareResult"),
    ("data_ops_lab.analytics_session", "AnalyticsSessionResumeResult"),
    (
        "data_ops_lab.analytics_translation_evaluation",
        "AnalyticsTranslationEvaluationResult",
    ),
    ("data_ops_lab.module_registry", "ModuleRegistryValidationResult"),
    ("data_ops_lab.product_canonical_promotion", "ProductCanonicalPromotionResult"),
    ("data_ops_lab.product_materialization", "ProductMaterializationResult"),
    ("data_ops_lab.reference_dataset_validation", "ReferenceDatasetValidationResult"),
)


@dataclass(frozen=True)
class RepresentativeResult:
    output_dir: Path
    status: str
    blocker_count: int
    outputs_changed: bool
    report_path: Path


def test_project_run_result_preserves_the_shared_fields(tmp_path):
    result = RepresentativeResult(
        output_dir=tmp_path,
        status="ready_for_local_preview",
        blocker_count=0,
        outputs_changed=False,
        report_path=tmp_path / "report.md",
    )

    envelope = project_run_result(result)

    assert isinstance(result, RunResultLike)
    assert envelope == RunResultEnvelope(
        output_dir=tmp_path,
        status="ready_for_local_preview",
        blocker_count=0,
        outputs_changed=False,
    )
    assert tuple(field.name for field in fields(envelope)) == RUN_RESULT_ENVELOPE_FIELDS


def test_project_run_result_does_not_infer_status_or_copy_module_fields(tmp_path):
    result = RepresentativeResult(
        output_dir=tmp_path,
        status="module_specific_ready_state",
        blocker_count=3,
        outputs_changed=True,
        report_path=tmp_path / "report.md",
    )

    envelope = project_run_result(result)

    assert envelope.status == "module_specific_ready_state"
    assert envelope.blocker_count == 3
    assert envelope.outputs_changed is True
    assert not hasattr(envelope, "report_path")


def test_all_reviewed_result_types_expose_the_exact_common_core():
    assert len(COMPATIBLE_RESULT_TYPES) == 23
    expected_fields = set(RUN_RESULT_ENVELOPE_FIELDS)

    for module_name, class_name in COMPATIBLE_RESULT_TYPES:
        result_type = getattr(importlib.import_module(module_name), class_name)
        result_fields = {field.name for field in fields(result_type)}

        assert expected_fields <= result_fields, f"{module_name}.{class_name}"
