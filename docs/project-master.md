# Project Master

## Mission

Build a modular, customer-hosted, local-first Data Intelligence platform that
receives raw operational XLSX/CSV exports and local database evidence, turns
them into validated analytical datasets and an evidence-backed ERP data model,
and lets small and medium-sized businesses ask governed analytical questions
without requiring SQL or data-analysis expertise. It should reduce manual
profiling, cleaning, relationship discovery, SQL preparation, BI export, and
business-answering work while preserving analyst/reviewer control,
traceability, and private data boundaries. The final system should coordinate
specialized modules through explicit contracts, support safe partial execution
and validation, and remain reproducible without external services by default.

## Users And Outcomes

Primary product users are business owners, managers, and operations teams at
PMEs that need decision-ready analysis but may not have a dedicated analyst.
Data and operations analysts remain advanced users and reviewers. A successful
run produces normalized staging data, profiles, schema/key candidates,
relationship evidence, review packages, a local DuckDB analytical layer,
Tableau-ready files, concise documentation, governed semantic context, and
reproducible answers with evidence.

## Architecture

The package is organized as a Python application under `src/data_ops_lab/`:

- `cli.py` exposes the default pipeline, staged modeling/review commands, and the three opt-in `governed-cleaning-*` commands.
- `workflow.py` coordinates the default conversion-to-export pipeline.
- Specialized modules own conversion, profiling, cleaning, schema inference, validation, SQL suggestions, export, and documentation.
- `governed_cleaning.py` defines the governed cleaning contract (candidates, evidence, computed confidence, hash-bound decisions and cleaning policy, exact authority, lineage) as pure types and functions.
- `governed_cleaning_engine.py` implements the opt-in propose/authorize/apply route over local Parquet with a verified source hash, an ordered hash-bound application plan, atomic publication, and lineage; the legacy cleaner and `run_workflow` are unchanged.
- Modeling modules prepare source onboarding, serial rules, canonical mappings, Product reconciliation, human review, Product materialization previews, dry-run promotion plans, and schema overview artifacts.
- The analytics backend is evolving from fixed SQL suggestions toward validated structured requests, semantic context, and controlled read-only execution.
- The recorded analytics session has a versioned, statically validated module
  registry; dynamic dispatch remains disabled.
- A synthetic isolated-process baseline measures Pandas-heavy stages, and
  schema/key inference now pushes metadata, null, uniqueness, and candidate
  overlap work into local DuckDB without changing candidate/approval state.
- Benchmark onboarding stores raw public samples outside Git, records provenance/checksums, converts supported local T-SQL rows without executing source scripts, and now validates exact reference provenance, license, reproduction, schema, keys, relationship evidence, and use scopes separately from human relationship authority.
- `config/data_model/` stores versioned candidates, business rules, canonical mappings, and separate approved files.
- `tests/` protects workflow behavior and preservation of source/approved files.
- `.codex/` contains project-specific domain rules, skills, and agent profiles.

See `docs/architecture.md` and `docs/orchestrator.md` for boundaries and flow details.
See `docs/ai-implementation-roadmap.md` for the ordered path from the current
backend to approved datasets, live-model evaluation, governed UX, EDS pilot,
and production readiness.
See `docs/backend-phase-2.md` for the active compatibility-preserving
consolidation of shared internal backend contracts.
See `docs/product-vision.md`, `docs/customer-data-boundary.md`,
`docs/security-architecture.md`, `docs/mvp-prd.md`, and
`docs/mvp-architecture.md` for the Sprint 0 product and security baseline.

## Project Stages

1. **Core analytical pipeline:** implemented for local CSV/XLSX conversion, profiling, cleaning, schema/key detection, relationship validation, DuckDB, Tableau export, and documentation.
2. **ERP source onboarding and candidate modeling:** implemented; versioned candidates remain `pending_review`.
3. **Human review and Product reconciliation:** active. Step 3E.4 contains the explicitly replaced Product state, Step 3E.5 produced a complete validated local Product preview, and Step 3E.6 produced a hash-bound dry-run promotion plan ready for canonical-state review.
4. **Approved canonical model:** pending. The Product promotion plan has not been applied, while `approved_keys.yml` and `approved_relationships.yml` remain intentionally empty.
5. **Migration/import execution:** not started and not authorized until approvals and safeguards exist.
6. **AI-assisted analytics interface:** Stage 5A safe structured query planning, Stage 5B controlled local DuckDB execution, Stage 5C semantic governance, Stage 5D deterministic/provider-neutral translation evaluation, a synthetic Stage 5E exact-answer harness, pre-execution answer preparation, sequential candidate-answer materialization, per-case dataset benchmark review/approval, dry-run immutable binding validation, approved offline dataset-backed execution, separate live loopback evaluation, a bounded local endurance harness, deterministic result presentation, recorded grounded narration, a two-phase local session coordinator, and its static declarative module registry are implemented. Northwind now has exact official provenance, MIT licensing, independent conversion equivalence, 13 technically valid PKs, approved local benchmark scope, a completed exact human review accepting all 13 physical relationships, and an applied 111-entity semantic registry with zero compiled blockers or ambiguities. A provider-neutral loopback Ollama `gpt-oss:20b` intent adapter is implemented with explicit socket opt-in, bounded structured output, and isolated live testing. Phase 5 executed 13 separately approved exact plans, produced a typed expected-answer pack with separate immutable approval, passed its recorded offline evaluator 13/13, and completed a separately authorized local live development comparison at 9/13 with all four mismatches blocked before query execution. The soak harness may repeat only that development comparison with concurrency one and resource stop gates. Northwind remains a development set; AdventureWorks 2025 is now the selected fresh holdout and its local read-only export contract is implemented, while real reproducible export and every later relationship, semantic, pack, live-provider, and provider-selection gate remain pending. Live narration, dynamic registry execution, and a user interface also remain pending.
7. **Product and security baseline:** Sprint 0 has documented the PME-oriented
   product vision, Customer Data Boundary, security architecture, threat model,
   AI authority split, MVP requirements, RBAC target, and product readiness
   checklist. These are design baselines, not implemented API/UI/security
   controls.
8. **Product extensions and advanced capabilities:** richer BI artifacts,
   dashboard building, additional connectors, advanced automation, and
   performance optimization remain future options after the MVP Product
   API/UI/security boundary is validated.

## Global Success Criteria

- Raw sources and completed human decisions are never changed silently.
- Every promoted key or relationship is supported by evidence and approval.
- Candidate and approved states remain mechanically and visibly separate.
- Main workflows run locally with deterministic offline tests.
- Modules expose clear inputs, outputs, failure behavior, and validation.
- The orchestrator can evolve toward partial execution, dry-run, checkpoints, and safe resume without absorbing business logic.
- Documentation and handoff files let a new agent identify the current stage and next safe step in minutes.
- Customer data, prompts, results, logs, generated artifacts, and secrets remain
  inside the Customer Data Boundary unless a separate documented authorization
  permits a narrower disclosure.
- The AI remains an interpretation and explanation layer; deterministic code
  remains authority for calculations, permissions, SQL planning/execution, and
  evidence.
