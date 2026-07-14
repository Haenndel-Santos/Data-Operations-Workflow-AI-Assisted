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
- Benchmark onboarding stores raw public samples outside Git, records provenance/checksums, and converts supported local T-SQL rows to DuckDB and compressed Parquet without executing the source scripts.
- `config/data_model/` stores versioned candidates, business rules, canonical mappings, and separate approved files.
- `tests/` protects workflow behavior and preservation of source/approved files.
- `.codex/` contains project-specific domain rules, skills, and agent profiles.

See `docs/architecture.md` and `docs/orchestrator.md` for boundaries and flow details.

## Project Stages

1. **Core analytical pipeline:** implemented for local CSV/XLSX conversion, profiling, cleaning, schema/key detection, relationship validation, DuckDB, Tableau export, and documentation.
2. **ERP source onboarding and candidate modeling:** implemented; versioned candidates remain `pending_review`.
3. **Human review and Product reconciliation:** active. Step 3E.4 contains the explicitly replaced Product state, Step 3E.5 produced a complete validated local Product preview, and Step 3E.6 produced a hash-bound dry-run promotion plan ready for canonical-state review.
4. **Approved canonical model:** pending. The Product promotion plan has not been applied, while `approved_keys.yml` and `approved_relationships.yml` remain intentionally empty.
5. **Migration/import execution:** not started and not authorized until approvals and safeguards exist.
6. **AI-assisted analytics interface:** Stage 5A safe structured query planning, Stage 5B controlled local DuckDB execution, and Stage 5C semantic validation plus explicit human review/application contracts are implemented. A concrete approved semantic registry, natural-language translation, approved benchmark packs, and expected-answer evaluation remain pending. Benchmark storage and restricted Northwind/Pubs conversion are implemented; the official AdventureWorks 2025 backup is locally restored, integrity-checked, and read-only pending export and review.
7. **Optional product extensions:** UI, richer BI artifacts, and additional performance work remain future options after the backend contracts are validated.

## Global Success Criteria

- Raw sources and completed human decisions are never changed silently.
- Every promoted key or relationship is supported by evidence and approval.
- Candidate and approved states remain mechanically and visibly separate.
- Main workflows run locally with deterministic offline tests.
- Modules expose clear inputs, outputs, failure behavior, and validation.
- The orchestrator can evolve toward partial execution, dry-run, checkpoints, and safe resume without absorbing business logic.
- Documentation and handoff files let a new agent identify the current stage and next safe step in minutes.
