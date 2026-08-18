"""Governed cleaning contract: candidates, evidence, decisions, policy, lineage.

This module defines the typed contract for governed data cleaning and the pure
functions that decide authority. It performs no I/O and touches no DataFrame.
The engine that proposes candidates from real data and applies authorized
transformations is a later, separate increment; nothing here can alter a value.

Authority split, matching the analytics side of the project:

    heuristic or model proposes an operation
    deterministic code measures the evidence
    deterministic code computes the confidence from that evidence
    a human decision, or a dataset-scoped policy, grants or refuses authority
    deterministic code applies only what was granted, and records lineage

Three sources of authority, one per governance class:

    safe_automatic   the operation table itself (structural, name-level only)
    configured_only  an exact, hash-bound dataset cleaning policy
    governed         an exact, hash-bound human decision on a candidate

States move only forward and never skip review:

    candidate -> pending_review -> approved -> applied
                                -> rejected

`candidate -> applied` does not exist, and authority to apply a governed
operation exists only for a candidate in the `approved` state. That state is a
projection of a hash-bound decision record; the decision is the authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .contracts.blockers import add_blocker


CONTRACT_VERSION = 1
CONFIDENCE_FORMULA_VERSION = 1
CONFIDENCE_PRECISION = 4
POLICY_VERSION = 1

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
CANDIDATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

# A raw source column name that normalize_column_name may act on. It is not an
# identifier yet - that is the point of the operation - but it is bounded: 1 to
# 255 characters, no control characters, and at least one letter or digit so a
# deterministic identifier can be derived from it. This exception exists for
# NORMALIZE_COLUMN_NAME only; every other operation scopes authority by
# IDENTIFIER_PATTERN.
RAW_COLUMN_NAME_MAX_LENGTH = 255
RAW_COLUMN_NAME_PATTERN = re.compile(r"^(?=.*[A-Za-z0-9])[^\x00-\x1f\x7f]{1,255}$")

def is_valid_raw_column_name(value: Any) -> bool:
    return isinstance(value, str) and RAW_COLUMN_NAME_PATTERN.fullmatch(value) is not None


class GovernanceClass(str, Enum):
    """How much authority a transformation needs before it may run.

    SAFE_AUTOMATIC   - structural and name-level only; never changes a cell
                       value; may run without review.
    CONFIGURED_ONLY  - changes cell values in a bounded, reversible way; runs
                       only under an exact, hash-bound dataset cleaning policy;
                       never by default.
    GOVERNED         - semantic coercion; always a candidate; requires an
                       approved decision bound to the exact candidate hash.
    """

    SAFE_AUTOMATIC = "safe_automatic"
    CONFIGURED_ONLY = "configured_only"
    GOVERNED = "governed"


class TransformationOperation(str, Enum):
    NORMALIZE_COLUMN_NAME = "normalize_column_name"
    TRIM_WHITESPACE = "trim_whitespace"
    NORMALIZE_BLANK_SENTINEL = "normalize_blank_sentinel"
    PARSE_NUMBER = "parse_number"
    PARSE_DATE = "parse_date"
    INTERPRET_DECIMAL_SEPARATOR = "interpret_decimal_separator"
    INTERPRET_LOCALE = "interpret_locale"
    CANONICALIZE_IDENTIFIER = "canonicalize_identifier"
    REMAP_CATEGORY = "remap_category"


# Which class each operation belongs to. This table is authority: an operation
# absent from it is unknown and is rejected before it can carry any state.
# trim_whitespace is not value-preserving (" ABC " -> "ABC" can collapse codes
# that differ only by padding), so it is configured, not automatic.
OPERATION_GOVERNANCE: Mapping[TransformationOperation, GovernanceClass] = {
    TransformationOperation.NORMALIZE_COLUMN_NAME: GovernanceClass.SAFE_AUTOMATIC,
    TransformationOperation.TRIM_WHITESPACE: GovernanceClass.CONFIGURED_ONLY,
    TransformationOperation.NORMALIZE_BLANK_SENTINEL: GovernanceClass.CONFIGURED_ONLY,
    TransformationOperation.PARSE_NUMBER: GovernanceClass.GOVERNED,
    TransformationOperation.PARSE_DATE: GovernanceClass.GOVERNED,
    TransformationOperation.INTERPRET_DECIMAL_SEPARATOR: GovernanceClass.GOVERNED,
    TransformationOperation.INTERPRET_LOCALE: GovernanceClass.GOVERNED,
    TransformationOperation.CANONICALIZE_IDENTIFIER: GovernanceClass.GOVERNED,
    TransformationOperation.REMAP_CATEGORY: GovernanceClass.GOVERNED,
}


class ReviewState(str, Enum):
    CANDIDATE = "candidate"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


# The only legal transitions. Everything else, including any path that reaches
# APPLIED without passing through APPROVED, is a contract violation.
ALLOWED_TRANSITIONS: Mapping[ReviewState, frozenset[ReviewState]] = {
    ReviewState.CANDIDATE: frozenset({ReviewState.PENDING_REVIEW}),
    ReviewState.PENDING_REVIEW: frozenset({ReviewState.APPROVED, ReviewState.REJECTED}),
    ReviewState.APPROVED: frozenset({ReviewState.APPLIED}),
    ReviewState.REJECTED: frozenset(),
    ReviewState.APPLIED: frozenset(),
}


class DecisionKind(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class AuthorityKind(str, Enum):
    """Which mechanism granted the authority a lineage record points to."""

    OPERATION_TABLE = "operation_table"
    CLEANING_POLICY = "cleaning_policy"
    HUMAN_DECISION = "human_decision"


# --------------------------------------------------------------------------- #
# Canonical hash domain
# --------------------------------------------------------------------------- #


class NonCanonicalPayloadError(ValueError):
    """A hash payload contains a value outside the canonical JSON domain."""


def _canonical(value: Any, path: str = "$") -> Any:
    """Reduce a payload to canonical JSON, or raise.

    Domain: None, bool, int, finite float, str, list/tuple (as list), and
    mappings with str keys. Enums reduce to their value and dataclasses to
    their field mapping because both are contract-owned and deterministic.
    Sets are rejected: their iteration order is not process-stable, so a hash
    over them would not be canonical. Non-finite floats are rejected because
    JSON has no representation for them.
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise NonCanonicalPayloadError(f"{path}: non-finite float is outside the canonical domain")
        return value
    if isinstance(value, Enum):
        return _canonical(value.value, path)
    if hasattr(value, "__dataclass_fields__"):
        return _canonical(asdict(value), path)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise NonCanonicalPayloadError(f"{path}: mapping key {key!r} is not a string")
            out[key] = _canonical(item, f"{path}.{key}")
        return out
    if isinstance(value, (list, tuple)):
        return [_canonical(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise NonCanonicalPayloadError(f"{path}: {type(value).__name__} is outside the canonical domain")


def canonical_json(payload: Any) -> str:
    """Stable serialization for hashing: sorted keys, no whitespace, ASCII,
    no NaN/Infinity. Raises NonCanonicalPayloadError outside the domain."""
    return json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_of(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def is_canonical_payload(payload: Any) -> bool:
    try:
        _canonical(payload)
    except NonCanonicalPayloadError:
        return False
    return True


def _check_canonical(payload: Any, *, field_name: str, blockers: list[dict[str, str]]) -> bool:
    try:
        _canonical(payload)
    except NonCanonicalPayloadError as error:
        add_blocker(blockers, "non_canonical_payload", f"{field_name} is outside the canonical hash domain: {error}", field=field_name)
        return False
    return True


def is_aware_iso_timestamp(value: Any) -> bool:
    """ISO-8601 with an explicit offset. Mirrors the semantic-approval rule so
    every audit timestamp in the project is unambiguous."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TransformationEvidence:
    """Deterministic measurements over the values a candidate would touch.

    Every field is a count or a ratio the engine can recompute from the same
    source. None of them is an opinion.
    """

    values_examined: int
    non_null_count: int
    candidate_count: int
    success_count: int
    failure_count: int
    ambiguous_count: int
    metrics: Mapping[str, float] = field(default_factory=dict)

    @property
    def success_ratio(self) -> float:
        if self.candidate_count <= 0:
            return 0.0
        return self.success_count / self.candidate_count

    @property
    def ambiguity_ratio(self) -> float:
        if self.candidate_count <= 0:
            return 0.0
        return self.ambiguous_count / self.candidate_count


@dataclass(frozen=True)
class TransformationCandidate:
    candidate_id: str
    source_sha256: str
    table: str
    column: str
    operation: TransformationOperation
    parameters: Mapping[str, Any]
    evidence: TransformationEvidence
    computed_confidence: float
    review_state: ReviewState = ReviewState.CANDIDATE
    contract_version: int = CONTRACT_VERSION
    confidence_formula_version: int = CONFIDENCE_FORMULA_VERSION

    @property
    def governance_class(self) -> GovernanceClass:
        return OPERATION_GOVERNANCE[self.operation]


@dataclass(frozen=True)
class TransformationDecision:
    candidate_id: str
    candidate_sha256: str
    decision: DecisionKind
    reviewer: str
    reviewed_at: str
    modified_parameters: Mapping[str, Any] | None = None
    note: str = ""


@dataclass(frozen=True)
class ApprovedTransformation:
    """What the engine is allowed to run for a governed operation: exact and
    hash-bound to an approved candidate and the decision that approved it.

    `effective_parameters` are the candidate's parameters for an approved
    decision and the reviewer's parameters for a modified decision. Either way
    the authority hash binds candidate, source, operation, and the parameters
    that will actually run, so a later drift in any of them is detectable.
    """

    candidate_id: str
    candidate_sha256: str
    decision_sha256: str
    source_sha256: str
    table: str
    column: str
    operation: TransformationOperation
    effective_parameters: Mapping[str, Any]
    authority_sha256: str
    authority_kind: AuthorityKind = AuthorityKind.HUMAN_DECISION


@dataclass(frozen=True)
class PolicyOperation:
    """One configured operation with its exact scope and parameters."""

    operation: TransformationOperation
    table: str
    columns: tuple[str, ...]
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CleaningPolicy:
    """Dataset-scoped authority for configured_only operations.

    Deployment defaults may propose or pre-populate a policy; only this
    versioned, hash-bound object grants authority, and only for the dataset,
    tables, and columns it names.
    """

    dataset_id: str
    configured_by: str
    configured_at: str
    operations: tuple[PolicyOperation, ...]
    policy_version: int = POLICY_VERSION


@dataclass(frozen=True)
class ConfiguredAuthority:
    """What the engine is allowed to run for a configured_only operation:
    exact and hash-bound to the policy, the source, and the scope."""

    policy_sha256: str
    dataset_id: str
    source_sha256: str
    table: str
    column: str
    operation: TransformationOperation
    effective_parameters: Mapping[str, Any]
    authority_sha256: str
    authority_kind: AuthorityKind = AuthorityKind.CLEANING_POLICY


@dataclass(frozen=True)
class AutomaticAuthority:
    """What the engine is allowed to run for a safe_automatic operation: the
    versioned operation-table entry, bound to the exact source and scope."""

    source_sha256: str
    table: str
    column: str
    operation: TransformationOperation
    authority_sha256: str
    authority_kind: AuthorityKind = AuthorityKind.OPERATION_TABLE


@dataclass(frozen=True)
class TransformationLineage:
    source_sha256: str
    authority_kind: AuthorityKind
    authority_sha256: str
    output_sha256: str
    table: str
    column: str
    operation: TransformationOperation
    rows_examined: int
    rows_changed: int
    applied_at: str
    contract_version: int = CONTRACT_VERSION


# --------------------------------------------------------------------------- #
# Confidence and hashes
# --------------------------------------------------------------------------- #


def compute_confidence(evidence: TransformationEvidence) -> float:
    """Confidence is a pure function of evidence. Nothing else may set it.

    Formula version 1:

        confidence = success_ratio * (1 - ambiguity_ratio)

    rounded to CONFIDENCE_PRECISION decimals. A candidate with no candidate
    values, or with any failure that the operation cannot explain, cannot reach
    1.0. The formula is deliberately simple; what matters is that it is
    reproducible from the recorded evidence and versioned.
    """
    if evidence.candidate_count <= 0:
        return 0.0
    raw = evidence.success_ratio * (1.0 - evidence.ambiguity_ratio)
    return round(max(0.0, min(1.0, raw)), CONFIDENCE_PRECISION)


def candidate_hash(candidate: TransformationCandidate) -> str:
    """Hash of everything a reviewer sees and approves. Excludes review_state."""
    return sha256_of(
        {
            "contract_version": candidate.contract_version,
            "confidence_formula_version": candidate.confidence_formula_version,
            "candidate_id": candidate.candidate_id,
            "source_sha256": candidate.source_sha256,
            "table": candidate.table,
            "column": candidate.column,
            "operation": candidate.operation,
            "parameters": candidate.parameters,
            "evidence": candidate.evidence,
            "computed_confidence": candidate.computed_confidence,
        }
    )


def decision_hash(decision: TransformationDecision) -> str:
    return sha256_of(decision)


def policy_hash(policy: CleaningPolicy) -> str:
    return sha256_of(policy)


def authority_hash(
    *,
    authority_kind: AuthorityKind,
    candidate_id: str,
    candidate_sha256: str,
    decision_sha256: str,
    source_sha256: str,
    table: str,
    column: str,
    operation: TransformationOperation,
    effective_parameters: Mapping[str, Any],
) -> str:
    """Bind everything the application will act on, including which mechanism
    granted it. Symmetric with the other authorities: a record retargeted to
    another table, column, or authority kind must fail its own self-check,
    not verify clean and poison lineage."""
    return sha256_of(
        {
            "authority_kind": authority_kind,
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "decision_sha256": decision_sha256,
            "source_sha256": source_sha256,
            "table": table,
            "column": column,
            "operation": operation,
            "effective_parameters": effective_parameters,
        }
    )


def configured_authority_hash(
    *,
    authority_kind: AuthorityKind,
    policy_sha256: str,
    source_sha256: str,
    dataset_id: str,
    operation: TransformationOperation,
    table: str,
    column: str,
    effective_parameters: Mapping[str, Any],
) -> str:
    return sha256_of(
        {
            "authority_kind": authority_kind,
            "policy_sha256": policy_sha256,
            "source_sha256": source_sha256,
            "dataset_id": dataset_id,
            "operation": operation,
            "table": table,
            "column": column,
            "effective_parameters": effective_parameters,
        }
    )


def automatic_authority_hash(
    *,
    authority_kind: AuthorityKind,
    source_sha256: str,
    table: str,
    column: str,
    operation: TransformationOperation,
) -> str:
    """Authority for safe_automatic operations is the versioned table entry,
    bound to the exact source and scope it will act on."""
    return sha256_of(
        {
            "authority_kind": authority_kind,
            "contract_version": CONTRACT_VERSION,
            "operation": operation,
            "governance_class": OPERATION_GOVERNANCE[operation],
            "source_sha256": source_sha256,
            "table": table,
            "column": column,
        }
    )


def governance_class_for(operation: TransformationOperation) -> GovernanceClass:
    return OPERATION_GOVERNANCE[operation]


# --------------------------------------------------------------------------- #
# State machine
# --------------------------------------------------------------------------- #


def transition(
    current: ReviewState,
    target: ReviewState,
    blockers: list[dict[str, str]],
) -> ReviewState:
    """Return the new state, or the unchanged state plus a blocker."""
    if target in ALLOWED_TRANSITIONS.get(current, frozenset()):
        return target
    add_blocker(
        blockers,
        "illegal_review_transition",
        f"Transition {current.value} -> {target.value} is not allowed.",
        field="review_state",
    )
    return current


# --------------------------------------------------------------------------- #
# Candidates
# --------------------------------------------------------------------------- #


def build_candidate(
    *,
    candidate_id: str,
    source_sha256: str,
    table: str,
    column: str,
    operation: TransformationOperation | str,
    parameters: Mapping[str, Any],
    evidence: TransformationEvidence,
    blockers: list[dict[str, str]],
    proposed_confidence: float | None = None,
) -> TransformationCandidate | None:
    """Construct a candidate, computing its confidence from evidence.

    A proposer may pass `proposed_confidence` for transparency, but the value
    is never stored: the candidate's confidence is always recomputed. If the
    proposer's number differs from the computed one, that is recorded as a
    blocker so the discrepancy is visible rather than silently overwritten.

    Only blockers raised by this call refuse this candidate. The list is a
    shared accumulator; an earlier, unrelated failure must not drop a later
    valid candidate.
    """
    start = len(blockers)
    if not CANDIDATE_ID_PATTERN.fullmatch(candidate_id or ""):
        add_blocker(blockers, "invalid_candidate_id", "Candidate id has an unsupported form.", field="candidate_id")
    if not SHA256_PATTERN.fullmatch(source_sha256 or ""):
        add_blocker(blockers, "invalid_source_sha256", "Source hash must be 64 lowercase hex characters.", field="source_sha256")
    if not IDENTIFIER_PATTERN.fullmatch(table or ""):
        add_blocker(blockers, "invalid_table_identifier", "Table must be a simple identifier.", field="table")
    if not IDENTIFIER_PATTERN.fullmatch(column or ""):
        add_blocker(blockers, "invalid_column_identifier", "Column must be a simple identifier.", field="column")
    try:
        resolved_operation = TransformationOperation(operation)
    except ValueError:
        add_blocker(blockers, "unknown_transformation_operation", f"Operation {operation!r} is not in the governed operation table.", field="operation")
        return None
    if resolved_operation not in OPERATION_GOVERNANCE:
        add_blocker(blockers, "unclassified_transformation_operation", f"Operation {resolved_operation.value} has no governance class.", field="operation")
        return None
    _check_canonical(parameters, field_name="parameters", blockers=blockers)
    if not _evidence_is_consistent(evidence, blockers):
        return None
    if len(blockers) > start:
        return None

    confidence = compute_confidence(evidence)
    if proposed_confidence is not None and round(float(proposed_confidence), CONFIDENCE_PRECISION) != confidence:
        add_blocker(
            blockers,
            "proposed_confidence_ignored",
            f"Proposer supplied confidence {proposed_confidence!r}; computed {confidence} from evidence and kept the computed value.",
            field="computed_confidence",
        )
        # Not fatal: the computed value stands and the discrepancy is on record.

    return TransformationCandidate(
        candidate_id=candidate_id,
        source_sha256=source_sha256,
        table=table,
        column=column,
        operation=resolved_operation,
        parameters=dict(parameters),
        evidence=evidence,
        computed_confidence=confidence,
    )


def _evidence_is_consistent(evidence: TransformationEvidence, blockers: list[dict[str, str]]) -> bool:
    ok = True
    counts = {
        "values_examined": evidence.values_examined,
        "non_null_count": evidence.non_null_count,
        "candidate_count": evidence.candidate_count,
        "success_count": evidence.success_count,
        "failure_count": evidence.failure_count,
        "ambiguous_count": evidence.ambiguous_count,
    }
    for name, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            add_blocker(blockers, "invalid_evidence_count", f"{name} must be a non-negative integer.", field=f"evidence.{name}")
            ok = False
    if not ok:
        return False
    if evidence.non_null_count > evidence.values_examined:
        add_blocker(blockers, "inconsistent_evidence", "non_null_count exceeds values_examined.", field="evidence.non_null_count")
        ok = False
    if evidence.candidate_count > evidence.non_null_count:
        add_blocker(blockers, "inconsistent_evidence", "candidate_count exceeds non_null_count.", field="evidence.candidate_count")
        ok = False
    if evidence.success_count + evidence.failure_count != evidence.candidate_count:
        add_blocker(blockers, "inconsistent_evidence", "success_count + failure_count must equal candidate_count.", field="evidence.success_count")
        ok = False
    if evidence.ambiguous_count > evidence.success_count:
        add_blocker(blockers, "inconsistent_evidence", "ambiguous_count exceeds success_count.", field="evidence.ambiguous_count")
        ok = False
    for name, value in evidence.metrics.items():
        if not isinstance(name, str) or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            add_blocker(blockers, "invalid_evidence_metric", f"metric {name!r} must be a finite number keyed by a string.", field="evidence.metrics")
            ok = False
    return ok


# --------------------------------------------------------------------------- #
# Decisions and governed authority
# --------------------------------------------------------------------------- #


def validate_decision(
    candidate: TransformationCandidate,
    decision: TransformationDecision,
    blockers: list[dict[str, str]],
) -> bool:
    """A decision is valid only for the exact candidate it names."""
    ok = True
    if decision.candidate_id != candidate.candidate_id:
        add_blocker(blockers, "decision_candidate_mismatch", "Decision names a different candidate id.", field="decision.candidate_id")
        ok = False
    expected = candidate_hash(candidate)
    if decision.candidate_sha256 != expected:
        add_blocker(blockers, "decision_hash_mismatch", "Decision is bound to a different candidate hash; the candidate changed after review.", field="decision.candidate_sha256")
        ok = False
    if not decision.reviewer.strip():
        add_blocker(blockers, "missing_reviewer", "A decision must name its reviewer.", field="decision.reviewer")
        ok = False
    if not decision.reviewed_at.strip():
        add_blocker(blockers, "missing_review_timestamp", "A decision must carry its timestamp.", field="decision.reviewed_at")
        ok = False
    elif not is_aware_iso_timestamp(decision.reviewed_at):
        add_blocker(blockers, "invalid_reviewed_at", "reviewed_at must be ISO-8601 with an explicit UTC offset.", field="decision.reviewed_at")
        ok = False
    if decision.decision is DecisionKind.MODIFIED and not decision.modified_parameters:
        add_blocker(blockers, "modified_decision_without_parameters", "A modified decision must state the parameters that replace the candidate's.", field="decision.modified_parameters")
        ok = False
    if decision.decision is not DecisionKind.MODIFIED and decision.modified_parameters:
        add_blocker(blockers, "unexpected_modified_parameters", "Only a modified decision may carry replacement parameters.", field="decision.modified_parameters")
        ok = False
    if decision.modified_parameters is not None and not _check_canonical(decision.modified_parameters, field_name="decision.modified_parameters", blockers=blockers):
        ok = False
    return ok


def submit_for_review(
    candidate: TransformationCandidate,
    blockers: list[dict[str, str]],
) -> TransformationCandidate | None:
    """Move a fresh candidate to pending_review. The only legal first move."""
    start = len(blockers)
    new_state = transition(candidate.review_state, ReviewState.PENDING_REVIEW, blockers)
    if len(blockers) > start:
        # transition() returns the unchanged state on refusal; when the current
        # state already equals the target that value is indistinguishable from
        # success, so the blocker - not the state - is the signal.
        return None
    return replace(candidate, review_state=new_state)


def record_decision(
    candidate: TransformationCandidate,
    decision: TransformationDecision,
    blockers: list[dict[str, str]],
) -> TransformationCandidate | None:
    """Move a pending candidate to approved or rejected under a valid decision.

    This is the API route to `approved`. It requires the candidate to be
    `pending_review` and the decision to bind this exact candidate. A modified
    decision approves with the reviewer's parameters taking effect at
    authorization time; the candidate itself is unchanged (so its hash, and
    the decision's binding to it, stay valid).

    `review_state` is a projection of the decision record, not independent
    authority. In-process, a frozen dataclass field can be replaced, so the
    state gate documents process; the security gate is the decision's binding
    to the exact candidate hash, which is the human artifact itself. The
    engine must therefore derive state from persisted decision records and
    never store `approved` as free-standing authority.
    """
    if candidate.review_state is not ReviewState.PENDING_REVIEW:
        add_blocker(
            blockers,
            "candidate_not_reviewable",
            f"Candidate in state {candidate.review_state.value} cannot receive a decision; only pending_review can.",
            field="review_state",
        )
        return None
    if not validate_decision(candidate, decision, blockers):
        return None
    target = ReviewState.REJECTED if decision.decision is DecisionKind.REJECTED else ReviewState.APPROVED
    start = len(blockers)
    new_state = transition(candidate.review_state, target, blockers)
    if len(blockers) > start:
        return None
    return replace(candidate, review_state=new_state)


def authorize_application(
    candidate: TransformationCandidate,
    decision: TransformationDecision,
    current_source_sha256: str,
    blockers: list[dict[str, str]],
) -> ApprovedTransformation | None:
    """Grant an exact, hash-bound authority to apply - or refuse with blockers.

    Requires the candidate to be in the `approved` state: `approved` is real
    authority, not a label. The decision must still bind this exact candidate
    (the candidate hash excludes review_state, so a decision recorded at
    pending_review keeps binding after the transition), must not be a
    rejection, and the source must be unchanged. Every refusal is fail-closed:
    there is no partial authority.
    """
    if candidate.review_state is not ReviewState.APPROVED:
        add_blocker(
            blockers,
            "candidate_not_approved",
            f"Candidate in state {candidate.review_state.value} has no authority; only approved does.",
            field="review_state",
        )
        return None
    if not validate_decision(candidate, decision, blockers):
        return None
    if decision.decision is DecisionKind.REJECTED:
        add_blocker(blockers, "decision_rejected", "A rejected decision grants no authority.", field="decision.decision")
        return None
    if current_source_sha256 != candidate.source_sha256:
        add_blocker(
            blockers,
            "source_changed_since_review",
            "The source no longer matches the hash the candidate was proposed against; the approval is void.",
            field="source_sha256",
        )
        return None
    if candidate.governance_class is not GovernanceClass.GOVERNED:
        add_blocker(
            blockers,
            "decision_authority_wrong_class",
            f"A human decision grants authority only for governed operations; {candidate.operation.value} is {candidate.governance_class.value}.",
            field="operation",
        )
        return None

    effective = (
        dict(decision.modified_parameters or {})
        if decision.decision is DecisionKind.MODIFIED
        else dict(candidate.parameters)
    )
    c_hash = candidate_hash(candidate)
    d_hash = decision_hash(decision)
    return ApprovedTransformation(
        candidate_id=candidate.candidate_id,
        candidate_sha256=c_hash,
        decision_sha256=d_hash,
        source_sha256=candidate.source_sha256,
        table=candidate.table,
        column=candidate.column,
        operation=candidate.operation,
        effective_parameters=effective,
        authority_sha256=authority_hash(
            authority_kind=AuthorityKind.HUMAN_DECISION,
            candidate_id=candidate.candidate_id,
            candidate_sha256=c_hash,
            decision_sha256=d_hash,
            source_sha256=candidate.source_sha256,
            table=candidate.table,
            column=candidate.column,
            operation=candidate.operation,
            effective_parameters=effective,
        ),
    )


def verify_authority(
    approved: ApprovedTransformation,
    *,
    current_source_sha256: str,
    blockers: list[dict[str, str]],
) -> bool:
    """Recheck an authority right before application. Drift is a blocker."""
    ok = True
    if current_source_sha256 != approved.source_sha256:
        add_blocker(blockers, "source_changed_since_review", "Source hash drifted after authority was granted.", field="source_sha256")
        ok = False
    expected = authority_hash(
        authority_kind=approved.authority_kind,
        candidate_id=approved.candidate_id,
        candidate_sha256=approved.candidate_sha256,
        decision_sha256=approved.decision_sha256,
        source_sha256=approved.source_sha256,
        table=approved.table,
        column=approved.column,
        operation=approved.operation,
        effective_parameters=approved.effective_parameters,
    )
    if expected != approved.authority_sha256:
        add_blocker(blockers, "authority_hash_mismatch", "Authority record does not match its own bound content.", field="authority_sha256")
        ok = False
    return ok


# --------------------------------------------------------------------------- #
# Cleaning policy and configured authority
# --------------------------------------------------------------------------- #


def validate_policy(policy: CleaningPolicy, blockers: list[dict[str, str]]) -> bool:
    """A policy grants authority only if every entry is exact and configurable.

    Only configured_only operations may appear: governed operations need a
    human decision and safe_automatic ones need nothing, so listing either in
    a policy would blur which mechanism granted authority.
    """
    ok = True
    if policy.policy_version != POLICY_VERSION:
        add_blocker(blockers, "unsupported_policy_version", f"Cleaning policy must use version {POLICY_VERSION}.", field="policy_version")
        ok = False
    if not IDENTIFIER_PATTERN.fullmatch(policy.dataset_id or ""):
        add_blocker(blockers, "invalid_dataset_identifier", "dataset_id must be a simple identifier.", field="dataset_id")
        ok = False
    if not policy.configured_by.strip():
        add_blocker(blockers, "missing_policy_author", "A policy must name who configured it.", field="configured_by")
        ok = False
    if not is_aware_iso_timestamp(policy.configured_at):
        add_blocker(blockers, "invalid_configured_at", "configured_at must be ISO-8601 with an explicit UTC offset.", field="configured_at")
        ok = False
    if not policy.operations:
        add_blocker(blockers, "empty_policy", "A policy must configure at least one operation.", field="operations")
        ok = False
    seen: set[tuple[TransformationOperation, str, str]] = set()
    for index, entry in enumerate(policy.operations):
        prefix = f"operations[{index}]"
        if not _check_canonical(entry.parameters, field_name=f"{prefix}.parameters", blockers=blockers):
            ok = False
        try:
            operation = TransformationOperation(entry.operation)
        except ValueError:
            add_blocker(blockers, "unknown_transformation_operation", f"Operation {entry.operation!r} is not in the governed operation table.", field=f"{prefix}.operation")
            ok = False
            continue
        if OPERATION_GOVERNANCE[operation] is not GovernanceClass.CONFIGURED_ONLY:
            add_blocker(
                blockers,
                "policy_operation_not_configurable",
                f"{operation.value} is {OPERATION_GOVERNANCE[operation].value}; a cleaning policy may only configure configured_only operations.",
                field=f"{prefix}.operation",
            )
            ok = False
        if not IDENTIFIER_PATTERN.fullmatch(entry.table or ""):
            add_blocker(blockers, "invalid_table_identifier", "Table must be a simple identifier.", field=f"{prefix}.table")
            ok = False
        if not entry.columns:
            add_blocker(blockers, "empty_policy_scope", "A policy entry must name at least one column.", field=f"{prefix}.columns")
            ok = False
        for column in entry.columns:
            if not IDENTIFIER_PATTERN.fullmatch(column or ""):
                add_blocker(blockers, "invalid_column_identifier", "Column must be a simple identifier.", field=f"{prefix}.columns")
                ok = False
                continue
            key = (operation, entry.table, column)
            if key in seen:
                add_blocker(blockers, "duplicate_policy_scope", f"{operation.value} on {entry.table}.{column} is configured more than once.", field=f"{prefix}.columns")
                ok = False
            seen.add(key)
    return ok


def authorize_configured(
    policy: CleaningPolicy,
    *,
    source_sha256: str,
    operation: TransformationOperation,
    table: str,
    column: str,
    blockers: list[dict[str, str]],
) -> ConfiguredAuthority | None:
    """Grant exact authority for one configured_only operation on one column,
    or refuse. The policy must be valid, name this exact scope, and the
    operation must be configured_only. Authority binds policy hash, source
    hash, dataset, operation, scope, and effective parameters."""
    if not validate_policy(policy, blockers):
        return None
    if not SHA256_PATTERN.fullmatch(source_sha256 or ""):
        add_blocker(blockers, "invalid_source_sha256", "Source hash must be 64 lowercase hex characters.", field="source_sha256")
        return None
    if OPERATION_GOVERNANCE.get(operation) is not GovernanceClass.CONFIGURED_ONLY:
        add_blocker(
            blockers,
            "policy_operation_not_configurable",
            f"{operation.value} cannot be authorized by a cleaning policy.",
            field="operation",
        )
        return None
    match = next(
        (entry for entry in policy.operations if entry.operation == operation and entry.table == table and column in entry.columns),
        None,
    )
    if match is None:
        add_blocker(
            blockers,
            "operation_not_configured",
            f"The policy for {policy.dataset_id} does not configure {operation.value} on {table}.{column}.",
            field="operations",
        )
        return None
    p_hash = policy_hash(policy)
    effective = dict(match.parameters)
    return ConfiguredAuthority(
        policy_sha256=p_hash,
        dataset_id=policy.dataset_id,
        source_sha256=source_sha256,
        table=table,
        column=column,
        operation=operation,
        effective_parameters=effective,
        authority_sha256=configured_authority_hash(
            authority_kind=AuthorityKind.CLEANING_POLICY,
            policy_sha256=p_hash,
            source_sha256=source_sha256,
            dataset_id=policy.dataset_id,
            operation=operation,
            table=table,
            column=column,
            effective_parameters=effective,
        ),
    )


def verify_configured_authority(
    authority: ConfiguredAuthority,
    *,
    current_source_sha256: str,
    blockers: list[dict[str, str]],
) -> bool:
    ok = True
    if current_source_sha256 != authority.source_sha256:
        add_blocker(blockers, "source_changed_since_review", "Source hash drifted after configured authority was granted.", field="source_sha256")
        ok = False
    expected = configured_authority_hash(
        authority_kind=authority.authority_kind,
        policy_sha256=authority.policy_sha256,
        source_sha256=authority.source_sha256,
        dataset_id=authority.dataset_id,
        operation=authority.operation,
        table=authority.table,
        column=authority.column,
        effective_parameters=authority.effective_parameters,
    )
    if expected != authority.authority_sha256:
        add_blocker(blockers, "authority_hash_mismatch", "Configured authority record does not match its own bound content.", field="authority_sha256")
        ok = False
    return ok


# --------------------------------------------------------------------------- #
# Automatic authority
# --------------------------------------------------------------------------- #


def build_automatic_authority(
    *,
    source_sha256: str,
    table: str,
    column: str,
    operation: TransformationOperation,
    blockers: list[dict[str, str]],
) -> AutomaticAuthority | None:
    """Grant exact authority for one safe_automatic operation on one column.
    Only the operation table grants it, and only for operations the table
    classifies as safe_automatic; everything else needs a policy or a decision.
    """
    start = len(blockers)
    if not SHA256_PATTERN.fullmatch(source_sha256 or ""):
        add_blocker(blockers, "invalid_source_sha256", "Source hash must be 64 lowercase hex characters.", field="source_sha256")
    if not IDENTIFIER_PATTERN.fullmatch(table or ""):
        add_blocker(blockers, "invalid_table_identifier", "Table must be a simple identifier.", field="table")
    if operation is TransformationOperation.NORMALIZE_COLUMN_NAME:
        # The one operation whose purpose is to act on a name that is not an
        # identifier yet. Its scope is the exact raw source name, bounded by
        # RAW_COLUMN_NAME_PATTERN, and the authority hash binds that raw name.
        if not is_valid_raw_column_name(column):
            add_blocker(blockers, "invalid_raw_column_name", "normalize_column_name needs a bounded raw source column name: 1-255 characters, no control characters, at least one letter or digit.", field="column")
    elif not IDENTIFIER_PATTERN.fullmatch(column or ""):
        add_blocker(blockers, "invalid_column_identifier", "Column must be a simple identifier.", field="column")
    if OPERATION_GOVERNANCE.get(operation) is not GovernanceClass.SAFE_AUTOMATIC:
        add_blocker(
            blockers,
            "operation_not_automatic",
            f"{getattr(operation, 'value', operation)} is not safe_automatic; the operation table grants no authority for it.",
            field="operation",
        )
    if len(blockers) > start:
        return None
    return AutomaticAuthority(
        source_sha256=source_sha256,
        table=table,
        column=column,
        operation=operation,
        authority_sha256=automatic_authority_hash(
            authority_kind=AuthorityKind.OPERATION_TABLE,
            source_sha256=source_sha256,
            table=table,
            column=column,
            operation=operation,
        ),
    )


def verify_automatic_authority(
    authority: AutomaticAuthority,
    *,
    current_source_sha256: str,
    blockers: list[dict[str, str]],
) -> bool:
    ok = True
    if current_source_sha256 != authority.source_sha256:
        add_blocker(blockers, "source_changed_since_review", "Source hash drifted after automatic authority was granted.", field="source_sha256")
        ok = False
    if OPERATION_GOVERNANCE.get(authority.operation) is not GovernanceClass.SAFE_AUTOMATIC:
        add_blocker(blockers, "operation_not_automatic", f"{authority.operation.value} is no longer safe_automatic in the operation table.", field="operation")
        ok = False
    if authority.operation is TransformationOperation.NORMALIZE_COLUMN_NAME and not is_valid_raw_column_name(authority.column):
        add_blocker(blockers, "invalid_raw_column_name", "Automatic authority carries a raw column name outside the bounded rule.", field="column")
        ok = False
    expected = automatic_authority_hash(
        authority_kind=authority.authority_kind,
        source_sha256=authority.source_sha256,
        table=authority.table,
        column=authority.column,
        operation=authority.operation,
    ) if OPERATION_GOVERNANCE.get(authority.operation) is not None else ""
    if expected != authority.authority_sha256:
        add_blocker(blockers, "authority_hash_mismatch", "Automatic authority record does not match its own bound content.", field="authority_sha256")
        ok = False
    return ok


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #


def build_lineage(
    authority: ApprovedTransformation | ConfiguredAuthority | AutomaticAuthority,
    *,
    output_sha256: str,
    rows_examined: int,
    rows_changed: int,
    applied_at: str,
    blockers: list[dict[str, str]],
) -> TransformationLineage | None:
    """Lineage points at exactly one authority record and one output. All three
    authority kinds reach lineage through the same door."""
    if not SHA256_PATTERN.fullmatch(output_sha256 or ""):
        add_blocker(blockers, "invalid_output_sha256", "Output hash must be 64 lowercase hex characters.", field="output_sha256")
        return None
    for name, value in (("rows_examined", rows_examined), ("rows_changed", rows_changed)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            add_blocker(blockers, "invalid_lineage_count", f"{name} must be a non-negative integer.", field=name)
            return None
    if rows_changed > rows_examined:
        add_blocker(blockers, "inconsistent_lineage", "rows_changed exceeds rows_examined.", field="rows_changed")
        return None
    if not applied_at.strip():
        add_blocker(blockers, "missing_applied_timestamp", "Lineage must carry the application timestamp.", field="applied_at")
        return None
    if not is_aware_iso_timestamp(applied_at):
        add_blocker(blockers, "invalid_applied_at", "applied_at must be ISO-8601 with an explicit UTC offset.", field="applied_at")
        return None
    return TransformationLineage(
        source_sha256=authority.source_sha256,
        authority_kind=authority.authority_kind,
        authority_sha256=authority.authority_sha256,
        output_sha256=output_sha256,
        table=authority.table,
        column=authority.column,
        operation=authority.operation,
        rows_examined=rows_examined,
        rows_changed=rows_changed,
        applied_at=applied_at,
    )
