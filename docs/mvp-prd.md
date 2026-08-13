# MVP Product Requirements

## Status

```yaml
version: 1
status: product_requirement_baseline
created: 2026-08-13
implementation_authority: not_started
```

This PRD defines the first product slice for the customer-hosted Data
Intelligence platform. It is a requirements baseline, not approval to implement
API/UI, call a live provider, process private data, or deploy production
infrastructure.

## Problem

Small and medium-sized businesses often have operational data in ERP exports,
spreadsheets, or local databases but no dedicated analyst to turn that data
into reliable decisions. Generic chat over files is not sufficient because it
can guess relationships, calculate incorrectly, leak data, or hide uncertainty.

## Target Outcome

An authorized stakeholder can ask a plain-language business question and get a
verified answer with evidence:

- the system understands or clarifies the business intent;
- the deterministic backend validates the semantic mapping and analytical plan;
- execution is local, read-only, bounded, and auditable;
- the result is presented in simple business language with an analytical drill
  down;
- corrections remain versioned review evidence.

## MVP Scope

| Area | Requirement |
| --- | --- |
| Dataset readiness | Show whether a dataset has approved relationships, approved semantics, and execution authority |
| Question input | Accept natural-language questions and preserve the authoritative user wording locally |
| Clarification | Stop when terms are ambiguous, unknown, unsafe, or unsupported |
| Plan review | Show metric, dimensions, filters, comparison, join path, limits, and caveats before execution when required |
| Execution | Use existing Stage 5A/5B read-only gates and fixed resource controls |
| Result | Show Simple View and Analytical View backed by the same facts package |
| Evidence | Expose hashes, controls, row/no-row status, preview truncation, blockers, and source identities |
| History | Save local session state and last valid checkpoints |
| Feedback | Record corrections as pending review evidence, not silent state mutation |
| Security | Enforce identity, RBAC, tenant/data-boundary policy, audit logging, and no raw SQL |

## Out Of Scope For MVP

- Model fine-tuning or model-parameter training.
- Hosted provider use.
- External upload or publication.
- Automatic relationship, semantic, or execution approval.
- Full dynamic orchestrator dispatch.
- Multi-provider selection marketplace.
- Production billing, licensing, or support portal.
- Direct frontend access to databases or provider endpoints.
- Shared SaaS-style multi-tenant release for the first pilot.

## Acceptance Criteria

| Criterion | Evidence |
| --- | --- |
| No raw SQL accepted from user or model | API and backend tests reject SQL-like fields and executable SQL |
| No unauthorized execution | Session cannot reach Stage 5B without exact review/authority gates |
| No unapproved joins | Cross-table plans require approved relationship projection |
| No external egress by default | Deployment/API tests prove provider/upload/training flags are closed |
| No cross-user/tenant access | RBAC and tenant tests block unauthorized dataset/session/result reads |
| Result grounding | Simple and Analytical views cite deterministic facts and controls |
| Private artifacts stay local | Git and support-bundle checks exclude raw data, prompts, result rows, secrets, and generated outputs |
| Failure is recoverable | Session reports last valid checkpoint and recovery options |

## MVP 1 Deployment Recommendation

MVP 1 should be planned as a single-tenant, customer-hosted pilot unless owner
review explicitly changes that direction. This keeps the Customer Data Boundary
small: one customer runtime, one local artifact store, and no cross-customer
shared service.

Product resources should still carry tenant or ownership scope where practical,
so a later private-cloud or shared multi-tenant architecture can evolve without
rewriting the Product API, RBAC, audit, or artifact contracts.

## Open Product Questions

- Does the owner accept the single-tenant, customer-hosted MVP 1
  recommendation, or should it be revised before implementation starts?
- Which user roles are required for the first pilot versus later commercial
  packaging?
- Which deployment target is first: local workstation, on-prem server, or
  customer private cloud?
- Which logs are required for support while still satisfying the Customer Data
  Boundary?

