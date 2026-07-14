from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .analytics_query_plan import (
    ALLOWED_AGGREGATES,
    IDENTIFIER_PATTERN,
    approved_relationships,
    casefold_lookup,
    catalog_digest,
    load_catalog,
    read_yaml_mapping,
    relationship_is_approved,
)
from .source_onboarding import ensure_dir, file_sha256


CATALOG_NAME = "analytics_semantic_catalog.yml"
BLOCKERS_NAME = "analytics_semantic_catalog_blockers.csv"
REPORT_NAME = "analytics_semantic_catalog_report.md"
OUTPUT_NAMES = {CATALOG_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_TABLES = 256
MAX_DIMENSIONS = 512
MAX_MEASURES = 512
MAX_RELATIONSHIP_PATHS = 256
MAX_PATH_HOPS = 8
MAX_SYNONYMS = 32
MAX_TERM_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 1_000
NUMERIC_TYPE_PREFIXES = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "UHUGEINT",
    "DECIMAL",
    "FLOAT",
    "DOUBLE",
    "REAL",
)
TERM_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class SemanticResolution:
    status: str
    normalized_term: str
    targets: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class AnalyticsSemanticCatalogResult:
    output_dir: Path
    status: str
    catalog_path: Path
    blockers_path: Path
    report_path: Path
    blocker_count: int
    ambiguity_count: int
    outputs_changed: bool
    catalog: dict[str, Any]


def add_blocker(
    blockers: list[dict[str, str]],
    blocker_type: str,
    explanation: str,
    *,
    field: str = "",
) -> None:
    blockers.append(
        {
            "blocker_id": f"BLOCKER_{len(blockers) + 1:03d}",
            "blocker_type": blocker_type,
            "field": field,
            "explanation": explanation,
        }
    )


