from __future__ import annotations

import csv
import io
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .analytics_nl_translation import (
    MAX_PROVIDER_RESPONSE_BYTES,
    SemanticTranslationPrompt,
    run_analytics_nl_translation,
    validate_provider_response,
)
from .analytics_query_plan import add_blocker, read_yaml_mapping
from .analytics_semantic_adapter import MAX_QUESTION_LENGTH, validate_approved_state
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_translation_evaluation.yml"
CASES_NAME = "analytics_translation_evaluation_cases.csv"
BLOCKERS_NAME = "analytics_translation_evaluation_blockers.csv"
REPORT_NAME = "analytics_translation_evaluation_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, CASES_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_PACK_FILE_BYTES = 2_000_000
MAX_CASES = 100
MAX_ACCEPTED_INTENTS = 10
IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ALLOWED_STATUSES = {"ready_for_query_plan", "clarification_required", "blocked"}
ALLOWED_BEHAVIORS = {"response", "timeout", "failure"}
REQUIRED_CATEGORIES = {
    "exact",
    "equivalent",
    "clarification",
    "hallucination",
    "unsafe",
    "provider_failure",
}
EXPECTED_CATEGORY_STATUS = {
    "exact": "ready_for_query_plan",
    "equivalent": "ready_for_query_plan",
    "clarification": "clarification_required",
    "hallucination": "blocked",
    "unsafe": "blocked",
    "provider_failure": "blocked",
}


@dataclass(frozen=True)
class AnalyticsTranslationEvaluationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    cases_path: Path
    blockers_path: Path
    report_path: Path
    case_count: int
    passed_count: int
    failed_count: int
    blocker_count: int
    outputs_changed: bool


class _SyntheticResponseProvider:
    name = "synthetic_evaluation_response"
    mode = "offline_synthetic"
    network_access_required = False

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del prompt, timeout_seconds
        return self.response


class _SyntheticTimeoutProvider:
    name = "synthetic_evaluation_timeout"
    mode = "offline_synthetic"
    network_access_required = False

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del prompt, timeout_seconds
        raise TimeoutError


class _SyntheticFailureProvider:
    name = "synthetic_evaluation_failure"
    mode = "offline_synthetic"
    network_access_required = False

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del prompt, timeout_seconds
        raise RuntimeError("synthetic provider details must be sanitized")


def _valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER_PATTERN.fullmatch(value))


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
        and len(value) == len(set(value))
    )


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
                "unsupported_evaluation_field",
                "The evaluation pack contains a field outside the version-1 contract.",
                field=f"{field}.{key}",
            )


