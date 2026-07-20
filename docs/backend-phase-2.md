# Backend Phase II - Internal Foundations

## Purpose

Consolidate repeated safety-critical backend behavior before expanding the
orchestrator, service layer, or user interface. This track is separate from
Phase 2 of `docs/ai-implementation-roadmap.md`.

The phase preserves current CLI and Python entrypoints while moving behavior
that is already proven equivalent into small internal contracts.

## Protected Boundaries

- Human review remains authoritative.
- Candidate, approved, rejected, blocked, and applied states remain separate.
- Raw inputs, approved YAML, completed reviews, and generated outputs are not
  rewritten by the refactor.
- Persisted schemas, hashes, blocker columns, ordering, and byte-level output
  remain compatible.
- Dynamic dispatch, concurrency, migrations, external providers, and UI work
  remain outside this phase.

## Delivery Sequence

| Increment | Scope | Status |
| --- | --- | --- |
| 2.1 | Common file hashing and the standard analytics blocker record | Implemented in `082920a` |
| 2.2 | Common atomic publication with characterized Windows retry and race semantics | Implemented in `28e962b` |
| 2.3 | Common source bindings, error taxonomy, and run-result envelope | Source bindings, reviewed dynamic/direct/exception provenance, and a 438-label classification registry implemented; further taxonomy expansion and run-result envelope pending |
| 2.4 | CLI command registration split by domain while preserving `data_ops_lab.cli:main` | Pending |

Other blocker shapes remain module-specific until their persisted schemas and
consumers are characterized. Product materialization and reference-dataset
validation are intentionally not coerced into the standard analytics blocker
shape.

## Increment 2.1 Contract

`data_ops_lab.contracts.hashing.file_sha256` owns the existing lowercase
SHA-256 file digest with 1 MiB streaming chunks. Legacy imports from source
onboarding, Product application, and reference-dataset validation remain valid.

`data_ops_lab.contracts.blockers.add_blocker` owns the existing version-1
analytics blocker shape:

```yaml
blocker_id:
blocker_type:
field:
explanation:
```

IDs remain sequential as `BLOCKER_001`, `BLOCKER_002`, and so on. Analytics
query planning, query execution, semantic catalog validation, and semantic
approval re-export the same function, so current consumers do not need an
immediate import migration.

## Increment 2.2 Contract

`data_ops_lab.contracts.atomic_publish.publish_new_directory` owns publication
of a fully prepared new directory. It retries only local `PermissionError`
failures, refuses a target that appears during retry through
`AtomicPublishTargetAppearedError`, and removes its staging directory after
success or failure.

`data_ops_lab.contracts.atomic_publish.atomic_write_text` owns same-directory
temporary text-file creation, bounded `os.replace` retry, replacement of the
owned checkpoint path, and temporary-file cleanup after success or exhaustion.

The live dataset evaluator and Ollama soak preserve their legacy wrappers,
retry schedules, domain-specific error messages, and evidence formats. The
filesystem contract cannot retry provider calls.

Benchmark conversion and reference-dataset validation still use explicit
`.building` directory semantics. They reject stale deterministic staging paths
before work and therefore were not migrated into the new-directory helper,
which uses unique staging and target-race handling.

## Increment 2.3 Source-Binding Contract

`existing_file_sha256_bindings` preserves input order, hashes only paths that
are files, and omits missing or directory paths. It is shared by analytics
presentation, narration, session prepare/resume, and the Ollama soak.

`declared_file_sha256_bindings` preserves every declared key and records `""`
for a missing or non-file path. It is shared by benchmark answer preparation
and materialization, where the complete binding key set is part of the
persisted contract.

The helpers do not decide whether expected bindings may contain extra keys,
whether the binding set must be exactly equal, or whether a missing file is a
blocker. Those validation policies remain in their owning modules because the
current semantics differ.

## Exit Gate

Backend Phase II is complete only when:

1. Existing persisted outputs remain byte-compatible or an explicit versioned
   migration is approved.
2. Public CLI and Python entrypoints remain compatible.
3. Critical modules use the shared hashing, blocker, atomic-publication,
   source-binding, error, and run-result contracts where their semantics match.
4. Focused compatibility tests and the full offline suite pass.
5. CLI decomposition removes registration concentration without moving domain
   logic into the CLI.
6. Documentation identifies any intentionally distinct contract instead of
   hiding it behind a generic abstraction.

## Validation Evidence

- Increment 2.1 focused compatibility and affected-module tests: 48 passed in
  10.44 seconds.
- Increment 2.2 atomic-publication and full live/soak consumer tests: 54 passed
  in 11.35 seconds.
- Increment 2.3 existing-file binding consumers: 76 passed in 17.77 seconds.
- Increment 2.3 declared-file binding consumers: 19 passed in 4.73 seconds.
- Increment 2.3 dataset-benchmark taxonomy and registered-consumer suite: 129
  passed in 24.02 seconds.
- Increment 2.3 translation/provider taxonomy and registered-consumer suite:
  146 passed in 21.66 seconds.
- Increment 2.3 synthetic answer-evaluation taxonomy and registered-consumer
  suite: 157 passed in 26.10 seconds.
