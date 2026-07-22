# AI Phase 5 Provider Selection Scope

## Scope State

```yaml
version: 1
status: pending_owner_review
created: 2026-07-22
decision_supported: select_or_reject_one_exact_local_provider_configuration
candidate_provider: ollama:gpt-oss:20b
candidate_prompt_contract: ollama_semantic_intent_v2
holdout_dataset: pending_owner_selection
dynamic_execution_enabled: false
external_provider_enabled: false
production_use_enabled: false
```

This document is the separately versioned scope required after Backend Phase II.
It fixes a reviewable Phase 5 decision boundary before any new holdout result is
visible. It does not approve the proposed thresholds, select a holdout dataset,
authorize an export or database connection, authorize a live provider call, or
select a provider. Those decisions require the explicit gates below.

## Required Owner Review

| Decision | Current state | Required action |
| --- | --- | --- |
| Primary KPI thresholds and mandatory guardrails | `pending` | Approve or revise this exact metric set before any holdout response is visible |
| Holdout dataset | `pending` | Select AdventureWorks 2025 or name another eligible dataset |
| Phase 5.2 export/conversion work | `not_authorized` | Authorize separately only after the dataset decision |
| Live holdout invocation | `not_authorized` | Authorize separately after every immutable review and dry-run gate passes |

Approval of this document would freeze the metric definitions and thresholds,
not authorize the later database or provider operations.

## Objective

Determine whether the exact local Ollama `gpt-oss:20b` configuration with the
`ollama_semantic_intent_v2` prompt contract is acceptable for controlled local
development in later AI phases. The outcome is `selected_for_controlled_local_development`
or `not_selected`. It is not a production-readiness, external-provider,
commercialization, narration, training, or EDS-data decision.

Northwind remains development evidence. Its approved questions, semantic
intents, expected results, aliases, and repeated soak outcomes cannot be reused
as independent holdout evidence.

The exact provider candidate for the eventual comparison is:

```yaml
name: ollama:gpt-oss:20b
mode: local_live
endpoint: http://127.0.0.1:11434
model: gpt-oss:20b
context_tokens: 8192
max_output_tokens: 1024
timeout_seconds: 120
prompt_contract_version: ollama_semantic_intent_v2
alias_normalization: reviewed_expected_aliases_only_after_non_alias_request_match
```

## Evidence Baseline

| Evidence | Current result | Role in this scope |
| --- | --- | --- |
| Recorded Northwind benchmark | 13/13 passed | Deterministic regression baseline only |
| Northwind live development comparison | 9/13 overall, 11/13 provider acceptance, 9/13 reviewed alias-normalized request agreement, 2/13 literal request agreement | Target-setting evidence only |
| Northwind exact results | 8/12 passed | Development evidence only |
| Northwind reviewed numeric tolerance | 1/1 passed | Development evidence only |
| Northwind provider latency | 31.759 s median, 43.220 s p95 | Local target anchor only |
| Northwind soak | 56 evidenced cycles; stopped safely on the RAM guard | Stability and guard evidence only |

The baseline supports thresholds but does not count toward the holdout
numerators or denominators.

## Proposed Selection Metrics

The thresholds below remain candidate human decisions until the project owner
reviews this exact document. Once approved, they must be frozen before any
provider response or result for the selected holdout is inspected.

### Primary KPIs

| Metric | Exact definition | Proposed gate | Evidence source |
| --- | --- | ---: | --- |
| End-to-end holdout accuracy | `metrics.overall.passed / metrics.overall.evaluated` across every frozen executable holdout case | At least 90%, with at least 20 evaluated cases | Live dataset benchmark manifest and case CSV |
| Reviewed semantic-request accuracy | `metrics.request_accuracy.passed / metrics.request_accuracy.evaluated`; only the existing reviewed expected-alias normalization is permitted | At least 90% | Live dataset benchmark manifest |
| Clarification decision accuracy | Exact match of governed status and clarification terms over the separately frozen live intent holdout | At least 90%, with at least 10 clarification/unknown cases | Bounded live intent evaluation evidence to be implemented in this scope |

Rates are evaluated against all declared cases, including provider rejection,
timeout, skipped, and evaluation-error rows. A missing result never disappears
from a denominator. With the minimum 20 executable cases, the 90% gate requires
at least 18 complete passes.

### Diagnostic Drivers

These metrics explain failures but cannot override a failed primary KPI:

- provider acceptance accuracy: at least 95%;
- table, relationship, dimension, measure, filter, order, and limit accuracy:
  each reported separately, with a target of at least 90%;
- literal request accuracy: always reported and never replaced by the reviewed
  alias-normalized value;
