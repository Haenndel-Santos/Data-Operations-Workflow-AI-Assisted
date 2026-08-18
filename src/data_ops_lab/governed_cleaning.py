"""Governed cleaning contract: candidates, evidence, decisions, lineage.

This module defines the typed contract for governed data cleaning and the pure
functions that decide authority. It performs no I/O and touches no DataFrame.
The engine that proposes candidates from real data and applies approved
transformations is a later, separate increment; nothing here can alter a value.

Authority split, matching the analytics side of the project:

    heuristic or model proposes an operation
    deterministic code measures the evidence
    deterministic code computes the confidence from that evidence
    a human decision grants or refuses authority
    deterministic code applies only what was granted, and records lineage

States move only forward and never skip review:

    candidate -> pending_review -> approved | rejected
    approved -> applied

`candidate -> applied` does not exist.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from .contracts.blockers import add_blocker


CONTRACT_VERSION = 1
CONFIDENCE_FORMULA_VERSION = 1
CONFIDENCE_PRECISION = 4

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
CANDIDATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class GovernanceClass(str, Enum):
    """How much authority a transformation needs before it may run.

    SAFE_AUTOMATIC   - structural, value-preserving normalization; may run
                       without review.
    CONFIGURED_ONLY  - runs automatically only when the deployment or dataset
                       policy explicitly enables it; never by default.
    GOVERNED         - always a candidate; requires an explicit approved
                       decision bound to the exact candidate hash.
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
OPERATION_GOVERNANCE: Mapping[TransformationOperation, GovernanceClass] = {
    TransformationOperation.NORMALIZE_COLUMN_NAME: GovernanceClass.SAFE_AUTOMATIC,
    TransformationOperation.TRIM_WHITESPACE: GovernanceClass.SAFE_AUTOMATIC,
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
    """What the engine is allowed to run: exact and hash-bound.

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


@dataclass(frozen=True)
class TransformationLineage:
    source_sha256: str
    authority_sha256: str
    output_sha256: str
    table: str
    column: str
    operation: TransformationOperation
    rows_examined: int
    rows_changed: int
    applied_at: str
    contract_version: int = CONTRACT_VERSION


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


def canonical_json(payload: Any) -> str:
    """Stable serialization for hashing: sorted keys, no whitespace, ASCII."""
    return json.dumps(
        _plain(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    return value


def sha256_of(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


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


def authority_hash(
    *,
    candidate_sha256: str,
    decision_sha256: str,
    source_sha256: str,
    operation: TransformationOperation,
    effective_parameters: Mapping[str, Any],
) -> str:
    return sha256_of(
        {
            "candidate_sha256": candidate_sha256,
            "decision_sha256": decision_sha256,
            "source_sha256": source_sha256,
            "operation": operation,
            "effective_parameters": effective_parameters,
        }
    )


def governance_class_for(operation: TransformationOperation) -> GovernanceClass:
    return OPERATION_GOVERNANCE[operation]


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
    if not _evidence_is_consistent(evidence, blockers):
        return None
    if len(blockers) > start:
        # Only blockers raised by this call refuse this candidate. The list is
        # a shared accumulator; an earlier, unrelated failure must not drop a
        # later valid candidate.
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
    return ok


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
    return ok


def authorize_application(
    candidate: TransformationCandidate,
    decision: TransformationDecision,
    current_source_sha256: str,
    blockers: list[dict[str, str]],
) -> ApprovedTransformation | None:
    """Grant an exact, hash-bound authority to apply - or refuse with blockers.

    Refuses when: the candidate is not in a reviewable state, the decision does
    not bind this exact candidate, the decision is a rejection, or the source
    changed since the candidate was proposed. Every refusal is fail-closed:
    there is no partial authority.
    """
    if candidate.review_state not in {ReviewState.PENDING_REVIEW, ReviewState.APPROVED}:
        add_blocker(
            blockers,
            "candidate_not_reviewable",
            f"Candidate in state {candidate.review_state.value} cannot be authorized for application.",
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
    if candidate.governance_class is GovernanceClass.GOVERNED and decision.decision not in {
        DecisionKind.APPROVED,
        DecisionKind.MODIFIED,
    }:
        add_blocker(blockers, "governed_operation_requires_approval", "A governed operation needs an approved or modified decision.", field="decision.decision")
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
            candidate_sha256=c_hash,
            decision_sha256=d_hash,
            source_sha256=candidate.source_sha256,
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
        candidate_sha256=approved.candidate_sha256,
        decision_sha256=approved.decision_sha256,
        source_sha256=approved.source_sha256,
        operation=approved.operation,
        effective_parameters=approved.effective_parameters,
    )
    if expected != approved.authority_sha256:
        add_blocker(blockers, "authority_hash_mismatch", "Authority record does not match its own bound content.", field="authority_sha256")
        ok = False
    return ok


def build_lineage(
    approved: ApprovedTransformation,
    *,
    output_sha256: str,
    rows_examined: int,
    rows_changed: int,
    applied_at: str,
    blockers: list[dict[str, str]],
) -> TransformationLineage | None:
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
        source_sha256=approved.source_sha256,
        authority_sha256=approved.authority_sha256,
        output_sha256=output_sha256,
        table=approved.table,
        column=approved.column,
        operation=approved.operation,
        rows_examined=rows_examined,
        rows_changed=rows_changed,
        applied_at=applied_at,
    )
