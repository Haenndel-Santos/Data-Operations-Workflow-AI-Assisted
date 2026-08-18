"""Invariants of the governed cleaning contract.

These tests prove properties of the contract itself: state transitions, hash
binding, confidence derivation, and authority granting. They exercise no
engine and touch no data. Properties that need the engine (a value is
unchanged on disk, a partial failure publishes nothing) belong to the engine
increment and are listed in docs/governed-cleaning.md as deferred.
"""

from __future__ import annotations

import dataclasses

import pytest

from data_ops_lab.governed_cleaning import (
    ALLOWED_TRANSITIONS,
    CONFIDENCE_FORMULA_VERSION,
    CONTRACT_VERSION,
    OPERATION_GOVERNANCE,
    ApprovedTransformation,
    DecisionKind,
    GovernanceClass,
    ReviewState,
    TransformationCandidate,
    TransformationDecision,
    TransformationEvidence,
    TransformationOperation,
    authorize_application,
    build_candidate,
    build_lineage,
    candidate_hash,
    canonical_json,
    compute_confidence,
    decision_hash,
    governance_class_for,
    is_aware_iso_timestamp,
    transition,
    validate_decision,
    verify_authority,
)

SOURCE = "a" * 64
OTHER_SOURCE = "b" * 64
OUTPUT = "c" * 64


def evidence(**overrides) -> TransformationEvidence:
    base = dict(
        values_examined=1240,
        non_null_count=1240,
        candidate_count=1240,
        success_count=1228,
        failure_count=12,
        ambiguous_count=3,
        metrics={"iso_ratio": 0.9871},
    )
    base.update(overrides)
    return TransformationEvidence(**base)


def candidate(**overrides) -> TransformationCandidate:
    blockers: list[dict[str, str]] = []
    params = dict(
        candidate_id="orders.invoice_date.parse_date",
        source_sha256=SOURCE,
        table="orders",
        column="invoice_date",
        operation=TransformationOperation.PARSE_DATE,
        parameters={"format": "%Y-%m-%d"},
        evidence=evidence(),
        blockers=blockers,
    )
    params.update(overrides)
    built = build_candidate(**params)
    assert built is not None, blockers
    assert not blockers, blockers
    return built


def approved_decision(cand: TransformationCandidate, **overrides) -> TransformationDecision:
    params = dict(
        candidate_id=cand.candidate_id,
        candidate_sha256=candidate_hash(cand),
        decision=DecisionKind.APPROVED,
        reviewer="owner",
        reviewed_at="2026-08-18T12:00:00Z",
    )
    params.update(overrides)
    return TransformationDecision(**params)


def pending(cand: TransformationCandidate) -> TransformationCandidate:
    return dataclasses.replace(cand, review_state=ReviewState.PENDING_REVIEW)


# --------------------------------------------------------------------------- #
# State machine
# --------------------------------------------------------------------------- #


def test_candidate_can_never_reach_applied_without_approval():
    """Invariant: candidate -> applied does not exist."""
    assert ReviewState.APPLIED not in ALLOWED_TRANSITIONS[ReviewState.CANDIDATE]
    assert ReviewState.APPLIED not in ALLOWED_TRANSITIONS[ReviewState.PENDING_REVIEW]
    assert ALLOWED_TRANSITIONS[ReviewState.APPROVED] == {ReviewState.APPLIED}
    blockers: list[dict[str, str]] = []
    assert transition(ReviewState.CANDIDATE, ReviewState.APPLIED, blockers) is ReviewState.CANDIDATE
    assert [b["blocker_type"] for b in blockers] == ["illegal_review_transition"]


def test_rejected_and_applied_are_terminal():
    assert ALLOWED_TRANSITIONS[ReviewState.REJECTED] == frozenset()
    assert ALLOWED_TRANSITIONS[ReviewState.APPLIED] == frozenset()
    for terminal in (ReviewState.REJECTED, ReviewState.APPLIED):
        for target in ReviewState:
            blockers: list[dict[str, str]] = []
            assert transition(terminal, target, blockers) is terminal
            assert blockers


def test_only_forward_path_is_candidate_pending_decision_applied():
    blockers: list[dict[str, str]] = []
    state = ReviewState.CANDIDATE
    state = transition(state, ReviewState.PENDING_REVIEW, blockers)
    state = transition(state, ReviewState.APPROVED, blockers)
    state = transition(state, ReviewState.APPLIED, blockers)
    assert state is ReviewState.APPLIED
    assert blockers == []


# --------------------------------------------------------------------------- #
# Governance classes
# --------------------------------------------------------------------------- #


def test_every_operation_has_exactly_one_governance_class():
    assert set(OPERATION_GOVERNANCE) == set(TransformationOperation)


