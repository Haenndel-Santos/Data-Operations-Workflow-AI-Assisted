# Orchestrator

## Current State

`src/data_ops_lab/workflow.py` contains the fixed default analytical sequence. It converts inputs, profiles and cleans staging data, infers schema/keys, validates relationships, generates SQL, builds DuckDB, exports Tableau files, writes documentation, and returns `WorkflowResult`.

`src/data_ops_lab/cli.py` separately dispatches ERP modeling and human-review commands. These commands are explicit and testable, but they do not yet share dependency resolution, checkpoint state, or resume behavior. Step 3E.4 provides a command-local decision digest; Step 3E.5 adds a deterministic ready/blocked materialization checkpoint; Step 3E.6 binds that complete snapshot to applied state in a dry-run promotion plan. None is yet shared orchestrator infrastructure.

CLI registration decomposition has started without changing that dispatch
boundary. The `src/data_ops_lab/cli_commands/` package now owns all 48 parser
declarations: seven dataset-benchmark commands, eight semantic catalog,
approval, adapter, translation, and offline evaluation commands, six query
planning, execution, presentation, narration, and session commands, two
reference-dataset conversion, SQL Server export, and validation commands, seven Step 3 ERP
modeling and human-review commands, nine Product reference audit,
reconciliation, review, validation, and apply commands, three Product
materialization, canonical-promotion, and repair commands, two conceptual
schema and business-flow documentation commands, two local analytics
foundation commands, and one separately controlled Ollama soak command.
`build_parser` invokes all ten registrars in the original command order and
contains no direct subparser declaration, while `data_ops_lab.cli:main`
retains execution and result formatting. This is static
registration organization, not module discovery or dynamic dispatch.

Stage 5A separately introduces a dry-run analytics query planner. Stage 5B adds
an explicit controlled executor that requires exact plan revalidation and
produces bounded local result evidence. Stage 5C adds metadata-only semantic
catalog validation with explicit ambiguity and human-review state. The local
analytics-session service now provides one narrow two-phase coordinator for
recorded Stage 5D through result narration. It stops at an immutable plan-review
checkpoint and resumes only with a separately completed exact human review. It
does not change `workflow.py` or provide general module discovery.

`src/data_ops_lab/module_registry.py` now validates the first versioned
declarative registry at `config/orchestrator/analytics_module_registry.yml`.
It inspects entrypoint source and exact signatures statically, validates module
and workflow dependencies, cycles, capabilities, test files, stage order,
failure policies, and the human execution gate, then writes dry-run evidence.
It cannot dispatch or execute a module.

`data_ops_lab.contracts.run_results` now exposes an additive structural
projection for the four fields shared by 23 existing blocker-producing result
classes: `output_dir`, opaque `status`, `blocker_count`, and `outputs_changed`.
No current workflow dispatches through this contract. A consumer audit found
that all 24 compatible CLI branches still render module-specific fields, while
the analytics-session coordinator uses child-specific statuses and artifacts
for stage gates and only aggregates the shared `outputs_changed` flag. The
projection therefore remains opt-in until a generic dispatcher or run recorder
needs its complete four-field view; blocker records, statuses, checkpoints,
artifacts, and authority remain local.

`benchmark-export-sqlserver` is an additive explicit Phase 5.2 entrypoint with
a separate `--execute` gate. It may read only an exact authorized local
read-only SQL Server database and publish new DuckDB/Parquet evidence; it does
not join the fixed workflow or declarative session registry.

`reference-dataset-validate` remains a separate explicit Phase 2/5.2
entrypoint. It
orders provenance/license/use preflight before any read-only DuckDB profiling
and stops at `ready_for_relationship_review` without an exact completed human
review. With a completed review it may report `ready_for_semantic_modeling` and
derive an approved-relationship registry containing accepted decisions only.
It is not yet part of the declarative analytics-session registry.

Northwind now has a separate Stage 5C catalog compiled from that accepted
relationship projection, a completed 111-entity review, and an applied approved
semantic registry. Stage 5D may consume that exact state, but Stage 5A
`ready_for_execution_review` still cannot be treated as Stage 5B execution
authority by the explicit CLI or future orchestration.

