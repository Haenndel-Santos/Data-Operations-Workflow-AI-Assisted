# Analytics Semantic Review And Approval Contract

## Modules

```yaml
review:
  name: analytics_semantic_review
  version: 1
  entrypoint: data_ops_lab.analytics_semantic_review.run_analytics_semantic_review
  output: analytics_semantic_review.yml
approval:
  name: analytics_semantic_approval
  version: 1
  entrypoint: data_ops_lab.analytics_semantic_approval.run_analytics_semantic_approval
  outputs:
    - analytics_semantic_approval_plan.yml
    - analytics_semantic_approval_blockers.csv
    - analytics_semantic_approval_report.md
  applied_state: config/analytics/approved_semantic_catalog.yml
failure_policy: fail_closed_and_preserve_existing_review_and_state
```

## Purpose

This contract places explicit human authority between the technically valid
Stage 5C catalog and the future Stage 5D natural-language adapter. Review
preparation is never approval. Approval validation is a dry-run by default, and
state changes require `--apply`.

No real project catalog was approved when this contract was implemented. Tests
use synthetic metadata only.

## Review Workflow

1. Generate a pending review from an exact compiled Stage 5C catalog.
2. A human records a reviewer, timezone-aware ISO-8601 timestamp, one decision
   and note for every semantic entity, and one decision and note for every
   ambiguous term.
3. The human changes `status` from `pending_human_review` to
   `completed_human_review`.
4. Run semantic approval without `--apply` and inspect the plan and blockers.
5. Apply only after the dry-run is accepted and the dataset is authorized.

The review stores the SHA-256 of the compiled catalog. Any catalog drift blocks
approval.

## Decision Rules

Entity decisions are `approved`, `rejected`, or `pending`. Version 1 applies
only when every entity is approved and documented. A rejection does not delete
the entity automatically; it blocks application so the candidate catalog can
be revised and technically revalidated.

Ambiguity decisions are:

- `requires_clarification`: preserve every candidate for future user
  clarification; `selected_target` must be null.
- `approved_target`: select one exact catalog candidate by explicit human
  authority.
- `pending`: block application.

Human notes are required but are not copied into the approved semantic
registry. The registry stores decision IDs, hashes, reviewer identity, review
time, and semantic definitions. Candidate physical relationships remain
unapproved.

## Safety And State

- Dry-run is the default and writes generated evidence only.
- `--apply` writes `approved_semantic_catalog.yml` only for a complete,
  hash-matched review with no blockers.
- A different existing state is refused.
- `--replace-existing` requires `--apply`, explicit authorization, and preserves
  the prior state under `config/analytics/history/`.
- Byte-identical evidence and state are reused.
- No data rows, SQL, DuckDB connection, external database, model API, migration,
  import, synchronization, or relationship promotion is performed.

## Commands

Prepare the review:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-review `
  --catalog "outputs/<run-id>/analytics_semantic_catalog/analytics_semantic_catalog.yml" `
  --output "outputs/<run-id>/analytics_semantic_review/analytics_semantic_review.yml"
```

Validate a completed review in dry-run mode:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval `
  --catalog "outputs/<run-id>/analytics_semantic_catalog/analytics_semantic_catalog.yml" `
  --review "outputs/<run-id>/analytics_semantic_review/analytics_semantic_review.yml" `
  --output "outputs/<run-id>/analytics_semantic_approval"
```

The apply form adds `--apply`. Do not use it until a concrete human-completed
review and dataset-use authorization exist. A replacement additionally requires
`--replace-existing` and separate explicit authority.
