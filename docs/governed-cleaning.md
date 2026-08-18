# Governed Cleaning Contract

## Status

```yaml
version: 1
status: contract_and_invariants
module: src/data_ops_lab/governed_cleaning.py
engine: not_implemented
legacy_path: unchanged
```

This document defines the contract for governed data cleaning: what a
transformation candidate is, what evidence it carries, how confidence is
derived, how a human decision grants authority, and what lineage an
application leaves behind. The module implements the contract's types and its
pure authority functions. It performs no I/O and touches no DataFrame. The
engine that proposes candidates from real data and applies approved
transformations is a later, separate increment.

`run_workflow()` and `clean_dataframe()` are unchanged. Their current behaviour
is pinned by `tests/legacy_cleaner_characterization_test.py` so the engine
increment can prove the legacy path stayed identical.

## Why

The legacy cleaner alters data on heuristics with no evidence, review, or
lineage. Two of its behaviours, pinned as characterization tests, are the
concrete motivation:

| Behaviour | Effect |
| --- | --- |
| Numeric coercion when >= 90% of values parse | `["100", ..., "ABC"]` becomes `Int64` with `NA` where `"ABC"` was, silently |
| Date parsing chosen by column *name*, `dayfirst` chosen by an 80% ISO sample threshold | A date column with 7/9 ISO values gets `dayfirst=True`; under the installed pandas `2024-01-05` becomes `2024-05-01` |

The second is not a lost value; it is a wrong value with no trace. The Sprint 0
capability matrix already states the rule this contract enforces: AI or
heuristics may propose cleaning; a deterministic engine applies reviewed rules
with lineage.

## Authority Split

```text
heuristic or model      proposes an operation on a column
deterministic code      measures the evidence
deterministic code      computes the confidence from that evidence
human decision, or      grants, modifies, or refuses authority
dataset cleaning policy
deterministic code      applies only what was granted; records lineage
```

The same split the analytics side already uses for translation, planning, and
execution. Each governance class has exactly one authority mechanism, and the
lineage record names which one granted the application:

| Class | Authority mechanism | `authority_kind` in lineage |
| --- | --- | --- |
| `safe_automatic` | the versioned operation table entry | `operation_table` |
| `configured_only` | an exact, hash-bound dataset cleaning policy | `cleaning_policy` |
| `governed` | an exact, hash-bound human decision on an approved candidate | `human_decision` |

A human decision cannot authorize a configured or automatic operation
(`decision_authority_wrong_class`), and a policy cannot authorize a governed or
automatic one (`policy_operation_not_configurable`). The mechanism is never
ambiguous.

## Governance Classes

Not every transformation deserves review; not every transformation may skip
it. The class is decided by the operation, and the table in the module is
authority. An operation absent from it is rejected before it can carry state.

| Class | Meaning | Operations |
| --- | --- | --- |
| `safe_automatic` | Structural and name-level only; never changes a cell value; may run without review | `normalize_column_name` |
| `configured_only` | Changes cell values in a bounded, reversible way; runs only under an exact, hash-bound dataset cleaning policy; never by default | `trim_whitespace`, `normalize_blank_sentinel` |
| `governed` | Always a candidate; requires an approved or modified decision bound to the exact candidate hash | `parse_number`, `parse_date`, `interpret_decimal_separator`, `interpret_locale`, `canonicalize_identifier`, `remap_category` |

Neither value-changing normalization is automatic. `normalize_blank_sentinel`
with the legacy set `{"", " ", "na", "n/a", "none", "null", "-", "--"}` erases
values that can be legitimate in a business dataset (`"-"` as a code, `"NA"`
as a region). `trim_whitespace` is not value-preserving either: `" ABC "` and
`"ABC"` may be distinct codes, and trimming collapses them silently.
`normalize_column_name` stays automatic because it is structural: it renames
columns and the existing converter already resolves collisions with unique
names; it never touches a cell.

## Data Model

### TransformationEvidence

Deterministic measurements over the values the candidate would touch. Every
field is a count or ratio the engine can recompute from the same source.

