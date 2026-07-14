from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .analytics_nl_translation import (
    AnalyticsNlTranslationResult,
    RecordedSemanticIntentProvider,
    run_analytics_nl_translation,
)
from .analytics_query_execution import (
    AnalyticsQueryExecutionResult,
    run_analytics_query_execution,
)
from .analytics_query_plan import (
    AnalyticsQueryPlanResult,
    add_blocker,
    read_yaml_mapping,
    run_analytics_query_plan,
)
from .analytics_result_narration import (
    AnalyticsResultNarrationResult,
    RecordedResultNarrationProvider,
    run_analytics_result_narration,
)
from .analytics_result_presentation import (
    AnalyticsResultPresentationResult,
    run_analytics_result_presentation,
)
from .source_onboarding import ensure_dir, file_sha256


PREPARE_MANIFEST_NAME = "analytics_session_prepare.yml"
REVIEW_TEMPLATE_NAME = "analytics_session_execution_review.yml"
PREPARE_BLOCKERS_NAME = "analytics_session_prepare_blockers.csv"
PREPARE_REPORT_NAME = "analytics_session_prepare_report.md"
RESUME_MANIFEST_NAME = "analytics_session_resume.yml"
RESUME_BLOCKERS_NAME = "analytics_session_resume_blockers.csv"
RESUME_REPORT_NAME = "analytics_session_resume_report.md"
TRANSLATION_DIR = "translation"
PLAN_DIR = "query_plan"
EXECUTION_DIR = "query_execution"
PRESENTATION_DIR = "result_presentation"
NARRATION_DIR = "result_narration"
REQUEST_RELATIVE_PATH = Path(TRANSLATION_DIR) / "semantic_adapter" / "analytics_request.yml"
PLAN_RELATIVE_PATH = Path(PLAN_DIR) / "analytics_query_plan.yml"
MAX_REVIEW_TEXT_LENGTH = 4_000


@dataclass(frozen=True)
class AnalyticsSessionPrepareResult:
    output_dir: Path
    status: str
    manifest_path: Path
    review_template_path: Path | None
    blockers_path: Path
    report_path: Path
    blocker_count: int
    translation_result: AnalyticsNlTranslationResult
    plan_result: AnalyticsQueryPlanResult | None
    outputs_changed: bool


@dataclass(frozen=True)
class AnalyticsSessionResumeResult:
    output_dir: Path
    status: str
    last_valid_checkpoint: str
    manifest_path: Path
    blockers_path: Path
    report_path: Path
    blocker_count: int
    execution_result: AnalyticsQueryExecutionResult | None
    presentation_result: AnalyticsResultPresentationResult | None
    narration_result: AnalyticsResultNarrationResult | None
    outputs_changed: bool


def canonical_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


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