def test_semantic_coercions_are_always_governed():
    """Invariant: string->number/date and locale interpretation are candidates."""
    for op in (
        TransformationOperation.PARSE_NUMBER,
        TransformationOperation.PARSE_DATE,
        TransformationOperation.INTERPRET_DECIMAL_SEPARATOR,
        TransformationOperation.INTERPRET_LOCALE,
        TransformationOperation.CANONICALIZE_IDENTIFIER,
        TransformationOperation.REMAP_CATEGORY,
    ):
        assert governance_class_for(op) is GovernanceClass.GOVERNED, op


def test_blank_sentinel_normalization_is_configured_only_not_automatic():
    """'-', '--', and 'NA' can be legitimate business values."""
    assert governance_class_for(TransformationOperation.NORMALIZE_BLANK_SENTINEL) is GovernanceClass.CONFIGURED_ONLY


def test_only_structural_value_preserving_operations_are_safe_automatic():
    safe = {op for op, cls in OPERATION_GOVERNANCE.items() if cls is GovernanceClass.SAFE_AUTOMATIC}
    assert safe == {
        TransformationOperation.NORMALIZE_COLUMN_NAME,
        TransformationOperation.TRIM_WHITESPACE,
    }


def test_unknown_operation_is_rejected_before_it_carries_state():
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="t.c.x",
        source_sha256=SOURCE,
        table="t",
        column="c",
        operation="coerce_everything",
        parameters={},
        evidence=evidence(),
        blockers=blockers,
    )
    assert built is None
    assert [b["blocker_type"] for b in blockers] == ["unknown_transformation_operation"]


# --------------------------------------------------------------------------- #
# Confidence is computed, never accepted
# --------------------------------------------------------------------------- #


def test_confidence_is_a_pure_function_of_evidence():
    ev = evidence()
    expected = round((1228 / 1240) * (1 - 3 / 1240), 4)
    assert compute_confidence(ev) == expected
    assert compute_confidence(ev) == compute_confidence(evidence())


def test_proposed_confidence_is_ignored_and_the_discrepancy_is_recorded():
    """Invariant: the model may propose an operation; it never sets confidence."""
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="orders.invoice_date.parse_date",
        source_sha256=SOURCE,
        table="orders",
        column="invoice_date",
        operation=TransformationOperation.PARSE_DATE,
        parameters={},
        evidence=evidence(),
        blockers=blockers,
        proposed_confidence=0.99,
    )
    assert built is not None
    assert built.computed_confidence == compute_confidence(evidence())
    assert built.computed_confidence != 0.99
    assert [b["blocker_type"] for b in blockers] == ["proposed_confidence_ignored"]


def test_matching_proposed_confidence_raises_no_blocker():
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="orders.invoice_date.parse_date",
        source_sha256=SOURCE,
        table="orders",
        column="invoice_date",
        operation=TransformationOperation.PARSE_DATE,
        parameters={},
        evidence=evidence(),
        blockers=blockers,
        proposed_confidence=compute_confidence(evidence()),
    )
    assert built is not None and blockers == []


def test_confidence_cannot_reach_one_with_failures_or_ambiguity():
    assert compute_confidence(evidence(success_count=1239, failure_count=1, ambiguous_count=0)) < 1.0
    assert compute_confidence(evidence(success_count=1240, failure_count=0, ambiguous_count=1)) < 1.0
    assert compute_confidence(evidence(success_count=1240, failure_count=0, ambiguous_count=0)) == 1.0
    assert compute_confidence(evidence(candidate_count=0, non_null_count=0, success_count=0, failure_count=0, ambiguous_count=0)) == 0.0


def test_the_ninety_percent_coercion_case_stays_a_governed_candidate():
    """The legacy cleaner coerces when >=90% parse. Under the contract the
    same evidence yields a governed candidate whose confidence records the
    failures, and no path applies it without a decision."""
    ev = evidence(values_examined=10, non_null_count=10, candidate_count=10,
                  success_count=9, failure_count=1, ambiguous_count=0, metrics={})
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="t.amount.parse_number",
        source_sha256=SOURCE, table="t", column="amount",
        operation=TransformationOperation.PARSE_NUMBER,
        parameters={}, evidence=ev, blockers=blockers,
    )
    assert built is not None
    assert built.governance_class is GovernanceClass.GOVERNED
    assert built.review_state is ReviewState.CANDIDATE
    assert built.computed_confidence == 0.9
    assert authorize_application(built, approved_decision(built), SOURCE, blockers) is None
    assert "candidate_not_reviewable" in {b["blocker_type"] for b in blockers}


def test_inconsistent_evidence_is_rejected():
    blockers: list[dict[str, str]] = []
    bad = evidence(success_count=1000, failure_count=1)  # != candidate_count
    assert build_candidate(
        candidate_id="t.c.parse_number", source_sha256=SOURCE, table="t", column="c",
        operation=TransformationOperation.PARSE_NUMBER, parameters={}, evidence=bad, blockers=blockers,
    ) is None
    assert "inconsistent_evidence" in {b["blocker_type"] for b in blockers}


