from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .source_onboarding import ensure_dir, file_sha256


REVIEW_NAME = "analytics_semantic_review.yml"
ENTITY_COLLECTIONS = (
    ("table", "tables"),
    ("dimension", "dimensions"),
    ("measure", "measures"),
    ("relationship_path", "relationship_paths"),
)


@dataclass(frozen=True)
class AnalyticsSemanticReviewResult:
    review_path: Path
    entity_count: int
    ambiguity_count: int
    output_changed: bool


def read_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a YAML mapping: {path}")
    return payload


def semantic_entities(catalog: dict[str, Any]) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    dataset = catalog.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("Reviewable semantic catalog requires one dataset mapping.")
    entities.append(_review_entity("dataset", dataset))
    for kind, collection in ENTITY_COLLECTIONS:
        rows = catalog.get(collection, [])
        if not isinstance(rows, list):
            raise ValueError(f"Reviewable semantic catalog field {collection} must be a list.")
        entities.extend(_review_entity(kind, row) for row in rows)
    keys = [(row["kind"], row["id"].casefold()) for row in entities]
    if len(keys) != len(set(keys)):
        raise ValueError("Reviewable semantic catalog contains duplicate entity IDs within a kind.")
    return entities


def _review_entity(kind: str, entity: Any) -> dict[str, str]:
    if not isinstance(entity, dict):
        raise ValueError(f"Semantic {kind} entries must be mappings.")
    semantic_id = entity.get("id")
    name = entity.get("name")
    if not isinstance(semantic_id, str) or not semantic_id.strip():
        raise ValueError(f"Semantic {kind} requires a non-empty ID.")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Semantic {kind} {semantic_id} requires a non-empty name.")
    return {"kind": kind, "id": semantic_id, "name": name}


def semantic_ambiguities(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    term_index = catalog.get("term_index", [])
    if not isinstance(term_index, list):
        raise ValueError("Reviewable semantic catalog term_index must be a list.")
    ambiguities: list[dict[str, Any]] = []
    for row in term_index:
        if not isinstance(row, dict) or row.get("status") != "ambiguous":
            continue
        term = row.get("term")
        targets = row.get("targets")
        if not isinstance(term, str) or not term or not isinstance(targets, list) or len(targets) < 2:
            raise ValueError("Ambiguous semantic terms require a term and at least two targets.")
        cleaned_targets = []
        for target in targets:
            if not isinstance(target, dict) or not {"kind", "id", "name"} <= set(target):
                raise ValueError(f"Ambiguous semantic term {term} contains an invalid target.")
            cleaned_targets.append(
                {
                    "kind": str(target["kind"]),
                    "id": str(target["id"]),
                    "name": str(target["name"]),
                }
            )
        ambiguities.append({"term": term, "candidate_targets": cleaned_targets})
    if catalog.get("ambiguities") != [row["term"] for row in ambiguities]:
        raise ValueError("Semantic catalog ambiguity summary does not match its term index.")
    return ambiguities


def validate_reviewable_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("version") != 1:
        raise ValueError("Semantic review requires compiled catalog version 1.")
    if catalog.get("status") != "ready_for_semantic_review":
        raise ValueError("Semantic review requires catalog status ready_for_semantic_review.")
    if catalog.get("blockers") != []:
        raise ValueError("Semantic review cannot begin while catalog blockers remain.")
    approval = catalog.get("approval")
    if not isinstance(approval, dict):
        raise ValueError("Semantic catalog approval metadata is missing.")
    if not isinstance(catalog.get("source"), dict):
        raise ValueError("Semantic catalog source fingerprints are missing.")
    if not isinstance(catalog.get("catalog"), dict):
        raise ValueError("Semantic catalog count metadata is missing.")
    if approval.get("semantic_definitions_approved") is not False:
        raise ValueError("Review input must contain unapproved semantic definitions.")
    if approval.get("adapter_use_authorized") is not False:
        raise ValueError("Review input must not already authorize adapter use.")
    if approval.get("candidate_relationships_accepted") is not False:
        raise ValueError("Review input must not accept candidate physical relationships.")
    if approval.get("requires_human_semantic_review") is not True:
        raise ValueError("Review input must explicitly require human semantic review.")
    semantic_entities(catalog)
    semantic_ambiguities(catalog)


def build_review_template(catalog_path: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    entities = semantic_entities(catalog)
    ambiguities = semantic_ambiguities(catalog)
    return {
        "version": 1,
        "status": "pending_human_review",
        "source": {
            "semantic_catalog_sha256": file_sha256(catalog_path),
        },
        "review": {
            "reviewer": "",
            "reviewed_at": "",
            "entity_decisions": [
                {
                    **entity,
                    "decision": "pending",
                    "notes": "",
                }
                for entity in entities
            ],
            "ambiguity_decisions": [
                {
                    **ambiguity,
                    "decision": "pending",
                    "selected_target": None,
                    "notes": "",
                }
                for ambiguity in ambiguities
            ],
        },
    }


def write_exact_review(path: Path, content: str) -> bool:
    if path.exists():
        if not path.is_file():
            raise ValueError(f"Semantic review output is not a file: {path}")
        if path.read_text(encoding="utf-8") == content:
            return False
        raise ValueError(
            f"A different semantic review already exists at {path}. "
            "Use a new path; human review evidence was not overwritten."
        )
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_semantic_review(
    catalog_path: Path,
    output_path: Path,
) -> AnalyticsSemanticReviewResult:
    catalog = read_yaml_mapping(catalog_path, "Compiled semantic catalog")
    validate_reviewable_catalog(catalog)
    review = build_review_template(catalog_path, catalog)
    content = yaml.safe_dump(review, sort_keys=False, allow_unicode=False)
    output_changed = write_exact_review(output_path, content)
    return AnalyticsSemanticReviewResult(
        review_path=output_path,
        entity_count=len(review["review"]["entity_decisions"]),
        ambiguity_count=len(review["review"]["ambiguity_decisions"]),
        output_changed=output_changed,
    )
