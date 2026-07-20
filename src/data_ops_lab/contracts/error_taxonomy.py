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


@dataclass(frozen=True)
class ErrorClassification:
    code: str
    category: ErrorCategory
    registered: bool


_AUTHORITY_CODES = {
    "database_changed_after_plan_revalidation",
    "database_changed_during_execution",
    "execution_inputs_changed",
    "reviewed_plan_mismatch",
    "semantic_catalog_drift",
}

_APPROVAL_CODES = {
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
    "unexpected_selected_target",
    "unknown_ambiguity_decision",
    "unknown_entity_decision",
}

_EXECUTION_LIMIT_CODES = {
    "dimension_limit_exceeded",
    "filter_limit_exceeded",
    "join_limit_exceeded",
    "metric_limit_exceeded",
    "order_limit_exceeded",
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
    "duplicate_output_alias",
    "duplicate_semantic_id",
    "empty_selection",
    "incompatible_measure_type",
    "invalid_ambiguity_decisions",
    "invalid_approved_relationship",
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
    "invalid_metric",
    "invalid_metrics",
    "invalid_order_by",
    "invalid_order_direction",
    "invalid_order_rule",
    "invalid_output_alias",
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
    "invalid_semantic_term",
    "invalid_source_column",
    "invalid_source_table",
    "invalid_synonyms",
    "invalid_table",
    "invalid_table_id",
    "invalid_yaml",
    "invalid_yaml_mapping",
    "non_contiguous_relationship_path",
    "self_relationship_hop",
    "semantic_tables_empty",
    "unknown_column",
    "unknown_order_field",
    "unknown_source_column",
    "unknown_source_table",
    "unknown_table",
    "unknown_table_id",
    "unsupported_aggregate",
    "unsupported_filter_operator",
    "unsupported_join_kind",
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


def _build_registry() -> dict[str, ErrorCategory]:
    groups = {
        ErrorCategory.CONTRACT: _CONTRACT_CODES,
        ErrorCategory.AUTHORITY: _AUTHORITY_CODES,
        ErrorCategory.APPROVAL: _APPROVAL_CODES,
        ErrorCategory.EXECUTION_LIMIT: _EXECUTION_LIMIT_CODES,
        ErrorCategory.FILESYSTEM: _FILESYSTEM_CODES,
        ErrorCategory.UNCLASSIFIED: _REVIEWED_UNCLASSIFIED_CODES,
    }
    registry: dict[str, ErrorCategory] = {}
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
