# ERP Business Flow

## Purpose

Analyze operational ERP flows and discover relationships between commercial, logistics, purchase, sales, and finance documents.

## When to use this skill

Use this skill for mapping ERP document chains, validating sales/purchase/logistics/finance flows, distinguishing header and line tables, and identifying flow breaks or missing relationships.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Confirmed core flow: `Organisation / Debtor -> CP -> OC -> ON -> GO -> GU -> CI`.
- Confirmed supplier-side flow: `Creditor / Organisation -> RFQ -> ON -> GO -> IF`.
- Known prefixes include `CR`, `DE`, `CP`, `OC`, `CQ`, `CI`, `GU`, `GO`, `ON`, `IF`, `RFQ`, `VK`, and `PD`.
- Line/detail tables can contain multiple rows for one header document reference.

## Hard rules

- Use confirmed flows only.
- Document uncertainty.
- Distinguish header tables from line/detail tables.
- Do not invent missing process steps or relationships.
- Flag flow breaks instead of forcing a chain.

## Recommended workflow

1. Read the shared domain rules.
2. Identify the document prefixes and business area involved.
3. Classify each table as header, line/detail, reference, bridge, or unclear.
4. Trace relationships using document references and validated evidence.
5. Record confirmed links, candidate links, blocked links, and flow breaks.
6. List open questions for missing, ambiguous, or conflicting evidence.

## Expected outputs

- Business flow maps.
- Relationship candidates.
- Flow-break reports.
- Open questions.

## Things to never do

- Never treat an observed sequence as confirmed without evidence.
- Never collapse header and line semantics.
- Never hide missing links by inventing intermediate relationships.
- Never ignore supplier-side flow when purchase documents are involved.
- Never override human review or validated outputs.
