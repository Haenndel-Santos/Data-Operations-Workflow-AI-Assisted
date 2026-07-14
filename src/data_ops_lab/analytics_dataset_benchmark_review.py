from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .analytics_dataset_benchmark import (
    MAX_CONTROL_FILE_BYTES,
    AnalyticsDatasetBenchmarkCandidate,
    inspect_analytics_dataset_benchmark_candidate,
)
from .analytics_query_plan import add_blocker
from .source_onboarding import ensure_dir, file_sha256


REVIEW_NAME = "analytics_dataset_benchmark_review.yml"
PLAN_NAME = "analytics_dataset_benchmark_approval_plan.yml"
BLOCKERS_NAME = "analytics_dataset_benchmark_approval_blockers.csv"
REPORT_NAME = "analytics_dataset_benchmark_approval_report.md"
OUTPUT_NAMES = {PLAN_NAME, BLOCKERS_NAME, REPORT_NAME}

SCOPE_DECISIONS = {
    "local_offline_evaluation": "approved",
    "live_provider_use": "not_authorized",
    "external_upload": "not_authorized",
    "model_training": "not_authorized",
}
CASE_REVIEW_FIELDS = (
    "recorded_provider_response",
    "expected_request",
    "expected_result",
    "comparison_policy",
)


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkReviewResult:
    review_path: Path
    case_count: int
    output_changed: bool


@dataclass(frozen=True)
class AnalyticsDatasetBenchmarkApprovalResult:
    output_dir: Path
    status: str
    plan_path: Path
    blockers_path: Path
    report_path: Path
    approval_path: Path
    blocker_count: int
    dry_run: bool
    approval_changed: bool
    outputs_changed: bool
    decision_digest: str


