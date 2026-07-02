# EDS SQL Codex Knowledge Layer

This `.codex` directory gives future Codex sessions project-specific rules for the EDS ERP SQL modeling workflow. It is a documentation and guidance layer only; it does not change source code, data, migrations, outputs, tests, or analytical results.

Use these skills and agent profiles when working on ERP data modeling, product reference reconciliation, business flow analysis, human approval handling, data quality review, SQL generation, documentation, and validation.

## Shared Context

All skills and agents should use `.codex/project-context/eds-sql-domain-rules.md` as shared project context before making recommendations.

The most important rule is:

**Human approval always wins over automation.**

Human review decisions must never be silently replaced. Conflicts between automated findings and human review files must be flagged clearly.

## Recommended Implementation Order

1. Data Model Architect
2. Product Reference Specialist
3. Human Approval Manager
4. ERP Business Flow Analyst
5. Data Quality Auditor
6. SQL Generator
7. Documentation Writer
8. ERP Test Engineer

## Choosing The Correct Skill

Use the narrowest skill that matches the work:

| Work type | Skill |
| --- | --- |
| Primary key, foreign key, relationship, or schema modeling decisions | `data-model-architect` |
| Product references, `Product_ref.nr.xlsx`, SKU/PD reconciliation, duplicate or missing product refs | `product-reference-specialist` |
| ERP document flow, commercial/logistics/purchase/finance relationships | `erp-business-flow` |
| Approved human review files, conflicting decisions, blocked decisions | `human-approval-manager` |
| Duplicates, nulls, malformed prefixes, orphan references, suspicious keys | `data-quality-auditor` |
| SQL schema, migration drafts, indexes, constraints, views | `sql-generator` |
| Markdown schema docs, flow maps, decision logs, executive summaries | `documentation-writer` |
| Validation checks, pytest planning, regression testing expectations | `test-engineer` |

Use agent profiles in `.codex/agents/` when a task needs several skills combined.

## Global Rules

- Do not invent relationships.
- Prefer evidence from ERP exports, validated outputs, tests, and approved human review files.
- Document every modeling decision.
- Every PK/FK recommendation must include evidence, confidence, and unresolved risks.
- Distinguish approved decisions, candidates, blocked items, and assumptions.
- Do not generate final SQL constraints from unapproved candidates.
- Do not change source data silently.
- Do not assume every product has a valid PD reference.
