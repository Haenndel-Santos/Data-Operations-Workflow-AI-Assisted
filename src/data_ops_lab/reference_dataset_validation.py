from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from .contracts.hashing import file_sha256


MODULE_VERSION = 3
MANIFEST_NAME = "reference_dataset_validation.yml"
REVIEW_NAME = "relationship_review.yml"
APPROVED_RELATIONSHIPS_NAME = "approved_relationships.yml"
REPORT_NAME = "reference_dataset_report.md"
IDENTIFIER_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,62}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SPDX_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,63}")
REQUIRED_LOCAL_SCOPES = (
    "local_conversion",
    "local_profiling",
    "local_benchmark_design",
    "local_offline_evaluation",
)
REQUIRED_CLOSED_SCOPES = (
    "external_upload",
    "model_parameter_training",
    "publication",
)


@dataclass(frozen=True)
class ReferenceDatasetValidationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    review_path: Path
    approved_relationships_path: Path
    report_path: Path
    blocker_count: int
    table_count: int
    row_count: int
    primary_key_count: int
    relationship_count: int
    approved_relationship_count: int
    outputs_changed: bool


def quote_identifier(value: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe normalized identifier: {value!r}")
    return f'"{value}"'


def add_blocker(
    blockers: list[dict[str, str]],
    code: str,
    message: str,
    field: str,
) -> None:
    blockers.append({"code": code, "message": message, "field": field})


def load_yaml(path: Path, field: str, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(blockers, "missing_file", "Required local YAML file is missing.", field)
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        add_blocker(blockers, "invalid_yaml", "Required local YAML is not valid UTF-8 YAML.", field)
        return {}
    if not isinstance(payload, dict):
        add_blocker(blockers, "invalid_yaml_mapping", "Required YAML root must be a mapping.", field)
        return {}
    return payload


def normalized_path(value: Any, field: str, blockers: list[dict[str, str]]) -> Path | None:
    if not isinstance(value, str) or not value.strip() or "://" in value:
        add_blocker(blockers, "invalid_local_path", "A non-URL local path is required.", field)
        return None
    return Path(value).expanduser().resolve()


def validate_hash(
    path: Path | None,
    expected: Any,
    field: str,
    blockers: list[dict[str, str]],
) -> str | None:
    if path is None:
        return None
    if not path.is_file():
        add_blocker(blockers, "missing_file", "Required local file is missing.", field)
        return None
    if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
        add_blocker(blockers, "invalid_sha256", "Expected SHA-256 must be 64 lowercase hexadecimal characters.", field)
        return None
    actual = file_sha256(path)
    if actual != expected:
        add_blocker(blockers, "sha256_mismatch", "Local file does not match its versioned SHA-256.", field)
    return actual


def validate_source(
    payload: dict[str, Any], blockers: list[dict[str, str]]
) -> tuple[Path | None, dict[str, Any]]:
    source = payload.get("source")
    if not isinstance(source, dict):
        add_blocker(blockers, "invalid_source", "A source mapping is required.", "source")
        return None, {}
    path = normalized_path(source.get("local_path"), "source.local_path", blockers)
    actual_hash = validate_hash(path, source.get("sha256"), "source.sha256", blockers)
    if path and path.is_file() and source.get("bytes") != path.stat().st_size:
        add_blocker(blockers, "source_size_mismatch", "Source byte count does not match the local file.", "source.bytes")
    if source.get("provenance_status") != "verified_exact_official_copy":
        add_blocker(blockers, "unverified_provenance", "Source provenance must be an exact verified official copy.", "source.provenance_status")
    official = source.get("official")
    if not isinstance(official, dict):
        add_blocker(blockers, "invalid_official_source", "Official source metadata is required.", "source.official")
        official = {}
    for name in ("repository", "path", "permalink", "blob_sha"):
        if not isinstance(official.get(name), str) or not official[name].strip():
            add_blocker(blockers, "missing_official_source_field", "Official source metadata is incomplete.", f"source.official.{name}")
    if not isinstance(official.get("commit"), str) or not COMMIT_PATTERN.fullmatch(official["commit"]):
        add_blocker(blockers, "invalid_source_commit", "Official source commit must be a full Git commit hash.", "source.official.commit")
    return path, {
        "local_path": source.get("local_path"),
        "bytes": path.stat().st_size if path and path.is_file() else None,
        "sha256": actual_hash,
        "provenance_status": source.get("provenance_status"),
        "official": official,
    }


def validate_license(payload: dict[str, Any], blockers: list[dict[str, str]]) -> dict[str, Any]:
    license_payload = payload.get("license")
    if not isinstance(license_payload, dict):
        add_blocker(blockers, "invalid_license", "A verified license mapping is required.", "license")
        return {}
    if license_payload.get("status") != "verified":
        add_blocker(blockers, "unverified_license", "Dataset license must be verified.", "license.status")
    spdx = license_payload.get("spdx")
    if not isinstance(spdx, str) or not SPDX_PATTERN.fullmatch(spdx):
        add_blocker(blockers, "invalid_spdx", "A valid SPDX-style license identifier is required.", "license.spdx")
    if not isinstance(license_payload.get("permalink"), str) or not license_payload["permalink"].startswith("https://"):
        add_blocker(blockers, "invalid_license_permalink", "A fixed HTTPS license permalink is required.", "license.permalink")
    if not isinstance(license_payload.get("commit"), str) or not COMMIT_PATTERN.fullmatch(license_payload["commit"]):
        add_blocker(blockers, "invalid_license_commit", "License commit must be a full Git commit hash.", "license.commit")
    return license_payload


def artifact_path(base: Path, value: Any, field: str, blockers: list[dict[str, str]]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        add_blocker(blockers, "invalid_artifact_path", "A relative artifact path is required.", field)
        return None
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()):
        add_blocker(blockers, "artifact_path_escape", "Artifact path must remain inside its conversion directory.", field)
        return None
    return path


def validate_conversion_artifacts(
    manifest: dict[str, Any],
    manifest_path: Path,
    blockers: list[dict[str, str]],
    field_prefix: str,
) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        add_blocker(blockers, "invalid_conversion_artifacts", "Conversion manifest artifacts are required.", f"{field_prefix}.artifacts")
        return {}
    entries: list[tuple[str, dict[str, Any]]] = []
    for name in ("database", "relationships", "report"):
        item = artifacts.get(name)
        if not isinstance(item, dict):
            add_blocker(blockers, "invalid_conversion_artifact", "Conversion artifact entry is missing.", f"{field_prefix}.artifacts.{name}")
        else:
            entries.append((name, item))
    schema = artifacts.get("schema")
    if schema is not None:
        if not isinstance(schema, dict):
            add_blocker(
                blockers,
                "invalid_conversion_artifact",
                "Optional conversion schema artifact entry must be a mapping.",
                f"{field_prefix}.artifacts.schema",
            )
        else:
            entries.append(("schema", schema))
    parquet = artifacts.get("parquet")
    if not isinstance(parquet, list):
        add_blocker(blockers, "invalid_parquet_artifacts", "Parquet artifact entries must be a list.", f"{field_prefix}.artifacts.parquet")
        parquet = []
    for index, item in enumerate(parquet):
        if not isinstance(item, dict):
            add_blocker(blockers, "invalid_parquet_artifact", "Parquet artifact entry must be a mapping.", f"{field_prefix}.artifacts.parquet[{index}]")
            continue
        entries.append((f"parquet[{index}]", item))
    resolved: dict[str, Any] = {"parquet": []}
    for name, item in entries:
        field = f"{field_prefix}.artifacts.{name}"
        path = artifact_path(manifest_path.parent, item.get("path"), f"{field}.path", blockers)
        actual = validate_hash(path, item.get("sha256"), f"{field}.sha256", blockers)
        evidence = {"path": item.get("path"), "sha256": actual}
        if name.startswith("parquet["):
            evidence.update({"table": item.get("table"), "rows": item.get("rows")})
            resolved["parquet"].append(evidence)
        else:
            resolved[name] = {**evidence, "resolved_path": path}
    return resolved


def conversion_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", {})
    return {
        "status": manifest.get("status"),
        "dataset": manifest.get("dataset"),
        "source": manifest.get("source"),
        "conversion": manifest.get("conversion"),
        "counts": manifest.get("counts"),
        "tables": manifest.get("tables"),
        "parquet": artifacts.get("parquet"),
        "relationships": artifacts.get("relationships"),
        "schema": artifacts.get("schema"),
        "report": artifacts.get("report"),
    }


def validate_conversion(
    payload: dict[str, Any],
    source_evidence: dict[str, Any],
    blockers: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = payload.get("conversion")
    if not isinstance(config, dict):
        add_blocker(blockers, "invalid_conversion", "Conversion metadata is required.", "conversion")
        return {}, {}, {}
    manifest_path = normalized_path(config.get("manifest_path"), "conversion.manifest_path", blockers)
    validate_hash(manifest_path, config.get("manifest_sha256"), "conversion.manifest_sha256", blockers)
    manifest = load_yaml(manifest_path, "conversion.manifest_path", blockers) if manifest_path else {}
    if manifest:
        if manifest.get("status") != "ready_for_local_benchmark":
            add_blocker(blockers, "conversion_not_ready", "Conversion manifest is not ready for local benchmark use.", "conversion.status")
        if manifest.get("dataset") != payload.get("dataset"):
            add_blocker(blockers, "conversion_dataset_mismatch", "Conversion dataset does not match the reference manifest.", "conversion.dataset")
        if manifest.get("source", {}).get("sha256") != source_evidence.get("sha256"):
            add_blocker(blockers, "conversion_source_mismatch", "Conversion is not bound to the verified source hash.", "conversion.source.sha256")
    artifacts = validate_conversion_artifacts(manifest, manifest_path, blockers, "conversion") if manifest and manifest_path else {}

    reproduction = config.get("reproduction")
    if not isinstance(reproduction, dict):
        add_blocker(blockers, "missing_reproduction", "An independent reproduction manifest is required.", "conversion.reproduction")
        return manifest, artifacts, {"equivalent": False}
    reproduction_path = normalized_path(reproduction.get("manifest_path"), "conversion.reproduction.manifest_path", blockers)
    reproduction_manifest = load_yaml(reproduction_path, "conversion.reproduction.manifest_path", blockers) if reproduction_path else {}
    reproduction_artifacts = (
        validate_conversion_artifacts(reproduction_manifest, reproduction_path, blockers, "conversion.reproduction")
        if reproduction_manifest and reproduction_path
        else {}
    )
    equivalent = bool(manifest and reproduction_manifest and conversion_projection(manifest) == conversion_projection(reproduction_manifest))
    if not equivalent:
        add_blocker(blockers, "reproduction_mismatch", "Independent conversion does not reproduce schema, counts, Parquet, relationships, and report hashes.", "conversion.reproduction")
    return manifest, artifacts, {
        "manifest_path": reproduction.get("manifest_path"),
        "manifest_sha256": file_sha256(reproduction_path) if reproduction_path and reproduction_path.is_file() else None,
        "equivalent": equivalent,
        "parquet_artifacts": len(reproduction_artifacts.get("parquet", [])),
        "database_sha256": reproduction_artifacts.get("database", {}).get("sha256"),
    }


def validate_benchmark_use(payload: dict[str, Any], blockers: list[dict[str, str]]) -> dict[str, Any]:
    use = payload.get("benchmark_use")
    if not isinstance(use, dict):
        add_blocker(blockers, "missing_benchmark_use", "Explicit benchmark-use authority is required.", "benchmark_use")
        return {}
    if use.get("status") != "approved":
        add_blocker(blockers, "benchmark_use_not_approved", "Local benchmark use has not been approved.", "benchmark_use.status")
    if not isinstance(use.get("approved_by"), str) or not use["approved_by"].strip():
        add_blocker(blockers, "missing_benchmark_approver", "Benchmark approval authority is required.", "benchmark_use.approved_by")
    try:
        datetime.fromisoformat(str(use.get("approved_at")))
    except ValueError:
        add_blocker(blockers, "invalid_benchmark_approval_time", "Benchmark approval time must be ISO-8601.", "benchmark_use.approved_at")
    scopes = use.get("scopes")
    if not isinstance(scopes, dict):
        add_blocker(blockers, "invalid_benchmark_scopes", "Benchmark-use scopes are required.", "benchmark_use.scopes")
        return use
    for scope in REQUIRED_LOCAL_SCOPES:
        if scopes.get(scope) != "approved":
            add_blocker(blockers, "local_scope_not_approved", "Required local benchmark scope is not approved.", f"benchmark_use.scopes.{scope}")
    for scope in REQUIRED_CLOSED_SCOPES:
        if scopes.get(scope) != "not_authorized":
            add_blocker(blockers, "unsafe_scope_state", "External, publication, and training scopes must remain not authorized.", f"benchmark_use.scopes.{scope}")
    return use


def expected_catalog(conversion_manifest: dict[str, Any], blockers: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    rows = conversion_manifest.get("tables")
    if not isinstance(rows, list):
        add_blocker(blockers, "invalid_conversion_tables", "Conversion table metadata must be a list.", "conversion.tables")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not IDENTIFIER_PATTERN.fullmatch(str(row.get("name", ""))):
            add_blocker(blockers, "invalid_conversion_table", "Converted table metadata is invalid.", f"conversion.tables[{index}]")
            continue
        columns = row.get("columns")
        if not isinstance(columns, list):
            add_blocker(blockers, "invalid_conversion_columns", "Converted columns must be a list.", f"conversion.tables[{index}].columns")
            continue
        normalized_columns = []
        for column_index, column in enumerate(columns):
            if not isinstance(column, dict) or not IDENTIFIER_PATTERN.fullmatch(str(column.get("name", ""))):
                add_blocker(blockers, "invalid_conversion_column", "Converted column metadata is invalid.", f"conversion.tables[{index}].columns[{column_index}]")
                continue
            normalized_columns.append({"name": column["name"], "type": column.get("duckdb_type")})
        result[row["name"]] = {"rows": row.get("rows"), "columns": normalized_columns}
    return result


def validate_primary_key_config(
    payload: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    schema = payload.get("schema")
    if not isinstance(schema, dict):
        add_blocker(blockers, "invalid_schema_review", "Schema review metadata is required.", "schema")
        return []
    keys = schema.get("primary_keys")
    if not isinstance(keys, list):
        add_blocker(blockers, "invalid_primary_keys", "Primary keys must be a list.", "schema.primary_keys")
        return []
    if schema.get("expected_primary_keys") != len(keys):
        add_blocker(blockers, "primary_key_count_mismatch", "Expected primary-key count does not match configured candidates.", "schema.expected_primary_keys")
    normalized = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for index, key in enumerate(keys):
        field = f"schema.primary_keys[{index}]"
        if not isinstance(key, dict):
            add_blocker(blockers, "invalid_primary_key", "Primary-key entry must be a mapping.", field)
            continue
        table = key.get("table")
        columns = key.get("columns")
        if table not in catalog or not isinstance(columns, list) or not columns:
            add_blocker(blockers, "unknown_primary_key", "Primary-key table and columns must exist in the converted schema.", field)
            continue
        known_columns = {column["name"] for column in catalog[table]["columns"]}
        if any(not isinstance(column, str) or column not in known_columns for column in columns):
            add_blocker(blockers, "unknown_primary_key_column", "Primary-key column is absent from the converted schema.", field)
            continue
        identity = (table, tuple(columns))
        if identity in seen:
            add_blocker(blockers, "duplicate_primary_key", "Primary-key entry is duplicated.", field)
            continue
        seen.add(identity)
        if key.get("evidence") != "source_declared_primary_key":
            add_blocker(blockers, "invalid_primary_key_evidence", "Primary-key evidence must come from a source declaration.", f"{field}.evidence")
        normalized.append({"table": table, "columns": columns, "evidence": key.get("evidence")})
    return normalized


def load_relationships(
    conversion_artifacts: dict[str, Any],
    expected_count: Any,
    blockers: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], str | None]:
    relationship_artifact = conversion_artifacts.get("relationships", {})
    path = relationship_artifact.get("resolved_path")
    payload = load_yaml(path, "conversion.artifacts.relationships", blockers) if isinstance(path, Path) else {}
    contract_version = payload.get("version")
    if contract_version not in {1, 2}:
        add_blocker(
            blockers,
            "invalid_relationship_candidates",
            "Relationship candidate artifact version must be 1 or 2.",
            "relationships.version",
        )
    rows = payload.get("relationship_candidates")
    if not isinstance(rows, list):
        add_blocker(blockers, "invalid_relationship_candidates", "Relationship candidates must be a list.", "relationships")
        return [], relationship_artifact.get("sha256")
    if expected_count != len(rows):
        add_blocker(blockers, "relationship_count_mismatch", "Expected relationship count does not match the conversion candidates.", "relationships.expected_candidates")
    normalized = []
    seen: set[tuple[str, tuple[str, ...], str, tuple[str, ...]]] = set()
    for index, row in enumerate(rows):
        field = f"relationships[{index}]"
        if not isinstance(row, dict):
            add_blocker(blockers, "invalid_relationship", "Relationship candidate must be a mapping.", field)
            continue
        source_table = row.get("source_table")
        target_table = row.get("target_table")
        if contract_version == 1:
            source_column = row.get("source_column")
            target_column = row.get("target_column")
            flat_identity = (source_table, source_column, target_table, target_column)
            if any(
                not isinstance(value, str)
                or not IDENTIFIER_PATTERN.fullmatch(value)
                for value in flat_identity
            ):
                add_blocker(blockers, "invalid_relationship_identifier", "Relationship identifiers must be normalized safe names.", field)
                continue
            source_columns = (source_column,)
            target_columns = (target_column,)
        else:
            source_values = row.get("source_columns")
            target_values = row.get("target_columns")
            if (
                not isinstance(source_table, str)
                or not IDENTIFIER_PATTERN.fullmatch(source_table)
                or not isinstance(target_table, str)
                or not IDENTIFIER_PATTERN.fullmatch(target_table)
                or not isinstance(source_values, list)
                or not source_values
                or not isinstance(target_values, list)
                or len(source_values) != len(target_values)
                or any(
                    not isinstance(value, str)
                    or not IDENTIFIER_PATTERN.fullmatch(value)
                    for value in [*source_values, *target_values]
                )
            ):
                add_blocker(blockers, "invalid_relationship_identifier", "Relationship identifiers must be normalized safe names with equal non-empty column lists.", field)
                continue
            if not isinstance(row.get("constraint_name"), str) or not row["constraint_name"].strip():
                add_blocker(blockers, "invalid_relationship", "Version 2 relationship candidates require a source constraint name.", field)
                continue
            source_columns = tuple(source_values)
            target_columns = tuple(target_values)
        identity = (source_table, source_columns, target_table, target_columns)
        if identity in seen:
            add_blocker(blockers, "duplicate_relationship", "Relationship candidate is duplicated.", field)
            continue
        seen.add(identity)
        if row.get("evidence") != "source_declared_foreign_key" or row.get("status") != "pending_review":
            add_blocker(blockers, "invalid_relationship_authority", "Converted relationships must remain source-declared pending candidates.", field)
        if contract_version == 1:
            normalized.append({
                "id": f"{source_table}.{source_columns[0]}->{target_table}.{target_columns[0]}",
                "source_table": source_table,
                "source_column": source_columns[0],
                "target_table": target_table,
                "target_column": target_columns[0],
                "evidence": row.get("evidence"),
            })
        else:
            source_id = ",".join(source_columns)
            target_id = ",".join(target_columns)
            normalized.append({
                "id": f"{source_table}.({source_id})->{target_table}.({target_id})",
                "constraint_name": row["constraint_name"],
                "source_table": source_table,
                "source_columns": list(source_columns),
                "target_table": target_table,
                "target_columns": list(target_columns),
                "evidence": row.get("evidence"),
            })
    return normalized, relationship_artifact.get("sha256")


def relationship_columns(
    relationship: dict[str, Any],
) -> tuple[list[str], list[str]]:
    if "source_columns" in relationship:
        return relationship["source_columns"], relationship["target_columns"]
    return [relationship["source_column"]], [relationship["target_column"]]


def query_technical_evidence(
    database_path: Path,
    database_hash: str,
    catalog: dict[str, dict[str, Any]],
    primary_keys: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    key_evidence: list[dict[str, Any]] = []
    relationship_evidence: list[dict[str, Any]] = []
    row_count = 0
    before_hash = file_sha256(database_path)
    try:
        with duckdb.connect(str(database_path), read_only=True) as connection:
            actual_rows = connection.execute(
                """
                select table_name, column_name, data_type, ordinal_position
                from information_schema.columns
                where table_schema = 'main'
                order by table_name, ordinal_position
                """
            ).fetchall()
            actual_catalog: dict[str, list[dict[str, str]]] = {}
            for table, column, data_type, _ in actual_rows:
                actual_catalog.setdefault(str(table), []).append({"name": str(column), "type": str(data_type)})
            if set(actual_catalog) != set(catalog):
                add_blocker(blockers, "database_table_drift", "DuckDB tables differ from the conversion manifest.", "database.schema")
            for table, expected in catalog.items():
                if actual_catalog.get(table) != expected["columns"]:
                    add_blocker(blockers, "database_column_drift", "DuckDB columns differ from the conversion manifest.", f"database.schema.{table}")
                    continue
                count = int(connection.execute(f"select count(*) from {quote_identifier(table)}").fetchone()[0])
                row_count += count
                if count != expected["rows"]:
                    add_blocker(blockers, "database_row_count_drift", "DuckDB row count differs from the conversion manifest.", f"database.rows.{table}")
            for key in primary_keys:
                table = key["table"]
                columns = key["columns"]
                grouped = ", ".join(quote_identifier(column) for column in columns)
                null_filter = " or ".join(f"{quote_identifier(column)} is null" for column in columns)
                null_rows = int(connection.execute(f"select count(*) from {quote_identifier(table)} where {null_filter}").fetchone()[0])
                duplicate_groups = int(connection.execute(
                    f"select count(*) from (select {grouped} from {quote_identifier(table)} group by {grouped} having count(*) > 1)"
                ).fetchone()[0])
                valid = null_rows == 0 and duplicate_groups == 0
                if not valid:
                    add_blocker(blockers, "invalid_primary_key_data", "Declared primary key has null or duplicate values.", f"schema.primary_keys.{table}")
                key_evidence.append({**key, "rows": catalog[table]["rows"], "null_key_rows": null_rows, "duplicate_key_groups": duplicate_groups, "valid": valid})
            for relationship in relationships:
                st = relationship["source_table"]
                tt = relationship["target_table"]
                source_relationship_columns, target_relationship_columns = (
                    relationship_columns(relationship)
                )
                if st not in catalog or tt not in catalog:
                    add_blocker(blockers, "unknown_relationship_table", "Relationship table is absent from the converted schema.", f"relationships.{relationship['id']}")
                    continue
                source_columns = {column["name"] for column in catalog[st]["columns"]}
                target_columns = {column["name"] for column in catalog[tt]["columns"]}
                if (
                    any(column not in source_columns for column in source_relationship_columns)
                    or any(column not in target_columns for column in target_relationship_columns)
                ):
                    add_blocker(blockers, "unknown_relationship_column", "Relationship column is absent from the converted schema.", f"relationships.{relationship['id']}")
                    continue
                qst = quote_identifier(st)
                qtt = quote_identifier(tt)
                qscs = [quote_identifier(column) for column in source_relationship_columns]
                qtcs = [quote_identifier(column) for column in target_relationship_columns]
                source_complete = " and ".join(f"s.{column} is not null" for column in qscs)
                source_incomplete = " or ".join(f"s.{column} is null" for column in qscs)
                target_complete = " and ".join(f"{column} is not null" for column in qtcs)
                join_predicate = " and ".join(
                    f"s.{source_column} = t.{target_column}"
                    for source_column, target_column in zip(qscs, qtcs, strict=True)
                )
                grouped_targets = ", ".join(qtcs)
                nonnull = int(connection.execute(f"select count(*) from {qst} s where {source_complete}").fetchone()[0])
                nulls = int(connection.execute(f"select count(*) from {qst} s where {source_incomplete}").fetchone()[0])
                orphans = int(connection.execute(
                    f"select count(*) from {qst} s where {source_complete} "
                    f"and not exists (select 1 from {qtt} t where {join_predicate})"
                ).fetchone()[0])
                target_duplicates = int(connection.execute(
                    f"select count(*) from (select {grouped_targets} from {qtt} "
                    f"where {target_complete} group by {grouped_targets} having count(*) > 1)"
                ).fetchone()[0])
                valid = orphans == 0 and target_duplicates == 0
                if not valid:
                    add_blocker(blockers, "invalid_relationship_data", "Relationship has orphan rows or a non-unique target.", f"relationships.{relationship['id']}")
                relationship_evidence.append({
                    **relationship,
                    "source_rows": catalog[st]["rows"],
                    "nonnull_source_rows": nonnull,
                    "null_source_rows": nulls,
                    "orphan_rows": orphans,
                    "target_duplicate_groups": target_duplicates,
                    "positive_coverage": nonnull > 0,
                    "valid": valid,
                })
    except duckdb.Error:
        add_blocker(blockers, "database_unreadable", "DuckDB could not be profiled in read-only mode.", "database")
    after_hash = file_sha256(database_path)
    if before_hash != database_hash or after_hash != database_hash:
        add_blocker(blockers, "database_hash_drift", "DuckDB hash changed or differs from its conversion artifact.", "database.sha256")
    return key_evidence, relationship_evidence, row_count


def validate_completed_review(
    review_path: Path | None,
    dataset: str,
    source_manifest_hash: str,
    relationship_hash: str | None,
    relationship_evidence: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]], str | None]:
    if review_path is None:
        return "pending_review", [], None
    review_hash = file_sha256(review_path) if review_path.is_file() else None
    review = load_yaml(review_path, "review", blockers)
    if not review:
        return "invalid", [], review_hash
    review_version = (
        2 if any("source_columns" in row for row in relationship_evidence) else 1
    )
    if review.get("version") != review_version or review.get("dataset") != dataset or review.get("status") != "completed":
        add_blocker(blockers, "invalid_relationship_review", "Completed review must match version, dataset, and completed status.", "review")
    if review.get("source_manifest_sha256") != source_manifest_hash:
        add_blocker(blockers, "review_manifest_drift", "Review is not bound to the exact reference manifest.", "review.source_manifest_sha256")
    if review.get("relationship_candidates_sha256") != relationship_hash:
        add_blocker(blockers, "review_candidate_drift", "Review is not bound to the exact relationship candidates.", "review.relationship_candidates_sha256")
    scopes = review.get("scope")
    if not isinstance(scopes, dict) or scopes.get("local_offline_relationship_use") != "approved":
        add_blocker(blockers, "relationship_scope_not_approved", "Completed review must approve local offline relationship use.", "review.scope.local_offline_relationship_use")
    for scope in REQUIRED_CLOSED_SCOPES:
        if not isinstance(scopes, dict) or scopes.get(scope) != "not_authorized":
            add_blocker(blockers, "unsafe_review_scope", "Completed review cannot authorize external, publication, or training use.", f"review.scope.{scope}")
    expected = {row["id"]: row for row in relationship_evidence}
    decisions = review.get("decisions")
    if not isinstance(decisions, list):
        add_blocker(blockers, "invalid_review_decisions", "Review decisions must be a list.", "review.decisions")
        return "invalid", [], review_hash
    actual: dict[str, dict[str, Any]] = {}
    for index, decision in enumerate(decisions):
        field = f"review.decisions[{index}]"
        if not isinstance(decision, dict) or decision.get("id") not in expected:
            add_blocker(blockers, "unknown_review_decision", "Review decision must reference one exact candidate.", field)
            continue
        identifier = decision["id"]
        if identifier in actual:
            add_blocker(blockers, "duplicate_review_decision", "Review decision is duplicated.", field)
            continue
        if decision.get("decision") not in {"accepted", "rejected"}:
            add_blocker(blockers, "pending_review_decision", "Every relationship must be explicitly accepted or rejected.", f"{field}.decision")
        if not isinstance(decision.get("reviewer"), str) or not decision["reviewer"].strip():
            add_blocker(blockers, "missing_reviewer", "Every decision requires a reviewer identity.", f"{field}.reviewer")
        try:
            datetime.fromisoformat(str(decision.get("reviewed_at")))
        except ValueError:
            add_blocker(blockers, "invalid_review_time", "Every decision requires an ISO-8601 review time.", f"{field}.reviewed_at")
        if not isinstance(decision.get("notes"), str) or not decision["notes"].strip():
            add_blocker(blockers, "missing_review_notes", "Every relationship decision requires review notes.", f"{field}.notes")
        actual[identifier] = decision
    missing = sorted(set(expected) - set(actual))
    if missing:
        add_blocker(blockers, "incomplete_relationship_review", "Completed review omits one or more relationship candidates.", "review.decisions")
    return "completed" if not missing else "incomplete", [actual[key] for key in sorted(actual)], review_hash


def pending_review_payload(
    dataset: str,
    source_manifest_hash: str,
    relationship_hash: str | None,
    relationship_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    review_version = (
        2 if any("source_columns" in row for row in relationship_evidence) else 1
    )

    def decision_payload(row: dict[str, Any]) -> dict[str, Any]:
        relationship = {
            "id": row["id"],
            "source_table": row["source_table"],
            "target_table": row["target_table"],
            "evidence": row["evidence"],
        }
        if review_version == 1:
            relationship.update(
                {
                    "source_column": row["source_column"],
                    "target_column": row["target_column"],
                }
            )
        else:
            relationship.update(
                {
                    "constraint_name": row["constraint_name"],
                    "source_columns": row["source_columns"],
                    "target_columns": row["target_columns"],
                }
            )
        relationship.update(
            {
                "technical_validation": {
                    "source_rows": row["source_rows"],
                    "nonnull_source_rows": row["nonnull_source_rows"],
                    "null_source_rows": row["null_source_rows"],
                    "orphan_rows": row["orphan_rows"],
                    "target_duplicate_groups": row["target_duplicate_groups"],
                    "positive_coverage": row["positive_coverage"],
                    "valid": row["valid"],
                },
                "decision": "pending",
                "reviewer": None,
                "reviewed_at": None,
                "notes": None,
            }
        )
        return relationship

    return {
        "version": review_version,
        "dataset": dataset,
        "status": "pending_review",
        "source_manifest_sha256": source_manifest_hash,
        "relationship_candidates_sha256": relationship_hash,
        "scope": {
            "local_offline_relationship_use": "pending",
            "external_upload": "not_authorized",
            "model_parameter_training": "not_authorized",
            "publication": "not_authorized",
        },
        "instructions": [
            "Review every exact candidate and its technical evidence.",
            "Set status to completed only after every decision is accepted or rejected.",
            "Provide reviewer, reviewed_at, and notes for every decision.",
            "Use a new validation output directory after completing this file.",
        ],
        "decisions": [decision_payload(row) for row in relationship_evidence],
    }


def approved_relationships_payload(
    dataset: str,
    status: str,
    source_manifest_hash: str,
    relationship_hash: str | None,
    review_hash: str | None,
    decisions: list[dict[str, Any]],
    relationship_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    decisions_by_id = {row["id"]: row for row in decisions}
    authority_complete = status == "ready_for_semantic_modeling"
    registry_version = (
        2 if any("source_columns" in row for row in relationship_evidence) else 1
    )
    approved = []
    rejected = []
    for relationship in relationship_evidence:
        decision = decisions_by_id.get(relationship["id"], {})
        if not authority_complete:
            continue
        if decision.get("decision") == "accepted":
            if registry_version == 1:
                approved.append(
                    {
                        "source_table": relationship["source_table"],
                        "source_column": relationship["source_column"],
                        "target_table": relationship["target_table"],
                        "target_column": relationship["target_column"],
                    }
                )
            else:
                approved.append(
                    {
                        "constraint_name": relationship["constraint_name"],
                        "source_table": relationship["source_table"],
                        "source_columns": relationship["source_columns"],
                        "target_table": relationship["target_table"],
                        "target_columns": relationship["target_columns"],
                    }
                )
        elif decision.get("decision") == "rejected":
            rejected.append(relationship["id"])
    return {
        "version": registry_version,
        "status": "approved" if authority_complete else "pending_review",
        "dataset": dataset,
        "authority": {
            "source_manifest_sha256": source_manifest_hash,
            "relationship_candidates_sha256": relationship_hash,
            "completed_review_sha256": review_hash if authority_complete else None,
            "derived_from_completed_human_review": authority_complete,
            "automatic_approval": False,
            "scope": "local_offline_relationship_use" if authority_complete else None,
        },
        "approved_relationships": approved,
        "rejected_relationship_ids": rejected,
        "non_authorizations": [
            "external_upload",
            "model_parameter_training",
            "publication",
        ],
    }


def render_report(evidence: dict[str, Any]) -> str:
    relationships = evidence["relationships"]
    schema = evidence["schema"]
    lines = [
        f"# {evidence['dataset']} Reference Dataset Validation",
        "",
        f"- Status: `{evidence['status']}`",
        f"- Blockers: {len(evidence['blockers'])}",
        f"- Tables: {schema['tables']}",
        f"- Rows: {schema['rows']}",
        f"- Technically valid primary keys: {schema['valid_primary_keys']}/{schema['primary_keys']}",
        f"- Technically valid relationships: {relationships['valid_candidates']}/{relationships['candidates']}",
        f"- Relationships with positive row coverage: {relationships['positive_coverage_candidates']}/{relationships['candidates']}",
        f"- Relationship review: `{relationships['review_status']}`",
        "",
        "## Boundary",
        "",
        "- Source and conversion artifacts were hash-validated locally.",
        "- DuckDB was opened read-only for schema, key, and orphan checks.",
        "- Technical validity does not approve a relationship.",
        "- External upload, publication, and model-parameter training remain not authorized.",
    ]
    if evidence["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{row['code']}` at `{row['field']}`: {row['message']}" for row in evidence["blockers"])
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError(f"Reference validation output is not a directory: {output_dir}")
        for name, content in contents.items():
            path = output_dir / name
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise ValueError(
                    f"Different reference dataset evidence already exists in {output_dir}. "
                    "Use a new output directory; existing evidence was not overwritten."
                )
        return False
    staging = output_dir.with_name(f"{output_dir.name}.building")
    if staging.exists():
        raise ValueError(f"Stale reference validation staging directory exists: {staging}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    try:
        for name, content in contents.items():
            (staging / name).write_text(content, encoding="utf-8")
        staging.rename(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return True


def run_reference_dataset_validation(
    reference_manifest_path: Path,
    output_dir: Path,
    review_path: Path | None = None,
) -> ReferenceDatasetValidationResult:
    blockers: list[dict[str, str]] = []
    reference_manifest_path = reference_manifest_path.resolve()
    reference = load_yaml(reference_manifest_path, "reference_manifest", blockers)
    if not reference:
        raise ValueError("Reference dataset manifest is missing or invalid.")
    if reference.get("version") != 1:
        add_blocker(blockers, "unsupported_reference_version", "Reference dataset manifest version must be 1.", "version")
    dataset = reference.get("dataset")
    if not isinstance(dataset, str) or not IDENTIFIER_PATTERN.fullmatch(dataset):
        add_blocker(blockers, "invalid_dataset", "Dataset identifier must be a normalized safe name.", "dataset")
        dataset = "invalid_dataset"
    source_path, source_evidence = validate_source(reference, blockers)
    license_evidence = validate_license(reference, blockers)
    benchmark_use = validate_benchmark_use(reference, blockers)
    conversion_manifest, conversion_artifacts, reproduction = validate_conversion(reference, source_evidence, blockers)
    catalog = expected_catalog(conversion_manifest, blockers) if conversion_manifest else {}
    primary_keys = validate_primary_key_config(reference, catalog, blockers) if catalog else []
    relationship_config = reference.get("relationships")
    if not isinstance(relationship_config, dict):
        add_blocker(blockers, "invalid_relationship_config", "Relationship review configuration is required.", "relationships")
        relationship_config = {}
    relationships, relationship_hash = load_relationships(
        conversion_artifacts,
        relationship_config.get("expected_candidates"),
        blockers,
    )

    key_evidence: list[dict[str, Any]] = []
    relationship_evidence: list[dict[str, Any]] = []
    row_count = 0
    database = conversion_artifacts.get("database", {})
    database_path = database.get("resolved_path")
    database_hash = database.get("sha256")
    if not blockers and isinstance(database_path, Path) and isinstance(database_hash, str):
        key_evidence, relationship_evidence, row_count = query_technical_evidence(
            database_path,
            database_hash,
            catalog,
            primary_keys,
            relationships,
            blockers,
        )

    reference_hash = file_sha256(reference_manifest_path)
    resolved_review = review_path.resolve() if review_path else None
    review_status, decisions, review_hash = validate_completed_review(
        resolved_review,
        dataset,
        reference_hash,
        relationship_hash,
        relationship_evidence,
        blockers,
    ) if relationship_evidence else ("pending_review", [], None)
    accepted = sum(row.get("decision") == "accepted" for row in decisions)
    rejected = sum(row.get("decision") == "rejected" for row in decisions)
    if blockers:
        status = "blocked"
    elif review_status == "completed":
        status = "ready_for_semantic_modeling"
    else:
        status = "ready_for_relationship_review"

    evidence = {
        "version": 1,
        "module": "reference-dataset-validate",
        "module_version": MODULE_VERSION,
        "status": status,
        "dataset": dataset,
        "source": source_evidence,
        "license": license_evidence,
        "conversion": {
            "manifest_path": reference.get("conversion", {}).get("manifest_path"),
            "manifest_sha256": file_sha256(Path(reference["conversion"]["manifest_path"]).resolve())
            if conversion_manifest
            else None,
            "database_sha256": database_hash,
            "reproduction": reproduction,
        },
        "schema": {
            "tables": len(catalog),
            "rows": row_count,
            "primary_keys": len(key_evidence),
            "valid_primary_keys": sum(row["valid"] for row in key_evidence),
            "evidence": key_evidence,
        },
        "relationships": {
            "candidates": len(relationship_evidence),
            "valid_candidates": sum(row["valid"] for row in relationship_evidence),
            "positive_coverage_candidates": sum(row["positive_coverage"] for row in relationship_evidence),
            "candidate_sha256": relationship_hash,
            "review_status": review_status,
            "review_sha256": review_hash,
            "accepted": accepted,
            "rejected": rejected,
            "pending": len(relationship_evidence) - accepted - rejected,
            "technical_evidence": relationship_evidence,
        },
        "benchmark_use": benchmark_use,
        "blockers": blockers,
        "inputs": {
            "reference_manifest": {
                "path": str(reference_manifest_path),
                "sha256": reference_hash,
            },
            "review": {
                "path": str(resolved_review) if resolved_review else None,
                "sha256": review_hash,
            },
        },
        "safety": {
            "source_modified": False,
            "database_opened_read_only": bool(key_evidence or relationship_evidence),
            "external_connection_used": False,
            "relationships_automatically_approved": False,
            "external_upload_authorized": False,
            "model_parameter_training_authorized": False,
        },
    }
    review_template = pending_review_payload(dataset, reference_hash, relationship_hash, relationship_evidence)
    review_content = (
        resolved_review.read_text(encoding="utf-8")
        if resolved_review and resolved_review.is_file()
        else yaml.safe_dump(review_template, sort_keys=False, allow_unicode=False)
    )
    relationship_registry = approved_relationships_payload(
        dataset,
        status,
        reference_hash,
        relationship_hash,
        review_hash,
        decisions,
        relationship_evidence,
    )
    contents = {
        MANIFEST_NAME: yaml.safe_dump(evidence, sort_keys=False, allow_unicode=False),
        REVIEW_NAME: review_content,
        APPROVED_RELATIONSHIPS_NAME: yaml.safe_dump(
            relationship_registry,
            sort_keys=False,
            allow_unicode=False,
        ),
        REPORT_NAME: render_report(evidence),
    }
    outputs_changed = write_outputs(output_dir.resolve(), contents)
    return ReferenceDatasetValidationResult(
        output_dir=output_dir.resolve(),
        status=status,
        manifest_path=output_dir.resolve() / MANIFEST_NAME,
        review_path=output_dir.resolve() / REVIEW_NAME,
        approved_relationships_path=output_dir.resolve() / APPROVED_RELATIONSHIPS_NAME,
        report_path=output_dir.resolve() / REPORT_NAME,
        blocker_count=len(blockers),
        table_count=len(catalog),
        row_count=row_count,
        primary_key_count=len(key_evidence),
        relationship_count=len(relationship_evidence),
        approved_relationship_count=accepted,
        outputs_changed=outputs_changed,
    )
