from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from .analytics_query_plan import add_blocker, read_yaml_mapping
from .analytics_semantic_adapter import (
    ALLOWED_INTENT_FIELDS,
    MAX_QUESTION_LENGTH,
    AnalyticsSemanticAdapterResult,
    compile_intent,
    run_analytics_semantic_adapter,
    validate_approved_state,
)
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_nl_translation_manifest.yml"
INTENT_NAME = "analytics_semantic_intent.yml"
BLOCKERS_NAME = "analytics_nl_translation_blockers.csv"
REPORT_NAME = "analytics_nl_translation_report.md"
ADAPTER_DIR_NAME = "semantic_adapter"
OUTPUT_NAMES = {MANIFEST_NAME, INTENT_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_PROVIDER_TIMEOUT_SECONDS = 120
MAX_QUESTION_FILE_BYTES = 16_384
MAX_PROVIDER_RESPONSE_BYTES = 1_000_000
MAX_SEMANTIC_CONTEXT_BYTES = 4_000_000
ALLOWED_PROVIDER_FIELDS = ALLOWED_INTENT_FIELDS - {"question"}


@dataclass(frozen=True)
class SemanticTranslationPrompt:
    question: str
    semantic_context: dict[str, Any]
    response_schema: dict[str, Any]


class SemanticIntentProvider(Protocol):
    name: str
    mode: str
    network_access_required: bool

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]: ...


