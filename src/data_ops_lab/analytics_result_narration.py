from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from .analytics_query_plan import add_blocker, read_yaml_mapping
from .contracts.source_bindings import existing_file_sha256_bindings
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_result_narration.yml"
NARRATIVE_NAME = "analytics_result_narrative.md"
BLOCKERS_NAME = "analytics_result_narration_blockers.csv"
REPORT_NAME = "analytics_result_narration_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, NARRATIVE_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_PROVIDER_RESPONSE_BYTES = 100_000
MAX_PROVIDER_TIMEOUT_SECONDS = 120
MAX_HEADLINE_LENGTH = 160
MAX_CLAIMS = 20
MAX_CLAIM_LENGTH = 1_000
MAX_CITATIONS_PER_CLAIM = 10
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:[.,]\d+)?%?(?![A-Za-z0-9_])")
SQL_PATTERN = re.compile(
    r"\b(select|insert|update|delete|drop|alter|create|merge|truncate|grant|revoke|attach|copy|pragma|call)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResultNarrationPrompt:
    question: str
    facts: tuple[dict[str, Any], ...]
    caveats: tuple[str, ...]
    response_schema: dict[str, Any]


class ResultNarrationProvider(Protocol):
    name: str
    mode: str
    network_access_required: bool

    def narrate(
        self,
        prompt: ResultNarrationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]: ...


class RecordedResultNarrationProvider:
    name = "recorded_response"
    mode = "offline"
    network_access_required = False

    def __init__(self, response_path: Path) -> None:
        self.response_path = response_path

    def narrate(
        self,
        prompt: ResultNarrationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del prompt, timeout_seconds
        if not self.response_path.is_file():
            raise FileNotFoundError("Recorded narration response is missing.")
        if self.response_path.stat().st_size > MAX_PROVIDER_RESPONSE_BYTES:
            raise ValueError("Recorded narration response exceeds the size limit.")
        try:
            payload = yaml.safe_load(self.response_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise ValueError("Recorded narration response is not valid UTF-8 YAML.") from error
        if not isinstance(payload, dict):
            raise ValueError("Recorded narration response must be a YAML mapping.")
        return payload


@dataclass(frozen=True)
class AnalyticsResultNarrationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    narrative_path: Path | None
    blockers_path: Path
    report_path: Path
    blocker_count: int
    claim_count: int
    provider_called: bool
    outputs_changed: bool


def canonical_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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


def response_schema() -> dict[str, Any]:
    return {
        "version": 1,
        "required": ["version", "headline", "claims"],
        "claim": {
            "required": ["text", "citations"],
            "citations": "one or more exact supplied fact IDs",
        },
        "forbidden": ["sql", "query", "recalculated values", "uncited claims"],
    }


def validate_facts_bundle(
    payload: dict[str, Any],
    blockers: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    if payload.get("version") != 1 or payload.get("status") != "ready_for_recorded_narration":
        add_blocker(
            blockers,
            "facts_not_ready",
            "A ready version-1 deterministic facts bundle is required.",
            field="facts",
        )
    question = payload.get("question", "")
    facts = payload.get("facts", [])
    caveats = payload.get("caveats", [])
    if not isinstance(question, str):
        add_blocker(blockers, "invalid_facts", "Question must be text.", field="facts.question")
        question = ""
    if not isinstance(facts, list) or not facts:
        add_blocker(blockers, "invalid_facts", "Facts must be a non-empty list.", field="facts.facts")
        facts = []
    if not isinstance(caveats, list) or not all(isinstance(item, str) for item in caveats):
        add_blocker(blockers, "invalid_facts", "Caveats must be a text list.", field="facts.caveats")
        caveats = []
    seen: set[str] = set()
    for index, item in enumerate(facts):
        if not isinstance(item, dict):
            add_blocker(
                blockers,
                "invalid_fact",
                "Every fact must be a mapping.",
                field=f"facts.facts[{index}]",
            )
            continue
        fact_id = item.get("id")
        value = item.get("value")
        required = item.get("required_citation")
        if (
            not isinstance(fact_id, str)
            or not fact_id
            or fact_id in seen
            or not isinstance(value, str)
            or not isinstance(required, bool)
        ):
            add_blocker(
                blockers,
                "invalid_fact",
                "Fact IDs must be unique and each fact needs text value and citation control.",
                field=f"facts.facts[{index}]",
            )
        else:
            seen.add(fact_id)
    return question, facts, caveats


def validate_presentation_manifest(
    payload: dict[str, Any],
    facts_path: Path,
    facts_bundle: dict[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    if payload.get("version") != 1 or payload.get("status") != "ready_for_recorded_narration":
        add_blocker(
            blockers,
            "presentation_not_ready",
            "A ready version-1 deterministic presentation manifest is required.",
            field="presentation_manifest",
        )
    if facts_path.is_file() and payload.get("facts_sha256") != file_sha256(facts_path):
        add_blocker(
            blockers,
            "facts_hash_mismatch",
            "The facts bundle does not match the deterministic presentation manifest.",
            field="facts",
        )
    manifest_source = payload.get("source", {})
    facts_source = facts_bundle.get("source", {})
    if not isinstance(manifest_source, dict) or manifest_source != facts_source:
        add_blocker(
            blockers,
            "facts_source_mismatch",
            "Facts source hashes do not match the deterministic presentation manifest.",
            field="facts.source",
        )
    controls = payload.get("controls", {})
    required_controls = {
        "stage_5b_result_is_numeric_authority": True,
        "query_execution_available": False,
        "raw_sql_accepted": False,
        "network_access": False,
        "full_result_modified": False,
    }
    if not isinstance(controls, dict) or any(
        controls.get(key) != expected for key, expected in required_controls.items()
    ):
        add_blocker(
            blockers,
            "unsafe_presentation_evidence",
            "The deterministic presentation safety controls are incomplete.",
            field="presentation_manifest.controls",
        )


def forbidden_narrative_text(value: str) -> bool:
    return bool(SQL_PATTERN.search(value) or "```" in value or ";" in value)


def markdown_text(value: str) -> str:
    escaped = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("#", "\\#")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    return " ".join(escaped.split())


def validate_provider_response(
    payload: Any,
    facts: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"version", "headline", "claims"}:
        add_blocker(
            blockers,
            "invalid_provider_response",
            "Narration response must contain only version, headline, and claims.",
            field="provider_response",
        )
        return {}
    if payload.get("version") != 1:
        add_blocker(
            blockers,
            "unsupported_provider_response_version",
            "Only version-1 narration responses are accepted.",
            field="provider_response.version",
        )
    headline = payload.get("headline")
    claims = payload.get("claims")
    if (
        not isinstance(headline, str)
        or not headline.strip()
        or len(headline.strip()) > MAX_HEADLINE_LENGTH
        or NUMBER_PATTERN.search(headline)
        or forbidden_narrative_text(headline)
    ):
        add_blocker(
            blockers,
            "invalid_headline",
            "Headline must be bounded non-numeric prose and cannot contain query language.",
            field="provider_response.headline",
        )
    if not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS:
        add_blocker(
            blockers,
            "invalid_claims",
            f"Narration must contain between 1 and {MAX_CLAIMS} claims.",
            field="provider_response.claims",
        )
        return {}

    fact_map = {
        item["id"]: item
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    cited_all: set[str] = set()
    for index, claim in enumerate(claims):
        field = f"provider_response.claims[{index}]"
        if not isinstance(claim, dict) or set(claim) != {"text", "citations"}:
            add_blocker(
                blockers,
                "invalid_claim",
                "Each claim must contain only text and citations.",
                field=field,
            )
            continue
        text = claim.get("text")
        citations = claim.get("citations")
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.strip()) > MAX_CLAIM_LENGTH
            or forbidden_narrative_text(text)
        ):
            add_blocker(
                blockers,
                "invalid_claim_text",
                "Claim text must be bounded prose and cannot contain query language.",
                field=f"{field}.text",
            )
            continue
        if (
            not isinstance(citations, list)
            or not 1 <= len(citations) <= MAX_CITATIONS_PER_CLAIM
            or len(set(citations)) != len(citations)
            or not all(isinstance(item, str) and item in fact_map for item in citations)
        ):
            add_blocker(
                blockers,
                "invalid_claim_citations",
                "Every claim needs unique citations to supplied fact IDs only.",
                field=f"{field}.citations",
            )
            continue
        cited_all.update(citations)
        cited_numeric_tokens = {
            token
            for fact_id in citations
            for token in NUMBER_PATTERN.findall(fact_map[fact_id]["value"])
        }
        claim_numeric_tokens = set(NUMBER_PATTERN.findall(text))
        if not claim_numeric_tokens.issubset(cited_numeric_tokens):
            add_blocker(
                blockers,
                "ungrounded_numeric_value",
                "Every numeric value in a claim must exactly match a cited fact value.",
                field=f"{field}.text",
            )
    required_ids = {
        item["id"]
        for item in facts
        if isinstance(item, dict) and item.get("required_citation") is True
    }
    if not required_ids.issubset(cited_all):
        add_blocker(
            blockers,
            "required_controls_not_cited",
            "Narration must cite row count, no-row state, and preview truncation controls.",
            field="provider_response.claims",
        )
    return payload if not blockers else {}


def render_narrative(response: dict[str, Any]) -> str:
    lines = [
        f"# {markdown_text(response['headline'])}",
        "",
        *[
            f"- {markdown_text(claim['text'])} "
            + " ".join(f"`[{fact_id}]`" for fact_id in claim["citations"])
            for claim in response["claims"]
        ],
        "",
        "## Authority",
        "",
        "The deterministic facts and Stage 5B result are authoritative. This narration is a cited presentation layer only.",
    ]
    return "\n".join(lines) + "\n"


def render_report(
    status: str,
    provider: ResultNarrationProvider,
    blocker_count: int,
    claim_count: int,
) -> str:
    return "\n".join(
        [
            "# Analytics Result Narration Report",
            "",
            f"- Status: `{status}`",
            f"- Provider: `{provider.name}`",
            f"- Provider mode: `{provider.mode}`",
            f"- Claims: {claim_count}",
            f"- Blockers: {blocker_count}",
            "",
            "## Boundary",
            "",
            "- Only supplied deterministic facts can be cited.",
            "- Numeric claim values must exactly match cited fact values.",
            "- Required result controls cannot be omitted.",
            "- SQL, query execution, fact mutation, and implicit network access are unavailable.",
            "- Narration is not analytical or numeric authority.",
        ]
    ) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Result narration output is not a directory: {output_dir}")
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
            f"Different result narration evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_analytics_result_narration(
    presentation_manifest_path: Path,
    facts_path: Path,
    output_dir: Path,
    provider: ResultNarrationProvider,
    *,
    timeout_seconds: int = 30,
    allow_network: bool = False,
) -> AnalyticsResultNarrationResult:
    blockers: list[dict[str, str]] = []
    input_paths = {
        "presentation_manifest": presentation_manifest_path,
        "facts": facts_path,
    }
    input_hashes = existing_file_sha256_bindings(input_paths)
    presentation_manifest = read_yaml_mapping(
        presentation_manifest_path,
        blockers,
        "presentation_manifest",
    )
    facts_bundle = read_yaml_mapping(facts_path, blockers, "facts")
    question, facts, caveats = validate_facts_bundle(facts_bundle, blockers)
    validate_presentation_manifest(
        presentation_manifest,
        facts_path,
        facts_bundle,
        blockers,
    )
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
            "Network narration requires explicit opt-in for this invocation.",
            field="provider",
        )

    prompt = ResultNarrationPrompt(
        question=question,
        facts=tuple(facts),
        caveats=tuple(caveats),
        response_schema=response_schema(),
    )
    provider_called = False
    response: dict[str, Any] = {}
    response_content = ""
    if not blockers:
        try:
            provider_called = True
            raw_response = provider.narrate(prompt, timeout_seconds=timeout_seconds)
            response_content = canonical_yaml(raw_response) if isinstance(raw_response, dict) else ""
            if len(response_content.encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
                add_blocker(
                    blockers,
                    "provider_response_too_large",
                    f"Narration response must be at most {MAX_PROVIDER_RESPONSE_BYTES} bytes.",
                    field="provider_response",
                )
            else:
                response = validate_provider_response(raw_response, facts, blockers)
        except TimeoutError:
            add_blocker(blockers, "provider_timeout", "The narration provider timed out.", field="provider")
        except Exception:
            add_blocker(
                blockers,
                "provider_failure",
                "The narration provider failed without producing an accepted response.",
                field="provider",
            )

    if not blockers:
        current_hashes = existing_file_sha256_bindings(input_paths)
        if current_hashes != input_hashes:
            add_blocker(
                blockers,
                "narration_inputs_changed",
                "A validated presentation input changed during narration.",
                field="inputs",
            )
            response = {}

    status = "blocked" if blockers else "ready_for_user"
    claim_count = len(response.get("claims", [])) if response else 0
    manifest = {
        "version": 1,
        "status": status,
        "source": {
            "presentation_manifest_sha256": (
                input_hashes.get("presentation_manifest", "")
            ),
            "facts_sha256": input_hashes.get("facts", ""),
            "provider_response_sha256": content_sha256(response_content) if response_content else "",
        },
        "provider": {
            "name": provider.name,
            "mode": provider.mode,
            "network_access_required": provider.network_access_required,
            "network_authorized": allow_network,
            "called": provider_called,
            "timeout_seconds": timeout_seconds,
        },
        "controls": {
            "facts_are_authoritative": True,
            "numeric_values_require_exact_cited_match": True,
            "required_caveat_controls_cited": not blockers,
            "query_execution_available": False,
            "raw_sql_accepted": False,
            "facts_modified": False,
        },
        "privacy": {
            "question_or_fact_values_in_manifest": False,
            "narrative_text_in_manifest": False,
        },
        "counts": {"claims": claim_count, "blockers": len(blockers)},
    }
    contents = {
        MANIFEST_NAME: canonical_yaml(manifest),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(status, provider, len(blockers), claim_count),
    }
    if response:
        contents[NARRATIVE_NAME] = render_narrative(response)
    outputs_changed = write_outputs(output_dir, contents)
    return AnalyticsResultNarrationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        narrative_path=output_dir / NARRATIVE_NAME if response else None,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        blocker_count=len(blockers),
        claim_count=claim_count,
        provider_called=provider_called,
        outputs_changed=outputs_changed,
    )