def _reject_unknown_fields(
    payload: dict[str, Any],
    allowed: set[str],
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    for key in payload:
        if key not in allowed:
            add_blocker(
                blockers,
                "unsupported_benchmark_review_field",
                "The benchmark review contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def _read_review(path: Path, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(blockers, "benchmark_review_missing", "The completed benchmark review file is required.", field="review")
        return {}
    if path.stat().st_size > MAX_CONTROL_FILE_BYTES:
        add_blocker(
            blockers,
            "benchmark_review_too_large",
            f"The benchmark review must be at most {MAX_CONTROL_FILE_BYTES} bytes.",
            field="review",
        )
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        add_blocker(blockers, "benchmark_review_unreadable", "The benchmark review must be readable YAML.", field="review")
        return {}
    if not isinstance(payload, dict):
        add_blocker(blockers, "invalid_benchmark_review", "The benchmark review must be a YAML mapping.", field="review")
        return {}
    return payload


def _valid_reviewed_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _candidate_or_raise(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
) -> AnalyticsDatasetBenchmarkCandidate:
    candidate = inspect_analytics_dataset_benchmark_candidate(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
    )
    if candidate.blockers:
        blocker_types = ", ".join(sorted({row["blocker_type"] for row in candidate.blockers}))
        raise ValueError(f"Benchmark review preparation requires a valid candidate package: {blocker_types}")
    return candidate


def _build_review_template(candidate: AnalyticsDatasetBenchmarkCandidate) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "pending_human_review",
        "source": candidate.source,
        "identity": {
            "dataset_id": candidate.dataset_id,
            "pack_id": candidate.pack_id,
        },
        "review": {
            "reviewer": "",
            "reviewed_at": "",
            "scope_decisions": [
                {"scope": scope, "decision": "pending", "notes": ""}
                for scope in SCOPE_DECISIONS
            ],
            "case_decisions": [
                {
                    "case_id": case_id,
                    **{field: "pending" for field in CASE_REVIEW_FIELDS},
                    "notes": "",
                }
                for case_id in candidate.case_ids
            ],
        },
    }


def _write_exact_file(path: Path, content: str, label: str) -> bool:
    if path.exists():
        if not path.is_file():
            raise ValueError(f"{label} output is not a file: {path}")
        if path.read_text(encoding="utf-8") == content:
            return False
        raise ValueError(f"A different {label} already exists at {path}. Use a new path; human authority was not overwritten.")
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_dataset_benchmark_review(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    output_path: Path,
) -> AnalyticsDatasetBenchmarkReviewResult:
    candidate = _candidate_or_raise(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
    )
    review = _build_review_template(candidate)
    content = yaml.safe_dump(review, sort_keys=False, allow_unicode=False)
    output_changed = _write_exact_file(output_path, content, "benchmark review")
    return AnalyticsDatasetBenchmarkReviewResult(
        review_path=output_path,
        case_count=candidate.case_count,
        output_changed=output_changed,
    )


def _validate_source(
    source: Any,
    expected: dict[str, str],
    blockers: list[dict[str, str]],
) -> None:
    if not isinstance(source, dict):
        add_blocker(blockers, "invalid_benchmark_review_source", "Review source hashes must be a mapping.", field="review_file.source")
        return
    _reject_unknown_fields(source, set(expected), blockers, "review_file.source")
    for name, digest in expected.items():
        if source.get(name) != digest:
            add_blocker(
                blockers,
                "benchmark_review_source_drift",
                "The review no longer matches an exact candidate source.",
                field=f"review_file.source.{name}",
            )


def _validate_scope_decisions(
    rows: Any,
    blockers: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        add_blocker(blockers, "invalid_benchmark_scope_decisions", "scope_decisions must be a list.", field="review.scope_decisions")
        rows = []
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        field = f"review.scope_decisions[{index}]"
        if not isinstance(row, dict):
            add_blocker(blockers, "invalid_benchmark_scope_decision", "Every scope decision must be a mapping.", field=field)
            continue
        _reject_unknown_fields(row, {"scope", "decision", "notes"}, blockers, field)
        scope = row.get("scope")
        if not isinstance(scope, str) or scope not in SCOPE_DECISIONS:
            add_blocker(blockers, "unknown_benchmark_scope", "The review contains an unknown benchmark scope.", field=f"{field}.scope")
            continue
        if scope in seen:
            add_blocker(blockers, "duplicate_benchmark_scope_decision", "Every benchmark scope must be reviewed exactly once.", field=f"{field}.scope")
            continue
        seen.add(scope)
        decision = row.get("decision")
        expected = SCOPE_DECISIONS[scope]
        if decision != expected:
            blocker_type = "benchmark_scope_expansion_not_allowed" if scope != "local_offline_evaluation" and decision == "approved" else "benchmark_scope_not_approved"
            add_blocker(
                blockers,
                blocker_type,
                f"Scope {scope} must be explicitly set to {expected}.",
                field=f"{field}.decision",
            )
        notes = row.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            add_blocker(blockers, "missing_benchmark_scope_notes", "Every scope decision requires human notes.", field=f"{field}.notes")
        normalized.append({"scope": scope, "decision": str(decision)})
    for scope in set(SCOPE_DECISIONS) - seen:
        add_blocker(blockers, "missing_benchmark_scope_decision", "Every benchmark scope must be reviewed exactly once.", field=f"review.scope_decisions.{scope}")
    return sorted(normalized, key=lambda row: row["scope"])


def _validate_case_decisions(
    rows: Any,
    expected_case_ids: tuple[str, ...],
    blockers: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        add_blocker(blockers, "invalid_benchmark_case_decisions", "case_decisions must be a list.", field="review.case_decisions")
        rows = []
    expected = set(expected_case_ids)
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    allowed = {"case_id", "notes", *CASE_REVIEW_FIELDS}
    for index, row in enumerate(rows):
        field = f"review.case_decisions[{index}]"
        if not isinstance(row, dict):
            add_blocker(blockers, "invalid_benchmark_case_decision", "Every case decision must be a mapping.", field=field)
            continue
        _reject_unknown_fields(row, allowed, blockers, field)
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id not in expected:
            add_blocker(blockers, "unknown_benchmark_case_decision", "The review case does not match the bound candidate pack.", field=f"{field}.case_id")
            continue
        if case_id in seen:
            add_blocker(blockers, "duplicate_benchmark_case_decision", "Every benchmark case must be reviewed exactly once.", field=f"{field}.case_id")
            continue
        seen.add(case_id)
        normalized_row = {"case_id": case_id}
        for name in CASE_REVIEW_FIELDS:
            decision = row.get(name)
            if decision != "approved":
                add_blocker(
                    blockers,
                    "benchmark_case_review_not_approved",
                    "Every response, request, result, and comparison policy must be explicitly approved.",
                    field=f"{field}.{name}",
                )
            normalized_row[name] = str(decision)
        notes = row.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            add_blocker(blockers, "missing_benchmark_case_notes", "Every benchmark case decision requires human notes.", field=f"{field}.notes")
        normalized.append(normalized_row)
    for case_id in expected - seen:
        add_blocker(blockers, "missing_benchmark_case_decision", "Every benchmark case must be reviewed exactly once.", field=f"review.case_decisions.{case_id}")
    return sorted(normalized, key=lambda row: row["case_id"])


def _decision_digest(scopes: list[dict[str, str]], cases: list[dict[str, str]]) -> str:
    payload = json.dumps(
        {"scope_decisions": scopes, "case_decisions": cases},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_review(
    review: dict[str, Any],
    candidate: AnalyticsDatasetBenchmarkCandidate,
    blockers: list[dict[str, str]],
) -> tuple[str, str, str]:
    _reject_unknown_fields(review, {"version", "status", "source", "identity", "review"}, blockers, "review_file")
    if isinstance(review.get("version"), bool) or review.get("version") != 1:
        add_blocker(blockers, "unsupported_benchmark_review_version", "Benchmark review must use version 1.", field="review_file.version")
    if review.get("status") != "completed_human_review":
        add_blocker(blockers, "benchmark_review_not_completed", "Review status must be completed_human_review.", field="review_file.status")
    _validate_source(review.get("source"), candidate.source, blockers)
    identity = review.get("identity")
    if not isinstance(identity, dict):
        add_blocker(blockers, "invalid_benchmark_review_identity", "Review identity must be a mapping.", field="review_file.identity")
    else:
        _reject_unknown_fields(identity, {"dataset_id", "pack_id"}, blockers, "review_file.identity")
        if identity.get("dataset_id") != candidate.dataset_id or identity.get("pack_id") != candidate.pack_id:
            add_blocker(blockers, "benchmark_review_identity_drift", "Review dataset and pack IDs must match the candidate.", field="review_file.identity")

    body = review.get("review")
    if not isinstance(body, dict):
        add_blocker(blockers, "invalid_benchmark_review_body", "review must be a mapping.", field="review_file.review")
        body = {}
    else:
        _reject_unknown_fields(body, {"reviewer", "reviewed_at", "scope_decisions", "case_decisions"}, blockers, "review_file.review")
    reviewer = body.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        add_blocker(blockers, "missing_benchmark_reviewer", "A human benchmark reviewer is required.", field="review.reviewer")
        reviewer = ""
    reviewed_at = body.get("reviewed_at")
    if not _valid_reviewed_at(reviewed_at):
        add_blocker(blockers, "invalid_benchmark_reviewed_at", "reviewed_at must be an ISO-8601 timestamp with a timezone.", field="review.reviewed_at")
        reviewed_at = ""
    scopes = _validate_scope_decisions(body.get("scope_decisions"), blockers)
    cases = _validate_case_decisions(body.get("case_decisions"), candidate.case_ids, blockers)
    return str(reviewer).strip(), str(reviewed_at).strip(), _decision_digest(scopes, cases)


def _build_approval(
    candidate: AnalyticsDatasetBenchmarkCandidate,
    review_path: Path,
    reviewer: str,
    reviewed_at: str,
    decision_digest: str,
) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "approved",
        "dataset_id": candidate.dataset_id,
        "pack_id": candidate.pack_id,
        "source": candidate.source,
        "review_evidence": {
            "review_sha256": file_sha256(review_path),
            "decision_digest": decision_digest,
        },
        "decision": {
            "local_offline_evaluation_approved": True,
            "recorded_provider_responses_reviewed": True,
            "expected_requests_reviewed": True,
            "expected_results_reviewed": True,
            "comparison_policy_reviewed": True,
            "live_provider_use_approved": False,
            "external_upload_approved": False,
            "model_training_approved": False,
        },
        "approved_by": reviewer,
        "approved_at": reviewed_at,
    }


def _blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["blocker_id", "blocker_type", "field", "explanation"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def _render_report(status: str, blockers: list[dict[str, str]], apply: bool) -> str:
    lines = [
        "# Analytics Dataset Benchmark Approval Report",
        "",
        f"- Status: `{status}`",
        f"- Mode: `{'apply' if apply else 'dry-run'}`",
        f"- Blockers: {len(blockers)}",
        "",
        "## Governance",
        "",
        "- Review authority is bound to the exact dataset, semantics, relationships, and pack by SHA-256.",
        "- Every case requires explicit response, request, result, comparison, and notes review.",
        "- Live providers, external upload, and model training remain outside this approval.",
        "- Questions, provider responses, expected rows, and notes are not copied into approval evidence.",
        "- The database is hashed as an opaque file and is never opened or queried.",
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


def _write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Benchmark approval output is not a directory: {output_dir}")
    existing = ({path.name: path for path in output_dir.iterdir() if path.is_file() and path.name in OUTPUT_NAMES} if output_dir.exists() else {})
    if existing:
        exact = set(existing) == set(contents) and all(existing[name].read_text(encoding="utf-8") == content for name, content in contents.items())
        if exact:
            return False
        raise ValueError(f"Different benchmark approval evidence already exists in {output_dir}. Use a new output directory; existing evidence was not overwritten.")
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_dataset_benchmark_approval(
    dataset_manifest_path: Path,
    database_path: Path,
    semantic_state_path: Path,
    relationships_path: Path,
    benchmark_pack_path: Path,
    review_path: Path,
    output_dir: Path,
    approval_path: Path,
    *,
    apply: bool = False,
) -> AnalyticsDatasetBenchmarkApprovalResult:
    candidate = inspect_analytics_dataset_benchmark_candidate(
        dataset_manifest_path,
        database_path,
        semantic_state_path,
        relationships_path,
        benchmark_pack_path,
    )
    blockers = list(candidate.blockers)
    review = _read_review(review_path, blockers)
    reviewer, reviewed_at, decision_digest = _validate_review(review, candidate, blockers)
    approval = _build_approval(candidate, review_path, reviewer, reviewed_at, decision_digest) if not blockers else {}
    status = "ready_for_apply" if not blockers else "blocked"
    approval_content = yaml.safe_dump(approval, sort_keys=False, allow_unicode=False) if approval else ""
    if apply and not blockers and approval_path.exists():
        if not approval_path.is_file() or approval_path.read_text(encoding="utf-8") != approval_content:
            raise ValueError(
                f"A different benchmark approval already exists at {approval_path}. "
                "Use a new path; human authority was not overwritten."
            )
    plan = {
        "version": 1,
        "status": status,
        "mode": "apply" if apply else "dry-run",
        "source": {
            **candidate.source,
            "review_sha256": file_sha256(review_path) if review_path.is_file() else "",
            "decision_digest": decision_digest,
        },
        "target_approval": str(approval_path),
        "proposed_approval": approval,
        "blockers": blockers,
    }
    contents = {
        PLAN_NAME: yaml.safe_dump(plan, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: _blockers_csv(blockers),
        REPORT_NAME: _render_report(status, blockers, apply),
    }
    outputs_changed = _write_outputs(output_dir, contents)

    approval_changed = False
    if apply and not blockers:
        approval_changed = _write_exact_file(approval_path, approval_content, "benchmark approval")
    return AnalyticsDatasetBenchmarkApprovalResult(
        output_dir=output_dir,
        status=status,
        plan_path=output_dir / PLAN_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        approval_path=approval_path,
        blocker_count=len(blockers),
        dry_run=not apply,
        approval_changed=approval_changed,
        outputs_changed=outputs_changed,
        decision_digest=decision_digest,
    )
