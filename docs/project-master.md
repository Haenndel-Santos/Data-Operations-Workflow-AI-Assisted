# Project Master

## Mission

Build a modular, local-first workflow that receives raw operational XLSX/CSV exports and turns them into validated analytical datasets and an evidence-backed ERP data model. It should reduce manual profiling, cleaning, relationship discovery, SQL preparation, and BI export work while preserving analyst control and traceability. The final system should coordinate specialized modules through explicit contracts, support safe partial execution and validation, and remain reproducible without external services.

## Users And Outcomes

Primary users are data and operations analysts working from ERP exports. A successful run produces normalized staging data, profiles, schema/key candidates, relationship evidence, review packages, a local DuckDB analytical layer, Tableau-ready files, and concise documentation.

## Architecture

The package is organized as a Python application under `src/data_ops_lab/`:

- `cli.py` exposes the default pipeline and staged modeling/review commands.
- `workflow.py` coordinates the default conversion-to-export pipeline.
- Specialized modules own conversion, profiling, cleaning, schema inference, validation, SQL suggestions, export, and documentation.
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

## Project Stages

1. **Core analytical pipeline:** implemented for local CSV/XLSX conversion, profiling, cleaning, schema/key detection, relationship validation, DuckDB, Tableau export, and documentation.
2. **ERP source onboarding and candidate modeling:** implemented; versioned candidates remain `pending_review`.
3. **Human review and Product reconciliation:** active. Step 3E.4 contains the explicitly replaced Product state, Step 3E.5 produced a complete validated local Product preview, and Step 3E.6 produced a hash-bound dry-run promotion plan ready for canonical-state review.
4. **Approved canonical model:** pending. The Product promotion plan has not been applied, while `approved_keys.yml` and `approved_relationships.yml` remain intentionally empty.
5. **Migration/import execution:** not started and not authorized until approvals and safeguards exist.
6. **AI-assisted analytics interface:** Stage 5A safe structured query planning, Stage 5B controlled local DuckDB execution, Stage 5C semantic governance, Stage 5D deterministic/provider-neutral translation evaluation, a synthetic Stage 5E exact-answer harness, per-case dataset benchmark review/approval, dry-run immutable binding validation, approved offline dataset-backed execution, deterministic result presentation, recorded grounded narration, a two-phase local session coordinator, and its static declarative module registry are implemented. Northwind now has exact official provenance, MIT licensing, independent conversion equivalence, 13 technically valid PKs, approved local benchmark scope, a completed exact human review accepting all 13 physical relationships, and an applied 111-entity semantic registry with zero compiled blockers or ambiguities. A real structured intent reached Stage 5A execution review without execution. A real benchmark pack, live model provider, dynamic registry execution, and user interface remain pending. The official AdventureWorks 2025 backup is locally restored, integrity-checked, and read-only pending export and review.
7. **Optional product extensions:** UI, richer BI artifacts, and additional performance work remain future options after the backend contracts are validated.

## Global Success Criteria

- Raw sources and completed human decisions are never changed silently.
- Every promoted key or relationship is supported by evidence and approval.
- Candidate and approved states remain mechanically and visibly separate.
- Main workflows run locally with deterministic offline tests.
- Modules expose clear inputs, outputs, failure behavior, and validation.
- The orchestrator can evolve toward partial execution, dry-run, checkpoints, and safe resume without absorbing business logic.
- Documentation and handoff files let a new agent identify the current stage and next safe step in minutes.
