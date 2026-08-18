from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .analytics_query_plan import (
    ALLOWED_AGGREGATES,
    ALLOWED_FILTERS,
    MAX_DIMENSIONS,
    MAX_FILTERS,
    MAX_IN_VALUES,
    MAX_JOINS,
    MAX_LIMIT,
    MAX_METRICS,
    MAX_ORDER_RULES,
    add_blocker,
    read_yaml_mapping,
    scalar_parameter_type,
    valid_alias,
)
from .analytics_semantic_catalog import normalize_term, resolve_semantic_term
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_semantic_adapter_manifest.yml"
REQUEST_NAME = "analytics_request.yml"
BLOCKERS_NAME = "analytics_semantic_adapter_blockers.csv"
CLARIFICATIONS_NAME = "analytics_semantic_clarifications.yml"
REPORT_NAME = "analytics_semantic_adapter_report.md"
OUTPUT_NAMES = {
    MANIFEST_NAME,
    REQUEST_NAME,
    BLOCKERS_NAME,
    CLARIFICATIONS_NAME,
    REPORT_NAME,
}
ALLOWED_INTENT_FIELDS = {
    "version",
    "question",
    "from",
    "relationship_paths",
    "dimensions",
    "metrics",
    "filters",
    "order_by",
    "limit",
}
MAX_QUESTION_LENGTH = 4_000
MAX_RELATIONSHIP_PATHS = 8


@dataclass(frozen=True)
class AnalyticsSemanticAdapterResult:
    output_dir: Path
    status: str
    manifest_path: Path
    request_path: Path | None
    blockers_path: Path
    clarifications_path: Path | None
    report_path: Path
    blocker_count: int
    clarification_count: int
    outputs_changed: bool
    request: dict[str, Any] | None


def add_clarification(
    clarifications: list[dict[str, Any]],
    field: str,
    term: str,
    expected_kind: str,
    targets: tuple[dict[str, str], ...],
) -> None:
    clarifications.append(
        {
            "clarification_id": f"CLARIFICATION_{len(clarifications) + 1:03d}",
            "field": field,
            "term": term.strip(),
            "normalized_term": normalize_term(term),
            "expected_kind": expected_kind,
            "candidates": [dict(target) for target in targets],
        }
    )