| Field | Meaning |
| --- | --- |
| `values_examined` | Rows inspected |
| `non_null_count` | Rows with a value |
| `candidate_count` | Values the operation would attempt |
| `success_count` | Values the operation parses/maps unambiguously |
| `failure_count` | Values the operation cannot handle |
| `ambiguous_count` | Successes with more than one plausible reading (e.g. `03/04/2024`) |
| `metrics` | Operation-specific extra measurements (e.g. `iso_ratio`) |

Consistency is enforced: `non_null_count <= values_examined`,
`candidate_count <= non_null_count`, `success + failure == candidate`,
`ambiguous <= success`. Inconsistent evidence is a blocker, not a warning.

### TransformationCandidate

`candidate_id`, `source_sha256`, `table`, `column`, `operation`, `parameters`,
`evidence`, `computed_confidence`, `review_state`, plus `contract_version` and
`confidence_formula_version`.

### TransformationDecision

`candidate_id`, `candidate_sha256`, `decision` (`approved | rejected |
modified`), `reviewer`, `reviewed_at`, optional `modified_parameters`, `note`.

A `modified` decision must carry replacement parameters; any other decision
must not. `reviewed_at` must be ISO-8601 with an explicit UTC offset, the same
rule the semantic-approval module enforces (`invalid_reviewed_at` otherwise);
naive local time is ambiguous evidence.

### ApprovedTransformation

The exact authority to apply: `candidate_sha256`, `decision_sha256`,
`source_sha256`, `operation`, `effective_parameters`, and an
`authority_sha256` binding all of them. `effective_parameters` are the
candidate's for an approved decision and the reviewer's for a modified one, so
a modified decision produces a different authority hash than a plain approval
of the same candidate.

### CleaningPolicy and PolicyOperation

Dataset-scoped authority for `configured_only` operations. Deployment defaults
may propose or pre-populate a policy; only this versioned, hash-bound object
grants authority, and only for the dataset, tables, and columns it names.

```yaml
policy_version: 1
dataset_id: customer_orders
configured_by: owner
configured_at: 2026-08-18T14:00:00Z
operations:
  - operation: trim_whitespace
    table: orders
    columns: [customer_code]
  - operation: normalize_blank_sentinel
    table: orders
    columns: [notes]
    parameters:
      sentinels: ["", "N/A"]
```

Validation (`validate_policy`): version 1; identifier-shaped `dataset_id`;
non-empty `configured_by`; timezone-aware `configured_at`; at least one
operation; every operation `configured_only` (`policy_operation_not_configurable`
otherwise); identifier-shaped tables and columns; at least one column per
entry; no duplicate `(operation, table, column)` scope; canonical parameters.

### ConfiguredAuthority

The exact authority to apply one `configured_only` operation on one column:
`policy_sha256`, `dataset_id`, `source_sha256`, `table`, `column`, `operation`,
`effective_parameters`, and

```text
authority_sha256 = sha256(policy_sha256 + source_sha256 + dataset_id
                          + operation + table + column + effective_parameters)
```

`authorize_configured` refuses when the policy is invalid, the operation is not
`configured_only`, or the policy does not name this exact scope
(`operation_not_configured`). Changing any configured parameter changes the
policy hash and therefore the authority hash. This closes mechanically the
question of who authorized `N/A` to become null in this dataset: the lineage
points at a policy hash, and the policy names its author and time.

### TransformationLineage

`source_sha256`, `authority_kind`, `authority_sha256`, `output_sha256`,
`table`, `column`, `operation`, `rows_examined`, `rows_changed`, `applied_at`
(ISO-8601 with explicit offset; `invalid_applied_at` otherwise). Lineage
points at exactly one authority record; `authority_kind` says which mechanism
produced it.

## States

```text
candidate -> pending_review -> approved -> applied
                            -> rejected
```

`rejected` and `applied` are terminal. `candidate -> applied` does not exist.
The transition table in the module is the only source of legal moves; an
illegal move returns the unchanged state with an `illegal_review_transition`
blocker.

