# Human Approval Manager

## Purpose

Ensure human decisions are never ignored and that approved review files remain authoritative over automated recommendations.

## When to use this skill

Use this skill whenever a task references approved decisions, review matrices, product reference shortlists, manual validation, conflict handling, or blocked modeling decisions.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Relevant human review files include:
  - `human_approval_matrix.xlsx`
  - `product_refnr_human_review_shortlist.xlsx`
  - `product_reference_human_review.xlsx`
- Human review applies to product references, relationship decisions, approval status, blocked items, and conflict resolution.

## Hard rules

- Human decision overrides automation.
- Never silently replace approved decisions.
- Any conflict between automation and human review must be flagged.
- If a review file is missing, mark the decision as blocked or pending.
- Preserve the distinction between accepted, rejected, pending, blocked, and conflicting decisions.

## Recommended workflow

1. Identify which human review file applies to the task.
2. Confirm whether the file exists and whether its decision is final, pending, rejected, or blocked.
3. Compare automated findings against the human decision.
4. Accept human-approved decisions as authoritative.
5. Flag conflicts and blocked decisions explicitly.
6. Record the evidence source, decision status, and next required human action.

## Expected outputs

- Approval status report.
- Conflict report.
- Blocked decisions.
- Accepted decisions.

## Things to never do

- Never overwrite human decisions with automated inference.
- Never silently discard a conflict.
- Never treat a missing review file as approval.
- Never mark a decision final if human review is required but unavailable.
- Never modify review files unless explicitly requested.