class RecordedSemanticIntentProvider:
    name = "recorded_response"
    mode = "offline"
    network_access_required = False

    def __init__(self, response_path: Path) -> None:
        self.response_path = response_path

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del prompt, timeout_seconds
        if not self.response_path.is_file():
            raise FileNotFoundError("Recorded provider response is missing.")
        if self.response_path.stat().st_size > MAX_PROVIDER_RESPONSE_BYTES:
            raise ValueError("Recorded provider response exceeds the size limit.")
        try:
            payload = yaml.safe_load(self.response_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise ValueError("Recorded provider response is not valid UTF-8 YAML.") from error
        if not isinstance(payload, dict):
            raise ValueError("Recorded provider response must be a YAML mapping.")
        return payload


@dataclass(frozen=True)
class AnalyticsNlTranslationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    intent_path: Path | None
    blockers_path: Path
    report_path: Path
    adapter_result: AnalyticsSemanticAdapterResult | None
    blocker_count: int
    clarification_count: int
    provider_called: bool
    outputs_changed: bool


def read_question(path: Path, blockers: list[dict[str, str]]) -> str:
    if not path.is_file():
        add_blocker(
            blockers,
            "question_file_missing",
            "A local UTF-8 question file is required.",
            field="question_file",
        )
        return ""
    if path.stat().st_size > MAX_QUESTION_FILE_BYTES:
        add_blocker(
            blockers,
            "question_file_too_large",
            f"The question file must be at most {MAX_QUESTION_FILE_BYTES} bytes.",
            field="question_file",
        )
        return ""
    try:
        question = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        add_blocker(
            blockers,
            "question_file_unreadable",
            "The question file must be readable UTF-8 text.",
            field="question_file",
        )
        return ""
    if not question or len(question) > MAX_QUESTION_LENGTH:
        add_blocker(
            blockers,
            "invalid_question",
            f"A question of at most {MAX_QUESTION_LENGTH} characters is required.",
            field="question_file",
        )
        return ""
    return question


def semantic_entity_context(entity: dict[str, Any]) -> dict[str, Any]:
    synonyms = entity.get("synonyms", [])
    return {
        "id": entity.get("id", ""),
        "name": entity.get("name", ""),
        "description": entity.get("description", ""),
        "synonyms": list(synonyms) if isinstance(synonyms, list) else [],
    }


def build_semantic_context(state: dict[str, Any]) -> dict[str, Any]:
    dataset = semantic_entity_context(state.get("dataset", {}))
    tables = [semantic_entity_context(row) for row in state.get("tables", [])]
    dimensions = []
    for row in state.get("dimensions", []):
        dimensions.append(
            {
                **semantic_entity_context(row),
                "table_id": row.get("table_id", ""),
            }
        )
    measures = []
    for row in state.get("measures", []):
        measures.append(
            {
                **semantic_entity_context(row),
                "table_id": row.get("table_id", ""),
            }
        )
    relationship_paths = []
    for row in state.get("relationship_paths", []):
        relationship_paths.append(
            {
                **semantic_entity_context(row),
                "semantic_hops": [
                    {
                        "source_semantic_table_id": hop.get("source_table_id", ""),
                        "target_semantic_table_id": hop.get("target_table_id", ""),
                    }
                    for hop in row.get("hops", [])
                    if isinstance(hop, dict)
                ],
            }
        )
    ambiguities = []
    for row in state.get("term_index", []):
        if not isinstance(row, dict) or row.get("status") != "ambiguous":
            continue
        ambiguities.append(
            {
                "term": row.get("term", ""),
                "candidates": [
                    {
                        "kind": target.get("kind", ""),
                        "id": target.get("id", ""),
                        "name": target.get("name", ""),
                    }
                    for target in row.get("targets", [])
                    if isinstance(target, dict)
                ],
            }
        )
    return {
        "version": 1,
        "dataset": dataset,
        "tables": tables,
        "dimensions": dimensions,
        "measures": measures,
        "relationship_paths": relationship_paths,
        "ambiguities": ambiguities,
    }


def provider_response_schema() -> dict[str, Any]:
    return {
        "version": 1,
        "required": ["version", "from"],
        "allowed_fields": sorted(ALLOWED_PROVIDER_FIELDS),
        "selection_item": {"term": "approved business term", "alias": "optional_identifier"},
        "filter_item": {
            "term": "approved dimension term",
            "operator": "eq|ne|gt|gte|lt|lte|in|is_null|not_null",
            "value": "required except for null checks",
        },
        "order_item": {"field": "selected output alias", "direction": "asc|desc"},
        "forbidden": ["question", "sql", "joins", "physical tables", "physical columns"],
    }


def canonical_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_provider_response(
    payload: Any,
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        add_blocker(
            blockers,
            "invalid_provider_response",
            "The provider response must be a mapping.",
            field="provider_response",
        )
        return {}
    for key in payload:
        if key == "question":
            add_blocker(
                blockers,
                "provider_question_not_allowed",
                "The provider cannot replace or repeat the authoritative local question.",
                field="provider_response.question",
            )
        elif key == "sql":
            add_blocker(
                blockers,
                "provider_sql_not_allowed",
                "Provider-generated SQL is never accepted.",
                field="provider_response.sql",
            )
        elif key == "joins":
            add_blocker(
                blockers,
                "provider_physical_join_not_allowed",
                "The provider must use semantic relationship paths, not physical joins.",
                field="provider_response.joins",
            )
        elif key not in ALLOWED_PROVIDER_FIELDS:
            add_blocker(
                blockers,
                "unsupported_provider_field",
                "The provider response contains a field outside the translation contract.",
                field=f"provider_response.{key}",
            )
    if isinstance(payload.get("version"), bool) or payload.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_provider_response_version",
            "The provider response must use version 1.",
            field="provider_response.version",
        )
    return payload


def build_intent(question: str, response: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "question": question,
        **{key: value for key, value in response.items() if key != "version"},
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


def render_report(
    status: str,
    provider: SemanticIntentProvider,
    blocker_count: int,
    clarification_count: int,
) -> str:
    lines = [
        "# Analytics Natural-Language Translation Report",
        "",
        f"- Status: `{status}`",
        f"- Provider: `{provider.name}`",
        f"- Provider mode: `{provider.mode}`",
        f"- Network required: `{str(provider.network_access_required).lower()}`",
        f"- Blockers: {blocker_count}",
        f"- Clarifications: {clarification_count}",
        "",
        "## Governance",
        "",
        "- The local question is authoritative; a provider cannot replace it.",
        "- Provider context excludes physical mappings, approval identity, and source fingerprints.",
        "- Provider output cannot contain SQL or physical joins.",
        "- Every accepted response passes through the deterministic Stage 5D semantic adapter.",
        "- Network providers require explicit opt-in and are disabled by default.",
        "- No database, query, migration, import, or synchronization is used.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Natural-language translation output is not a directory: {output_dir}")
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
            f"Different natural-language translation evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_nl_translation(
    question_path: Path,
    semantic_state_path: Path,
    output_dir: Path,
    provider: SemanticIntentProvider,
    *,
    timeout_seconds: int = 30,
    allow_network: bool = False,
) -> AnalyticsNlTranslationResult:
    blockers: list[dict[str, str]] = []
    question = read_question(question_path, blockers)
    state = read_yaml_mapping(semantic_state_path, blockers, "semantic_state")
    validate_approved_state(state, blockers)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or not 1 <= timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS
    ):
        add_blocker(
            blockers,
            "invalid_provider_timeout",
            f"Provider timeout must be between 1 and {MAX_PROVIDER_TIMEOUT_SECONDS} seconds.",
            field="timeout_seconds",
        )
    if provider.network_access_required and not allow_network:
        add_blocker(
            blockers,
            "network_provider_not_authorized",
            "Network provider use requires explicit opt-in for this invocation.",
            field="provider",
        )

    semantic_context = build_semantic_context(state) if not blockers else {}
    if semantic_context and len(canonical_yaml(semantic_context).encode("utf-8")) > MAX_SEMANTIC_CONTEXT_BYTES:
        add_blocker(
            blockers,
            "semantic_context_too_large",
            f"Minimized semantic context must be at most {MAX_SEMANTIC_CONTEXT_BYTES} bytes.",
            field="semantic_state",
        )
        semantic_context = {}
    prompt = SemanticTranslationPrompt(
        question=question,
        semantic_context=semantic_context,
        response_schema=provider_response_schema(),
    )
    provider_called = False
    response: dict[str, Any] = {}
    if not blockers:
        try:
            provider_called = True
            raw_response = provider.translate(prompt, timeout_seconds=timeout_seconds)
            raw_response_content = canonical_yaml(raw_response) if isinstance(raw_response, dict) else ""
            if len(raw_response_content.encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
                add_blocker(
                    blockers,
                    "provider_response_too_large",
                    f"Provider response must be at most {MAX_PROVIDER_RESPONSE_BYTES} bytes.",
                    field="provider_response",
                )
            else:
                response = validate_provider_response(raw_response, blockers)
        except TimeoutError:
            add_blocker(
                blockers,
                "provider_timeout",
                "The semantic translation provider timed out.",
                field="provider",
            )
        except Exception:
            add_blocker(
                blockers,
                "provider_failure",
                "The semantic translation provider failed without producing an accepted response.",
                field="provider",
            )

    intent = build_intent(question, response) if response and not blockers else None
    adapter_blockers: list[dict[str, str]] = []
    clarifications: list[dict[str, Any]] = []
    if intent is not None:
        compile_intent(intent, state, adapter_blockers, clarifications)
        blockers.extend(adapter_blockers)
        if blockers:
            intent = None

    status = (
        "blocked"
        if blockers
        else "clarification_required"
        if clarifications
        else "ready_for_query_plan"
    )
    intent_content = canonical_yaml(intent) if intent is not None else ""
    response_content = canonical_yaml(response) if response else ""
    context_content = canonical_yaml(semantic_context) if semantic_context else ""
    source = {
        "question_sha256": file_sha256(question_path) if question_path.is_file() else "",
        "approved_semantic_state_sha256": (
            file_sha256(semantic_state_path) if semantic_state_path.is_file() else ""
        ),
        "provider_response_sha256": content_sha256(response_content) if response_content else "",
        "semantic_context_sha256": content_sha256(context_content) if context_content else "",
    }
    manifest = {
        "version": 1,
        "status": status,
        "source": source,
        "provider": {
            "name": provider.name,
            "mode": provider.mode,
            "network_access_required": provider.network_access_required,
            "network_authorized": allow_network,
            "called": provider_called,
            "timeout_seconds": timeout_seconds,
        },
        "privacy": {
            "question_persisted_only_in_local_intent_and_request": bool(intent),
            "physical_mappings_shared_with_provider": False,
            "approval_identity_shared_with_provider": False,
            "source_fingerprints_shared_with_provider": False,
        },
        "counts": {
            "blockers": len(blockers),
            "clarifications": len(clarifications),
        },
        "intent_sha256": content_sha256(intent_content) if intent_content else "",
    }
    contents = {
        MANIFEST_NAME: canonical_yaml(manifest),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(
            status,
            provider,
            len(blockers),
            len(clarifications),
        ),
    }
    if intent_content:
        contents[INTENT_NAME] = intent_content
    outputs_changed = write_outputs(output_dir, contents)

    adapter_result = None
    intent_path = output_dir / INTENT_NAME if intent is not None else None
    if intent_path is not None:
        adapter_result = run_analytics_semantic_adapter(
            intent_path,
            semantic_state_path,
            output_dir / ADAPTER_DIR_NAME,
        )
        if adapter_result.status != status:
            raise ValueError("Stage 5D translation and semantic adapter statuses diverged.")
    return AnalyticsNlTranslationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        intent_path=intent_path,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        adapter_result=adapter_result,
        blocker_count=len(blockers),
        clarification_count=len(clarifications),
        provider_called=provider_called,
        outputs_changed=outputs_changed or bool(adapter_result and adapter_result.outputs_changed),
    )
