# Generic Dataset Readiness

## Status

```yaml
version: 1
status: design_for_review
implementation_authority: not_granted
module: src/data_ops_lab/dataset_readiness.py   # planned
cli: dataset-readiness-evaluate                 # planned, flat, one command
```

This document is the design for the next increment. It grants no
implementation authority; the contract, tests, and code follow owner review.

## The Question

> When can a dataset be declared, mechanically, ready to enter the generic
> Data Intelligence layer?

The answer this design gives:

> A dataset is ready when every authority the layer depends on **exists**, is
> **bound by hash to exactly this dataset**, and is **mutually consistent** -
> and readiness proves that by recomputation, grants nothing new, and records
> the result as an exact artifact that downstream consumers re-verify before
> use.

Readiness is an aggregation and verification gate over authorities that
already exist (governed cleaning, relationship approval, semantic approval,
execution contracts). It never creates authority: no candidate becomes a key,
no relationship is promoted, no semantic term is approved, no transformation
is applied. If something is missing, readiness says exactly what and which
existing gate produces it.

## Where It Sits

```text
verified source (raw Parquet or local database evidence)
        |
        v
governed cleaning (D2)         optional; when present, lineage links source -> analytical dataset
        |
        v
analytical dataset (Parquet + DuckDB)
        |
        +-- schema / key evidence           candidates; approved keys separate
        +-- relationship authority          approved_relationships derived from a completed human review
        +-- semantic authority              approved semantic catalog bound to physical catalog + relationships
        +-- execution contract              read-only DuckDB, fixed limits, module registry
        |
        v
DATASET READINESS  ---------->  exact readiness artifact  ---------->  Product API /datasets (re-verifies)
   deterministic                (dataset_readiness.yml)               Generic dataset onboarding UI
   recomputes every binding                                           any downstream that must not guess
```

## Vocabulary

| Term | Meaning |
| --- | --- |
| Dataset | One analytical dataset: a directory of Parquet tables plus its DuckDB file, identified by `dataset_id` and by content hashes, never by name alone |
| Readiness profile | A versioned, named set of requirements. Readiness is always evaluated *for* a profile; "ready" without a profile is meaningless |
| Check | One deterministic verification with a stable `check_id`, a class, a result, and the evidence hashes it examined |
| Requirement class | `integrity` (must hold; failure is `blocked`), `required` (must be present and valid; absence is `not_ready`), `advisory` (absence or weakness is a warning) |
| Readiness state | `ready`, `not_ready`, or `blocked`, plus a list of warnings in every state |
| Readiness artifact | The persisted result, hash-bound to every input it verified and self-hashed |

## States

```text
blocked      an integrity check failed: something claims to describe this dataset
             and does not (hash mismatch, contradictory bindings, tampered or
             unreadable authority artifact). Nothing downstream may treat the
             dataset as anything until this is resolved.

not_ready    integrity holds, but a required authority for the profile is absent,
             pending, rejected, or out of scope. The artifact names the exact
             missing gate and its next step.

ready        integrity holds and every required check passes. Warnings from
             advisory checks are listed; they do not block.
```

Three states, no intermediate. Levels of readiness are expressed by
**profiles**, not by extra states, so a consumer asks a boolean question
("ready for `analytics_v1`?") and always gets an answer it can act on. A
dataset can be `ready` for `preparation_v1` and `not_ready` for `analytics_v1`
at the same time; that is the intended way to say "cleaned and verified, not
yet queryable".

`blocked` is separate from `not_ready` on purpose: a missing semantic review is
work to do; a semantic state whose `physical_catalog_sha256` does not match
the DuckDB on disk is evidence that something drifted or was tampered, and
must not be reported as merely incomplete.

## Profiles (v1)

### `preparation_v1` - the dataset is verified and its transformations are accounted for

| check_id | class | Passes when |
| --- | --- | --- |
| `source.identity` | integrity | Every Parquet table exists, is readable, and the recomputed `source_sha256` (D2 definition: sorted `{path, sha256}` list) matches the identity the dataset claims |
| `source.provenance` | advisory | A source manifest exists and matches the actual files (D2 `verify_source` semantics) |
| `cleaning.provenance_chain` | required | One of: (a) the analytical Parquet **is** the verified source (no transformation), or (b) a D2 `application_manifest.yml` with status `applied` whose `source_sha256` equals the verified source and whose per-table `logical_content_sha256` equals the recomputed logical hash of every analytical table. Legacy `02_cleaned` output with no lineage does **not** satisfy this check |
| `cleaning.lineage_integrity` | integrity | When (b): `lineage.yml` rows are contract `TransformationLineage` records whose `output_sha256` equals the table's logical hash and whose `authority_sha256` values appear in the referenced authority bundle |
| `cleaning.pending_candidates` | advisory | The proposal that fed the application has no governed candidate left without disposition (a `rejected` disposition is fine; `missing` is a warning, not a blocker - the owner may have chosen not to decide yet) |
| `schema.inference_present` | advisory | `schema.json` / `keys.json` (or equivalent evidence) exist for the analytical tables |

