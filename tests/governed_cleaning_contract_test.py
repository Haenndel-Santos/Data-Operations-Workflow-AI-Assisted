"""Invariants of the governed cleaning contract.

These tests prove properties of the contract itself: state transitions, hash
binding, canonical hash domain, confidence derivation, authority granting for
governed and configured operations, and lineage. They exercise no engine and
touch no data. Properties that need the engine (a value is unchanged on disk,
a partial failure publishes nothing) belong to the engine increment and are
listed in docs/governed-cleaning.md as deferred.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from data_ops_lab.governed_cleaning import (
    ALLOWED_TRANSITIONS,
    CONFIDENCE_FORMULA_VERSION,
    CONTRACT_VERSION,
    OPERATION_GOVERNANCE,
    POLICY_VERSION,
    ApprovedTransformation,
    AuthorityKind,
    CleaningPolicy,
    ConfiguredAuthority,
    DecisionKind,
    GovernanceClass,
    NonCanonicalPayloadError,
    PolicyOperation,
    ReviewState,
    TransformationCandidate,
    TransformationDecision,
    TransformationEvidence,
    TransformationOperation,
    authorize_application,
    authorize_configured,
    build_candidate,
    build_lineage,
    candidate_hash,
    canonical_json,
    compute_confidence,
    decision_hash,
    governance_class_for,
    is_aware_iso_timestamp,
    is_canonical_payload,
    operation_table_authority_hash,
    policy_hash,
    record_decision,
    sha256_of,
    submit_for_review,
    transition,
    validate_decision,
    validate_policy,
    verify_authority,
    verify_configured_authority,
)

SOURCE = "a" * 64
OTHER_SOURCE = "b" * 64
OUTPUT = "c" * 64
NOW = "2026-08-18T12:00:00Z"


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
        reviewed_at=NOW,
    )
    params.update(overrides)
    return TransformationDecision(**params)


def pending(cand: TransformationCandidate) -> TransformationCandidate:
    blockers: list[dict[str, str]] = []
    moved = submit_for_review(cand, blockers)
    assert moved is not None and blockers == []
    return moved


def approved(cand: TransformationCandidate, decision: TransformationDecision | None = None) -> TransformationCandidate:
    """The only legitimate route to the approved state."""
    blockers: list[dict[str, str]] = []
    result = record_decision(pending(cand), decision or approved_decision(cand), blockers)
    assert result is not None, blockers
    assert result.review_state is ReviewState.APPROVED
    return result


def policy(**overrides) -> CleaningPolicy:
    base = dict(
        dataset_id="customer_orders",
        configured_by="owner",
        configured_at="2026-08-18T14:00:00Z",
        operations=(
            PolicyOperation(TransformationOperation.TRIM_WHITESPACE, "orders", ("customer_code",)),
            PolicyOperation(
                TransformationOperation.NORMALIZE_BLANK_SENTINEL, "orders", ("notes",),
                {"sentinels": ["", "N/A"]},
            ),
        ),
    )
    base.update(overrides)
    return CleaningPolicy(**base)


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
# approved is real authority, not a label
# --------------------------------------------------------------------------- #


def test_pending_candidate_has_no_authority_even_with_a_valid_approved_decision():
    """The documented machine is candidate -> pending_review -> approved ->
    applied. Authority exists only in the approved state; a valid decision
    that has not been recorded grants nothing yet."""
    c = pending(candidate())
    d = approved_decision(c)
    blockers: list[dict[str, str]] = []
    assert validate_decision(c, d, [])  # the decision itself is fine
    assert authorize_application(c, d, SOURCE, blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["candidate_not_approved"]


def test_record_decision_is_the_only_route_to_approved():
    c = pending(candidate())
    d = approved_decision(c)
    blockers: list[dict[str, str]] = []
    moved = record_decision(c, d, blockers)
    assert moved is not None and blockers == []
    assert moved.review_state is ReviewState.APPROVED
    assert candidate_hash(moved) == candidate_hash(c)  # hash excludes review_state
    assert candidate_hash(moved) == d.candidate_sha256  # so the decision still binds


def test_record_decision_moves_rejected_to_terminal_rejected():
    c = pending(candidate())
    d = approved_decision(c, decision=DecisionKind.REJECTED)
    blockers: list[dict[str, str]] = []
    moved = record_decision(c, d, blockers)
    assert moved is not None and moved.review_state is ReviewState.REJECTED and blockers == []
    assert authorize_application(moved, d, SOURCE, blockers) is None
    assert "candidate_not_approved" in {b["blocker_type"] for b in blockers}


@pytest.mark.parametrize("state", [ReviewState.CANDIDATE, ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.APPLIED])
def test_record_decision_requires_pending_review(state):
    c = dataclasses.replace(candidate(), review_state=state)
    blockers: list[dict[str, str]] = []
    assert record_decision(c, approved_decision(c), blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["candidate_not_reviewable"]


def test_record_decision_refuses_a_decision_bound_to_another_candidate():
    c = pending(candidate())
    tampered = dataclasses.replace(c, parameters={"format": "%d/%m/%Y"})
    blockers: list[dict[str, str]] = []
    assert record_decision(tampered, approved_decision(c), blockers) is None
    assert "decision_hash_mismatch" in {b["blocker_type"] for b in blockers}
    assert tampered.review_state is ReviewState.PENDING_REVIEW  # unchanged


def test_approved_candidate_with_its_decision_yields_exact_authority():
    c = approved(candidate())
    d = approved_decision(c)
    blockers: list[dict[str, str]] = []
    auth = authorize_application(c, d, SOURCE, blockers)
    assert isinstance(auth, ApprovedTransformation)
    assert blockers == []
    assert auth.authority_kind is AuthorityKind.HUMAN_DECISION
    assert auth.candidate_sha256 == candidate_hash(c)
    assert auth.decision_sha256 == decision_hash(d)
    assert auth.effective_parameters == c.parameters
    assert verify_authority(auth, current_source_sha256=SOURCE, blockers=blockers)
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


def test_value_changing_normalizations_are_configured_only_not_automatic():
    """'-', '--', 'NA' can be legitimate values, and ' ABC ' -> 'ABC' can
    collapse codes that differ only by padding. Neither runs by default."""
    assert governance_class_for(TransformationOperation.NORMALIZE_BLANK_SENTINEL) is GovernanceClass.CONFIGURED_ONLY
    assert governance_class_for(TransformationOperation.TRIM_WHITESPACE) is GovernanceClass.CONFIGURED_ONLY


def test_only_name_level_structural_operations_are_safe_automatic():
    safe = {op for op, cls in OPERATION_GOVERNANCE.items() if cls is GovernanceClass.SAFE_AUTOMATIC}
    assert safe == {TransformationOperation.NORMALIZE_COLUMN_NAME}


def test_safe_automatic_authority_is_the_versioned_table_entry():
    h = operation_table_authority_hash(TransformationOperation.NORMALIZE_COLUMN_NAME)
    assert h == operation_table_authority_hash(TransformationOperation.NORMALIZE_COLUMN_NAME)
    assert h == sha256_of({
        "authority_kind": AuthorityKind.OPERATION_TABLE, "contract_version": CONTRACT_VERSION,
        "operation": TransformationOperation.NORMALIZE_COLUMN_NAME, "governance_class": GovernanceClass.SAFE_AUTOMATIC,
    })


def test_unknown_operation_is_rejected_before_it_carries_state():
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="t.c.x", source_sha256=SOURCE, table="t", column="c",
        operation="coerce_everything", parameters={}, evidence=evidence(), blockers=blockers,
    )
    assert built is None
    assert [b["blocker_type"] for b in blockers] == ["unknown_transformation_operation"]


def test_a_human_decision_cannot_authorize_a_non_governed_operation():
    """Each class has exactly one authority mechanism. A decision on a
    configured_only candidate is refused so the mechanism stays unambiguous."""
    c = approved(candidate(candidate_id="orders.notes.trim", column="notes",
                          operation=TransformationOperation.TRIM_WHITESPACE, parameters={}))
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, approved_decision(c), SOURCE, blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["decision_authority_wrong_class"]


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
        candidate_id="orders.invoice_date.parse_date", source_sha256=SOURCE, table="orders", column="invoice_date",
        operation=TransformationOperation.PARSE_DATE, parameters={}, evidence=evidence(), blockers=blockers,
        proposed_confidence=0.99,
    )
    assert built is not None
    assert built.computed_confidence == compute_confidence(evidence())
    assert built.computed_confidence != 0.99
    assert [b["blocker_type"] for b in blockers] == ["proposed_confidence_ignored"]


def test_matching_proposed_confidence_raises_no_blocker():
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="orders.invoice_date.parse_date", source_sha256=SOURCE, table="orders", column="invoice_date",
        operation=TransformationOperation.PARSE_DATE, parameters={}, evidence=evidence(), blockers=blockers,
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
    failures, and no path applies it without a recorded approval."""
    ev = evidence(values_examined=10, non_null_count=10, candidate_count=10,
                  success_count=9, failure_count=1, ambiguous_count=0, metrics={})
    blockers: list[dict[str, str]] = []
    built = build_candidate(
        candidate_id="t.amount.parse_number", source_sha256=SOURCE, table="t", column="amount",
        operation=TransformationOperation.PARSE_NUMBER, parameters={}, evidence=ev, blockers=blockers,
    )
    assert built is not None
    assert built.governance_class is GovernanceClass.GOVERNED
    assert built.review_state is ReviewState.CANDIDATE
    assert built.computed_confidence == 0.9
    assert authorize_application(built, approved_decision(built), SOURCE, blockers) is None
    assert "candidate_not_approved" in {b["blocker_type"] for b in blockers}


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
    assert len(blockers) == 1


