# AI Platform Implementation Roadmap

## Purpose

Evolve the current governed analytics backend into a local-first product where
an analyst can connect an approved dataset, review its semantic model, ask a
question in natural language, approve the analytical plan, and receive a
reproducible result with evidence and cited narration without writing SQL.

This roadmap is sequencing guidance, not authority to use real data, connect an
external provider, approve relationships, upload information, train a model, or
deploy to production. Every existing human, privacy, dataset, and execution gate
continues to apply.

## Current Baseline

As of 2026-07-14, the project has:

- governed Stage 5A planning and Stage 5B read-only DuckDB execution;
- semantic review, approval, and Stage 5D deterministic adaptation;
- provider-neutral translation with a recorded offline provider;
- synthetic and separately approved dataset-backed Stage 5E evaluation;
- deterministic result presentation and cited recorded narration;
- a two-phase local session that stops for exact human plan review;
- a versioned static module registry for those session phases with dynamic
  execution, concurrency, network, and review auto-approval disabled;
- 173 passing offline tests and no approved real semantic registry, live model
  provider, production UI, or authorized real benchmark execution.

Phase 0 passed its exit gate on 2026-07-14 through static validation only.
Phase 1 also passed its exit gate with an isolated synthetic baseline and an
exact-contract schema/key DuckDB pushdown: peak process memory fell 27.23% and
runtime fell 98.99% on the fixed 3-table workload. Phase 2 now requires explicit
reference-dataset provenance, license, schema, relationship, and use decisions.
Northwind has since passed provenance, MIT-license, checksum, independent
conversion, schema/key, relationship-integrity, and local-use gates. Phase 2
remains open because all 13 exact relationship candidates still require human
accept/reject decisions before Northwind can enter semantic modeling.

## Target Architecture

```text
approved local dataset
  -> onboarding, profiling, and schema candidates
  -> human-approved semantic catalog and relationships
  -> minimized semantic retrieval context
  -> provider-neutral natural-language interpretation
  -> deterministic structured request and Stage 5A plan
  -> exact human execution review
  -> bounded read-only DuckDB execution
  -> deterministic facts, controls, and evidence
  -> cited non-authoritative narration
  -> governed API, user interface, history, and feedback
```

The model is an interpretation layer. Deterministic local code remains the
authority for schema resolution, SQL compilation, execution, numeric values,
approvals, and evidence.

## Delivery Phases

| Phase | Primary delivery | Exit gate |
| --- | --- | --- |
| 0 | Versioned analytics module registry | Contracts, entrypoints, dependencies, cycles, workflows, and controls pass dry-run validation; execution remains explicit. |
| 1 | Measured scale and memory improvements | Peak memory and runtime baselines exist; at least one measured bottleneck is improved without contract regression. |
| 2 | Approved reference datasets | Each selected dataset has provenance, license, checksum, reproducible conversion, reviewed schema, relationships, and benchmark-use approval. |
| 3 | Real semantic catalogs | Entities, dimensions, measures, synonyms, paths, and ambiguities complete human review for each authorized dataset. |
| 4 | Live provider boundary | At least one provider adapter passes privacy, timeout, failure, cost, and offline-mock tests; network use remains explicit per invocation. |
| 5 | Model and answer evaluation | Provider/model selection is supported by semantic accuracy, answer accuracy, grounding, safety, latency, and cost evidence. |
| 6 | Generic dataset recognition | New datasets produce bounded schema and semantic candidates with confidence/evidence and no automatic approval. |
| 7 | Product API and interface | Users can ask, clarify, review, execute, inspect evidence, export, and revisit analyses through governed sessions. |
| 8 | EDS controlled pilot | EDS semantics and required relationships are approved; local pilot questions are verified against human answers and privacy controls. |
| 9 | Supervised feedback loop | Human corrections become versioned evaluation/retrieval evidence without silently changing approved state or model parameters. |
| 10 | Production and commercialization | Authentication, authorization, isolation, secrets, audit, observability, recovery, packaging, privacy, and support controls pass release review. |

## Phase Details

### Phase 0 - Module Registry

- Define versioned contracts for the analytics-session entrypoints.
- Validate entrypoint existence without calling it.
- Validate module and workflow dependencies, stage order, cycles, capabilities,
  test files, failure policies, and human-review gates.
- Keep dynamic execution, concurrency, network access, and review auto-approval
  disabled.
- Add discovery or dynamic dispatch only in a later reviewed increment.

### Phase 1 - Scale And Memory

- Measure peak memory, runtime, scanned bytes, output size, and temporary storage
  for representative synthetic workloads.
- Locate full-table Pandas loads and rank them by measured cost.
- Move suitable projection, filtering, joining, grouping, and aggregation into
  DuckDB over typed Parquet.
- Use streaming or bounded batches for profiling and validation where exact
  whole-table DataFrames are unnecessary.
- Preserve exact controls for keys, relationships, row counts, and approvals.

### Phase 2 - Reference Datasets

Recommended sequence:

1. Northwind for small commercial flows.
2. Chinook for a different media-commerce domain.
3. AdventureWorks for broader sales, product, purchasing, and dimensional data.
4. EDS only after public/synthetic contracts are proven.

For every dataset, record authoritative source, version, license, SHA-256,
conversion procedure, expected schema, reviewed relationships, semantic state,
benchmark questions, expected requests/results, and separate permitted uses.