def relative_artifact(output_dir: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.relative_to(output_dir).as_posix()
    except ValueError:
        return ""


def artifact(path: Path | None, output_dir: Path) -> dict[str, str]:
    return {
        "path": relative_artifact(output_dir, path),
        "sha256": file_sha256(path) if path is not None and path.is_file() else "",
    }


def database_identity(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {"size_bytes": 0, "modified_ns": 0}
    stat = path.stat()
    return {"size_bytes": stat.st_size, "modified_ns": stat.st_mtime_ns}


def write_outputs(
    output_dir: Path,
    contents: dict[str, str],
    output_names: set[str],
    label: str,
) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"{label} output is not a directory: {output_dir}")
    existing = (
        {
            path.name: path
            for path in output_dir.iterdir()
            if path.is_file() and path.name in output_names
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
            f"Different {label} evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def render_prepare_report(
    status: str,
    translation_status: str,
    plan_status: str,
    blocker_count: int,
) -> str:
    return "\n".join(
        [
            "# Analytics Session Preparation Report",
            "",
            f"- Status: `{status}`",
            f"- Translation: `{translation_status}`",
            f"- Query plan: `{plan_status or 'not_started'}`",
            f"- Blockers: {blocker_count}",
            "",
            "## Boundary",
            "",
            "- Preparation may translate, compile semantic intent, and build Stage 5A evidence.",
            "- It never executes Stage 5B or treats a ready plan as approval.",
            "- Execution requires a separate completed review bound to exact checkpoint hashes.",
            "- Recorded local translation only; no network or live provider is available.",
        ]
    ) + "\n"


def review_template(prepare_manifest_content: str, plan_path: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "pending_review",
        "source": {
            "prepare_manifest_sha256": hashlib.sha256(
                prepare_manifest_content.encode("utf-8")
            ).hexdigest(),
            "reviewed_plan_sha256": file_sha256(plan_path),
        },
        "review": {
            "decision": "pending",
            "reviewed_by": "",
            "reviewed_at": "",
            "notes": "",
        },
    }


def run_analytics_session_prepare(
    question_path: Path,
    semantic_state_path: Path,
    translation_response_path: Path,
    database_path: Path,
    relationships_path: Path,
    output_dir: Path,
) -> AnalyticsSessionPrepareResult:
    blockers: list[dict[str, str]] = []
    input_paths = {
        "question": question_path,
        "semantic_state": semantic_state_path,
        "translation_response": translation_response_path,
        "relationships": relationships_path,
    }
    input_hashes = {
        name: file_sha256(path) for name, path in input_paths.items() if path.is_file()
    }
    database_before = database_identity(database_path)
    translation_result = run_analytics_nl_translation(
        question_path,
        semantic_state_path,
        output_dir / TRANSLATION_DIR,
        RecordedSemanticIntentProvider(translation_response_path),
    )
    plan_result: AnalyticsQueryPlanResult | None = None
    if translation_result.status == "ready_for_query_plan" and translation_result.adapter_result:
        request_path = translation_result.adapter_result.request_path
        if request_path is None:
            add_blocker(
                blockers,
                "translation_request_missing",
                "Translation reported readiness without a Stage 5A request.",
                field="translation",
            )
        else:
            plan_result = run_analytics_query_plan(
                request_path,
                database_path,
                relationships_path,
                output_dir / PLAN_DIR,
            )
            if plan_result.status != "ready_for_execution_review":
                add_blocker(
                    blockers,
                    "query_plan_blocked",
                    "Stage 5A did not produce a review-ready plan.",
                    field="query_plan",
                )
    elif translation_result.status == "clarification_required":
        status = "clarification_required"
    else:
        add_blocker(
            blockers,
            "translation_blocked",
            "Stage 5D translation did not produce a query-planning request.",
            field="translation",
        )

    current_hashes = {
        name: file_sha256(path) for name, path in input_paths.items() if path.is_file()
    }
    if current_hashes != input_hashes or database_identity(database_path) != database_before:
        add_blocker(
            blockers,
            "session_prepare_inputs_changed",
            "A session input changed during preparation.",
            field="inputs",
        )

    if translation_result.status == "clarification_required" and not blockers:
        status = "clarification_required"
    elif blockers:
        status = "blocked"
    elif plan_result and plan_result.status == "ready_for_execution_review":
        status = "awaiting_execution_review"
    else:
        status = "blocked"

    request_path = (
        translation_result.adapter_result.request_path
        if translation_result.adapter_result is not None
        else None
    )
    plan_path = plan_result.plan_path if plan_result is not None else None
    manifest = {
        "version": 1,
        "status": status,
        "workflow": "recorded_local_analytics_session",
        "source": {
            "question_sha256": input_hashes.get("question", ""),
            "semantic_state_sha256": input_hashes.get("semantic_state", ""),
            "translation_response_sha256": input_hashes.get("translation_response", ""),
            "relationships_sha256": input_hashes.get("relationships", ""),
            "database": database_before,
        },
        "stages": {
            "translation": {
                "status": translation_result.status,
                "manifest": artifact(translation_result.manifest_path, output_dir),
            },
            "query_plan": {
                "status": plan_result.status if plan_result else "not_started",
                "manifest": artifact(plan_path, output_dir),
            },
            "query_execution": {"status": "not_authorized"},
            "result_presentation": {"status": "not_started"},
            "result_narration": {"status": "not_started"},
        },
        "artifacts": {
            "request": artifact(request_path, output_dir),
            "review_template": REVIEW_TEMPLATE_NAME if status == "awaiting_execution_review" else "",
        },
        "controls": {
            "recorded_translation_only": True,
            "network_access": False,
            "execution_authorized": False,
            "human_plan_review_required": True,
            "raw_sql_accepted": False,
        },
        "counts": {"blockers": len(blockers)},
    }
    manifest_content = canonical_yaml(manifest)
    contents = {
        PREPARE_MANIFEST_NAME: manifest_content,
        PREPARE_BLOCKERS_NAME: blockers_csv(blockers),
        PREPARE_REPORT_NAME: render_prepare_report(
            status,
            translation_result.status,
            plan_result.status if plan_result else "",
            len(blockers),
        ),
    }
    review_path: Path | None = None
    if status == "awaiting_execution_review" and plan_path is not None:
        contents[REVIEW_TEMPLATE_NAME] = canonical_yaml(
            review_template(manifest_content, plan_path)
        )
        review_path = output_dir / REVIEW_TEMPLATE_NAME
    root_changed = write_outputs(
        output_dir,
        contents,
        {PREPARE_MANIFEST_NAME, REVIEW_TEMPLATE_NAME, PREPARE_BLOCKERS_NAME, PREPARE_REPORT_NAME},
        "analytics session preparation",
    )
    return AnalyticsSessionPrepareResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / PREPARE_MANIFEST_NAME,
        review_template_path=review_path,
        blockers_path=output_dir / PREPARE_BLOCKERS_NAME,
        report_path=output_dir / PREPARE_REPORT_NAME,
        blocker_count=len(blockers),
        translation_result=translation_result,
        plan_result=plan_result,
        outputs_changed=(
            root_changed
            or translation_result.outputs_changed
            or bool(plan_result and plan_result.outputs_changed)
        ),
    )


def validate_review(
    review: dict[str, Any],
    prepare_manifest_path: Path,
    plan_path: Path,
    blockers: list[dict[str, str]],
) -> None:
    if set(review) != {"version", "status", "source", "review"}:
        add_blocker(
            blockers,
            "invalid_execution_review",
            "Execution review contains unsupported or missing top-level fields.",
            field="review",
        )
        return
    source = review.get("source", {})
    decision = review.get("review", {})
    if review.get("version") != 1 or review.get("status") != "completed":
        add_blocker(
            blockers,
            "execution_review_incomplete",
            "Execution review must be version 1 with completed status.",
            field="review.status",
        )
    if not isinstance(source, dict) or set(source) != {
        "prepare_manifest_sha256",
        "reviewed_plan_sha256",
    }:
        add_blocker(
            blockers,
            "invalid_execution_review_source",
            "Execution review source bindings are incomplete.",
            field="review.source",
        )
    else:
        if source.get("prepare_manifest_sha256") != file_sha256(prepare_manifest_path):
            add_blocker(
                blockers,
                "prepare_manifest_review_mismatch",
                "Execution review does not bind the exact preparation checkpoint.",
                field="review.source.prepare_manifest_sha256",
            )
        if source.get("reviewed_plan_sha256") != file_sha256(plan_path):
            add_blocker(
                blockers,
                "reviewed_plan_hash_mismatch",
                "Execution review does not bind the exact Stage 5A plan.",
                field="review.source.reviewed_plan_sha256",
            )
    if not isinstance(decision, dict) or set(decision) != {
        "decision",
        "reviewed_by",
        "reviewed_at",
        "notes",
    }:
        add_blocker(
            blockers,
            "invalid_execution_review_decision",
            "Execution review decision fields are incomplete.",
            field="review.review",
        )
        return
    if decision.get("decision") != "approved":
        add_blocker(
            blockers,
            "execution_not_approved",
            "The exact Stage 5A plan requires an approved human decision.",
            field="review.review.decision",
        )
    for field in ("reviewed_by", "notes"):
        value = decision.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_REVIEW_TEXT_LENGTH:
            add_blocker(
                blockers,
                "invalid_execution_review_text",
                f"Execution review {field} must be non-empty bounded text.",
                field=f"review.review.{field}",
            )
    reviewed_at = decision.get("reviewed_at")
    try:
        parsed = datetime.fromisoformat(reviewed_at) if isinstance(reviewed_at, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        add_blocker(
            blockers,
            "invalid_execution_review_time",
            "Execution review time must be an ISO-8601 timestamp with timezone.",
            field="review.review.reviewed_at",
        )


def validate_prepare_checkpoint(
    prepare_manifest_path: Path,
    database_path: Path,
    relationships_path: Path,
    blockers: list[dict[str, str]],
) -> tuple[dict[str, Any], Path, Path]:
    prepare = read_yaml_mapping(prepare_manifest_path, blockers, "prepare_manifest")
    prepare_dir = prepare_manifest_path.parent
    request_path = prepare_dir / REQUEST_RELATIVE_PATH
    plan_path = prepare_dir / PLAN_RELATIVE_PATH
    if prepare.get("version") != 1 or prepare.get("status") != "awaiting_execution_review":
        add_blocker(
            blockers,
            "prepare_checkpoint_not_ready",
            "Session preparation must be awaiting execution review.",
            field="prepare_manifest.status",
        )
    controls = prepare.get("controls", {})
    if not isinstance(controls, dict) or any(
        controls.get(key) != expected
        for key, expected in {
            "recorded_translation_only": True,
            "network_access": False,
            "execution_authorized": False,
            "human_plan_review_required": True,
            "raw_sql_accepted": False,
        }.items()
    ):
        add_blocker(
            blockers,
            "unsafe_prepare_checkpoint",
            "Preparation safety controls are incomplete.",
            field="prepare_manifest.controls",
        )
    artifacts = prepare.get("artifacts", {})
    stages = prepare.get("stages", {})
    request_evidence = artifacts.get("request", {}) if isinstance(artifacts, dict) else {}
    plan_stage = stages.get("query_plan", {}) if isinstance(stages, dict) else {}
    plan_evidence = plan_stage.get("manifest", {}) if isinstance(plan_stage, dict) else {}
    for label, path, evidence, expected_relative in (
        ("request", request_path, request_evidence, REQUEST_RELATIVE_PATH.as_posix()),
        ("plan", plan_path, plan_evidence, PLAN_RELATIVE_PATH.as_posix()),
    ):
        if (
            not path.is_file()
            or not isinstance(evidence, dict)
            or evidence.get("path") != expected_relative
            or evidence.get("sha256") != file_sha256(path)
        ):
            add_blocker(
                blockers,
                "prepare_artifact_mismatch",
                f"Prepared {label} does not match the immutable checkpoint.",
                field=f"prepare_manifest.{label}",
            )
    source = prepare.get("source", {})
    if not isinstance(source, dict):
        source = {}
    if (
        not relationships_path.is_file()
        or source.get("relationships_sha256") != file_sha256(relationships_path)
    ):
        add_blocker(
            blockers,
            "relationships_changed_after_prepare",
            "Approved relationships changed after session preparation.",
            field="relationships",
        )
    if source.get("database") != database_identity(database_path):
        add_blocker(
            blockers,
            "database_changed_after_prepare",
            "The local DuckDB identity changed after session preparation.",
            field="database",
        )
    return prepare, request_path, plan_path


def render_resume_report(
    status: str,
    last_valid_checkpoint: str,
    blocker_count: int,
) -> str:
    return "\n".join(
        [
            "# Analytics Session Resume Report",
            "",
            f"- Status: `{status}`",
            f"- Last valid checkpoint: `{last_valid_checkpoint}`",
            f"- Blockers: {blocker_count}",
            "",
            "## Boundary",
            "",
            "- Resume requires an exact completed human review before Stage 5B.",
            "- Existing specialized modules retain all query, result, and narration controls.",
            "- Failed stages preserve prior checkpoints and do not authorize later stages.",
            "- Recorded local narration only; no network or live provider is available.",
        ]
    ) + "\n"


def preflight_existing_resume(
    output_dir: Path,
    authority_hashes: dict[str, str],
    database: dict[str, int],
) -> None:
    if not output_dir.exists() or not output_dir.is_dir():
        return
    root_names = {RESUME_MANIFEST_NAME, RESUME_BLOCKERS_NAME, RESUME_REPORT_NAME}
    existing = {path.name for path in output_dir.iterdir() if path.is_file() and path.name in root_names}
    if not existing:
        return
    if existing != root_names:
        raise ValueError(
            f"Incomplete analytics session resume evidence already exists in {output_dir}. "
            "Use a new output directory; existing evidence was not modified."
        )
    manifest_path = output_dir / RESUME_MANIFEST_NAME
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ValueError("Existing analytics session resume manifest is unreadable.") from error
    expected_source = {
        "prepare_manifest_sha256": authority_hashes.get("prepare_manifest", ""),
        "request_sha256": authority_hashes.get("request", ""),
        "reviewed_plan_sha256": authority_hashes.get("plan", ""),
        "execution_review_sha256": authority_hashes.get("review", ""),
        "relationships_sha256": authority_hashes.get("relationships", ""),
        "narration_response_sha256": authority_hashes.get("narration_response", ""),
        "database": database,
    }
    if not isinstance(manifest, dict) or manifest.get("source") != expected_source:
        raise ValueError(
            f"Different analytics session resume authority already exists in {output_dir}. "
            "Use a new output directory; no dependent stage was started."
        )


def run_analytics_session_resume(
    prepare_manifest_path: Path,
    review_path: Path,
    database_path: Path,
    relationships_path: Path,
    narration_response_path: Path,
    output_dir: Path,
) -> AnalyticsSessionResumeResult:
    blockers: list[dict[str, str]] = []
    prepared_request_path = prepare_manifest_path.parent / REQUEST_RELATIVE_PATH
    prepared_plan_path = prepare_manifest_path.parent / PLAN_RELATIVE_PATH
    authority_paths = {
        "prepare_manifest": prepare_manifest_path,
        "request": prepared_request_path,
        "plan": prepared_plan_path,
        "review": review_path,
        "relationships": relationships_path,
        "narration_response": narration_response_path,
    }
    authority_hashes = {
        name: file_sha256(path) for name, path in authority_paths.items() if path.is_file()
    }
    database_before = database_identity(database_path)
    preflight_existing_resume(output_dir, authority_hashes, database_before)
    prepare, request_path, plan_path = validate_prepare_checkpoint(
        prepare_manifest_path,
        database_path,
        relationships_path,
        blockers,
    )
    review = read_yaml_mapping(review_path, blockers, "review")
    if prepare_manifest_path.is_file() and plan_path.is_file():
        validate_review(review, prepare_manifest_path, plan_path, blockers)
    review_validated = not blockers
    if not narration_response_path.is_file():
        add_blocker(
            blockers,
            "narration_response_missing",
            "A local recorded narration response is required.",
            field="narration_response",
        )

    execution_result: AnalyticsQueryExecutionResult | None = None
    presentation_result: AnalyticsResultPresentationResult | None = None
    narration_result: AnalyticsResultNarrationResult | None = None
    last_valid_checkpoint = "execution_review" if review_validated else "prepare"

    if not blockers:
        execution_result = run_analytics_query_execution(
            request_path,
            database_path,
            relationships_path,
            plan_path,
            output_dir / EXECUTION_DIR,
        )
        if execution_result.status not in {"completed", "completed_no_rows"}:
            add_blocker(
                blockers,
                "query_execution_blocked",
                "Stage 5B blocked the reviewed session plan.",
                field="query_execution",
            )
        else:
            last_valid_checkpoint = "query_execution"
    if not blockers and execution_result and execution_result.result_path:
        presentation_result = run_analytics_result_presentation(
            request_path,
            execution_result.manifest_path,
            execution_result.result_path,
            output_dir / PRESENTATION_DIR,
        )
        if presentation_result.status != "ready_for_recorded_narration":
            add_blocker(
                blockers,
                "result_presentation_blocked",
                "Deterministic result presentation did not reach narration readiness.",
                field="result_presentation",
            )
        else:
            last_valid_checkpoint = "result_presentation"
    if not blockers and presentation_result and presentation_result.facts_path:
        narration_result = run_analytics_result_narration(
            presentation_result.manifest_path,
            presentation_result.facts_path,
            output_dir / NARRATION_DIR,
            RecordedResultNarrationProvider(narration_response_path),
        )
        if narration_result.status != "ready_for_user":
            add_blocker(
                blockers,
                "result_narration_blocked",
                "Recorded result narration failed grounded validation.",
                field="result_narration",
            )
        else:
            last_valid_checkpoint = "result_narration"

    current_hashes = {
        name: file_sha256(path) for name, path in authority_paths.items() if path.is_file()
    }
    if not blockers and (
        current_hashes != authority_hashes or database_identity(database_path) != database_before
    ):
        add_blocker(
            blockers,
            "session_authority_changed",
            "A session authority input changed during resume; completion was discarded.",
            field="inputs",
        )
        last_valid_checkpoint = "prepare"

    status = "completed" if not blockers else "blocked"
    stages = {
        "prepare": {"status": prepare.get("status", "")},
        "execution_review": {"status": "approved" if review_validated else "blocked"},
        "query_execution": {
            "status": execution_result.status if execution_result else "not_started",
            "manifest": artifact(execution_result.manifest_path, output_dir) if execution_result else {},
        },
        "result_presentation": {
            "status": presentation_result.status if presentation_result else "not_started",
            "manifest": artifact(presentation_result.manifest_path, output_dir)
            if presentation_result
            else {},
        },
        "result_narration": {
            "status": narration_result.status if narration_result else "not_started",
            "manifest": artifact(narration_result.manifest_path, output_dir)
            if narration_result
            else {},
        },
    }
    manifest = {
        "version": 1,
        "status": status,
        "workflow": "recorded_local_analytics_session",
        "last_valid_checkpoint": last_valid_checkpoint,
        "source": {
            "prepare_manifest_sha256": authority_hashes.get("prepare_manifest", ""),
            "request_sha256": authority_hashes.get("request", ""),
            "reviewed_plan_sha256": authority_hashes.get("plan", ""),
            "execution_review_sha256": authority_hashes.get("review", ""),
            "relationships_sha256": authority_hashes.get("relationships", ""),
            "narration_response_sha256": authority_hashes.get("narration_response", ""),
            "database": database_before,
        },
        "stages": stages,
        "controls": {
            "human_plan_review_validated": review_validated,
            "recorded_providers_only": True,
            "network_access": False,
            "raw_sql_accepted": False,
            "specialized_stage_contracts_reused": True,
        },
        "privacy": {
            "question_or_result_values_in_manifest": False,
            "sql_or_parameters_in_manifest": False,
        },
        "counts": {"blockers": len(blockers)},
    }
    contents = {
        RESUME_MANIFEST_NAME: canonical_yaml(manifest),
        RESUME_BLOCKERS_NAME: blockers_csv(blockers),
        RESUME_REPORT_NAME: render_resume_report(status, last_valid_checkpoint, len(blockers)),
    }
    root_changed = write_outputs(
        output_dir,
        contents,
        {RESUME_MANIFEST_NAME, RESUME_BLOCKERS_NAME, RESUME_REPORT_NAME},
        "analytics session resume",
    )
    nested_changed = any(
        result is not None and result.outputs_changed
        for result in (execution_result, presentation_result, narration_result)
    )
    return AnalyticsSessionResumeResult(
        output_dir=output_dir,
        status=status,
        last_valid_checkpoint=last_valid_checkpoint,
        manifest_path=output_dir / RESUME_MANIFEST_NAME,
        blockers_path=output_dir / RESUME_BLOCKERS_NAME,
        report_path=output_dir / RESUME_REPORT_NAME,
        blocker_count=len(blockers),
        execution_result=execution_result,
        presentation_result=presentation_result,
        narration_result=narration_result,
        outputs_changed=root_changed or nested_changed,
    )