# --------------------------------------------------------------------------- #
# Canonical hash domain
# --------------------------------------------------------------------------- #


def test_canonical_json_is_order_independent_and_ascii():
    a = canonical_json({"b": [1, 2.5, "x", None, True], "a": {"z": 1, "y": (1, 2)}})
    b = canonical_json({"a": {"y": [1, 2], "z": 1}, "b": [1, 2.5, "x", None, True]})
    assert a == b == '{"a":{"y":[1,2],"z":1},"b":[1,2.5,"x",null,true]}'
    assert canonical_json({"k": "é"}) == '{"k":"\\u00e9"}'


@pytest.mark.parametrize(
    "payload",
    [
        {"tags": {"b", "a"}},                     # set: iteration order not process-stable
        {"tags": frozenset({"b", "a"})},
        {1: "one"},                                # non-string key
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": -float("inf")},
        {"x": object()},
        {"x": b"bytes"},
        {"nested": {"deep": [1, {"s": {"a"}}]}},   # rejected at depth
    ],
)
def test_values_outside_the_canonical_domain_are_rejected(payload):
    assert not is_canonical_payload(payload)
    with pytest.raises(NonCanonicalPayloadError):
        canonical_json(payload)
    with pytest.raises(NonCanonicalPayloadError):
        sha256_of(payload)