- exact-result and reviewed numeric-tolerance accuracy: reported separately;
- provider wall-time median, p95, maximum, and total;
- prompt and completion token totals and per-call telemetry completeness.

### Mandatory Guardrails

Every guardrail must pass. A primary KPI cannot compensate for a guardrail
failure.

| Guardrail | Required result |
| --- | --- |
| Contract blockers | Exactly zero |
| Unauthorized database writes or external disclosures | Exactly zero |
| Raw model-generated SQL execution | Exactly zero |
| Semantic/request mismatch reaching Stage 5A or Stage 5B | Exactly zero |
| Approved-relationship and exact-plan-review enforcement | 100% |
| Authority hash recheck before provider/query use | 100% of eligible cases |
| Executed-result and execution-control mismatch | Exactly zero executed cases with either mismatch |
| Provider timeout | Exactly zero; a timeout trips the existing circuit breaker |
| Provider wall-time telemetry | Present for 100% of provider calls |
| Provider p95 wall time | At most 60 seconds on the reviewed workstation configuration |
| Hosted API cost for this local candidate | USD 0 |
| External provider, upload, training, narration, publication | All remain false |

The 60-second p95 target is anchored above the measured 43.220-second Northwind
development p95 and below the existing 120-second per-case timeout. It is a
local workstation target, not a portable service-level objective.

## Holdout Design Contract

### Dataset Eligibility

A selected dataset must have, before holdout design:

1. exact source provenance, fixed version, license, byte count, and SHA-256;
2. a reproducible local DuckDB/Parquet representation;
3. validated schema, primary keys, and relationship evidence;
4. a separate completed relationship review and approved projection;
5. a separately completed semantic review and applied approved catalog;
6. explicit local benchmark-design, answer-collection, offline-evaluation, and
   live-loopback-evaluation permissions;
7. no external upload, publication, or model-parameter-training authority.

Current candidates are:

| Dataset | Evidence today | Holdout status |
| --- | --- | --- |
| AdventureWorks 2025 | Exact official Microsoft source and MIT license verified; local read-only restore and integrity checks passed | Preferred candidate, but pending explicit owner selection, reproducible export, relationship review, semantic approval, and benchmark-use approval |
| Pubs | Local conversion exists | Blocked on exact provenance and license confirmation, then all later reviews |
| Contoso recipe | Schema recipe only; external rows were not loaded | Ineligible without a separately approved local dataset |
| Chinook | Recommended by the roadmap but not present in the versioned local inventory | Acquisition and onboarding not authorized by this scope |
| Northwind | Fully approved development pack | Ineligible as the fresh holdout because it informed prompt and alias-policy refinement |

### Executable Answer Pack

The fresh executable pack must contain 20-40 cases, remain within the existing
version-1 benchmark contract, and satisfy all of these minimum coverage rules:

- at least 4 scalar or direct aggregate cases;
- at least 6 grouped aggregate cases;
- at least 6 filter cases spanning equality, range/date, null, and no-row
  behavior;
- at least 4 deterministic order/limit cases;
- at least 5 approved-relationship cases, including at least one multi-hop path
  when the reviewed semantic catalog supports it;
- at least 2 exact no-row or explicit-null cases;
- at least 2 separately reviewed numeric-tolerance cases;
- more than one fact/grain area when the approved catalog supports it.

One case may satisfy multiple coverage rules, but the coverage manifest must
make that overlap explicit. Questions, recorded semantic responses, expected
requests, expected results, comparison policies, and case order must be frozen
and approved before live provider use. Exact Northwind questions, intents,
filters, and expected answers must not be copied.

### Live Intent And Clarification Pack

Provider selection also requires a separately frozen 10-20 case live intent
pack. It must include answerable exact/equivalent questions, ambiguous terms,
unknown terms, clarification cases, hallucination pressure, and requests that
attempt to elicit unsafe output. Expected statuses, accepted semantic intents,
blocker types, and clarification terms require a separate review checkpoint.

The existing synthetic translation evaluator remains the offline regression
authority. A bounded live intent evaluator is a scoped missing capability: it
may call only the exact authorized loopback provider, must not open DuckDB, and
must persist only sanitized IDs, statuses, comparison booleans, blockers, and
telemetry. It must reuse Stage 5D rather than duplicate semantic logic.

## Deterministic Execution Order

1. **Approve this scope.** Review the decision boundary, candidate thresholds,
   dataset choice, and non-authorizations. Stop while any item is pending.
2. **Qualify the selected dataset.** Perform only a separately authorized local
   export/conversion, then validate provenance, license, hashes, schema, keys,
   relationships, and permitted uses. Stop at `ready_for_relationship_review`.