### `analytics_v1` - the dataset can be queried through the governed analytics route

Includes every `preparation_v1` check, plus:

| check_id | class | Passes when |
| --- | --- | --- |
| `database.present` | required | The DuckDB file exists and opens read-only with external access disabled |
| `database.catalog_binding` | integrity | The DuckDB physical catalog hash (the same computation the semantic catalog compiler uses) equals the semantic state's `source.physical_catalog_sha256`, and every table in the catalog exists among the analytical Parquet tables with matching row counts |
| `relationships.authority` | required | An approved relationships file exists with `status: approved`, `authority.derived_from_completed_human_review: true`, `authority.automatic_approval: false`, and a scope that includes local offline use |
| `relationships.binding` | integrity | The relationships file's `authority.source_manifest_sha256` matches the dataset's source manifest (when present) and its content hash equals the semantic state's `source.relationships_sha256` |
| `relationships.coverage` | advisory | Every approved relationship references tables and columns that exist in the catalog; every catalog table with a foreign-key-shaped candidate has at least one approved or explicitly rejected relationship |
| `semantics.authority` | required | Semantic state exists with `status: approved`, `approval.semantic_definitions_approved: true`, `approval.adapter_use_authorized: true` |
| `semantics.binding` | integrity | Semantic state hashes (`compiled_semantic_catalog_sha256`, `review_sha256`, `decision_digest`) match the artifacts they name when those artifacts are supplied |
| `semantics.compiles` | required | The approved semantic catalog compiles against the current physical catalog with zero blockers and zero unresolved ambiguities (`analytics-semantic-catalog` contract, read-only) |
| `execution.contract` | required | The analytics module registry validates statically for the session entrypoints (no execution), and Stage 5A/5B limits are the fixed ones (readiness records the limit values it saw) |
| `keys.approval` | advisory | `approved_keys.yml` (or the dataset's equivalent) is non-empty; absence is a warning because Stage 5A does not need approved keys, only approved relationships |

The two profiles are the v1 answer to "which properties are necessary before
the Product API can accept a dataset": the API accepts a dataset for
question-answering only when a fresh `analytics_v1` evaluation is `ready` **and**
its bindings still verify at request time.

## Proving It Is Exactly The Governed Dataset

Readiness does not trust names or paths. It binds:

```text
source_sha256                    recomputed from the Parquet files
  == application_manifest.source_sha256                 (when governed cleaning was applied)
application_manifest.logical_dataset_sha256
  == recomputed sha256 over per-table logical hashes    (recomputed from the Parquet files)
physical_catalog_sha256          recomputed from the DuckDB catalog
  == semantic_state.source.physical_catalog_sha256
sha256(approved_relationships file)
  == semantic_state.source.relationships_sha256
approved_relationships.authority.source_manifest_sha256
  == sha256(source manifest)                            (when a manifest exists)
```

Every equality above is an `integrity` check. Any failure is `blocked`. The
readiness artifact records every hash it recomputed and every hash it
compared against, so a later reader can repeat the same comparisons.

## The Artifact

`dataset_readiness.yml`, published atomically to a new directory with
`blockers.csv` and `report.md`, following the repository convention:

```yaml
version: 1
engine_version: 1
dataset_id: customer_orders
profile: analytics_v1
profile_version: 1
evaluated_at: 2026-08-19T10:00:00Z
state: ready | not_ready | blocked
bindings:
  source_sha256: ...
  logical_dataset_sha256: ...
  physical_catalog_sha256: ...
  relationships_sha256: ...
  semantic_state_sha256: ...
  application_manifest_sha256: ...      # when present
  source_manifest_sha256: ...           # when present
checks:
  - check_id: relationships.authority
    class: required
    result: pass | fail | skipped
    evidence:                             # exact hashes / paths examined
      relationships_path: ...
      relationships_sha256: ...
    blockers: []                          # blocker codes when result is fail and class is integrity/required
    warnings: []                          # warning codes when class is advisory
next_steps:                               # only when not_ready: the exact gate that produces the missing authority
  - check_id: semantics.authority
    command: analytics-semantic-review
    reason: no approved semantic state for this dataset
warnings: [...]
readiness_sha256: ...                     # over the whole document except this field
```

`readiness_sha256` is a self-hash. It has the same limit every bundle root in
this repository has: an editor with write access to the file can rehash it.
It is still worth having because it detects accidental edits and truncation
and gives the Product API something to compare against, and because
downstream must **re-verify the bindings against the current files anyway**
before treating the artifact as current. Readiness evidence is a snapshot,
never a standing permission.

## What Readiness Never Does

- Never promotes a candidate key, relationship, or semantic term. It reads
  `approved_*` and completed-review artifacts only; candidates feed advisory
  checks and nothing else.
- Never applies a transformation, never opens DuckDB writable, never touches
  `config/data_model/`, never writes anywhere but its own new output directory.
- Never calls a model or the network. It is a deterministic aggregation over
  local artifacts.
- Never infers "close enough": a required authority is present and valid, or
  the dataset is `not_ready`.
- Never treats a legacy `02_cleaned` output as governed. It can still be
  evaluated; `cleaning.provenance_chain` fails with a `next_steps` entry that
  names the governed route.

## Human Review

Readiness itself is deterministic and needs no human gate: every human
decision it depends on already happened upstream (relationship review,
semantic review, cleaning decisions and policy). Adding a human "readiness
approval" would duplicate those decisions with a weaker artifact.

What remains human is **registration**: deciding that this ready dataset is
offered to users of a deployment. That belongs to the Product API's dataset
registry and RBAC, not to readiness. Readiness answers "may this dataset be
offered without guessing"; registration answers "is it offered here, to whom".

## Failure Vocabulary

Blocker codes (integrity / required failures) will be literal, registered in a
new `dataset_readiness` taxonomy family, and named by check: for example
`source_identity_mismatch`, `cleaning_provenance_chain_missing`,
`lineage_output_hash_mismatch`, `catalog_binding_mismatch`,
`relationships_authority_missing`, `relationships_not_human_derived`,
`semantic_authority_missing`, `semantic_binding_mismatch`,
`semantic_catalog_does_not_compile`, `execution_contract_invalid`,
`unsupported_profile`, `unsupported_readiness_engine_version`. Warning codes
are a separate, also-literal vocabulary (`source_manifest_absent`,
`pending_cleaning_candidates`, `approved_keys_absent`,
`relationship_coverage_gap`, ...). Exact lists are fixed at contract time.

## Testing Strategy

- **Synthetic datasets only**, built in temporary directories the way the D2
  tests do: a Parquet set, optionally run through the real D2 route, a DuckDB
  built from it, a synthetic approved relationships file and semantic state
  produced through the real semantic catalog/review/approval contracts (or
  fixtures already used by those tests). No customer data.
- **Northwind** may be used only through its already-versioned development
  artifacts (`northwind.reference.yml`, reviewed relationships, approved
  semantic catalog) as an existing development fixture. **AdventureWorks is
  not touched** in any readiness test; readiness must not read holdout
  artifacts, and no readiness fixture may be derived from it.
- Adversarial coverage mirrors D2: every integrity check has a tamper test
  (change one byte upstream, rehash the artifact that claims to describe it,
  readiness reports `blocked`); every required check has an absence test
  (`not_ready` with the right `next_steps`); every advisory check has a
  warning test; profile mismatch and engine-version mismatch are refused;
  the artifact re-verifies against itself; a stale artifact whose bindings no
  longer match the files is detected by the re-verify entrypoint the Product
  API will call; two evaluations of the same inputs produce identical checks
  and bindings (only `evaluated_at` differs).
- The legacy path: a `02_cleaned` output evaluated for `preparation_v1` is
  `not_ready` on `cleaning.provenance_chain`, never `ready`, never `blocked`.

## Module And CLI (planned)

```text
src/data_ops_lab/dataset_readiness.py
    evaluate_dataset_readiness(dataset_dir, database_path, output_dir, *,
        profile, dataset_id, semantic_state_path=None, relationships_path=None,
        application_manifest_path=None, source_manifest_path=None,
        schema_dir=None) -> DatasetReadinessResult
    verify_readiness_artifact(artifact_path, ...) -> bool + blockers   # downstream re-verify

cli_commands/dataset_readiness.py
    dataset-readiness-evaluate   one flat command; additive registration in cli.py
```

Contract-level pieces (states, classes, check registry, artifact hash, profile
tables) will be pure and testable without I/O, in the D1 style; the evaluator
does the file reading in the D2 style.

## Decisions Requested From The Owner

1. **Provenance chain rule.** Confirm that `preparation_v1` requires either
   "analytical dataset == verified source" or a governed D2 application, and
   that legacy `02_cleaned` output is `not_ready` (not a warning). This is the
   product stance that the Data Intelligence layer never sits on silent
   coercion.
2. **Two profiles.** Confirm `preparation_v1` and `analytics_v1` as the v1 set,
   with `analytics_v1` as the Product API acceptance bar.
3. **Approved keys advisory.** Confirm that absent `approved_keys` is a warning
   under `analytics_v1` (Stage 5A needs approved relationships, not approved
   keys). If keys should be required, say so and the class flips.
4. **No human readiness gate.** Confirm that readiness is deterministic and
   that human registration lives in the Product API.
5. **`blocked` vs `not_ready`.** Confirm the split: integrity failure is not
   incompleteness.

## Related

- [Governed Cleaning Contract](governed-cleaning.md) and
  [Governed Cleaning Engine](governed-cleaning-engine.md) - the provenance chain
- [Reference dataset validation](reference-dataset-validation.md) - relationship
  authority format and review binding
- [Analytics semantic catalog](analytics-semantic-catalog.md) and
  [approval](analytics-semantic-approval.md) - semantic authority format
- [Analytics module registry](analytics-module-registry.md) - execution contract
- [MVP Product Requirements](mvp-prd.md) and [MVP Architecture](mvp-architecture.md) -
  "Dataset readiness" as the first product screen and `/datasets` endpoint
- [AI platform implementation roadmap](ai-implementation-roadmap.md) - Phase 6
