# RBAC Matrix

## Purpose

Define initial role and permission targets for the future product API and UI.
This matrix is not implemented in the current codebase; it is a Sprint 0
security and product design artifact.

## Roles

| Role | Description |
| --- | --- |
| Owner | Customer-side accountable owner for product configuration, provider policy, data-use approvals, and user administration |
| Admin | Operates datasets, connectors, schedules, feature flags, and tenant-local configuration |
| Reviewer | Reviews relationships, semantic definitions, execution plans, expected-answer packs, and corrections |
| Analyst | Asks questions, reviews evidence, explores results, and exports approved outputs |
| Stakeholder | Asks approved-scope questions and consumes Simple View/Analytical View results |
| Support | Views only redacted diagnostics after customer approval |

## Permission Matrix

| Action | Owner | Admin | Reviewer | Analyst | Stakeholder | Support |
| --- | --- | --- | --- | --- | --- | --- |
| Manage users and roles | Yes | Limited | No | No | No | No |
| Configure tenant boundary | Yes | Limited | No | No | No | No |
| Configure provider policy | Yes | No | No | No | No | No |
| Register local dataset | Yes | Yes | No | No | No | No |
| View dataset readiness | Yes | Yes | Yes | Yes | Scoped | No |
| Approve relationships | Yes | No | Yes | No | No | No |
| Approve semantic catalog | Yes | No | Yes | No | No | No |
| Ask question | Yes | Yes | Yes | Yes | Yes | No |
| Resolve clarification | Yes | Yes | Yes | Yes | Scoped | No |
| Approve execution plan | Yes | No | Yes | Scoped | No | No |
| Execute approved plan | Yes | Yes | Yes | Yes | Scoped | No |
| View Simple View result | Yes | Yes | Yes | Yes | Scoped | No |
| View Analytical View evidence | Yes | Yes | Yes | Yes | Limited | No |
| Export result | Yes | Yes | Yes | Yes | No by default | No |
| Record feedback/correction | Yes | Yes | Yes | Yes | Yes | No |
| Apply approved corrections | Yes | No | Yes | No | No | No |
| View audit logs | Yes | Yes | Limited | No | No | No |
| Create support bundle | Yes | Yes | No | No | No | No |
| View support bundle | Yes | Yes | No | No | No | Redacted only |

`Scoped` means the action is limited to datasets, sessions, or analyses that
the user is explicitly authorized to access.

## Enforcement Requirements

- Every persisted product resource must carry tenant and ownership scope, or
  live in a physically isolated single-tenant deployment.
- Authorization must happen before reading dataset metadata, questions,
  results, facts, reports, logs, exports, or support bundles.
- Frontend hiding is not enforcement. The API and storage layer must enforce
  the decision.
- Reviewer authority must be exact and hash-bound, matching the existing
  relationship, semantic, execution, and benchmark review style.
- Support access never includes raw rows, prompts, provider responses, SQL
  parameters, credentials, or unredacted screenshots by default.

## Future Test Targets

- Each endpoint rejects an authenticated user without the required role.
- A user cannot access another tenant's dataset, session, result, export, audit
  event, or support report.
- A role change invalidates or rechecks active sessions.
- Feature flags cannot grant permissions that RBAC denies.
- Plan approval cannot be forged by editing client-side state.

