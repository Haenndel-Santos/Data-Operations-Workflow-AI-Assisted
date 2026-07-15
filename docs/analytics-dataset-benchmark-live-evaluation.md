# Dataset Benchmark Live Evaluation

## Purpose

`analytics-dataset-benchmark-evaluate-ollama` compares one explicitly approved
dataset-backed answer pack with the local loopback Ollama provider. It is a
Phase 5 evaluation boundary, not a production question endpoint or provider
selection decision.

The Python entrypoint is
`run_analytics_dataset_benchmark_live_evaluation` in
`src/data_ops_lab/analytics_dataset_benchmark_live_evaluation.py`. Version 1 is
implemented and intentionally remains outside dynamic registry dispatch.

## Required Authority

The command requires all of these exact inputs:

- dataset manifest and immutable local DuckDB artifact;
- applied approved semantic state and approved relationships;
- reviewed benchmark pack and its separate offline approval; and
- a separate live-evaluation authorization bound by SHA-256 to every preceding
  input, the ordered case IDs, the exact provider configuration, timeout, prompt
  contract, and execution controls.

The live authorization permits only the named loopback Ollama comparison and
local read-only answer evaluation. It must keep external providers, upload,
model training, narration, and publication false. An older authorization cannot
silently authorize a changed prompt or execution contract; a changed contract
requires a new additive authorization file.

## Invocation Modes

Dry-run is the default. It validates the complete package and live authority,
but makes zero provider calls and never opens DuckDB:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-evaluate-ollama --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --approval "<approval.yml>" --live-authorization "<live-authorization.yml>" --endpoint "http://127.0.0.1:11434" --model "gpt-oss:20b" --context-tokens 8192 --max-output-tokens 1024 --timeout-seconds 120 --output "outputs\<new-preflight-id>"
```

Live mode requires both explicit flags. The endpoint must remain a literal
loopback address and must exactly match the authorization:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-evaluate-ollama --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --approval "<approval.yml>" --live-authorization "<live-authorization.yml>" --endpoint "http://127.0.0.1:11434" --model "gpt-oss:20b" --context-tokens 8192 --max-output-tokens 1024 --timeout-seconds 120 --output "outputs\<new-live-run-id>" --execute --allow-network
```

## Execution Contract

Cases execute sequentially. Before every provider call, before every Stage 5B
query, and after the complete run, the evaluator rehashes the dataset,
semantics, relationships, pack, offline approval, and live authorization. A
provider timeout trips a circuit breaker for the remaining cases.

The provider may emit only approved semantic IDs. The deterministic Stage 5D
adapter must accept the response. Before Stage 5A or Stage 5B can run, every
non-alias request field must equal the reviewed expected request: fact table,
relationship paths, physical semantic mapping, functions, filters and values,
ordering structure and directions, and limit. Version 1 may normalize only
dimension, metric, and corresponding order aliases to their already reviewed
expected aliases. Exact and alias-normalized accuracy are reported separately;
normalization never repairs a semantic difference.

Eligible cases then pass through ordinary Stage 5A planning and Stage 5B
revalidation with these fixed local limits:

- read-only DuckDB;
- 30 seconds per query;
- 512 MB memory, one thread, and 256 MB temporary storage;
- 10,000 result rows and 10,000,000 result bytes.

## Evidence And Failure Policy

Each new output directory contains:

- `analytics_dataset_benchmark_live_evaluation.yml`;
- `analytics_dataset_benchmark_live_evaluation_cases.csv`;
- `analytics_dataset_benchmark_live_evaluation_blockers.csv`; and
- `analytics_dataset_benchmark_live_evaluation_report.md`.

Evidence records component accuracy, pipeline/result/control agreement, provider
latency and token telemetry, hosted API cost, and point-in-time host RAM/GPU
observations. Electricity and hardware depreciation are not costed, and resource
samples are not continuous per-process peak measurements.

Questions, provider responses, expected or actual rows, SQL, parameters, and
filter values are temporary and are not persisted in evaluator evidence. New
evidence is staged and published as one directory. Byte-identical reruns are
reused; an empty, unknown, partial, or divergent existing directory is never
overwritten. Contract drift blocks and discards case evidence. Expectation
failures remain `failed`, separately from contract-level `blocked` status.

## Northwind Development Evidence

On 2026-07-15, the separately authorized 13-case Northwind comparison ran
locally through `gpt-oss:20b` with no external provider or hosted charge.
Authorization v3 SHA-256 is
`a47ffac89f91eaa1e48a1024c5d206887e0c1a2e2269d7f1e6617d1d1e70ba81`.
The final v3 evidence manifest SHA-256 is
`745f0a533956307be6d58056fb219e7efa489386a739a44e47b1c3c0ebc442ff`.

The run passed 9/13 cases end to end and failed four safely before query
execution: two provider rejections, one filter mismatch, and one scalar
alias/limit mismatch. It reported 11/13 provider acceptance, 9/13 semantic
request agreement after the authorized alias-only normalization, 2/13 literal
request agreement, and 9/13 result/control agreement. Eight of twelve exact
cases and the single numeric-tolerance case passed. All 13 calls reported
telemetry: 80,804 prompt tokens, 1,638 completion tokens, 429.073 seconds total
provider wall time, 31.759 seconds median, and 43.220 seconds p95. Observed GPU
use reached 7,461 of 8,192 MB; available system RAM fell from 18,462.6 MB before
the run to a minimum 8,041.5 MB after a case.

This pack was used to refine the general prompt and alias policy, so it is now a
development set rather than a holdout. The 9/13 result is valid development
evidence but does not pass the Phase 5 provider-selection gate. Final model
selection requires a fresh, separately reviewed holdout pack and thresholds
fixed before its live invocation.

## Explicit Non-Authorizations

This contract does not authorize an external or hosted provider, data upload,
model-parameter training, live narration, publication, concurrent evaluation,
dynamic module dispatch, automatic query execution, or production use.
