# Deterministic Analytics Result Presentation Contract

## Module

```yaml
name: analytics_result_presentation
version: 1
status: implemented
entrypoint: data_ops_lab.analytics_result_presentation.run_analytics_result_presentation
inputs:
  - exact_stage_5a_request
  - completed_stage_5b_execution_manifest
  - exact_stage_5b_result_csv
outputs:
  - analytics_result_presentation.yml
  - analytics_result_facts.yml_when_ready
  - analytics_result_presentation.md
  - analytics_result_presentation_blockers.csv
failure_policy: fail_closed_without_result_values_and_preserve_existing_evidence
```

## Authority And Validation

The renderer accepts only a completed version-1 Stage 5B execution. It verifies
the request and result SHA-256 bindings, CSV header and shape controls, no-row
state, result byte budget, non-truncation, reviewed-plan controls, read-only
mode, disabled external access, and the raw-SQL prohibition. Failed validation
produces blockers and a value-free diagnostic instead of facts or a preview.

The Stage 5B CSV remains the complete analytical and numeric authority. The
renderer does not connect to DuckDB, execute or modify a query, recalculate
values, infer NULL values from empty CSV text, or change any input.

## Bounded Local Outputs

The local preview is limited to 100 rows, 20 columns, and 2,000 cells. Its facts
bundle preserves displayed CSV text exactly and assigns stable IDs to control
facts and cells. It also records whether the preview is truncated and cites the
request, execution-manifest, and result hashes. The deterministic Markdown
escapes data-provided markup. CSV validation streams the complete bounded file
while retaining only preview rows in memory.

The control manifest contains hashes and counts but no question or result
values. The facts and Markdown necessarily contain local question/preview data
and belong under ignored private output storage.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-result-present `
  --request "outputs\<run-id>\analytics_request.yml" `
  --execution-manifest "outputs\<run-id>\analytics_query_execution\analytics_query_execution.yml" `
  --result "outputs\<run-id>\analytics_query_execution\analytics_query_result.csv" `
  --output "outputs\<run-id>\analytics_result_presentation"
```

Byte-identical reruns reuse existing evidence. Different evidence is never
overwritten; use a new output directory.
