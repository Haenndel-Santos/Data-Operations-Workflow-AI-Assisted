from __future__ import annotations

import csv
import hashlib
import io
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .analytics_semantic_review import (
    read_yaml_mapping,
    semantic_ambiguities,
    semantic_entities,
    validate_reviewable_catalog,
)
from .contracts.blockers import add_blocker
from .source_onboarding import backup_existing, ensure_dir, file_sha256


PLAN_NAME = "analytics_semantic_approval_plan.yml"
BLOCKERS_NAME = "analytics_semantic_approval_blockers.csv"
REPORT_NAME = "analytics_semantic_approval_report.md"
STATE_NAME = "approved_semantic_catalog.yml"
OUTPUT_NAMES = {PLAN_NAME, BLOCKERS_NAME, REPORT_NAME}
ENTITY_DECISIONS = {"approved", "rejected", "pending"}
AMBIGUITY_DECISIONS = {"approved_target", "requires_clarification", "pending"}


@dataclass(frozen=True)
class AnalyticsSemanticApprovalResult:
    output_dir: Path
    status: str
    plan_path: Path
    blockers_path: Path
    report_path: Path
    state_path: Path
    blocker_count: int
    dry_run: bool
    state_changed: bool
    outputs_changed: bool
    decision_digest: str


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
                "unsupported_review_field",
                "The semantic review contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def parse_reviewed_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_review(
    catalog_path: Path,
    catalog: dict[str, Any],
    review: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, Any]], str, str]:
    blockers: list[dict[str, str]] = []
    reject_unknown_fields(review, {"version", "status", "source", "review"}, blockers, "review_file")
    if review.get("version") != 1:
        add_blocker(blockers, "unsupported_review_version", "Semantic review must use version 1.", field="version")
    if review.get("status") != "completed_human_review":
        add_blocker(
            blockers,
            "review_not_completed",
            "Review status must be explicitly changed to completed_human_review.",
            field="status",
        )

    source = review.get("source")
    if not isinstance(source, dict):
        add_blocker(blockers, "invalid_review_source", "Review source metadata must be a mapping.", field="source")
        source = {}
    else:
        reject_unknown_fields(source, {"semantic_catalog_sha256"}, blockers, "source")
    expected_hash = file_sha256(catalog_path)
    if source.get("semantic_catalog_sha256") != expected_hash:
        add_blocker(
            blockers,
            "semantic_catalog_drift",
            "The review is not bound to the exact compiled semantic catalog being applied.",
            field="source.semantic_catalog_sha256",
        )

    review_body = review.get("review")
    if not isinstance(review_body, dict):
        add_blocker(blockers, "invalid_review_body", "review must be a mapping.", field="review")
        review_body = {}
    else:
        reject_unknown_fields(
            review_body,
            {"reviewer", "reviewed_at", "entity_decisions", "ambiguity_decisions"},
            blockers,
            "review",
        )
    reviewer = review_body.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        add_blocker(blockers, "missing_reviewer", "A human reviewer is required.", field="review.reviewer")
        reviewer = ""
    reviewed_at = review_body.get("reviewed_at")
    if not parse_reviewed_at(reviewed_at):
        add_blocker(
            blockers,
            "invalid_reviewed_at",
            "reviewed_at must be a non-empty ISO-8601 timestamp.",
            field="review.reviewed_at",
        )
        reviewed_at = ""

    expected_entities = {(row["kind"], row["id"]): row for row in semantic_entities(catalog)}
    entity_rows = review_body.get("entity_decisions", [])
    if not isinstance(entity_rows, list):
        add_blocker(
            blockers,
            "invalid_entity_decisions",
            "entity_decisions must be a list.",
            field="review.entity_decisions",
        )
        entity_rows = []
    normalized_entities: list[dict[str, str]] = []
    seen_entities: set[tuple[str, str]] = set()
    for index, row in enumerate(entity_rows):
        field = f"review.entity_decisions[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_entity_decision",
                "Each entity decision must be a mapping.",
                field=field,
            )
            continue
        reject_unknown_fields(row, {"kind", "id", "name", "decision", "notes"}, blockers, field)
        key = (str(row.get("kind", "")), str(row.get("id", "")))
        expected = expected_entities.get(key)
        if key in seen_entities:
            add_blocker(
                blockers,
                "duplicate_entity_decision",
                "Each semantic entity must be reviewed exactly once.",
                field=field,
            )
            continue
        seen_entities.add(key)
        if expected is None or row.get("name") != expected["name"]:
            add_blocker(
                blockers,
                "unknown_entity_decision",
                "The review entity does not match the compiled catalog.",
                field=field,
            )
            continue
        decision = row.get("decision")
        notes = row.get("notes")
        if decision not in ENTITY_DECISIONS:
            add_blocker(
                blockers,
                "invalid_entity_decision",
                "Entity decision must be approved, rejected, or pending.",
                field=f"{field}.decision",
            )
        elif decision == "pending":
            add_blocker(
                blockers,
                "pending_entity_decision",
                "Pending semantic decisions cannot be applied.",
                field=f"{field}.decision",
            )
        elif decision == "rejected":
            add_blocker(
                blockers,
                "rejected_semantic_entity",
                "Rejected semantics require candidate-catalog revision and revalidation.",
                field=f"{field}.decision",
            )
        if not isinstance(notes, str) or not notes.strip():
            add_blocker(
                blockers,
                "missing_decision_notes",
                "Every semantic decision requires human notes.",
                field=f"{field}.notes",
            )
        normalized_entities.append({"kind": key[0], "id": key[1], "decision": str(decision)})
    for key in expected_entities.keys() - seen_entities:
        add_blocker(
            blockers,
            "missing_entity_decision",
            "Every semantic entity must be reviewed exactly once.",
            field=f"review.entity_decisions.{key[0]}:{key[1]}",
        )

    expected_ambiguities = {row["term"]: row for row in semantic_ambiguities(catalog)}
    ambiguity_rows = review_body.get("ambiguity_decisions", [])
    if not isinstance(ambiguity_rows, list):
        add_blocker(
            blockers,
            "invalid_ambiguity_decisions",
            "ambiguity_decisions must be a list.",
            field="review.ambiguity_decisions",
        )
        ambiguity_rows = []
    normalized_ambiguities: list[dict[str, Any]] = []
    seen_terms: set[str] = set()
    for index, row in enumerate(ambiguity_rows):
        field = f"review.ambiguity_decisions[{index}]"
        if not isinstance(row, dict):
            add_blocker(
                blockers,
                "invalid_ambiguity_decision",
                "Each ambiguity decision must be a mapping.",
                field=field,
            )
            continue
        reject_unknown_fields(
            row,
            {"term", "candidate_targets", "decision", "selected_target", "notes"},
            blockers,
            field,
        )
        term = str(row.get("term", ""))
        expected = expected_ambiguities.get(term)
        if term in seen_terms:
            add_blocker(
                blockers,
                "duplicate_ambiguity_decision",
                "Each ambiguous term must be reviewed exactly once.",
                field=field,
            )
            continue
        seen_terms.add(term)
        if expected is None or row.get("candidate_targets") != expected["candidate_targets"]:
            add_blocker(
                blockers,
                "unknown_ambiguity_decision",
                "The ambiguity does not match the compiled catalog.",
                field=field,
            )
            continue
        decision = row.get("decision")
        selected = row.get("selected_target")
        notes = row.get("notes")
        if decision not in AMBIGUITY_DECISIONS:
            add_blocker(
                blockers,
                "invalid_ambiguity_decision",
                "Ambiguity decision must be approved_target, requires_clarification, or pending.",
                field=f"{field}.decision",
            )
        elif decision == "pending":
            add_blocker(
                blockers,
                "pending_ambiguity_decision",
                "Pending ambiguity decisions cannot be applied.",
                field=f"{field}.decision",
            )
        elif decision == "requires_clarification" and selected is not None:
            add_blocker(
                blockers,
                "unexpected_selected_target",
                "Clarification decisions cannot select a target.",
                field=f"{field}.selected_target",
            )
        elif decision == "approved_target":
            if (
                not isinstance(selected, dict)
                or set(selected) != {"kind", "id", "name"}
                or selected not in expected["candidate_targets"]
            ):
                add_blocker(
                    blockers,
                    "invalid_selected_target",
                    "The selected target must exactly match one ambiguity candidate.",
                    field=f"{field}.selected_target",
                )
        if not isinstance(notes, str) or not notes.strip():
            add_blocker(
                blockers,
                "missing_ambiguity_notes",
                "Every ambiguity decision requires human notes.",
                field=f"{field}.notes",
            )
        normalized_ambiguities.append(
            {
                "term": term,
                "decision": str(decision),
                "selected_target": deepcopy(selected) if isinstance(selected, dict) else None,
            }
        )
    for term in expected_ambiguities.keys() - seen_terms:
        add_blocker(
            blockers,
            "missing_ambiguity_decision",
            "Every ambiguous term must be reviewed exactly once.",
            field=f"review.ambiguity_decisions.{term}",
        )

    return blockers, normalized_entities, normalized_ambiguities, reviewer.strip(), str(reviewed_at).strip()