3. **Complete relationship authority.** Review every exact candidate and create
   only the accepted projection. Stop on missing, pending, rejected-as-required,
   conflicting, or drifted review evidence.
4. **Complete semantic authority.** Compile, review, validate, and explicitly
   apply the dataset-specific semantic catalog. Stop before adapter use if any
   semantic item remains unreviewed or drifted.
5. **Design both holdout packs.** Freeze coverage, questions, expected intents,
   exact plans, expected answers, comparison policies, and case order without a
   live provider call.
6. **Approve answer collection.** Use the existing aggregate exact-plan review
   before any Stage 5B table-row access, then materialize candidate answers
   sequentially under fixed limits.
7. **Approve the benchmark authority.** Complete the separate per-case answer
   and comparison review; revalidate the immutable offline pack.
8. **Validate the live intent boundary.** Implement only the missing bounded
   live intent evaluator plus offline mocks and contract tests; do not add
   dynamic dispatch or concurrency.
9. **Freeze exact live authority.** Bind the provider, prompt, endpoint, limits,
   pack hashes, case order, thresholds, and non-authorizations. Run dry-run
   preflight without provider or database access.
10. **Invoke the holdout once.** Require explicit live and loopback-network
    flags. Run sequentially, preserve fail-closed gates, and do not tune prompts,
    aliases, policies, semantics, or expected answers after results are visible.
11. **Record the human decision.** Report each KPI and guardrail independently.
    The project owner records `selected_for_controlled_local_development` or
    `not_selected`; the evaluator cannot select itself.

After step 10, the exposed pack becomes evaluation evidence. A changed prompt,
provider, model, normalization policy, or semantic contract requires a new
authorization and a fresh unseen holdout for a new selection claim.

## Increments And Validation

| Increment | Deliverable | Required checks | Safe stop point |
| --- | --- | --- | --- |
| 5.1 | Reviewed threshold and dataset-selection scope | Internal links and documentation diff | `awaiting_scope_approval` |
| 5.2 | Reproducible selected-dataset export/conversion and reference manifest | Focused conversion/reference tests, independent reproduction, full offline suite | `ready_for_relationship_review` |
| 5.3 | Completed relationship and semantic authority | Focused review/catalog/approval tests and full offline suite | `semantic_catalog_approved` |
| 5.4 | Frozen executable and intent holdout designs, exact plan review, candidate answers, and benchmark approval | Existing preparation/materialization/review/evaluation suites | `ready_for_live_authorization` |
| 5.5 | Bounded live intent evaluator | Offline provider mocks, failure/privacy/immutability tests, full offline suite | `ready_for_live_intent_preflight` |
| 5.6 | Dry-run then one separately authorized live evaluation | Exact authority preflight, explicit live flags, post-run hash recheck | `awaiting_provider_selection_review` |

No increment may consume the authority of a later increment. Partial evidence
remains at its last valid checkpoint and cannot be renamed to a later status.

## Compatibility Boundary

This scope preserves:

- all 47 CLI command registrations and the `data_ops_lab.cli:main` entrypoint;
- explicit domain dispatch and module-specific result formatting;
- the opt-in four-field run-result projection;
- existing hashing, blocker, atomic-publication, source-binding, taxonomy,
  checkpoint, and authority contracts;
- sequential provider execution and the existing Stage 5A/5B gates;
- dynamic registry execution, generic resume, and concurrency disabled.

Any necessary new command must be additive, registered in the existing
analytics domain registrar, and covered by exact parser compatibility tests.

## Explicit Non-Authorizations

This scope does not authorize:

- connecting to SQL Server or exporting AdventureWorks;
- selecting AdventureWorks or any other dataset without explicit owner review;
- changing completed Northwind reviews, packs, approvals, or evidence;
- a provider/network invocation or reuse of an old live authorization;
- hosted or LAN providers, credentials, upload, publication, or training;
- live narration, dynamic dispatch, concurrency, automatic plan approval, or a
  user interface;
- Product canonical apply, EDS relationship approval, migration, import, or
  synchronization;
- production or commercial use of any provider result.

## Phase 5 Exit Gate

Phase 5 may close only when:

1. this scope and its thresholds are explicitly approved before holdout results;
2. the selected dataset and both holdout packs pass every authority gate;
3. recorded/offline regressions pass on the exact frozen contracts;
4. one exact live configuration is evaluated once without holdout tuning;
5. every mandatory guardrail passes;
6. all three primary KPIs pass their fixed thresholds; and
7. a separate human decision records selection or rejection with evidence hashes.

Until then, the current safe resume point is `awaiting_scope_approval`.
