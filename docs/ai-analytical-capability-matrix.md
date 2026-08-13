# AI Analytical Capability Matrix

## Purpose

Define which parts of the future product may use AI and which parts must remain
deterministic. This prevents "AI-assisted" from becoming unbounded model
agency.

## Authority Split

| Capability | AI role | Deterministic authority |
| --- | --- | --- |
| Understand a user question | Interpret intent and map language to known semantic IDs | Validate against approved semantic catalog and ambiguity rules |
| Recognize business terms | Suggest likely terms or ask for clarification | Resolve only approved terms; preserve ambiguity |
| Discover physical types | May summarize or explain findings | Profiler/schema engine determines types, nulls, and evidence |
| Identify duplicates and nulls | May explain impact or suggest review priority | Data-quality engine detects counts and examples |
| Propose cleaning | Suggest candidate rules and likely canonical forms | Cleaning engine applies reviewed deterministic rules with lineage |
| Choose relationships | May explain candidates and evidence | Only completed human-approved relationships are operational |
| Build analysis | Produce semantic intent within schema | Stage 5D, Stage 5A, and Stage 5B validate and execute |
| Calculate metrics | No authority | DuckDB/statistics engine calculates from approved plan |
| Detect trend or variance | May describe the trend | Deterministic statistical functions calculate deltas and significance rules |
| Explain result | Narrate cited facts | Fact bundle and numeric token validation are authority |
| Recommend action | Contextualize evidence and assumptions | Product must show caveats, confidence, and non-authoritative status |

## Analytical Building Blocks

The future analytical layer should cover these governed concepts:

| Block | Examples | Gate |
| --- | --- | --- |
| Metrics | revenue, margin, units, count, average, freight, stock | Approved semantic measures and deterministic definitions |
| Dimensions | customer, product, supplier, region, employee, date | Approved semantic dimensions |
| Filters | equality, ranges, nulls, no-row behavior | Structured request validation |
| Comparisons | period over period, segment vs segment, top/bottom N | Deterministic plan and result controls |
| Relationships | customer-order-line-product paths, supplier-product paths | Approved relationship projection only |
| Explanations | driver contribution, caveats, confidence | Facts package plus citation validation |
| Clarifications | ambiguous term, unknown term, unsupported request | Explicit clarification state |

## Cleaning Philosophy

AI may generate proposed cleaning rules, but it must not mutate data silently.
The expected contract is:

```yaml
proposed_cleaning_rule:
  target: <table.column>
  operation: <canonicalize | normalize | parse | classify | exclude_candidate>
  confidence: <0.0-1.0>
  affected_rows: <count>
  evidence:
    - <safe aggregate evidence>
  review_state: pending_review
```

The deterministic cleaning engine applies only approved or explicitly scoped
rules and records lineage:

```yaml
lineage:
  original_value_hash: <hash when raw value is private>
  transformed_value: <value or hash depending on privacy policy>
  rule_id: <stable rule id>
  applied_at: <timestamp>
  source_artifact_sha256: <hash>
```

## Benchmark Strategy

Do not fine-tune first. Measure first:

1. Recorded synthetic cases prove contract behavior.
2. Approved public datasets prove deterministic answer correctness.
3. Local live provider runs measure interpretation accuracy and safety.
4. Fresh holdouts protect against prompt tuning leakage.
5. Human corrections become regression and retrieval evidence.
6. Fine-tuning is considered only after benchmarks show prompting/retrieval is
   insufficient and data governance permits model-parameter training.

## Current Evidence

- Northwind recorded benchmark passed 13/13 as deterministic regression
  evidence.
- Northwind local Ollama development comparison passed 9/13 and is not holdout
  evidence.
- AdventureWorks is selected as the fresh holdout, but export, relationship
  review, semantic approval, answer packs, and live invocation remain gated.