def test_shared_blocker_accumulator_does_not_drop_later_valid_candidates():
    """Regression: build_candidate must judge only the blockers it raised.
    An engine looping over columns with one shared list must not lose every
    candidate after the first unrelated failure."""
    blockers: list[dict[str, str]] = []
    first = build_candidate(
        candidate_id="t.a.parse_number", source_sha256=SOURCE, table="t", column="a",
        operation=TransformationOperation.PARSE_NUMBER, parameters={}, evidence=evidence(), blockers=blockers,
    )
    assert first is not None and blockers == []
    bad = build_candidate(
        candidate_id="t.b.nope", source_sha256=SOURCE, table="t", column="b",
        operation="not_an_operation", parameters={}, evidence=evidence(), blockers=blockers,
    )
    assert bad is None and len(blockers) == 1
    second = build_candidate(
        candidate_id="t.c.parse_date", source_sha256=SOURCE, table="t", column="c",
        operation=TransformationOperation.PARSE_DATE, parameters={}, evidence=evidence(), blockers=blockers,
    )
    assert second is not None, blockers
    assert len(blockers) == 1  # the earlier failure is still on record, nothing new


# --------------------------------------------------------------------------- #
# Hash binding
# --------------------------------------------------------------------------- #


def test_candidate_hash_is_deterministic_and_independent_of_dict_order():
    a = candidate(parameters={"format": "%Y-%m-%d", "dayfirst": False})
    b = candidate(parameters={"dayfirst": False, "format": "%Y-%m-%d"})
    assert candidate_hash(a) == candidate_hash(b)
    assert canonical_json(a.parameters) == canonical_json(b.parameters)


def test_candidate_hash_excludes_review_state():
    c = candidate()
    assert candidate_hash(c) == candidate_hash(pending(c))


@pytest.mark.parametrize(
    "field_name, new_value",
    [
        ("source_sha256", OTHER_SOURCE),
        ("table", "orders_v2"),
        ("column", "ship_date"),
        ("operation", TransformationOperation.PARSE_NUMBER),
        ("parameters", {"format": "%d/%m/%Y"}),
        ("computed_confidence", 0.5),
        ("contract_version", CONTRACT_VERSION + 1),
        ("confidence_formula_version", CONFIDENCE_FORMULA_VERSION + 1),
    ],
)
def test_any_reviewed_field_change_breaks_the_decision_binding(field_name, new_value):
    """Invariant: only the exact approved candidate hash can be applied."""
    original = pending(candidate())
    decision = approved_decision(original)
    tampered = dataclasses.replace(original, **{field_name: new_value})
    blockers: list[dict[str, str]] = []
    assert authorize_application(tampered, decision, tampered.source_sha256, blockers) is None
    assert "decision_hash_mismatch" in {b["blocker_type"] for b in blockers}


def test_evidence_change_breaks_the_decision_binding():
    original = pending(candidate())
    decision = approved_decision(original)
    tampered = dataclasses.replace(original, evidence=evidence(ambiguous_count=4))
    blockers: list[dict[str, str]] = []
    assert authorize_application(tampered, decision, SOURCE, blockers) is None
    assert "decision_hash_mismatch" in {b["blocker_type"] for b in blockers}


# --------------------------------------------------------------------------- #
# Authority granting
# --------------------------------------------------------------------------- #


def test_pending_candidate_with_approved_decision_yields_exact_authority():
    c = pending(candidate())
    d = approved_decision(c)
    blockers: list[dict[str, str]] = []
    auth = authorize_application(c, d, SOURCE, blockers)
    assert isinstance(auth, ApprovedTransformation)
    assert blockers == []
    assert auth.candidate_sha256 == candidate_hash(c)
    assert auth.decision_sha256 == decision_hash(d)
    assert auth.effective_parameters == c.parameters
    assert verify_authority(auth, current_source_sha256=SOURCE, blockers=blockers)
    assert blockers == []


def test_rejected_decision_grants_no_authority():
    """Invariant: rejected never alters a value - there is nothing to apply."""
    c = pending(candidate())
    d = approved_decision(c, decision=DecisionKind.REJECTED)
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, d, SOURCE, blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["decision_rejected"]


def test_source_change_voids_a_prior_approval():
    """Invariant: a source change invalidates the earlier approval."""
    c = pending(candidate())
    d = approved_decision(c)
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, d, OTHER_SOURCE, blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["source_changed_since_review"]


