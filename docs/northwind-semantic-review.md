# Northwind Semantic Catalog Review

## Status And Authority

The Northwind semantic catalog is a technically valid candidate, not approved
semantic state. The versioned candidate is
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

The generated review at
`outputs/benchmarks/northwind-phase3-semantic-review/analytics_semantic_review.yml`
has 111 pending entity decisions and zero ambiguity decisions. It must remain
pending until a human has evaluated the definitions below.

## What The Reviewer Must Evaluate

Review the candidate in five groups:

1. **Dataset and table grain:** confirm that each table description states what
   one row represents. The important transactional grains are one row per order
   in `orders`, one row per order/product pair in `order_details`, and one row
   per employee/territory pair in `employee_territories`.
2. **Dimensions:** confirm that IDs, names, dates, geography, status, and rate
   fields have accurate business labels and useful English/Portuguese synonyms.
   A synonym must refer to the same concept, not merely a related concept.
3. **Measures:** confirm the aggregation, source column, grain, and unit implied
   by every measure. Counts use distinct identifiers where possible; the two
   direct row-count measures use their physical row grains.
4. **Relationship paths:** confirm that every path starts on the detailed side
   and moves many-to-one toward descriptive data. These paths preserve the base
   grain and use only the 13 separately approved physical relationships.
5. **Omissions and caveats:** confirm that the catalog is honest about concepts
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

A complete review requires one `approved` or `rejected` decision and a factual
note for the dataset plus all 13 tables, 60 dimensions, 19 measures, and 18
relationship paths. Version 1 can be applied only when all 111 entities are
approved. A rejection should lead to a revised candidate and new compilation;
it must not be deleted silently from the existing review.

Approval of this catalog would authorize only the separately defined local
semantic state and adapter scope. It would not authorize a live provider,
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
```

Both commands are metadata/review preparation only. They do not query table
rows, apply semantic state, execute an analytical request, or use a network.
