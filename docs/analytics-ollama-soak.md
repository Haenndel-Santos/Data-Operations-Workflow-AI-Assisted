# Local Ollama Overnight Soak

## Purpose

`analytics-ollama-soak` repeatedly exercises the already approved Northwind
development pack through local Ollama, Stage 5D semantic validation, Stage 5A
planning, and eligible read-only Stage 5B execution. It measures sustained local
model stability, answer/request variation, latency, tokens, GPU temperature and
memory, system memory, disk, and technical failures.

The runtime is ordinary local Python, Ollama, and DuckDB. After launch it does
not call Codex or a hosted model API and therefore consumes no Codex or hosted
model tokens. Ollama still reports local prompt/completion token counts as
workload telemetry; these are not billable hosted tokens.

## Why Model Calls Are Sequential

The workstation has an RTX 3070 Ti with 8 GB dedicated VRAM and approximately
32 GB system RAM. The installed `gpt-oss:20b` artifact is about 13 GB. A live
canary used about 7.3 GB VRAM and Ollama split the model workload across CPU and
GPU. The GPU already performs tensor operations in parallel internally.

Version 1 therefore fixes provider concurrency at one. Multiple simultaneous
requests would duplicate context/KV-cache pressure, increase CPU/RAM offload,
and primarily measure resource contention. Sequential repeated inference gives
more reliable stability and quality evidence on this hardware.

## Separate Authority

The soak requires both the exact live-evaluation authorization and a separate
additive soak authorization. The latter binds by SHA-256:

- dataset manifest and local DuckDB artifact;
- approved semantic state and relationships;
- approved benchmark pack and offline answer approval;
- exact live-evaluation authorization;
- provider, model, endpoint, prompt contract, context, output, and timeout;
- duration, cycles, cooldown, concurrency, stop file, and resource limits; and
- explicit false decisions for external providers, parallel model requests,
  upload, training, narration, publication, and production use.

The project-owner authorization for the first run permits 12 hours, at most 96
cycles, a 45-second cooldown, and no more than two consecutive technical cycle
errors. Model quality failures are measured and do not count as technical
errors.

## Safety Limits

The authorized run stops when any of these conditions is observed:

- GPU temperature reaches 78 degrees Celsius;
- available system memory falls below 6,144 MB;
- free disk falls below 20,480 MB;
- a provider timeout occurs;
- two consecutive technical cycle errors occur;
- 12 hours or 96 cycles are reached; or
- a file named `STOP` appears in the run directory.

Resources and the `STOP` file are checked before every model case and throughout
cooldown. A request already in progress may continue only until its configured
120-second provider timeout. NVIDIA's own driver controls remain additional
hardware protection, not a replacement for these application limits.

## Commands

Dry-run validates both authorities and every bound input without provider calls
or DuckDB access:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-ollama-soak --dataset-manifest "datasets\benchmarks\manifests\northwind.dataset-benchmark.yml" --database "datasets\benchmarks\derived\northwind\northwind.duckdb" --semantic-state "config\analytics\approved_semantic_catalog.yml" --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" --pack "datasets\benchmarks\manifests\northwind.answer-benchmark-pack.yml" --approval "datasets\benchmarks\manifests\northwind.answer-benchmark-approval.yml" --live-authorization "datasets\benchmarks\manifests\northwind.live-model-evaluation-authorization-v3.yml" --soak-authorization "datasets\benchmarks\manifests\northwind.ollama-overnight-soak-authorization.yml" --endpoint "http://127.0.0.1:11434" --model "gpt-oss:20b" --context-tokens 8192 --max-output-tokens 1024 --timeout-seconds 120 --output "outputs\benchmarks\<new-soak-preflight>"
```

Live mode adds only the two explicit invocation flags and must use a new output
directory:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-ollama-soak <same-bound-inputs> --output "outputs\benchmarks\<new-soak-run>" --execute --allow-network
```

The policy cannot be weakened through CLI flags; changing it requires a new
authorization.

## Evidence And Monitoring

The root run directory is checkpointed atomically after each cycle and contains:

- `analytics_ollama_soak.yml`: status, PID, heartbeat, authority, limits, totals,
  resource extrema, Python/Ollama process memory, and stop reason;
- `analytics_ollama_soak_cycles.csv`: one safe aggregate row per cycle;
- `analytics_ollama_soak_case_stability.csv`: pass/accept/request/result counts
  per case ID; and
- `analytics_ollama_soak_report.md`: concise current/final summary.

Each `cycles/cycle-NNNN/` directory contains the existing minimized live
evaluation evidence. No soak summary copies questions, responses, SQL,
parameters, filter values, expected rows, or actual rows.

Atomic cycle-directory publication retries only transient `PermissionError`
failures for a bounded maximum of 3.85 seconds. Any destination that appears
during retry is preserved and causes failure. Soak-owned root checkpoint files
use a separate bounded retry of at most 1.9 seconds. The retry policy does not
relax divergent-output or unknown-file protection.

On Windows, each resource sample attributes:

- working set and private memory for the effective Python soak process;
- aggregate working set, private memory, and process count for executables whose
  names begin with `ollama`; and
- total/available system RAM separately.

This attribution is diagnostic evidence. It does not change the 6,144 MB
available-system-memory stop gate.

To inspect progress:

```powershell
Get-Content "<run-directory>\analytics_ollama_soak.yml"
nvidia-smi
```

To request a graceful stop:

```powershell
New-Item "<run-directory>\STOP" -ItemType File
```

The process then stops before the next provider call or during cooldown and
publishes its final checkpoint.

## First Overnight Result

The first authorized run started at 17:16 and stopped safely at 23:55 on
2026-07-15 after available system memory reached 6,089.3 MB, just below the
6,144 MB guard. It completed 57 cycle records over approximately 6 hours 38
minutes. Fifty-six cycles produced case evidence; the last stopped after 11
provider calls, before its final two cases. Recorded totals were 726 provider
calls, 558 passed cases, 4,531,904 prompt tokens, 91,091 completion tokens, zero
timeouts, zero contract blockers, and an empty standard-error log.

Fifty-four evidenced cycles passed 10/13 cases. The first and final evidenced
cycles passed 9/13. Seven cases passed 56/56 times. The persistent gaps were
`customers_without_region` at 0/56 due to limit selection,
`orders_placed_in_1997` at 0/56 due to filter selection, and
`no_orders_for_atlantis` at 1/55 provider calls due primarily to order/limit
selection.

Cycle 27 ran for 375.6 seconds but failed with `PermissionError` before its
cycle directory appeared. Because its result was not published, provider calls,
tokens, and case outcomes from that cycle are not included in recorded totals.
The bounded publication retry was added after this observation. The run
continued successfully from cycle 28.

Point-in-time samples recorded a 52-degree maximum GPU temperature and 7,297 MB
maximum VRAM, while a separate manual launch observation saw 58 degrees, 98%
GPU utilization, and about 172 W. Resource samples therefore remain periodic,
not continuous peak measurements. RAM recovered above 14 GB after the process
ended and Ollama unloaded, so the prior evidence does not by itself identify
which process or Windows cache caused the gradual available-memory decline. The
new process attribution is required for that diagnosis in a future separately
authorized run.

Final evidence-manifest SHA-256:
`72b5e7c7808b3439dd679f62563516e178850a0c3999facfa7fd1747cf371f62`.

## Interpretation

Repeated Northwind results measure development-set stability and local runtime
behavior. They must not be interpreted as new holdout evidence, provider
selection, training, or production readiness. The approved gold answers remain
unchanged regardless of model variation.