### Phase 3 - Semantic Intelligence

- Propose dataset, table, entity, dimension, measure, date, currency, quantity,
  identifier, and relationship-path candidates.
- Add business descriptions and synonyms with evidence and confidence.
- Keep unknown and ambiguous terms visible for clarification.
- Require human review before operational adapter use.
- Build retrieval context from approved semantic metadata, not unrestricted raw
  schema dumps or data rows.

### Phase 4 - Live Model Provider

- Implement interchangeable adapters for an explicitly selected hosted or local
  model while preserving the recorded provider for regression tests.
- Minimize prompts and exclude physical mappings, credentials, approval identity,
  rows, SQL, and unnecessary business metadata.
- Require explicit network authorization, bounded timeout, sanitized failures,
  retention/privacy review, cost limits, and separately labeled online tests.
- Continue rejecting provider-generated SQL and physical joins.

### Phase 5 - Evaluation And Provider Selection

Measure at least:

- intent and semantic-term accuracy;
- table, dimension, measure, filter, order, and relationship selection;
- clarification precision and usefulness;
- exact or reviewed-tolerance answer agreement;
- hallucination and unsafe-output rejection;
- narration citation coverage and numeric fidelity;
- latency, token usage, cost, memory, and execution runtime.

Select a provider only after comparing it against versioned synthetic and
approved dataset-backed packs. Passing recorded cases is not live-model proof.

### Phase 6 - Generic Dataset Recognition

- Detect physical types, nullability, uniqueness, candidate keys, repeated line
  structures, relationship evidence, and business-domain patterns.
- Generate semantic candidates and clarification questions.
- Separate evidence, assumptions, candidates, rejected items, and approved state.
- Support multiple datasets through dataset-specific packs over one stable core
  contract rather than hardcoded EDS rules.

### Phase 7 - API And User Interface

Provide governed views for:

- dataset selection and onboarding status;
- question entry and clarification;
- semantic interpretation and plan review;
- execution progress and last valid checkpoint;
- result table, evidence hashes, controls, caveats, and cited narration;
- saved analyses, exports, feedback, and review history.

Use a versioned local service API as the product boundary. A lightweight UI may
prototype workflows, but a commercial product should keep the backend API and
frontend separable.

### Phase 8 - EDS Pilot

- Approve only the semantic entities and relationships needed by the pilot.
- Keep all EDS processing local unless separate disclosure authority exists.
- Build verified business questions and compare answers with human analysis.
- Measure incorrect interpretations, clarification burden, answer accuracy,
  runtime, and analyst time saved.
- Add masking, role restrictions, audit evidence, and explicit pilot scope.

### Phase 9 - Feedback And Learning

- Store accepted corrections as versioned examples with reviewer authority.
- Use them first for regression packs, semantic retrieval, synonyms, prompt
  improvements, and clarification rules.
- Never let feedback silently alter approved catalogs or relationships.
- Consider fine-tuning only when benchmark evidence shows a durable advantage
  over prompting/retrieval and data governance explicitly permits it.

### Phase 10 - Production Readiness

- Authentication, role/dataset authorization, tenant and session isolation.
- Secret management, provider policies, encryption, retention, and deletion.
- PII classification, masking, export controls, and audit logs.
- Health metrics, traces, failure alerts, cost controls, backups, and recovery.
- Versioned installation, updates, migration policy, licensing, documentation,
  support, and release rollback.

## Critical Path

```text
module registry
  -> measured performance
  -> approved reference datasets
  -> approved semantic catalogs
  -> live provider adapter
  -> comparative evaluation
  -> generic dataset recognition
  -> API and interface
  -> EDS pilot
  -> production controls
```

Performance profiling, UI research, and security design may proceed in parallel,
but they must not bypass dataset, semantic, relationship, review, or privacy
gates on the critical path.

## Quality Targets

Targets must be finalized from benchmark evidence. Initial release gates should
include:

- zero unauthorized database writes or external disclosures;
- zero execution of raw model-generated SQL;
- 100% enforcement of approved relationships and plan-review checkpoints;
- exact numeric preservation between Stage 5B facts and presented values;
- measurable benchmark thresholds for intent and answer accuracy;
- bounded memory, runtime, rows, result bytes, and provider cost;
- reproducible offline main suite with isolated opt-in online tests.

## Indicative Timeline

For one focused developer using coding agents, subject to review availability
and dataset/licensing decisions:

| Outcome | Indicative range |
| --- | ---: |
| Strong technical pilot over approved public datasets | 12-18 weeks |
| Controlled EDS operational pilot | 18-24 weeks |
| Initial commercial product | 24-36 weeks |

These ranges are planning assumptions, not delivery commitments. Re-estimate at
the end of each phase using measured throughput, unresolved approvals, provider
cost, and test results.

## Expected Capability Progression

- Current overall AI-assisted product maturity: approximately 5/10.
- Live provider plus approved semantics and benchmark evidence: approximately
  7/10.
- Multi-dataset recognition, governed UX, continuous evaluation, and production
  controls: approximately 8-8.5/10 as a vertical data-analysis platform.

The goal is not to reproduce the general knowledge of ChatGPT or Claude. The
goal is to be more reliable for governed operational analysis by combining a
capable language model with deterministic data authority and human control.