`approved` is real authority, not a label. `submit_for_review` is the API for
the first move and `record_decision` is the API route into `approved`: it
requires `pending_review`, validates the decision against the exact candidate
hash, and moves the candidate to `approved` (for an approved or modified
decision) or `rejected`. `authorize_application` then requires the candidate to
be `approved`; a valid decision that has not been recorded grants nothing
(`candidate_not_approved`). Because the candidate hash excludes
`review_state`, a decision recorded at `pending_review` keeps binding after the
transition.

Stated limit: `review_state` is a projection of the decision record, not
independent authority. In-process, a frozen dataclass field can be replaced,
so the state gate documents process; the security gate is the decision's
binding to the exact candidate hash, which is the human artifact itself. A
forged `approved` with a genuine decision grants exactly what that decision
grants; a forged state with no valid decision grants nothing. The engine
increment must derive state from persisted decision records and never store
`approved` as free-standing authority. This is pinned by
`test_review_state_is_a_projection_the_decision_is_the_authority`.

## Confidence

Confidence is a pure function of evidence. Nothing else may set it.

```text
formula version 1:
  success_ratio    = success_count / candidate_count
  ambiguity_ratio  = ambiguous_count / candidate_count
  confidence       = round(success_ratio * (1 - ambiguity_ratio), 4)
```

Worked example from the contract tests:

```yaml
evidence:
  values_examined: 1240
  non_null_count: 1240
  candidate_count: 1240
  success_count: 1228
  failure_count: 12
  ambiguous_count: 3
computed_confidence: 0.9879
```

A proposer may pass a `proposed_confidence` for transparency. It is never
stored. If it differs from the computed value, a `proposed_confidence_ignored`
blocker records the discrepancy and the computed value stands. Any failure or
ambiguity keeps confidence below `1.0`; no candidate values yields `0.0`.

The formula is versioned. Changing it changes `confidence_formula_version`,
which is part of the candidate hash, so a prior approval cannot silently
apply to a candidate scored differently.

## Hash Binding

| Hash | Covers | Excludes |
| --- | --- | --- |
| `candidate_sha256` | contract and formula versions, id, source hash, table, column, operation, parameters, evidence, computed confidence | `review_state` |
| `decision_sha256` | the whole decision | - |
| `authority_sha256` (human decision) | authority kind, candidate id, candidate hash, decision hash, source hash, table, column, operation, effective parameters | - |
| `policy_sha256` | the whole policy | - |
| `authority_sha256` (cleaning policy) | authority kind, policy hash, source hash, dataset, operation, table, column, effective parameters | - |
| operation-table authority | authority kind, contract version, operation, governance class | - |

### Canonical hash domain

Hash binding is the core invariant, so every payload that reaches a hash must
serialize identically in every process. Serialization is canonical JSON:
sorted keys, no whitespace, ASCII, `allow_nan=False`. The accepted domain is
exactly:

```text
null | bool | int | finite float | str | list (tuples become lists)
mapping with str keys
```

plus contract-owned enums (their value) and dataclasses (their fields).
Everything else is rejected with `non_canonical_payload` where the contract
accepts caller data (`parameters`, `modified_parameters`, policy parameters)
and with `invalid_evidence_metric` for evidence metrics. Sets and frozensets
are rejected on purpose: their iteration order is not process-stable, so a
hash over them would not be canonical. Non-string mapping keys and non-finite
floats are rejected because JSON has no faithful representation for them.
Parameter dictionaries hash the same regardless of insertion order.

## Authority Rules

`authorize_application(candidate, decision, current_source_sha256)` returns an
`ApprovedTransformation` or nothing plus blockers. It refuses when:

