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
| 2.3 | Common source bindings, error taxonomy, and run-result envelope | Implemented; the additive projection remains opt-in after the consumer audit found no semantics-neutral runtime adopter |
| 2.4 | CLI command registration split by domain while preserving `data_ops_lab.cli:main` | In progress; 42 registrations are extracted across seven coherent domain slices |

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
- Increment 2.3 result-presentation/narration taxonomy and
  registered-consumer suite: 190 passed in 33.82 seconds.
- Increment 2.3 analytics-session taxonomy and registered-consumer suite: 201
  passed in 36.44 seconds.
- Increment 2.3 module-registry taxonomy and registered-consumer suite: 210
  passed in 36.84 seconds.
- Increment 2.3 Ollama-soak taxonomy and registered-consumer suite: 214 passed
  in 36.98 seconds.
- Increment 2.3 reference-dataset-validation taxonomy and registered-consumer
  suite: 218 passed in 37.67 seconds.
- Increment 2.3 Product canonical-promotion taxonomy and registered-consumer
  suite: 227 passed in 38.03 seconds.
- Increment 2.3 Product materialization taxonomy and registered-consumer suite:
  235 passed in 40.91 seconds.
- Increment 2.3 run-result compatibility and registered-consumer suite: 238
  passed in 39.63 seconds.
- Increment 2.4 dataset-benchmark CLI registration slice: 61 focused tests
  passed in 15.25 seconds; the complete parser signature remained
  `ddfc7ba0a1cfe91fbe0e7e6baf084c14cbe665100f1cb7260c56e27f5b634b37`
  across all 47 commands.
- Increment 2.4 semantic/translation CLI registration slice: 60 focused tests
  passed in 9.00 seconds; the same complete 47-command parser signature was
  preserved.
- Increment 2.4 query/session CLI registration slice: 36 focused tests passed
  in 9.52 seconds; the same complete parser signature and all six individual
  command signatures were preserved.
- Increment 2.4 reference-dataset CLI registration slice: 13 focused tests
  passed in 3.91 seconds; the same complete parser signature and both
  individual command signatures were preserved.
- Increment 2.4 ERP modeling registration slice: 276 tests passed and 2 opt-in
  live-provider tests skipped in 49.29 seconds on Windows/Python 3.13; 111
  internal links checked, 0 broken; the complete parser and diff gates passed.
- Increment 2.4 Product reference registration slice: 276 tests passed and 2
  opt-in live-provider tests skipped in 52.44 seconds on Windows/Python 3.13;
  111 internal links checked, 0 broken; the complete parser and diff gates passed.
- Increment 2.4 Product publication registration slice: isolated syntax and
  exact signature equivalence preserved all three command signatures;
  reconstructed registration order preserved the complete 47-command surface.
  Automated repository validation is pending.
- Latest full offline suite: 276 passed and 2 opt-in live-provider tests skipped
  in 44.98 seconds on Windows.
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

The additive registry now classifies 675 labels used by 22 complete consumer
modules across twelve slices: the four initial standard analytics consumers, the
semantic adapter, six dataset-benchmark modules, and the natural-language
translation plus synthetic offline evaluation pair, followed by the synthetic
exact-answer evaluator, the result-presentation/narration pair, and the
analytics-session coordinator, static module-registry validator, bounded local
Ollama soak, reference-dataset validator, Product canonical promotion, and
Product materialization. The latest slice reviewed 15 literal Product
materialization codes plus one directly constructed code and added all 16. It
does not classify isolated labels from a partially reviewed family. It uses
these top-level categories:

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
| Product canonical promotion | 1 | Five codes selected from a local integrity-check tuple | Registered with the complete consumer; module-specific `artifact` format remains separate |

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

Four additional inherited flows bind result presentation and narration to the
shared YAML producer. The result-CSV parsing catch emits the sanitized
`invalid_result_csv` blocker. Narration maps `TimeoutError` to
`provider_timeout` and all other provider failures to `provider_failure` while
dropping exception messages. Facts readiness, presentation readiness, and
narration readiness remain text-status surfaces outside the registry. Stage 5B
facts and controls retain numeric authority; narration remains cited and
non-authoritative.

Two further inherited flows bind session preparation and resume to the shared
YAML blocker producer. The coordinator's artifact-path normalization,
human-review timestamp parsing, and existing-resume preflight catches have
separate provenance. Fourteen preparation, nested-stage, review-template,
resume, and last-valid-checkpoint text sources remain outside the registry.
Five aggregate stage-blocked codes are registered but `unclassified` because
their underlying specialized stage can fail in multiple categories. The
coordinator preserves its stop-before-execution gate and last-valid-checkpoint
failure policy.

The static validator has no inherited or dynamic blocker sources. Its six file,
YAML, module-spec, AST, and hash catches map to fixed sanitized blockers with
exact provenance. The generated `valid`/`blocked` status remains a separate
text surface. Registry safety controls and human-review gates remain authority
and approval boundaries; the validator remains non-executing and cannot import
or call declared entrypoints.

The soak has no inherited or dynamic blocker sources. Its ten authorization,
telemetry, cycle-evidence, and live-cycle catches have exact provenance without
persisted exception messages; only the exception class name is retained for a
cycle failure. Overall and per-cycle statuses remain text surfaces, while mode
and stop reason are separately provenanced control text. Its embedded
`blocker_001` records are classified without coercing them into the shared
`BLOCKER_001` standard analytics format. The aggregate live-authority preflight
failure remains explicitly `unclassified` because its nested validator spans
multiple categories. No soak, provider, network, or database execution is
authorized by taxonomy metadata.