def _validate_expected(
    expected: Any,
    category: str,
    behavior: str,
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    if not isinstance(expected, dict):
        add_blocker(
            blockers,
            "invalid_evaluation_expectation",
            "Every evaluation case requires an expected outcome mapping.",
            field=field,
        )
        return
    _reject_unknown_fields(
        expected,
        {"status", "accepted_intents", "blocker_types", "clarification_terms"},
        blockers,
        field,
    )
    status = expected.get("status")
    if status not in ALLOWED_STATUSES:
        add_blocker(
            blockers,
            "invalid_expected_status",
            "Expected status must be ready_for_query_plan, clarification_required, or blocked.",
            field=f"{field}.status",
        )
    if category in EXPECTED_CATEGORY_STATUS and status != EXPECTED_CATEGORY_STATUS[category]:
        add_blocker(
            blockers,
            "evaluation_category_status_mismatch",
            "The category must retain its governed expected status.",
            field=f"{field}.status",
        )
    accepted = expected.get("accepted_intents", [])
    if not isinstance(accepted, list) or len(accepted) > MAX_ACCEPTED_INTENTS:
        add_blocker(
            blockers,
            "invalid_accepted_intents",
            f"Accepted intents must be a list of at most {MAX_ACCEPTED_INTENTS} mappings.",
            field=f"{field}.accepted_intents",
        )
    else:
        for index, intent in enumerate(accepted):
            intent_blockers: list[dict[str, str]] = []
            validate_provider_response(intent, intent_blockers)
            if intent_blockers:
                add_blocker(
                    blockers,
                    "invalid_accepted_intent",
                    "Accepted intents must satisfy the provider response contract.",
                    field=f"{field}.accepted_intents[{index}]",
                )
        if status in {"ready_for_query_plan", "clarification_required"} and not accepted:
            add_blocker(
                blockers,
                "accepted_intent_required",
                "Ready and clarification cases require at least one accepted semantic intent.",
                field=f"{field}.accepted_intents",
            )
        if status == "blocked" and accepted:
            add_blocker(
                blockers,
                "blocked_intent_not_allowed",
                "Blocked cases cannot declare an accepted semantic intent.",
                field=f"{field}.accepted_intents",
            )
    blocker_types = expected.get("blocker_types", [])
    clarification_terms = expected.get("clarification_terms", [])
    if not _string_list(blocker_types):
        add_blocker(
            blockers,
            "invalid_expected_blockers",
            "Expected blocker types must be a unique list of non-empty strings.",
            field=f"{field}.blocker_types",
        )
    if not _string_list(clarification_terms):
        add_blocker(
            blockers,
            "invalid_expected_clarifications",
            "Expected clarification terms must be a unique list of non-empty strings.",
            field=f"{field}.clarification_terms",
        )
    if status == "blocked" and not blocker_types:
        add_blocker(
            blockers,
            "expected_blocker_required",
            "Blocked cases require at least one expected blocker type.",
            field=f"{field}.blocker_types",
        )
    if status != "blocked" and blocker_types:
        add_blocker(
            blockers,
            "unexpected_blocker_expectation",
            "Non-blocked cases cannot expect blocker types.",
            field=f"{field}.blocker_types",
        )
    if status == "clarification_required" and not clarification_terms:
        add_blocker(
            blockers,
            "expected_clarification_required",
            "Clarification cases require at least one expected term.",
            field=f"{field}.clarification_terms",
        )
    if status != "clarification_required" and clarification_terms:
        add_blocker(
            blockers,
            "unexpected_clarification_expectation",
            "Only clarification cases can expect clarification terms.",
            field=f"{field}.clarification_terms",
        )
    required_failure = {"timeout": "provider_timeout", "failure": "provider_failure"}.get(behavior)
    if required_failure and blocker_types != [required_failure]:
        add_blocker(
            blockers,
            "provider_failure_expectation_mismatch",
            "Synthetic provider failure behavior must retain its exact governed blocker.",
            field=f"{field}.blocker_types",
        )


def validate_evaluation_pack(
    pack: dict[str, Any],
    blockers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    _reject_unknown_fields(pack, {"version", "pack_id", "description", "cases"}, blockers, "pack")
    if isinstance(pack.get("version"), bool) or pack.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_evaluation_pack_version",
            "The translation evaluation pack must use version 1.",
            field="pack.version",
        )
    if not _valid_identifier(pack.get("pack_id")):
        add_blocker(
            blockers,
            "invalid_evaluation_pack_id",
            "The evaluation pack ID must be a lowercase stable identifier.",
            field="pack.pack_id",
        )
    if not isinstance(pack.get("description"), str) or not pack["description"].strip():
        add_blocker(
            blockers,
            "invalid_evaluation_description",
            "The evaluation pack requires a non-empty description.",
            field="pack.description",
        )
    cases = pack.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        add_blocker(
            blockers,
            "invalid_evaluation_cases",
            f"The evaluation pack requires between 1 and {MAX_CASES} cases.",
            field="pack.cases",
        )
        return []

    validated_cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    categories: set[str] = set()
    behaviors: set[str] = set()
    for index, case in enumerate(cases):
        field = f"pack.cases[{index}]"
        if not isinstance(case, dict):
            add_blocker(
                blockers,
                "invalid_evaluation_case",
                "Every evaluation case must be a mapping.",
                field=field,
            )
            continue
        _reject_unknown_fields(
            case,
            {"id", "category", "question", "provider_behavior", "provider_response", "expected"},
            blockers,
            field,
        )
        case_id = case.get("id")
        if not _valid_identifier(case_id):
            add_blocker(
                blockers,
                "invalid_evaluation_case_id",
                "Each case ID must be a lowercase stable identifier.",
                field=f"{field}.id",
            )
        elif case_id in seen_ids:
            add_blocker(
                blockers,
                "duplicate_evaluation_case_id",
                "Evaluation case IDs must be unique.",
                field=f"{field}.id",
            )
        else:
            seen_ids.add(case_id)
        category = case.get("category")
        if category not in REQUIRED_CATEGORIES:
            add_blocker(
                blockers,
                "invalid_evaluation_category",
                "Evaluation case category is outside the required version-1 set.",
                field=f"{field}.category",
            )
        else:
            categories.add(category)
        question = case.get("question")
        if not isinstance(question, str) or not question.strip() or len(question.strip()) > MAX_QUESTION_LENGTH:
            add_blocker(
                blockers,
                "invalid_evaluation_question",
                f"Each synthetic question must contain at most {MAX_QUESTION_LENGTH} characters.",
                field=f"{field}.question",
            )
        behavior = case.get("provider_behavior")
        if behavior not in ALLOWED_BEHAVIORS:
            add_blocker(
                blockers,
                "invalid_provider_behavior",
                "Provider behavior must be response, timeout, or failure.",
                field=f"{field}.provider_behavior",
            )
        else:
            behaviors.add(behavior)
        response = case.get("provider_response")
        if behavior == "response":
            if not isinstance(response, dict):
                add_blocker(
                    blockers,
                    "provider_response_required",
                    "Response behavior requires one provider response mapping.",
                    field=f"{field}.provider_response",
                )
            elif len(yaml.safe_dump(response).encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
                add_blocker(
                    blockers,
                    "provider_response_too_large",
                    "Synthetic provider response exceeds the translation boundary limit.",
                    field=f"{field}.provider_response",
                )
        elif "provider_response" in case:
            add_blocker(
                blockers,
                "provider_response_not_allowed",
                "Timeout and failure behaviors cannot include a provider response.",
                field=f"{field}.provider_response",
            )
        if isinstance(category, str) and isinstance(behavior, str):
            _validate_expected(case.get("expected"), category, behavior, blockers, f"{field}.expected")
        validated_cases.append(case)

    missing_categories = sorted(REQUIRED_CATEGORIES - categories)
    if missing_categories:
        add_blocker(
            blockers,
            "evaluation_coverage_incomplete",
            "The pack must cover every required version-1 evaluation category.",
            field="pack.cases",
        )
    if not {"timeout", "failure"}.issubset(behaviors):
        add_blocker(
            blockers,
            "provider_failure_coverage_incomplete",
            "The pack must cover both timeout and provider failure behavior.",
            field="pack.cases",
        )
    return validated_cases


def _provider_for_case(case: dict[str, Any]) -> Any:
    behavior = case["provider_behavior"]
    if behavior == "timeout":
        return _SyntheticTimeoutProvider()
    if behavior == "failure":
        return _SyntheticFailureProvider()
    return _SyntheticResponseProvider(case["provider_response"])


def _read_blocker_types(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row["blocker_type"] for row in csv.DictReader(handle)]


def _read_clarification_terms(path: Path | None) -> list[str]:
    if path is None:
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [row["term"] for row in payload.get("clarifications", [])]


def _read_provider_intent(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return None
    return {key: value for key, value in payload.items() if key != "question"}


def _case_row(case: dict[str, Any], semantic_state_path: Path) -> dict[str, Any]:
    expected = case["expected"]
    accepted_intents = expected.get("accepted_intents", [])
    try:
        with tempfile.TemporaryDirectory(prefix="dataops_translation_evaluation_") as temp_name:
            temp_dir = Path(temp_name)
            question_path = temp_dir / "question.txt"
            question_path.write_text(case["question"].strip() + "\n", encoding="utf-8", newline="")
            result = run_analytics_nl_translation(
                question_path,
                semantic_state_path,
                temp_dir / "translation",
                _provider_for_case(case),
            )
            actual_intent = _read_provider_intent(result.intent_path)
            actual_blockers = _read_blocker_types(result.blockers_path)
            clarification_path = (
                result.adapter_result.clarifications_path if result.adapter_result else None
            )
            actual_clarifications = _read_clarification_terms(clarification_path)
            observed_status = result.status
    except Exception:
        actual_intent = None
        actual_blockers = ["evaluation_error"]
        actual_clarifications = []
        observed_status = "evaluation_error"

    status_match = observed_status == expected["status"]
    intent_evaluated = bool(accepted_intents)
    intent_match = actual_intent in accepted_intents if intent_evaluated else actual_intent is None
    blocker_match = sorted(actual_blockers) == sorted(expected.get("blocker_types", []))
    clarification_match = sorted(actual_clarifications) == sorted(
        expected.get("clarification_terms", [])
    )
    passed = status_match and intent_match and blocker_match and clarification_match
    return {
        "case_id": case["id"],
        "category": case["category"],
        "expected_status": expected["status"],
        "observed_status": observed_status,
        "status_match": status_match,
        "intent_evaluated": intent_evaluated,
        "intent_match": intent_match,
        "blocker_match": blocker_match,
        "clarification_match": clarification_match,
        "passed": passed,
    }


def _metric(rows: list[dict[str, Any]], field: str, *, evaluated: str | None = None) -> dict[str, Any]:
    applicable = [row for row in rows if evaluated is None or row[evaluated]]
    passed = sum(bool(row[field]) for row in applicable)
    count = len(applicable)
    return {
        "passed": passed,
        "evaluated": count,
        "rate": round(passed / count, 6) if count else None,
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall": _metric(rows, "passed"),
        "status_accuracy": _metric(rows, "status_match"),
        "semantic_intent_acceptance": _metric(rows, "intent_match", evaluated="intent_evaluated"),
        "blocker_accuracy": _metric(rows, "blocker_match"),
        "clarification_accuracy": _metric(rows, "clarification_match"),
    }


def _cases_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "case_id",
        "category",
        "expected_status",
        "observed_status",
        "status_match",
        "intent_evaluated",
        "intent_match",
        "blocker_match",
        "clarification_match",
        "passed",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["blocker_id", "blocker_type", "field", "explanation"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def _render_report(
    status: str,
    pack_id: str,
    rows: list[dict[str, Any]],
    blockers: list[dict[str, str]],
    metrics: dict[str, Any],
) -> str:
    lines = [
        "# Analytics Translation Evaluation Report",
        "",
        f"- Status: `{status}`",
        f"- Pack: `{pack_id or 'invalid'}`",
        f"- Cases: {len(rows)}",
        f"- Passed: {sum(bool(row['passed']) for row in rows)}",
        f"- Failed: {sum(not bool(row['passed']) for row in rows)}",
        f"- Contract blockers: {len(blockers)}",
        "",
        "## Metrics",
        "",
    ]
    for name, metric in metrics.items():
        rate = "not evaluated" if metric["rate"] is None else f"{metric['rate']:.6f}"
        lines.append(
            f"- {name.replace('_', ' ').title()}: {metric['passed']}/{metric['evaluated']} ({rate})"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- This pack measures deterministic contract behavior, not live-model quality.",
            "- Providers are synthetic, in-memory, offline, and cannot access a network.",
            "- Questions, provider responses, filter values, and physical mappings are omitted from outputs.",
            "- No database, query, model API, migration, import, or synchronization is used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Translation evaluation output is not a directory: {output_dir}")
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
            f"Different translation evaluation evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_translation_evaluation(
    pack_path: Path,
    semantic_state_path: Path,
    output_dir: Path,
) -> AnalyticsTranslationEvaluationResult:
    blockers: list[dict[str, str]] = []
    if pack_path.is_file() and pack_path.stat().st_size > MAX_PACK_FILE_BYTES:
        add_blocker(
            blockers,
            "evaluation_pack_too_large",
            f"The evaluation pack must be at most {MAX_PACK_FILE_BYTES} bytes.",
            field="pack",
        )
        pack: dict[str, Any] = {}
    else:
        pack = read_yaml_mapping(pack_path, blockers, "evaluation_pack")
    cases = validate_evaluation_pack(pack, blockers) if pack else []
    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")
    validate_approved_state(state, blockers)

    rows = [] if blockers else [_case_row(case, semantic_state_path) for case in cases]
    status = "blocked" if blockers else "passed" if all(row["passed"] for row in rows) else "failed"
    metrics = _metrics(rows)
    passed_count = sum(bool(row["passed"]) for row in rows)
    pack_id = pack.get("pack_id", "") if isinstance(pack, dict) else ""
    if not _valid_identifier(pack_id):
        pack_id = ""
    manifest = {
        "version": 1,
        "status": status,
        "pack_id": pack_id,
        "source": {
            "evaluation_pack_sha256": file_sha256(pack_path) if pack_path.is_file() else "",
            "approved_semantic_state_sha256": (
                file_sha256(semantic_state_path) if semantic_state_path.is_file() else ""
            ),
        },
        "controls": {
            "network_accessed": False,
            "model_api_used": False,
            "database_accessed": False,
            "questions_persisted": False,
            "provider_responses_persisted": False,
            "physical_mappings_persisted": False,
        },
        "counts": {
            "cases": len(rows),
            "passed": passed_count,
            "failed": len(rows) - passed_count,
            "contract_blockers": len(blockers),
        },
        "metrics": metrics,
    }
    contents = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        CASES_NAME: _cases_csv(rows),
        BLOCKERS_NAME: _blockers_csv(blockers),
        REPORT_NAME: _render_report(
            status,
            manifest["pack_id"],
            rows,
            blockers,
            metrics,
        ),
    }
    outputs_changed = _write_outputs(output_dir, contents)
    return AnalyticsTranslationEvaluationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        cases_path=output_dir / CASES_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        case_count=len(rows),
        passed_count=passed_count,
        failed_count=len(rows) - passed_count,
        blocker_count=len(blockers),
        outputs_changed=outputs_changed,
    )
