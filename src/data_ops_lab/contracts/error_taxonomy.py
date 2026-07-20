from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(str, Enum):
    CONTRACT = "contract"
    AUTHORITY = "authority"
    APPROVAL = "approval"
    EXECUTION_LIMIT = "execution_limit"
    PROVIDER = "provider"
    FILESYSTEM = "filesystem"
    EXPECTED_RESULT = "expected_result"
    UNCLASSIFIED = "unclassified"


class DynamicCodeSurface(str, Enum):
    FORWARDED_STANDARD_BLOCKER = "forwarded_standard_blocker"
    PARAMETERIZED_STANDARD_BLOCKER = "parameterized_standard_blocker"
    EXCEPTION_CODE = "exception_code"
    MODULE_SPECIFIC_BLOCKER = "module_specific_blocker"


class TaxonomyDisposition(str, Enum):
    REGISTERED = "registered"
    DEFERRED_CONSUMER_FAMILY = "deferred_consumer_family"
    SEPARATE_EXCEPTION_SURFACE = "separate_exception_surface"
    SEPARATE_RECORD_FORMAT = "separate_record_format"
    SEPARATE_TEXT_STATUS = "separate_text_status"


@dataclass(frozen=True)
class ErrorClassification:
    code: str
    category: ErrorCategory
    registered: bool


@dataclass(frozen=True)
class DynamicErrorCodeProvenance:
    consumer_family: str
    value_source: str
    surface: DynamicCodeSurface
    disposition: TaxonomyDisposition
    possible_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectBlockerReuseProvenance:
    consumer_family: str
    value_source: str
    record_format: str
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class TextStatusProvenance:
    consumer_family: str
    value_source: str
    output_field: str
    status_values: tuple[str, ...]
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class ExceptionTranslationProvenance:
    consumer_family: str
    value_source: str
    caught_exception: str
    persisted_blocker_code: str
    exception_message_persisted: bool
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class StandardBlockerFlowProvenance:
    consumer_family: str
    producer_family: str
    value_source: str
    record_format: str
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class ExceptionFallbackProvenance:
    consumer_family: str
    value_source: str
    caught_exceptions: tuple[str, ...]
    output_surface: str
    output_field: str
    output_value: str
    exception_message_persisted: bool
    disposition: TaxonomyDisposition


# Families are admitted only after every literal call site in the listed files
# has been reviewed. Dynamic codes are added separately through the provenance
# registry below; any deferred or module-specific surface remains outside this
# boundary until its owning family or record contract is reviewed.
REGISTERED_ERROR_CONSUMER_FILES = {
    "standard_analytics": frozenset(
        {
            "analytics_query_execution.py",
            "analytics_query_plan.py",
            "analytics_semantic_approval.py",
            "analytics_semantic_catalog.py",
        }
    ),
    "semantic_adapter": frozenset({"analytics_semantic_adapter.py"}),
    "dataset_benchmark": frozenset(
        {
            "analytics_dataset_benchmark.py",
            "analytics_dataset_benchmark_evaluation.py",
            "analytics_dataset_benchmark_live_evaluation.py",
            "analytics_dataset_benchmark_materialization.py",
            "analytics_dataset_benchmark_preparation.py",
            "analytics_dataset_benchmark_review.py",
        }
    ),
    "natural_language_translation": frozenset(
        {
            "analytics_nl_translation.py",
            "analytics_translation_evaluation.py",
        }
    ),
    "synthetic_answer_evaluation": frozenset(
        {"analytics_answer_evaluation.py"}
    ),
}


