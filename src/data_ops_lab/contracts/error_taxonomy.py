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
    SEPARATE_CONTROL_TEXT = "separate_control_text"
    SEPARATE_APPROVAL_PROJECTION = "separate_approval_projection"
    SEPARATE_AUTHORITY_BOUNDARY = "separate_authority_boundary"


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
class DirectBlockerConstructionProvenance:
    consumer_family: str
    value_source: str
    record_format: str
    possible_codes: tuple[str, ...]
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class TextStatusProvenance:
    consumer_family: str
    value_source: str
    output_field: str
    status_values: tuple[str, ...]
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class ControlTextProvenance:
    consumer_family: str
    value_source: str
    output_field: str
    value_domain: str
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class BlockerRecordFormatProvenance:
    consumer_family: str
    value_source: str
    output_surface: str
    record_format: str
    record_fields: tuple[str, ...]
    identifier_format: str | None
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class ApprovalProjectionProvenance:
    consumer_family: str
    value_source: str
    output_surface: str
    authority_gate: str
    decision_domain: tuple[str, ...]
    projected_fields: tuple[str, ...]
    disposition: TaxonomyDisposition


@dataclass(frozen=True)
class AuthorityBoundaryProvenance:
    consumer_family: str
    value_source: str
    output_surface: str
    authority_values: tuple[str, ...]
    required_next_authority: str
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
    "result_presentation_narration": frozenset(
        {
            "analytics_result_narration.py",
            "analytics_result_presentation.py",
        }
    ),
    "analytics_session": frozenset({"analytics_session.py"}),
    "module_registry": frozenset({"module_registry.py"}),
    "ollama_soak": frozenset({"analytics_ollama_soak.py"}),
    "reference_dataset_validation": frozenset(
        {"reference_dataset_validation.py"}
    ),
    "product_canonical_promotion": frozenset(
        {"product_canonical_promotion.py"}
    ),
    "product_materialization": frozenset({"product_materialization.py"}),
    "governed_cleaning": frozenset({"governed_cleaning.py"}),
    "governed_cleaning_engine": frozenset({"governed_cleaning_engine.py"}),
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
        disposition=TaxonomyDisposition.REGISTERED,
        possible_codes=(
            "duplicate_product_id",
            "duplicate_product_ref_nr",
            "empty_product_id",
            "empty_product_ref_nr",
            "invalid_product_id",
        ),
    ),
}


