# Northwind Expected-Answer Plan Review

## Review State

The Phase 5 answer design produced 13 of 13 exact Stage 5A plans with zero
blockers. On 2026-07-15, the project owner approved every exact hash-bound plan
for sequential, bounded, local read-only answer collection. That authority is
complete; it does not approve the collected expected values.

Authority is bound to:

- answer design SHA-256 `8bce09e23112c1b3cfc300b27e6c9fe7c5fe17600e2b59d170da9b44a7dd93ff`;
- dataset manifest SHA-256 `a28082e46a3f142be58ae3d7078e95c91f21747835caa90f12c3e06a36a92393`;
- DuckDB SHA-256 `4195629326d6aa0a4f7556f6423902eb4b70c4dde11997a5e02fde133c012b76`;
- approved semantic state SHA-256 `bc2daed705320ae344286cd4678645fe54844e11f8657e55c52e999e046f2d10`;
- approved relationships SHA-256 `b12b3f19d199c605fb9e88bfabacb8d1ca9369ba54aa91208d393f99de7efd72`.

The authoritative completed review is versioned as
[northwind.answer-execution-review.yml](../datasets/benchmarks/manifests/northwind.answer-execution-review.yml).
The original pending template remains unchanged under
`outputs/benchmarks/northwind-phase5-answer-preparation-v1/`.
The exact design is
[northwind.answer-benchmark-design.yml](../datasets/benchmarks/manifests/northwind.answer-benchmark-design.yml).

All 13 queries have since completed through the governed materializer. Review
the still-unapproved values in the separate
[Northwind Expected-Answer Review](northwind-expected-answer-review.md).

## What To Check

For every case, confirm that the plan uses the intended table grain, aggregate,
filter values, approved join path, deterministic ordering, limit, output
aliases, and comparison rule. The plans are parameterized; filter values remain
in each corresponding `analytics_request.yml`, not in the plan manifest.

Pay particular attention to fanout safety:

- freight is summed from `orders` without joining to order lines;
- product counts stay at product grain through a many-to-one category join;
- quantities and discounts stay at order-line grain through many-to-one joins;
- territory assignment counts stay at assignment grain through territory and
  region joins.

## Case Checklist

| Case | Exact plan to approve | Parameters and expected output policy |
| --- | --- | --- |
| `total_order_count` | Distinct `orders.order_id` count from `orders`. | No parameters; one integer `order_count`; exact. |
| `customers_by_country` | Group `customers` by country and distinct-count customers; descending count, ascending country; top 10. | No parameters; string `country`, integer `customer_count`; exact. |
| `freight_by_ship_country` | Sum order-grain freight by shipping country; descending freight, ascending country; top 10. | No parameters; string `ship_country`, decimal `freight_total`; exact. |
| `orders_placed_in_1997` | Distinct order count where `order_date >= ?` and `< ?`. | Parameters `1997-01-01`, `1998-01-01`; one integer `order_count`; exact. |
| `discontinued_product_count` | Distinct product count where `products.discontinued = ?`. | Boolean parameter `true`; one integer `product_count`; exact. |
| `products_by_category` | Approved products-to-categories join; distinct product count by category; deterministic descending count. | No parameters; string `category`, integer `product_count`; exact. |
| `units_by_product` | Approved order-lines-to-products join; sum line quantity by product; top 10. | No parameters; string `product`, integer `units_ordered`; exact. |
| `orders_by_shipper` | Approved orders-to-shippers join; distinct order count by shipper. | No parameters; string `shipper`, integer `order_count`; exact. |
| `units_by_supplier_country` | Approved two-hop order-lines-to-products-to-suppliers path; sum line quantity by supplier country; top 10. | No parameters; string `supplier_country`, integer `units_ordered`; exact. |
| `assignments_by_sales_region` | Approved two-hop assignments-to-territories-to-regions path; count assignment rows by region. | No parameters; string `sales_region`, integer `assignment_count`; exact. |
| `customers_without_region` | Customer company names where region is null, alphabetically ordered. | No value parameter for `IS NULL`; string `customer`; exact. |
| `no_orders_for_atlantis` | Order IDs where shipping country equals the supplied value, ascending ID. | String parameter `Atlantis`; integer `order_id`; exact and intentionally expected to yield no rows. |
| `average_discount_by_category` | Approved two-hop order-lines-to-products-to-categories path; average line discount by category. | No parameters; string `category`, float `average_discount_rate`; absolute tolerance `1e-9`, all other cells exact. |

## Decision Boundary

Accepting these plans authorizes only sequential, bounded, local, read-only
Stage 5B answer collection for these exact hashes. It does not authorize live
Ollama evaluation, external upload, publication, model training, narration, or
approval of the resulting expected values. Those values receive a second
per-case human review before any comparative evaluation.
