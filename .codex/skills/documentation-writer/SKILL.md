# Documentation Writer

## Purpose

Standardize Markdown documentation for schema overview, business flow mapping, relationship candidates, and decision logs.

## When to use this skill

Use this skill for writing or updating schema overview documents, business flow maps, relationship candidate tables, decision logs, executive summaries, and Markdown documentation standards.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Documentation must preserve the difference between approved decisions, candidates, blocked items, rejected items, and assumptions.
- Human approval always wins and must be visible when relevant.
- PK/FK recommendations need evidence, confidence, and unresolved risks.

## Hard rules

- Documentation must distinguish approved decisions, candidates, blocked items, and assumptions.
- Use concise tables where useful.
- Include source/evidence notes.
- Do not present uncertain decisions as final.
- Keep terminology consistent with canonical ERP prefixes.

## Recommended workflow

1. Read the shared domain rules.
2. Identify the document type and target audience.
3. Gather source/evidence notes from ERP exports, validated outputs, tests, and human review files.
4. Use tables for decision logs, relationship candidates, flow maps, and risk summaries.
5. Mark unresolved questions and blocked items clearly.
6. Keep executive summaries concise and traceable to evidence.

## Expected outputs

- `schema_overview.md`-style documents.
- `business_flow_mapping.md`-style documents.
- Decision logs.
- Executive summaries.

## Things to never do

- Never remove uncertainty or approval status to make a document look cleaner.
- Never omit evidence for a modeling recommendation.
- Never mix product reference assumptions with confirmed product mappings.
- Never invent source files or validation results.
- Never change data or code while doing documentation-only work.