| Condition | Blocker |
| --- | --- |
| Candidate not `approved` (only `record_decision` reaches that state) | `candidate_not_approved` |
| Decision on a non-governed operation | `decision_authority_wrong_class` |
| Decision names another candidate id | `decision_candidate_mismatch` |
| Decision hash does not match the candidate | `decision_hash_mismatch` |
| Decision is `rejected` | `decision_rejected` |
| Source hash differs from the candidate's | `source_changed_since_review` |
| Reviewer missing, or `reviewed_at` missing/naive/malformed | `missing_reviewer`, `missing_review_timestamp`, `invalid_reviewed_at` |
| Modified decision without parameters, or parameters on a non-modified decision | `modified_decision_without_parameters`, `unexpected_modified_parameters` |
| `record_decision` on a candidate not in `pending_review` | `candidate_not_reviewable` |
| Authority record does not match its own bound content (`verify_authority`, `verify_configured_authority`) | `authority_hash_mismatch` |
| Structural defects in candidate, evidence, policy, or lineage inputs | `invalid_*`, `inconsistent_*`, `unknown_transformation_operation`, `unclassified_transformation_operation`, `empty_policy`, `empty_policy_scope`, `duplicate_policy_scope`, `unsupported_policy_version`, `missing_policy_author`, `missing_applied_timestamp` |

Every refusal is fail-closed. There is no partial authority.

`build_candidate` judges a candidate only by the blockers it raised itself.
The blocker list is the repository's shared accumulator; an engine looping over
columns with one list must not lose a later valid candidate because an
earlier, unrelated one failed. This is pinned by
`test_shared_blocker_accumulator_does_not_drop_later_valid_candidates`.

`verify_authority(approved, current_source_sha256)` rechecks the authority
record right before application: source drift and a tampered record are both
blockers.

## The D1 Invariant Checklist

The owner's checklist for this increment, numbered so the two tables below
can reference it. Items marked "on disk" need the engine; their contract-level
counterparts are proven here.

```text
 1. pending_review never alters a value            (contract: no authority; on disk: engine)
 2. rejected never alters a value                  (contract: no authority; on disk: engine)
 3. only the exact approved candidate hash applies
 4. a source change invalidates a prior approval
 5. same source + same approval -> same result     (contract: same authority; on disk: engine)
 6. output receives hash and lineage
 7. partial failure does not promote output        (engine)
 8. confidence is computed, never accepted
 9. ambiguous date/number coercion stays a candidate
10. legacy cleaner behaviourally unchanged         (characterization here; golden file: engine)
```

## Invariants Proven By The Contract Tests

| # | Property | Where proven |
| --- | --- | --- |
| 1 | No authority exists without a recorded approval; `approved` is a real state | `test_pending_candidate_has_no_authority_even_with_a_valid_approved_decision`, `test_record_decision_is_the_only_route_to_approved`, `test_approved_candidate_with_its_decision_yields_exact_authority`, `test_the_ninety_percent_coercion_case_stays_a_governed_candidate` |
| 2 | A rejected decision grants no authority | `test_rejected_decision_grants_no_authority` |
| 3 | Only the exact approved candidate hash can be applied | `test_any_reviewed_field_change_breaks_the_decision_binding` (parametrized over every reviewed field), `test_evidence_change_breaks_the_decision_binding` |
| 4 | A source change voids a prior approval | `test_source_change_voids_a_prior_approval`, `test_source_drift_after_authority_is_caught_by_verify` |
| 5 | Same source and same decision produce the same authority | `test_same_source_and_same_decision_produce_the_same_authority`, `test_candidate_hash_is_deterministic_and_independent_of_dict_order` |
| 6 | Output receives hash and lineage | `test_lineage_from_a_human_decision_names_that_authority`, `test_lineage_from_a_policy_names_that_authority` |
| - | A tampered authority record fails its own self-check on every bound field | `test_tampered_authority_record_fails_self_check` (parametrized over table, column, id, operation, source, hashes, parameters), `test_tampered_configured_authority_fails_self_check` |
| 8 | Confidence is computed, never accepted | `test_proposed_confidence_is_ignored_and_the_discrepancy_is_recorded`, `test_confidence_is_a_pure_function_of_evidence` |
| 9 | Ambiguous coercion stays a candidate | `test_semantic_coercions_are_always_governed`, `test_the_ninety_percent_coercion_case_stays_a_governed_candidate` |
| 10 | Legacy cleaner behaviourally unchanged | `tests/legacy_cleaner_characterization_test.py` (9 pinned behaviours) |
| - | Audit timestamps are timezone-aware ISO-8601 | `test_naive_or_malformed_review_timestamp_is_rejected`, `test_aware_iso_review_timestamp_is_accepted`, `test_lineage_rejects_naive_applied_timestamp` |
| - | A shared blocker accumulator cannot drop later valid candidates | `test_shared_blocker_accumulator_does_not_drop_later_valid_candidates` |
| - | `candidate -> applied` does not exist | `test_candidate_can_never_reach_applied_without_approval` |
| - | Value-changing normalizations are not automatic | `test_value_changing_normalizations_are_configured_only_not_automatic`, `test_only_name_level_structural_operations_are_safe_automatic` |
| - | Each class has exactly one authority mechanism | `test_a_human_decision_cannot_authorize_a_non_governed_operation`, `test_policy_may_only_configure_configured_only_operations` |
| - | Configured authority is exact per dataset, operation, table, column, and parameters | `test_valid_policy_grants_exact_scoped_authority`, `test_policy_scope_is_exact_per_table_and_column`, `test_policy_scope_is_exact_per_operation`, `test_policy_hash_changes_with_any_configured_parameter` |
| - | Lineage names its authority mechanism | `test_lineage_from_a_human_decision_names_that_authority`, `test_lineage_from_a_policy_names_that_authority` |
| - | The hash domain is canonical | `test_canonical_json_is_order_independent_and_ascii`, `test_values_outside_the_canonical_domain_are_rejected` (parametrized), `test_non_canonical_candidate_parameters_are_a_blocker` |

