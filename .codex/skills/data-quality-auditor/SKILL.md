---
name: data-quality-auditor
description: Audit ERP and operational data for duplicates, nulls, orphan references, malformed prefixes, inconsistent formats, and suspicious candidate keys without mutating source data. Use for profiling, integrity checks, candidate validation, and human-review shortlist preparation.
---

# Data Quality Auditor

## Purpose

Detect duplicates, nulls, inconsistent references, orphan keys, malformed prefixes, and suspicious candidate keys.

## When to use this skill

Use this skill for profiling raw exports, validating candidate keys, checking FK consistency, finding malformed ERP references, building human review shortlists, and separating data issues from modeling assumptions.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Known prefixes include `CR`, `DE`, `CP`, `OC`, `CQ`, `CI`, `GU`, `GO`, `ON`, `IF`, `RFQ`, `VK`, and `PD`.
- `ref_nr` in line tables is normally a header reference and may repeat.
- Product references can be corrected by `Product_ref.nr.xlsx` and may be incomplete or duplicated before reconciliation.

## Hard rules

- Report issues without changing source data.
- Separate raw data problems from modeling assumptions.
- Never fix data silently.
- Do not treat duplicates as errors until table role and expected grain are known.
- Human review conflicts must be flagged.

## Recommended workflow

1. Read the shared domain rules.
2. Identify table grain, expected prefixes, and candidate key fields.
3. Profile duplicates, nulls, empty strings, malformed prefixes, orphan references, and inconsistent formats.
4. Separate confirmed quality issues from expected line-table repetition or unresolved modeling assumptions.
5. Create a review shortlist for ambiguous or high-impact cases.
6. Recommend next validation checks without modifying data.

## Expected outputs

- Data quality summary.
- Duplicate report.
- Null/empty field report.
- Orphan reference report.
- Recommended review shortlist.

## Things to never do

- Never mutate raw exports or approved outputs during audit work.
- Never normalize or correct values silently.
- Never label repeated line-table references as duplicate defects without checking grain.
- Never hide uncertainty about candidate keys.
- Never bypass human review for ambiguous records.
