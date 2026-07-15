# Northwind Semantic Catalog Review

## Status And Authority

The Northwind semantic catalog is now approved local semantic state. The
versioned candidate is
[`northwind.semantic-catalog-candidate.yml`](../datasets/benchmarks/manifests/northwind.semantic-catalog-candidate.yml)
at SHA-256
`b67181e7de1e1d876719a341d7275d5f493e95d7e6d34c1014c80748b2676b08`.

The current local compilation is under
`outputs/benchmarks/northwind-phase3-semantic-catalog-v2/` and is bound to:

- approved relationship registry SHA-256
  `b12b3f19d199c605fb9e88bfabacb8d1ca9369ba54aa91208d393f99de7efd72`;
- physical DuckDB catalog SHA-256
  `1659954ac2def925cee82348e953820cc49e7d531669d9b2ceab21a4839b323c`;
- compiled semantic catalog SHA-256
  `c46696f29890e70dbbc075882219d9daf319d8749d6a1dbdfead47f91ef0bb0d`.

The original generated template at
`outputs/benchmarks/northwind-phase3-semantic-review/analytics_semantic_review.yml`
remains pending and unchanged. The separate completed review is
[`northwind.semantic-review.yml`](../datasets/benchmarks/manifests/northwind.semantic-review.yml)
at SHA-256
`2528ebd5a6c33da05fab4fab276ae83f239faad95901fd60e0420dd53c91e2c5`.
It records 111 approved entity decisions and zero ambiguity decisions from the
project owner at `2026-07-15T12:20:39.3771266+02:00`.

## What Was Reviewed

The project owner approved the candidate in five groups:

1. **Dataset and table grain:** confirmed that each table description states what
   one row represents. The important transactional grains are one row per order
   in `orders`, one row per order/product pair in `order_details`, and one row
   per employee/territory pair in `employee_territories`.
2. **Dimensions:** confirmed that IDs, names, dates, geography, status, and rate
   fields have accurate business labels and useful English/Portuguese synonyms.
   A synonym must refer to the same concept, not merely a related concept.
3. **Measures:** confirmed the aggregation, source column, grain, and unit implied
   by every measure. Counts use distinct identifiers where possible; the two
   direct row-count measures use their physical row grains.
4. **Relationship paths:** confirmed that every path starts on the detailed side
   and moves many-to-one toward descriptive data. These paths preserve the base
   grain and use only the 13 separately approved physical relationships.
5. **Omissions and caveats:** confirmed that the catalog is honest about concepts
   the source or version-1 contract cannot safely represent.

## Material Modeling Choices

- No `revenue`, `sales amount`, or `net sales` measure is defined. Northwind
  requires a calculated expression over unit price, quantity, and discount,
  while the current contract permits only direct single-column aggregates.
- `order_details.unit_price` is the price captured on an order line before its
  discount. `products.unit_price` is the current product catalog price. They are
  deliberately named as different concepts.
- `discount` is modeled as a fractional line discount rate. Its average is an
  unweighted average across lines.
- `orders.freight` belongs to the order grain. Summing it after expanding an
  order to its lines would duplicate freight and is explicitly unsafe.
- Monetary columns have no currency-code column in this snapshot. The catalog
  does not claim a currency, perform conversion, or mix them into a derived
  monetary measure.
- `units_in_stock` and `units_on_order` are current product snapshots, not
  movements and not time-additive measures.
- `customer_customer_demo` and `customer_demographics` are structurally modeled
  but empty. Their two paths use left joins and have no positive row evidence in
  this snapshot.
- `employees.reports_to` is exposed as the immediate-manager identifier. The
  physical relationship is approved, but the version-1 semantic path contract
  cannot express a self-join, so no employee-to-manager path is proposed.
- Parent-to-child paths are intentionally absent. The 18 proposed paths move
  from order lines, orders, products, assignments, or territories toward
  many-to-one context to reduce fanout risk.
- The candidate compiles to 339 normalized search terms with zero ambiguities.
  Six accidental ID-versus-path synonym collisions found in the first compile
  were removed rather than delegated to unnecessary user clarification.

## Approval Outcome

A complete review now records one factual `approved` decision for the dataset
plus all 13 tables, 60 dimensions, 19 measures, and 18 relationship paths. The
dry-run returned `ready_for_apply` with zero blockers. The approved state at
[`approved_semantic_catalog.yml`](../config/analytics/approved_semantic_catalog.yml)
has SHA-256
`bc2daed705320ae344286cd4678645fe54844e11f8657e55c52e999e046f2d10`
and decision digest
`49c9b9f73a93db4378e441f8ab37dd58d46bd44f8ce48574a02adf8506affc8c`.
Repeated application changed neither evidence nor state.

Approval authorizes only the defined local semantic state and deterministic
adapter scope. It does not authorize a live provider,
external upload, publication, model-parameter training, database writes, or a
Northwind expected-answer benchmark pack.

## Reproduction

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-catalog `
  --catalog "datasets\benchmarks\manifests\northwind.semantic-catalog-candidate.yml" `
  --database "datasets\benchmarks\derived\northwind\northwind.duckdb" `
  --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" `
  --output "outputs\benchmarks\northwind-phase3-semantic-catalog-v2"

.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-review `
  --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" `
  --output "outputs\benchmarks\northwind-phase3-semantic-review\analytics_semantic_review.yml"

.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval `
  --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" `
  --review "datasets\benchmarks\manifests\northwind.semantic-review.yml" `
  --output "outputs\benchmarks\northwind-phase3-semantic-approval-dry-run" `
  --config "config\analytics"

.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval `
  --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" `
  --review "datasets\benchmarks\manifests\northwind.semantic-review.yml" `
  --output "outputs\benchmarks\northwind-phase3-semantic-approval-apply" `
  --config "config\analytics" `
  --apply
```

These commands do not query table rows, execute an analytical request, or use a
network. Only the final explicit `--apply` command writes the approved semantic
state.