def test_canonical_domain_accepts_exactly_json_scalars_lists_and_string_keyed_maps():
    assert is_canonical_payload({"n": None, "b": False, "i": 0, "f": 1.5, "s": "", "l": [], "t": (), "m": {}})
    assert is_canonical_payload({"deep": [{"k": [1, [2, [3]]]}]})


def test_non_canonical_candidate_parameters_are_a_blocker():
    blockers: list[dict[str, str]] = []
    assert build_candidate(
        candidate_id="t.c.parse_number", source_sha256=SOURCE, table="t", column="c",
        operation=TransformationOperation.PARSE_NUMBER, parameters={"formats": {"a", "b"}},
        evidence=evidence(), blockers=blockers,
    ) is None
    assert [b["blocker_type"] for b in blockers] == ["non_canonical_payload"]
    assert blockers[0]["field"] == "parameters"


def test_non_canonical_modified_parameters_are_a_blocker():
    c = pending(candidate())
    d = approved_decision(c, decision=DecisionKind.MODIFIED, modified_parameters={"formats": {"a"}})
    blockers: list[dict[str, str]] = []
    assert record_decision(c, d, blockers) is None
    assert "non_canonical_payload" in {b["blocker_type"] for b in blockers}


def test_non_finite_evidence_metric_is_a_blocker():
    blockers: list[dict[str, str]] = []
    assert build_candidate(
        candidate_id="t.c.parse_number", source_sha256=SOURCE, table="t", column="c",
        operation=TransformationOperation.PARSE_NUMBER, parameters={},
        evidence=evidence(metrics={"iso_ratio": math.nan}), blockers=blockers,
    ) is None
    assert "invalid_evidence_metric" in {b["blocker_type"] for b in blockers}