def decision_digest(
    entities: list[dict[str, str]],
    ambiguities: list[dict[str, Any]],
) -> str:
    payload = json.dumps(
        {"entity_decisions": entities, "ambiguity_decisions": ambiguities},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approved_term_index(
    term_index: list[dict[str, Any]],
    ambiguities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions = {row["term"]: row for row in ambiguities}
    approved = deepcopy(term_index)
    for row in approved:
        decision = decisions.get(row.get("term"))
        if not decision or decision["decision"] != "approved_target":
            continue
        row["status"] = "resolved"
        row["candidate_count"] = 1
        row["ambiguity_score"] = 0.0
        row["requires_clarification"] = False
        row["resolution_authority"] = "human_approval"
        row["targets"] = [deepcopy(decision["selected_target"])]
    return approved


def build_state(
    catalog_path: Path,
    review_path: Path,
    catalog: dict[str, Any],
    reviewer: str,
    reviewed_at: str,
    entities: list[dict[str, str]],
    ambiguities: list[dict[str, Any]],
    digest: str,
) -> dict[str, Any]:
    unresolved = [row["term"] for row in ambiguities if row["decision"] == "requires_clarification"]
    return {
        "version": 1,
        "status": "approved",
        "source": {
            "compiled_semantic_catalog_sha256": file_sha256(catalog_path),
            "candidate_semantic_catalog_sha256": catalog.get("source", {}).get("semantic_catalog_sha256", ""),
            "relationships_sha256": catalog.get("source", {}).get("relationships_sha256", ""),
            "physical_catalog_sha256": catalog.get("source", {}).get("catalog_sha256", ""),
            "review_sha256": file_sha256(review_path),
            "decision_digest": digest,
        },
        "approval": {
            "semantic_definitions_approved": True,
            "adapter_use_authorized": True,
            "candidate_relationships_accepted": False,
            "approved_by": reviewer,
            "approved_at": reviewed_at,
            "requires_clarification": bool(unresolved),
        },
        "catalog": deepcopy(catalog.get("catalog", {})),
        "dataset": deepcopy(catalog["dataset"]),
        "tables": deepcopy(catalog.get("tables", [])),
        "dimensions": deepcopy(catalog.get("dimensions", [])),
        "measures": deepcopy(catalog.get("measures", [])),
        "relationship_paths": deepcopy(catalog.get("relationship_paths", [])),
        "term_index": approved_term_index(catalog.get("term_index", []), ambiguities),
        "ambiguities": unresolved,
        "ambiguity_decisions": deepcopy(ambiguities),
        "entity_decisions": deepcopy(entities),
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


def render_report(status: str, blockers: list[dict[str, str]], state_path: Path, apply: bool) -> str:
    lines = [
        "# Analytics Semantic Approval Report",
        "",
        f"- Status: `{status}`",
        f"- Mode: `{'apply' if apply else 'dry-run'}`",
        f"- Target state: `{state_path}`",
        f"- Blockers: {len(blockers)}",
        "",
        "## Governance",
        "",
        "- Human review is bound to the exact compiled semantic catalog by SHA-256.",
        "- Rejected, pending, missing, duplicate, or stale decisions block application.",
        "- Review notes are validated but are not copied into the approved registry.",
        "- Candidate relationships are never promoted by semantic approval.",
        "- Ambiguous terms remain clarification points unless a human selects an exact candidate.",
        "- No data rows, SQL, database connection, model API, migration, import, or sync is used.",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(
            f"- `{row['blocker_id']}` `{row['blocker_type']}`: field=`{row['field'] or 'not_available'}`"
            for row in blockers
        )
    else:
        lines.append("- No approval blockers found.")
    return "\n".join(lines) + "\n"


def write_approval_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Semantic approval output path is not a directory: {output_dir}")
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
            f"Different semantic approval evidence already exists in {output_dir}. "
            "Use a new output directory; existing review evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_semantic_approval(
    catalog_path: Path,
    review_path: Path,
    output_dir: Path,
    config_dir: Path = Path("config/analytics"),
    *,
    apply: bool = False,
    replace_existing: bool = False,
) -> AnalyticsSemanticApprovalResult:
    if replace_existing and not apply:
        raise ValueError("--replace-existing requires --apply.")
    catalog = read_yaml_mapping(catalog_path, "Compiled semantic catalog")
    validate_reviewable_catalog(catalog)
    review = read_yaml_mapping(review_path, "Semantic review")
    blockers, entities, ambiguities, reviewer, reviewed_at = validate_review(catalog_path, catalog, review)
    digest = decision_digest(entities, ambiguities)
    state_path = config_dir / STATE_NAME
    state = (
        build_state(catalog_path, review_path, catalog, reviewer, reviewed_at, entities, ambiguities, digest)
        if not blockers
        else {}
    )
    status = "ready_for_apply" if not blockers else "blocked"
    current_state: dict[str, Any] = {}
    if state_path.exists():
        current_state = read_yaml_mapping(state_path, "Approved semantic state")
    if apply and not blockers and current_state and current_state != state and not replace_existing:
        raise ValueError(
            f"A different approved semantic state already exists at {state_path}. "
            "Review it and use --replace-existing only with explicit authorization."
        )

    plan = {
        "version": 1,
        "status": status,
        "mode": "apply" if apply else "dry-run",
        "source": {
            "compiled_semantic_catalog_sha256": file_sha256(catalog_path),
            "review_sha256": file_sha256(review_path),
            "decision_digest": digest,
        },
        "target_state": str(state_path),
        "proposed_state": state,
        "blockers": blockers,
    }
    contents = {
        PLAN_NAME: yaml.safe_dump(plan, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(status, blockers, state_path, apply),
    }
    outputs_changed = write_approval_outputs(output_dir, contents)

    state_changed = False
    if apply and not blockers and current_state != state:
        ensure_dir(state_path.parent)
        if state_path.exists():
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_existing(state_path, run_id)
        state_path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=False), encoding="utf-8")
        state_changed = True

    return AnalyticsSemanticApprovalResult(
        output_dir=output_dir,
        status=status,
        plan_path=output_dir / PLAN_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        state_path=state_path,
        blocker_count=len(blockers),
        dry_run=not apply,
        state_changed=state_changed,
        outputs_changed=outputs_changed,
        decision_digest=digest,
    )
