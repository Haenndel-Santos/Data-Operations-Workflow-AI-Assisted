# MVP Architecture

## Purpose

Define the smallest product slice that can demonstrate the new Data
Intelligence vision without weakening existing governance. This document is
architecture guidance, not implementation authority for API, UI, live provider
use, or production deployment.

## MVP Outcome

A customer-hosted local product slice should let an authorized user:

1. Select an approved local dataset.
2. Ask a natural-language business question.
3. Receive clarification when terms are ambiguous.
4. Review the interpreted semantic intent and deterministic plan.
5. Approve execution when required.
6. Run a bounded read-only analysis.
7. View Simple View and Analytical View backed by the same evidence.
8. Save the analysis history and export safe artifacts inside the boundary.

MVP 1 should target a single-tenant customer-hosted deployment unless owner
review revises that direction. The API and persisted resources should still be
designed with tenant or ownership scope where practical, but shared
multi-tenant SaaS is deferred beyond the first pilot.

## MVP Components

| Component | Responsibility | Status |
| --- | --- | --- |
| Product API | Versioned product boundary for sessions, datasets, questions, reviews, execution, evidence, and exports | Planned |
| Web UI | Stakeholder and reviewer workflows | Planned |
| Identity | Authentication and session binding | Planned |
| RBAC | Role/dataset/action authorization | Planned |
| Dataset registry | Approved dataset metadata and artifact pointers | Partially exists through manifests; product API not implemented |
| Semantic registry | Approved business terms and relationship paths | Implemented for Northwind; generic product surface planned |
| AI interpreter | Provider-neutral translation to semantic intent | Implemented for recorded/local Ollama boundaries |
| Plan compiler | Deterministic Stage 5A planning | Implemented |
| Execution engine | Read-only Stage 5B execution | Implemented |
| Result presentation | Deterministic facts and markdown | Implemented |
| Narration validator | Cited non-authoritative explanation | Recorded provider implemented |
| Audit log | Product-level event and decision trail | Planned |
| Error reporting | Local screenshot/log capture with redaction | Planned |
| Feature flags | Enable/disable modules/providers per deployment and tenant | Planned |

## API Surface Sketch

| Endpoint family | Purpose |
| --- | --- |
| `/datasets` | List approved datasets and readiness state |
| `/sessions` | Create and resume governed analytical sessions |
| `/questions` | Submit a question and receive semantic/clarification state |
| `/reviews` | Record exact human decisions for plans, semantics, relationships, and benchmarks |
| `/executions` | Run only reviewed, authorized plans under fixed limits |
| `/results` | Retrieve facts, Simple View, Analytical View, and evidence |
| `/exports` | Produce approved local exports inside the boundary |
| `/admin/security` | Inspect roles, feature flags, audit settings, and data-boundary policy |
| `/support/reports` | Create local redacted support bundles after user approval |

The API must call existing module entrypoints rather than reimplementing their
domain logic.

## UI Workflow

```text
Dataset readiness
  -> Ask question
  -> Clarify if needed
  -> Review interpretation
  -> Review plan
  -> Execute
  -> Simple View answer
  -> Analytical View evidence
  -> Save/export/feedback
```

The first screen of the application should be the usable analysis workspace,
not a marketing landing page.

## Non-Negotiable MVP Gates

- No API endpoint accepts raw SQL.
- No frontend talks directly to DuckDB/source databases/provider endpoints.
- No execution occurs without the existing Stage 5A/5B gates.
- No cross-table analysis uses unapproved relationships.
- No live provider is enabled without explicit provider authority.
- No logs or support reports export private content by default.
- No multi-user release ships without authentication and RBAC.
- No multi-tenant release ships without tenant isolation tests.

## Deferrable Beyond MVP

- Full dynamic orchestrator dispatch.
- Multi-provider marketplace.
- Shared SaaS-style multi-tenant release.
- Model fine-tuning.
- External warehouse connectors.
- Complex dashboard builder.
- Production billing/licensing.
- Automated relationship approval.
- Cross-tenant benchmarks.