def test_source_drift_after_authority_is_caught_by_verify():
    c = pending(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert not verify_authority(auth, current_source_sha256=OTHER_SOURCE, blockers=blockers)
    assert "source_changed_since_review" in {b["blocker_type"] for b in blockers}


def test_tampered_authority_record_fails_self_check():
    c = pending(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    forged = dataclasses.replace(auth, effective_parameters={"format": "%d/%m/%Y"})
    blockers: list[dict[str, str]] = []
    assert not verify_authority(forged, current_source_sha256=SOURCE, blockers=blockers)
    assert "authority_hash_mismatch" in {b["blocker_type"] for b in blockers}


def test_modified_decision_binds_the_reviewer_parameters_not_the_proposal():
    c = pending(candidate())
    d = approved_decision(c, decision=DecisionKind.MODIFIED, modified_parameters={"format": "%d/%m/%Y"})
    blockers: list[dict[str, str]] = []
    auth = authorize_application(c, d, SOURCE, blockers)
    assert auth is not None and blockers == []
    assert auth.effective_parameters == {"format": "%d/%m/%Y"}
    # A different set of effective parameters is a different authority.
    plain = authorize_application(c, approved_decision(c), SOURCE, [])
    assert plain is not None
    assert plain.authority_sha256 != auth.authority_sha256


def test_modified_decision_without_parameters_is_invalid():
    c = pending(candidate())
    d = approved_decision(c, decision=DecisionKind.MODIFIED)
    blockers: list[dict[str, str]] = []
    assert not validate_decision(c, d, blockers)
    assert "modified_decision_without_parameters" in {b["blocker_type"] for b in blockers}


def test_decision_for_another_candidate_id_is_refused():
    c = pending(candidate())
    d = approved_decision(c, candidate_id="orders.other.parse_date")
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, d, SOURCE, blockers) is None
    assert "decision_candidate_mismatch" in {b["blocker_type"] for b in blockers}


def test_decision_must_name_reviewer_and_time():
    c = pending(candidate())
    blockers: list[dict[str, str]] = []
    assert not validate_decision(c, approved_decision(c, reviewer="  "), blockers)
    assert not validate_decision(c, approved_decision(c, reviewed_at=""), blockers)
    types = {b["blocker_type"] for b in blockers}
    assert {"missing_reviewer", "missing_review_timestamp"} <= types


@pytest.mark.parametrize("value", ["yesterday afternoon", "2026-08-18", "2026-08-18T12:00:00", "12:00", "not a time"])
def test_naive_or_malformed_review_timestamp_is_rejected(value):
    """Audit timestamps must be ISO-8601 with an explicit offset, matching the
    semantic-approval convention; naive local time is ambiguous evidence."""
    assert not is_aware_iso_timestamp(value)
    c = pending(candidate())
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, approved_decision(c, reviewed_at=value), SOURCE, blockers) is None
    assert "invalid_reviewed_at" in {b["blocker_type"] for b in blockers}


@pytest.mark.parametrize("value", ["2026-08-18T12:00:00Z", "2026-08-18T12:00:00+00:00", "2026-08-18T14:00:00+02:00"])
def test_aware_iso_review_timestamp_is_accepted(value):
    assert is_aware_iso_timestamp(value)
    c = pending(candidate())
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, approved_decision(c, reviewed_at=value), SOURCE, blockers) is not None
    assert blockers == []


def test_same_source_and_same_decision_produce_the_same_authority():
    """Invariant: reproducibility of the authority record."""
    c1 = pending(candidate())
    c2 = pending(candidate())
    d1 = approved_decision(c1)
    d2 = approved_decision(c2)
    a1 = authorize_application(c1, d1, SOURCE, [])
    a2 = authorize_application(c2, d2, SOURCE, [])
    assert a1 == a2


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #


def test_lineage_binds_source_authority_and_output():
    c = pending(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    lineage = build_lineage(auth, output_sha256=OUTPUT, rows_examined=1240, rows_changed=1228,
                            applied_at="2026-08-18T12:05:00Z", blockers=blockers)
    assert lineage is not None and blockers == []
    assert (lineage.source_sha256, lineage.authority_sha256, lineage.output_sha256) == (SOURCE, auth.authority_sha256, OUTPUT)


def test_lineage_rejects_impossible_counts_and_bad_hashes():
    c = pending(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert build_lineage(auth, output_sha256=OUTPUT, rows_examined=10, rows_changed=11,
                         applied_at="t", blockers=blockers) is None
    assert build_lineage(auth, output_sha256="nothex", rows_examined=10, rows_changed=1,
                         applied_at="t", blockers=blockers) is None
    types = {b["blocker_type"] for b in blockers}
    assert {"inconsistent_lineage", "invalid_output_sha256"} <= types


def test_lineage_rejects_naive_applied_timestamp():
    c = pending(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert build_lineage(auth, output_sha256=OUTPUT, rows_examined=10, rows_changed=1,
                         applied_at="2026-08-18T12:05:00", blockers=blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["invalid_applied_at"]
