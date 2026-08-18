---
name: query-planning-safety
description: Review governed analytical query planning and read-only execution for safety. Use whenever work touches structured analytics requests, the semantic adapter, Stage 5A plan compilation, Stage 5B execution, approved relationship projection, or the compiled SQL that those stages produce as evidence.
---

# Query Planning Safety

## Purpose

Keep the analytical query path deterministic and read-only. This skill reviews
how a structured request becomes an approved plan and a bounded execution. It
does not author SQL for the product to run.

The governed path is:

```text
structured semantic request
  -> approved semantic catalog
  -> approved relationship projection
  -> deterministic Stage 5A plan
  -> exact human plan review
  -> bounded read-only Stage 5B execution
```

## When to use this skill

Use it for changes to `analytics_query_plan`, `analytics_query_execution`,
`analytics_semantic_adapter`, `analytics_nl_translation`, or any code that
builds, reviews, or executes an analytical query. Also use it when reviewing
compiled SQL that a module emits as evidence.

## Required sources

- `docs/analytics-query-plan.md`
- `docs/analytics-query-execution.md`
- `docs/analytics-semantic-adapter.md`
- `docs/security-architecture.md`
- `docs/ai-analytical-capability-matrix.md`

## Invariants

- Deterministic code is the authority for schema resolution, SQL compilation,
  joins, filters, and numeric values. The model interprets; it does not compute.
- Identifiers reaching SQL are validated against `IDENTIFIER_PATTERN` and
  double-quoted. Values reach SQL only as bound parameters.
- Cross-table access requires an approved relationship projection. A candidate
  relationship is never authority.
- Execution opens DuckDB read-only with external access and extension autoload
  disabled, under fixed row, byte, runtime, memory, thread, and temp limits.
- A reviewed plan is rebuilt and compared by SHA-256 before execution. A
  mismatch is a blocker, not a warning.
- Failure is fail-closed: no partial plan, no partial result, no partial
  authority.

## Required checks

- The offline suite covering the touched stages.
- `ruff check .`, which enforces the versioned security rule selection.
- The network-boundary architecture test when the change touches egress.
- Blocker coverage for every new rejection path, including its taxonomy entry.

## May do

- Review a deterministic plan and its compiled SQL as evidence.
- Verify dialect compatibility, quoting, and parameter binding.
- Detect unsafe constructs, unapproved joins, and missing limits.
- Verify that read-only and resource properties still hold.
- Propose new blockers and tests for gaps found.

## Never do

- Never generate SQL for the model or the product to execute.
- Never accept provider-produced SQL, physical tables, or physical joins.
- Never invent a join or widen a relationship path.
- Never propose DDL, migrations, indexes, or any write-capable statement. The
  project has no authorized migration or import execution stage.
- Never open a database connection outside the read-only execution contract.
- Never convert a candidate relationship, semantic term, or plan into authority.
- Never bypass the Stage 5A review gate or the Stage 5B hash check.
