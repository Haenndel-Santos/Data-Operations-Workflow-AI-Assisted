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
human decision          grants, modifies, or refuses authority
deterministic code      applies only what was granted; records lineage
```

The same split the analytics side already uses for translation, planning, and
execution.

## Governance Classes

Not every transformation deserves review; not every transformation may skip
it. The class is decided by the operation, and the table in the module is
authority. An operation absent from it is rejected before it can carry state.

| Class | Meaning | Operations |
| --- | --- | --- |
| `safe_automatic` | Structural and value-preserving; may run without review | `normalize_column_name`, `trim_whitespace` |
| `configured_only` | Runs automatically only when the deployment or dataset policy explicitly enables it; never by default | `normalize_blank_sentinel` |
| `governed` | Always a candidate; requires an approved or modified decision bound to the exact candidate hash | `parse_number`, `parse_date`, `interpret_decimal_separator`, `interpret_locale`, `canonicalize_identifier`, `remap_category` |

`normalize_blank_sentinel` is deliberately not automatic. The legacy set
`{"", " ", "na", "n/a", "none", "null", "-", "--"}` erases values that can be
legitimate in a business dataset (`"-"` as a code, `"NA"` as a region).

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

### TransformationLineage

`source_sha256`, `authority_sha256`, `output_sha256`, `table`, `column`,
`operation`, `rows_examined`, `rows_changed`, `applied_at` (ISO-8601 with
explicit offset; `invalid_applied_at` otherwise).

## States

```text
candidate -> pending_review -> approved -> applied
                            -> rejected
```

`rejected` and `applied` are terminal. `candidate -> applied` does not exist.
The transition table in the module is the only source of legal moves; an
illegal move returns the unchanged state with an `illegal_review_transition`
blocker.

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
| `authority_sha256` | candidate hash, decision hash, source hash, operation, effective parameters | - |

Serialization is canonical JSON: sorted keys, no whitespace, ASCII. Parameter
dictionaries hash the same regardless of insertion order.

## Authority Rules

`authorize_application(candidate, decision, current_source_sha256)` returns an
`ApprovedTransformation` or nothing plus blockers. It refuses when:

| Condition | Blocker |
| --- | --- |
| Candidate not in `pending_review` or `approved` | `candidate_not_reviewable` |
| Decision names another candidate id | `decision_candidate_mismatch` |
| Decision hash does not match the candidate | `decision_hash_mismatch` |
| Decision is `rejected` | `decision_rejected` |
| Source hash differs from the candidate's | `source_changed_since_review` |
| Governed operation without approved/modified decision | `governed_operation_requires_approval` |
| Reviewer missing, or `reviewed_at` missing/naive/malformed | `missing_reviewer`, `missing_review_timestamp`, `invalid_reviewed_at` |
| Modified decision without parameters, or parameters on a non-modified decision | `modified_decision_without_parameters`, `unexpected_modified_parameters` |

Every refusal is fail-closed. There is no partial authority.

`build_candidate` judges a candidate only by the blockers it raised itself.
The blocker list is the repository's shared accumulator; an engine looping over
columns with one list must not lose a later valid candidate because an
earlier, unrelated one failed. This is pinned by
`test_shared_blocker_accumulator_does_not_drop_later_valid_candidates`.

`verify_authority(approved, current_source_sha256)` rechecks the authority
record right before application: source drift and a tampered record are both
blockers.

## Invariants Proven By The Contract Tests

| # | Property | Where proven |
| --- | --- | --- |
| 1 | No authority exists without an approved or modified decision | `test_pending_candidate_with_approved_decision_yields_exact_authority`, `test_the_ninety_percent_coercion_case_stays_a_governed_candidate` |
| 2 | A rejected decision grants no authority | `test_rejected_decision_grants_no_authority` |
| 3 | Only the exact approved candidate hash can be applied | `test_any_reviewed_field_change_breaks_the_decision_binding` (parametrized over every reviewed field), `test_evidence_change_breaks_the_decision_binding` |
| 4 | A source change voids a prior approval | `test_source_change_voids_a_prior_approval`, `test_source_drift_after_authority_is_caught_by_verify` |
| 5 | Same source and same decision produce the same authority | `test_same_source_and_same_decision_produce_the_same_authority`, `test_candidate_hash_is_deterministic_and_independent_of_dict_order` |
| 6 | Output receives hash and lineage | `test_lineage_binds_source_authority_and_output` |
| 8 | Confidence is computed, never accepted | `test_proposed_confidence_is_ignored_and_the_discrepancy_is_recorded`, `test_confidence_is_a_pure_function_of_evidence` |
| 9 | Ambiguous coercion stays a candidate | `test_semantic_coercions_are_always_governed`, `test_the_ninety_percent_coercion_case_stays_a_governed_candidate` |
| 10 | Legacy cleaner behaviourally unchanged | `tests/legacy_cleaner_characterization_test.py` (9 pinned behaviours) |
| - | Audit timestamps are timezone-aware ISO-8601 | `test_naive_or_malformed_review_timestamp_is_rejected`, `test_aware_iso_review_timestamp_is_accepted`, `test_lineage_rejects_naive_applied_timestamp` |
| - | A shared blocker accumulator cannot drop later valid candidates | `test_shared_blocker_accumulator_does_not_drop_later_valid_candidates` |
| - | `candidate -> applied` does not exist | `test_candidate_can_never_reach_applied_without_approval` |
| - | Blank sentinel normalization is not automatic | `test_blank_sentinel_normalization_is_configured_only_not_automatic` |

## Deferred To The Engine Increment

These properties need real data flow and are not claimed by this contract:

| # | Property | Mechanism the engine will use |
| --- | --- | --- |
| 1 | `pending_review` never alters a value on disk | Engine applies only `ApprovedTransformation`; nothing else reaches the apply function |
| 2 | `rejected` never alters a value on disk | Same |
| 5 | Same source + same approval produce byte-identical output | Deterministic application over Parquet; output hash recorded in lineage |
| 7 | Partial failure does not promote incomplete output | `contracts.atomic_publish.publish_new_directory` |
| 10 | Legacy path byte-for-byte unchanged | Characterization tests here plus a golden-file comparison over the sample dataset |

The engine will live beside `cleaner.py` as an opt-in route
(`propose_transformations`, `validate_review`, `apply_approved_transformations`,
`write_cleaning_lineage`), reachable through separate CLI commands. The legacy
workflow keeps working exactly as today while equivalence and safety evidence
is built.

## Environment Note

The legacy cleaner's behaviour depends on the pandas major version. Under
pandas 3 the default string dtype is `str`, so the legacy checks
`dtype == "object"` and `str(dtype) == "string"` are both false: blank
normalization, trimming, and numeric coercion do not fire on freshly-read
string columns, while name-based date parsing still does. `pyproject.toml`
leaves pandas unpinned at `>=2.2.0`. This is recorded, not fixed, here; it is
one more reason the governed engine must not inherit the legacy branches.

## Related

- [AI Analytical Capability Matrix](ai-analytical-capability-matrix.md) - the
  cleaning philosophy this contract implements
- [Product Vision](product-vision.md)
- [Architecture](architecture.md)
- [Testing](testing.md)
