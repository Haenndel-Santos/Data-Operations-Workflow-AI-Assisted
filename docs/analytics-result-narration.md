# Grounded Analytics Result Narration Contract

## Module

```yaml
name: analytics_result_narration
version: 1
status: recorded_provider_implemented
entrypoint: data_ops_lab.analytics_result_narration.run_analytics_result_narration
inputs:
  - deterministic_presentation_manifest
  - exact_deterministic_facts_bundle
  - provider
  - bounded_timeout
outputs:
  - analytics_result_narration.yml
  - analytics_result_narrative.md_when_ready
  - analytics_result_narration_blockers.csv
  - analytics_result_narration_report.md
failure_policy: fail_closed_without_narrative_and_preserve_existing_evidence
```

## Grounding Boundary

Before calling a provider, the module verifies that the presentation is ready,
the facts file matches its recorded SHA-256, source hashes agree, and query,
network, result-mutation, and raw-SQL controls are disabled. A provider receives
only the local question, bounded facts, caveats, and response schema. It cannot
issue queries or modify facts.

Every claim must cite one or more supplied fact IDs. Any numeric token in claim
text must exactly match a numeric token in one of its cited values. Row count,
no-row state, and preview-truncation controls are mandatory citations. Unknown,
duplicate, missing, or uncited facts; altered numbers; query language; code
blocks; unsupported fields; and oversized responses fail closed. Provider text
is escaped before Markdown rendering.

This mechanical validation does not prove that arbitrary prose is semantically
correct. The narrative is explicitly non-authoritative; users and downstream
components must retain the deterministic facts and Stage 5B result as evidence.

## Provider And Network Policy

The concrete CLI provider reads a recorded local YAML response and never uses
the network. The Python boundary can represent a network provider, but refuses
to call one without explicit per-invocation authorization. No live provider,
credential, endpoint, retention policy, or online test is selected here.

Recorded response shape:

```yaml
version: 1
headline: Open customer order result
claims:
  - text: The result contains 1 row.
    citations:
      - result.row_count
```

The complete response must also cite `result.no_rows` and
`control.preview_truncated`.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-result-narrate-recorded `
  --presentation-manifest "outputs\<run-id>\analytics_result_presentation\analytics_result_presentation.yml" `
  --facts "outputs\<run-id>\analytics_result_presentation\analytics_result_facts.yml" `
  --provider-response "outputs\<run-id>\recorded_narration.yml" `
  --output "outputs\<run-id>\analytics_result_narration"
```

The command exposes no network switch. Byte-identical evidence is reused and
different existing evidence is not overwritten.