# --------------------------------------------------------------------------- #
# Hash binding
# --------------------------------------------------------------------------- #


def test_candidate_hash_is_deterministic_and_independent_of_dict_order():
    a = candidate(parameters={"format": "%Y-%m-%d", "dayfirst": False})
    b = candidate(parameters={"dayfirst": False, "format": "%Y-%m-%d"})
    assert candidate_hash(a) == candidate_hash(b)


def test_candidate_hash_excludes_review_state():
    c = candidate()
    assert candidate_hash(c) == candidate_hash(pending(c)) == candidate_hash(approved(c))


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
    original = approved(candidate())
    decision = approved_decision(original)
    tampered = dataclasses.replace(original, **{field_name: new_value})
    blockers: list[dict[str, str]] = []
    assert authorize_application(tampered, decision, tampered.source_sha256, blockers) is None
    assert "decision_hash_mismatch" in {b["blocker_type"] for b in blockers}


def test_evidence_change_breaks_the_decision_binding():
    original = approved(candidate())
    decision = approved_decision(original)
    tampered = dataclasses.replace(original, evidence=evidence(ambiguous_count=4))
    blockers: list[dict[str, str]] = []
    assert authorize_application(tampered, decision, SOURCE, blockers) is None
    assert "decision_hash_mismatch" in {b["blocker_type"] for b in blockers}


# --------------------------------------------------------------------------- #
# Governed authority
# --------------------------------------------------------------------------- #


def test_rejected_decision_grants_no_authority():
    """Invariant: rejected never alters a value - there is nothing to apply.
    Even a forged approved-state candidate with a rejected decision is refused."""
    c = dataclasses.replace(candidate(), review_state=ReviewState.APPROVED)
    d = approved_decision(c, decision=DecisionKind.REJECTED)
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, d, SOURCE, blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["decision_rejected"]


def test_source_change_voids_a_prior_approval():
    """Invariant: a source change invalidates the earlier approval."""
    c = approved(candidate())
    d = approved_decision(c)
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, d, OTHER_SOURCE, blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["source_changed_since_review"]