The reference validator has no inherited, dynamic, or direct blocker-record
reuse. Its five YAML, timestamp, DuckDB, and staged-publication catches have
exact provenance; staged-publication failure cleans its `.building` directory
and re-raises the original exception. Six conversion, review, decision,
projection, and overall status surfaces remain outside the registry. Its local
`code`/`message`/`field` blocker record and the exact completed-review approval
projection are separately provenanced without changing either output.
`invalid_relationship_review` remains registered but `unclassified` because
one code currently combines version shape, dataset identity, and completed
review state. Classification does not approve candidates, apply relationships,
open project data, or expand local, upload, publication, or training authority.

Product canonical promotion has one finite dynamic integrity tuple and no
inherited or direct blocker-record reuse. Its four YAML, UUID, integer-count,
and CSV catches have exact provenance without persisted exception messages.
Applied-state, materialization-readiness, and dry-run-plan statuses remain text
surfaces. The four-field `artifact` blocker record remains separate even though
all 24 effective family codes are registered. The plan's explicit
`canonical_state_applied=false`, `database_operation_authorized=false`, and
`requires_explicit_apply_contract=true` values are a separate authority
boundary. The aggregate `materialization_blockers_present` remains
`unclassified` because the underlying materialization blockers can span
multiple categories. Taxonomy metadata does not apply canonical state, copy
private Product rows, mutate approvals, or authorize database operations.

Product materialization has no dynamic call sites, inherited standard-blocker
flows, direct blocker-list reuses, or catch-site fallbacks. Fifteen literal
codes plus the directly constructed `invalid_source_identifier_count` are
registered as one complete family. Its internal four-field blocker candidates
are normalized into a distinct persisted five-field record with deterministic
`BLOCKER_{ordinal:03d}` identifiers; both formats retain exact provenance and
remain local. Preview readiness is text status, applied decision and lineage
actions are control text, and the exact applied-state match plus preview-only
manifest are separate authority gates. The two aggregate failures
`approved_decision_not_materialized` and
`retained_original_product_unresolved` remain `unclassified` because each can
span multiple underlying causes. No private Product source, materialization,
approval apply, canonical promotion, or database operation was executed.

## Increment 2.3 Run-Result Contract

The source-only audit found no remaining literal blocker labels or consumer
files outside the registry: all 658 literal labels and all 22 files recognized
by the inventory are covered. Separately provenanced dynamic calls, direct
constructions/reuses, statuses, controls, exceptions, authority gates, and five
module-specific blocker formats remain distinct.

`data_ops_lab.contracts.run_results` defines a structural `RunResultLike`
protocol, immutable `RunResultEnvelope`, and `project_run_result` projection.
The common fields are exactly:

```yaml
output_dir:
status:
blocker_count:
outputs_changed:
```

Twenty-three existing result classes already expose this core. The projection
copies values without changing the original result object, interpreting status,
inferring success, reading blocker records, or copying module-specific artifact
paths. Existing Python return types, CLI text, manifests, CSVs, reports,
checkpoints, approvals, and private-data boundaries remain unchanged.

The follow-up consumer audit reviewed all 24 CLI branches backed by those 23
result types. Every branch reads `status` and `blocker_count`, 23 read
`outputs_changed`, none reads `output_dir`, and every branch also renders
module-specific counts, modes, checkpoints, or artifact paths. Projecting the
common fields inside those branches would therefore duplicate local reads
without creating a generic consumer or simplifying registration.

The recorded analytics-session coordinator also remains specialized. It uses
child status values as stage-specific gates, child artifact paths to start the
next stage, and child manifests as persisted evidence. Its only generic
aggregation is `outputs_changed`; allocating envelopes solely to read that
boolean would not improve the boundary. The projection therefore remains
available for a future dispatcher or run recorder that actually consumes the
four-field core. This evidence closes increment 2.3 without a decorative
runtime adoption.

## Increment 2.4 CLI Registration Contract

`data_ops_lab.cli_commands.analytics_dataset_benchmark` now owns registration
of the seven dataset-backed benchmark commands. The adjacent
`analytics_semantic` registrar owns eight semantic catalog/review/approval,
adapter, translation, and offline evaluation commands. The
`analytics_query_session` registrar owns six governed query planning,
execution, presentation, recorded narration, and two-phase session commands.
The `reference_dataset` registrar owns local SQL sample conversion and exact
reference-dataset validation. The `erp_modeling` registrar owns seven Step 3
source onboarding, human-review, serial-rule, approval-spreadsheet, and canonical
model commands. The `product_reference` registrar owns nine contiguous Product
reference audit, reconciliation, human-review, validation, and explicit-apply
commands. The `product_publication` registrar owns Product materialization
preview, dry-run canonical promotion planning, and missing-notes repair.
`build_parser` calls all seven registration functions at their original
positions, so command order, names, options, types, required flags, defaults,
help text, and root help remain unchanged.

The extracted modules import only `argparse`, `Path`, and the existing Ollama
CLI defaults. They do not import or call domain run functions. Dispatch, result
formatting, execution gates, network flags, approval semantics, and the public
`data_ops_lab.cli:main` entrypoint remain in their prior locations. This is a
registration-only boundary, not dynamic dispatch or a new orchestrator.

## Next Increment

Validate the Product publication registration slice through GitHub Actions,
then continue increment 2.4 with the next coherent registration slice while
preserving the complete parser signature and `data_ops_lab.cli:main`. Keep
domain execution and result formatting in their existing modules until a
separate dispatch contract is approved. Do not add a generic success predicate
or merge module-specific status, blocker, artifact, checkpoint, or authority
semantics.
