---
name: data-model-architect
description: Define and review ERP schema models, candidate primary and foreign keys, relationships, normalization, and model changes using evidence and approval state. Use for PK/FK recommendations, schema design, relationship discovery, candidate classification, and modeling risk review.
---

# Data Model Architect

## Purpose

Define candidate primary keys, define candidate foreign keys, validate relationships, and prevent inconsistent model changes in the EDS ERP SQL model.

## When to use this skill

Use this skill for schema design, relationship discovery, PK/FK recommendations, relationship validation, normalization decisions, and model change review.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Confirmed document prefixes include `CR`, `DE`, `CP`, `OC`, `CQ`, `CI`, `GU`, `GO`, `ON`, `IF`, `RFQ`, `VK`, and `PD`.
- Confirmed core flow: `Organisation / Debtor -> CP -> OC -> ON -> GO -> GU -> CI`.
- Confirmed supplier flow: `Creditor / Organisation -> RFQ -> ON -> GO -> IF`.
- In line tables, `ref_nr` is normally a document/header reference, not a unique line-level primary key by itself.
- Product references may require reconciliation before they are safe for key decisions.

## Hard rules

- Human review always wins.
- Do not invent relationships.
- Do not promote candidates to final decisions without evidence.
- Document every modeling decision.
- Every PK/FK recommendation must include evidence, confidence, and unresolved risks.
- Keep candidate, approved, blocked, and rejected decisions separate.

## Recommended workflow

1. Read the shared domain rules.
2. Identify the table, fields, ERP prefixes, and likely header/detail role.
3. Check existing validated outputs, tests, ERP exports, and human review files.
4. Evaluate uniqueness, nullability, duplicate risk, orphan risk, and prefix consistency.
5. Classify each relationship as approved, candidate, blocked, or rejected.
6. Record evidence, confidence, unresolved risks, and the next validation step.

## Expected outputs

- PK/FK decision notes.
- Relationship candidate tables.
- Modeling risks.
- Recommended next validation step.

## Things to never do

- Never infer a relationship only from similar column names.
- Never treat a line-table `ref_nr` as unique without proving line-level uniqueness.
- Never override human review with automated findings.
- Never hide uncertainty in final-looking schema language.
- Never convert a candidate into a final constraint without approval evidence.
