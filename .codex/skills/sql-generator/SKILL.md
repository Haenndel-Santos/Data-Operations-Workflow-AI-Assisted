# SQL Generator

## Purpose

Generate SQL schema, migration drafts, constraints, indexes, and views based only on approved or clearly marked candidate decisions.

## When to use this skill

Use this skill when drafting PostgreSQL-compatible SQL, schema definitions, migration proposals, indexes, constraints, views, or reversible migration notes for EDS ERP modeling work.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Human approval always wins.
- Candidate relationships and candidate keys must remain visibly provisional.
- Product references may need technical/generated `product_id` keys until reconciliation is complete.
- Line-table `ref_nr` values may repeat and should not be treated as unique line IDs without evidence.

## Hard rules

- Do not generate final PK/FK constraints from unapproved candidates.
- Mark provisional constraints clearly.
- Respect human approval files.
- Prefer PostgreSQL-compatible SQL unless the repository specifies otherwise.
- Include evidence and risk notes with constraints.
- Consider rollback or reversibility for migration drafts.

## Recommended workflow

1. Read the shared domain rules and relevant decision notes.
2. Confirm whether each PK/FK/index/view is approved, candidate, blocked, or rejected.
3. Generate final SQL only for approved decisions.
4. Generate provisional SQL only when explicitly labeled as candidate or draft.
5. Add comments or companion notes for assumptions, confidence, unresolved risks, and human approval status.
6. Include reversible migration considerations.

## Expected outputs

- SQL schema draft.
- Migration draft.
- Constraint notes.
- Reversible migration considerations.

## Things to never do

- Never create final constraints from unapproved model candidates.
- Never assume PostgreSQL-incompatible syntax unless the repository requires another dialect.
- Never make product references primary keys without reconciliation evidence.
- Never ignore nullable or duplicate candidate key findings.
- Never mix final and provisional DDL without labeling them.