- Latest full offline suite: 249 passed and 2 opt-in live-provider tests skipped
  in 40.20 seconds on Windows.
- No external database, provider, network, production data, migration, import,
  synchronization, or approval apply was used.

## Increment 2.3 Error-Taxonomy Contract

The first repository-wide blocker-label inventory is now reproducible with
`scripts/inventory_failure_labels.py`. Its 2026-07-16 baseline found 658
distinct literal labels passed to `add_blocker` or `_add_blocker`, plus 10
dynamic call sites. Their manual provenance review is now versioned separately
from the source-only parser. The inventory parses Python source without
importing modules, opening datasets, or executing workflows.

This baseline is evidence, not yet a runtime taxonomy. It intentionally does
not infer categories from label prefixes and does not include exception
messages, free-text status values, provider payloads, or blocker dictionaries
constructed without the two recognized append functions. Those separate
failure surfaces must be characterized before inclusion.

The additive registry now classifies 438 labels used by 14 complete consumer
modules across five slices: the four initial standard analytics consumers, the
semantic adapter, six dataset-benchmark modules, and the natural-language
translation plus synthetic offline evaluation pair, followed by the synthetic
exact-answer evaluator. The latest slice explicitly classifies all 49 literal
Stage 5E codes. It does not classify isolated labels from a partially reviewed
family. It uses these top-level categories:

| Category | Boundary |
| --- | --- |
| `contract` | Invalid version, shape, field, type, or unsupported input contract |
| `authority` | Hash, identity, source-binding, or immutable-evidence drift |
| `approval` | Missing, incomplete, rejected, or scope-invalid human review |
| `execution_limit` | Timeout, row/byte/resource bound, truncation, or safe-query limit |
| `provider` | Provider configuration, response, timeout, or invocation failure |
| `filesystem` | Missing/unreadable files, publication races, or write failures |
| `expected_result` | Exact-answer, comparison, or governed expectation mismatch |

`classify_error` returns the original code, its category, and whether that code
was explicitly registered. Classification is explicit per label; unknown codes
remain unregistered and `unclassified` rather than being guessed from spelling.
Two reviewed umbrella failures, `plan_revalidation_failed` and
`query_execution_failed`, remain registered as `unclassified` because none of
the seven categories describes them without losing meaning.

All 10 syntactically dynamic call sites now have exact, versioned provenance.
The regression binds the registry to each current source location, so a moved
or newly introduced dynamic site requires another explicit review.

| Consumer | Calls | Value provenance and surface | Taxonomy disposition |
| --- | ---: | --- | --- |
| Dataset benchmark evaluation | 1 | Standard blocker rows copied from prerequisite validation CSV evidence | Registered with the complete dataset-benchmark family |
| Dataset benchmark materialization | 2 | One finite scope-decision branch and candidate blocker rows returned by benchmark inspection | Registered with the complete dataset-benchmark family |
| Dataset benchmark preparation | 1 | Provider-response blocker rows returned by the existing response validator | Registered with the complete dataset-benchmark family |
| Dataset benchmark review | 1 | Finite benchmark-scope decision branch | Registered with the complete dataset-benchmark family |
| Analytics query execution | 1 | Three codes transported by `ExecutionLimitExceeded` and persisted as standard blockers | Codes registered as `execution_limit`; exception behavior remains local |
| Semantic adapter | 3 | Six codes derived from the bounded `dimensions`/`metrics` and `dimension`/`measure` parameters | Registered with the complete semantic-adapter consumer family |
| Product canonical promotion | 1 | Five codes selected from a local integrity-check tuple | Kept separate with the module-specific `artifact` blocker format |

The registry exposes metadata alongside the existing code. It does not rename
persisted labels, add columns to existing blocker CSVs, coerce module-specific
blocker shapes, or change failure behavior. Exception objects and their
messages remain distinct from the blocker code persisted by the catch site.
The two direct `candidate.blockers` list reuses in validation and approval now
have exact provenance and remain the standard four-field record. The live
evaluator's `provider_outcome` values remain a separate text-status surface;
the natural-language translation result, its evaluator result, and per-case
observed statuses are also separate text surfaces. Six exact flows record the
already-classified blockers written by shared YAML and semantic-adapter helpers
into translation/evaluation evidence. The two translation catch sites have
explicit provenance from injected-provider exceptions to the sanitized
`provider_timeout` and `provider_failure` blockers. The local Ollama adapter
itself has no standard-blocker call sites and remains an exception producer
rather than a registered blocker consumer. Three further inherited flows bind
the answer evaluator to those same complete producer families. Its temporary
dataset catch emits the sanitized
`synthetic_dataset_materialization_failed` blocker, while its per-case catch
emits only the `evaluation_error` text status; neither persists the exception
message. Translation, planning, execution, and overall evaluator statuses stay
outside the registry. The compound
`benchmark_answer_execution_incomplete` and
`benchmark_answer_result_integrity_failed` codes, together with
`synthetic_dataset_materialization_failed`, remain explicitly `unclassified`
because their current meanings span more than one category.

## Next Increment

Review the result-presentation/narration consumers next as one coherent family.
Keep narration-provider exceptions, presentation/narration statuses, Product's
`artifact` blocker format, and the common run-result envelope separate.
