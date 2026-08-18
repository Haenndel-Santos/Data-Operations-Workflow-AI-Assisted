# Governed Cleaning Engine

## Status

```yaml
version: 1
status: implemented_opt_in
module: src/data_ops_lab/governed_cleaning_engine.py
contract: docs/governed-cleaning.md
cli:
  - governed-cleaning-propose
  - governed-cleaning-authorize
  - governed-cleaning-apply
legacy_path: unchanged
network_or_model_dependency: none
```

The engine turns the [Governed Cleaning Contract](governed-cleaning.md) into
an opt-in route that lives beside the legacy cleaner. `run_workflow()` and
`clean_dataframe()` are untouched; the engine never runs unless one of its
three commands is invoked explicitly, and none of them changes a source file.

## The Route

```text
PROPOSE     actual Parquet (+ optional source manifest)
            -> verify source inventory and hashes
            -> derive source_sha256 from the real files
            -> deterministic profiling
            -> proposal bundle: automatic and configured exact steps,
               governed candidates at pending_review, review template
            -> atomic publish; no value is changed

            [ human review happens on the artifact ]

AUTHORIZE   proposal bundle + exact review + cleaning policy
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
```

Discovery happens once, in `propose`. Authority is born once, in `authorize`.
`apply` never infers anything it was not handed.

## Source Verification

`source_sha256` is always derived from the real files: the SHA-256 of the
sorted list of `{path, sha256}` for every `.parquet` in the directory. A
source manifest, when given, is verified against those files: a different
inventory (`source_manifest_inventory_mismatch`) or a different hash
(`source_manifest_hash_mismatch`) is a blocker and zero candidates are
published. The manifest adds provenance; it never grants the hash.

Every later phase re-derives the hash from the current files and compares it
to the one the previous phase bound: `source_changed_since_proposal` and
`source_changed_since_authorization` stop the phase before any work.

## Propose

Deterministic per-column profiling of string-like columns:

| Finding | Governance class | What is published |
| --- | --- | --- |
| Column name is not `slugify(name)` | `safe_automatic` | exact automatic step `{operation, table, column, target}` |
| Values with leading/trailing whitespace | `configured_only` | exact configured step with observed count |
| Values matching an observed blank sentinel | `configured_only` | exact configured step with the sentinels observed |
| Values parseable as numbers (`≥ 50%`) | `governed` | candidate with evidence, computed confidence, `pending_review` |
| Values parseable as dates (`≥ 50%`, dominant format) | `governed` | candidate with evidence, computed confidence, `pending_review` |

The 50% threshold is proposer policy, not authority: below it the proposer
does not bother the reviewer. Dates are proposed with an explicit `format`
(`%Y-%m-%d`, `%d/%m/%Y`, or `%m/%d/%Y`, whichever parses more); slash dates
that parse under both day and month orders count as `ambiguous_count`. There
is no `dayfirst` heuristic anywhere in the engine.

A column whose name is not identifier-shaped receives only the automatic
rename in this cycle; the contract scopes value authority by identifier, so
value operations come in a later cycle over the renamed column. The rename
authority itself binds the exact raw source name under the contract's bounded
raw-name rule (`invalid_raw_column_name` otherwise); the target is
`slugify(name)`, derived by the engine. Two renames in one table that collapse
to the same target, or a target that collides with an existing column, are
`rename_target_collision` at authorize. On the converted-Parquet route the
converter has already normalized names, so the automatic list is normally
empty - verified per column, not assumed.

Every proposal carries a `proposal_id` (UUID) covered by `proposal_sha256`, so
two proposals over unchanged data are distinct artifacts even within the same
second.

Bundle:

```text
proposal/
├── proposal_manifest.yml   source hash, tables, automatic, configured, governed ids+hashes, proposal_sha256
├── candidates.yml          full candidate records, bound to proposal_sha256
├── review_template.yml     one empty decision row per governed candidate
├── blockers.csv
└── report.md
```

`proposal_sha256` covers the manifest content (including `proposal_id`,
`engine_version`, source files, tables, and every step); `candidates.yml` is
bound to it, and its governed list must match the manifest exactly.

