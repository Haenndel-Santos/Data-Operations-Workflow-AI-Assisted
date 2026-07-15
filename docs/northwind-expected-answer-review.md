# Northwind Expected-Answer Review

## Completed Gate

The 13 approved exact plans completed locally and sequentially against the
hash-bound Northwind DuckDB artifact. The candidate pack is
[`northwind.answer-benchmark-pack.yml`](../datasets/benchmarks/manifests/northwind.answer-benchmark-pack.yml),
SHA-256
`68d453860a0bf9841b86b4062ef1265e5876ba1724ed11dca23ce9eb70707683`.
The pack remains mechanically `candidate_for_review`; human authority is kept
separate in the approval below.
The completed human review is
[`northwind.answer-benchmark-review.yml`](../datasets/benchmarks/manifests/northwind.answer-benchmark-review.yml),
SHA-256
`deaa274d7a015071896d91788a7ca8f2d7c2f358e416f4e9b40833242493630f`.
It generated the immutable
[`northwind.answer-benchmark-approval.yml`](../datasets/benchmarks/manifests/northwind.answer-benchmark-approval.yml),
SHA-256
`b1ceda6e675448d3fc808d21af2a919c26de4f2016e7d68dfbb6b32b019016b0`.

The project owner approved the recorded provider response, exact request,
expected result, and comparison policy for every case. Approval is limited to
the recorded local offline evaluation; it does not authorize Ollama, upload,
training, or publication. The summaries below remain a navigation aid, while the
complete pack and immutable approval are the versioned authority.

## Candidate Results

| Case | Candidate expected result | Policy |
| --- | --- | --- |
| `total_order_count` | `830` orders | exact |
| `customers_by_country` | USA 13; France 11; Germany 11; Brazil 9; UK 7; Mexico 5; Spain 5; Venezuela 4; Argentina 3; Canada 3 | exact, top 10 |
| `freight_by_ship_country` | USA 13771.2900; Germany 11283.2800; Austria 7391.5000; Brazil 4880.1900; France 4237.8400; Sweden 3237.6000; UK 2954.2700; Ireland 2755.2400; Venezuela 2735.1800; Canada 2198.0900 | exact decimal, top 10 |
| `orders_placed_in_1997` | `408` orders | exact |
| `discontinued_product_count` | `8` products | exact |
| `products_by_category` | Confections 13; Beverages 12; Condiments 12; Seafood 12; Dairy Products 10; Grains/Cereals 7; Meat/Poultry 6; Produce 5 | exact ordered rows |
| `units_by_product` | Camembert Pierrot 1577; Raclette Courdavault 1496; Gorgonzola Telino 1397; Gnocchi di nonna Alice 1263; Pavlova 1158; Rhönbräu Klosterbier 1155; Guaraná Fantástica 1125; Boston Crab Meat 1103; Tarte au sucre 1083; Chang 1057 | exact, top 10 |
| `orders_by_shipper` | United Package 326; Federal Shipping 255; Speedy Express 249 | exact ordered rows |
| `units_by_supplier_country` | USA 6828; Germany 6120; Australia 6045; UK 5064; France 5023; Italy 4197; Canada 3344; Japan 2551; Norway 2526; Sweden 2151 | exact, top 10 |
| `assignments_by_sales_region` | Eastern 19; Western 15; Northern 11; Southern 4 | exact ordered rows |
| `customers_without_region` | 60 alphabetically ordered company names; first `Alfreds Futterkiste`, last `Wolski  Zajazd` | exact; inspect all 60 rows in the pack |
| `no_orders_for_atlantis` | no rows, status `completed_no_rows` | exact |
| `average_discount_by_category` | Meat/Poultry 0.06445086705202312; Beverages 0.061881188118811825; Seafood 0.06024242424242425; Confections 0.056946107784431155; Dairy Products 0.05344262295081969; Condiments 0.052638888888888874; Produce 0.04544117647058822; Grains/Cereals 0.04530612244897959 | absolute tolerance `1e-9` |

## Recorded Decision

The owner accepted four independent items for every case in the complete pack:

1. `recorded_provider_response`: the semantic intent represents the English question.
2. `expected_request`: the resolved tables, joins, columns, aggregation, filters, order, and limit are correct.
3. `expected_result`: every value, type, row order, control total, and no-row status is correct.
4. `comparison_policy`: exact comparison or the declared numeric tolerance is appropriate.

The completed form keeps `local_offline_evaluation` separate from the three
non-authorized scopes. Approval dry-run/apply and final package validation found
zero blockers. The recorded offline evaluator passed 13/13: 12/12 exact results
and 1/1 reviewed numeric-tolerance result. Its evidence is local under
`outputs/benchmarks/northwind-phase5-recorded-evaluation-v1/` and was
byte-idempotent on rerun. No live provider or network was used.
