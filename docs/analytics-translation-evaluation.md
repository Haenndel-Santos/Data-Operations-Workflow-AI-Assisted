# Analytics Translation Evaluation Contract

## Module

```yaml
name: analytics_translation_evaluation
version: 1
status: implemented_synthetic_offline
entrypoint: data_ops_lab.analytics_translation_evaluation.run_analytics_translation_evaluation
inputs:
  - versioned_synthetic_evaluation_pack_yaml
  - applied_approved_semantic_catalog_yaml
outputs:
  - analytics_translation_evaluation.yml
  - analytics_translation_evaluation_cases.csv
  - analytics_translation_evaluation_blockers.csv
  - analytics_translation_evaluation_report.md
dependencies:
  - analytics_nl_translation
  - analytics_semantic_adapter
failure_policy: validate_before_cases_and_never_overwrite_different_evidence
```

## Purpose

This Stage 5D module evaluates the existing translation and semantic-adapter
boundaries with deterministic synthetic cases. It measures whether the backend
accepts enumerated semantic intents, preserves ambiguity, rejects hallucinated
terms and unsafe provider output, and sanitizes timeout and provider failures.

The bundled fixture pack under `tests/fixtures/analytics_translation/` is test
evidence only. It does not approve a real semantic catalog and does not measure
the accuracy, latency, cost, privacy, or reliability of a live model.

## Pack Contract

A version-1 pack has a stable lowercase `pack_id`, a description, and at most
100 cases. It must cover `exact`, `equivalent`, `clarification`,
`hallucination`, `unsafe`, and `provider_failure`, including both timeout and
generic provider-failure behavior.

Each case contains:

- a stable ID and required category;
- one synthetic question of at most 4,000 characters;
- `response`, `timeout`, or `failure` provider behavior;
- a provider response only for `response` behavior;
- expected status, accepted semantic intents, blocker types, and clarification
  terms.

Ready and clarification cases require one or more accepted semantic intents.
This explicitly supports equivalent valid representations without weakening
the contract to loose string similarity. Blocked cases require exact expected
blocker types and cannot declare an accepted intent. Category/status mappings
and timeout/failure blockers are fixed by the evaluator.

## Execution

Every case uses an in-memory provider with `network_access_required = False`
and calls `run_analytics_nl_translation`. Accepted responses therefore pass
through the same deterministic Stage 5D adapter used by the recorded-response
command. Temporary question and translation files are deleted after each case.

The evaluator compares:

- observed status with expected status;
- the semantic intent, excluding only the authoritative local question, with
  one enumerated accepted intent;
- exact blocker-type sets;
- exact clarification-term sets.

The pack is `passed` only when every case passes. A valid pack with an outcome
mismatch is `failed`. Invalid pack structure or semantic approval produces
`blocked` before any case runs.

## Metrics And Evidence

The manifest reports pass/evaluated counts and rates for overall cases, status,
semantic-intent acceptance, blockers, and clarifications. The case CSV contains
only IDs, categories, statuses, comparison booleans, and pass/fail state.

Persistent evidence omits questions, provider responses, filter values,
provider exception details, and physical mappings. Source files are represented
by SHA-256. Byte-identical reruns reuse evidence; a different rerun must use a
new directory and never overwrites existing generated evidence.

## Offline Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-translation-evaluate `
  --pack "tests/fixtures/analytics_translation/translation_evaluation_pack.yml" `
  --semantic-state "tests/fixtures/analytics_translation/approved_semantic_catalog.yml" `
  --output "outputs/<run-id>/analytics_translation_evaluation"
```

This command uses no network, model API, database, query, migration, import, or
synchronization. Live-provider evaluation requires a separate provider,
credential, privacy, retention, cost, and online-test decision.