# The keys intentionally bind the manual review to the source-only inventory.
# A moved or added dynamic call site must therefore receive an explicit new
# provenance decision instead of inheriting a category from its spelling.
DYNAMIC_ERROR_CODE_PROVENANCE = {
    "src/data_ops_lab/analytics_dataset_benchmark_evaluation.py:92": DynamicErrorCodeProvenance(
        consumer_family="dataset_benchmark",
        value_source=(
            "blocker_type column copied from blocker evidence emitted by "
            "run_analytics_dataset_benchmark_validation"
        ),
        surface=DynamicCodeSurface.FORWARDED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_dataset_benchmark_materialization.py:306": DynamicErrorCodeProvenance(
        consumer_family="dataset_benchmark",
        value_source="local execution-scope decision branch",
        surface=DynamicCodeSurface.PARAMETERIZED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=(
            "answer_collection_scope_expansion_not_allowed",
            "answer_collection_scope_not_approved",
        ),
    ),
    "src/data_ops_lab/analytics_dataset_benchmark_materialization.py:1044": DynamicErrorCodeProvenance(
        consumer_family="dataset_benchmark",
        value_source=(
            "blocker_type copied from "
            "inspect_analytics_dataset_benchmark_candidate(...).blockers"
        ),
        surface=DynamicCodeSurface.FORWARDED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=("invalid_materialized_candidate_pack",),
    ),
    "src/data_ops_lab/analytics_dataset_benchmark_preparation.py:125": DynamicErrorCodeProvenance(
        consumer_family="dataset_benchmark",
        value_source="blocker_type copied from validate_provider_response(...).blockers",
        surface=DynamicCodeSurface.FORWARDED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=(
            "invalid_provider_response",
            "provider_physical_join_not_allowed",
            "provider_question_not_allowed",
            "provider_sql_not_allowed",
            "unsupported_provider_field",
            "unsupported_provider_response_version",
        ),
    ),
    "src/data_ops_lab/analytics_dataset_benchmark_review.py:245": DynamicErrorCodeProvenance(
        consumer_family="dataset_benchmark",
        value_source="local benchmark-scope decision branch",
        surface=DynamicCodeSurface.PARAMETERIZED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=(
            "benchmark_scope_expansion_not_allowed",
            "benchmark_scope_not_approved",
        ),
    ),
    "src/data_ops_lab/analytics_query_execution.py:444": DynamicErrorCodeProvenance(
        consumer_family="standard_analytics",
        value_source=(
            "ExecutionLimitExceeded.blocker_type raised by controlled query execution "
            "or result collection"
        ),
        surface=DynamicCodeSurface.EXCEPTION_CODE,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=(
            "query_timeout",
            "result_row_limit_exceeded",
            "result_size_limit_exceeded",
        ),
    ),
    "src/data_ops_lab/analytics_semantic_adapter.py:464": DynamicErrorCodeProvenance(
        consumer_family="semantic_adapter",
        value_source="name parameter restricted by callers to dimensions or metrics",
        surface=DynamicCodeSurface.PARAMETERIZED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=("invalid_dimensions", "invalid_metrics"),
    ),
    "src/data_ops_lab/analytics_semantic_adapter.py:467": DynamicErrorCodeProvenance(
        consumer_family="semantic_adapter",
        value_source="name parameter restricted by callers to dimensions or metrics",
        surface=DynamicCodeSurface.PARAMETERIZED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=("dimensions_limit_exceeded", "metrics_limit_exceeded"),
    ),
    "src/data_ops_lab/analytics_semantic_adapter.py:484": DynamicErrorCodeProvenance(
        consumer_family="semantic_adapter",
        value_source="expected_kind parameter restricted by callers to dimension or measure",
        surface=DynamicCodeSurface.PARAMETERIZED_STANDARD_BLOCKER,
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=("invalid_dimension", "invalid_measure"),
    ),
    "src/data_ops_lab/product_canonical_promotion.py:332": DynamicErrorCodeProvenance(
        consumer_family="product_canonical_promotion",
        value_source="local canonical Product integrity-check tuple",
        surface=DynamicCodeSurface.MODULE_SPECIFIC_BLOCKER,
        disposition=TaxonomyDisposition.SEPARATE_RECORD_FORMAT,
        possible_codes=(
            "duplicate_product_id",
            "duplicate_product_ref_nr",
            "empty_product_id",
            "empty_product_ref_nr",
            "invalid_product_id",
        ),
    ),
}