## Deferred To The Engine Increment

These properties need real data flow and are not claimed by this contract:

| # | Property | Mechanism the engine will use |
| --- | --- | --- |
| 1 | `pending_review` never alters a value on disk | Engine applies only `ApprovedTransformation`; nothing else reaches the apply function |
| 2 | `rejected` never alters a value on disk | Same |
| 5 | Same source + same approval produce byte-identical output | Deterministic application over Parquet; output hash recorded in lineage |
| 7 | Partial failure does not promote incomplete output | `contracts.atomic_publish.publish_new_directory` |
| 10 | Legacy path byte-for-byte unchanged | Characterization tests here plus a golden-file comparison over the sample dataset |

The engine will live beside `cleaner.py` as an opt-in route reachable through
three flat CLI commands, matching the repository's `analytics-semantic-*`
naming:

```text
governed-cleaning-propose      profile -> candidates with evidence and confidence
governed-cleaning-authorize    validate the human review and the cleaning policy;
                               turn decisions and policy into exact authority
governed-cleaning-apply        apply only authorized transformations; write lineage
```

The human review happens on the artifact between `propose` and `authorize`;
`authorize` is the command that validates it, which is why it is not called
`review`. The legacy workflow keeps working exactly as today while equivalence
and safety evidence is built.

## Environment Note

The legacy cleaner's behaviour depends on the pandas major version. Under
pandas 3 the default string dtype is `str`, so the legacy checks
`dtype == "object"` and `str(dtype) == "string"` are both false: blank
normalization, trimming, and numeric coercion do not fire on freshly-read
string columns, while name-based date parsing still does. `pyproject.toml`
leaves pandas unpinned at `>=2.2.0`. This is recorded, not fixed, here; it is
one more reason the governed engine must not inherit the legacy branches. The
decision is to pin `pandas>=3.0.3,<3.1` in a small separate dependency PR
before the engine increment - not to repair the legacy cleaner, but so the
frozen behaviour cannot change again because an installation resolved another
major or minor. The range is widened deliberately later, with tests.

## Related

- [AI Analytical Capability Matrix](ai-analytical-capability-matrix.md) - the
  cleaning philosophy this contract implements
- [Product Vision](product-vision.md)
- [Architecture](architecture.md)
- [Testing](testing.md)