## Responsibility

The orchestrator may discover, validate, select, order, execute, record, recover, and summarize module work. It must not duplicate specialized module logic, hide failures, mutate inputs, or promote unapproved decisions.

## Target Module Contract

Use these fields when a module becomes orchestratable:

```yaml
name:
version:
description:
status:
entrypoint:
inputs:
outputs:
dependencies:
capabilities:
workflows:
validation:
tests:
failure_policy:
```

## Incremental Evolution

1. Document contracts for existing entrypoints without changing behavior.
   Implemented for the recorded analytics session.
2. Validate contracts and dependencies in isolation. Implemented for the
   recorded analytics session with static, non-executing registry validation.
3. Add workflow selection and ordered execution behind current CLI compatibility. Implemented narrowly for the recorded analytics session.
4. Add explicit run state, logs, and failure summaries. Implemented for the recorded analytics session only.
5. Add partial execution and dry-run. The analytics session has an explicit preparation phase; generic partial runs remain pending.
6. Add idempotent checkpoints and safe resume only after state semantics are tested. Implemented for exact analytics plan review; generic resume remains pending.

Each step requires contract, unit, integration, workflow, and regression coverage proportional to its impact. Do not combine this evolution with data migration, dependency upgrades, or unrelated refactoring.

## Current Safety Gate

No orchestrator feature may treat `pending_review`, a valid-but-blocked workbook, or `ready_for_canonical_state_review` as approval. Product Step 3E.4 contains the explicitly replaced 15-approved/13-rejected state, Step 3E.5 produced a complete validated local preview, and Step 3E.6 produced only a hash-bound dry-run promotion plan. No downstream stage may bypass the applied digest, restore excluded identities, consume stale blocked outputs, apply canonical state, or import/synchronize the preview without a separate authorized contract.

No future AI adapter may submit raw model-generated SQL. It must produce the versioned structured analytics request, and cross-table plans must continue to require approved relationships. `ready_for_execution_review` is not execution authorization; Stage 5B runs only through its separate explicit entrypoint after exact plan revalidation.

`ready_for_semantic_review` is also not semantic approval. Future orchestration
must require a separate approved semantic representation before Stage 5D may
resolve business terms operationally.

`awaiting_execution_review` is not execution authority. The analytics-session
resume command requires a separate completed human review bound to the exact
preparation manifest and plan hashes. It cannot auto-approve its own output.

A `valid` module registry is not execution authority. Registry controls require
dynamic execution, concurrency, network, and review auto-approval to remain
disabled, and the validator has no execution or apply mode.

The selected Ollama semantic provider is exposed through a separate explicit
CLI and the existing injected provider contract. Its capability is declared in
the registry, but the registry does not dispatch it: `network_enabled` and
dynamic execution remain false. A live semantic response still passes through
Stage 5D and stops before the existing human Stage 5A execution review.

The Phase 5 dataset benchmark answer-preparation command is also standalone and
not dynamically dispatched by the registry. It batches recorded Stage 5D and
Stage 5A preparation only, then emits one aggregate pending review bound to all
exact plan hashes. It cannot call Stage 5B, auto-complete its review, invoke the
live Ollama provider, or approve the expected answers that a later reviewed
collection may produce.

The dataset benchmark live evaluator is likewise standalone. Dry-run validates
its separate SHA-256-bound live authority without provider or database access;
live mode additionally requires explicit execution and loopback-network flags.
It cannot be invoked by the static registry, use an external provider, run
cases concurrently, bypass Stage 5A/5B controls, narrate, publish, or train a
model. A completed live comparison is evaluation evidence, not provider
selection or production authority.

The overnight Ollama soak is another explicit standalone command and is not a
registry workflow. It may repeat only the exact authorized development pack,
keeps model concurrency at one, and must stop on its bound duration/cycle,
timeout, technical-error, resource, or `STOP` gate. Its checkpoints are
stability evidence only and cannot approve a provider, holdout, training,
production dispatch, or broader network use.

`ready_for_relationship_review` is likewise not relationship authority. A
future semantic-catalog workflow may consume only the accepted subset from a
completed exact relationship review that revalidates as
`ready_for_semantic_modeling`.