## Authorize

Inputs: the proposal bundle, the current source, an optional completed review
(`--review`), an optional cleaning policy (`--policy`).

The review must name the exact proposal artifact: `review.proposal_sha256`
must equal the proposal manifest's; otherwise `review_proposal_hash_mismatch`.
Two proposals over unchanged data carry identical candidate hashes and are
still different artifacts - the human reviewed one of them. Proposals from
another `engine_version` are refused (`unsupported_engine_version`).

Dispositions, exactly as the contract states:

| Situation | Effect |
| --- | --- |
| Decision `approved` / `modified`, valid | `record_decision` → `authorize_application` → `ApprovedTransformation` |
| Decision `rejected`, valid | disposition recorded, zero authority |
| Decision missing or empty | `authorization_incomplete`; no apply-ready plan; **not a blocker** |
| Decision malformed, hash-mismatched, duplicate, or for an unknown candidate | blocker |
| Configured step named exactly by the policy | `authorize_configured` → `ConfiguredAuthority` |
| Configured step not named by the policy, or no policy | disposition `not_configured` / `no_policy`, zero authority |
| Policy defective (wrong class, bad scope, naive timestamp, …) | blocker |
| Automatic step | `build_automatic_authority` → `AutomaticAuthority` |

`approved` is derived from the decisions and never stored: candidates on disk
stay `pending_review`, and no bundle file carries `review_state: approved`.

### Application plan

Authorities are ordered canonically - value-changing operations first by
`(table, column, operation)`, column renames last, so every value step is
addressed by the source column name it was authorized for - and the ordered
list of authority hashes is hashed:

```text
application_plan_sha256 = sha256({version, source_sha256, steps: [authority_sha256, ...]})
```

Each plan step carries exactly `sequence` and `authority_sha256`. The plan is
authoritative only over order; every other fact about a step (kind, table,
column, operation, parameters) is read from the self-bound authority record it
references, so there is no redundant metadata that could disagree with the
authority. A step with any other key is refused at apply
(`invalid_application_plan`).

The plan is the exact executable projection of the **complete** authorized
bundle: every authority once, in canonical order. Apply recomputes
`_order_steps(all verified authorities)` and requires the plan's hash list to
equal it (`application_plan_authority_set_mismatch`). A plan that omits, adds,
repeats, or reorders authorities is refused even when every referenced
authority is genuine and every hash was rehashed consistently.

Engine v1 composition rule: at most one value-changing operation per
`(table, column)`; a second one is `unsupported_operation_composition` and
blocks authorization. Start restrictive; widen with tests.

Bundle:

```text
authority/
├── authorities.yml            authority records in plan order (hashed as authorities_sha256)
├── application_plan.yml       ordered steps + application_plan_sha256
├── authorization_manifest.yml status, proposal/source/policy/authorities/plan hashes, dispositions
├── blockers.csv
└── report.md
```

## Apply

All preconditions are checked before staging is created:

1. authorization status is `authorized` and `engine_version` matches;
2. current source hash equals the authorized one;
3. `authorities.yml` hashes to `authorities_sha256` in the manifest;
4. `application_plan.yml` hashes to its own `application_plan_sha256` **and**
   to the manifest's; its source hash matches; each step carries exactly
   `sequence` and `authority_sha256`;
5. every plan step references exactly one known authority, once, in sequence;
6. the plan equals the canonical projection of the complete verified bundle
   (`application_plan_authority_set_mismatch` otherwise);
7. every authority passes its own `verify_*` against the current source;
8. every operation is one engine v1 implements;
9. the composition rule holds.

Any failure publishes a `blocked` bundle with blockers and **no `parquet/`**.

Then, in one staging directory: read every source table, apply steps in plan
order, write every table, compute hashes, build lineage, write the manifest,
self-check the staged files, and `publish_new_directory`. A failure anywhere
before publish removes staging and promotes nothing.

Operations implemented in v1: `normalize_column_name`, `trim_whitespace`,
`normalize_blank_sentinel` (exact string match against the configured list),
`parse_number` (configured thousands/decimal), `parse_date` (explicit format).
Values a governed operation cannot parse become `NA` **and are counted** in
lineage as `values_failed`; the reviewer approved the candidate knowing its
`failure_count`, and the record shows what happened.

