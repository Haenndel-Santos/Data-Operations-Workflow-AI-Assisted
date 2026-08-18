"""Governed cleaning engine: propose, authorize, apply.

The engine turns the governed cleaning contract into an opt-in route that
lives beside the legacy cleaner. `run_workflow()` and `clean_dataframe()` are
untouched. Nothing here calls a model or the network; D2 v1 is deterministic
and local.

    PROPOSE     actual Parquet (+ optional source manifest)
                -> verify source inventory and hashes
                -> derive source_sha256 from the real files
                -> deterministic profiling
                -> proposal bundle: automatic and configured exact steps,
                   governed candidates at pending_review, review template
                -> atomic publish; no value is changed

    AUTHORIZE   proposal bundle + exact human review + cleaning policy
                -> verify proposal hash and current source binding
                -> require an explicit disposition for every governed candidate
                -> record_decision, then one authority per governance class
                -> ordered, hash-bound application plan
                -> atomic publish; no value is changed

    APPLY       authority bundle + application plan + current source
                -> verify everything again, before touching staging
                -> apply steps in plan order into staging
                -> logical and physical output hashes, lineage per step
                -> atomic publish; a failure anywhere before publish leaves
                   zero promoted output

Discovery happens once, in propose. Authority is born once, in authorize.
Apply never infers anything it was not handed.
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

from dataclasses import asdict

from .contracts.atomic_publish import publish_new_directory
from .contracts.blockers import add_blocker
from .contracts.hashing import file_sha256
from .governed_cleaning import (
    IDENTIFIER_PATTERN,
    ApprovedTransformation,
    AutomaticAuthority,
    CleaningPolicy,
    ConfiguredAuthority,
    DecisionKind,
    GovernanceClass,
    PolicyOperation,
    ReviewState,
    TransformationCandidate,
    TransformationDecision,
    TransformationEvidence,
    TransformationOperation,
    authorize_application,
    authorize_configured,
    build_automatic_authority,
    build_candidate,
    build_lineage,
    candidate_hash,
    governance_class_for,
    record_decision,
    sha256_of,
    submit_for_review,
    verify_authority,
    verify_automatic_authority,
    verify_configured_authority,
)
from .io_utils import slugify


ENGINE_VERSION = 1
PROPOSAL_VERSION = 1
AUTHORIZATION_VERSION = 1
APPLICATION_PLAN_VERSION = 1
APPLICATION_VERSION = 1

# Proposer policy, not authority: below this share of parseable values the
# proposer does not bother the reviewer with a governed candidate.
PROPOSAL_MIN_SUCCESS_RATIO = 0.5

# The only sentinels the proposer will *observe* and report; the policy decides
# which of them, if any, are normalized.
OBSERVED_BLANK_SENTINELS = ("", " ", "na", "n/a", "none", "null", "-", "--")

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLASH_DATE_PATTERN = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
NUMBER_PATTERN = re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")

PROPOSAL_MANIFEST_NAME = "proposal_manifest.yml"
CANDIDATES_NAME = "candidates.yml"
REVIEW_TEMPLATE_NAME = "review_template.yml"
AUTHORITIES_NAME = "authorities.yml"
APPLICATION_PLAN_NAME = "application_plan.yml"
AUTHORIZATION_MANIFEST_NAME = "authorization_manifest.yml"
APPLICATION_MANIFEST_NAME = "application_manifest.yml"
LINEAGE_NAME = "lineage.yml"
BLOCKERS_NAME = "blockers.csv"
REPORT_NAME = "report.md"
PARQUET_DIR_NAME = "parquet"

# Engine v1 applies exactly these. Anything else authorized by the contract is
# refused at apply time with operation_not_supported_by_engine.
ENGINE_SUPPORTED_OPERATIONS = frozenset(
    {
        TransformationOperation.NORMALIZE_COLUMN_NAME,
        TransformationOperation.TRIM_WHITESPACE,
        TransformationOperation.NORMALIZE_BLANK_SENTINEL,
        TransformationOperation.PARSE_NUMBER,
        TransformationOperation.PARSE_DATE,
    }
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_yaml(payload: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(payload), sort_keys=False, allow_unicode=False)


def blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["blocker_id", "blocker_type", "field", "explanation"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def read_yaml_mapping(path: Path, field: str, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(blockers, "missing_input_file", f"{field} file is missing.", field=field)
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        add_blocker(blockers, "unreadable_input_file", f"{field} file is not readable YAML.", field=field)
        return {}
    if not isinstance(payload, dict):
        add_blocker(blockers, "invalid_input_file", f"{field} file must contain a mapping.", field=field)
        return {}
    return payload


def _publish_bundle(output_dir: Path, files: Mapping[str, str]) -> None:
    """Write every file into a staging sibling, then publish atomically."""
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        for name, content in files.items():
            (staging / name).write_text(content, encoding="utf-8", newline="")
        publish_new_directory(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


@dataclass(frozen=True)
class SourceInventory:
    source_sha256: str
    files: tuple[dict[str, str], ...]  # {path, sha256}


def verify_source(
    parquet_dir: Path,
    source_manifest_path: Path | None,
    blockers: list[dict[str, str]],
) -> SourceInventory | None:
    """Derive the source hash from the real files. A manifest, if given, is
    verified against them and never trusted on its own."""
    if not parquet_dir.is_dir():
        add_blocker(blockers, "source_directory_missing", "Parquet source directory does not exist.", field="parquet_dir")
        return None
    files = []
    for path in sorted(parquet_dir.glob("*.parquet")):
        files.append({"path": path.name, "sha256": file_sha256(path)})
    if not files:
        add_blocker(blockers, "source_directory_empty", "Parquet source directory contains no .parquet files.", field="parquet_dir")
        return None
    if source_manifest_path is not None:
        manifest = read_yaml_mapping(source_manifest_path, "source_manifest", blockers)
        declared = manifest.get("files")
        if not isinstance(declared, list):
            add_blocker(blockers, "invalid_source_manifest", "source_manifest must list files with path and sha256.", field="source_manifest.files")
            return None
        declared_map: dict[str, str] = {}
        for entry in declared:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str):
                add_blocker(blockers, "invalid_source_manifest", "Every source_manifest file entry needs path and sha256.", field="source_manifest.files")
                return None
            declared_map[entry["path"]] = entry["sha256"]
        actual_map = {f["path"]: f["sha256"] for f in files}
        if set(declared_map) != set(actual_map):
            add_blocker(blockers, "source_manifest_inventory_mismatch", "source_manifest lists a different set of Parquet files than the directory contains.", field="source_manifest.files")
            return None
        for name, digest in actual_map.items():
            if declared_map[name] != digest:
                add_blocker(blockers, "source_manifest_hash_mismatch", f"source_manifest hash for {name} does not match the actual file.", field="source_manifest.files")
                return None
    return SourceInventory(source_sha256=sha256_of(files), files=tuple(files))


def logical_content_sha256(frame: pd.DataFrame) -> str:
    """Hash of schema + values in canonical JSON, independent of Parquet
    encoder bytes. Two frames with the same columns, dtypes, and values hash
    the same regardless of the writer version."""
    columns = [{"name": str(c), "dtype": str(frame[c].dtype)} for c in frame.columns]
    rows: list[list[Any]] = []
    for record in frame.itertuples(index=False, name=None):
        rows.append([_json_value(v) for v in record])
    return sha256_of({"columns": columns, "rows": rows})


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return float(repr(value)) if value == value else None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _string_series(series: pd.Series) -> pd.Series | None:
    """Return the non-null values as Python str, or None if not string-like."""
    non_null = series.dropna()
    if non_null.empty:
        return None
    if not all(isinstance(v, str) for v in non_null.head(50)):
        return None
    if not all(isinstance(v, str) for v in non_null):
        return None
    return non_null.astype(str)


# --------------------------------------------------------------------------- #
# PROPOSE
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GovernedCleaningProposeResult:
    output_dir: Path
    status: str
    source_sha256: str
    proposal_sha256: str
    candidate_count: int
    configured_step_count: int
    automatic_step_count: int
    blocker_count: int


def _profile_parse_number(values: pd.Series) -> tuple[TransformationEvidence, dict[str, Any]] | None:
    total = int(len(values))
    matches = values.map(lambda v: bool(NUMBER_PATTERN.fullmatch(v.strip())))
    success = int(matches.sum())
    if success == 0:
        return None
    thousands = int(values[matches].map(lambda v: "," in v).sum())
    ev = TransformationEvidence(
        values_examined=total,
        non_null_count=total,
        candidate_count=total,
        success_count=success,
        failure_count=total - success,
        ambiguous_count=0,
        metrics={"thousands_separator_ratio": round(thousands / success, 4) if success else 0.0},
    )
    return ev, {"thousands": ",", "decimal": "."}


def _profile_parse_date(values: pd.Series) -> tuple[TransformationEvidence, dict[str, Any]] | None:
    total = int(len(values))
    stripped = values.map(str.strip)
    iso = stripped.map(lambda v: bool(ISO_DATE_PATTERN.fullmatch(v)))
    slash = stripped.map(lambda v: bool(SLASH_DATE_PATTERN.fullmatch(v)))
    iso_count, slash_count = int(iso.sum()), int(slash.sum())
    if iso_count == 0 and slash_count == 0:
        return None
    if iso_count >= slash_count:
        fmt = "%Y-%m-%d"
        parsed = pd.to_datetime(stripped, format=fmt, errors="coerce")
        success = int(parsed.notna().sum())
        ambiguous = 0
    else:
        # Choose the slash order that parses more values; count values that
        # parse under both orders as ambiguous.
        dmy = pd.to_datetime(stripped, format="%d/%m/%Y", errors="coerce")
        mdy = pd.to_datetime(stripped, format="%m/%d/%Y", errors="coerce")
        dmy_ok, mdy_ok = int(dmy.notna().sum()), int(mdy.notna().sum())
        fmt = "%d/%m/%Y" if dmy_ok >= mdy_ok else "%m/%d/%Y"
        success = max(dmy_ok, mdy_ok)
        ambiguous = int((dmy.notna() & mdy.notna()).sum())
    if success == 0:
        return None
    ev = TransformationEvidence(
        values_examined=total,
        non_null_count=total,
        candidate_count=total,
        success_count=success,
        failure_count=total - success,
        ambiguous_count=ambiguous,
        metrics={"iso_ratio": round(iso_count / total, 4)},
    )
    return ev, {"format": fmt}


def _profile_table(
    table: str,
    frame: pd.DataFrame,
    source_sha256: str,
    blockers: list[dict[str, str]],
) -> tuple[list[TransformationCandidate], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[TransformationCandidate] = []
    configured: list[dict[str, Any]] = []
    automatic: list[dict[str, Any]] = []
    for column in frame.columns:
        name = str(column)
        if slugify(name) != name:
            automatic.append({"operation": TransformationOperation.NORMALIZE_COLUMN_NAME.value, "table": table, "column": name, "target": slugify(name)})
        if not IDENTIFIER_PATTERN.fullmatch(name):
            # The contract scopes authority by identifier-shaped table and
            # column. A column that is not one yet can only receive the
            # automatic rename in this cycle; value operations come after.
            continue
        values = _string_series(frame[column])
        if values is None:
            continue
        stripped_diff = int((values != values.map(str.strip)).sum())
        if stripped_diff:
            configured.append({"operation": TransformationOperation.TRIM_WHITESPACE.value, "table": table, "column": name, "observed": {"values_with_padding": stripped_diff}})
        observed = sorted({v for v in values.map(str.strip).map(str.lower) if v in OBSERVED_BLANK_SENTINELS})
        if observed:
            configured.append({"operation": TransformationOperation.NORMALIZE_BLANK_SENTINEL.value, "table": table, "column": name, "observed": {"sentinels": observed}})
        for operation, profiler in ((TransformationOperation.PARSE_NUMBER, _profile_parse_number), (TransformationOperation.PARSE_DATE, _profile_parse_date)):
            profiled = profiler(values)
            if profiled is None:
                continue
            evidence, parameters = profiled
            if evidence.success_ratio < PROPOSAL_MIN_SUCCESS_RATIO:
                continue
            candidate = build_candidate(
                candidate_id=f"{table}.{name}.{operation.value}",
                source_sha256=source_sha256,
                table=table,
                column=name,
                operation=operation,
                parameters=parameters,
                evidence=evidence,
                blockers=blockers,
            )
            if candidate is None:
                continue
            submitted = submit_for_review(candidate, blockers)
            if submitted is not None:
                candidates.append(submitted)
    return candidates, configured, automatic


def _candidate_record(candidate: TransformationCandidate) -> dict[str, Any]:
    ev = candidate.evidence
    return {
        "candidate_id": candidate.candidate_id,
        "candidate_sha256": candidate_hash(candidate),
        "source_sha256": candidate.source_sha256,
        "table": candidate.table,
        "column": candidate.column,
        "operation": candidate.operation.value,
        "governance_class": candidate.governance_class.value,
        "parameters": dict(candidate.parameters),
        "evidence": {
            "values_examined": ev.values_examined,
            "non_null_count": ev.non_null_count,
            "candidate_count": ev.candidate_count,
            "success_count": ev.success_count,
            "failure_count": ev.failure_count,
            "ambiguous_count": ev.ambiguous_count,
            "metrics": dict(ev.metrics),
        },
        "computed_confidence": candidate.computed_confidence,
        "review_state": candidate.review_state.value,
        "contract_version": candidate.contract_version,
        "confidence_formula_version": candidate.confidence_formula_version,
    }


def _candidate_from_record(record: Mapping[str, Any], blockers: list[dict[str, str]], field: str) -> TransformationCandidate | None:
    try:
        ev = record["evidence"]
        evidence = TransformationEvidence(
            values_examined=int(ev["values_examined"]),
            non_null_count=int(ev["non_null_count"]),
            candidate_count=int(ev["candidate_count"]),
            success_count=int(ev["success_count"]),
            failure_count=int(ev["failure_count"]),
            ambiguous_count=int(ev["ambiguous_count"]),
            metrics=dict(ev.get("metrics") or {}),
        )
        candidate = build_candidate(
            candidate_id=str(record["candidate_id"]),
            source_sha256=str(record["source_sha256"]),
            table=str(record["table"]),
            column=str(record["column"]),
            operation=str(record["operation"]),
            parameters=dict(record.get("parameters") or {}),
            evidence=evidence,
            blockers=blockers,
        )
    except (KeyError, TypeError, ValueError):
        add_blocker(blockers, "invalid_candidate_record", "Candidate record is missing required fields or has wrong types.", field=field)
        return None
    if candidate is None:
        return None
    try:
        state = ReviewState(str(record.get("review_state", "candidate")))
    except ValueError:
        add_blocker(blockers, "invalid_candidate_record", "Candidate record carries an unknown review_state.", field=f"{field}.review_state")
        return None
    if state is ReviewState.PENDING_REVIEW:
        candidate = submit_for_review(candidate, blockers)
        if candidate is None:
            return None
    elif state is not ReviewState.CANDIDATE:
        add_blocker(blockers, "candidate_record_carries_authority", f"Persisted candidate records may not carry state {state.value}; state is derived from decisions.", field=f"{field}.review_state")
        return None
    if candidate_hash(candidate) != record.get("candidate_sha256"):
        add_blocker(blockers, "candidate_record_hash_mismatch", "Persisted candidate_sha256 does not match the recomputed candidate.", field=f"{field}.candidate_sha256")
        return None
    return candidate


def _proposal_hash(manifest: Mapping[str, Any]) -> str:
    payload = {k: v for k, v in manifest.items() if k != "proposal_sha256"}
    return sha256_of(payload)


def run_governed_cleaning_propose(
    parquet_dir: Path,
    output_dir: Path,
    *,
    source_manifest_path: Path | None = None,
) -> GovernedCleaningProposeResult:
    blockers: list[dict[str, str]] = []
    if output_dir.exists():
        add_blocker(blockers, "output_directory_exists", "Output directory already exists; proposals are published to a new directory only.", field="output_dir")
        return GovernedCleaningProposeResult(output_dir, "blocked", "", "", 0, 0, 0, len(blockers))

    inventory = verify_source(parquet_dir, source_manifest_path, blockers)
    candidates: list[TransformationCandidate] = []
    configured: list[dict[str, Any]] = []
    automatic: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    if inventory is not None:
        for entry in inventory.files:
            table = Path(entry["path"]).stem
            try:
                frame = pd.read_parquet(parquet_dir / entry["path"])
            except Exception:  # noqa: BLE001 - any reader failure is a source blocker, reported and stopped
                add_blocker(blockers, "source_parquet_unreadable", f"{entry['path']} could not be read as Parquet.", field="parquet_dir")
                continue
            tables.append({"table": table, "path": entry["path"], "sha256": entry["sha256"], "rows": int(len(frame)), "columns": [str(c) for c in frame.columns]})
            c, cfg, auto = _profile_table(table, frame, inventory.source_sha256, blockers)
            candidates.extend(c)
            configured.extend(cfg)
            automatic.extend(auto)

    status = "blocked" if blockers else "ready_for_review"
    if status == "blocked":
        candidates, configured, automatic = [], [], []

    manifest: dict[str, Any] = {
        "version": PROPOSAL_VERSION,
        "engine_version": ENGINE_VERSION,
        "status": status,
        # Artifact identity, covered by proposal_sha256. Two proposals over
        # unchanged data in the same second would otherwise hash the same, and
        # a review must bind to the exact artifact the human looked at.
        "proposal_id": str(uuid.uuid4()),
        "proposed_at": utc_now(),
        "source_sha256": inventory.source_sha256 if inventory else "",
        "source_files": [dict(f) for f in inventory.files] if inventory else [],
        "tables": tables,
        "automatic": automatic,
        "configured": configured,
        "governed": [{"candidate_id": c.candidate_id, "candidate_sha256": candidate_hash(c)} for c in candidates],
        "blocker_count": len(blockers),
    }
    manifest["proposal_sha256"] = _proposal_hash(manifest)

    candidates_doc = {
        "version": PROPOSAL_VERSION,
        "proposal_sha256": manifest["proposal_sha256"],
        "source_sha256": manifest["source_sha256"],
        "candidates": [_candidate_record(c) for c in candidates],
    }
    review_template = {
        "version": AUTHORIZATION_VERSION,
        "proposal_sha256": manifest["proposal_sha256"],
        "reviewer": "",
        "decisions": [
            {"candidate_id": c.candidate_id, "candidate_sha256": candidate_hash(c), "decision": "", "reviewed_at": "", "note": ""}
            for c in candidates
        ],
    }
    report = "\n".join(
        [
            "# Governed Cleaning Proposal",
            "",
            f"- Status: {status}",
            f"- Source SHA-256: {manifest['source_sha256'] or '(unverified)'}",
            f"- Proposal SHA-256: {manifest['proposal_sha256']}",
            f"- Tables: {len(tables)}",
            f"- Automatic steps: {len(automatic)}",
            f"- Configured steps: {len(configured)}",
            f"- Governed candidates: {len(candidates)}",
            f"- Blockers: {len(blockers)}",
            "",
            "No value was changed. Governed candidates are pending_review; configured steps",
            "need an exact cleaning policy; automatic steps run under the operation table.",
            "",
        ]
    )
    _publish_bundle(
        output_dir,
        {
            PROPOSAL_MANIFEST_NAME: canonical_yaml(manifest),
            CANDIDATES_NAME: canonical_yaml(candidates_doc),
            REVIEW_TEMPLATE_NAME: canonical_yaml(review_template),
            BLOCKERS_NAME: blockers_csv(blockers),
            REPORT_NAME: report,
        },
    )
    return GovernedCleaningProposeResult(
        output_dir=output_dir,
        status=status,
        source_sha256=manifest["source_sha256"],
        proposal_sha256=manifest["proposal_sha256"],
        candidate_count=len(candidates),
        configured_step_count=len(configured),
        automatic_step_count=len(automatic),
        blocker_count=len(blockers),
    )


# --------------------------------------------------------------------------- #
# AUTHORIZE
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GovernedCleaningAuthorizeResult:
    output_dir: Path
    status: str
    source_sha256: str
    proposal_sha256: str
    application_plan_sha256: str
    authority_count: int
    step_count: int
    incomplete_count: int
    blocker_count: int


VALUE_CHANGING_CLASSES = frozenset({GovernanceClass.CONFIGURED_ONLY, GovernanceClass.GOVERNED})


def _load_proposal(proposal_dir: Path, blockers: list[dict[str, str]]) -> tuple[dict[str, Any], list[TransformationCandidate]]:
    manifest = read_yaml_mapping(proposal_dir / PROPOSAL_MANIFEST_NAME, "proposal_manifest", blockers)
    if not manifest:
        return {}, []
    if manifest.get("version") != PROPOSAL_VERSION:
        add_blocker(blockers, "unsupported_proposal_version", f"Proposal must use version {PROPOSAL_VERSION}.", field="proposal_manifest.version")
        return {}, []
    if manifest.get("engine_version") != ENGINE_VERSION:
        add_blocker(blockers, "unsupported_engine_version", f"Proposal was produced by engine version {manifest.get('engine_version')!r}; this engine is version {ENGINE_VERSION}.", field="proposal_manifest.engine_version")
        return {}, []
    if manifest.get("status") != "ready_for_review":
        add_blocker(blockers, "proposal_not_ready", f"Proposal status is {manifest.get('status')!r}, not ready_for_review.", field="proposal_manifest.status")
        return {}, []
    if _proposal_hash(manifest) != manifest.get("proposal_sha256"):
        add_blocker(blockers, "proposal_hash_mismatch", "proposal_manifest changed after it was published.", field="proposal_manifest.proposal_sha256")
        return {}, []
    candidates_doc = read_yaml_mapping(proposal_dir / CANDIDATES_NAME, "candidates", blockers)
    if not candidates_doc:
        return {}, []
    if candidates_doc.get("proposal_sha256") != manifest["proposal_sha256"]:
        add_blocker(blockers, "proposal_hash_mismatch", "candidates.yml is bound to a different proposal.", field="candidates.proposal_sha256")
        return {}, []
    records = candidates_doc.get("candidates")
    if not isinstance(records, list):
        add_blocker(blockers, "invalid_candidate_record", "candidates.yml must list candidates.", field="candidates.candidates")
        return {}, []
    candidates: list[TransformationCandidate] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            add_blocker(blockers, "invalid_candidate_record", "Candidate record must be a mapping.", field=f"candidates[{index}]")
            continue
        candidate = _candidate_from_record(record, blockers, f"candidates[{index}]")
        if candidate is not None:
            candidates.append(candidate)
    declared = {(g.get("candidate_id"), g.get("candidate_sha256")) for g in manifest.get("governed", []) if isinstance(g, dict)}
    actual = {(c.candidate_id, candidate_hash(c)) for c in candidates}
    if declared != actual:
        add_blocker(blockers, "proposal_hash_mismatch", "candidates.yml does not match the governed list in proposal_manifest.", field="candidates")
        return {}, []
    return manifest, candidates


def _load_review(
    review_path: Path | None,
    candidates: list[TransformationCandidate],
    expected_proposal_sha256: str,
    blockers: list[dict[str, str]],
) -> dict[str, TransformationDecision]:
    """Return decisions keyed by candidate_id. Malformed, duplicate, or unknown
    decisions are blockers; a missing decision is not (it is incompleteness).
    The review must name the exact proposal artifact being authorized: two
    proposals over unchanged data can carry identical candidate hashes and
    still be different artifacts, and the human reviewed one of them."""
    decisions: dict[str, TransformationDecision] = {}
    if review_path is None:
        return decisions
    review = read_yaml_mapping(review_path, "review", blockers)
    if not review:
        return decisions
    if review.get("version") != AUTHORIZATION_VERSION:
        add_blocker(blockers, "unsupported_review_version", f"Review must use version {AUTHORIZATION_VERSION}.", field="review.version")
        return decisions
    if str(review.get("proposal_sha256") or "") != expected_proposal_sha256:
        add_blocker(blockers, "review_proposal_hash_mismatch", "The review is bound to a different proposal artifact than the one being authorized.", field="review.proposal_sha256")
        return decisions
    default_reviewer = str(review.get("reviewer") or "")
    entries = review.get("decisions")
    if not isinstance(entries, list):
        add_blocker(blockers, "invalid_review_file", "review must list decisions.", field="review.decisions")
        return decisions
    by_id = {c.candidate_id: c for c in candidates}
    for index, entry in enumerate(entries):
        field = f"review.decisions[{index}]"
        if not isinstance(entry, dict):
            add_blocker(blockers, "invalid_review_file", "Decision entry must be a mapping.", field=field)
            continue
        cid = str(entry.get("candidate_id") or "")
        if cid not in by_id:
            add_blocker(blockers, "unknown_review_candidate", f"Decision names candidate {cid!r}, which the proposal does not contain.", field=f"{field}.candidate_id")
            continue
        if cid in decisions:
            add_blocker(blockers, "duplicate_review_decision", f"Candidate {cid} has more than one decision.", field=f"{field}.candidate_id")
            continue
        raw_kind = str(entry.get("decision") or "").strip()
        if not raw_kind:
            # An empty decision is "not decided yet", not a malformed record.
            continue
        try:
            kind = DecisionKind(raw_kind)
        except ValueError:
            add_blocker(blockers, "invalid_review_decision", f"Decision {raw_kind!r} is not approved, rejected, or modified.", field=f"{field}.decision")
            continue
        modified = entry.get("modified_parameters")
        decisions[cid] = TransformationDecision(
            candidate_id=cid,
            candidate_sha256=str(entry.get("candidate_sha256") or ""),
            decision=kind,
            reviewer=str(entry.get("reviewer") or default_reviewer),
            reviewed_at=str(entry.get("reviewed_at") or ""),
            modified_parameters=dict(modified) if isinstance(modified, dict) else None,
            note=str(entry.get("note") or ""),
        )
    return decisions


def _load_policy(policy_path: Path | None, blockers: list[dict[str, str]]) -> CleaningPolicy | None:
    if policy_path is None:
        return None
    raw = read_yaml_mapping(policy_path, "cleaning_policy", blockers)
    if not raw:
        return None
    entries = raw.get("operations")
    if not isinstance(entries, list):
        add_blocker(blockers, "invalid_policy_file", "cleaning_policy must list operations.", field="cleaning_policy.operations")
        return None
    operations: list[PolicyOperation] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            add_blocker(blockers, "invalid_policy_file", "Policy operation must be a mapping.", field=f"cleaning_policy.operations[{index}]")
            return None
        try:
            operation = TransformationOperation(str(entry.get("operation")))
        except ValueError:
            add_blocker(blockers, "unknown_transformation_operation", f"Operation {entry.get('operation')!r} is not in the governed operation table.", field=f"cleaning_policy.operations[{index}].operation")
            return None
        columns = entry.get("columns")
        if not isinstance(columns, list):
            add_blocker(blockers, "invalid_policy_file", "Policy operation must list columns.", field=f"cleaning_policy.operations[{index}].columns")
            return None
        params = entry.get("parameters") or {}
        operations.append(PolicyOperation(operation, str(entry.get("table") or ""), tuple(str(c) for c in columns), dict(params) if isinstance(params, dict) else {}))
    try:
        version = int(raw.get("policy_version", 0))
    except (TypeError, ValueError):
        version = 0
    return CleaningPolicy(
        dataset_id=str(raw.get("dataset_id") or ""),
        configured_by=str(raw.get("configured_by") or ""),
        configured_at=str(raw.get("configured_at") or ""),
        operations=tuple(operations),
        policy_version=version,
    )


def _authority_record(auth: ApprovedTransformation | ConfiguredAuthority | AutomaticAuthority) -> dict[str, Any]:
    record: dict[str, Any] = {
        "authority_kind": auth.authority_kind.value,
        "authority_sha256": auth.authority_sha256,
        "source_sha256": auth.source_sha256,
        "table": auth.table,
        "column": auth.column,
        "operation": auth.operation.value,
    }
    if isinstance(auth, ApprovedTransformation):
        record.update({"candidate_id": auth.candidate_id, "candidate_sha256": auth.candidate_sha256, "decision_sha256": auth.decision_sha256, "effective_parameters": dict(auth.effective_parameters)})
    elif isinstance(auth, ConfiguredAuthority):
        record.update({"policy_sha256": auth.policy_sha256, "dataset_id": auth.dataset_id, "effective_parameters": dict(auth.effective_parameters)})
    return record


def _authority_from_record(record: Mapping[str, Any], blockers: list[dict[str, str]], field: str):
    try:
        kind = record["authority_kind"]
        operation = TransformationOperation(str(record["operation"]))
        common = dict(source_sha256=str(record["source_sha256"]), table=str(record["table"]), column=str(record["column"]), operation=operation, authority_sha256=str(record["authority_sha256"]))
        if kind == "human_decision":
            return ApprovedTransformation(candidate_id=str(record["candidate_id"]), candidate_sha256=str(record["candidate_sha256"]), decision_sha256=str(record["decision_sha256"]), effective_parameters=dict(record.get("effective_parameters") or {}), **common)
        if kind == "cleaning_policy":
            return ConfiguredAuthority(policy_sha256=str(record["policy_sha256"]), dataset_id=str(record["dataset_id"]), effective_parameters=dict(record.get("effective_parameters") or {}), **common)
        if kind == "operation_table":
            return AutomaticAuthority(**common)
    except (KeyError, TypeError, ValueError):
        pass
    add_blocker(blockers, "invalid_authority_record", "Authority record is malformed or names an unknown authority kind.", field=field)
    return None


def _plan_hash(source_sha256: str, ordered_authority_hashes: list[str]) -> str:
    return sha256_of({"version": APPLICATION_PLAN_VERSION, "source_sha256": source_sha256, "steps": ordered_authority_hashes})


def _order_steps(authorities: list) -> list:
    """Canonical order: value-changing operations first by (table, column,
    operation); column renames last, so every value step is addressed by the
    source column name it was authorized for."""
    def key(auth):
        renames_last = 1 if auth.operation is TransformationOperation.NORMALIZE_COLUMN_NAME else 0
        return (renames_last, auth.table, auth.column, auth.operation.value)
    return sorted(authorities, key=key)


def _check_composition(authorities: list, blockers: list[dict[str, str]], table_columns: Mapping[str, list[str]] | None = None) -> None:
    """Engine v1: at most one value-changing operation per (table, column), and
    no two renames in one table may collapse to the same target, nor may a
    rename target collide with an existing column that is not being renamed."""
    seen: dict[tuple[str, str], str] = {}
    targets: dict[str, dict[str, str]] = {}
    renamed_sources: dict[str, set[str]] = {}
    for auth in authorities:
        if auth.operation is TransformationOperation.NORMALIZE_COLUMN_NAME:
            target = slugify(auth.column)
            table_targets = targets.setdefault(auth.table, {})
            if target in table_targets:
                add_blocker(blockers, "rename_target_collision", f"{auth.table}: both {table_targets[target]!r} and {auth.column!r} normalize to {target!r}.", field="application_plan")
            table_targets[target] = auth.column
            renamed_sources.setdefault(auth.table, set()).add(auth.column)
            continue
        if governance_class_for(auth.operation) not in VALUE_CHANGING_CLASSES:
            continue
        key = (auth.table, auth.column)
        if key in seen:
            add_blocker(blockers, "unsupported_operation_composition", f"{auth.table}.{auth.column} has more than one value-changing operation ({seen[key]} and {auth.operation.value}); engine v1 supports one per column.", field="application_plan")
        seen[key] = auth.operation.value
    if table_columns:
        for table, table_targets in targets.items():
            existing = set(table_columns.get(table, [])) - renamed_sources.get(table, set())
            for target, source in table_targets.items():
                if target in existing:
                    add_blocker(blockers, "rename_target_collision", f"{table}: renaming {source!r} to {target!r} would collide with an existing column.", field="application_plan")


def run_governed_cleaning_authorize(
    proposal_dir: Path,
    parquet_dir: Path,
    output_dir: Path,
    *,
    review_path: Path | None = None,
    policy_path: Path | None = None,
) -> GovernedCleaningAuthorizeResult:
    blockers: list[dict[str, str]] = []
    if output_dir.exists():
        add_blocker(blockers, "output_directory_exists", "Output directory already exists; authorizations are published to a new directory only.", field="output_dir")
        return GovernedCleaningAuthorizeResult(output_dir, "blocked", "", "", "", 0, 0, 0, len(blockers))

    manifest, candidates = _load_proposal(proposal_dir, blockers)
    inventory = verify_source(parquet_dir, None, blockers)
    source_sha256 = manifest.get("source_sha256", "") if manifest else ""
    if inventory is not None and manifest and inventory.source_sha256 != source_sha256:
        add_blocker(blockers, "source_changed_since_proposal", "The Parquet source no longer matches the hash the proposal was built against.", field="source_sha256")
    decisions = _load_review(review_path, candidates, str(manifest.get("proposal_sha256") or "") if manifest else "", blockers)
    policy = _load_policy(policy_path, blockers)

    authorities: list = []
    dispositions: list[dict[str, Any]] = []
    incomplete = 0
    if not blockers:
        for candidate in candidates:
            decision = decisions.get(candidate.candidate_id)
            if decision is None:
                incomplete += 1
                dispositions.append({"candidate_id": candidate.candidate_id, "candidate_sha256": candidate_hash(candidate), "governance_class": "governed", "disposition": "missing", "authority_sha256": ""})
                continue
            recorded = record_decision(candidate, decision, blockers)
            if recorded is None:
                continue
            if recorded.review_state is ReviewState.REJECTED:
                dispositions.append({"candidate_id": candidate.candidate_id, "candidate_sha256": candidate_hash(candidate), "governance_class": "governed", "disposition": "rejected", "authority_sha256": ""})
                continue
            auth = authorize_application(recorded, decision, source_sha256, blockers)
            if auth is None:
                continue
            authorities.append(auth)
            dispositions.append({"candidate_id": candidate.candidate_id, "candidate_sha256": candidate_hash(candidate), "governance_class": "governed", "disposition": decision.decision.value, "authority_sha256": auth.authority_sha256})
        for step in manifest.get("configured", []) if manifest else []:
            try:
                operation = TransformationOperation(str(step.get("operation")))
            except ValueError:
                add_blocker(blockers, "unknown_transformation_operation", f"Proposal configured step names unknown operation {step.get('operation')!r}.", field="proposal_manifest.configured")
                continue
            table, column = str(step.get("table") or ""), str(step.get("column") or "")
            if policy is None:
                dispositions.append({"governance_class": "configured_only", "operation": operation.value, "table": table, "column": column, "disposition": "no_policy", "authority_sha256": ""})
                continue
            probe: list[dict[str, str]] = []
            auth = authorize_configured(policy, source_sha256=source_sha256, operation=operation, table=table, column=column, blockers=probe)
            if auth is None:
                kinds = {b["blocker_type"] for b in probe}
                if kinds == {"operation_not_configured"}:
                    dispositions.append({"governance_class": "configured_only", "operation": operation.value, "table": table, "column": column, "disposition": "not_configured", "authority_sha256": ""})
                    continue
                blockers.extend(probe)
                continue
            authorities.append(auth)
            dispositions.append({"governance_class": "configured_only", "operation": operation.value, "table": table, "column": column, "disposition": "configured", "authority_sha256": auth.authority_sha256, "policy_sha256": auth.policy_sha256})
        for step in manifest.get("automatic", []) if manifest else []:
            try:
                operation = TransformationOperation(str(step.get("operation")))
            except ValueError:
                add_blocker(blockers, "unknown_transformation_operation", f"Proposal automatic step names unknown operation {step.get('operation')!r}.", field="proposal_manifest.automatic")
                continue
            auth = build_automatic_authority(source_sha256=source_sha256, table=str(step.get("table") or ""), column=str(step.get("column") or ""), operation=operation, blockers=blockers)
            if auth is None:
                continue
            authorities.append(auth)
            dispositions.append({"governance_class": "safe_automatic", "operation": operation.value, "table": auth.table, "column": auth.column, "disposition": "automatic", "authority_sha256": auth.authority_sha256})
        table_columns = {str(tbl.get("table")): list(tbl.get("columns") or []) for tbl in manifest.get("tables", []) if isinstance(tbl, dict)}
        _check_composition(authorities, blockers, table_columns)

    if blockers:
        status = "blocked"
        ordered = []
    else:
        ordered = _order_steps(authorities)
        status = "authorization_incomplete" if incomplete else "authorized"

    plan_hashes = [a.authority_sha256 for a in ordered]
    plan_sha256 = _plan_hash(source_sha256, plan_hashes) if status == "authorized" else ""
    plan_doc = {
        "version": APPLICATION_PLAN_VERSION,
        "source_sha256": source_sha256,
        # The plan is authoritative only over order. Every other fact about a
        # step is read from the self-bound authority record it references, so
        # there is no redundant metadata that could disagree with it.
        "steps": [
            {"sequence": i + 1, "authority_sha256": a.authority_sha256}
            for i, a in enumerate(ordered)
        ] if status == "authorized" else [],
        "application_plan_sha256": plan_sha256,
    }
    authorities_doc = {
        "version": AUTHORIZATION_VERSION,
        "source_sha256": source_sha256,
        "authorities": [_authority_record(a) for a in ordered] if status == "authorized" else [],
    }
    authorities_sha256 = sha256_of(authorities_doc["authorities"]) if status == "authorized" else ""
    auth_manifest = {
        "version": AUTHORIZATION_VERSION,
        "engine_version": ENGINE_VERSION,
        "status": status,
        "authorized_at": utc_now(),
        "proposal_sha256": manifest.get("proposal_sha256", "") if manifest else "",
        "source_sha256": source_sha256,
        "policy_sha256": (sha256_of(policy) if policy is not None and status != "blocked" else ""),
        "authorities_sha256": authorities_sha256,
        "application_plan_sha256": plan_sha256,
        "dispositions": dispositions if status != "blocked" else [],
        "authority_count": len(ordered),
        "incomplete_count": incomplete,
        "blocker_count": len(blockers),
    }
    report = "\n".join([
        "# Governed Cleaning Authorization", "",
        f"- Status: {status}", f"- Source SHA-256: {source_sha256}", f"- Proposal SHA-256: {auth_manifest['proposal_sha256']}",
        f"- Application plan SHA-256: {plan_sha256 or '(none)'}", f"- Authorities: {len(ordered)}",
        f"- Governed candidates without disposition: {incomplete}", f"- Blockers: {len(blockers)}", "",
        "No value was changed. Every governed candidate needs an explicit disposition before an",
        "apply-ready plan exists; approved is derived from decisions and never stored on its own.", "",
    ])
    _publish_bundle(output_dir, {
        AUTHORITIES_NAME: canonical_yaml(authorities_doc),
        APPLICATION_PLAN_NAME: canonical_yaml(plan_doc),
        AUTHORIZATION_MANIFEST_NAME: canonical_yaml(auth_manifest),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: report,
    })
    return GovernedCleaningAuthorizeResult(output_dir, status, source_sha256, auth_manifest["proposal_sha256"], plan_sha256, len(ordered), len(plan_doc["steps"]), incomplete, len(blockers))


# --------------------------------------------------------------------------- #
# APPLY
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GovernedCleaningApplyResult:
    output_dir: Path
    status: str
    source_sha256: str
    application_plan_sha256: str
    step_count: int
    tables_written: int
    blocker_count: int


def _apply_trim(series: pd.Series) -> tuple[pd.Series, int]:
    out = series.map(lambda v: v.strip() if isinstance(v, str) else v)
    changed = int((out.astype(object) != series.astype(object)).fillna(False).sum()) if len(series) else 0
    return out, changed


def _apply_blank_sentinel(series: pd.Series, sentinels: list[str]) -> tuple[pd.Series, int]:
    sentinel_set = set(sentinels)
    mask = series.map(lambda v: isinstance(v, str) and v in sentinel_set)
    changed = int(mask.sum())
    out = series.mask(mask, pd.NA)
    return out, changed


def _apply_parse_number(series: pd.Series, thousands: str, decimal: str) -> tuple[pd.Series, int, int]:
    def convert(v: Any) -> Any:
        if not isinstance(v, str):
            return v
        s = v.strip()
        if thousands:
            s = s.replace(thousands, "")
        if decimal and decimal != ".":
            s = s.replace(decimal, ".")
        return s
    prepared = series.map(convert)
    out = pd.to_numeric(prepared, errors="coerce")
    non_null_in = int(series.notna().sum())
    failed = int((series.notna() & out.isna()).sum())
    if out.notna().all() and (out.dropna() == out.dropna().round()).all():
        try:
            out = out.astype("Int64")
        except (TypeError, ValueError):
            pass
    else:
        try:
            out = out.astype("Int64") if (out.dropna() == out.dropna().round()).all() else out
        except (TypeError, ValueError):
            pass
    return out, non_null_in, failed


def _apply_parse_date(series: pd.Series, fmt: str) -> tuple[pd.Series, int, int]:
    text = series.map(lambda v: v.strip() if isinstance(v, str) else v)
    parsed = pd.to_datetime(text, format=fmt, errors="coerce")
    non_null_in = int(series.notna().sum())
    failed = int((series.notna() & parsed.isna()).sum())
    return parsed.dt.date.astype(object), non_null_in, failed


def _load_authorization(authority_dir: Path, blockers: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any], list]:
    manifest = read_yaml_mapping(authority_dir / AUTHORIZATION_MANIFEST_NAME, "authorization_manifest", blockers)
    if not manifest:
        return {}, {}, []
    if manifest.get("version") != AUTHORIZATION_VERSION:
        add_blocker(blockers, "unsupported_authorization_version", f"Authorization must use version {AUTHORIZATION_VERSION}.", field="authorization_manifest.version")
        return {}, {}, []
    if manifest.get("engine_version") != ENGINE_VERSION:
        add_blocker(blockers, "unsupported_engine_version", f"Authorization was produced by engine version {manifest.get('engine_version')!r}; this engine is version {ENGINE_VERSION}.", field="authorization_manifest.engine_version")
        return {}, {}, []
    if manifest.get("status") != "authorized":
        add_blocker(blockers, "authorization_not_ready", f"Authorization status is {manifest.get('status')!r}, not authorized; nothing may be applied.", field="authorization_manifest.status")
        return {}, {}, []
    authorities_doc = read_yaml_mapping(authority_dir / AUTHORITIES_NAME, "authorities", blockers)
    plan = read_yaml_mapping(authority_dir / APPLICATION_PLAN_NAME, "application_plan", blockers)
    if not authorities_doc or not plan:
        return {}, {}, []
    records = authorities_doc.get("authorities")
    if not isinstance(records, list):
        add_blocker(blockers, "invalid_authority_record", "authorities.yml must list authorities.", field="authorities.authorities")
        return {}, {}, []
    if sha256_of(records) != manifest.get("authorities_sha256"):
        add_blocker(blockers, "authority_bundle_hash_mismatch", "authorities.yml changed after authorization.", field="authorities")
        return {}, {}, []
    steps = plan.get("steps")
    if not isinstance(steps, list) or plan.get("version") != APPLICATION_PLAN_VERSION:
        add_blocker(blockers, "invalid_application_plan", "application_plan.yml must be version 1 and list steps.", field="application_plan")
        return {}, {}, []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) != {"sequence", "authority_sha256"}:
            add_blocker(blockers, "invalid_application_plan", f"application_plan step {index + 1} must carry exactly sequence and authority_sha256; step semantics come from the referenced authority record.", field=f"application_plan.steps[{index}]")
            return {}, {}, []
    step_hashes = [str(s.get("authority_sha256") or "") for s in steps if isinstance(s, dict)]
    recomputed = _plan_hash(str(plan.get("source_sha256") or ""), step_hashes)
    if recomputed != plan.get("application_plan_sha256") or recomputed != manifest.get("application_plan_sha256"):
        add_blocker(blockers, "application_plan_hash_mismatch", "application_plan.yml does not match its own hash or the authorization manifest; the plan changed or was reordered after authorization.", field="application_plan.application_plan_sha256")
        return {}, {}, []
    if plan.get("source_sha256") != manifest.get("source_sha256"):
        add_blocker(blockers, "application_plan_hash_mismatch", "application_plan.yml is bound to a different source than the authorization.", field="application_plan.source_sha256")
        return {}, {}, []
    authorities = []
    for index, record in enumerate(records):
        auth = _authority_from_record(record, blockers, f"authorities[{index}]")
        if auth is not None:
            authorities.append(auth)
    if len(authorities) != len(records):
        return {}, {}, []
    return manifest, plan, authorities


def run_governed_cleaning_apply(
    authority_dir: Path,
    parquet_dir: Path,
    output_dir: Path,
) -> GovernedCleaningApplyResult:
    blockers: list[dict[str, str]] = []
    if output_dir.exists():
        add_blocker(blockers, "output_directory_exists", "Output directory already exists; applications are published to a new directory only.", field="output_dir")
        return GovernedCleaningApplyResult(output_dir, "blocked", "", "", 0, 0, len(blockers))

    manifest, plan, authorities = _load_authorization(authority_dir, blockers)
    inventory = verify_source(parquet_dir, None, blockers)
    source_sha256 = str(manifest.get("source_sha256") or "") if manifest else ""
    if inventory is not None and manifest and inventory.source_sha256 != source_sha256:
        add_blocker(blockers, "source_changed_since_authorization", "The Parquet source no longer matches the hash the authorities were granted against; nothing may be applied.", field="source_sha256")

    ordered: list = []
    if not blockers:
        by_hash = {a.authority_sha256: a for a in authorities}
        if len(by_hash) != len(authorities):
            add_blocker(blockers, "duplicate_authority_in_bundle", "authorities.yml contains the same authority_sha256 more than once.", field="authorities")
        seen: set[str] = set()
        for index, step in enumerate(plan.get("steps", [])):
            h = str(step.get("authority_sha256") or "")
            if h in seen:
                add_blocker(blockers, "duplicate_plan_step", f"application_plan step {index + 1} repeats authority {h[:12]}.", field=f"application_plan.steps[{index}]")
                continue
            seen.add(h)
            auth = by_hash.get(h)
            if auth is None:
                add_blocker(blockers, "unknown_plan_authority", f"application_plan step {index + 1} references an authority that is not in authorities.yml.", field=f"application_plan.steps[{index}]")
                continue
            if step.get("sequence") != index + 1:
                add_blocker(blockers, "invalid_application_plan", f"application_plan step sequence must be {index + 1}.", field=f"application_plan.steps[{index}].sequence")
            ordered.append(auth)
        # The plan is the exact executable projection of the complete
        # authorized bundle: every authority once, in canonical order. A plan
        # that omits, adds, repeats, or reorders authorities is refused even
        # if every referenced authority is genuine and every hash was rehashed.
        expected = [a.authority_sha256 for a in _order_steps(authorities)]
        actual = [str(s.get("authority_sha256") or "") for s in plan.get("steps", []) if isinstance(s, dict)]
        if actual != expected:
            add_blocker(blockers, "application_plan_authority_set_mismatch", "application_plan.yml is not the complete authorized authority set in canonical order; it omits, adds, repeats, or reorders authorities.", field="application_plan.steps")
        for auth in ordered:
            if isinstance(auth, ApprovedTransformation):
                verify_authority(auth, current_source_sha256=source_sha256, blockers=blockers)
            elif isinstance(auth, ConfiguredAuthority):
                verify_configured_authority(auth, current_source_sha256=source_sha256, blockers=blockers)
            else:
                verify_automatic_authority(auth, current_source_sha256=source_sha256, blockers=blockers)
            if auth.operation not in ENGINE_SUPPORTED_OPERATIONS:
                add_blocker(blockers, "operation_not_supported_by_engine", f"{auth.operation.value} is authorized by the contract but engine v1 does not implement it.", field="application_plan")
        _check_composition(ordered, blockers)
    if blockers:
        _publish_bundle(output_dir, {
            APPLICATION_MANIFEST_NAME: canonical_yaml({"version": APPLICATION_VERSION, "engine_version": ENGINE_VERSION, "status": "blocked", "applied_at": utc_now(), "source_sha256": source_sha256, "application_plan_sha256": "", "blocker_count": len(blockers), "tables": [], "steps": []}),
            LINEAGE_NAME: canonical_yaml({"version": APPLICATION_VERSION, "lineage": []}),
            BLOCKERS_NAME: blockers_csv(blockers),
            REPORT_NAME: "# Governed Cleaning Application\n\n- Status: blocked\n- Nothing was applied; see blockers.csv.\n",
        })
        return GovernedCleaningApplyResult(output_dir, "blocked", source_sha256, "", 0, 0, len(blockers))

    # ---- all preconditions passed: build the entire output in staging ----
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        (staging / PARQUET_DIR_NAME).mkdir()
        frames: dict[str, pd.DataFrame] = {}
        if inventory is None:  # pragma: no cover - blockers above already returned
            raise ValueError("Source inventory missing after precondition checks.")
        for entry in inventory.files:
            frames[Path(entry["path"]).stem] = pd.read_parquet(parquet_dir / entry["path"])
        applied_at = utc_now()
        step_metrics: list[dict[str, Any]] = []
        step_rows: list[dict[str, Any]] = []
        for index, auth in enumerate(ordered):
            frame = frames.get(auth.table)
            if frame is None or auth.column not in frame.columns:
                raise ValueError(f"Authorized scope {auth.table}.{auth.column} is not present in the source.")
            series = frame[auth.column]
            rows_examined = int(len(series))
            failed = 0
            if auth.operation is TransformationOperation.TRIM_WHITESPACE:
                out, changed = _apply_trim(series)
            elif auth.operation is TransformationOperation.NORMALIZE_BLANK_SENTINEL:
                sentinels = auth.effective_parameters.get("sentinels", [])
                if not isinstance(sentinels, list) or not all(isinstance(s, str) for s in sentinels):
                    raise ValueError("normalize_blank_sentinel requires parameters.sentinels as a list of strings.")
                out, changed = _apply_blank_sentinel(series, sentinels)
            elif auth.operation is TransformationOperation.PARSE_NUMBER:
                out, non_null_in, failed = _apply_parse_number(series, str(auth.effective_parameters.get("thousands", "")), str(auth.effective_parameters.get("decimal", ".")))
                changed = non_null_in
            elif auth.operation is TransformationOperation.PARSE_DATE:
                fmt = auth.effective_parameters.get("format")
                if not isinstance(fmt, str) or not fmt:
                    raise ValueError("parse_date requires parameters.format.")
                out, non_null_in, failed = _apply_parse_date(series, fmt)
                changed = non_null_in
            elif auth.operation is TransformationOperation.NORMALIZE_COLUMN_NAME:
                target = slugify(auth.column)
                if target in frame.columns and target != auth.column:
                    raise ValueError(f"Renaming {auth.column} to {target} would collide with an existing column.")
                frames[auth.table] = frame.rename(columns={auth.column: target})
                out, changed = None, 0
            else:  # pragma: no cover - guarded by ENGINE_SUPPORTED_OPERATIONS
                raise ValueError(f"Unsupported operation {auth.operation.value}.")
            if out is not None:
                frame = frame.copy()
                frame[auth.column] = out
                frames[auth.table] = frame
            step_metrics.append({"authority": auth, "rows_examined": rows_examined, "rows_changed": changed, "values_failed": failed})
            step_rows.append({"sequence": index + 1, "authority_sha256": auth.authority_sha256, "operation": auth.operation.value, "table": auth.table, "column": auth.column})
        tables_out: list[dict[str, Any]] = []
        for table, frame in sorted(frames.items()):
            path = staging / PARQUET_DIR_NAME / f"{table}.parquet"
            frame.to_parquet(path, index=False)
            tables_out.append({"table": table, "path": f"{PARQUET_DIR_NAME}/{table}.parquet", "rows": int(len(frame)), "columns": [str(c) for c in frame.columns], "physical_sha256": file_sha256(path), "logical_content_sha256": logical_content_sha256(frame)})
        by_table = {t["table"]: t for t in tables_out}
        # Lineage is the D1 TransformationLineage built with the real output
        # hash, serialized as-is; D2 adds its own evidence beside it. The
        # contract output_sha256 is the logical content hash, which is what
        # the engine promises to be deterministic; the physical Parquet hash
        # is recorded as D2 metadata.
        lineage_rows: list[dict[str, Any]] = []
        for index, metric in enumerate(step_metrics):
            auth = metric["authority"]
            lineage = build_lineage(
                auth,
                output_sha256=by_table[auth.table]["logical_content_sha256"],
                rows_examined=metric["rows_examined"],
                rows_changed=metric["rows_changed"],
                applied_at=applied_at,
                blockers=blockers,
            )
            if lineage is None:
                raise ValueError("Lineage could not be built for an authorized step.")
            record = {k: (v.value if hasattr(v, "value") else v) for k, v in asdict(lineage).items()}
            record["sequence"] = index + 1
            record["values_failed"] = metric["values_failed"]
            record["output_physical_sha256"] = by_table[auth.table]["physical_sha256"]
            lineage_rows.append(record)
        app_manifest = {
            "version": APPLICATION_VERSION,
            "engine_version": ENGINE_VERSION,
            "status": "applied",
            "applied_at": applied_at,
            "source_sha256": source_sha256,
            "proposal_sha256": manifest.get("proposal_sha256", ""),
            "authorities_sha256": manifest.get("authorities_sha256", ""),
            "application_plan_sha256": manifest.get("application_plan_sha256", ""),
            "logical_dataset_sha256": sha256_of([{"table": t["table"], "logical_content_sha256": t["logical_content_sha256"]} for t in tables_out]),
            "tables": tables_out,
            "steps": step_rows,
            "blocker_count": 0,
        }
        (staging / APPLICATION_MANIFEST_NAME).write_text(canonical_yaml(app_manifest), encoding="utf-8", newline="")
        (staging / LINEAGE_NAME).write_text(canonical_yaml({"version": APPLICATION_VERSION, "source_sha256": source_sha256, "application_plan_sha256": app_manifest["application_plan_sha256"], "lineage": lineage_rows}), encoding="utf-8", newline="")
        (staging / BLOCKERS_NAME).write_text(blockers_csv([]), encoding="utf-8", newline="")
        (staging / REPORT_NAME).write_text("\n".join([
            "# Governed Cleaning Application", "", "- Status: applied", f"- Source SHA-256: {source_sha256}",
            f"- Application plan SHA-256: {app_manifest['application_plan_sha256']}", f"- Logical dataset SHA-256: {app_manifest['logical_dataset_sha256']}",
            f"- Steps applied: {len(step_rows)}", f"- Tables written: {len(tables_out)}", "",
            "Every step was re-verified against the current source immediately before application.",
            "Physical Parquet hashes depend on the writer version; logical content hashes do not.", "",
        ]), encoding="utf-8", newline="")
        # final self-check of the staging bundle before promotion
        for t in tables_out:
            if file_sha256(staging / t["path"]) != t["physical_sha256"]:
                raise ValueError("Staged Parquet changed before publication.")
        publish_new_directory(staging, output_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return GovernedCleaningApplyResult(output_dir, "applied", source_sha256, str(manifest.get("application_plan_sha256") or ""), len(ordered), len(tables_out), 0)
