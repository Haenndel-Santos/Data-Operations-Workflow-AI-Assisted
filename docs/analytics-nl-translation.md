# Analytics Natural-Language Translation Contract

## Module

```yaml
name: analytics_nl_translation
version: 1
status: implemented_offline_provider_boundary
entrypoint: data_ops_lab.analytics_nl_translation.run_analytics_nl_translation
inputs:
  - local_utf8_question_file
  - applied_approved_semantic_catalog_yaml
  - injected_semantic_intent_provider
outputs:
  - analytics_nl_translation_manifest.yml
  - analytics_semantic_intent.yml_when_accepted
  - analytics_nl_translation_blockers.csv
  - analytics_nl_translation_report.md
  - semantic_adapter_stage5d_outputs_when_accepted
dependencies:
  - analytics_semantic_approval
  - analytics_semantic_adapter
failure_policy: fail_closed_no_retry_and_preserve_existing_evidence
```

## Purpose

This Stage 5D increment separates free-text translation from deterministic
semantic authorization. A provider receives one local question, approved
semantic metadata, and the version-1 response contract. Its response is never
trusted directly: accepted output must pass through `analytics_semantic_adapter`
before a Stage 5A request can exist.

The module defines a provider-neutral Python protocol. The only concrete
provider currently implemented is `RecordedSemanticIntentProvider`, which reads
a local YAML response and performs no network or model call. No model SDK,
credential, endpoint, retry policy, or online provider is configured.

## Provider Contract

A provider exposes:

```text
name
mode
network_access_required
translate(prompt, timeout_seconds) -> mapping
```

The prompt contains:

- the authoritative local question;
- minimized approved semantic context;
- the allowed version-1 response shape.

The provider must honor the supplied timeout and return one mapping. The runner
catches timeout and provider failures, stores only a sanitized blocker, and does
not retry automatically. A future network provider is not called unless its
invocation explicitly sets `allow_network=True`. The recorded CLI intentionally
has no network flag.

Questions are capped at 16 KiB on disk and 4,000 characters after decoding.
Minimized semantic context is capped at 4 MB, provider responses at 1 MB, and
provider timeouts at 120 seconds.

## Minimized Context

Provider context includes only:

- dataset, table, dimension, measure, and relationship-path semantic IDs;
- approved names, descriptions, and synonyms;
- semantic table ownership for dimensions and measures;
- semantic source/target table IDs for relationship paths;
- unresolved semantic terms and their approved candidates.

It excludes physical table/column/type mappings, aggregate implementation,
source and review fingerprints, approval identity, filter data, table rows, and
database access. Approved descriptions and terms may still be business metadata;
future network exposure therefore requires explicit privacy authorization.

## Provider Response

The provider returns semantic fields only and omits the question:

```yaml
version: 1
from: sales orders
relationship_paths: []
dimensions:
  - term: order status
    alias: status
metrics:
  - term: order count
    alias: orders
filters:
  - term: order status
    operator: eq
    value: open
order_by:
  - field: orders
    direction: desc
limit: 20
```

The local question remains authoritative and is inserted by deterministic code.
Provider `question`, `sql`, `joins`, unknown top-level fields, invalid versions,
and any response rejected by the semantic adapter produce blockers and no
intent file.

## Pipeline

```text
local question file
  -> provider-neutral translation prompt
  -> schema-bounded semantic response
  -> local semantic intent
  -> deterministic Stage 5D semantic adapter
  -> Stage 5A request or clarification/blocker evidence
```

- `ready_for_query_plan`: intent and nested Stage 5D request are written.
- `clarification_required`: intent is retained and the nested adapter writes all
  semantic candidates but no request.
- `blocked`: no intent or nested adapter output is written.

Stage 5A live-catalog validation and Stage 5B reviewed execution remain separate
mandatory boundaries.

## Privacy And Evidence

The question is read from a file to avoid placing it in terminal command history.
It is persisted only in the accepted local intent and nested local request. The
translation manifest stores hashes, provider mode, network authorization,
timeout, counts, and privacy flags. Reports and blockers do not repeat the
question, filter values, or provider exception messages.

Generated intents and requests may contain private business questions and
values. Keep them local under `outputs/` and do not commit or upload them.

## Recorded Offline Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-nl-translate-recorded `
  --question-file "outputs/<run-id>/question.txt" `
  --semantic-state "config/analytics/approved_semantic_catalog.yml" `
  --provider-response "outputs/<run-id>/recorded_semantic_response.yml" `
  --output "outputs/<run-id>/analytics_nl_translation" `
  --timeout-seconds 30
```

This command validates a locally supplied recorded response. It does not infer
the response itself. Real project use remains blocked because no real approved
semantic registry exists.