### Lineage

Each row of `lineage.yml` is the D1 `TransformationLineage` built by
`build_lineage` with the **real** output hash after the table is written,
serialized as-is (`source_sha256`, `authority_kind`, `authority_sha256`,
`output_sha256`, `table`, `column`, `operation`, `rows_examined`,
`rows_changed`, `applied_at`, `contract_version`), plus D2 evidence beside it:
`sequence`, `values_failed`, and `output_physical_sha256`. There is no
placeholder hash and no parallel lineage schema.

Decision: the contract `output_sha256` is the **logical content hash** of the
output table, because that is what the engine promises to be deterministic
across environments; the physical Parquet hash is recorded as D2 metadata and
is not promised across writer versions. `applied_at` is part of the contract
and stays; determinism tests compare the deterministic fields and exclude the
timestamp and the physical hash.

Bundle:

```text
output/
├── parquet/<table>.parquet
├── lineage.yml               D1 TransformationLineage per step + sequence, values_failed,
│                             output_physical_sha256
├── application_manifest.yml  status, all upstream hashes, per-table physical and logical hashes,
│                             logical_dataset_sha256
├── blockers.csv
└── report.md
```

## Determinism: two hashes

| Hash | Over | Promise |
| --- | --- | --- |
| `logical_content_sha256` | canonical JSON of `{columns: [{name, dtype}], rows: [[values]]}` | Same source + same ordered plan → same hash, in any environment |
| `physical_sha256` | the Parquet bytes | Recorded, not promised across writer versions |

`pyarrow` remains unpinned; the engine does not promise byte-identical Parquet
across installations. Lineage and the application manifest carry both hashes
so "the data changed" and "the encoder changed" stay distinguishable.

## Engine Version

Every bundle records `engine_version`. Artifacts that cross a process boundary
are checked on load with the v1 policy `artifact.engine_version ==
ENGINE_VERSION`: the proposal manifest by `authorize`, the authorization
manifest by `apply`. A mismatch is `unsupported_engine_version` and nothing is
authorized or applied. Widening the policy (ranges, migrations) is a later,
explicit decision.

## Legacy Baseline

The legacy path is compared against a **fixed** baseline, not against itself:
`tests/fixtures/legacy_cleaner/legacy_cleaner_golden.yml` holds the logical
content hashes of `customers`, `order_items`, and `orders` produced by
`run_workflow` over `samples/raw` on `origin/main` at `826cfc4` (pandas
3.0.3), before the engine existed. The regression test runs the current
workflow and compares against those static values; a deterministic change to
`cleaner.py` fails it even though two fresh runs would still agree with each
other. `tests/legacy_cleaner_characterization_test.py` remains beside it: the
characterization suite pins individual behaviors, the golden pins the whole
output.

## The D2 Checklist

```text
 1. proposal never changes source data
 2. pending_review has zero apply authority
 3. rejected has zero apply authority
 4. every governed proposal has an explicit disposition before apply-ready authorization
 5. only exact hash-bound authorities enter an application plan
 6. application order is explicit and hash-bound
 7. source drift invalidates proposal / authority / application
 8. tampering any authority invalidates apply
 9. tampering the application plan invalidates apply
10. partial failure publishes nothing
11. same source + same ordered authorities -> same deterministic logical result
12. every applied transformation produces lineage
13. lineage identifies exactly one authority mechanism
14. configured operations cannot borrow human authority
15. governed operations cannot borrow policy authority
16. non-automatic operations cannot borrow operation-table authority
17. legacy clean_dataframe remains unchanged
18. run_workflow remains unchanged
19. the engine is opt-in only
20. no model / provider / network dependency in v1
```