def normalize_term(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(character for character in decomposed if not unicodedata.combining(character))
    return TERM_SEPARATOR_PATTERN.sub(" ", ascii_value.casefold()).strip()


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
                "unsupported_semantic_field",
                "The semantic catalog contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def required_identifier(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> str | None:
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        add_blocker(
            blockers,
            "invalid_semantic_id",
            "Semantic IDs must be simple identifiers of at most 63 characters.",
            field=field,
        )
        return None
    return value


def required_term(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> str | None:
    if not isinstance(value, str):
        add_blocker(blockers, "invalid_semantic_term", "A business term is required.", field=field)
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > MAX_TERM_LENGTH or not normalize_term(cleaned):
        add_blocker(
            blockers,
            "invalid_semantic_term",
            f"Business terms must contain searchable text within {MAX_TERM_LENGTH} characters.",
            field=field,
        )
        return None
    return cleaned


def optional_description(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value.strip()) > MAX_DESCRIPTION_LENGTH:
        add_blocker(
            blockers,
            "invalid_semantic_description",
            f"Descriptions must be text within {MAX_DESCRIPTION_LENGTH} characters.",
            field=field,
        )
        return ""
    return value.strip()


def clean_synonyms(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        add_blocker(blockers, "invalid_synonyms", "Synonyms must be a list.", field=field)
        return []
    if len(value) > MAX_SYNONYMS:
        add_blocker(
            blockers,
            "synonym_limit_exceeded",
            f"At most {MAX_SYNONYMS} synonyms are allowed per semantic entity.",
            field=field,
        )
    synonyms: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value[:MAX_SYNONYMS]):
        term = required_term(item, blockers, f"{field}[{index}]")
        if not term:
            continue
        normalized = normalize_term(term)
        if normalized not in seen:
            seen.add(normalized)
            synonyms.append(term)
    return synonyms


def list_payload(
    payload: dict[str, Any],
    name: str,
    maximum: int,
    blockers: list[dict[str, str]],
) -> list[Any]:
    rows = payload.get(name, [])
    if not isinstance(rows, list):
        add_blocker(
            blockers,
            "invalid_semantic_collection",
            f"{name} must be a list.",
            field=name,
        )
        return []
    if len(rows) > maximum:
        add_blocker(
            blockers,
            "semantic_collection_limit_exceeded",
            f"{name} accepts at most {maximum} entries.",
            field=name,
        )
    return rows[:maximum]


def resolve_live_table(
    value: Any,
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
    field: str,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        add_blocker(blockers, "invalid_source_table", "A source table is required.", field=field)
        return None
    resolved = casefold_lookup(list(catalog)).get(value.strip().casefold())
    if not resolved:
        add_blocker(
            blockers,
            "unknown_source_table",
            "The semantic table does not resolve unambiguously in the DuckDB catalog.",
            field=field,
        )
        return None
    return resolved


def resolve_live_column(
    table: str,
    value: Any,
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, str] | None:
    if not isinstance(value, str) or not value.strip():
        add_blocker(blockers, "invalid_source_column", "A source column is required.", field=field)
        return None
    lookup = casefold_lookup([column["name"] for column in catalog.get(table, [])])
    resolved = lookup.get(value.strip().casefold())
    if not resolved:
        add_blocker(
            blockers,
            "unknown_source_column",
            "The semantic field does not resolve unambiguously in its source table.",
            field=field,
        )
        return None
    return next(column for column in catalog[table] if column["name"] == resolved)


def base_entity(
    row: dict[str, Any],
    field: str,
    blockers: list[dict[str, str]],
) -> tuple[str | None, str | None, str, list[str]]:
    semantic_id = required_identifier(row.get("id"), blockers, f"{field}.id")
    name = required_term(row.get("name"), blockers, f"{field}.name")
    description = optional_description(row.get("description"), blockers, f"{field}.description")
    synonyms = clean_synonyms(row.get("synonyms"), blockers, f"{field}.synonyms")
    return semantic_id, name, description, synonyms


def compile_dataset(
    payload: dict[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    row = payload.get("dataset")
    if not isinstance(row, dict):
        add_blocker(
            blockers,
            "invalid_dataset_semantics",
            "dataset must be a mapping with an ID and business name.",
            field="dataset",
        )
        return {}
    reject_unknown_fields(row, {"id", "name", "description", "synonyms"}, blockers, "dataset")
    semantic_id, name, description, synonyms = base_entity(row, "dataset", blockers)
    if not semantic_id or not name:
        return {}
    return {
        "id": semantic_id,
        "name": name,
        "description": description,
        "synonyms": synonyms,
    }


def compile_tables(
    payload: dict[str, Any],
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    compiled: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(list_payload(payload, "tables", MAX_TABLES, blockers)):
        field = f"tables[{index}]"
        if not isinstance(item, dict):
            add_blocker(blockers, "invalid_semantic_entity", "Each table must be a mapping.", field=field)
            continue
        reject_unknown_fields(
            item,
            {"id", "source_table", "name", "description", "synonyms"},
            blockers,
            field,
        )
        before = len(blockers)
        semantic_id, name, description, synonyms = base_entity(item, field, blockers)
        source_table = resolve_live_table(item.get("source_table"), catalog, blockers, f"{field}.source_table")
        if semantic_id and semantic_id.casefold() in by_id:
            add_blocker(
                blockers,
                "duplicate_semantic_id",
                "Table semantic IDs must be unique.",
                field=f"{field}.id",
            )
        if len(blockers) != before or not semantic_id or not name or not source_table:
            continue
        row = {
            "id": semantic_id,
            "source_table": source_table,
            "name": name,
            "description": description,
            "synonyms": synonyms,
        }
        by_id[semantic_id.casefold()] = row
        compiled.append(row)
    if not compiled:
        add_blocker(
            blockers,
            "semantic_tables_empty",
            "At least one valid semantic table is required.",
            field="tables",
        )
    return compiled, by_id


def resolve_semantic_table(
    value: Any,
    tables_by_id: dict[str, dict[str, Any]],
    blockers: list[dict[str, str]],
    field: str,
) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value.strip():
        add_blocker(blockers, "invalid_table_id", "A semantic table ID is required.", field=field)
        return None
    table = tables_by_id.get(value.strip().casefold())
    if not table:
        add_blocker(
            blockers,
            "unknown_table_id",
            "The referenced semantic table ID is not valid.",
            field=field,
        )
    return table


def compile_dimensions(
    payload: dict[str, Any],
    tables_by_id: dict[str, dict[str, Any]],
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(list_payload(payload, "dimensions", MAX_DIMENSIONS, blockers)):
        field = f"dimensions[{index}]"
        if not isinstance(item, dict):
            add_blocker(blockers, "invalid_semantic_entity", "Each dimension must be a mapping.", field=field)
            continue
        reject_unknown_fields(
            item,
            {"id", "table_id", "source_column", "name", "description", "synonyms"},
            blockers,
            field,
        )
        before = len(blockers)
        semantic_id, name, description, synonyms = base_entity(item, field, blockers)
        table = resolve_semantic_table(item.get("table_id"), tables_by_id, blockers, f"{field}.table_id")
        column = (
            resolve_live_column(
                table["source_table"],
                item.get("source_column"),
                catalog,
                blockers,
                f"{field}.source_column",
            )
            if table
            else None
        )
        if semantic_id and semantic_id.casefold() in seen:
            add_blocker(blockers, "duplicate_semantic_id", "Dimension IDs must be unique.", field=f"{field}.id")
        if len(blockers) != before or not semantic_id or not name or not table or not column:
            continue
        seen.add(semantic_id.casefold())
        compiled.append(
            {
                "id": semantic_id,
                "table_id": table["id"],
                "source_table": table["source_table"],
                "source_column": column["name"],
                "source_type": column["type"],
                "name": name,
                "description": description,
                "synonyms": synonyms,
            }
        )
    return compiled


def numeric_type(data_type: str) -> bool:
    return data_type.upper().startswith(NUMERIC_TYPE_PREFIXES)


def compile_measures(
    payload: dict[str, Any],
    tables_by_id: dict[str, dict[str, Any]],
    catalog: dict[str, list[dict[str, str]]],
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(list_payload(payload, "measures", MAX_MEASURES, blockers)):
        field = f"measures[{index}]"
        if not isinstance(item, dict):
            add_blocker(blockers, "invalid_semantic_entity", "Each measure must be a mapping.", field=field)
            continue
        reject_unknown_fields(
            item,
            {"id", "table_id", "source_column", "function", "name", "description", "synonyms"},
            blockers,
            field,
        )
        before = len(blockers)
        semantic_id, name, description, synonyms = base_entity(item, field, blockers)
        table = resolve_semantic_table(item.get("table_id"), tables_by_id, blockers, f"{field}.table_id")
        function = str(item.get("function", "")).lower()
        if function not in ALLOWED_AGGREGATES:
            add_blocker(
                blockers,
                "unsupported_measure_function",
                "The measure function is not allowlisted by the analytics planner.",
                field=f"{field}.function",
            )
        source_column = item.get("source_column")
        column: dict[str, str] | None = None
        if function == "count" and source_column == "*":
            column = {"name": "*", "type": "ROW_COUNT"}
        elif table:
            column = resolve_live_column(
                table["source_table"],
                source_column,
                catalog,
                blockers,
                f"{field}.source_column",
            )
        if column and function in {"sum", "avg"} and not numeric_type(column["type"]):
            add_blocker(
                blockers,
                "incompatible_measure_type",
                "SUM and AVG measures require a numeric source column.",
                field=f"{field}.source_column",
            )
        if semantic_id and semantic_id.casefold() in seen:
            add_blocker(blockers, "duplicate_semantic_id", "Measure IDs must be unique.", field=f"{field}.id")
        if len(blockers) != before or not semantic_id or not name or not table or not column:
            continue
        seen.add(semantic_id.casefold())
        compiled.append(
            {
                "id": semantic_id,
                "table_id": table["id"],
                "source_table": table["source_table"],
                "source_column": column["name"],
                "source_type": column["type"],
                "function": function,
                "name": name,
                "description": description,
                "synonyms": synonyms,
            }
        )
    return compiled


def compile_relationship_paths(
    payload: dict[str, Any],
    tables_by_id: dict[str, dict[str, Any]],
    catalog: dict[str, list[dict[str, str]]],
    relationships_payload: dict[str, Any],
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    approved = approved_relationships(relationships_payload, blockers)
    compiled: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(
        list_payload(payload, "relationship_paths", MAX_RELATIONSHIP_PATHS, blockers)
    ):
        field = f"relationship_paths[{index}]"
        if not isinstance(item, dict):
            add_blocker(blockers, "invalid_semantic_entity", "Each relationship path must be a mapping.", field=field)
            continue
        reject_unknown_fields(
            item,
            {"id", "name", "description", "synonyms", "hops"},
            blockers,
            field,
        )
        before = len(blockers)
        semantic_id, name, description, synonyms = base_entity(item, field, blockers)
        if semantic_id and semantic_id.casefold() in seen:
            add_blocker(blockers, "duplicate_semantic_id", "Relationship path IDs must be unique.", field=f"{field}.id")
        hops_payload = item.get("hops", [])
        if not isinstance(hops_payload, list) or not 1 <= len(hops_payload) <= MAX_PATH_HOPS:
            add_blocker(
                blockers,
                "invalid_relationship_path",
                f"Relationship paths require between 1 and {MAX_PATH_HOPS} hops.",
                field=f"{field}.hops",
            )
            hops_payload = []
        hops: list[dict[str, str]] = []
        previous_target_id = ""
        for hop_index, hop in enumerate(hops_payload[:MAX_PATH_HOPS]):
            hop_field = f"{field}.hops[{hop_index}]"
            if not isinstance(hop, dict):
                add_blocker(blockers, "invalid_relationship_hop", "Each relationship hop must be a mapping.", field=hop_field)
                continue
            reject_unknown_fields(
                hop,
                {"source_table_id", "source_column", "target_table_id", "target_column", "kind"},
                blockers,
                hop_field,
            )
            source_table = resolve_semantic_table(
                hop.get("source_table_id"), tables_by_id, blockers, f"{hop_field}.source_table_id"
            )
            target_table = resolve_semantic_table(
                hop.get("target_table_id"), tables_by_id, blockers, f"{hop_field}.target_table_id"
            )
            if previous_target_id and source_table and source_table["id"].casefold() != previous_target_id:
                add_blocker(
                    blockers,
                    "non_contiguous_relationship_path",
                    "Each path hop must start from the previous hop's target table.",
                    field=hop_field,
                )
            source_column = (
                resolve_live_column(
                    source_table["source_table"],
                    hop.get("source_column"),
                    catalog,
                    blockers,
                    f"{hop_field}.source_column",
                )
                if source_table
                else None
            )
            target_column = (
                resolve_live_column(
                    target_table["source_table"],
                    hop.get("target_column"),
                    catalog,
                    blockers,
                    f"{hop_field}.target_column",
                )
                if target_table
                else None
            )
            kind = str(hop.get("kind", "left")).lower()
            if kind not in {"left", "inner"}:
                add_blocker(
                    blockers,
                    "unsupported_join_kind",
                    "Semantic relationship hops support only left or inner joins.",
                    field=f"{hop_field}.kind",
                )
            if source_table and target_table and source_table["id"].casefold() == target_table["id"].casefold():
                add_blocker(
                    blockers,
                    "self_relationship_hop",
                    "A semantic relationship hop must connect two different tables.",
                    field=hop_field,
                )
            if source_table and target_table and source_column and target_column:
                if not relationship_is_approved(
                    approved,
                    source_table["source_table"],
                    source_column["name"],
                    target_table["source_table"],
                    target_column["name"],
                ):
                    add_blocker(
                        blockers,
                        "relationship_not_approved",
                        "Every semantic path hop requires an approved physical relationship.",
                        field=hop_field,
                    )
                else:
                    hops.append(
                        {
                            "source_table_id": source_table["id"],
                            "source_table": source_table["source_table"],
                            "source_column": source_column["name"],
                            "target_table_id": target_table["id"],
                            "target_table": target_table["source_table"],
                            "target_column": target_column["name"],
                            "kind": kind,
                        }
                    )
                previous_target_id = target_table["id"].casefold()
        if len(blockers) != before or not semantic_id or not name or not hops:
            continue
        seen.add(semantic_id.casefold())
        compiled.append(
            {
                "id": semantic_id,
                "name": name,
                "description": description,
                "synonyms": synonyms,
                "hops": hops,
            }
        )
    return compiled


def entity_terms(entity: dict[str, Any], *, include_source_table: bool = False) -> list[str]:
    terms = [entity["id"], entity["name"], *entity.get("synonyms", [])]
    if include_source_table:
        terms.append(entity["source_table"])
    return terms


def build_term_index(
    dataset: dict[str, Any],
    tables: list[dict[str, Any]],
    dimensions: list[dict[str, Any]],
    measures: list[dict[str, Any]],
    relationship_paths: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    term_targets: dict[str, dict[tuple[str, str], dict[str, str]]] = {}

    def add_terms(kind: str, entity: dict[str, Any], terms: list[str]) -> None:
        target = {"kind": kind, "id": entity["id"], "name": entity["name"]}
        for term in terms:
            normalized = normalize_term(term)
            if normalized:
                term_targets.setdefault(normalized, {})[(kind, entity["id"].casefold())] = target

    if dataset:
        add_terms("dataset", dataset, entity_terms(dataset))
    for table in tables:
        add_terms("table", table, entity_terms(table, include_source_table=True))
    for dimension in dimensions:
        add_terms("dimension", dimension, entity_terms(dimension))
    for measure in measures:
        add_terms("measure", measure, entity_terms(measure))
    for path in relationship_paths:
        add_terms("relationship_path", path, entity_terms(path))

    result: list[dict[str, Any]] = []
    for term in sorted(term_targets):
        targets = sorted(term_targets[term].values(), key=lambda row: (row["kind"], row["id"].casefold()))
        candidate_count = len(targets)
        result.append(
            {
                "term": term,
                "status": "resolved" if candidate_count == 1 else "ambiguous",
                "candidate_count": candidate_count,
                "ambiguity_score": round(1 - (1 / candidate_count), 6),
                "requires_clarification": candidate_count > 1,
                "targets": targets,
            }
        )
    return result


def resolve_semantic_term(catalog: dict[str, Any], term: str) -> SemanticResolution:
    normalized = normalize_term(term) if isinstance(term, str) else ""
    if catalog.get("status") == "blocked":
        return SemanticResolution("catalog_blocked", normalized, ())
    for row in catalog.get("term_index", []):
        if isinstance(row, dict) and row.get("term") == normalized:
            targets = tuple(
                {"kind": str(target["kind"]), "id": str(target["id"]), "name": str(target["name"])}
                for target in row.get("targets", [])
                if isinstance(target, dict) and {"kind", "id", "name"} <= set(target)
            )
            return SemanticResolution(str(row.get("status", "unknown")), normalized, targets)
    return SemanticResolution("unknown", normalized, ())


def build_semantic_catalog(
    source_path: Path,
    database_path: Path,
    relationships_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    payload = read_yaml_mapping(source_path, blockers, "semantic_catalog")
    relationships_payload = read_yaml_mapping(relationships_path, blockers, "relationships")
    catalog = load_catalog(database_path, blockers)
    reject_unknown_fields(
        payload,
        {"version", "dataset", "tables", "dimensions", "measures", "relationship_paths"},
        blockers,
        "semantic_catalog",
    )
    if payload.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_semantic_version",
            "The semantic catalog must use contract version 1.",
            field="version",
        )
    dataset = compile_dataset(payload, blockers)
    tables, tables_by_id = compile_tables(payload, catalog, blockers)
    dimensions = compile_dimensions(payload, tables_by_id, catalog, blockers)
    measures = compile_measures(payload, tables_by_id, catalog, blockers)
    relationship_paths = compile_relationship_paths(
        payload,
        tables_by_id,
        catalog,
        relationships_payload,
        blockers,
    )
    term_index = build_term_index(dataset, tables, dimensions, measures, relationship_paths)
    ambiguities = [row["term"] for row in term_index if row["status"] == "ambiguous"]
    database_stat = database_path.stat() if database_path.is_file() else None
    compiled = {
        "version": 1,
        "status": "ready_for_semantic_review" if not blockers else "blocked",
        "source": {
            "semantic_catalog_sha256": file_sha256(source_path) if source_path.is_file() else "",
            "relationships_sha256": (
                file_sha256(relationships_path) if relationships_path.is_file() else ""
            ),
            "catalog_sha256": catalog_digest(catalog) if catalog else "",
            "database_size_bytes": database_stat.st_size if database_stat else 0,
            "database_modified_ns": database_stat.st_mtime_ns if database_stat else 0,
        },
        "dataset": dataset,
        "catalog": {
            "physical_tables": len(catalog),
            "physical_columns": sum(len(columns) for columns in catalog.values()),
            "semantic_tables": len(tables),
            "dimensions": len(dimensions),
            "measures": len(measures),
            "relationship_paths": len(relationship_paths),
            "terms": len(term_index),
            "ambiguities": len(ambiguities),
        },
        "tables": tables,
        "dimensions": dimensions,
        "measures": measures,
        "relationship_paths": relationship_paths,
        "term_index": term_index,
        "ambiguities": ambiguities,
        "approval": {
            "semantic_definitions_approved": False,
            "adapter_use_authorized": False,
            "candidate_relationships_accepted": False,
            "requires_human_semantic_review": True,
        },
        "blockers": blockers,
    }
    return compiled, blockers


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


def render_report(catalog: dict[str, Any]) -> str:
    counts = catalog["catalog"]
    lines = [
        "# Analytics Semantic Catalog Report",
        "",
        f"- Status: `{catalog['status']}`",
        f"- Semantic tables: {counts['semantic_tables']}",
        f"- Dimensions: {counts['dimensions']}",
        f"- Measures: {counts['measures']}",
        f"- Relationship paths: {counts['relationship_paths']}",
        f"- Search terms: {counts['terms']}",
        f"- Ambiguous terms: {counts['ambiguities']}",
        f"- Blockers: {len(catalog['blockers'])}",
        "",
        "## Governance",
        "",
        "- This command validates metadata only and does not query table rows.",
        "- Semantic definitions remain unapproved and require human review.",
        "- Relationship paths use approved physical relationships only.",
        "- Ambiguous terms remain unresolved and require clarification.",
        "- No SQL plan or query execution is produced by Stage 5C.",
        "",
        "## Ambiguities",
        "",
    ]
    if catalog["ambiguities"]:
        lines.extend(f"- `{term}`" for term in catalog["ambiguities"])
    else:
        lines.append("- No ambiguous semantic terms found.")
    lines.extend(["", "## Blockers", ""])
    if catalog["blockers"]:
        lines.extend(
            f"- `{row['blocker_id']}` `{row['blocker_type']}`: "
            f"field=`{row['field'] or 'not_available'}`"
            for row in catalog["blockers"]
        )
    else:
        lines.append("- No technical catalog blockers found.")
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Semantic catalog output path is not a directory: {output_dir}")
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
            f"Different semantic catalog outputs already exist in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_semantic_catalog(
    source_path: Path,
    database_path: Path,
    relationships_path: Path,
    output_dir: Path,
) -> AnalyticsSemanticCatalogResult:
    catalog, blockers = build_semantic_catalog(source_path, database_path, relationships_path)
    contents = {
        CATALOG_NAME: yaml.safe_dump(catalog, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(catalog),
    }
    outputs_changed = write_outputs(output_dir, contents)
    return AnalyticsSemanticCatalogResult(
        output_dir=output_dir,
        status=catalog["status"],
        catalog_path=output_dir / CATALOG_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        blocker_count=len(blockers),
        ambiguity_count=catalog["catalog"]["ambiguities"],
        outputs_changed=outputs_changed,
        catalog=catalog,
    )
