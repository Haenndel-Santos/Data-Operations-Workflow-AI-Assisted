# Analytics Semantic Adapter Contract

## Module

```yaml
name: analytics_semantic_adapter
version: 1
status: implemented_offline_intent_compiler
entrypoint: data_ops_lab.analytics_semantic_adapter.run_analytics_semantic_adapter
inputs:
  - structured_semantic_intent_yaml
  - applied_approved_semantic_catalog_yaml
outputs:
  - analytics_semantic_adapter_manifest.yml
  - analytics_request.yml_when_ready
  - analytics_semantic_adapter_blockers.csv
  - analytics_semantic_clarifications.yml_when_required
  - analytics_semantic_adapter_report.md
dependencies:
  - analytics_semantic_approval
  - analytics_query_plan_contract_v1
failure_policy: fail_closed_and_preserve_existing_evidence
```

## Purpose

Stage 5D converts a structured, model-independent semantic intent into the
existing Stage 5A analytics request. It is a deterministic local compiler, not
an AI client. The current implementation does not call a model, parse free text
itself, connect to a database, generate SQL, or execute a query.

The adapter requires an applied semantic registry with:

- `status: approved`;
- `semantic_definitions_approved: true`;
- `adapter_use_authorized: true`;
- `candidate_relationships_accepted: false`.

A technically valid Stage 5C candidate or pending human review is insufficient.

## Intent Contract

```yaml
version: 1
question: Which customers have the highest open sales value?
from: sales orders
relationship_paths:
  - sales customers
dimensions:
  - term: customer
    alias: customer
metrics:
  - term: total sales
    alias: total_sales
filters:
  - term: order status
    operator: eq
    value: open
order_by:
  - field: total_sales
    direction: desc
limit: 25
```

The intent contains terms that must resolve through the approved semantic
index; it cannot provide physical mappings directly. Dimension and metric
entries may also be plain term strings; aliases then default to the approved
semantic ID.

The model or caller cannot choose an aggregate function, source column, or
physical join. Measures retain their approved function and column. Dimensions
and filters retain their approved source columns. `relationship_paths` expand
only the physical hops already present in the approved semantic registry.

## Resolution Outcomes

- `ready_for_query_plan`: writes `analytics_request.yml` for Stage 5A.
- `clarification_required`: writes all candidates and no request.
- `blocked`: writes contract or approval blockers and no request.

An ambiguous term is never narrowed by field context. It remains a clarification
unless prior human semantic approval resolved that exact term to one target.
Unknown terms, semantic-kind mismatches, missing relationship paths, duplicate
aliases, unsupported operators, unsafe limits, raw SQL, and physical joins fail
closed.

## Stage 5A Boundary

`ready_for_query_plan` is not query execution approval. Stage 5A must still open
the authorized local DuckDB file read-only, validate live tables and columns,
revalidate every physical join against `approved_relationships.yml`, and produce
its separate reviewed plan. Stage 5B remains the only controlled execution
boundary.

## Privacy

`analytics_request.yml` intentionally preserves the local question and filter
values needed by Stage 5A. Keep it under generated local outputs and treat it as
potentially private. The adapter manifest, report, and blocker CSV store hashes,
counts, field locations, and governance status without copying the question or
filter values. Clarification evidence includes only the submitted ambiguous term
and approved semantic candidates.

No output is uploaded or sent to a model by this module.

## Limits

Stage 5D aligns with Stage 5A:

- 4,000 characters per question.
- 8 semantic relationship paths and at most 8 expanded joins.
- 64 dimensions, 64 measures, 64 filters, and 64 order rules.
- 1,000 scalar values per `in` filter.
- Result limit between 1 and 10,000.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-adapter `
  --intent "outputs/<run-id>/analytics_semantic_intent.yml" `
  --semantic-state "config/analytics/approved_semantic_catalog.yml" `
  --output "outputs/<run-id>/analytics_semantic_adapter"
```

The repository currently has no approved real semantic state, so the default
command remains blocked for real datasets. Synthetic tests create approved
state only inside pytest temporary directories.
