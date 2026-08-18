# Agent Knowledge Layer

This directory gives agent sessions project-specific rules for the customer-hosted
Data Intelligence platform described in `docs/product-vision.md`. It is a guidance
layer only: it does not change source code, data, outputs, tests, approvals, or
analytical results.

Skills orient. Code, tests, and CI enforce. When this directory and an executable
check disagree, the check wins and this directory is wrong.

Read `AGENTS.md` (or `CLAUDE.md`), `docs/progress.md`, and the newest entry in
`docs/agent-handoff.md` before selecting a skill.

## Scope

The project began as an EDS ERP/SQL modeling workflow and now targets a broader
product: small and medium-sized businesses asking governed analytical questions
without SQL expertise. ERP knowledge remains valuable, but it is a **domain
specialization**, not the definition of the system.

- Cross-project skills apply to any dataset and any product surface.
- Domain skills carry EDS-specific ERP semantics and apply only to that work.

## Permanent Rules

- Human approval always wins over automation.
- Candidate, pending, approved, rejected, blocked, and conflicting states stay
  mechanically separate.
- The model interprets and explains; deterministic code calculates, authorizes,
  plans, and executes.
- Customer data, prompts, results, logs, and generated artifacts stay inside the
  Customer Data Boundary.
- Do not invent relationships or promote candidates without evidence.
- Generated reports are evidence, never authority over versioned approvals.

## Choosing The Correct Skill

Use the narrowest skill that matches the work.

### Cross-project

| Work type | Skill |
| --- | --- |
| Mission, scope, stage, architecture, or change-alignment review | `project-guardian` |
| Workflow selection, dependency ordering, state, dry-run, or resume design | `project-orchestrator` |
| Module input/output/schema/failure/compatibility definition | `module-contract` |
| Small approved code or documentation implementation | `implementation` |
| Validation checks, pytest planning, regression testing expectations | `test-engineer` |
| Approved human review files, conflicting decisions, blocked decisions | `human-approval-manager` |
| Analytical query planning, semantic adaptation, read-only execution safety | `query-planning-safety` |
| Network, providers, logs, telemetry, exports, or anything that could expose customer data | `customer-data-boundary` |
| Duplicates, nulls, malformed values, orphan references, suspicious keys | `data-quality-auditor` |
| Primary key, foreign key, relationship, or schema modeling decisions | `data-model-architect` |
| Markdown schema docs, flow maps, decision logs, executive summaries | `documentation-writer` |

### Domain: EDS ERP

These carry EDS-specific ERP semantics from
`.codex/project-context/eds-sql-domain-rules.md`. Do not apply them to generic
customer datasets, benchmark datasets, or product API/UI work.

| Work type | Skill |
| --- | --- |
| ERP document flow, commercial/logistics/purchase/finance relationships | `erp-business-flow` |
| Product references, SKU/PD reconciliation, duplicate or missing product refs | `product-reference-specialist` |

Agent profiles in `.codex/agents/` combine several skills. The current profiles
are EDS-oriented and named accordingly.

## Product And Security Baseline

Product, boundary, and security work must start from the Sprint 0 baseline
rather than from this directory:

- [Product Vision](../docs/product-vision.md)
- [Customer Data Boundary](../docs/customer-data-boundary.md)
- [Security Architecture Baseline](../docs/security-architecture.md)
- [Product Threat Model](../docs/threat-model.md)
- [AI Analytical Capability Matrix](../docs/ai-analytical-capability-matrix.md)
- [MVP Architecture](../docs/mvp-architecture.md)

## Enforcement

Guidance in this directory is not a substitute for a check. The mechanical gates
are:

| Invariant | Enforced by |
| --- | --- |
| No known-vulnerable dependency | `pip-audit` in CI |
| No secret in the working tree or history | Gitleaks in CI |
| Correctness and security lint rules | `ruff check .` in CI |
| Contract, approval, and execution behaviour | the offline pytest suite |
| Documentation links resolve | `scripts/check_internal_links.py` in CI |
| Network access stays inside the sanctioned egress allowlist | `tests/network_boundary_test.py` |

Adding a rule here without a corresponding check makes it advisory. Prefer the
check.
