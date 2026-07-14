# Analytics Semantic Catalog Contract

## Module

```yaml
name: analytics_semantic_catalog
version: 1
status: implemented_review_ready
entrypoint: data_ops_lab.analytics_semantic_catalog.run_analytics_semantic_catalog
inputs:
  - candidate_semantic_catalog_yaml
  - local_duckdb_database
  - approved_relationship_registry
outputs:
  - analytics_semantic_catalog.yml
  - analytics_semantic_catalog_blockers.csv
  - analytics_semantic_catalog_report.md
failure_policy: fail_closed_and_preserve_existing_evidence
```

## Purpose

Stage 5C separates stable business language from physical DuckDB names. It
validates dataset/table names, synonyms, dimensions, measures, and relationship
paths against the live local catalog. It produces a normalized term index for a
future natural-language adapter but does not generate a request, SQL plan, or
query execution.

## Input Shape

```yaml
version: 1
dataset:
  id: sales_operations
  name: Sales Operations
  synonyms: [commercial operations]
tables:
  - id: sales_orders
    source_table: orders
    name: Sales Orders
    synonyms: [orders]
dimensions:
  - id: customer
    table_id: sales_orders
    source_column: customer_name
    name: Customer
    synonyms: [client, buyer]
measures:
  - id: order_count
    table_id: sales_orders
    source_column: "*"
    function: count
    name: Order Count
relationship_paths: []
```

Semantic IDs are stable identifiers. `source_table` and `source_column` bind
them to the physical catalog. Measures use the same aggregate allowlist as
Stage 5A; `sum` and `avg` require numeric columns. A `count` measure alone may
use `source_column: "*"`.

## Relationship Paths

Each path contains one to eight contiguous hops expressed with semantic table
IDs and physical source columns. Every hop must match an exact relationship in
`approved_relationships.yml`, in either direction. Candidate relationships are
never accepted or promoted by this module.

## Term Resolution And Ambiguity

Terms are normalized case-insensitively, with accents removed and punctuation
collapsed. IDs, business names, synonyms, and physical table names contribute
to the index.

- `resolved`: exactly one semantic target matches.
- `ambiguous`: multiple targets match; all candidates are preserved and
  `requires_clarification` is true.
- `unknown`: no target matches.
- `catalog_blocked`: the compiled catalog has technical blockers.

The ambiguity score is `1 - (1 / candidate_count)`. Stage 5C never chooses an
ambiguous target silently.

## Approval Boundary

A technically valid output has status `ready_for_semantic_review`. Its approval
fields remain false. This command cannot approve business terminology or
authorize adapter use. A separate human review/apply contract is required
before Stage 5D may rely on the catalog operationally.

## Limits

- 256 semantic tables.
- 512 dimensions.
- 512 measures.
- 256 relationship paths with at most eight hops each.
- 32 synonyms per entity.
- 120 characters per searchable term.
- 1,000 characters per description.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-catalog `
  --catalog "outputs/<run-id>/semantic_catalog_candidate.yml" `
  --database "outputs/<run-id>/duckdb/operations_lab.duckdb" `
  --relationships "config/data_model/approved_relationships.yml" `
  --output "outputs/<run-id>/analytics_semantic_catalog"
```

The command reads metadata only. Existing byte-identical evidence is reused;
different existing evidence is never overwritten.
