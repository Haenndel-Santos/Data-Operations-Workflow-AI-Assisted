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
| 2.3 | Common source bindings, error taxonomy, and run-result envelope | Source-binding substep implemented in `2b6a10f` and `51372fd`; remaining work pending |
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
- Latest full offline suite: 235 passed and 2 opt-in live-provider tests skipped
  in 38.61 seconds.
- No external database, provider, network, production data, migration, import,
  synchronization, or approval apply was used.

## Next Increment

Inventory blocker and failure labels before defining an error taxonomy.
Separate contract failures, authority drift, human-review gates, execution
limits, provider failures, filesystem failures, and expected-result failures.
Do not replace persisted blocker codes or module-specific blocker columns in
the first taxonomy change. A common run-result envelope remains a later,
separate substep.
