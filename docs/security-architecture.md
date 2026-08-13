# Security Architecture Baseline

## Purpose

Sprint 0 moves security architecture earlier than production hardening. The
complete implementation can remain phased, but the system boundary, trust
rules, and verification targets must be explicit before API, UI, connectors,
multi-user workflows, or commercial packaging are built.

## Security Objective

Protect customer operational data while preserving governed analysis:

- no unauthorized data disclosure;
- no unauthorized database writes;
- no cross-tenant or cross-user data access;
- no execution of raw model-generated SQL;
- no silent promotion of candidates to approved state;
- no secrets in source code or versioned artifacts;
- no unreviewed live provider, upload, publication, or training use;
- deterministic evidence for every executed answer.

## Control Map

| Product control | Sprint 0 definition | Current implementation state |
| --- | --- | --- |
| PRD | Product vision, MVP, data boundary, and roadmap are versioned before UI work | Added as documentation baseline |
| System map | Product API, UI, local model, semantic layer, analytics engine, connectors, storage, and audit boundaries are defined | Architecture docs updated; no API/UI implemented |
| RBAC | Roles and permissions must be explicit before shared UI execution | Planned, not implemented |
| Tenant separation | Customer data must be partitioned by tenant and deployment policy | Planned, not implemented |
| Row-level security | Future multi-tenant database storage must enforce access below the UI layer | Planned, not implemented |
| Secrets management | Credentials stay out of Git and source code; runtime reads from secret controls | Repository ignores `.env*`; secret manager not implemented |
| Feature flags | Modules/providers/connectors/UI capabilities are enableable by policy | Planned, not implemented |
| Error reporting | Error capture must be local, redacted, and user-approved before external support | Planned, not implemented |
| Automated tests | Main suite remains offline; security controls need focused tests as they are implemented | Existing offline tests are strong for backend gates |
| Security audit | Production deploy requires a release gate for vulnerabilities and control evidence | Planned, not implemented |
| WAF/rate limiting | Internet-facing deployments require ingress controls | Deployment concern, not implemented |
| HTTPS/HSTS | Browser/API traffic requires TLS and strict transport controls | Deployment concern, not implemented |

## Target Product Architecture

```text
Browser UI
  -> Product API
     -> identity and session policy
     -> RBAC and tenant policy
     -> feature flag policy
     -> analytics session coordinator
        -> AI translation boundary
        -> approved semantic catalog
        -> deterministic query planner
        -> exact execution review gate
        -> read-only execution engine
        -> deterministic facts and presentation
        -> grounded narration validator
     -> audit and error reporting
  -> local/customer data stores and connectors
```

The frontend must not talk directly to DuckDB, source databases, provider
endpoints, or private artifact stores. The API is the product boundary that
enforces identity, authorization, workflow state, and audit evidence.

## Trust Boundaries

| Boundary | Rule |
| --- | --- |
| User to UI/API | Authenticate the user, bind session identity, and authorize every dataset/session/action |
| API to analytics modules | Pass only versioned requests and approved state; preserve current CLI/Python contracts |
| LLM to deterministic engine | Accept only schema-validated semantic intent; reject SQL, physical joins, unsupported IDs, and unsafe output |
| Analytics engine to data stores | Use read-only access by default; enforce limits, plan review, and authority hash checks |
| Tenant to tenant | No shared data access without explicit cross-tenant authority; future storage needs tenant keys and/or isolated stores |
| Runtime to internet | Deny customer-data egress by default; explicit provider authority is per invocation |
| Logs/support to external parties | Redact, summarize, and require explicit approval before export |

## Initial Roles

| Role | Intended permissions |
| --- | --- |
| Owner | Configure deployment, manage users, approve high-impact data and provider policies |
| Admin | Manage datasets, connectors, schedules, and access within a tenant |
| Reviewer | Review relationships, semantic definitions, execution plans, expected-answer packs, and corrections |
| Analyst | Ask questions, inspect analytical evidence, export approved results |
| Stakeholder | Ask approved-scope questions and view Simple View answers |
| Support | View sanitized diagnostics only after customer approval |

These roles are design targets. They are not implemented in the current code.

## Security Verification Suite

As features are implemented, tests should prove:

- database writes are impossible in analytics execution paths;
- external egress is denied or explicitly authorized and recorded;
- raw model SQL never reaches planning or execution;
- tenant/user permissions are enforced before dataset, session, result, export,
  and support-bundle access;
- row-level and tenant-level policies prevent cross-customer leakage;
- logs omit prompts, source rows, provider responses, credentials, SQL
  parameters, and private identifiers unless explicitly approved;
- secrets are loaded from runtime controls and never committed;
- feature flags cannot enable unreviewed providers, upload, training,
  auto-approval, or dynamic dispatch;
- error reporting captures useful metadata without leaking private values;
- HTTPS, WAF, rate limiting, backup, restore, retention, deletion, and audit
  controls pass release review.

## Current Backend Controls To Preserve

- Candidate and approved state are separate.
- Human approval remains authoritative.
- Stage 5A compiles structured requests but does not execute.
- Stage 5B revalidates reviewed plans and opens DuckDB read-only.
- Stage 5D rejects model SQL, physical joins, unknown terms, and unsafe output.
- Provider calls are explicit and loopback-only for the selected local
  development path.
- Result narration cites deterministic facts and is non-authoritative.
- Benchmark and holdout authority is hash-bound and staged.
- Generated outputs and private raw data remain outside Git.

## Deployment Controls Not Yet Implemented

- Product API.
- Browser UI.
- Authentication.
- RBAC enforcement.
- Multi-tenant isolation.
- Database row-level security.
- WAF/rate limiting/TLS/HSTS configuration.
- Secret manager integration.
- Central audit logging.
- Error-reporting workflow.
- Update and rollback mechanism.
- Backup/restore automation.
- Release security audit gate.