DIRECT_BLOCKER_CONSTRUCTION_PROVENANCE = {
    "src/data_ops_lab/product_materialization.py:145": DirectBlockerConstructionProvenance(
        consumer_family="product_materialization",
        value_source="applied decisions with zero or multiple source identifiers",
        record_format="product_materialization_candidate_blocker_v1",
        possible_codes=("invalid_source_identifier_count",),
        disposition=TaxonomyDisposition.REGISTERED,
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
    "src/data_ops_lab/analytics_result_presentation.py:269": ExceptionFallbackProvenance(
        consumer_family="result_presentation_narration",
        value_source="bounded Stage 5B result CSV read and parse",
        caught_exceptions=("OSError", "UnicodeError", "csv.Error"),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="invalid_result_csv",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_result_narration.py:514": ExceptionFallbackProvenance(
        consumer_family="result_presentation_narration",
        value_source="TimeoutError raised by an injected ResultNarrationProvider",
        caught_exceptions=("TimeoutError",),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="provider_timeout",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_result_narration.py:516": ExceptionFallbackProvenance(
        consumer_family="result_presentation_narration",
        value_source=(
            "non-timeout Exception raised by an injected ResultNarrationProvider, "
            "including recorded-response file and validation failures"
        ),
        caught_exceptions=("Exception",),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="provider_failure",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_session.py:108": ExceptionFallbackProvenance(
        consumer_family="analytics_session",
        value_source="artifact path normalization outside the owned session directory",
        caught_exceptions=("ValueError",),
        output_surface="artifact_metadata",
        output_field="path",
        output_value="",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_session.py:443": ExceptionFallbackProvenance(
        consumer_family="analytics_session",
        value_source="human execution-review timestamp parsing",
        caught_exceptions=("ValueError",),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="invalid_execution_review_time",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_session.py:574": ExceptionFallbackProvenance(
        consumer_family="analytics_session",
        value_source="existing resume-manifest read and YAML parse preflight",
        caught_exceptions=("OSError", "UnicodeError", "yaml.YAMLError"),
        output_surface="exception",
        output_field="exception_type",
        output_value="ValueError",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/module_registry.py:114": ExceptionFallbackProvenance(
        consumer_family="module_registry",
        value_source="registry file-size preflight",
        caught_exceptions=("OSError",),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="registry_unreadable",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/module_registry.py:127": ExceptionFallbackProvenance(
        consumer_family="module_registry",
        value_source="registry UTF-8 read and YAML parse",
        caught_exceptions=("OSError", "UnicodeError", "yaml.YAMLError"),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="invalid_registry_yaml",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/module_registry.py:208": ExceptionFallbackProvenance(
        consumer_family="module_registry",
        value_source="static module-spec resolution without importing the entrypoint",
        caught_exceptions=(
            "ImportError",
            "AttributeError",
            "ModuleNotFoundError",
            "ValueError",
        ),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="entrypoint_not_resolvable",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/module_registry.py:223": ExceptionFallbackProvenance(
        consumer_family="module_registry",
        value_source="bounded entrypoint source read and AST parse",
        caught_exceptions=("OSError", "UnicodeError", "SyntaxError"),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="entrypoint_source_unreadable",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/module_registry.py:736": ExceptionFallbackProvenance(
        consumer_family="module_registry",
        value_source="initial registry SHA-256 binding",
        caught_exceptions=("OSError",),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="registry_unreadable",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/module_registry.py:772": ExceptionFallbackProvenance(
        consumer_family="module_registry",
        value_source="final registry SHA-256 drift check",
        caught_exceptions=("OSError",),
        output_surface="standard_blocker",
        output_field="blocker_type",
        output_value="registry_changed_during_validation",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:161": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="overnight-soak authorization UTF-8 read and YAML parse",
        caught_exceptions=("OSError", "UnicodeError", "yaml.YAMLError"),
        output_surface="authorization_payload",
        output_field="mapping",
        output_value="empty_mapping",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:195": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="human soak-authorization timestamp parsing",
        caught_exceptions=("ValueError",),
        output_surface="module_specific_blocker",
        output_field="blocker_type",
        output_value="ollama_soak_authorized_at_invalid",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:296": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="required execution/resource policy field extraction",
        caught_exceptions=("KeyError",),
        output_surface="module_specific_blocker",
        output_field="blocker_type",
        output_value="ollama_soak_policy_incomplete",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:395": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="literal loopback endpoint normalization",
        caught_exceptions=("ValueError",),
        output_surface="module_specific_blocker",
        output_field="blocker_type",
        output_value="ollama_soak_provider_not_loopback",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:530": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="Windows soak/Ollama process-memory sampling",
        caught_exceptions=("AttributeError", "OSError", "ValueError"),
        output_surface="resource_sample",
        output_field="process_memory",
        output_value="partial_unavailable_process_memory",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:572": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="bounded nvidia-smi telemetry collection",
        caught_exceptions=(
            "FileNotFoundError",
            "OSError",
            "subprocess.SubprocessError",
            "ValueError",
        ),
        output_surface="resource_sample",
        output_field="gpu_telemetry",
        output_value="unavailable_gpu_telemetry",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:577": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="soak output-volume free-disk sampling",
        caught_exceptions=("OSError",),
        output_surface="resource_sample",
        output_field="disk_free_mb",
        output_value="unavailable_disk_free_mb",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:630": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="completed live-cycle manifest read and YAML parse",
        caught_exceptions=("OSError", "UnicodeError", "yaml.YAMLError"),
        output_surface="cycle_summary",
        output_field="manifest",
        output_value="empty_mapping",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:641": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="completed live-cycle case CSV read",
        caught_exceptions=("OSError", "UnicodeError"),
        output_surface="cycle_summary",
        output_field="cases",
        output_value="empty_list",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:1209": ExceptionFallbackProvenance(
        consumer_family="ollama_soak",
        value_source="one governed live-evaluation cycle invocation",
        caught_exceptions=("Exception",),
        output_surface="cycle_text",
        output_field="failure_type",
        output_value="<exception_class_name>",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:76": ExceptionFallbackProvenance(
        consumer_family="reference_dataset_validation",
        value_source="required local YAML UTF-8 read and parse",
        caught_exceptions=("OSError", "UnicodeError", "yaml.YAMLError"),
        output_surface="module_specific_blocker",
        output_field="code",
        output_value="invalid_yaml",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:293": ExceptionFallbackProvenance(
        consumer_family="reference_dataset_validation",
        value_source="benchmark-use human approval timestamp parsing",
        caught_exceptions=("ValueError",),
        output_surface="module_specific_blocker",
        output_field="code",
        output_value="invalid_benchmark_approval_time",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:582": ExceptionFallbackProvenance(
        consumer_family="reference_dataset_validation",
        value_source="read-only DuckDB technical-evidence profiling",
        caught_exceptions=("duckdb.Error",),
        output_surface="module_specific_blocker",
        output_field="code",
        output_value="database_unreadable",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:640": ExceptionFallbackProvenance(
        consumer_family="reference_dataset_validation",
        value_source="per-relationship human review timestamp parsing",
        caught_exceptions=("ValueError",),
        output_surface="module_specific_blocker",
        output_field="code",
        output_value="invalid_review_time",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:837": ExceptionFallbackProvenance(
        consumer_family="reference_dataset_validation",
        value_source="staged validation-evidence publication",
        caught_exceptions=("Exception",),
        output_surface="exception",
        output_field="failure_policy",
        output_value="cleanup_staging_and_reraise",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:108": ExceptionFallbackProvenance(
        consumer_family="product_canonical_promotion",
        value_source="Product state or materialization-manifest YAML parse",
        caught_exceptions=("yaml.YAMLError",),
        output_surface="module_specific_blocker",
        output_field="blocker_type",
        output_value="invalid_yaml",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:135": ExceptionFallbackProvenance(
        consumer_family="product_canonical_promotion",
        value_source="canonical Product UUID5 integrity predicate",
        caught_exceptions=("ValueError", "AttributeError"),
        output_surface="integrity_predicate",
        output_field="valid_uuid5",
        output_value="false",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:145": ExceptionFallbackProvenance(
        consumer_family="product_canonical_promotion",
        value_source="materialization manifest integer-count normalization",
        caught_exceptions=("TypeError", "ValueError"),
        output_surface="manifest_count_parser",
        output_field="integer_value",
        output_value="none",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:276": ExceptionFallbackProvenance(
        consumer_family="product_canonical_promotion",
        value_source="bounded materialization artifact CSV read and parse",
        caught_exceptions=("csv.Error", "OSError", "UnicodeError"),
        output_surface="module_specific_blocker",
        output_field="blocker_type",
        output_value="invalid_csv",
        exception_message_persisted=False,
        disposition=TaxonomyDisposition.SEPARATE_EXCEPTION_SURFACE,
    ),
}


BLOCKER_RECORD_FORMAT_PROVENANCE = {
    "src/data_ops_lab/analytics_ollama_soak.py:132": BlockerRecordFormatProvenance(
        consumer_family="ollama_soak",
        value_source="local _add_blocker appends embedded soak contract blockers",
        output_surface="manifest.contract_blockers",
        record_format="ollama_soak_embedded_blocker_v1",
        record_fields=("blocker_id", "blocker_type", "field", "explanation"),
        identifier_format="blocker_{ordinal:03d}",
        disposition=TaxonomyDisposition.SEPARATE_RECORD_FORMAT,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:67": BlockerRecordFormatProvenance(
        consumer_family="reference_dataset_validation",
        value_source="local add_blocker appends reference-validation blockers",
        output_surface="manifest.blockers",
        record_format="reference_dataset_blocker_v1",
        record_fields=("code", "message", "field"),
        identifier_format=None,
        disposition=TaxonomyDisposition.SEPARATE_RECORD_FORMAT,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:83": BlockerRecordFormatProvenance(
        consumer_family="product_canonical_promotion",
        value_source="local add_blocker appends canonical-promotion blockers",
        output_surface="plan.blockers + product_canonical_promotion_blockers.csv",
        record_format="product_canonical_promotion_artifact_blocker_v1",
        record_fields=("blocker_id", "blocker_type", "artifact", "explanation"),
        identifier_format="BLOCKER_{ordinal:03d}",
        disposition=TaxonomyDisposition.SEPARATE_RECORD_FORMAT,
    ),
    "src/data_ops_lab/product_materialization.py:174": BlockerRecordFormatProvenance(
        consumer_family="product_materialization",
        value_source="local add_blocker appends internal materialization candidates",
        output_surface="internal materialization blocker candidates",
        record_format="product_materialization_candidate_blocker_v1",
        record_fields=("issue_ids", "source_identifier", "blocker_type", "explanation"),
        identifier_format=None,
        disposition=TaxonomyDisposition.SEPARATE_RECORD_FORMAT,
    ),
    "src/data_ops_lab/product_materialization.py:223": BlockerRecordFormatProvenance(
        consumer_family="product_materialization",
        value_source="normalize_blockers deduplicates candidates and assigns blocker IDs",
        output_surface="manifest.blockers + product_materialization_blockers.csv",
        record_format="product_materialization_blocker_v1",
        record_fields=(
            "blocker_id",
            "issue_ids",
            "source_identifier",
            "blocker_type",
            "explanation",
        ),
        identifier_format="BLOCKER_{ordinal:03d}",
        disposition=TaxonomyDisposition.SEPARATE_RECORD_FORMAT,
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
    "src/data_ops_lab/analytics_result_presentation.py:520": StandardBlockerFlowProvenance(
        consumer_family="result_presentation_narration",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes request input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_result_presentation.py:521": StandardBlockerFlowProvenance(
        consumer_family="result_presentation_narration",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes execution-manifest input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_result_narration.py:459": StandardBlockerFlowProvenance(
        consumer_family="result_presentation_narration",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes presentation-manifest input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_result_narration.py:464": StandardBlockerFlowProvenance(
        consumer_family="result_presentation_narration",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes facts input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_session.py:460": StandardBlockerFlowProvenance(
        consumer_family="analytics_session",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes preparation-manifest input blockers",
        record_format="standard_blocker",
        disposition=TaxonomyDisposition.REGISTERED,
    ),
    "src/data_ops_lab/analytics_session.py:620": StandardBlockerFlowProvenance(
        consumer_family="analytics_session",
        producer_family="standard_analytics",
        value_source="read_yaml_mapping writes execution-review input blockers",
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
    "src/data_ops_lab/analytics_result_presentation.py:369": TextStatusProvenance(
        consumer_family="result_presentation_narration",
        value_source="validated deterministic facts construction",
        output_field="facts.status",
        status_values=("ready_for_recorded_narration",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_result_presentation.py:544": TextStatusProvenance(
        consumer_family="result_presentation_narration",
        value_source="presentation blockers after exact Stage 5B evidence validation",
        output_field="status",
        status_values=(
            "blocked",
            "ready_for_recorded_narration",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_result_narration.py:535": TextStatusProvenance(
        consumer_family="result_presentation_narration",
        value_source="narration blockers after exact fact and citation validation",
        output_field="status",
        status_values=(
            "blocked",
            "ready_for_user",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:188": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="new execution-review template before human action",
        output_field="review_template.status",
        status_values=("pending_review",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:196": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="new execution-review decision before human action",
        output_field="review_template.review.decision",
        status_values=("pending",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:271": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="preparation blockers and nested translation/planning outcomes",
        output_field="prepare.status",
        status_values=(
            "awaiting_execution_review",
            "blocked",
            "clarification_required",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:298": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="nested Stage 5D translation result",
        output_field="prepare.stages.translation.status",
        status_values=("blocked", "clarification_required", "ready_for_query_plan"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:302": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="nested Stage 5A planning result or not-started sentinel",
        output_field="prepare.stages.query_plan.status",
        status_values=("blocked", "not_started", "ready_for_execution_review"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:305": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="prepare-phase execution authorization boundary",
        output_field="prepare.stages.query_execution.status",
        status_values=("not_authorized",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:306": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="prepare-phase presentation sentinel",
        output_field="prepare.stages.result_presentation.status",
        status_values=("not_started",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:307": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="prepare-phase narration sentinel",
        output_field="prepare.stages.result_narration.status",
        status_values=("not_started",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:635": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="last successfully validated resume checkpoint",
        output_field="last_valid_checkpoint",
        status_values=(
            "execution_review",
            "prepare",
            "query_execution",
            "result_narration",
            "result_presentation",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:699": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="resume blockers after exact stage coordination",
        output_field="resume.status",
        status_values=("blocked", "completed"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:702": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="exact execution-review validation outcome",
        output_field="resume.stages.execution_review.status",
        status_values=("approved", "blocked"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:704": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="nested Stage 5B execution result or not-started sentinel",
        output_field="resume.stages.query_execution.status",
        status_values=("blocked", "completed", "completed_no_rows", "not_started"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:708": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="nested result-presentation outcome or not-started sentinel",
        output_field="resume.stages.result_presentation.status",
        status_values=("blocked", "not_started", "ready_for_recorded_narration"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_session.py:714": TextStatusProvenance(
        consumer_family="analytics_session",
        value_source="nested result-narration outcome or not-started sentinel",
        output_field="resume.stages.result_narration.status",
        status_values=("blocked", "not_started", "ready_for_user"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/module_registry.py:781": TextStatusProvenance(
        consumer_family="module_registry",
        value_source="complete static contract validation blocker outcome",
        output_field="status",
        status_values=("blocked", "valid"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:669": TextStatusProvenance(
        consumer_family="ollama_soak",
        value_source="nested live-evaluation cycle result or sanitized exception fallback",
        output_field="cycle.status",
        status_values=("blocked", "evaluation_error", "failed", "passed"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:829": TextStatusProvenance(
        consumer_family="ollama_soak",
        value_source="contract preflight and bounded live-soak runtime state",
        output_field="status",
        status_values=(
            "blocked",
            "completed",
            "ready_for_overnight_soak",
            "running",
            "stopped_by_request",
            "stopped_error_limit",
            "stopped_provider_timeout",
            "stopped_resource_guard",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:222": TextStatusProvenance(
        consumer_family="reference_dataset_validation",
        value_source="validated benchmark-conversion manifest projection",
        output_field="conversion_projection.status",
        status_values=("ready_for_local_benchmark",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:590": TextStatusProvenance(
        consumer_family="reference_dataset_validation",
        value_source="optional exact relationship-review validation outcome",
        output_field="relationships.review_status",
        status_values=("completed", "incomplete", "invalid", "pending_review"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:705": TextStatusProvenance(
        consumer_family="reference_dataset_validation",
        value_source="generated relationship-review template",
        output_field="relationship_review.status",
        status_values=("pending_review",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:694": TextStatusProvenance(
        consumer_family="reference_dataset_validation",
        value_source="generated pending or preserved completed human decision",
        output_field="relationship_review.decisions[].decision",
        status_values=("accepted", "pending", "rejected"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:768": TextStatusProvenance(
        consumer_family="reference_dataset_validation",
        value_source="human-review-gated approved-relationship projection",
        output_field="approved_relationships.status",
        status_values=("approved", "pending_review"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/reference_dataset_validation.py:914": TextStatusProvenance(
        consumer_family="reference_dataset_validation",
        value_source="blocker outcome and completed exact relationship review",
        output_field="status",
        status_values=(
            "blocked",
            "ready_for_relationship_review",
            "ready_for_semantic_modeling",
        ),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:212": TextStatusProvenance(
        consumer_family="product_canonical_promotion",
        value_source="required applied Product reconciliation checkpoint",
        output_field="product_reconciliation_state.status",
        status_values=("applied",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:227": TextStatusProvenance(
        consumer_family="product_canonical_promotion",
        value_source="required Step 3E.5 materialization checkpoint",
        output_field="materialization_manifest.status",
        status_values=("ready_for_local_preview",),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/product_canonical_promotion.py:397": TextStatusProvenance(
        consumer_family="product_canonical_promotion",
        value_source="complete dry-run promotion-plan blocker outcome",
        output_field="plan.status",
        status_values=("blocked", "ready_for_canonical_state_review"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
    "src/data_ops_lab/product_materialization.py:649": TextStatusProvenance(
        consumer_family="product_materialization",
        value_source="complete fail-closed materialization blocker outcome",
        output_field="manifest.status",
        status_values=("blocked", "ready_for_local_preview"),
        disposition=TaxonomyDisposition.SEPARATE_TEXT_STATUS,
    ),
}


CONTROL_TEXT_PROVENANCE = {
    "src/data_ops_lab/analytics_ollama_soak.py:830": ControlTextProvenance(
        consumer_family="ollama_soak",
        value_source="explicit execute flag",
        output_field="mode",
        value_domain="one of: dry-run, live",
        disposition=TaxonomyDisposition.SEPARATE_CONTROL_TEXT,
    ),
    "src/data_ops_lab/analytics_ollama_soak.py:858": ControlTextProvenance(
        consumer_family="ollama_soak",
        value_source=(
            "bounded duration/cycle/provider/STOP sentinels or a stable comma-separated "
            "subset of resource-guard reason tokens"
        ),
        output_field="runtime.stop_reason",
        value_domain="bounded soak stop-reason control text",
        disposition=TaxonomyDisposition.SEPARATE_CONTROL_TEXT,
    ),
    "src/data_ops_lab/product_materialization.py:48": ControlTextProvenance(
        consumer_family="product_materialization",
        value_source="exact applied human decision action",
        output_field="applied_decision.action",
        value_domain=(
            "one of: apply_corrected_product_ref_nr, "
            "exclude_from_target_product_model"
        ),
        disposition=TaxonomyDisposition.SEPARATE_CONTROL_TEXT,
    ),
    "src/data_ops_lab/product_materialization.py:427": ControlTextProvenance(
        consumer_family="product_materialization",
        value_source="deterministic retained Product lineage construction",
        output_field="lineage.materialization_action",
        value_domain=(
            "one of: matched_authoritative_correction, "
            "approved_same_row_conflict_resolution, approved_product_refnr_only"
        ),
        disposition=TaxonomyDisposition.SEPARATE_CONTROL_TEXT,
    ),
}


APPROVAL_PROJECTION_PROVENANCE = {
    "src/data_ops_lab/reference_dataset_validation.py:734": ApprovalProjectionProvenance(
        consumer_family="reference_dataset_validation",
        value_source=(
            "accepted/rejected decisions from the exact completed human review, "
            "bound to manifest, candidate, and review hashes"
        ),
        output_surface="approved_relationships.yml",
        authority_gate="status == 'ready_for_semantic_modeling'",
        decision_domain=("accepted", "rejected"),
        projected_fields=(
            "status",
            "authority.completed_review_sha256",
            "authority.derived_from_completed_human_review",
            "authority.automatic_approval",
            "authority.scope",
            "approved_relationships",
            "rejected_relationship_ids",
        ),
        disposition=TaxonomyDisposition.SEPARATE_APPROVAL_PROJECTION,
    ),
}


AUTHORITY_BOUNDARY_PROVENANCE = {
    "src/data_ops_lab/product_canonical_promotion.py:444": AuthorityBoundaryProvenance(
        consumer_family="product_canonical_promotion",
        value_source="dry-run canonical Product promotion plan",
        output_surface="plan.approval",
        authority_values=(
            "canonical_state_applied=false",
            "database_operation_authorized=false",
            "requires_explicit_apply_contract=true",
        ),
        required_next_authority="a separate explicit canonical-state apply contract",
        disposition=TaxonomyDisposition.SEPARATE_AUTHORITY_BOUNDARY,
    ),
    "src/data_ops_lab/product_materialization.py:127": AuthorityBoundaryProvenance(
        consumer_family="product_materialization",
        value_source="validated review workbook projected through the application contract",
        output_surface="materialization_preflight",
        authority_values=("applied_state_matches_validated_workbook=true",),
        required_next_authority="the exact applied Product reconciliation state",
        disposition=TaxonomyDisposition.SEPARATE_AUTHORITY_BOUNDARY,
    ),
    "src/data_ops_lab/product_materialization.py:662": AuthorityBoundaryProvenance(
        consumer_family="product_materialization",
        value_source="fail-closed local Product materialization manifest",
        output_surface="manifest.contract",
        authority_values=(
            "exclusion_precedence=true",
            "preview_only=true",
        ),
        required_next_authority=(
            "separate canonical-promotion review and explicit apply contracts"
        ),
        disposition=TaxonomyDisposition.SEPARATE_AUTHORITY_BOUNDARY,
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


_RESULT_PRESENTATION_NARRATION_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "facts_hash_mismatch",
        "facts_source_mismatch",
        "narration_inputs_changed",
        "presentation_inputs_changed",
        "request_hash_mismatch",
        "result_artifact_mismatch",
        "result_hash_mismatch",
        "unsafe_execution_evidence",
        "unsafe_presentation_evidence",
    },
    ErrorCategory.EXECUTION_LIMIT: {
        "result_size_invalid",
        "truncated_result_not_allowed",
    },
    ErrorCategory.PROVIDER: {
        "invalid_claim",
        "invalid_claim_citations",
        "invalid_claim_text",
        "invalid_claims",
        "invalid_headline",
        "required_controls_not_cited",
        "ungrounded_numeric_value",
    },
    ErrorCategory.FILESYSTEM: {
        "invalid_result_csv",
        "result_missing",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "no_rows_control_mismatch",
        "result_controls_mismatch",
    },
    ErrorCategory.CONTRACT: {
        "execution_has_blockers",
        "execution_not_presentable",
        "facts_not_ready",
        "invalid_execution_columns",
        "invalid_execution_manifest",
        "invalid_fact",
        "invalid_facts",
        "invalid_null_control",
        "presentation_not_ready",
        "unsupported_execution_manifest_version",
    },
}


_ANALYTICS_SESSION_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "database_changed_after_prepare",
        "prepare_artifact_mismatch",
        "prepare_manifest_review_mismatch",
        "relationships_changed_after_prepare",
        "reviewed_plan_hash_mismatch",
        "session_authority_changed",
        "session_prepare_inputs_changed",
        "unsafe_prepare_checkpoint",
    },
    ErrorCategory.APPROVAL: {
        "execution_not_approved",
        "execution_review_incomplete",
        "invalid_execution_review_text",
        "invalid_execution_review_time",
    },
    ErrorCategory.FILESYSTEM: {
        "narration_response_missing",
    },
    ErrorCategory.CONTRACT: {
        "invalid_execution_review",
        "invalid_execution_review_decision",
        "invalid_execution_review_source",
        "prepare_checkpoint_not_ready",
        "translation_request_missing",
    },
    ErrorCategory.UNCLASSIFIED: {
        "query_execution_blocked",
        "query_plan_blocked",
        "result_narration_blocked",
        "result_presentation_blocked",
        "translation_blocked",
    },
}


_MODULE_REGISTRY_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "registry_changed_during_validation",
        "unsafe_registry_controls",
        "unsafe_stage_failure_policy",
        "unsafe_workflow_gate",
    },
    ErrorCategory.APPROVAL: {
        "missing_human_review_gate",
    },
    ErrorCategory.EXECUTION_LIMIT: {
        "registry_too_large",
        "too_many_modules",
        "too_many_workflow_gates",
        "too_many_workflow_stages",
        "too_many_workflows",
    },
    ErrorCategory.FILESYSTEM: {
        "entrypoint_source_unreadable",
        "registry_missing",
        "registry_unreadable",
        "test_file_missing",
    },
    ErrorCategory.CONTRACT: {
        "entrypoint_input_mismatch",
        "entrypoint_not_resolvable",
        "entrypoint_variadic",
        "invalid_entrypoint",
        "invalid_identifier_list",
        "invalid_module_contract",
        "invalid_module_dependency",
        "invalid_module_failure_policy",
        "invalid_module_name",
        "invalid_module_text",
        "invalid_registry_contract",
        "invalid_registry_mapping",
        "invalid_registry_yaml",
        "invalid_stage_id",
        "invalid_stage_module",
        "invalid_stage_order",
        "invalid_string_list",
        "invalid_test_path",
        "invalid_workflow_contract",
        "invalid_workflow_coordinator",
        "invalid_workflow_failure_policy",
        "invalid_workflow_gate",
        "invalid_workflow_gates",
        "invalid_workflow_metadata",
        "invalid_workflow_name",
        "invalid_workflow_stage",
        "missing_module_workflow",
        "module_dependency_cycle",
        "modules_missing",
        "unknown_module_workflow",
        "unsupported_module_state",
        "unsupported_registry_state",
        "unused_module_workflow",
        "workflow_stages_missing",
        "workflows_missing",
    },
}


_OLLAMA_SOAK_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "ollama_soak_parallel_or_stop_policy_invalid",
        "ollama_soak_source_mismatch",
    },
    ErrorCategory.APPROVAL: {
        "ollama_soak_authorized_at_invalid",
        "ollama_soak_authorizer_missing",
        "ollama_soak_network_flag_not_allowed_in_dry_run",
        "ollama_soak_network_not_authorized_for_invocation",
        "ollama_soak_not_approved",
        "ollama_soak_notes_missing",
        "ollama_soak_scope_not_bounded",
    },
    ErrorCategory.EXECUTION_LIMIT: {
        "ollama_soak_authorization_too_large",
        "ollama_soak_policy_value_invalid",
    },
    ErrorCategory.PROVIDER: {
        "ollama_soak_provider_mismatch",
        "ollama_soak_provider_not_loopback",
    },
    ErrorCategory.FILESYSTEM: {
        "ollama_soak_authorization_missing",
    },
    ErrorCategory.CONTRACT: {
        "ollama_soak_authorization_invalid",
        "ollama_soak_execution_policy_missing",
        "ollama_soak_policy_incomplete",
        "ollama_soak_resource_policy_missing",
        "unsupported_ollama_soak_authorization_field",
        "unsupported_ollama_soak_authorization_version",
    },
    ErrorCategory.UNCLASSIFIED: {
        "ollama_soak_live_authority_preflight_failed",
    },
}


_REFERENCE_DATASET_VALIDATION_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "conversion_dataset_mismatch",
        "conversion_source_mismatch",
        "database_column_drift",
        "database_hash_drift",
        "database_row_count_drift",
        "database_table_drift",
        "invalid_primary_key_evidence",
        "invalid_relationship_authority",
        "missing_reproduction",
        "reproduction_mismatch",
        "review_candidate_drift",
        "review_manifest_drift",
        "sha256_mismatch",
        "source_size_mismatch",
        "unverified_license",
        "unverified_provenance",
    },
    ErrorCategory.APPROVAL: {
        "benchmark_use_not_approved",
        "duplicate_review_decision",
        "incomplete_relationship_review",
        "invalid_benchmark_scopes",
        "invalid_review_decisions",
        "invalid_review_time",
        "local_scope_not_approved",
        "missing_benchmark_approver",
        "missing_benchmark_use",
        "missing_review_notes",
        "pending_review_decision",
        "relationship_scope_not_approved",
        "unsafe_review_scope",
        "unsafe_scope_state",
        "unknown_review_decision",
    },
    ErrorCategory.FILESYSTEM: {
        "missing_file",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "invalid_primary_key_data",
        "invalid_relationship_data",
        "primary_key_count_mismatch",
        "relationship_count_mismatch",
    },
    ErrorCategory.CONTRACT: {
        "artifact_path_escape",
        "conversion_not_ready",
        "duplicate_primary_key",
        "duplicate_relationship",
        "invalid_artifact_path",
        "invalid_conversion",
        "invalid_conversion_artifact",
        "invalid_conversion_artifacts",
        "invalid_conversion_column",
        "invalid_conversion_columns",
        "invalid_conversion_table",
        "invalid_conversion_tables",
        "invalid_dataset",
        "invalid_license",
        "invalid_license_commit",
        "invalid_license_permalink",
        "invalid_local_path",
        "invalid_official_source",
        "invalid_parquet_artifact",
        "invalid_parquet_artifacts",
        "invalid_primary_key",
        "invalid_primary_keys",
        "invalid_relationship",
        "invalid_relationship_candidates",
        "invalid_relationship_config",
        "invalid_relationship_identifier",
        "invalid_schema_review",
        "invalid_sha256",
        "invalid_source",
        "invalid_source_commit",
        "invalid_spdx",
        "missing_official_source_field",
        "unknown_primary_key",
        "unknown_primary_key_column",
        "unknown_relationship_column",
        "unknown_relationship_table",
        "unsupported_reference_version",
    },
    ErrorCategory.UNCLASSIFIED: {
        "invalid_relationship_review",
    },
}


_PRODUCT_CANONICAL_PROMOTION_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "decision_digest_mismatch",
        "manifest_count_mismatch",
        "manifest_validation_mismatch",
        "materialization_contract_mismatch",
        "product_model_contract_mismatch",
        "review_workbook_hash_mismatch",
    },
    ErrorCategory.APPROVAL: {
        "product_state_not_applied",
    },
    ErrorCategory.FILESYSTEM: {
        "invalid_csv",
        "required_artifact_missing",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "duplicate_product_id",
        "duplicate_product_ref_nr",
        "empty_product_id",
        "empty_product_ref_nr",
        "excluded_identifier_in_lineage",
        "invalid_exclusion_identifiers",
        "invalid_product_id",
        "lineage_product_mismatch",
        "optional_pd_reference_mismatch",
    },
    ErrorCategory.CONTRACT: {
        "duplicate_preview_columns",
        "materialization_not_ready",
        "required_preview_column_missing",
    },
    ErrorCategory.UNCLASSIFIED: {
        "materialization_blockers_present",
    },
}


_PRODUCT_MATERIALIZATION_CLASSIFICATIONS = {
    ErrorCategory.AUTHORITY: {
        "approved_conflict_alignment_changed",
        "approved_conflict_reference_row_missing",
        "approved_product_refnr_row_missing",
        "source_identifier_out_of_range",
    },
    ErrorCategory.APPROVAL: {
        "approved_conflict_reference_rejected",
        "retained_product_uses_rejected_reference_row",
        "unmatched_product_refnr_without_supported_decision",
    },
    ErrorCategory.EXPECTED_RESULT: {
        "approved_authoritative_row_empty",
        "approved_corrected_reference_missing",
        "duplicate_generated_product_id",
    },
    ErrorCategory.CONTRACT: {
        "invalid_source_identifier",
        "invalid_source_identifier_count",
        "missing_product_ref_nr_column",
        "unsupported_materialization_action",
    },
    ErrorCategory.UNCLASSIFIED: {
        "approved_decision_not_materialized",
        "retained_original_product_unresolved",
    },
}


_GOVERNED_CLEANING_CLASSIFICATIONS = {
    ErrorCategory.CONTRACT: {
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
        "invalid_source_sha256",
        "invalid_table_identifier",
        "missing_applied_timestamp",
        "missing_policy_author",
        "missing_review_timestamp",
        "modified_decision_without_parameters",
        "non_canonical_payload",
        "proposed_confidence_ignored",
        "unclassified_transformation_operation",
        "unexpected_modified_parameters",
        "unknown_transformation_operation",
        "unsupported_policy_version",
    },
    ErrorCategory.AUTHORITY: {
        "authority_hash_mismatch",
        "candidate_not_approved",
        "candidate_not_reviewable",
        "decision_authority_wrong_class",
        "decision_candidate_mismatch",
        "decision_hash_mismatch",
        "operation_not_automatic",
        "operation_not_configured",
        "policy_operation_not_configurable",
        "source_changed_since_review",
    },
    ErrorCategory.APPROVAL: {
        "decision_rejected",
    },
}


_GOVERNED_CLEANING_ENGINE_CLASSIFICATIONS = {
    ErrorCategory.CONTRACT: {
        "candidate_record_carries_authority",
        "invalid_application_plan",
        "invalid_authority_record",
        "invalid_candidate_record",
        "invalid_input_file",
        "invalid_policy_file",
        "invalid_review_decision",
        "invalid_review_file",
        "invalid_source_manifest",
        "unsupported_authorization_version",
        "unsupported_proposal_version",
    },
    ErrorCategory.AUTHORITY: {
        "application_plan_hash_mismatch",
        "authority_bundle_hash_mismatch",
        "authorization_not_ready",
        "candidate_record_hash_mismatch",
        "duplicate_authority_in_bundle",
        "duplicate_plan_step",
        "operation_not_supported_by_engine",
        "proposal_hash_mismatch",
        "proposal_not_ready",
        "source_changed_since_authorization",
        "source_changed_since_proposal",
        "source_manifest_hash_mismatch",
        "source_manifest_inventory_mismatch",
        "unknown_plan_authority",
        "unknown_review_candidate",
        "unsupported_operation_composition",
    },
    ErrorCategory.FILESYSTEM: {
        "missing_input_file",
        "output_directory_exists",
        "source_directory_empty",
        "source_directory_missing",
        "source_parquet_unreadable",
        "unreadable_input_file",
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
        _RESULT_PRESENTATION_NARRATION_CLASSIFICATIONS,
        _ANALYTICS_SESSION_CLASSIFICATIONS,
        _MODULE_REGISTRY_CLASSIFICATIONS,
        _OLLAMA_SOAK_CLASSIFICATIONS,
        _REFERENCE_DATASET_VALIDATION_CLASSIFICATIONS,
        _PRODUCT_CANONICAL_PROMOTION_CLASSIFICATIONS,
        _PRODUCT_MATERIALIZATION_CLASSIFICATIONS,
        _GOVERNED_CLEANING_CLASSIFICATIONS,
        _GOVERNED_CLEANING_ENGINE_CLASSIFICATIONS,
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