# Provider exceptions remain local control-flow surfaces. The translation
# boundary catches them, drops their messages, and emits one sanitized standard
# blocker code; neither the exception class nor its message enters the registry.
PROVIDER_EXCEPTION_TRANSLATION_PROVENANCE = {
    "src/data_ops_lab/analytics_nl_translation.py:425": ExceptionTranslationProvenance(
        consumer_family="natural_language_translation",
        value_source=(
            "TimeoutError raised by an injected SemanticIntentProvider, including "
            "the normalized local Ollama socket timeout"
        ),
        caught_exception="TimeoutError",
        persisted_blocker_code="provider_timeout",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_nl_translation.py:432": ExceptionTranslationProvenance(
        consumer_family="natural_language_translation",
        value_source=(
            "non-timeout Exception raised by an injected SemanticIntentProvider, "
            "including OllamaProviderError and recorded-provider validation failures"
        ),
        caught_exception="Exception",
        persisted_blocker_code="provider_failure",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
}


EXCEPTION_FALLBACK_PROVENANCE = {
    "src/data_ops_lab/analytics_answer_evaluation.py:931": ExceptionFallbackProvenance(
        consumer_family="synthetic_answer_evaluation",
        value_source="temporary synthetic DuckDB dataset materialization",
        caught_exceptions=("duckdb.Error", "OSError", "ValueError"),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="synthetic_dataset_materialization_failed",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:952": ExceptionFallbackProvenance(
        consumer_family="synthetic_answer_evaluation",
        value_source="per-case translation, planning, execution, or comparison failure",
        caught_exceptions=("Exception",),
        output_surface="text_status",
        output_field="translation_status",
        output_value="evaluation_error",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
}


# These calls append already-classified standard blockers from complete
# producer families into the translation/evaluation outputs. They do not add
# labels to the registry, but their exact source locations make the consumer
# boundary explicit instead of relying on an implicit call graph.
STANDARD_BLOCKER_FLOW_PROVENANCE = {
    "src/data_ops_lab/analytics_nl_translation.py:374": StandardBlockerFlowProvenance(
        consumer_family="natural_language_translation",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes semantic-state input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_nl_translation.py:375": StandardBlockerFlowProvenance(
        consumer_family="natural_language_translation",
        producer_family="semantic_adapter",
        value_source="validate_approved_state writes semantic-state blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_nl_translation.py:445": StandardBlockerFlowProvenance(
        consumer_family="natural_language_translation",
        producer_family="semantic_adapter",
        value_source="adapter_blockers populated by compile_intent are extended into blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_translation_evaluation.py:628": StandardBlockerFlowProvenance(
        consumer_family="natural_language_translation",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes evaluation-pack input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_translation_evaluation.py:630": StandardBlockerFlowProvenance(
        consumer_family="natural_language_translation",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes semantic-state input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_translation_evaluation.py:631": StandardBlockerFlowProvenance(
        consumer_family="natural_language_translation",
        producer_family="semantic_adapter",
        value_source="validate_approved_state writes semantic-state blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:909": StandardBlockerFlowProvenance(
        consumer_family="synthetic_answer_evaluation",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes answer-pack input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:911": StandardBlockerFlowProvenance(
        consumer_family="synthetic_answer_evaluation",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes semantic-state input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:912": StandardBlockerFlowProvenance(
        consumer_family="synthetic_answer_evaluation",
        producer_family="semantic_adapter",
        value_source="validate_approved_state writes semantic-state blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
}


DIRECT_BLOCKER_REUSE_PROVENANCE = {
    "src/data_ops_lab/analytics_dataset_benchmark.py:838": DirectBlockerReuseProvenance(
        consumer_family="dataset_benchmark",
        value_source=(
            "candidate.blockers returned by "
            "inspect_analytics_dataset_benchmark_candidate"
        ),
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_dataset_benchmark_review.py:457": DirectBlockerReuseProvenance(
        consumer_family="dataset_benchmark",
        value_source=(
            "candidate.blockers returned by "
            "inspect_analytics_dataset_benchmark_candidate"
        ),
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
}


TEXT_STATUS_PROVENANCE = {
    "src/data_ops_lab/analytics_dataset_benchmark_live_evaluation.py:467": TextStatusProvenance(
        consumer_family="dataset_benchmark",
        value_source=(
            "translation status plus provider_timeout/provider_failure blocker codes"
        ),
        output_field="provider_outcome",
        status_values=(
            "accepted",
            "clarification",
            "provider_failure",
            "rejected",
            "timeout",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_nl_translation.py:449": TextStatusProvenance(
        consumer_family="natural_language_translation",
        value_source="local blocker and clarification collections",
        output_field="status",
        status_values=(
            "blocked",
            "clarification_required",
            "ready_for_query_plan",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_translation_evaluation.py:468": TextStatusProvenance(
        consumer_family="natural_language_translation",
        value_source=(
            "nested translation result status or sanitized evaluation_error fallback"
        ),
        output_field="observed_status",
        status_values=(
            "blocked",
            "clarification_required",
            "evaluation_error",
            "ready_for_query_plan",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_translation_evaluation.py:634": TextStatusProvenance(
        consumer_family="natural_language_translation",
        value_source="evaluation contract blockers and per-case comparison outcomes",
        output_field="status",
        status_values=(
            "blocked",
            "failed",
            "passed",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:704": TextStatusProvenance(
        consumer_family="synthetic_answer_evaluation",
        value_source="nested translation result or sanitized per-case exception fallback",
        output_field="translation_status",
        status_values=(
            "blocked",
            "clarification_required",
            "evaluation_error",
            "ready_for_query_plan",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:707": TextStatusProvenance(
        consumer_family="synthetic_answer_evaluation",
        value_source="nested Stage 5A plan result or pre-gate not_run sentinel",
        output_field="planning_status",
        status_values=(
            "blocked",
            "not_run",
            "ready_for_execution_review",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:708": TextStatusProvenance(
        consumer_family="synthetic_answer_evaluation",
        value_source="nested Stage 5B execution result or pre-gate not_run sentinel",
        output_field="execution_status",
        status_values=(
            "blocked",
            "completed",
            "completed_no_rows",
            "not_run",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_answer_evaluation.py:968": TextStatusProvenance(
        consumer_family="synthetic_answer_evaluation",
        value_source="contract blockers and per-case exact evaluation outcomes",
        output_field="status",
        status_values=(
            "blocked",
            "failed",
            "passed",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
}


_AUTHORITY_CODES = {
    "database_changed_after_plan_revalidation",
    "database_changed_during_execution",
    "execution_inputs_changed",
    "reviewed_plan_mismatch",
    "semantic_catalog_drift",
}

_APPROVAL_CODES = {
    "candidate_relationship_authority_invalid",
    "duplicate_ambiguity_decision",
    "duplicate_entity_decision",
    "invalid_ambiguity_decision",
    "invalid_entity_decision",
    "invalid_selected_target",
    "missing_ambiguity_decision",
    "missing_ambiguity_notes",
    "missing_decision_notes",
    "missing_entity_decision",
    "missing_reviewer",
    "pending_ambiguity_decision",
    "pending_entity_decision",
    "rejected_semantic_entity",
    "relationship_not_approved",
    "review_not_completed",
    "reviewed_plan_missing",
    "semantic_adapter_not_authorized",
    "semantic_definitions_not_approved",
    "semantic_state_not_approved",
    "unexpected_selected_target",
    "unknown_ambiguity_decision",
    "unknown_entity_decision",
}

_EXECUTION_LIMIT_CODES = {
    "dimension_limit_exceeded",
    "dimensions_limit_exceeded",
    "filter_limit_exceeded",
    "filters_limit_exceeded",
    "join_limit_exceeded",
    "metric_limit_exceeded",
    "metrics_limit_exceeded",
    "order_by_limit_exceeded",
    "order_limit_exceeded",
    "query_timeout",
    "relationship_path_limit_exceeded",
    "result_row_limit_exceeded",
    "result_size_limit_exceeded",
    "semantic_collection_limit_exceeded",
    "synonym_limit_exceeded",
}

_FILESYSTEM_CODES = {
    "database_missing",
    "database_unreadable",
    "required_input_missing",
    "reviewed_plan_unreadable",
}

_CONTRACT_CODES = {
    "column_table_not_selected",
    "database_catalog_empty",
    "duplicate_approved_semantic_id",
    "duplicate_output_alias",
    "duplicate_semantic_id",
    "duplicate_semantic_term",
    "empty_selection",
    "incompatible_measure_type",
    "invalid_ambiguity_decisions",
    "invalid_approved_relationship",
    "invalid_approved_relationship_path",
    "invalid_approved_semantic_state",
    "invalid_column",
    "invalid_dataset_semantics",
    "invalid_dimension",
    "invalid_dimensions",
    "invalid_entity_decisions",
    "invalid_execution_limit",
    "invalid_filter",
    "invalid_filter_value",
    "invalid_filters",
    "invalid_in_filter",
    "invalid_join",
    "invalid_join_order",
    "invalid_joins",
    "invalid_limit",
    "invalid_measure",
    "invalid_metric",
    "invalid_metrics",
    "invalid_order_by",
    "invalid_order_direction",
    "invalid_order_rule",
    "invalid_output_alias",
    "invalid_question",
    "invalid_relationship_paths",
    "invalid_relationship_hop",
    "invalid_relationship_path",
    "invalid_relationship_registry",
    "invalid_review_body",
    "invalid_review_source",
    "invalid_reviewed_at",
    "invalid_semantic_collection",
    "invalid_semantic_description",
    "invalid_semantic_entity",
    "invalid_semantic_id",
    "invalid_semantic_approval",
    "invalid_semantic_path_order",
    "invalid_semantic_state_source",
    "invalid_semantic_target",
    "invalid_semantic_term",
    "invalid_semantic_term_index",
    "invalid_source_column",
    "invalid_source_table",
    "invalid_synonyms",
    "invalid_table",
    "invalid_table_id",
    "invalid_yaml",
    "invalid_yaml_mapping",
    "non_contiguous_relationship_path",
    "physical_join_not_allowed",
    "raw_sql_not_allowed",
    "self_relationship_hop",
    "semantic_ambiguity_state_mismatch",
    "semantic_kind_mismatch",
    "semantic_table_not_selected",
    "semantic_tables_empty",
    "unexpected_filter_value",
    "unknown_column",
    "unknown_order_field",
    "unknown_semantic_target",
    "unknown_semantic_term",
    "unknown_source_column",
    "unknown_source_table",
    "unknown_table",
    "unknown_table_id",
    "unsupported_aggregate",
    "unsupported_filter_operator",
    "unsupported_join_kind",
    "unsupported_intent_field",
    "unsupported_intent_version",
    "unsupported_measure_function",
    "unsupported_request_field",
    "unsupported_request_version",
    "unsupported_review_field",
    "unsupported_review_version",
    "unsupported_semantic_field",
    "unsupported_semantic_version",
}

# These reviewed labels do not fit the initial seven-category boundary. Keeping
# them explicit prevents spelling-based guesses while later categories evolve.
_REVIEWED_UNCLASSIFIED_CODES = {
    "plan_revalidation_failed",
    "query_execution_failed",
}


_DATASET_BENCHMARK_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "answer_collection_review_identity_mismatch",
        "answer_collection_review_source_drift",
        "benchmark_answer_design_binding_mismatch",
        "benchmark_answer_design_dataset_mismatch",
        "benchmark_approval_identity_mismatch",
        "benchmark_database_changed_during_preparation",
        "benchmark_dataset_id_mismatch",
        "benchmark_hash_binding_mismatch",
        "benchmark_license_not_verified",
        "benchmark_materialization_authority_changed_before_query",
        "benchmark_materialization_authority_changed_during_collection",
        "benchmark_materialization_authority_changed_during_query",
        "benchmark_preparation_artifact_drift",
        "benchmark_preparation_case_mismatch",
        "benchmark_preparation_identity_mismatch",
        "benchmark_preparation_source_drift",
        "benchmark_provenance_not_verified",
        "benchmark_review_identity_drift",
        "benchmark_review_source_drift",
        "dataset_artifact_changed_during_validation",
        "dataset_artifact_hash_mismatch",
        "dataset_artifact_size_mismatch",
        "dataset_benchmark_authority_blocked",
        "dataset_benchmark_authority_changed_before_evaluation",
        "dataset_benchmark_authority_changed_before_live_case",
        "dataset_benchmark_authority_changed_before_live_preflight",
        "dataset_benchmark_authority_changed_before_live_query",
        "dataset_benchmark_authority_changed_before_query",
        "dataset_benchmark_inputs_changed_during_evaluation",
        "dataset_benchmark_inputs_changed_during_live_evaluation",
        "dataset_expected_question_mismatch",
        "dataset_package_not_verified",
        "invalid_relationship_registry_authority_hash",
        "live_evaluation_identity_mismatch",
        "live_evaluation_source_mismatch",
        "materialization_question_mismatch",
        "reviewed_answer_plan_hash_mismatch",
    },
    ErrorCategory.APPROVAL: {
        "answer_collection_case_not_approved",
        "answer_collection_review_not_completed",
        "answer_collection_scope_expansion_not_allowed",
        "answer_collection_scope_not_approved",
        "benchmark_answer_case_not_review_ready",
        "benchmark_approval_scope_invalid",
        "benchmark_case_not_execution_ready",
        "benchmark_case_review_not_approved",
        "benchmark_evaluation_not_approved",
        "benchmark_preparation_not_review_ready",
        "benchmark_review_not_completed",
        "benchmark_scope_expansion_not_allowed",
        "benchmark_scope_not_approved",
        "duplicate_answer_collection_case",
        "duplicate_answer_collection_scope",
        "duplicate_benchmark_case_decision",
        "duplicate_benchmark_scope_decision",
        "invalid_answer_collection_case_decision",
        "invalid_answer_collection_case_decisions",
        "invalid_answer_collection_review_time",
        "invalid_answer_collection_scope_decision",
        "invalid_answer_collection_scope_decisions",
        "invalid_benchmark_approval_decision",
        "invalid_benchmark_approval_identity",
        "invalid_benchmark_approval_time",
        "invalid_benchmark_case_decision",
        "invalid_benchmark_case_decisions",
        "invalid_benchmark_review_evidence",
        "invalid_benchmark_reviewed_at",
        "invalid_benchmark_scope_decision",
        "invalid_benchmark_scope_decisions",
        "invalid_relationship_registry_authority",
        "invalid_relationship_registry_non_authorizations",
        "live_evaluation_authorization_notes_missing",
        "live_evaluation_authorized_at_invalid",
        "live_evaluation_authorizer_missing",
        "live_evaluation_execution_scope_mismatch",
        "live_evaluation_not_approved",
        "live_evaluation_scope_not_bounded",
        "missing_answer_collection_case",
        "missing_answer_collection_case_notes",
        "missing_answer_collection_reviewer",
        "missing_answer_collection_scope",
        "missing_answer_collection_scope_notes",
        "missing_benchmark_case_decision",
        "missing_benchmark_case_notes",
        "missing_benchmark_reviewer",
        "missing_benchmark_scope_decision",
        "missing_benchmark_scope_notes",
        "relationship_registry_not_approved",
        "unknown_answer_collection_case",
        "unknown_answer_collection_scope",
        "unknown_benchmark_case_decision",
        "unknown_benchmark_scope",
    },
    ErrorCategory.EXECUTION_LIMIT: {
        "benchmark_answer_design_too_large",
        "benchmark_materialization_control_too_large",
        "benchmark_review_too_large",
        "dataset_benchmark_control_too_large",
        "live_evaluation_authorization_too_large",
    },
    ErrorCategory.PROVIDER: {
        "benchmark_answer_design_provider_response_too_large",
        "invalid_dataset_provider_response",
        "invalid_provider_response",
        "live_evaluation_network_flag_not_allowed_in_dry_run",
        "live_evaluation_network_not_authorized_for_invocation",
        "live_evaluation_provider_mismatch",
        "live_evaluation_provider_not_loopback_ollama",
        "live_evaluation_provider_not_network_gated",
        "live_evaluation_timeout_invalid",
        "provider_physical_join_not_allowed",
        "provider_question_not_allowed",
        "provider_sql_not_allowed",
        "unsupported_provider_field",
        "unsupported_provider_response_version",
    },
    ErrorCategory.FILESYSTEM: {
        "benchmark_database_missing",
        "benchmark_preparation_artifact_missing",
        "benchmark_review_missing",
        "benchmark_review_unreadable",
        "dataset_benchmark_validation_evidence_missing",
        "live_evaluation_authorization_missing",
        "missing_benchmark_preparation_artifact",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "ambiguous_materialized_string_null",
        "benchmark_answer_design_coverage_mismatch",
        "benchmark_answer_design_order_required",
        "benchmark_answer_design_output_mismatch",
        "benchmark_answer_design_shape_mismatch",
        "benchmark_design_tolerance_required",
        "dataset_completed_requires_rows",
        "dataset_deterministic_order_required",
        "dataset_expected_column_count_mismatch",
        "dataset_expected_null_count_mismatch",
        "dataset_expected_row_count_mismatch",
        "dataset_no_row_expectation_mismatch",
        "duplicate_benchmark_design_column",
        "duplicate_benchmark_design_tolerance",
        "duplicate_dataset_expected_column",
        "duplicate_dataset_tolerance",
        "exact_benchmark_design_tolerance_not_allowed",
        "exact_comparison_tolerance_not_allowed",
        "invalid_benchmark_answer_design_result_shape",
        "invalid_benchmark_design_column",
        "invalid_benchmark_design_columns",
        "invalid_benchmark_design_comparison",
        "invalid_benchmark_design_tolerance",
        "invalid_benchmark_design_tolerance_column",
        "invalid_benchmark_design_tolerance_value",
        "invalid_benchmark_design_tolerances",
        "invalid_dataset_comparison",
        "invalid_dataset_comparison_mode",
        "invalid_dataset_expected_column",
        "invalid_dataset_expected_columns",
        "invalid_dataset_expected_result",
        "invalid_dataset_expected_row",
        "invalid_dataset_expected_rows",
        "invalid_dataset_expected_status",
        "invalid_dataset_expected_value",
        "invalid_dataset_tolerance",
        "invalid_dataset_tolerance_column",
        "invalid_dataset_tolerance_value",
        "invalid_dataset_tolerances",
        "invalid_materialized_answer_columns",
        "materialized_answer_control_mismatch",
        "materialized_answer_csv_invalid",
        "materialized_answer_schema_mismatch",
        "materialized_answer_value_invalid",
        "numeric_tolerance_required",
        "unsupported_benchmark_design_type",
        "unsupported_dataset_expected_type",
    },
    ErrorCategory.CONTRACT: {
        "duplicate_benchmark_answer_design_case_id",
        "duplicate_dataset_benchmark_case_id",
        "invalid_answer_collection_review",
        "invalid_benchmark_answer_design_bindings",
        "invalid_benchmark_answer_design_case",
        "invalid_benchmark_answer_design_case_id",
        "invalid_benchmark_answer_design_cases",
        "invalid_benchmark_answer_design_coverage",
        "invalid_benchmark_answer_design_id",
        "invalid_benchmark_answer_design_question",
        "invalid_benchmark_answer_design_status",
        "invalid_benchmark_hash_bindings",
        "invalid_benchmark_pack_id",
        "invalid_benchmark_pack_status",
        "invalid_benchmark_preparation_cases",
        "invalid_benchmark_preparation_controls",
        "invalid_benchmark_preparation_relationships",
        "invalid_benchmark_relationship_registry",
        "invalid_benchmark_review",
        "invalid_benchmark_review_body",
        "invalid_benchmark_review_identity",
        "invalid_benchmark_review_source",
        "invalid_dataset_artifact",
        "invalid_dataset_benchmark_case",
        "invalid_dataset_benchmark_case_id",
        "invalid_dataset_benchmark_cases",
        "invalid_dataset_benchmark_question",
        "invalid_dataset_expected_request",
        "invalid_dataset_expected_request_version",
        "invalid_dataset_identity",
        "invalid_materialized_candidate_pack",
        "invalid_rejected_relationship_ids",
        "invalid_relationship_registry_dataset",
        "unsafe_benchmark_preparation_artifact_path",
        "unsupported_answer_materialization_field",
        "unsupported_benchmark_answer_design_version",
        "unsupported_benchmark_data_classification",
        "unsupported_benchmark_dataset_format",
        "unsupported_benchmark_pack_version",
        "unsupported_benchmark_preparation_field",
        "unsupported_benchmark_preparation_version",
        "unsupported_benchmark_review_field",
        "unsupported_benchmark_review_version",
        "unsupported_dataset_benchmark_field",
        "unsupported_dataset_expected_request_field",
        "unsupported_dataset_manifest_version",
        "unsupported_live_evaluation_authorization_field",
        "unsupported_live_evaluation_authorization_version",
    },
    ErrorCategory.UNCLASSIFIED: {
        "benchmark_answer_execution_incomplete",
        "benchmark_answer_result_integrity_failed",
    },
}


# The two standard-blocker consumers in the Stage 5D translation/evaluation
# family expose 46 unique literal codes. Seven were already registered by the
# earlier standard-analytics and dataset-benchmark slices; these groups add the
# remaining 39 without duplicating their global classifications.
_NATURAL_LANGUAGE_TRANSLATION_CLASSIFICATIONS = {
    ErrorCategory.APPROVAL: {
        "network_provider_not_authorized",
    },
    ErrorCategory.EXECUTION_LIMIT: {
        "evaluation_pack_too_large",
        "question_file_too_large",
        "semantic_context_too_large",
    },
    ErrorCategory.PROVIDER: {
        "invalid_provider_behavior",
        "invalid_provider_timeout",
        "provider_failure",
        "provider_response_not_allowed",
        "provider_response_required",
        "provider_response_too_large",
        "provider_timeout",
    },
    ErrorCategory.FILESYSTEM: {
        "question_file_missing",
        "question_file_unreadable",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "accepted_intent_required",
        "blocked_intent_not_allowed",
        "evaluation_category_status_mismatch",
        "evaluation_coverage_incomplete",
        "expected_blocker_required",
        "expected_clarification_required",
        "provider_failure_coverage_incomplete",
        "provider_failure_expectation_mismatch",
        "unexpected_blocker_expectation",
        "unexpected_clarification_expectation",
    },
    ErrorCategory.CONTRACT: {
        "duplicate_evaluation_case_id",
        "invalid_accepted_intent",
        "invalid_accepted_intents",
        "invalid_evaluation_case",
        "invalid_evaluation_case_id",
        "invalid_evaluation_cases",
        "invalid_evaluation_category",
        "invalid_evaluation_description",
        "invalid_evaluation_expectation",
        "invalid_evaluation_pack_id",
        "invalid_evaluation_question",
        "invalid_expected_blockers",
        "invalid_expected_clarifications",
        "invalid_expected_status",
        "unsupported_evaluation_field",
        "unsupported_evaluation_pack_version",
    },
}


_SYNTHETIC_ANSWER_EVALUATION_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "expected_question_mismatch",
    },
    ErrorCategory.EXECUTION_LIMIT: {
        "answer_pack_too_large",
        "synthetic_row_limit_exceeded",
    },
    ErrorCategory.PROVIDER: {
        "answer_provider_response_too_large",
        "invalid_answer_provider_response",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "answer_category_status_mismatch",
        "answer_coverage_incomplete",
        "completed_answer_requires_rows",
        "deterministic_order_required",
        "expected_column_count_mismatch",
        "expected_null_count_mismatch",
        "expected_row_count_mismatch",
        "invalid_expected_answer",
        "invalid_expected_columns",
        "invalid_expected_row",
        "invalid_expected_rows",
        "no_row_expectation_mismatch",
    },
    ErrorCategory.CONTRACT: {
        "duplicate_answer_case_id",
        "duplicate_synthetic_column",
        "duplicate_synthetic_relationship",
        "duplicate_synthetic_table",
        "invalid_answer_case",
        "invalid_answer_case_id",
        "invalid_answer_cases",
        "invalid_answer_category",
        "invalid_answer_pack_description",
        "invalid_answer_pack_id",
        "invalid_answer_question",
        "invalid_expected_request",
        "invalid_expected_request_version",
        "invalid_synthetic_column",
        "invalid_synthetic_column_name",
        "invalid_synthetic_columns",
        "invalid_synthetic_dataset",
        "invalid_synthetic_nullability",
        "invalid_synthetic_relationship",
        "invalid_synthetic_relationships",
        "invalid_synthetic_row",
        "invalid_synthetic_rows",
        "invalid_synthetic_table",
        "invalid_synthetic_table_name",
        "invalid_synthetic_tables",
        "invalid_synthetic_value",
        "unknown_synthetic_relationship_reference",
        "unsupported_answer_evaluation_field",
        "unsupported_answer_pack_version",
        "unsupported_expected_request_field",
        "unsupported_synthetic_type",
    },
    ErrorCategory.UNCLASSIFIED: {
        "synthetic_dataset_materialization_failed",
    },
}


def _build_registry() -> dict[str, ErrorCategory]:
    initial_groups = {
        ErrorCategory.CONTRACT: _CONTRACT_CODES,
        ErrorCategory.AUTHORITY: _AUTHORITY_CODES,
        ErrorCategory.APPROVAL: _APPROVAL_CODES,
        ErrorCategory.EXECUTION_LIMIT: _EXECUTION_LIMIT_CODES,
        ErrorCategory.FILESYSTEM: _FILESYSTEM_CODES,
        ErrorCategory.UNCLASSIFIED: _REVIEWED_UNCLASSIFIED_CODES,
    }
    registry: dict[str, ErrorCategory] = {}
    for groups in (
        initial_groups,
        _DATASET_BENCHMARK_CLASSIFICATIONS,
        _NATURAL_LANGUAGE_TRANSLATION_CLASSIFICATIONS,
        _SYNTHETIC_ANSWER_EVALUATION_CLASSIFICATIONS,
    ):
        for category, codes in groups.items():
            for code in codes:
                if code in registry:
                    raise RuntimeError(f"Duplicate error-taxonomy code: {code}")
                registry[code] = category
    return registry


ERROR_CLASSIFICATION_REGISTRY = _build_registry()


def classify_error(code: str) -> ErrorClassification:
    """Return additive metadata without changing or normalizing the input code."""
    category = ERROR_CLASSIFICATION_REGISTRY.get(code)
    return ErrorClassification(
        code=code,
        category=category or ErrorCategory.UNCLASSIFIED,
        registered=category is not None,
    )