def test_source_drift_after_authority_is_caught_by_verify():
    c = approved(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert not verify_authority(auth, current_source_sha256=OTHER_SOURCE, blockers=blockers)
    assert "source_changed_since_review" in {b["blocker_type"] for b in blockers}


@pytest.mark.parametrize(
    "field_name, new_value",
    [
        ("effective_parameters", {"format": "%d/%m/%Y"}),
        ("table", "secret_table"),
        ("column", "ssn"),
        ("candidate_id", "orders.other.parse_date"),
        ("operation", TransformationOperation.PARSE_NUMBER),
        ("source_sha256", OTHER_SOURCE),
        ("candidate_sha256", "d" * 64),
        ("decision_sha256", "e" * 64),
    ],
)
def test_tampered_authority_record_fails_self_check(field_name, new_value):
    """Regression: the human-decision authority hash must bind everything the
    application acts on, including table and column, symmetric with the
    configured authority. A record retargeted to another column must not
    verify clean and poison lineage."""
    c = approved(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    forged = dataclasses.replace(auth, **{field_name: new_value})
    blockers: list[dict[str, str]] = []
    assert not verify_authority(forged, current_source_sha256=forged.source_sha256, blockers=blockers)
    assert "authority_hash_mismatch" in {b["blocker_type"] for b in blockers}


def test_submit_for_review_is_the_only_legal_first_move():
    c = candidate()
    blockers: list[dict[str, str]] = []
    moved = submit_for_review(c, blockers)
    assert moved is not None and moved.review_state is ReviewState.PENDING_REVIEW and blockers == []
    for state in (ReviewState.PENDING_REVIEW, ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.APPLIED):
        blockers = []
        assert submit_for_review(dataclasses.replace(c, review_state=state), blockers) is None
        assert [b["blocker_type"] for b in blockers] == ["illegal_review_transition"]


def test_review_state_is_a_projection_the_decision_is_the_authority():
    """Documented limit: in-process a frozen field can be replaced, so a forged
    approved state with a genuine decision grants authority - because the
    decision is the human artifact and it is what binds. A forged state with
    no valid decision grants nothing. The engine derives state from persisted
    decision records and never stores approved as free-standing authority."""
    c = candidate()
    forged_state = dataclasses.replace(c, review_state=ReviewState.APPROVED)
    blockers: list[dict[str, str]] = []
    # genuine decision -> authority (the decision, not the state, is what binds)
    assert authorize_application(forged_state, approved_decision(c), SOURCE, blockers) is not None
    # forged decision hash -> refused
    blockers = []
    assert authorize_application(forged_state, approved_decision(c, candidate_sha256="f" * 64), SOURCE, blockers) is None
    assert "decision_hash_mismatch" in {b["blocker_type"] for b in blockers}


def test_modified_decision_binds_the_reviewer_parameters_not_the_proposal():
    base = candidate()
    d = approved_decision(base, decision=DecisionKind.MODIFIED, modified_parameters={"format": "%d/%m/%Y"})
    c = approved(base, d)
    blockers: list[dict[str, str]] = []
    auth = authorize_application(c, d, SOURCE, blockers)
    assert auth is not None and blockers == []
    assert auth.effective_parameters == {"format": "%d/%m/%Y"}
    plain = authorize_application(approved(base), approved_decision(base), SOURCE, [])
    assert plain is not None
    assert plain.authority_sha256 != auth.authority_sha256


def test_modified_decision_without_parameters_is_invalid():
    c = pending(candidate())
    d = approved_decision(c, decision=DecisionKind.MODIFIED)
    blockers: list[dict[str, str]] = []
    assert not validate_decision(c, d, blockers)
    assert "modified_decision_without_parameters" in {b["blocker_type"] for b in blockers}


def test_decision_for_another_candidate_id_is_refused():
    c = approved(candidate())
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
    assert record_decision(c, approved_decision(c, reviewed_at=value), blockers) is None
    assert "invalid_reviewed_at" in {b["blocker_type"] for b in blockers}


@pytest.mark.parametrize("value", ["2026-08-18T12:00:00Z", "2026-08-18T12:00:00+00:00", "2026-08-18T14:00:00+02:00"])
def test_aware_iso_review_timestamp_is_accepted(value):
    assert is_aware_iso_timestamp(value)
    c = approved(candidate(), approved_decision(candidate(), reviewed_at=value))
    blockers: list[dict[str, str]] = []
    assert authorize_application(c, approved_decision(c, reviewed_at=value), SOURCE, blockers) is not None
    assert blockers == []


def test_same_source_and_same_decision_produce_the_same_authority():
    """Invariant: reproducibility of the authority record."""
    a1 = authorize_application(approved(candidate()), approved_decision(candidate()), SOURCE, [])
    a2 = authorize_application(approved(candidate()), approved_decision(candidate()), SOURCE, [])
    assert a1 == a2


# --------------------------------------------------------------------------- #
# Cleaning policy: configured_only authority
# --------------------------------------------------------------------------- #


def test_valid_policy_grants_exact_scoped_authority():
    p = policy()
    blockers: list[dict[str, str]] = []
    auth = authorize_configured(
        p, source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL,
        table="orders", column="notes", blockers=blockers,
    )
    assert isinstance(auth, ConfiguredAuthority) and blockers == []
    assert auth.authority_kind is AuthorityKind.CLEANING_POLICY
    assert auth.policy_sha256 == policy_hash(p)
    assert auth.dataset_id == "customer_orders"
    assert auth.effective_parameters == {"sentinels": ["", "N/A"]}
    assert verify_configured_authority(auth, current_source_sha256=SOURCE, blockers=blockers)
    assert blockers == []


def test_policy_scope_is_exact_per_table_and_column():
    p = policy()
    for table, column in (("orders", "customer_name"), ("invoices", "notes")):
        blockers: list[dict[str, str]] = []
        assert authorize_configured(
            p, source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL,
            table=table, column=column, blockers=blockers,
        ) is None
        assert [b["blocker_type"] for b in blockers] == ["operation_not_configured"]


def test_policy_scope_is_exact_per_operation():
    """trim_whitespace is configured for customer_code; blank normalization is not."""
    blockers: list[dict[str, str]] = []
    assert authorize_configured(
        policy(), source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL,
        table="orders", column="customer_code", blockers=blockers,
    ) is None
    assert [b["blocker_type"] for b in blockers] == ["operation_not_configured"]


@pytest.mark.parametrize("op", [TransformationOperation.PARSE_DATE, TransformationOperation.PARSE_NUMBER, TransformationOperation.NORMALIZE_COLUMN_NAME])
def test_policy_may_only_configure_configured_only_operations(op):
    """A governed op needs a decision; a safe op needs nothing. Listing either
    would blur which mechanism granted authority."""
    p = policy(operations=(PolicyOperation(op, "orders", ("x",)),))
    blockers: list[dict[str, str]] = []
    assert not validate_policy(p, blockers)
    assert "policy_operation_not_configurable" in {b["blocker_type"] for b in blockers}
    blockers = []
    assert authorize_configured(policy(), source_sha256=SOURCE, operation=op, table="orders", column="x", blockers=blockers) is None
    assert "policy_operation_not_configurable" in {b["blocker_type"] for b in blockers}


def test_policy_hash_changes_with_any_configured_parameter():
    a = policy()
    b = policy(operations=(
        a.operations[0],
        dataclasses.replace(a.operations[1], parameters={"sentinels": ["", "N/A", "-"]}),
    ))
    assert policy_hash(a) != policy_hash(b)
    auth_a = authorize_configured(a, source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL, table="orders", column="notes", blockers=[])
    auth_b = authorize_configured(b, source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL, table="orders", column="notes", blockers=[])
    assert auth_a is not None and auth_b is not None
    assert auth_a.authority_sha256 != auth_b.authority_sha256


def test_configured_authority_is_void_after_source_change():
    auth = authorize_configured(policy(), source_sha256=SOURCE, operation=TransformationOperation.TRIM_WHITESPACE, table="orders", column="customer_code", blockers=[])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert not verify_configured_authority(auth, current_source_sha256=OTHER_SOURCE, blockers=blockers)
    assert "source_changed_since_review" in {b["blocker_type"] for b in blockers}


def test_tampered_configured_authority_fails_self_check():
    auth = authorize_configured(policy(), source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL, table="orders", column="notes", blockers=[])
    assert auth is not None
    forged = dataclasses.replace(auth, effective_parameters={"sentinels": ["", "N/A", "-", "--"]})
    blockers: list[dict[str, str]] = []
    assert not verify_configured_authority(forged, current_source_sha256=SOURCE, blockers=blockers)
    assert "authority_hash_mismatch" in {b["blocker_type"] for b in blockers}


def test_policy_canonical_check_runs_even_when_the_operation_is_unknown():
    p = policy(operations=(PolicyOperation("not_an_operation", "orders", ("x",), {"s": {"a"}}),))  # type: ignore[arg-type]
    blockers: list[dict[str, str]] = []
    assert not validate_policy(p, blockers)
    assert {"unknown_transformation_operation", "non_canonical_payload"} <= {b["blocker_type"] for b in blockers}


def test_policy_validation_rejects_structural_defects():
    cases = {
        "unsupported_policy_version": policy(policy_version=POLICY_VERSION + 1),
        "invalid_dataset_identifier": policy(dataset_id="customer orders"),
        "missing_policy_author": policy(configured_by=" "),
        "invalid_configured_at": policy(configured_at="2026-08-18T14:00:00"),
        "empty_policy": policy(operations=()),
        "empty_policy_scope": policy(operations=(PolicyOperation(TransformationOperation.TRIM_WHITESPACE, "orders", ()),)),
        "duplicate_policy_scope": policy(operations=(
            PolicyOperation(TransformationOperation.TRIM_WHITESPACE, "orders", ("a", "a")),
        )),
        "non_canonical_payload": policy(operations=(
            PolicyOperation(TransformationOperation.NORMALIZE_BLANK_SENTINEL, "orders", ("notes",), {"sentinels": {"", "N/A"}}),
        )),
    }
    for expected, p in cases.items():
        blockers: list[dict[str, str]] = []
        assert not validate_policy(p, blockers), expected
        assert expected in {b["blocker_type"] for b in blockers}, (expected, blockers)


def test_same_policy_and_source_produce_the_same_configured_authority():
    a = authorize_configured(policy(), source_sha256=SOURCE, operation=TransformationOperation.TRIM_WHITESPACE, table="orders", column="customer_code", blockers=[])
    b = authorize_configured(policy(), source_sha256=SOURCE, operation=TransformationOperation.TRIM_WHITESPACE, table="orders", column="customer_code", blockers=[])
    assert a == b


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #


def test_lineage_from_a_human_decision_names_that_authority():
    c = approved(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    lineage = build_lineage(auth, output_sha256=OUTPUT, rows_examined=1240, rows_changed=1228, applied_at=NOW, blockers=blockers)
    assert lineage is not None and blockers == []
    assert lineage.authority_kind is AuthorityKind.HUMAN_DECISION
    assert (lineage.source_sha256, lineage.authority_sha256, lineage.output_sha256) == (SOURCE, auth.authority_sha256, OUTPUT)


def test_lineage_from_a_policy_names_that_authority():
    """Closes 'who authorized N/A to become null in this dataset?' mechanically:
    the lineage points at the policy-derived authority hash."""
    auth = authorize_configured(policy(), source_sha256=SOURCE, operation=TransformationOperation.NORMALIZE_BLANK_SENTINEL, table="orders", column="notes", blockers=[])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    lineage = build_lineage(auth, output_sha256=OUTPUT, rows_examined=1240, rows_changed=7, applied_at=NOW, blockers=blockers)
    assert lineage is not None and blockers == []
    assert lineage.authority_kind is AuthorityKind.CLEANING_POLICY
    assert lineage.authority_sha256 == auth.authority_sha256
    assert (lineage.table, lineage.column, lineage.operation) == ("orders", "notes", TransformationOperation.NORMALIZE_BLANK_SENTINEL)


def test_lineage_rejects_impossible_counts_and_bad_hashes():
    c = approved(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert build_lineage(auth, output_sha256=OUTPUT, rows_examined=10, rows_changed=11, applied_at=NOW, blockers=blockers) is None
    assert build_lineage(auth, output_sha256="nothex", rows_examined=10, rows_changed=1, applied_at=NOW, blockers=blockers) is None
    types = {b["blocker_type"] for b in blockers}
    assert {"inconsistent_lineage", "invalid_output_sha256"} <= types


def test_lineage_rejects_naive_applied_timestamp():
    c = approved(candidate())
    auth = authorize_application(c, approved_decision(c), SOURCE, [])
    assert auth is not None
    blockers: list[dict[str, str]] = []
    assert build_lineage(auth, output_sha256=OUTPUT, rows_examined=10, rows_changed=1, applied_at="2026-08-18T12:05:00", blockers=blockers) is None
    assert [b["blocker_type"] for b in blockers] == ["invalid_applied_at"]