def reject_unknown_fields(
    payload: dict[str, Any],
    allowed: set[str],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    for key in payload:
        if key not in allowed:
            add_blocker(
                blockers,
                "unsupported_intent_field",
                "The semantic intent contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def semantic_entities(
    state: dict[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, dict[str, dict[str, Any]]]:
    collections = {
        "table": "tables",
        "dimension": "dimensions",
        "measure": "measures",
        "relationship_path": "relationship_paths",
    }
    entities: dict[str, dict[str, dict[str, Any]]] = {
        "dataset": {},
        **{kind: {} for kind in collections},
    }
    dataset = state.get("dataset")
    if isinstance(dataset, dict):
        dataset_id = dataset.get("id")
        dataset_name = dataset.get("name")
        if isinstance(dataset_id, str) and dataset_id and isinstance(dataset_name, str):
            entities["dataset"][dataset_id.casefold()] = dataset
        else:
            add_blocker(
                blockers,
                "invalid_approved_semantic_state",
                "Approved semantic state requires one dataset ID and name.",
                field="semantic_state.dataset",
            )
    else:
        add_blocker(
            blockers,
            "invalid_approved_semantic_state",
            "Approved semantic state requires one dataset mapping.",
            field="semantic_state.dataset",
        )
    for kind, collection in collections.items():
        rows = state.get(collection, [])
        if not isinstance(rows, list):
            add_blocker(
                blockers,
                "invalid_approved_semantic_state",
                f"Approved semantic {collection} must be a list.",
                field=f"semantic_state.{collection}",
            )
            continue
        for index, row in enumerate(rows):
            field = f"semantic_state.{collection}[{index}]"
            if not isinstance(row, dict):
                add_blocker(
                    blockers,
                    "invalid_approved_semantic_state",
                    f"Approved semantic {kind} entries must be mappings.",
                    field=field,
                )
                continue
            semantic_id = row.get("id")
            name = row.get("name")
            if not isinstance(semantic_id, str) or not semantic_id or not isinstance(name, str):
                add_blocker(
                    blockers,
                    "invalid_approved_semantic_state",
                    f"Approved semantic {kind} entries require IDs and names.",
                    field=field,
                )
                continue
            key = semantic_id.casefold()
            if key in entities[kind]:
                add_blocker(
                    blockers,
                    "duplicate_approved_semantic_id",
                    "Approved semantic IDs must be unique within each kind.",
                    field=field,
                )
                continue
            required_fields = {
                "table": ("source_table",),
                "dimension": ("source_table", "source_column"),
                "measure": ("source_table", "source_column", "function"),
                "relationship_path": ("hops",),
            }[kind]
            if any(
                field_name not in row
                or row[field_name] in (None, "", [])
                for field_name in required_fields
            ):
                add_blocker(
                    blockers,
                    "invalid_approved_semantic_state",
                    f"Approved semantic {kind} is missing required physical metadata.",
                    field=field,
                )
                continue
            if kind == "measure" and row.get("function") not in ALLOWED_AGGREGATES:
                add_blocker(
                    blockers,
                    "invalid_approved_semantic_state",
                    "Approved semantic measures require an allowlisted aggregate.",
                    field=field,
                )
                continue
            entities[kind][key] = row
    return entities


def validate_approved_state(
    state: dict[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, dict[str, dict[str, Any]]]:
    if (
        isinstance(state.get("version"), bool)
        or state.get("version") != 1
        or state.get("status") != "approved"
    ):
        add_blocker(
            blockers,
            "semantic_state_not_approved",
            "Stage 5D requires an applied version-1 approved semantic registry.",
            field="semantic_state.status",
        )
    source = state.get("source")
    required_source_fields = {
        "compiled_semantic_catalog_sha256",
        "review_sha256",
        "decision_digest",
    }
    if not isinstance(source, dict) or any(
        not isinstance(source.get(field), str) or not source[field]
        for field in required_source_fields
    ):
        add_blocker(
            blockers,
            "invalid_semantic_state_source",
            "Approved semantic state requires catalog, review, and decision fingerprints.",
            field="semantic_state.source",
        )
    approval = state.get("approval")
    if not isinstance(approval, dict):
        add_blocker(
            blockers,
            "invalid_semantic_approval",
            "Approved semantic state requires approval metadata.",
            field="semantic_state.approval",
        )
        approval = {}
    if approval.get("semantic_definitions_approved") is not True:
        add_blocker(
            blockers,
            "semantic_definitions_not_approved",
            "Semantic definitions must be explicitly approved before adapter use.",
            field="semantic_state.approval.semantic_definitions_approved",
        )
    if approval.get("adapter_use_authorized") is not True:
        add_blocker(
            blockers,
            "semantic_adapter_not_authorized",
            "The approved state does not authorize Stage 5D adapter use.",
            field="semantic_state.approval.adapter_use_authorized",
        )
    if approval.get("candidate_relationships_accepted") is not False:
        add_blocker(
            blockers,
            "candidate_relationship_authority_invalid",
            "Semantic approval must not authorize candidate physical relationships.",
            field="semantic_state.approval.candidate_relationships_accepted",
        )
    if not isinstance(approval.get("approved_by"), str) or not approval["approved_by"].strip():
        add_blocker(
            blockers,
            "invalid_semantic_approval",
            "Approved semantic state requires human approval identity.",
            field="semantic_state.approval.approved_by",
        )
    if not isinstance(approval.get("approved_at"), str) or not approval["approved_at"].strip():
        add_blocker(
            blockers,
            "invalid_semantic_approval",
            "Approved semantic state requires human approval time.",
            field="semantic_state.approval.approved_at",
        )

    entities = semantic_entities(state, blockers)
    term_index = state.get("term_index")
    if not isinstance(term_index, list):
        add_blocker(
            blockers,
            "invalid_semantic_term_index",
            "Approved semantic state requires a term index.",
            field="semantic_state.term_index",
        )
        return entities
    seen_terms: set[str] = set()
    ambiguous_terms: list[str] = []
    for index, row in enumerate(term_index):
        field = f"semantic_state.term_index[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_semantic_term_index",
                "Every semantic term entry must be a mapping.",
                field=field,
            )
            continue
        term = row.get("term")
        status = row.get("status")
        targets = row.get("targets")
        if not isinstance(term, str) or not term or term != normalize_term(term):
            add_blocker(
                blockers,
                "invalid_semantic_term_index",
                "Semantic term-index keys must be normalized non-empty strings.",
                field=field,
            )
            continue
        if term in seen_terms:
            add_blocker(
                blockers,
                "duplicate_semantic_term",
                "Approved semantic term-index keys must be unique.",
                field=field,
            )
        seen_terms.add(term)
        if status not in {"resolved", "ambiguous"} or not isinstance(targets, list):
            add_blocker(
                blockers,
                "invalid_semantic_term_index",
                "Semantic terms must be resolved or ambiguous with candidate targets.",
                field=field,
            )
            continue
        expected_clarification = status == "ambiguous"
        if row.get("requires_clarification") is not expected_clarification:
            add_blocker(
                blockers,
                "semantic_ambiguity_state_mismatch",
                "Term clarification flags must match resolved or ambiguous status.",
                field=field,
            )
        if (status == "resolved" and len(targets) != 1) or (
            status == "ambiguous" and len(targets) < 2
        ):
            add_blocker(
                blockers,
                "invalid_semantic_term_index",
                "Resolved terms require one target and ambiguous terms require at least two.",
                field=field,
            )
        if row.get("candidate_count") != len(targets):
            add_blocker(
                blockers,
                "invalid_semantic_term_index",
                "Semantic candidate counts must match the stored targets.",
                field=field,
            )
        if status == "ambiguous":
            ambiguous_terms.append(term)
        for target in targets:
            if not isinstance(target, dict):
                add_blocker(
                    blockers,
                    "invalid_semantic_target",
                    "Every semantic target must be a mapping.",
                    field=field,
                )
                continue
            kind = target.get("kind")
            semantic_id = target.get("id")
            name = target.get("name")
            entity = (
                entities.get(str(kind), {}).get(str(semantic_id).casefold())
                if isinstance(kind, str) and isinstance(semantic_id, str)
                else None
            )
            if entity is None or entity.get("name") != name:
                add_blocker(
                    blockers,
                    "unknown_semantic_target",
                    "The term index references an entity outside the approved registry.",
                    field=field,
                )
    if state.get("ambiguities") != ambiguous_terms:
        add_blocker(
            blockers,
            "semantic_ambiguity_state_mismatch",
            "Approved ambiguity summary must match the term index.",
            field="semantic_state.ambiguities",
        )
    if approval.get("requires_clarification") is not bool(ambiguous_terms):
        add_blocker(
            blockers,
            "semantic_ambiguity_state_mismatch",
            "Approval clarification status must match unresolved semantic terms.",
            field="semantic_state.approval.requires_clarification",
        )
    return entities


def resolve_entity(
    state: dict[str, Any],
    entities: dict[str, dict[str, dict[str, Any]]],
    term: Any,
    expected_kind: str,
    field: str,
    blockers: list[dict[str, str]],
    clarifications: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(term, str) or not term.strip():
        add_blocker(
            blockers,
            "invalid_semantic_term",
            "A non-empty semantic term is required.",
            field=field,
        )
        return None
    resolution = resolve_semantic_term(state, term)
    if resolution.status == "ambiguous":
        add_clarification(clarifications, field, term, expected_kind, resolution.targets)
        return None
    if resolution.status != "resolved" or len(resolution.targets) != 1:
        add_blocker(
            blockers,
            "unknown_semantic_term",
            "The requested business term is not present in the approved semantic registry.",
            field=field,
        )
        return None
    target = resolution.targets[0]
    if target["kind"] != expected_kind:
        add_blocker(
            blockers,
            "semantic_kind_mismatch",
            f"This field requires a semantic {expected_kind}.",
            field=field,
        )
        return None
    entity = entities.get(expected_kind, {}).get(target["id"].casefold())
    if entity is None:
        add_blocker(
            blockers,
            "unknown_semantic_target",
            "The resolved target is missing from the approved semantic registry.",
            field=field,
        )
    return entity


def parse_selection_rows(
    intent: dict[str, Any],
    name: str,
    maximum: int,
    expected_kind: str,
    state: dict[str, Any],
    entities: dict[str, dict[str, dict[str, Any]]],
    blockers: list[dict[str, str]],
    clarifications: list[dict[str, Any]],
) -> list[tuple[dict[str, Any] | None, str | None]]:
    rows = intent.get(name, [])
    if not isinstance(rows, list):
        add_blocker(blockers, f"invalid_{name}", f"{name} must be a list.", field=name)
        return []
    if len(rows) > maximum:
        add_blocker(
            blockers,
            f"{name}_limit_exceeded",
            f"At most {maximum} {name} are allowed in one semantic intent.",
            field=name,
        )
    parsed: list[tuple[dict[str, Any] | None, str | None]] = []
    for index, row in enumerate(rows[:maximum]):
        field = f"{name}[{index}]"
        if isinstance(row, str):
            term = row
            alias_value: Any = None
        elif isinstance(row, dict):
            reject_unknown_fields(row, {"term", "alias"}, blockers, field)
            term = row.get("term")
            alias_value = row.get("alias")
        else:
            add_blocker(
                blockers,
                f"invalid_{expected_kind}",
                f"Each {expected_kind} must be a term string or mapping.",
                field=field,
            )
            continue
        entity = resolve_entity(
            state,
            entities,
            term,
            expected_kind,
            f"{field}.term",
            blockers,
            clarifications,
        )
        default_alias = entity.get("id") if entity else None
        if alias_value is None and default_alias is None:
            alias = None
        else:
            alias = valid_alias(
                default_alias if alias_value is None else alias_value,
                blockers,
                f"{field}.alias",
            )
        parsed.append((entity, alias))
    return parsed


def parse_filters(
    intent: dict[str, Any],
    state: dict[str, Any],
    entities: dict[str, dict[str, dict[str, Any]]],
    blockers: list[dict[str, str]],
    clarifications: list[dict[str, Any]],
) -> list[tuple[dict[str, Any] | None, str, Any]]:
    rows = intent.get("filters", [])
    if not isinstance(rows, list):
        add_blocker(blockers, "invalid_filters", "filters must be a list.", field="filters")
        return []
    if len(rows) > MAX_FILTERS:
        add_blocker(
            blockers,
            "filters_limit_exceeded",
            f"At most {MAX_FILTERS} filters are allowed in one semantic intent.",
            field="filters",
        )
    parsed: list[tuple[dict[str, Any] | None, str, Any]] = []
    for index, row in enumerate(rows[:MAX_FILTERS]):
        field = f"filters[{index}]"
        if not isinstance(row, dict):
            add_blocker(blockers, "invalid_filter", "Each filter must be a mapping.", field=field)
            continue
        reject_unknown_fields(row, {"term", "operator", "value"}, blockers, field)
        entity = resolve_entity(
            state,
            entities,
            row.get("term"),
            "dimension",
            f"{field}.term",
            blockers,
            clarifications,
        )
        operator = str(row.get("operator", "")).lower()
        value = row.get("value")
        if operator not in ALLOWED_FILTERS:
            add_blocker(
                blockers,
                "unsupported_filter_operator",
                "The semantic filter operator is not allowlisted.",
                field=f"{field}.operator",
            )
        elif operator in {"is_null", "not_null"}:
            if "value" in row:
                add_blocker(
                    blockers,
                    "unexpected_filter_value",
                    "Null-check filters must not contain a value.",
                    field=f"{field}.value",
                )
        elif operator == "in":
            if not isinstance(value, list) or not 1 <= len(value) <= MAX_IN_VALUES:
                add_blocker(
                    blockers,
                    "invalid_in_filter",
                    f"IN filters require between 1 and {MAX_IN_VALUES} scalar values.",
                    field=f"{field}.value",
                )
            elif any(
                scalar_parameter_type(item) in {None, "null"}
                for item in value
            ):
                add_blocker(
                    blockers,
                    "invalid_filter_value",
                    "Filter values must be non-null scalar YAML values.",
                    field=f"{field}.value",
                )
        elif scalar_parameter_type(value) in {None, "null"}:
            add_blocker(
                blockers,
                "invalid_filter_value",
                "Comparison filters require a non-null scalar YAML value.",
                field=f"{field}.value",
            )
        parsed.append((entity, operator, value))
    return parsed


def parse_order_by(
    intent: dict[str, Any],
    blockers: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows = intent.get("order_by", [])
    if not isinstance(rows, list):
        add_blocker(blockers, "invalid_order_by", "order_by must be a list.", field="order_by")
        return []
    if len(rows) > MAX_ORDER_RULES:
        add_blocker(
            blockers,
            "order_by_limit_exceeded",
            f"At most {MAX_ORDER_RULES} order rules are allowed in one semantic intent.",
            field="order_by",
        )
    parsed: list[dict[str, str]] = []
    for index, row in enumerate(rows[:MAX_ORDER_RULES]):
        field = f"order_by[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_order_rule",
                "Each order rule must be a mapping.",
                field=field,
            )
            continue
        reject_unknown_fields(row, {"field", "direction"}, blockers, field)
        alias = valid_alias(row.get("field"), blockers, f"{field}.field")
        direction = str(row.get("direction", "asc")).lower()
        if direction not in {"asc", "desc"}:
            add_blocker(
                blockers,
                "invalid_order_direction",
                "Order direction must be asc or desc.",
                field=f"{field}.direction",
            )
        if alias and direction in {"asc", "desc"}:
            parsed.append({"field": alias, "direction": direction})
    return parsed


def compile_intent(
    intent: dict[str, Any],
    state: dict[str, Any],
    blockers: list[dict[str, str]],
    clarifications: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for key in intent:
        if key == "sql":
            add_blocker(
                blockers,
                "raw_sql_not_allowed",
                "Stage 5D never accepts or emits model-generated SQL.",
                field="sql",
            )
        elif key == "joins":
            add_blocker(
                blockers,
                "physical_join_not_allowed",
                "Stage 5D accepts approved semantic relationship paths, not physical joins.",
                field="joins",
            )
        elif key not in ALLOWED_INTENT_FIELDS:
            add_blocker(
                blockers,
                "unsupported_intent_field",
                "The semantic intent contains a field outside the version-1 contract.",
                field=key,
            )
    if isinstance(intent.get("version"), bool) or intent.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_intent_version",
            "The semantic intent must use contract version 1.",
            field="version",
        )
    question = intent.get("question")
    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question.strip()) > MAX_QUESTION_LENGTH
    ):
        add_blocker(
            blockers,
            "invalid_question",
            f"A question of at most {MAX_QUESTION_LENGTH} characters is required.",
            field="question",
        )

    entities = validate_approved_state(state, blockers)
    base_entity = resolve_entity(
        state,
        entities,
        intent.get("from"),
        "table",
        "from",
        blockers,
        clarifications,
    )

    path_terms = intent.get("relationship_paths", [])
    if not isinstance(path_terms, list):
        add_blocker(
            blockers,
            "invalid_relationship_paths",
            "relationship_paths must be a list of semantic terms.",
            field="relationship_paths",
        )
        path_terms = []
    if len(path_terms) > MAX_RELATIONSHIP_PATHS:
        add_blocker(
            blockers,
            "relationship_path_limit_exceeded",
            f"At most {MAX_RELATIONSHIP_PATHS} paths are allowed in one semantic intent.",
            field="relationship_paths",
        )
    paths = [
        resolve_entity(
            state,
            entities,
            term,
            "relationship_path",
            f"relationship_paths[{index}]",
            blockers,
            clarifications,
        )
        for index, term in enumerate(path_terms[:MAX_RELATIONSHIP_PATHS])
    ]
    dimensions = parse_selection_rows(
        intent,
        "dimensions",
        MAX_DIMENSIONS,
        "dimension",
        state,
        entities,
        blockers,
        clarifications,
    )
    metrics = parse_selection_rows(
        intent,
        "metrics",
        MAX_METRICS,
        "measure",
        state,
        entities,
        blockers,
        clarifications,
    )
    filters = parse_filters(intent, state, entities, blockers, clarifications)
    order_by = parse_order_by(intent, blockers)
    limit = intent.get("limit", 1_000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        add_blocker(
            blockers,
            "invalid_limit",
            f"Limit must be an integer between 1 and {MAX_LIMIT}.",
            field="limit",
        )
    if not dimensions and not metrics:
        add_blocker(
            blockers,
            "empty_selection",
            "At least one semantic dimension or measure is required.",
            field="dimensions/metrics",
        )

    if blockers or clarifications:
        return None
    assert base_entity is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
    assert isinstance(limit, int)  # noqa: S101 - type narrowing after a guard that already returned; not validation

    base_table = str(base_entity.get("source_table", ""))
    selected_tables = {base_table}
    joins: list[dict[str, str]] = []
    for path_index, path in enumerate(paths):
        assert path is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
        hops = path.get("hops", [])
        if not isinstance(hops, list) or not hops:
            add_blocker(
                blockers,
                "invalid_approved_relationship_path",
                "Approved semantic relationship paths require at least one hop.",
                field=f"relationship_paths[{path_index}]",
            )
            continue
        for hop_index, hop in enumerate(hops):
            field = f"relationship_paths[{path_index}].hops[{hop_index}]"
            if not isinstance(hop, dict):
                add_blocker(
                    blockers,
                    "invalid_approved_relationship_path",
                    "Approved semantic relationship hops must be mappings.",
                    field=field,
                )
                continue
            source_table = str(hop.get("source_table", ""))
            target_table = str(hop.get("target_table", ""))
            if source_table not in selected_tables or target_table in selected_tables:
                add_blocker(
                    blockers,
                    "invalid_semantic_path_order",
                    "Each semantic path must connect a selected table to one new table.",
                    field=field,
                )
                continue
            join = {
                "source_table": source_table,
                "source_column": str(hop.get("source_column", "")),
                "target_table": target_table,
                "target_column": str(hop.get("target_column", "")),
                "kind": str(hop.get("kind", "")),
            }
            if any(not value for value in join.values()) or join["kind"] not in {"left", "inner"}:
                add_blocker(
                    blockers,
                    "invalid_approved_relationship_path",
                    "Approved semantic relationship hops require complete physical metadata.",
                    field=field,
                )
                continue
            joins.append(join)
            selected_tables.add(target_table)
    if len(joins) > MAX_JOINS:
        add_blocker(
            blockers,
            "join_limit_exceeded",
            f"Expanded semantic paths exceed the Stage 5A limit of {MAX_JOINS} joins.",
            field="relationship_paths",
        )

    request_dimensions: list[dict[str, str]] = []
    request_metrics: list[dict[str, str]] = []
    output_aliases: set[str] = set()
    for index, (entity, alias) in enumerate(dimensions):
        assert entity is not None and alias is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
        source_table = str(entity.get("source_table", ""))
        if source_table not in selected_tables:
            add_blocker(
                blockers,
                "semantic_table_not_selected",
                "A selected dimension requires an approved relationship path to its table.",
                field=f"dimensions[{index}]",
            )
        if alias.casefold() in output_aliases:
            add_blocker(
                blockers,
                "duplicate_output_alias",
                "Every selected semantic field must have a unique output alias.",
                field=f"dimensions[{index}].alias",
            )
        output_aliases.add(alias.casefold())
        request_dimensions.append(
            {
                "column": f"{source_table}.{entity.get('source_column', '')}",
                "alias": alias,
            }
        )
    for index, (entity, alias) in enumerate(metrics):
        assert entity is not None and alias is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
        source_table = str(entity.get("source_table", ""))
        source_column = str(entity.get("source_column", ""))
        if source_table not in selected_tables:
            add_blocker(
                blockers,
                "semantic_table_not_selected",
                "A selected measure requires an approved relationship path to its table.",
                field=f"metrics[{index}]",
            )
        if alias.casefold() in output_aliases:
            add_blocker(
                blockers,
                "duplicate_output_alias",
                "Every selected semantic field must have a unique output alias.",
                field=f"metrics[{index}].alias",
            )
        output_aliases.add(alias.casefold())
        request_metrics.append(
            {
                "function": str(entity.get("function", "")),
                "column": "*" if source_column == "*" else f"{source_table}.{source_column}",
                "alias": alias,
            }
        )

    request_filters: list[dict[str, Any]] = []
    for index, (entity, operator, value) in enumerate(filters):
        assert entity is not None  # noqa: S101 - type narrowing after a guard that already returned; not validation
        source_table = str(entity.get("source_table", ""))
        if source_table not in selected_tables:
            add_blocker(
                blockers,
                "semantic_table_not_selected",
                "A semantic filter requires an approved relationship path to its table.",
                field=f"filters[{index}]",
            )
        row: dict[str, Any] = {
            "column": f"{source_table}.{entity.get('source_column', '')}",
            "operator": operator,
        }
        if operator not in {"is_null", "not_null"}:
            row["value"] = value
        request_filters.append(row)
    for index, order in enumerate(order_by):
        if order["field"].casefold() not in output_aliases:
            add_blocker(
                blockers,
                "unknown_order_field",
                "Order fields must reference a selected output alias.",
                field=f"order_by[{index}].field",
            )
    if blockers:
        return None
    return {
        "version": 1,
        "question": question.strip(),
        "from": base_table,
        "joins": joins,
        "dimensions": request_dimensions,
        "metrics": request_metrics,
        "filters": request_filters,
        "order_by": order_by,
        "limit": limit,
    }


def blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["blocker_id", "blocker_type", "field", "explanation"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def render_report(status: str, blockers: list[dict[str, str]], clarifications: list[dict[str, Any]]) -> str:
    lines = [
        "# Analytics Semantic Adapter Report",
        "",
        f"- Status: `{status}`",
        f"- Blockers: {len(blockers)}",
        f"- Clarifications: {len(clarifications)}",
        "",
        "## Governance",
        "",
        "- Stage 5D consumes only an explicitly approved semantic registry.",
        "- The adapter accepts structured semantic intent, not raw SQL.",
        "- Aggregates and physical columns come from approved semantic definitions.",
        "- Physical joins come only from approved semantic relationship paths.",
        "- Ambiguous terms produce clarification evidence and are never selected automatically.",
        "- Stage 5A must still validate the generated request against live DuckDB metadata.",
        "- No model API, database, query, migration, import, or synchronization is used.",
        "",
        "## Result",
        "",
    ]
    if status == "ready_for_query_plan":
        lines.append("- A version-1 structured analytics request was generated for Stage 5A.")
    elif status == "clarification_required":
        lines.append("- No request was generated; explicit semantic clarification is required.")
    else:
        lines.append("- No request was generated; contract or approval blockers must be corrected.")
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Semantic adapter output path is not a directory: {output_dir}")
    existing = (
        {
            path.name: path
            for path in output_dir.iterdir()
            if path.is_file() and path.name in OUTPUT_NAMES
        }
        if output_dir.exists()
        else {}
    )
    if existing:
        exact = set(existing) == set(contents) and all(
            existing[name].read_text(encoding="utf-8") == content
            for name, content in contents.items()
        )
        if exact:
            return False
        raise ValueError(
            f"Different semantic adapter evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_semantic_adapter(
    intent_path: Path,
    semantic_state_path: Path,
    output_dir: Path,
) -> AnalyticsSemanticAdapterResult:
    blockers: list[dict[str, str]] = []
    clarifications: list[dict[str, Any]] = []
    intent = read_yaml_mapping(intent_path, blockers, "intent")
    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")
    request = compile_intent(intent, state, blockers, clarifications)
    status = (
        "blocked"
        if blockers
        else "clarification_required"
        if clarifications
        else "ready_for_query_plan"
    )
    request_content = (
        yaml.safe_dump(request, sort_keys=False, allow_unicode=False)
        if request is not None
        else ""
    )
    source = {
        "intent_sha256": file_sha256(intent_path) if intent_path.is_file() else "",
        "approved_semantic_state_sha256": (
            file_sha256(semantic_state_path) if semantic_state_path.is_file() else ""
        ),
    }
    manifest = {
        "version": 1,
        "status": status,
        "source": source,
        "contract": {
            "semantic_intent_version": intent.get("version") if isinstance(intent, dict) else None,
            "analytics_request_version": 1 if request is not None else None,
            "raw_sql_accepted": False,
            "model_api_used": False,
            "database_accessed": False,
        },
        "counts": {
            "blockers": len(blockers),
            "clarifications": len(clarifications),
        },
        "request_sha256": content_sha256(request_content) if request_content else "",
    }
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(status, blockers, clarifications),
    }
    if request_content:
        contents[REQUEST_NAME] = request_content
    if clarifications:
        clarification_payload = {
            "version": 1,
            "status": "clarification_required",
            "source": source,
            "clarifications": clarifications,
        }
        contents[CLARIFICATIONS_NAME] = yaml.safe_dump(
            clarification_payload,
            sort_keys=False,
            allow_unicode=False,
        )
    outputs_changed = write_outputs(output_dir, contents)
    return AnalyticsSemanticAdapterResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        request_path=(output_dir / REQUEST_NAME) if request is not None else None,
        blockers_path=output_dir / BLOCKERS_NAME,
        clarifications_path=(
            output_dir / CLARIFICATIONS_NAME if clarifications else None
        ),
        report_path=output_dir / REPORT_NAME,
        blocker_count=len(blockers),
        clarification_count=len(clarifications),
        outputs_changed=outputs_changed,
        request=request,
    )
