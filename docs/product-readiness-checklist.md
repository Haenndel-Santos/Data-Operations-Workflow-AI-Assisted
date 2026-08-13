# Product Readiness Checklist

## Purpose

Track the productization controls highlighted during Sprint 0. This checklist
is intentionally broader than the current backend implementation, so each item
must distinguish design, implementation, test evidence, and release approval.

## Checklist

| Area | Required evidence | Current state |
| --- | --- | --- |
| PRD | Versioned product requirements, non-goals, acceptance criteria | Baseline in [MVP Product Requirements](mvp-prd.md) |
| System map | UI/API/model/analytics/storage/audit boundaries documented | Baseline in [MVP Architecture](mvp-architecture.md) and [Security Architecture](security-architecture.md) |
| Customer Data Boundary | Covered data, trust zones, egress defaults, repository implications | Baseline documented |
| Threat model | Assets, attacker-controlled inputs, boundaries, invariants | Baseline documented |
| RBAC | Roles, permission matrix, enforcement requirements | Baseline documented; not implemented |
| Tenant separation | Tenant policy, storage strategy, tests | Planned; not implemented |
| Row-level security | Database-level or equivalent policy for shared storage | Planned; not implemented |
| Secrets | No secrets in Git/source/logs; runtime secret mechanism | Repository ignore exists; manager not implemented |
| Feature flags | Default-closed providers, upload, training, publication, support access, dynamic execution | Planned; not implemented |
| Error reporting | Local redacted capture, support bundle approval, no private leakage | Planned; not implemented |
| Automated tests | Offline suite plus security/API/UI tests as features land | Existing backend suite strong; product tests pending |
| Security audit gate | Release review for vulnerabilities and control evidence | Planned; not implemented |
| WAF and bot controls | Ingress policy for internet-facing deployments | Deployment planned; not implemented |
| Rate limiting | Per-user/session/IP limits and abuse handling | Planned; not implemented |
| HTTPS/TLS/HSTS | Browser/API transport security | Deployment planned; not implemented |
| Audit logs | Who approved, executed, exported, changed access, changed provider policy | Planned; not implemented |
| Backup and restore | Tested recovery for configs, artifacts, approvals, and audit logs | Planned; not implemented |
| Update and rollback | Safe versioned deployment and rollback path | Planned; not implemented |
| Support model | Customer-approved, redacted diagnostics workflow | Planned; not implemented |

## Release Gate Rule

No commercial or production release should be marked ready until every required
area has:

1. a versioned design;
2. implementation evidence;
3. automated or manual validation evidence;
4. owner-reviewed accepted risk for anything incomplete.

## Current Sprint 0 Result

Sprint 0 completes the baseline design layer for product vision, data boundary,
security architecture, threat model, AI authority split, MVP architecture, MVP
requirements, RBAC, and product readiness. It does not complete product
implementation or production readiness.