| # | Proven by |
| --- | --- |
| 1 | `test_propose_never_changes_source_data`, `test_apply_never_touches_the_source` |
| 2, 4 | `test_missing_disposition_yields_incomplete_not_a_blocker_and_no_apply_ready_bundle`, `test_authorization_never_stores_approved_as_free_standing_state` |
| 3 | `test_rejected_is_a_valid_disposition_with_zero_authority` |
| 5 | `test_authorization_emits_canonical_order_and_a_hash_bound_plan`, `test_unknown_authority_in_plan_fails_apply`, `test_plan_that_omits_one_authorized_authority_is_refused_before_transformation`, `test_apply_recomputes_canonical_order_from_the_verified_bundle` |
| 6 | `test_same_authorities_in_a_different_order_have_a_different_plan_hash`, `test_tampered_or_reordered_application_plan_fails_apply_before_staging`, `test_plan_reordered_with_every_hash_rehashed_is_still_refused` |
| 7 | `test_source_changed_after_propose_fails_authorization`, `test_source_changed_after_authorize_fails_before_transformation`, `test_propose_refuses_when_source_manifest_disagrees_with_actual_parquet` |
| 8 | `test_tampered_authority_bundle_fails_apply`, `test_one_authority_failing_verify_leaves_zero_output`, `test_forged_authority_kind_on_disk_fails_the_per_authority_self_check` |
| 9 | `test_tampered_or_reordered_application_plan_fails_apply_before_staging`, `test_plan_step_with_extra_metadata_is_refused_before_transformation` |
| 10 | `test_partial_failure_publishes_nothing`, `test_one_authority_failing_verify_leaves_zero_output` |
| 11 | `test_same_source_and_same_plan_produce_the_same_logical_output_and_lineage` |
| 12, 13 | `test_apply_writes_every_table_and_lineage_names_exactly_one_mechanism_per_step`, `test_persisted_lineage_is_the_d1_contract_object_with_the_real_output_hash` |
| 14 | `test_configured_operation_outside_exact_policy_scope_gets_no_authority`, `test_no_policy_means_configured_steps_get_no_authority` |
| 15 | `test_policy_that_lists_a_governed_operation_is_a_blocker` (contract: `test_a_human_decision_cannot_authorize_a_non_governed_operation`) |
| 16 | contract: `test_operation_table_grants_no_authority_outside_safe_automatic`; engine: `test_raw_column_name_is_proposed_authorized_and_renamed_end_to_end`, `test_two_raw_names_that_normalize_to_the_same_target_are_refused_at_authorize` |
| 17, 18 | `test_legacy_workflow_matches_the_fixed_golden_baseline`, `test_golden_fixture_values_are_static_hex_digests`, `tests/legacy_cleaner_characterization_test.py` |
| 19 | `test_engine_is_opt_in_and_run_workflow_does_not_call_it` |
| 20 | `test_engine_imports_no_network_capable_module`, `tests/network_boundary_test.py` |
| v1 rule | `test_two_value_changing_operations_on_one_column_are_refused_before_apply` |
| review binding | `test_review_for_another_proposal_over_the_same_source_is_refused` |
| engine version | `test_proposal_from_another_engine_version_is_refused_by_authorize`, `test_authorization_from_another_engine_version_is_refused_by_apply` |

## CLI

```text
dataops governed-cleaning-propose   --parquet-dir DIR [--source-manifest FILE] [--output DIR]
dataops governed-cleaning-authorize --proposal DIR --parquet-dir DIR [--review FILE] [--policy FILE] [--output DIR]
dataops governed-cleaning-apply     --authority DIR --parquet-dir DIR [--output DIR]
```

Every command publishes to a **new** directory only (`output_directory_exists`
otherwise). The registrar is `cli_commands/governed_cleaning.py`; `cli.py`
imports it, calls it in `build_parser`, and dispatches the three commands
before the legacy `run_workflow` fallback. The 48 existing commands are
unchanged.

## Not In v1

- `interpret_decimal_separator`, `interpret_locale`, `canonicalize_identifier`,
  `remap_category`: contract operations the engine refuses at apply with
  `operation_not_supported_by_engine`.
- More than one value-changing operation per column.
- Cross-environment byte-identical Parquet.
- Any model or provider involvement in proposing.

## Related

- [Governed Cleaning Contract](governed-cleaning.md)
- [Architecture](architecture.md)
- [Testing](testing.md)
