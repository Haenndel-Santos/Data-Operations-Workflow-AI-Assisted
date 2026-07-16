# Agent Handoff

Append new entries in chronological order. Do not edit or remove prior entries.

## 2026-07-13 - Codex - Shared execution protocol adoption

### Initial Context

- Branch: `main`
- Initial commit: `5bb4058`
- Initial worktree: clean and tracking `origin/main`
- Stage found: Product final-review validation blocked by 10 missing required notes
- Objective received: incorporate the supplied execution, efficiency, and multi-agent continuity protocol

### Work Performed

- Added shared agent instructions and responsibility-specific project state documents.
- Added project governance, orchestration, contract, and implementation skills.
- Standardized existing local skills for discovery and validation.
- No source code, private data, generated outputs, approvals, migrations, or runtime dependencies were changed.

### Decisions

- Repository files and Git are the shared memory across agents.
- Existing domain skills remain authoritative for their narrow concerns; new skills cover only missing cross-project responsibilities.
- Latest Product final-review validation supersedes the older pending-question counts.

### Validation

- Skill validation: 12 of 12 local skills valid.
- Tests: 28 passed offline in 3.41 seconds.
- Documentation: 10 internal links checked, 0 broken.
- Diff check: passed; only Windows LF-to-CRLF warnings were reported.
- Online tests: not run; none are required by the current suite.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Stage 3 human review and Product reconciliation; application remains blocked.
- Functionality completed: shared execution protocol, state documents, and valid local skills.
- Functionality partially completed: no Product decisions were applied.
- Known blocker: 10 Product final-review decisions require human notes.
- Do not apply Product decisions, modify approved YAML, run imports/migrations, or edit generated outputs yet.

### Next Logical Steps

1. Have a human complete the 10 missing Product final-review notes.
2. Rerun `validate-product-refnr-final-review` without applying decisions.
3. Define a reversible apply contract only after validation reports readiness and the user authorizes it.

### Useful Commands

```powershell
git status --short --branch
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\check_internal_links.py
```

## 2026-07-13 16:30 +02:00 - Codex - Product blockers rejected and validated

### Initial Context

- Branch: `main`
- Initial commit: `d9dc95e`
- Initial worktree: clean; branch was one commit ahead of `origin/main`
- Stage found: Product final review blocked by 10 missing notes
- Objective received: honor the prior Product approval and treat the 10 blockers as invalid

### Work Performed

- Inspected the final-review and missing-notes workbooks structurally and visually.
- Recorded `rejected` plus an explicit invalid-Product exclusion note for all 10 issue IDs in a new workbook.
- Validated the edited workbook using `validate-product-refnr-final-review`.
- Kept the source review workbook, raw Product files, generated historical outputs, and approved YAML files unchanged.

### Decisions

- The 10 review blockers are invalid Product records and must be excluded from the target Product model.
- The five unmatched original records must not receive generated technical Product identities.
- The clean validation establishes readiness only; it does not authorize an undefined direct write to approved model state.

### Validation

- Product final review: clean and `ready_for_apply=true`.
- Decisions: 28 valid, 18 approved, 10 rejected.
- Blockers: 0 empty, 0 pending, 0 invalid values, 0 missing notes, 0 inconsistencies.
- Formula scan: no spreadsheet formula errors found.
- Visual review: all six sheets rendered and checked.
- Project tests: 28 passed offline in 3.39 seconds.
- Documentation: 10 internal links checked, 0 broken.
- Diff check: passed; only Windows LF-to-CRLF warnings were reported.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Step 3E.4 apply-contract definition.
- Validated workbook: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/product_refnr_human_review_shortlist_validated.xlsx`.
- Historical reports under `outputs/originaldatabase_analysis/` are stale.
- `approved_keys.yml` and `approved_relationships.yml` remain unchanged.

### Next Logical Steps

1. Define a reversible Step 3E.4 input/output and exclusion-state contract.
2. Add tests proving rejected Product items are excluded without mutating raw sources.
3. Implement and run the apply step only after the target-state representation is explicitly approved.

### Do Not Do Yet

- Do not delete Product source rows or overwrite the original review workbook.
- Do not infer how exclusions should be represented in approved model state.
- Do not run migrations, imports, or database writes.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab validate-product-refnr-final-review --output outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b --workbook outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\product_refnr_final_review_invalidated.xlsx
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-13 - Codex - Step 3E.4 contract and dry-run

### Initial Context

- Branch: `main`
- Initial commit: `15f8c3c`
- Initial worktree: clean; branch was two commits ahead of `origin/main`
- Stage found: clean Product review ready for Step 3E.4 contract definition
- Objective received: continue with the next project steps

### Work Performed

- Added the Step 3E.4 application contract, module, and CLI command.
- Added dry-run by default, explicit apply/replace gates, deterministic decision digest, and idempotent state handling.
- Added tests for protected-file preservation, private-value exclusion, rejected-item mapping, idempotency, unresolved context, and divergent-state refusal.
- Ran the real validated workbook in dry-run mode only.

### Decisions

- Proposed approved state is `config/data_model/product_reconciliation_state.yml`.
- Versioned state contains no raw Product references or human notes.
- `rejected` maps to `exclude_from_target_product_model`; it never deletes source rows.
- Writing the proposed state remains pending explicit approval.

### Validation

- Real dry-run: 28 decisions, 18 approved, 10 rejected/excluded.
- Decision digest: `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`.
- Validated workbook, `approved_keys.yml`, and `approved_relationships.yml` SHA-256 hashes remained unchanged.
- `product_reconciliation_state.yml` was not created.
- Focused tests: 7 passed.
- Full offline suite: 33 passed in 3.27 seconds.
- Documentation: 11 internal links checked, 0 broken.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Step 3E.4 contract review before explicit apply authorization.
- Contract: `docs/product-refnr-application.md`.
- Dry-run report: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e4_product_application/product_refnr_application_report.md`.
- The relocated `.venv` editable install and `dataops.exe` still reference the old project location.

### Next Logical Steps

1. Review and approve or revise the proposed `product_reconciliation_state.yml` representation.
2. If approved, run the same command with `--apply` and verify the digest and state diff.
3. Continue downstream Product model construction only from applied state, never by editing raw sources.

### Do Not Do Yet

- Do not use `--apply` or `--replace-existing` without explicit authorization.
- Do not delete or edit Product source rows or review workbooks.
- Do not run migrations, imports, database writes, or external synchronization.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab apply-product-refnr-decisions --workbook outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\product_refnr_human_review_shortlist_validated.xlsx --output outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e4_product_application
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-13 - Codex - Step 3E.4 state applied

### Initial Context

- Branch: `main`
- Initial commit: `4cfc336`
- Initial worktree: clean; branch was three commits ahead of `origin/main`
- Stage found: Step 3E.4 contract and dry-run complete, state application awaiting approval
- Objective received: proceed with the documented next step

### Work Performed

- Treated the user's instruction as explicit approval of the documented state representation.
- Applied the validated Product workbook with `--apply`.
- Structurally validated the state, expected issue IDs, actions, counts, hashes, and absence of private source fields.
- Reapplied the same workbook to prove state-level idempotency.

### Decisions

- `product_reconciliation_state.yml` is now the authoritative Product-specific reconciliation state.
- The 10 rejected review items are logical target-model exclusions and must not receive target Product identities.
- Broader key and relationship approvals remain separate and pending.

### Validation

- Applied digest: `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`.
- State counts: 28 total, 18 approved, 10 rejected/excluded.
- State SHA-256: `7E4E3CF407675B885BBBFD4812FADA03C31D492CD54D0A649315D3E84FBFAD73`.
- Immediate reapplication: `state_changed=False`; state hash unchanged.
- All checked raw-source files, the validated workbook, `approved_keys.yml`, and `approved_relationships.yml` retained their hashes.
- Full offline suite: 33 passed in 3.56 seconds.
- Documentation: 11 internal links checked, 0 broken.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Step 3E.4 complete; Product materialization contract is next.
- Applied state: `config/data_model/product_reconciliation_state.yml`.
- Local apply report: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e4_product_application/product_refnr_application_report.md`.
- No database, migration, import, or external synchronization was run.

### Next Logical Steps

1. Define a Product materialization input/output contract that consumes the applied state.
2. Add preservation, exclusion, technical-ID, referential-integrity, and idempotency tests.
3. Generate and validate a local Product preview before considering any downstream import or database work.

### Do Not Do Yet

- Do not change or replace the applied state without a new reviewed decision set and explicit authorization.
- Do not edit Product source rows or human-review workbooks.
- Do not run migrations, imports, database writes, or external synchronization.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab apply-product-refnr-decisions --workbook outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\product_refnr_human_review_shortlist_validated.xlsx --output outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e4_product_application --apply
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-14 - Codex - Product materialization validation blocked

### Initial Context

- Branch: `main`
- Initial commit: `668db5f`
- Initial worktree: clean; branch was four commits ahead of `origin/main`
- Stage found: Step 3E.4 applied; read-only Product materialization was next
- Objective received: proceed with the next documented milestone

### Work Performed

- Added the Product materialization v1 contract, specialized module, CLI command, and offline tests.
- Reused applied-state validation and the existing Product reconciliation module.
- Implemented exclusion precedence, exact same-row conflict resolution, deterministic source-bound UUID5 IDs, lineage, exclusions, manifests, blockers, and non-overwrite idempotency.
- Ran the real materialization command against the applied state and current private sources.

### Decisions

- Materialization must fail closed when an approved row has no materializable source content.
- No partial Product preview may be generated while blockers exist.
- The applied state remains unchanged; resolving the three empty rows requires a new explicit human decision or corrected source evidence.

### Validation

- Focused tests: 5 passed.
- Full offline suite: 38 passed in 3.75 seconds.
- Documentation: 12 internal links checked, 0 broken.
- Real source counts: 1,734 original Product rows and 1,739 Product_ref.nr rows.
- Real result: `blocked`, 10 exclusion identifiers preserved, 3 blockers, 0 preview rows written.
- Blockers: `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013`; each authoritative source row is completely empty.
- All protected source, review, state, key, and relationship files retained their hashes.
- Repeated blocked run: `outputs_changed=False`; blocker artifacts retained their hashes.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Step 3E.5 blocked pending human decision on three empty approved records.
- Contract: `docs/product-materialization.md`.
- Local report: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e5_product_materialization/product_materialization_report.md`.
- No Product preview, database, import, migration, or external synchronization was produced.

### Next Logical Steps

1. Ask the human owner whether the three empty rows are invalid/rejected or whether corrected source evidence exists.
2. If rejected, update the review and applied state through the existing explicit contracts; do not hand-edit the state.
3. Rerun materialization and validate the complete preview, lineage, exclusions, references, and deterministic IDs.

### Do Not Do Yet

- Do not generate technical Product identities for the three empty rows.
- Do not silently remove the rows from an otherwise partial preview.
- Do not change the applied state without explicit human authority.
- Do not run migrations, imports, database writes, or external synchronization.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab product-materialization-preview --workbook outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\product_refnr_human_review_shortlist_validated.xlsx --output outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e5_product_materialization
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-14 - Codex - Empty Product rows rejected and preview completed

### Initial Context

- Branch: `main`
- Initial commit: `7d41fb3`
- Initial worktree: clean; branch was five commits ahead of `origin/main`
- Stage found: Step 3E.5 blocked by three approved but completely empty `Product_ref.nr` rows
- Objective received: proceed and treat the empty records as invalid

### Work Performed

- Created a new review workbook without changing the prior validated workbook and set `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013` to `rejected` in every review occurrence.
- Validated all 28 final decisions and visually inspected all six workbook sheets before and after validation.
- Replaced the applied Product reconciliation state through the existing explicit command and preserved the previous state in versioned history.
- Generated and structurally validated a complete local Product preview, lineage, exclusions, manifest, and report.
- Repeated state application and materialization to verify byte-stable idempotency.

### Decisions

- The three completely empty `Product_ref.nr` rows are invalid target Product records and receive no Product identity.
- Decision digest `4f14e2cb265d9729263ab5bd572a41365f4bbbceec7e007d930b539faa5fe260` supersedes the prior applied digest.
- The generated preview remains local evidence only; no database, import, migration, or synchronization is authorized.

### Validation

- Review validation: 28 valid decisions, 15 approved, 13 rejected, no pending or inconsistent rows.
- Applied state SHA-256: `45CE926042BE43261128B869E301E47511FCBFD5EF449741289A427A5BEEA5C7`.
- Previous state backup SHA-256: `7E4E3CF407675B885BBBFD4812FADA03C31D492CD54D0A649315D3E84FBFAD73`.
- Materialization: `ready_for_local_preview`, 1,733 preview rows, 13 exclusions, zero blockers.
- Preview integrity: 1,733 unique filled `product_id` values, zero empty or duplicate `product_ref_nr` values, and no excluded identifiers in lineage.
- Repeated application: `state_changed=False`; repeated materialization: `outputs_changed=False`; all compared hashes unchanged.
- Full offline suite: 38 passed in 4.14 seconds.
- Documentation: 12 internal links checked, 0 broken.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Step 3E.5 complete with a validated local Product preview.
- Applied state: `config/data_model/product_reconciliation_state.yml`.
- Local review: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e5_empty_rows_rejected/product_refnr_human_review_shortlist_validated.xlsx`.
- Local materialization report: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e5_product_materialization_resolved/product_materialization_report.md`.

### Next Logical Steps

1. Review the completed local Product preview and exclusion evidence.
2. Define an explicit offline consumption or promotion contract for the canonical Product model.
3. Keep broader key and relationship approvals separate until business context is available.

### Do Not Do Yet

- Do not restore identities for rejected records or consume stale blocked outputs.
- Do not edit raw Product sources or prior validated review workbooks.
- Do not run migrations, imports, database writes, or external synchronization.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab product-materialization-preview --workbook outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e5_empty_rows_rejected\product_refnr_human_review_shortlist_validated.xlsx --output outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e5_product_materialization_resolved
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-14 - Codex - Step 3E.6 canonical promotion dry-run

### Initial Context

- Branch: `main`
- Initial commit: `4e3fb60`
- Initial worktree: clean; branch was six commits ahead of `origin/main`
- Stage found: Step 3E.5 complete with a validated local Product preview
- Objective received: continue with the next project steps

### Work Performed

- Added an explicit Step 3E.6 dry-run module contract and CLI command with no apply option.
- Validated all six Step 3E.5 artifacts against the applied reconciliation digest, workbook hash, model contract, manifest, technical IDs, lineage, exclusions, references, and counts.
- Added fail-closed blockers, private-value exclusion, deterministic non-overwrite behavior, and tests for drift and malformed manifests.
- Ran the real resolved Product package twice and verified byte-stable idempotency.

### Decisions

- Canonical Product promotion requires a hash-bound dry-run checkpoint before any apply contract can be considered.
- `ready_for_canonical_state_review` is not canonical approval and does not authorize a configuration or database write.
- Versioned Step 3E.6 evidence contains hashes, schema, counts, and validation only; Product row values remain in ignored local outputs.

### Validation

- Real status: `ready_for_canonical_state_review`, 1,733 candidate rows, 13 exclusions, zero blockers.
- Repeated real run: `outputs_changed=False`.
- Plan SHA-256: `B919946919ED3C9A908A5B72A0AD3FF0C7A5BB1FDBBC78D05181AC1DA42E7A6B`.
- Private preview values found in Step 3E.6 outputs: zero.
- Applied state, `canonical_tables.yml`, approved keys, and approved relationships retained their prior hashes.
- Focused tests: 5 passed in 1.00 seconds.
- Full offline suite: 43 passed in 3.92 seconds.
- Documentation: 13 internal links checked, 0 broken.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Current stage: Step 3E.6 dry-run complete; canonical Product state remains unapplied.
- Contract: `docs/product-canonical-promotion.md`.
- Local plan: `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e6_product_canonical_promotion/product_canonical_promotion_plan.yml`.
- Applied Product reconciliation state remains `config/data_model/product_reconciliation_state.yml`.

### Next Logical Steps

1. Review the Step 3E.6 plan and approval boundary.
2. Decide how a minimal applied canonical Product state should be represented without versioning private rows.
3. Define, test, and explicitly authorize a separate apply contract before changing canonical configuration.

### Do Not Do Yet

- Do not treat dry-run readiness as approval or edit `canonical_tables.yml` directly.
- Do not copy private Product rows into versioned files.
- Do not run migrations, imports, database writes, or external synchronization.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab product-canonical-promotion-plan --materialization outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e5_product_materialization_resolved --state config\data_model\product_reconciliation_state.yml --output outputs\019f21a4-daf0-7272-b2a7-09b4f0e2c75b\step3e6_product_canonical_promotion
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-14 - Codex - Stage 5A safe analytics query planning

### Initial Context

- Branch: `main`
- Initial commit: `81a9d67`
- Initial worktree: clean; branch was seven commits ahead of `origin/main`
- Stage found: Product Step 3E.6 dry-run complete; conversational analytics remained a future concept
- Objective received: implement the backend direction for natural-language analysis, scalable local processing, and multi-dataset learning

### Work Performed

- Defined the AI-assisted analytics backend, scale strategy, dataset governance, success measures, and Stages 5A through 5G.
- Added a structured version-1 request contract between future natural-language interpretation and SQL.
- Implemented `analytics-query-plan` with read-only DuckDB catalog discovery, strict table/column resolution, allowlisted aggregates and filters, bounded requests, approved joins, identifier quoting, and parameterized values.
- Added deterministic ready/blocked plan, blocker, and report artifacts without executing SQL or copying question/filter values.
- Added tests that execute the compiled SQL only against a temporary synthetic DuckDB fixture.

### Decisions

- AI models may propose structured intent but may not submit executable raw SQL.
- Cross-table queries require exact human-approved relationships; candidates are insufficient.
- EDS is private local evaluation/retrieval evidence, not authorized parameter-training data.
- AdventureWorksDW2019 and Chinook are candidate evaluation benchmarks only after source, license, checksum, schema, and relationship review.
- Initial learning work means deterministic evaluation and grounded retrieval; fine-tuning remains optional and separately governed.

### Validation

- Focused query-plan tests: 7 passed in 1.52 seconds.
- Full offline suite: 50 passed in 5.02 seconds.
- Documentation: 16 internal links checked, 0 broken.
- Tests prove parameter privacy, read-only database preservation, byte-stable idempotency, approved cross-table execution, unapproved-join blocking, raw-SQL rejection, date parameters, and non-overwrite behavior.
- No EDS query, public dataset download, external database connection, model API call, or SQL write was performed.

### State For Next Agent

- Branch: `main`
- Final commit: the commit containing this handoff entry; verify with `git log -1`.
- Product track: Step 3E.6 remains ready for canonical-state review but unapplied.
- Analytics track: Stage 5A query planning is implemented; execution is not authorized or implemented.
- Backend roadmap: `docs/ai-analytics-backend.md`.
- Query-plan contract: `docs/analytics-query-plan.md`.

### Next Logical Steps

1. Define Stage 5B controlled local execution with read-only enforcement, timeout/resource/result limits, and result manifests.
2. Test execution only against synthetic temporary fixtures before requesting EDS dataset authorization.
3. Design dataset-specific semantic/benchmark packs before onboarding AdventureWorks or Chinook.

### Do Not Do Yet

- Do not execute raw model-generated SQL or treat `ready_for_execution_review` as authorization.
- Do not use candidate relationships for cross-table answers.
- Do not upload EDS data, fine-tune on it, or connect to production systems.
- Do not download or import public benchmark datasets without provenance and license review.

### Useful Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-query-plan --request outputs\<run-id>\analytics_request.yml --database outputs\<run-id>\duckdb\operations_lab.duckdb --relationships config\data_model\approved_relationships.yml --output outputs\<run-id>\analytics_query_plan
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

## 2026-07-14 - Codex - Governed benchmark onboarding and conversion

### Initial Context

- Branch: `main`
- Initial commit: `fb56fb9`
- Initial worktree: clean; branch was eight commits ahead of `origin/main`
- Objective: relocate user-supplied sample databases and convert suitable local data into more efficient analytical formats without external database access

### Work Performed

- Inventoried six files with byte sizes and SHA-256 values, then moved them file by file from `new_db/` into dataset-specific ignored raw directories.
- Added versioned provenance, license, processing, and approval metadata while keeping raw and derived data outside Git.
- Implemented `benchmark-convert-sql` using SQLGlot T-SQL parsing; it materializes only parsed columns and local insert rows, normalizes names/types, generates deterministic omitted identities, and exports DuckDB plus Zstandard-compressed Parquet.
- Converted Northwind to 13 tables and 3,308 rows, and Pubs to 11 tables and 255 rows. Extracted 13 and 10 relationship candidates respectively, all `pending_review`.
- Retained AdventureWorks 2025 raw-only because no compatible SQL Server runtime exists. Retained Contoso raw-only because it references external Azure data and contains no local rows.
- Updated the internal link checker to exclude ignored benchmark raw/derived/work artifacts and added a regression test.

### Validation

- Focused converter tests: 5 passed in 1.40 seconds.
- Full offline suite: 56 passed in 5.24 seconds.
- Python compile check: passed.
- Documentation: 20 internal links checked, 0 broken.
- Repeated Northwind/Pubs conversions reported `Outputs changed: False`.
- Every DuckDB and Parquet table count and artifact SHA-256 matched its conversion manifest; validation failures: zero.
- Source SHA-256 values matched the pre-move inventory. No external database, URL, production data, migration, import, synchronization, or model API was used.

### State For Next Agent

- Product track remains at Step 3E.6 dry-run with no canonical apply.
- Analytics track remains at Stage 5A query planning with no controlled executor.
- Benchmark ingestion/conversion foundation is implemented; no benchmark pack or relationship has been approved.
- Raw and derived locations are ignored under `datasets/benchmarks/`; versioned inventory is `datasets/benchmarks/manifests/datasets.yml`.
- Exact source provenance/license confirmation is still pending for all supplied files.

### Next Logical Steps

1. Confirm authoritative download sources and licenses for each local sample.
2. Review Northwind/Pubs schemas and relationship candidates before benchmark approval.
3. Define expected benchmark questions, plans, results, and control totals after approval.
4. Implement Stage 5B first against synthetic fixtures with strict read-only limits.

### Do Not Do Yet

- Do not restore the AdventureWorks backup, execute Contoso external loads, or connect to any external database without explicit authorization.
- Do not treat parsed foreign keys as approved relationships.
- Do not upload, publish, fine-tune on, or otherwise use the datasets beyond approved local storage/conversion.

## 2026-07-14 - Codex - AdventureWorks local restore validation

### Initial Context

- Branch: `main`
- Initial commit: `a13f9c7`
- Initial worktree: clean; branch was nine commits ahead of `origin/main`
- Objective: make the user-supplied AdventureWorks backup functional through an authorized local SQL Server installation without accessing external or production databases

### Work Performed

- Installed SQL Server command-line tools and SSMS, then applied SQL Server 2025 CU6 to build `17.0.4055.5`.
- Configured SQL Server services for manual operation and disabled both SQL telemetry services; `SQLWriter` was left unchanged.
- Verified that the local 50,229,248-byte backup exactly matches Microsoft's official `AdventureWorks2025.bak` SHA-256 `fa6a2a5d431ad88123f89b36b1f2c7e42ca4bdf6b293269a44df80f6de3738a5` and recorded its MIT license source.
- Ran `RESTORE VERIFYONLY`, restored `AdventureWorks2025` to the default local Developer instance, immediately set it to `READ_ONLY`, and ran metadata-only validation plus `DBCC CHECKDB`.
- Updated project state and benchmark governance documentation. Raw data and database files remain ignored or outside the repository.

### Validation

- SQL Server: `Standard Developer Edition (64-bit)`, version `17.0.4055.5`.
- AdventureWorks: online, read-only, compatibility level 170; 6 user schemas, 71 tables, 20 views, 90 declared foreign keys, and 760,167 aggregate rows.
- `RESTORE VERIFYONLY`: passed. `DBCC CHECKDB`: passed with no reported errors.
- Full offline suite: 56 passed in 9.09 seconds.
- Documentation: 20 internal links checked, 0 broken; benchmark inventory YAML loaded successfully.
- Final service state: both SQL Server instances, both agents, and SQL Browser stopped; database services remain manual and telemetry services remain disabled. `SQLWriter` was unchanged.
- No external database, private EDS data, migration, synchronization, model API, or relationship promotion was used.

### State For Next Agent

- AdventureWorks is restored and validated, but no DuckDB/Parquet export or benchmark approval exists.
- The default `MSSQLSERVER` instance is the authorized temporary restore bridge; the separate `DATAOPSLAB` Evaluation instance remains stopped and is not a project dependency.
- All SQL services should remain stopped between explicitly authorized restore/export tasks.

### Next Logical Steps

1. Implement a fail-closed, read-only SQL Server-to-DuckDB/Parquet exporter with synthetic or controlled validation first.
2. Export AdventureWorks to ignored derived storage and verify table counts, hashes, types, nullability, and declared relationship candidates.
3. Review the schema, relationships, expected questions, and control totals before any benchmark-use approval.

### Do Not Do Yet

- Do not treat the 90 declared foreign keys as approved relationships.
- Do not use AdventureWorks for benchmark evaluation or model training until the separate governance gates are completed.
- Do not connect to external databases or query private EDS data.

## 2026-07-14 - Codex - Stage 5B controlled analytics execution

### Initial Context

- Branch: `main`
- Initial commit: `cd2f94c`
- Initial worktree: clean; branch was 10 commits ahead of `origin/main`
- Objective: resume backend optimization from Stage 5A without using EDS or benchmark data

### Work Performed

- Added the separate `analytics_query_execution` version-1 contract and `analytics-query-execute` CLI command.
- Recompiled every request at execution time and required an exact match with the reviewed Stage 5A plan, including request, relationship, catalog, database-size, and database-modification fingerprints.
- Opened DuckDB only with `read_only=True`; disabled external access, extension installation, and extension autoload; isolated temporary spill outside the database.
- Enforced bounded runtime with interruption, memory, threads, temporary spill, result rows, and result bytes.
- Added hash-bound execution manifest, blockers, report, CSV-on-success, control totals, no-row diagnostics, drift rejection, byte-identical reuse, and non-overwrite behavior.
- Preserved parameter privacy in metadata; result CSV remains generated data and may contain selected values by design.

### Validation

- Focused planning/execution tests: 15 passed in 3.68 seconds.
- Full offline suite: 64 passed in 7.58 seconds.
- Python compilation: passed.
- Documentation: 21 internal links checked, 0 broken.
- Tests used temporary synthetic DuckDB databases only and verified source/database/plan preservation, request and database drift blocking, runtime interruption, real row/byte limits, empty results, private-parameter exclusion, and byte-stable reruns.
- No EDS query, benchmark execution, SQL Server start, external database, model API, migration, import, synchronization, or approved-relationship change was performed.

### State For Next Agent

- Analytics Stage 5A planning and Stage 5B controlled local execution are implemented as separate modules.
- The executor accepts no raw SQL and does not bypass the existing approved-relationship registry.
- Database drift uses size and nanosecond modification time for efficiency; cryptographic immutable dataset-package identity is still pending.
- Stage 5C semantic catalog, natural-language translation, result narration, and benchmark harness remain unimplemented.

### Next Logical Steps

1. Define Stage 5C semantic-catalog contracts with synthetic fixtures: business names, synonyms, measures, dimensions, relationship paths, and ambiguity handling.
2. Measure the highest-memory Pandas pipeline stages and select one evidence-backed DuckDB pushdown refactor.
3. Keep AdventureWorks export/review, EDS execution, and Product canonical apply as separate approval tracks.

### Do Not Do Yet

- Do not execute EDS or benchmark datasets merely because Stage 5B exists.
- Do not accept raw model-generated SQL or candidate relationships.
- Do not treat a successful result as semantic correctness or benchmark approval.

## 2026-07-14 - Codex - Stage 5C review-ready semantic catalog

### Initial Context

- Branch: `main`
- Initial commit: `4a37be1`
- Initial worktree: clean; branch was 11 commits ahead of `origin/main`
- Objective: implement Stage 5C semantic context after controlled Stage 5B execution without using EDS or benchmark data

### Work Performed

- Added the `analytics_semantic_catalog` version-1 contract and `analytics-semantic-catalog` CLI command.
- Separated stable semantic IDs from physical DuckDB table and column names.
- Validated candidate dataset/table names, synonyms, dimensions, aggregate measures, numeric measure compatibility, and contiguous relationship paths.
- Required every relationship-path hop to match `approved_relationships.yml`; candidate relationships remain unusable.
- Added accent-insensitive term normalization plus `resolved`, `ambiguous`, `unknown`, and `catalog_blocked` resolution states.
- Preserved all ambiguity candidates with score and clarification flags instead of selecting one automatically.
- Produced review-ready YAML, blockers, and report artifacts with byte-identical reuse and divergent-output refusal.
- Kept semantic approval and adapter authorization false; no apply mode was introduced.

### Validation

- Focused semantic-catalog tests: 6 passed in 1.67 seconds.
- Full offline suite: 70 passed in 8.03 seconds.
- Python compilation: passed.
- Documentation: 22 internal links checked, 0 broken.
- Tests used schema-only temporary DuckDB fixtures and covered a contiguous two-hop approved path, unapproved paths, unknown columns, incompatible measure types, schema typos, duplicate IDs, ambiguity, accent normalization, blocked resolution, preservation, idempotency, and non-overwrite behavior.
- No table rows, EDS data, benchmark data, SQL Server, external database, model API, migration, import, synchronization, or approval file was used or changed.

### State For Next Agent

- Stages 5A planning, 5B controlled execution, and 5C technical semantic validation are implemented as separate modules.
- Valid catalogs stop at `ready_for_semantic_review`; they are not authorized for Stage 5D adapter use.
- There is no approved semantic registry or human review/apply contract yet.
- Ambiguous terms are evidence requiring clarification, not technical blockers.

### Next Logical Steps

1. Define a minimal, versioned semantic review and approval representation without conflating technical validity with business approval.
2. Add a dry-run approval plan and explicit apply contract before Stage 5D consumes semantic definitions.
3. Continue measured backend optimization by profiling Pandas-heavy stages separately from semantic governance.

### Do Not Do Yet

- Do not begin natural-language request generation from unapproved semantic catalogs.
- Do not auto-select ambiguous terms or import candidate relationships into semantic paths.
- Do not execute EDS or benchmark data merely because the semantic validator exists.

## 2026-07-14 - Codex - Stage 5C human semantic approval contract

### Initial Context

- Branch: `main`
- Initial commit: `b71e03a`
- Initial worktree: clean; branch was 12 commits ahead of `origin/main`
- Objective: implement the next safe semantic-governance milestone before Stage 5D without approving or querying a real dataset

### Work Performed

- Added `analytics-semantic-review` to generate a pending review bound to one exact compiled Stage 5C catalog by SHA-256.
- Required reviewer identity, timezone-aware review time, explicit completion status, and one documented decision for every semantic entity and ambiguity.
- Added `analytics-semantic-approval` with dry-run default, blocker/plan/report evidence, and explicit `--apply` state persistence.
- Blocked stale, rejected, pending, missing, duplicate, malformed, or undocumented decisions.
- Preserved ambiguities for clarification or accepted one exact human-selected candidate without promoting candidate physical relationships.
- Protected an existing different semantic registry; replacement requires `--apply --replace-existing` and preserves the prior state under `history/`.
- Added the contract documentation, durable decision, CLI references, testing instructions, and current-state updates.

### Validation

- Focused semantic catalog/review tests: 14 passed in 1.90 seconds.
- New semantic review/approval tests: 8 passed in 1.59 seconds.
- Full offline suite: 78 passed in 8.97 seconds on the final run.
- Python compilation: passed.
- Documentation: 26 internal links checked, 0 broken.
- Tests used synthetic metadata and pytest temporary directories only.
- No real semantic catalog, EDS data, benchmark data, DuckDB/SQL Server connection, model API, migration, import, synchronization, approved relationship, or real `config/analytics` state was used or changed.

### State For Next Agent

- Stage 5C now has separate technical validation, human review preparation, dry-run approval validation, and explicit apply contracts.
- The repository contains no approved real semantic registry; contract implementation is not business approval or dataset-use authorization.
- `approved_target` records exact human ambiguity resolution; `requires_clarification` keeps the ambiguity available to a future adapter.
- Review notes are validated but excluded from the approved registry; review and decision hashes preserve audit binding.

### Next Logical Steps

1. Define Stage 5D with synthetic fixtures and require an explicitly approved semantic registry before producing the existing version-1 structured request.
2. Keep the initial adapter deterministic around a supplied model-intent payload; do not add external model API or raw-SQL execution.
3. Profile Pandas-heavy stages separately and select a measured DuckDB pushdown target.

### Do Not Do Yet

- Do not apply an EDS or benchmark semantic registry without concrete completed human review and dataset-use authorization.
- Do not let Stage 5D consume `ready_for_semantic_review`; it must require applied approved state.
- Do not infer ambiguous targets, accept raw model SQL, start SQL Server, or execute EDS/benchmark queries.

## 2026-07-14 - Codex - Stage 5D offline semantic-intent compiler

### Initial Context

- Branch: `main`
- Initial commit: `bb06440`
- Initial worktree: clean; branch was 13 commits ahead of `origin/main`
- Objective: begin Stage 5D through the approved deterministic boundary without model, database, or real-data access

### Work Performed

- Added the `analytics_semantic_adapter` version-1 contract and `analytics-semantic-adapter` CLI command.
- Required applied version-1 semantic state with human approval fingerprints and explicit adapter authorization.
- Resolved semantic table, dimension, measure, filter, and relationship-path terms through the approved term index.
- Copied measure functions, physical columns, and relationship hops only from approved semantic entities.
- Preserved unresolved ambiguity as candidate-rich clarification evidence instead of narrowing by field context.
- Rejected raw SQL, physical joins, unknown terms, semantic-kind mismatches, unselected tables, malformed filters, unsafe limits, duplicate aliases, and invalid order fields.
- Produced a Stage 5A-compatible `analytics_request.yml` only when no blockers or clarifications remain.
- Added hash-bound manifest, blockers, optional clarifications, report, exact reuse, divergent-output refusal, CLI integration, documentation, and privacy boundaries.

### Validation

- New Stage 5D tests: 8 passed in 1.24 seconds on the final focused run.
- Integrated Stage 5A/5C/5D tests: 29 passed in 2.90 seconds.
- Full offline suite: 86 passed in 8.94 seconds.
- Python compilation: passed.
- Documentation: 28 internal links checked, 0 broken.
- One integration test generated a request from synthetic approved semantics and compiled it with Stage 5A against a schema-only temporary DuckDB database and temporary approved relationship registry.
- No model API, network service, EDS/benchmark data, table row, project DuckDB, SQL Server connection, migration, import, synchronization, real semantic state, or default output directory was used or changed.

### State For Next Agent

- Stage 5D now has the deterministic semantic authorization/compiler boundary, but it does not translate free text by itself or call a model.
- `ready_for_query_plan` means only that Stage 5D produced the version-1 request; Stage 5A live-catalog planning and Stage 5B reviewed execution remain mandatory.
- Questions and filter values persist only in the generated local request. Manifest, report, and blockers omit them; clarification evidence contains the ambiguous term and approved candidates.
- The real repository still has no `config/analytics/approved_semantic_catalog.yml`, so real Stage 5D use remains blocked.

### Next Logical Steps

1. Define a provider-neutral free-text translation interface and response schema with an offline fake provider.
2. Minimize model context to approved semantic metadata and document explicit consent, secrets, retention, timeout, and error boundaries before any live API use.
3. Feed every provider response through the implemented Stage 5D compiler; never accept provider SQL or physical mappings.

### Do Not Do Yet

- Do not configure or call a live model provider without explicit authorization and credential/privacy controls.
- Do not fabricate or apply a real semantic registry merely to unblock Stage 5D.
- Do not bypass Stage 5A/5B, auto-select ambiguous terms, start SQL Server, or execute EDS/benchmark queries.

## 2026-07-14 - Codex - Stage 5D provider-neutral translation boundary

### Initial Context

- Branch: `main`
- Initial commit: `a6770d6`
- Initial worktree: clean; branch was 14 commits ahead of `origin/main`
- Objective: add the next Stage 5D free-text boundary without selecting or calling a live model provider

### Work Performed

- Added the `analytics_nl_translation` version-1 provider protocol and `analytics-nl-translate-recorded` CLI command.
- Added a concrete recorded-response provider that reads local YAML and cannot use network access.
- Built minimized provider context from approved semantic IDs, names, descriptions, synonyms, table ownership, semantic path endpoints, and unresolved candidates.
- Excluded physical mappings, aggregate implementation, source/review fingerprints, approval identity, rows, and databases from provider context.
- Kept the local question authoritative and rejected provider question replacement, SQL, physical joins, unknown fields, and invalid versions.
- Required explicit per-invocation opt-in for any injected provider declaring network access; the recorded CLI exposes no network flag.
- Added sanitized timeout/failure handling without automatic retries and bounded question, context, response, and timeout sizes.
- Routed every accepted response through the existing deterministic Stage 5D semantic adapter and verified matching ready/clarification statuses.
- Added hash-bound control evidence, local intent output, nested adapter evidence, exact reuse, divergent-output refusal, documentation, and shared-state updates.

### Validation

- New provider-boundary tests: 12 passed as part of the final focused run.
- Focused translation/adapter tests: 20 passed in 1.91 seconds.
- Full offline suite: 98 passed in 9.45 seconds.
- Python compilation: passed.
- Documentation: 31 internal links checked, 0 broken.
- Tests used recorded or injected in-memory fake providers and temporary synthetic approved state only. The network opt-in test called an in-memory fake object and made no network request.
- No model SDK, API key, endpoint, network service, real semantic state, EDS/benchmark data, table row, project database, SQL Server connection, migration, import, synchronization, or default output directory was used or changed.

### State For Next Agent

- Stage 5D now separates provider translation from deterministic semantic authorization and physical planning.
- `analytics-nl-translate-recorded` validates reproducibility but does not infer an answer or call AI.
- Future providers receive the local question and minimized approved semantic metadata only after explicit network authorization, then must return semantic intent without SQL or physical mappings.
- Real use remains blocked because the repository has no applied real semantic registry and no authorized live provider.

### Next Logical Steps

1. Create a synthetic translation evaluation pack covering exact intents, equivalent intents, clarification, hallucination, unsafe output, and provider-failure cases.
2. Define acceptance metrics and regression reporting before selecting a live provider.
3. Treat provider choice, credentials, cost, retention, and online testing as a separate explicit authorization decision.

### Do Not Do Yet

- Do not install a model SDK, request credentials, or call a live provider without explicit authorization.
- Do not send EDS, benchmark rows, physical schema, approval identities, or source fingerprints to a provider.
- Do not use recorded responses as evidence of model quality or bypass semantic, Stage 5A, or Stage 5B validation.

## 2026-07-14 - Codex - Stage 5D synthetic translation evaluation

### Initial Context

- Branch: `main`
- Initial commit: `ff80715`
- Initial worktree: clean; branch was 15 commits ahead of `origin/main`
- Objective: add measurable offline translation regression evidence before any live-provider decision

### Work Performed

- Added the `analytics_translation_evaluation` version-1 contract and `analytics-translation-evaluate` CLI command.
- Added a versioned synthetic approved semantic fixture and seven-case translation pack covering exact/equivalent intent, clarification, hallucinated term, provider SQL, timeout, and provider failure.
- Replayed every case through `run_analytics_nl_translation` and the deterministic semantic adapter using in-memory providers that declare no network requirement.
- Added strict pack validation, required category/timeout/failure coverage, fixed category outcomes, enumerated semantic-intent acceptance, exact blocker/clarification comparison, and separate `passed`, `failed`, and `blocked` states.
- Added aggregate status, intent, blocker, clarification, and overall metrics plus per-case boolean evidence.
- Omitted questions, provider responses, filter values, exception details, and physical mappings from persistent outputs; temporary case artifacts are deleted.
- Added hash-bound source evidence, exact idempotent reuse, divergent-output refusal, CLI tests, contract documentation, and shared-state updates.

### Validation

- New evaluation tests: 6 passed as part of the focused and full runs.
- Focused Stage 5D evaluation/translation/adapter tests: 26 passed in 2.76 seconds.
- Full offline suite: 104 passed in 10.77 seconds.
- Python compilation: passed.
- Documentation: 34 internal links checked, 0 broken.
- The bundled seven-case pack passed 7/7 with all five reported metric rates at 1.0.
- No model SDK, API key, endpoint, network service, EDS/benchmark data, project database, SQL Server connection, query, migration, import, synchronization, or real semantic state was used or changed.

### State For Next Agent

- Stage 5D now has deterministic semantic authorization, a provider-neutral translation boundary, and a reproducible synthetic contract-regression pack.
- Synthetic pass rates prove only the programmed backend expectations; they do not estimate live-model accuracy, latency, cost, privacy, or robustness.
- Real use remains blocked by the absence of an applied real semantic registry and an explicitly selected/authorized live provider.

### Next Logical Steps

1. Define a synthetic Stage 5E expected-answer harness that chains the existing offline boundaries through controlled temporary DuckDB execution.
2. Keep result narration separate from exact answer/control validation so generated prose cannot become analytical authority.
3. Profile Pandas-heavy stages separately and select a measured DuckDB pushdown target.

### Do Not Do Yet

- Do not install a model SDK, request credentials, enable network access, or claim model quality from the synthetic pack.
- Do not use EDS or benchmark rows until the corresponding semantic, relationship, provenance, license, and data-use approvals exist.
- Do not bypass reviewed Stage 5A plans or Stage 5B resource and drift controls in a future end-to-end harness.

## 2026-07-14 - Codex - Stage 5E synthetic expected-answer harness

### Initial Context

- Branch: `main`
- Initial commit: `6bf0ac9`
- Initial worktree: clean and synchronized with `origin/main`
- Objective: chain the existing offline analytics boundaries through exact synthetic answer validation without a live provider or real dataset

### Work Performed

- Added the `analytics_answer_evaluation` version-1 contract and `analytics-answer-evaluate` CLI command.
- Added a versioned synthetic semantic registry and answer pack with two temporary tables and one explicitly approved synthetic relationship.
- Added five cases covering an approved `LEFT JOIN`, grouped aggregate, filtered decimal aggregate, no-row result, and `is_null` filter.
- Materialized temporary DuckDB only from validated lowercase identifiers, fixed allowlisted types, bounded rows, generated DDL, and parameterized values; pack-supplied setup SQL is rejected.
- Replayed recorded responses through Stage 5D and required the generated physical request to exactly equal the versioned expected request before planning or execution.
- Reused Stage 5A for catalog/relationship validation and Stage 5B for exact plan revalidation, read-only execution, and fixed resource limits.
- Compared exact ordered CSV plus row, column, null, request, pipeline, and control states.
- Added separate `passed`, expectation `failed`, and contract `blocked` outcomes, hash-bound source evidence, exact idempotent reuse, and divergent-output refusal.
- Kept runtime question/response/request/plan/database/result artifacts temporary; persistent evidence contains only source hashes, limits, case IDs/states, and metrics.
- Added contract, architecture, testing, decision, roadmap, README, and changelog documentation.

### Validation

- New Stage 5E tests: 8 passed in 6.09 seconds on the final focused run.
- Integrated Stage 5A/5B/5D/5E tests: 49 passed in 9.57 seconds before the final approved-join fixture extension; the final focused join-inclusive run passed all 8 Stage 5E tests.
- Final full offline suite after the join and input-limit hardening: 112 passed in 17.95 seconds.
- Python compilation: passed.
- Documentation: 37 internal links checked, 0 broken.
- CLI smoke test: 5/5 cases passed; four summary artifacts were written and no DuckDB artifact persisted.
- No live model, API key, endpoint, network service, EDS/benchmark data, project database, SQL Server connection, migration, import, synchronization, or narration was used.

### State For Next Agent

- Stage 5E now proves exact end-to-end behavior on synthetic single-table and approved-join cases.
- The versioned expected request is the pre-execution synthetic gate; a merely schema-valid provider response is never sufficient.
- The input pack intentionally contains synthetic case content, while generated evaluation evidence omits that content.
- Dataset-backed evaluation remains blocked by immutable dataset identity, provenance/use approval, semantic approval, and reviewed relationship requirements.

### Next Logical Steps

1. Define a dataset-backed Stage 5E contract that references an immutable local dataset manifest rather than embedding rows.
2. Bind benchmark packs to cryptographic dataset, semantic-state, and approved-relationship hashes plus explicit benchmark-use authority.
3. Define exact comparison by default and narrowly typed numeric tolerance only where the reviewed benchmark requires it.

### Do Not Do Yet

- Do not export or query AdventureWorks, EDS, Northwind, or Pubs merely to implement the dataset-backed contract.
- Do not treat synthetic pass rates as model, benchmark, or business-answer quality.
- Do not add narration before deterministic result validation and evidence authority are explicit.

## 2026-07-14 - Codex - Stage 5E dataset-backed binding contract

### Initial Context

- Branch: `main`
- Initial commit: `3f0edab`
- Initial worktree: clean and synchronized with `origin/main`
- Objective: define the next dataset-backed Stage 5E safety boundary without opening, querying, exporting, or approving any real dataset

### Work Performed

- Added the `analytics_dataset_benchmark` version-1 dry-run contract and `analytics-dataset-benchmark-validate` CLI command.
- Required a verified synthetic/public local DuckDB manifest with exact byte size, SHA-256, provenance source, license identifier, and approved semantic/relationship bindings.
- Required a candidate pack bound to the manifest, database, semantic state, and relationship registry by SHA-256.
- Added bounded recorded provider responses, exact Stage 5A expected requests, typed expected rows and controls, deterministic ordering for multi-row results, and exact or reviewed per-column numeric tolerance policy.
- Required a separate human approval bound to the manifest, database, semantic state, relationships, and candidate pack. Offline approval cannot authorize a live provider, external upload, or model training.
- Added timezone-aware ISO-8601 approval timestamps, bounded control-file sizes, strict version-1 fields, input preservation, exact idempotent reuse, and divergent-evidence refusal.
- Hashed each DuckDB artifact once as an opaque local file with a before/after stability check. The validator creates no DuckDB connection and never opens a catalog, table, row, or query connection.
- Persisted only source hashes, safe IDs, counts, controls, blockers, and a boundary report; questions, provider responses, expected requests/results, approval identity, and dataset content are omitted.
- Updated the README, architecture, backend, benchmark, testing, decision, project-state, changelog, and contract documentation.

### Validation

- New dataset-contract tests: 9 passed in 1.79 seconds on the final focused run.
- Final full offline suite: 121 passed in 17.06 seconds.
- Python compilation: passed.
- Documentation: 41 internal links checked, 0 broken.
- Tests used only pytest temporary synthetic DuckDB files. No EDS, AdventureWorks, Northwind, Pubs, project database, SQL Server connection, live provider, network, credentials, migration, import, export, synchronization, narration, external upload, or model training was used.

### State For Next Agent

- Stage 5E can now determine whether independently reviewed dataset, semantic, relationship, pack, and approval artifacts are cryptographically aligned for a future offline evaluation.
- `ready_for_offline_evaluation` is a contract state only. No dataset-backed evaluator currently consumes it or executes cases.
- No real dataset currently meets the contract. Existing Northwind/Pubs conversion and AdventureWorks restoration do not grant benchmark-use, relationship, semantic, expected-answer, provider, upload, or training authority.
- Stage 5B still uses size/mtime plan-to-execution drift checks; a future dataset-backed runner must additionally enforce the immutable SHA-256 authority validated here.

### Next Logical Steps

1. Add a pending benchmark-review preparation artifact bound to the exact candidate manifest and pack.
2. Validate complete human decisions and produce the separate approval file without allowing the candidate pack to approve itself.
3. Only after that governance path is tested, design a dataset-backed offline runner that rechecks every hash and preserves Stage 5A/5B controls.

### Do Not Do Yet

- Do not query, export, or approve EDS, AdventureWorks, Northwind, Pubs, or another real dataset merely to exercise this contract.
- Do not treat `ready_for_offline_evaluation` as execution, business-answer correctness, live-model quality, or permission for upload/training.
- Do not add a live provider, credentials, narration, or external connector before their separate authority and test boundaries exist.

## 2026-07-14 - Codex - Stage 5E benchmark review and approval

### Initial Context

- Branch: `main`
- Initial commit: `7144863`
- Initial worktree: clean and synchronized with `origin/main`
- Objective: add the human-review gate required before any dataset-backed offline evaluator can consume a benchmark pack

### Work Performed

- Refactored dataset candidate inspection into one reusable entrypoint so review preparation, approval, and final binding validation use identical hashes and candidate gates.
- Added `analytics-dataset-benchmark-review` to generate a pending review bound to the exact manifest, opaque DuckDB artifact, approved semantic state, approved relationships, and candidate pack.
- Added one review row per case without copying questions, provider responses, expected requests/results, comparison values, or notes into generated approval evidence.
- Required explicit per-case decisions for recorded provider response, expected Stage 5A request, typed expected result, comparison policy, and non-empty human notes.
- Required explicit scope decisions: local offline evaluation must be approved, while live-provider use, external upload, and model training must be not authorized.
- Added `analytics-dataset-benchmark-approval` with dry-run default and explicit `--apply` for one user-supplied approval path.
- Bound generated approval to the completed review SHA-256 and a normalized decision digest, then made those fields mandatory in final dataset benchmark validation.
- Refused source/identity drift, pending/rejected/missing/duplicate/unknown decisions, scope expansion, invalid reviewer/time, divergent evidence, and different existing approval files.
- Preflighted approval conflicts before evidence writes, reused byte-identical review/approval/evidence, and provided no replacement flag for immutable benchmark authority.
- Updated contract, architecture, backend, testing, decision, project-state, README, and changelog documentation.

### Validation

- Focused dataset benchmark validation/review/approval tests: 19 passed in 2.73 seconds.
- Final full offline suite: 131 passed in 16.59 seconds.
- Python compilation: passed.
- Documentation: 45 internal links checked, 0 broken.
- Integration test generated a synthetic approval, consumed it in final binding validation, and forced any post-fixture `duckdb.connect` call to fail.
- No EDS, AdventureWorks, Northwind, Pubs, project database, SQL Server connection, live provider, network, credentials, export, migration, import, synchronization, narration, upload, training, real review, or real approval was used or changed.

### State For Next Agent

- The governance sequence now exists from valid candidate package to pending review, completed-review dry-run, explicit immutable approval, and final `ready_for_offline_evaluation` binding validation.
- A generated approval contains only IDs, source hashes, review evidence, bounded decisions, and human authority metadata; it does not contain case content or grant execution authority.
- No real benchmark pack or semantic registry is approved. Current Northwind/Pubs/AdventureWorks assets remain outside this workflow until their existing gates are completed.
- No dataset-backed evaluator consumes `ready_for_offline_evaluation` yet.

### Next Logical Steps

1. Implement a dataset-backed offline evaluator that requires the generated approval and rechecks every bound hash immediately before execution.
2. Reuse recorded Stage 5D translation, exact Stage 5A request matching, Stage 5A planning, Stage 5B read-only execution, and typed expected-result comparison.
3. Test the runner only with temporary synthetic DuckDB before requesting authority for any real benchmark.

### Do Not Do Yet

- Do not query/export or create reviews/approvals for EDS, AdventureWorks, Northwind, Pubs, or another real dataset merely to exercise the runner.
- Do not interpret generated approval as answer correctness, live-model quality, narration authority, external disclosure, or training permission.
- Do not bypass immutable hash revalidation, exact request gates, approved relationships, or Stage 5B resource controls in dataset-backed execution.

## 2026-07-14 - Codex - Stage 5E approved dataset-backed evaluation

### Initial Context

- Branch: `main`
- Initial commit: `8db6867`
- Initial worktree: clean and synchronized with `origin/main`
- Objective: consume generated benchmark authority through the governed offline analytics pipeline without using any real dataset

### Work Performed

- Added `analytics_dataset_benchmark_evaluation` and the `analytics-dataset-benchmark-evaluate` CLI command.
- Required the existing complete dataset-backed validation to reach `ready_for_offline_evaluation` before reading the candidate pack or opening DuckDB.
- Replayed each approved recorded response through Stage 5D and required the generated request to exactly equal the reviewed Stage 5A request before planning.
- Reused Stage 5A read-only catalog validation and Stage 5B exact plan revalidation, parameterized execution, drift controls, external-access restrictions, and read-only connection mode.
- Rechecked manifest, DuckDB, semantic state, relationships, pack, and approval SHA-256 immediately before every Stage 5B call and after all cases; drift blocks queries or discards case evidence.
- Added fixed limits of 10,000 rows, 10 MB results, 30 seconds, 512 MB memory, one thread, and 256 MB temporary storage with no CLI overrides.
- Added exact ordered CSV/control comparison and per-column absolute/relative numeric tolerance using the reviewed expected value as the relative baseline.
- Kept `passed`, expectation `failed`, and contract `blocked` distinct and reported overall, pipeline, request, result, control, exact, and tolerance metrics.
- Kept question, response, request, plan, result, and case artifacts temporary; persistent evidence contains only hashes, safe IDs, case states, fixed controls, and metrics.
- Added fail-closed handling for missing prerequisite blocker evidence, exact idempotent reuse, divergent-evidence refusal, CLI tests, and contract/state documentation.

### Validation

- Final focused dataset validation/review/approval/evaluation tests: 26 passed in 5.61 seconds.
- Final full offline suite: 138 passed in 18.43 seconds.
- Python compilation: passed.
- Documentation: 51 internal links checked, 0 broken.
- Tests covered exact pass/fail, numeric tolerance inside/outside bounds, completed/no-row execution, blocked approval before database access, read-only connection enforcement, pre-Stage-5B authority drift, input preservation, idempotency, evidence minimization, and non-overwrite behavior.
- No EDS, AdventureWorks, Northwind, Pubs, project database, SQL Server connection, live provider, network, credentials, real review/approval, export, migration, import, synchronization, narration, upload, or training was used or changed.

### State For Next Agent

- Stage 5E now has synthetic contract evaluation and an end-to-end approved-package path from immutable manifest through human review, approval, binding validation, and controlled offline execution.
- No real semantic registry or benchmark pack is approved, so the new executor has only synthetic temporary evidence and must not be pointed at current project datasets.
- `passed` proves reviewed recorded cases only; it does not measure a live model or authorize narrative claims beyond exact result evidence.
- Result narration and user-facing presentation remain absent.

### Next Logical Steps

1. Define a result-presentation contract that consumes validated Stage 5B/evaluation evidence without becoming query or numeric authority.
2. Build a deterministic offline renderer with source/control citations, no-result diagnostics, and explicit caveats.
3. Add a provider-neutral recorded narration boundary only after deterministic value preservation is tested; keep live provider selection separate.

### Do Not Do Yet

- Do not execute EDS, AdventureWorks, Northwind, Pubs, or another real dataset without its exact completed semantic, relationship, pack, review, and approval chain.
- Do not send questions, rows, SQL, parameters, results, or approval identity to a live provider or network service.
- Do not let narration recompute values, suppress caveats, alter controls, or become execution authority.

## 2026-07-14 - Codex - Deterministic result presentation and recorded narration

### Initial Context

- Branch: `main`
- Initial commit: `117f6f4`
- Initial worktree: clean and synchronized with `origin/main`
- Objective: implement the next documented result-presentation milestone without real data, a live provider, or network access

### Work Performed

- Added `analytics_result_presentation` and `analytics-result-present` to revalidate exact Stage 5B request/result hashes, reviewed-plan and read-only controls, CSV shape, result limits, non-truncation, and no-row state.
- Added a bounded deterministic local preview of at most 100 rows, 20 columns, and 2,000 cells plus stable control/cell fact IDs, source hashes, and streaming full-result validation that retains only preview rows.
- Kept question and preview values out of the control manifest; blocked output contains no result values.
- Added `analytics_result_narration` and `analytics-result-narrate-recorded` with an exact presentation-manifest/facts binding and a provider-neutral Python protocol.
- Required every claim to cite supplied facts, every numeric token to match cited values exactly, and row-count, no-row, and preview-truncation controls to be cited.
- Rejected query language, code blocks, unknown/duplicate citations, unsupported response fields, facts drift, implicit network use, and divergent output replacement.
- Escaped data/provider Markdown, rechecked input hashes during presentation and narration, preserved Stage 5B as numeric authority, and documented that mechanical grounding does not establish prose truth.
- Added contracts, CLI examples, architecture/backend updates, a durable decision, current state, testing guidance, README links, and changelog entry.

### Validation

- Focused result presentation/narration tests: 13 passed in 3.74 seconds after final streaming and drift-control changes.
- Final full offline suite: 151 passed in 21.72 seconds.
- Python compilation: passed; generated `__pycache__` directories were removed afterward.
- Diff whitespace check: passed; only expected Git line-ending notices were emitted.
- Documentation: 55 internal links checked, 0 broken.
- Tests covered normal/no-row/bounded-preview rendering, source preservation, tampered results, unsafe execution evidence, exact reuse, facts drift, numeric mutation, unknown citations, SQL rejection, network blocking, CLI shape, and divergent-evidence refusal.
- No EDS, AdventureWorks, Northwind, Pubs, project database, SQL Server, live provider, network, credentials, real review/approval, export, migration, import, synchronization, upload, or training was used or changed.

### State For Next Agent

- A completed Stage 5B result can now become a deterministic local answer table and hash-bound facts package without another database connection.
- Recorded narration can present cited facts but remains non-authoritative; no live provider or online disclosure policy exists.
- No real semantic registry or benchmark pack is approved, so synthetic fixtures remain the only exercised end-to-end path.
- The individual backend stages are governed but are not yet composed into one resumable analysis-session service.

### Next Logical Steps

1. Define a local analysis-session contract that coordinates existing stage entrypoints and records artifact/status checkpoints without duplicating business logic.
2. Implement a recorded/offline happy path plus blocked/resume paths using temporary synthetic fixtures only.
3. Keep live provider choice, UI work, real datasets, and external disclosure as separate later decisions.

### Do Not Do Yet

- Do not send questions, facts, rows, SQL, parameters, hashes, or approval identity to a live provider or network service.
- Do not treat citation validation as proof that arbitrary narrative prose is semantically correct.
- Do not query EDS or public benchmark data merely to test presentation or orchestration.

## 2026-07-14 - Codex - Two-phase recorded analytics session

### Initial Context

- Branch: `main`
- Initial commit: `b5ac615`
- Initial worktree: clean and synchronized with `origin/main`
- Objective: compose the governed analytics stages into a resumable local service without bypassing human plan review

### Work Performed

- Added `analytics_session` with separate preparation and resume entrypoints instead of one self-authorizing command.
- Added `analytics-session-prepare-recorded` to reuse recorded Stage 5D translation, semantic adaptation, and Stage 5A, then stop at `awaiting_execution_review`.
- Generated a pending human execution-review template bound to the exact preparation-manifest and Stage 5A plan SHA-256.
- Added `analytics-session-resume-recorded` to validate a separate completed/approved human review before calling the existing Stage 5B executor.
- Reused the unchanged deterministic presentation and grounded narration entrypoints after successful execution.
- Recorded immutable source identities, stage states, safe artifact paths, controls, blockers, and last valid checkpoint without persisting question, filter, SQL, parameter, row, or narrative values in session manifests.
- Preserved ambiguity as `clarification_required`, stopped dependent stages on blockers, rechecked input identities during both phases, reused byte-identical evidence, and preflighted existing resume authority before refusing divergent outputs.
- Exposed no execution bypass, review auto-approval, raw-SQL input, live-provider choice, or network flag.
- Added the session contract, durable two-phase decision, orchestrator/architecture/backend updates, CLI examples, testing guidance, README link, project state, and changelog entry.

### Validation

- Final focused analytics-session tests: 8 passed in 2.72 seconds.
- Final full offline suite: 159 passed in 23.34 seconds.
- Documentation: 57 internal links checked, 0 broken.
- Diff whitespace check: passed; only expected Git line-ending notices were emitted.
- Tests covered private/idempotent preparation, clarification stop, pending review, exact complete resume, plan-hash mismatch, relationship drift, checkpoint preservation after narration failure, input preservation, preflight refusal before dependent stages, and CLI boundaries.
- No EDS, AdventureWorks, Northwind, Pubs, project database, SQL Server, live provider, network, credentials, real semantic approval, real review, export, migration, import, synchronization, upload, or training was used or changed.

### State For Next Agent

- The recorded analytics path now has tested preparation and resume semantics without changing existing specialized module contracts.
- A ready Stage 5A plan is not execution authority; resume requires the separate exact human review file.
- Session evidence is immutable per output directory. Corrected review/provider inputs require a new resume output directory when prior evidence differs.
- General module discovery and dependency validation remain absent; the coordinator currently has one intentionally explicit stage order.

### Next Logical Steps

1. Define a versioned declarative registry for the modules used by the analytics session.
2. Validate entrypoints, dependencies, capabilities, workflow order, cycles, and failure policies without making execution dynamic yet.
3. Keep live providers, UI, generic concurrency, real datasets, and external disclosure separate.

### Do Not Do Yet

- Do not auto-complete or auto-approve the generated execution-review template.
- Do not turn the first module registry into dynamic execution before dry-run validation and compatibility tests exist.
- Do not use EDS or public benchmark data merely to exercise session orchestration.

## 2026-07-14 - Codex - AI platform implementation roadmap

### Work Performed

- Added `docs/ai-implementation-roadmap.md` as the durable execution plan from the current governed backend through performance work, approved reference datasets, real semantic catalogs, live-provider evaluation, generic dataset recognition, governed UX, EDS pilot, supervised feedback, and production readiness.
- Recorded phase dependencies, exit gates, quality targets, critical path, indicative timing assumptions, capability progression, and explicit non-authorizations.
- Linked the roadmap from `AGENTS.md`, `README.md`, `docs/project-master.md`, and `docs/ai-analytics-backend.md` so future agents can locate it without conversation history.
- Kept the partially started module-registry implementation separate from this documentation-only checkpoint.

### Validation

- Documentation: 59 internal links checked, 0 broken; diff whitespace check passed with only expected Git line-ending notices.
- No source code, configuration, generated output, source data, approved state, database, provider, network service, or external system was changed by this documentation task.

### Next Logical Step

- Continue Phase 0 by validating and completing the versioned analytics module registry in dry-run mode before making execution dynamic.

## 2026-07-14 - Codex - AI roadmap Phase 0 module registry

### Initial Context

- Branch: `main`
- Initial commit: `a53be58`
- Initial worktree: untracked partial `config/orchestrator/` and
  `src/data_ops_lab/module_registry.py`; both were preserved and completed as
  the documented next milestone.
- Objective: complete AI roadmap Phase 0 without enabling dynamic execution or
  weakening any human, data, provider, or review boundary.

### Work Performed

- Completed the version-1 registry for 8 analytics modules, 2 immutable session
  phases, and 5 ordered stages.
- Added bounded fail-closed validation for exact fields, controls, identifiers,
  dependencies, missing references, cycles, workflow membership, stage order,
  tests, capabilities, failure policies, source drift, and review gates.
- Replaced runtime entrypoint import with static AST inspection and exact
  function-parameter matching; registered entrypoints are neither imported nor
  called by validation.
- Required an explicit non-automatic human review gate before the registered
  `read_only_execution` stage.
- Added immutable validation evidence, byte-identical reuse, divergent-output
  refusal, and the `analytics-module-registry-validate` dry-run CLI.
- Added focused contract/regression tests and documented the contract,
  architecture, durable decision, CLI, testing procedure, roadmap state, and
  project state.

### Validation

- Focused registry tests: 6 passed in 1.95 seconds.
- Full offline suite: 165 passed in 23.15 seconds.
- CLI dry-run: valid with 8 modules, 2 workflows, 5 stages, and 0 blockers.
- Documentation: 62 internal links checked, 0 broken.
- Diff whitespace check passed with only expected Git line-ending notices.
- No registered workflow, real dataset, DuckDB database, SQL Server, provider,
  network, credential, approved state, external system, upload, or training was
  used or changed.

### State For Next Agent

- AI roadmap Phase 0 passed its static validation exit gate.
- The registry remains descriptive. Existing explicit CLI/Python entrypoints
  are the only execution paths.
- Dynamic import/dispatch, concurrency, generic partial runs, generic resume,
  and review auto-approval remain absent.

### Next Logical Step

- Begin Phase 1 with a reproducible synthetic baseline for peak memory,
  runtime, input/scanned bytes, output bytes, and temporary storage, then select
  one measured Pandas-heavy bottleneck for a contract-preserving optimization.

### Do Not Do Yet

- Do not execute modules from the registry or add concurrency before a separate
  reviewed execution contract and compatibility tests exist.
- Do not use EDS, public benchmark datasets, external providers, or databases
  merely to produce performance measurements.

## 2026-07-14 - Codex - AI roadmap Phase 1 measured schema pushdown

### Initial Context

- Branch: `main`
- Initial commit: `3951d7f`
- Initial worktree: clean; branch was one local commit ahead of `origin/main`.
- Objective: establish reproducible scale evidence and improve one measured
  Pandas-heavy bottleneck without changing schema/key candidate contracts.

### Work Performed

- Added `pipeline-performance-baseline`, which generates bounded deterministic
  synthetic Parquet and measures profiling, cleaning, schema/key inference, and
  relationship validation in isolated child processes.
- Recorded runtime, Windows Peak Working Set/POSIX `ru_maxrss`, peak Python
  allocation, unique input footprint, output bytes, and temporary storage with
  environment and source hashes.
- Accepted no external input/database path and deleted synthetic rows after
  measurement; run-specific evidence refuses overwrite.
- Measured schema as the initial highest-memory and dominant-runtime stage.
- Replaced full-table Pandas loading in `write_schema_outputs` with Arrow schema
  metadata and local single-threaded DuckDB aggregates/semi joins over
  parameterized Parquet paths.
- Preserved the existing DataFrame functions for compatibility and kept all
  inferred keys/relationships as candidates only.
- Added exact equivalence tests covering physical/semantic types, nullability,
  NaN, empty tables, uniqueness, repeated line references, primary-key
  candidates, relationship candidates, input preservation, and absence of
  `pd.read_parquet` on the optimized output path.

### Measured Evidence

- Workload: 3 generated tables x 50,000 rows x 6 columns; 1,461,441 input
  bytes; identical per-file SHA-256 before and after.
- Schema peak process memory: 184,971,264 -> 134,606,848 bytes (-27.23%).
- Schema peak Python allocation: 16,773,488 -> 2,256,049 bytes (-86.55%).
- Schema runtime: 35.096404 -> 0.353394 seconds (-98.99%; 99.31x faster).
- Schema output size: 7,282 bytes before and after.
- Generated local evidence: `outputs/phase1_synthetic_baseline_before/` and
  `outputs/phase1_synthetic_baseline_after/` (ignored, not versioned).

### Validation

- Focused performance harness tests: 6 passed in 4.06 seconds.
- Focused schema equivalence plus workflow smoke tests: 3 passed in 1.36 seconds.
- Full offline suite: 173 passed in 26.18 seconds.
- No EDS, public benchmark rows, SQL Server, project database, provider,
  network, credential, approved state, external system, upload, or training was
  used or changed.

### State For Next Agent

- AI roadmap Phase 1 passed its exit gate: baseline evidence exists and one
  measured bottleneck improved without contract regression.
- Cleaning is now the highest-memory stage in the fixed synthetic workload and
  remains a candidate for a separate measured bounded-batch increment.
- Phase 2 cannot complete until a human selects the first reference dataset and
  confirms source, version, license, checksum, local benchmark use, and
  relationship-review scope.

### Next Logical Step

- Obtain the missing Phase 2 reference-dataset authority. Northwind is the
  recommended first small commercial dataset, but its current local source and
  license remain pending exact confirmation.

### Do Not Do Yet

- Do not treat local Northwind/Pubs/AdventureWorks presence as provenance,
  license, relationship, semantic, or benchmark-use approval.
- Do not change candidate outputs or test expectations to claim a performance
  improvement.

## 2026-07-15 - Codex - AI roadmap Phase 2 Northwind reference validation

### Initial Context

- Branch: `main` at `e8c12a1`, two local commits ahead of `origin/main`.
- Initial worktree: clean; ignored Northwind raw/derived assets were preserved.
- The project owner explicitly selected the recommended Northwind dataset and
  authorized the local Phase 2 provenance, licensing, conversion, profiling,
  benchmark-design, and offline-evaluation work.
- General implementation authority was not treated as approval of relationship
  candidates that had not yet been presented with exact evidence.

### Work Performed

- Verified both local Northwind SQL files byte-for-byte against Microsoft's
  official `microsoft/sql-server-samples` repository at commit
  `2f85f3724ee45776a5183ed34d064488a6e1dc53`.
- Fixed the applicable repository license to MIT at license commit
  `4693087abebd7e835f9ee46d005dcdaa03092a40`.
- Re-ran the restricted SQL conversion independently under
  `outputs/benchmarks/northwind-phase2-repro/` without overwriting the current
  derived package.
- Confirmed exact equivalence for source/conversion contract, normalized schema,
  table counts, all 13 Parquet hashes, all 13 relationship candidates, and the
  conversion report. The independently created DuckDB binary has a different
  physical hash and matches its own manifest, so binary identity remains
  package-specific rather than the cross-run equivalence rule.
- Added `reference-dataset-validate`, which fails closed on provenance, license,
  artifact, reproduction, use-scope, schema, key, relationship, and completed-
  review drift; preflight blockers prevent DuckDB access.
- Added immutable read-only technical evidence, a separate exact pending review,
  completed-review validation, idempotent reuse, and divergent-output refusal.
- Added the versioned Northwind reference manifest and recorded approved local
  conversion/profiling/benchmark-design/offline-evaluation scopes while keeping
  external upload, publication, and model-parameter training not authorized.
- Updated inventory, architecture, testing, roadmap, backend, project state,
  durable decision, README, changelog, and the dedicated contract document.

### Northwind Evidence

- Canonical source: 1,049,720 bytes; SHA-256
  `3cc62b3fca6d244a47dbde698b809331e4f85988a0685b2b370717d431e94871`;
  exact official match.
- Alternate Azure SQL script: 1,049,643 bytes; SHA-256
  `0722013fb25c4f7f9d3d6050bc76845568b465edd6f6848e1cb1e02094ee1cc5`;
  exact official match.
- Current conversion: 13 tables, 3,308 rows, 13 PK declarations, and 13 FK
  candidates.
- Primary keys: 13/13 with zero null-key rows and duplicate groups.
- Relationships: 13/13 with zero orphans and unique targets; 11 have positive
  source-row coverage.
- The two `customer_customer_demo` candidates have no positive coverage because
  their candidate source/target tables are empty; this remains visible in the
  review template.
- Versioned reference-manifest SHA-256:
  `c9107a35ae24d7065f53af8e1de264cbf3d2ad5c234f9c8d32cdcfb806b50592`.
- Generated validation evidence SHA-256:
  `2107eec61b57f3cb170370e361e515130013fe7953c26f586da267a3469ac701`.
- Generated pending review SHA-256:
  `5bbd7da188245aa316a5c1095385f79ffc68f503081a00db58ab50bceb33fd08`.

### Validation

- Focused reference/conversion tests: 12 passed in 2.65 seconds.
- Full offline suite: 180 passed in 27.66 seconds.
- Real Northwind validation: `ready_for_relationship_review`, zero blockers,
  and a repeated run reported `Outputs changed: False`.
- Documentation: 69 internal links checked, zero broken.
- Diff whitespace check: passed; only expected Git line-ending notices appeared.
- No source/approved file was modified, no source SQL was executed, and no
  external database, credential, provider, upload, publication, or model
  training was used.

### State For Next Agent

- AI roadmap Phase 2 is technically complete for Northwind up to the mandatory
  exact relationship authority gate.
- Generated pending review:
  `outputs/benchmarks/northwind-phase2-validation/relationship_review.yml`.
- No relationship is approved yet; the derived converter candidates remain
  `pending_review` and versioned global approved registries were not changed.
- Northwind may not enter real semantic catalog work until the completed review
  revalidates as `ready_for_semantic_modeling`.

### Next Logical Step

- Have the project owner accept or reject all 13 exact candidates, including
  explicit consideration of the two no-positive-coverage candidates. Record
  reviewer, ISO-8601 time, and notes for each decision, then run
  `reference-dataset-validate --review` into a new output directory.

### Do Not Do Yet

- Do not infer relationship approval from source declarations, zero orphans,
  local benchmark-use authorization, or this technical validation.
- Do not start the Northwind semantic catalog, expected-answer pack, real
  dataset-backed evaluator, live provider, upload, publication, or model
  training before their exact downstream gates are satisfied.

## 2026-07-15 - Codex - Northwind relationship approval and Phase 2 exit

### Initial Context

- Branch: `main` at `2bc3eb4`; worktree clean and three local commits ahead of
  `origin/main`.
- The project owner approved the exact Northwind relationship review after
  receiving the database location, semantic interpretation, coverage, orphan,
  hierarchy, bridge-table, and fanout caveats.
- The approval was interpreted as acceptance of all 13 candidates, explicitly
  including both empty-table bridges and `employees.reports_to` as the immediate
  manager hierarchy.

### Work Performed

- Preserved the generated pending template under `outputs/` unchanged.
- Added the separate versioned completed review at
  `datasets/benchmarks/manifests/northwind.relationship-review.yml`, bound to
  reference-manifest SHA-256
  `c9107a35ae24d7065f53af8e1de264cbf3d2ad5c234f9c8d32cdcfb806b50592`
  and candidate SHA-256
  `11b0f289218e951db0fcf2e81e7fbe98c6a4d4b144654bc8078c7d1c5968eb2b`.
- Recorded one accepted decision, reviewer, ISO-8601 time, and evidence-specific
  notes for every exact relationship. The two empty-table decisions state that
  their authority is structural and lacks positive row coverage.
- Extended reference validation version 2 to generate
  `approved_relationships.yml` only from a valid completed review. Pending and
  rejected decisions cannot enter the approved list; rejected IDs remain
  separate.
- Revalidated into `outputs/benchmarks/northwind-phase2-reviewed/` and obtained
  `ready_for_semantic_modeling`, zero blockers, 13 accepted relationships, and
  zero rejected relationships.
- Updated dataset inventory, roadmap, backend, architecture, project state,
  testing, README, changelog, and the reference-dataset contract.

### Validation

- Focused reference validation tests: 8 passed in 3.61 seconds.
- Full offline suite: 181 passed in 36.19 seconds.
- Repeated real validation: `Outputs changed: False`.
- Completed review SHA-256:
  `b3131c460bcef79903324fafd07c4083c8018259cdc221847568d33862872f16`.
- Generated approved registry SHA-256:
  `b12b3f19d199c605fb9e88bfabacb8d1ca9369ba54aa91208d393f99de7efd72`.
- Source SQL, raw/derived dataset content, global EDS approvals, external
  systems, provider, upload, publication, and training state were not changed.

### State For Next Agent

- AI roadmap Phase 2 passed its exit gate for Northwind.
- The versioned completed review is the human authority; the ignored approved
  registry is a reproducible adapter for semantic/query modules.
- Northwind physical relationships are ready for Phase 3, but no semantic
  definition has yet been reviewed or applied.

### Next Logical Step

- Prepare a bounded Northwind semantic catalog candidate using only the approved
  relationship projection, validate it with the existing Stage 5C compiler, and
  generate the separate pending semantic review.

### Do Not Do Yet

- Do not treat physical relationship approval as semantic-definition,
  expected-answer, provider, upload, publication, or training authority.
- Do not apply semantic state before the separate exact human semantic review.

## 2026-07-15 - Codex - Northwind semantic candidate and Phase 3 review gate

### Initial Context

- Branch: `main` at `12b0307`; worktree clean and four local commits ahead of
  `origin/main`.
- Northwind had passed Phase 2 with 13 accepted exact physical relationships,
  but no real semantic definition had been proposed, reviewed, or applied.
- The project owner authorized continued implementation; the completed physical
  relationship review was not treated as advance approval of unseen semantic
  definitions.

### Work Performed

- Added the versioned candidate at
  `datasets/benchmarks/manifests/northwind.semantic-catalog-candidate.yml` with
  one dataset, 13 table grains, 60 dimensions, 19 direct-column measures, 18
  approved many-to-one relationship paths, and English/Portuguese terms.
- Kept calculated revenue absent because the version-1 measure contract cannot
  express unit price times quantity times discount. Distinguished order-line
  price from product list price, marked freight as order-grain, retained stock
  quantities as snapshots, and documented the unknown currency code.
- Retained both empty demographic tables as structural candidates and exposed
  `employees.reports_to` only as an immediate-manager ID because version 1
  rejects self-relationship hops.
- Compiled the candidate against the local Northwind DuckDB metadata and the
  Phase 2 approved relationship projection. The first immutable output recorded
  six accidental ID-versus-path synonym ambiguities; the versioned candidate
  was revised with explicit relationship terms and compiled into a new output
  with zero ambiguities.
- Prepared the separate hash-bound pending semantic review with 111 entity
  decisions and zero ambiguity decisions. No decision was prefilled or applied.
- Added `docs/northwind-semantic-review.md` with the material modeling choices,
  review checklist, hashes, authority boundary, and reproduction commands.
- Updated the dataset inventory, roadmap, current state, backend, architecture,
  orchestrator, benchmark/semantic/testing docs, README, and changelog.

### Validation

- Candidate SHA-256:
  `b67181e7de1e1d876719a341d7275d5f493e95d7e6d34c1014c80748b2676b08`.
- Approved relationship registry SHA-256:
  `b12b3f19d199c605fb9e88bfabacb8d1ca9369ba54aa91208d393f99de7efd72`.
- Physical catalog SHA-256:
  `1659954ac2def925cee82348e953820cc49e7d531669d9b2ceab21a4839b323c`.
- Compiled catalog SHA-256:
  `c46696f29890e70dbbc075882219d9daf319d8749d6a1dbdfead47f91ef0bb0d`.
- Real compile: `ready_for_semantic_review`, zero blockers, zero ambiguities,
  13 tables, 60 dimensions, 19 measures, 18 paths, and 339 terms.
- Repeated compile: `Outputs changed: False`; repeated review preparation:
  `Output changed: False`.
- Focused semantic catalog/approval tests: 14 passed in 2.38 seconds.
- Full offline suite: 181 passed in 32.17 seconds.
- Internal links: 78 checked, zero broken.
- No table rows, analytical query, external database, provider, network, upload,
  publication, model training, EDS approval, or `config/analytics` state was
  used or changed.

### State For Next Agent

- Northwind is `semantic_candidate_ready_for_human_review`.
- The compiled candidate and pending review are generated under
  `outputs/benchmarks/northwind-phase3-semantic-catalog-v2/` and
  `outputs/benchmarks/northwind-phase3-semantic-review/`.
- Phase 3 has not passed. Stage 5D remains blocked for Northwind until the exact
  111-entity review is completed and semantic approval/apply succeeds.

### Next Logical Step

- Have the project owner evaluate the definitions and material caveats in
  `docs/northwind-semantic-review.md`. Record an approved/rejected decision and
  factual note for every entity in a separate completed review. If all are
  approved, run semantic approval in dry-run mode before requesting an explicit
  apply decision.

### Do Not Do Yet

- Do not infer semantic approval from the earlier physical relationship review,
  implementation authorization, or zero technical blockers.
- Do not apply `config/analytics/approved_semantic_catalog.yml`, create expected
  answers, execute Northwind analytics through Stage 5D, use a live provider,
  upload, publish, or train a model before their separate gates are satisfied.

## 2026-07-15 - Codex - Northwind semantic approval and Phase 3 exit

### Initial Context

- Branch: `main` at `5c2bfb2`; worktree clean and five local commits ahead of
  `origin/main`.
- Northwind had a technically valid 111-entity semantic candidate and a
  generated pending review, but no completed semantic authority or applied
  `config/analytics` state.
- After receiving the grouped review guide and material caveats, the project
  owner replied `/aprovado`, explicitly accepting the complete package.

### Work Performed

- Preserved the original generated pending review unchanged under `outputs/`.
- Added the separate versioned completed review at
  `datasets/benchmarks/manifests/northwind.semantic-review.yml`, bound to the
  exact compiled catalog SHA-256 and recording `project_owner`, a timezone-aware
  timestamp, 111 approved decisions, notes by semantic kind, and zero ambiguity
  decisions.
- Ran semantic approval first in dry-run mode. It returned
  `ready_for_apply`, zero blockers, and no state change.
- Used the explicit approval to run `analytics-semantic-approval --apply` into
  the previously absent `config/analytics/approved_semantic_catalog.yml`.
  Candidate physical relationships remained explicitly unaccepted by semantic
  approval.
- Repeated the apply command and confirmed `State changed: False` and
  `Outputs changed: False`.
- Compiled a local smoke intent for total ordered quantity by product through
  the applied Stage 5D registry. It reached `ready_for_query_plan`; Stage 5A
  then reached `ready_for_execution_review` against the real local Northwind
  catalog and approved relationships. Stage 5B was not called and no SQL ran.
- Updated dataset inventory, roadmap, current state, durable decisions,
  architecture, orchestrator, backend, semantic contracts, benchmark/testing
  docs, README, changelog, and the Northwind review record.

### Validation

- Completed semantic review SHA-256:
  `2528ebd5a6c33da05fab4fab276ae83f239faad95901fd60e0420dd53c91e2c5`.
- Decision digest:
  `49c9b9f73a93db4378e441f8ab37dd58d46bd44f8ce48574a02adf8506affc8c`.
- Approved semantic state SHA-256:
  `bc2daed705320ae344286cd4678645fe54844e11f8657e55c52e999e046f2d10`.
- State counts: 13 semantic tables, 60 dimensions, 19 measures, 18
  relationship paths, 339 terms, zero ambiguities, and 111 entity decisions.
- Focused semantic catalog/approval/adapter tests: 22 passed in 3.03 seconds.
- Full offline suite: 181 passed in 32.90 seconds.
- Internal links: 82 checked, zero broken.
- Real dry-run/apply, adapter, and Stage 5A reruns were byte-identical and
  idempotent.
- No Stage 5B execution, table-row read, database write, external database,
  live provider, network, credential, upload, publication, model training,
  migration, import, or synchronization was used.

### State For Next Agent

- AI roadmap Phase 3 passed its exit gate for Northwind.
- `config/analytics/approved_semantic_catalog.yml` is the first applied real
  semantic registry and authorizes deterministic local Stage 5D use for its
  exact approved definitions.
- Version-1 limitations remain explicit: no calculated revenue measure, no
  encoded currency, no employee-manager self-join path, empty demographic
  tables, order-grain freight, and snapshot inventory quantities.
- No real expected-answer pack, live provider, online test, or natural-language
  quality evidence exists yet.

### Next Logical Step

- Begin Phase 4 only after a concrete hosted or local provider is selected and
  its retention/privacy behavior, credential storage, network boundary,
  timeout, cost ceiling, failure handling, and isolated online-test policy are
  explicitly documented. The recorded provider remains the offline default.

### Do Not Do Yet

- Do not infer provider/network, expected-answer, upload, publication, training,
  or query-execution authority from semantic approval.
- Do not execute the generated smoke plan; `ready_for_execution_review` remains
  a mandatory separate human checkpoint.

## 2026-07-15 - Codex - Local Ollama provider and Phase 4 exit

### Initial Context

- Branch: `main` at `56d0363`; worktree clean and six local commits ahead of
  `origin/main`.
- Northwind had an applied approved semantic registry and deterministic/recorded
  Stage 5D coverage, but no live model adapter or quality evidence.
- The project owner selected the locally installed Ollama `gpt-oss:20b`, chose
  English as the internal AI language, and explicitly approved the next Phase 4
  implementation increment.
- Measured workstation: Ryzen 9 5900X, 32 GB RAM, RTX 3070 Ti 8 GB. Ollama had
  already demonstrated hybrid CPU/GPU inference.

### Work Performed

- Added `OllamaSemanticIntentProvider` using only the Python standard library.
  It accepts literal `127.0.0.1`/`::1` HTTP origins with an explicit port,
  rejects credentials/path/query/fragment/localhost/LAN/external endpoints, and
  disables proxy routing.
- Added bounded English semantic prompting, 8,192 default context tokens, 1,024
  default output tokens, two-minute keep-alive, a 512 KB request limit, a 2 MB
  HTTP response limit, supplied timeout, no retry, and sanitized error flow.
- Constrained model output through dynamic JSON Schema enums: `from`, paths,
  dimensions, measures, and filters can contain only approved semantic IDs of
  the correct kind. Physical mappings, rows, SQL, approval identity,
  fingerprints, and credentials remain outside the prompt.
- Added the explicit `analytics-nl-translate-ollama` CLI with mandatory
  `--allow-network` for the loopback socket. The recorded provider remains the
  offline default and the public runner signature is unchanged.
- Added offline endpoint, prompt minimization, schema, timeout, malformed
  response, configuration, CLI, and full adapter tests. Added a separately
  marked environment-gated local live test.
- Updated the static registry capability without enabling registry execution,
  concurrency, network, or review auto-approval.
- Updated the contract, roadmap, current state, durable decisions,
  architecture, backend, orchestrator, testing guide, README, and changelog.

### Validation

- Focused provider/registry suite: 30 passed, 1 live test skipped in 2.96
  seconds before the live run.
- The first live output incorrectly used a relationship-path ID in `from`; the
  deterministic adapter blocked it with `semantic_kind_mismatch`. No intent,
  plan, database access, or SQL execution occurred.
- After constraining each field to approved IDs of its correct kind, the
  isolated live Northwind smoke test passed in 18.82 seconds.
- Live runtime at 8,192 context tokens: Ollama reported 57% CPU / 43% GPU;
  approximately 7.4 GB of 8 GB VRAM was in use. This is single-request
  development evidence only.
- Full offline suite: 193 passed and 1 opt-in live test skipped in 32.86 seconds.
- Internal links: 82 checked, zero broken.
- No DuckDB connection, table-row read, SQL execution, external provider,
  credential, API charge, upload, publication, training, migration, import, or
  synchronization was used by the live provider smoke.

### State For Next Agent

- AI roadmap Phase 4 has passed for the selected local Ollama development
  provider. The provider is additive, explicitly invoked, and cannot be
  dispatched by the static module registry.
- `gpt-oss:20b` can interpret the approved Northwind semantic catalog on the
  current workstation, but one smoke question is not accuracy evidence.
- The recorded provider remains required for deterministic offline regression.
- Live narration, concurrency, external providers, automatic query execution,
  dynamic dispatch, and UI remain unimplemented.

### Next Logical Step

- Begin Phase 5 by preparing a bounded English Northwind candidate pack with
  expected semantic intents and deterministic expected answers. Generate a
  separate per-case human review before any real dataset-backed evaluation.

### Do Not Do Yet

- Do not infer expected-answer approval or business quality from the live smoke.
- Do not execute unreviewed benchmark cases, enable automatic query execution,
  add live narration, connect an external provider, upload/publish data, or
  fine-tune/train model parameters without their separate gates.

## 2026-07-15 - Codex - Phase 5 Northwind answer-plan preparation

### Initial Context

- Branch: `main` at `209d87e`; worktree clean and seven local commits ahead of
  `origin/main`.
- AI roadmap Phases 0-4 had passed for Northwind and local Ollama
  `gpt-oss:20b`, but only one live non-executing smoke question existed.
- Northwind provenance, MIT license, local benchmark scope, all 13 physical
  relationships, and all 111 semantic entities were already separately
  approved.
- No real expected-answer pack or safe workflow for collecting its values
  existed. General Phase 5 authorization was not treated as exact query-plan
  approval.

### Work Performed

- Added `analytics_dataset_benchmark_preparation` and the
  `analytics-dataset-benchmark-answer-prepare` CLI. The module validates a
  verified immutable dataset manifest, approved semantics and relationships,
  bounded recorded semantic intents, deterministic result shape/aliases, typed
  columns, comparison policy, and exact source hashes.
- Reused the existing recorded Stage 5D and local-session Stage 5A preparation
  for each case. The module never imports or calls Stage 5B and generates one
  aggregate pending execution review bound to the complete preparation manifest
  and every exact plan hash.
- Added a public shared dataset-manifest contract validator without changing its
  existing behavior or consumers.
- Added six focused tests for review readiness/idempotency, provider SQL refusal
  before catalog access, source binding drift, output alias drift, divergent
  evidence preservation, and fixed CLI safety.
- Added the versioned Northwind public dataset manifest and a 13-case English
  answer design covering table, dimension, measure, filter, order,
  relationship, null-filter, no-row, exact, and numeric-tolerance behavior.
- Ran the real preparation against the bound local Northwind DuckDB. All 13
  recorded intents reached exact Stage 5A plan readiness with zero blockers.
  Generated local evidence is under
  `outputs/benchmarks/northwind-phase5-answer-preparation-v1/`.
- Added a human-readable per-case review guide at
  `docs/northwind-answer-benchmark-review.md` and recorded the durable two-gate
  answer-authority decision.
- Created feature commit `c69dc4a` (`feat(benchmarks): prepare northwind answer
  plans`). No push was performed.

### Validation

- Focused preparation plus existing dataset benchmark suite: 32 passed in 7.18
  seconds.
- Full offline suite: 199 passed and 1 opt-in Ollama live test skipped in 36.50
  seconds.
- Internal links: 91 checked, zero broken.
- Real Northwind preparation: `awaiting_execution_review`, 13 cases, 13 exact
  review-ready plans, zero blockers.
- Repeated real preparation: `Outputs changed: False`.
- Design SHA-256:
  `8bce09e23112c1b3cfc300b27e6c9fe7c5fe17600e2b59d170da9b44a7dd93ff`.
- Preparation-manifest SHA-256:
  `8a645dd34fad6f0a039f78d7b19f874d4d0cbaa2648916ad697734de611da3ca`.
- No Stage 5B query, table-row read, expected result, live provider, network,
  credential, upload, publication, narration, model training, migration,
  import, or synchronization was used.

### State For Next Agent

- Phase 5 is active but its exit gate remains open.
- The exact pending aggregate review is
  `outputs/benchmarks/northwind-phase5-answer-preparation-v1/analytics_dataset_benchmark_execution_review.yml`.
- The review guide lists every question, table grain, measure, filter value,
  join path, ordering, output type, and comparison policy that the human must
  inspect.
- Approval of these plans will authorize only sequential fixed-limit local
  read-only answer collection. It will not approve the collected values.
- A completed-review validator and candidate-pack materializer remain the next
  implementation unit; after collection, the existing final per-case benchmark
  review/approval contract remains mandatory before evaluation.

### Next Logical Step

- Obtain an explicit decision on all 13 exact plans. If approved, implement and
  test completed execution-review validation plus sequential Stage 5B candidate
  answer materialization, run it against the unchanged hashes, and generate the
  separate pending final expected-answer review.

### Do Not Do Yet

- Do not convert the pending execution review into approval without the project
  owner's explicit per-case decision.
- Do not execute any of the 13 Northwind plans, collect expected values, approve
  the resulting pack, or run comparative live Ollama evaluation before their
  exact gates.
- Do not enable concurrency, dynamic dispatch, live narration, external
  providers, upload, publication, or model-parameter training.

## 2026-07-15 - Codex - Northwind candidate-answer materialization

### Initial Context

- Branch: `main` at `e32e61c`; worktree clean and nine local commits ahead of
  `origin/main`.
- The project owner explicitly approved all 13 exact Northwind plans after
  reviewing `docs/northwind-answer-benchmark-review.md`.
- Authority remained limited to local read-only answer collection. The final
  expected values, live provider, upload, training, publication, and narration
  were not approved.

### Work Performed

- Versioned the completed exact-plan authority as
  `datasets/benchmarks/manifests/northwind.answer-execution-review.yml`, with
  all 13 plan hashes approved and every broader scope explicitly not
  authorized.
- Added `analytics_dataset_benchmark_materialization` and the
  `analytics-dataset-benchmark-answer-materialize` CLI. It validates the exact
  preparation/review authority before table-row access, resolves only bounded
  preparation artifacts, executes cases sequentially through ordinary Stage
  5B plan revalidation, and rechecks immutable sources before and after every
  query.
- Added typed CSV-to-pack conversion with schema, DuckDB-type, result-hash,
  row/column/null, no-row, truncation, and ambiguous string-null checks. The
  candidate pack is written only after the existing pack inspector reports no
  blockers.
- Hash-bound the persistent case CSV, blocker CSV, and report in the root
  materialization manifest. Exact reuse is idempotent; partial, divergent, and
  tampered evidence is preserved and refused.
- Extended the dataset benchmark validator to accept both its legacy minimal
  relationship registry and the existing governed registry projection, while
  validating version, approval status, human-review authority hashes, local
  scope, non-automatic approval, rejected IDs, and non-authorizations.
- Added six materialization tests and one governed relationship-registry
  compatibility test.
- The first real run completed all 13 queries but correctly withheld the pack
  because the old final validator rejected the governed registry's authority
  metadata. That blocked evidence remains under
  `outputs/benchmarks/northwind-phase5-answer-materialization-v1/`.
- After the compatibility fix, the definitive hash-bound `v3` run completed all
  13 cases with zero blockers and a byte-idempotent rerun. The versioned pack is
  `datasets/benchmarks/manifests/northwind.answer-benchmark-pack.yml`.
- Generated the separate pending final review under
  `outputs/benchmarks/northwind-phase5-expected-answer-review-v1/` and added
  `docs/northwind-expected-answer-review.md`. No final case was auto-approved.
- Created feature commit `363547c` (`feat(benchmarks): materialize northwind
  answer pack`).

### Validation

- Focused materialization suite: 6 passed in 2.68 seconds.
- Focused materialization plus dataset benchmark suite: 32 passed in 7.63
  seconds after the evidence-integrity test was added.
- Final full offline suite: 206 passed and 1 opt-in live-provider test skipped
  in 36.17 seconds.
- Internal links: 101 checked, zero broken.
- Definitive real materialization: `awaiting_final_review`, 13 cases, 13
  completed, zero blockers; repeated run reported `Outputs changed: False`.
- Candidate pack SHA-256:
  `68d453860a0bf9841b86b4062ef1265e5876ba1724ed11dca23ce9eb70707683`.
- Completed execution-review SHA-256:
  `847426897e5c4c73eaf69d40dfe171ad04fb66a0105bb7e16d685d9fd0de83eb`.
- Northwind DuckDB, approved semantic state, and approved relationships retained
  their prior SHA-256 values.
- No live Ollama call, external network, credential, upload, publication,
  narration, model training, migration, import, synchronization, or database
  write was used.

### State For Next Agent

- Phase 5 remains active at the second, final per-case expected-answer review
  gate.
- The candidate pack contains all questions, recorded semantic responses, exact
  Stage 5A requests, typed expected rows, controls, ordering, and comparison
  policies. It is `candidate_for_review`, not approved benchmark authority.
- The pending form requires four decisions per case: recorded provider
  response, expected request, expected result, and comparison policy. It also
  requires bounded scope decisions, reviewer identity, timestamp, and notes.
- The candidate pack and pending review are byte-idempotent against the current
  source hashes.

### Next Logical Step

- Obtain explicit project-owner decisions for all 13 candidate cases using
  `docs/northwind-expected-answer-review.md`. If fully approved, validate the
  completed review in dry-run, explicitly generate the immutable benchmark
  approval, and run the recorded offline dataset-backed evaluator before
  designing any live-model comparison.

### Do Not Do Yet

- Do not treat successful Stage 5B collection as expected-answer approval.
- Do not edit the generated pending form in place without explicit human
  decisions or auto-approve any case.
- Do not call Ollama for comparative evaluation, enable concurrency/dynamic
  dispatch, add live narration, connect external providers, upload/publish
  data, or train model parameters before their separate gates.

## 2026-07-15 - Codex - Northwind approved recorded-answer baseline

### Initial Context

- Branch: `main` at `5531b2b`; worktree clean and synchronized with
  `origin/main`.
- The project owner explicitly approved all 13 final Northwind cases after an
  independent read-only result and data-quality review.
- The accepted scope was the recorded local offline evaluation only. Live
  provider use, external upload, and model training remained not authorized.

### Work Performed

- Preserved the generated pending form and created the additive completed review
  at `datasets/benchmarks/manifests/northwind.answer-benchmark-review.yml`.
- Recorded all four required decisions for every case. Notes retain the accepted
  unweighted line-level discount average and deterministic alphabetical tie
  rules at both exact top-10 cutoffs.
- Ran the approval workflow first in dry-run and then with explicit apply. Both
  reported zero blockers; a repeated apply reused the exact approval without
  changes.
- Generated the immutable approval at
  `datasets/benchmarks/manifests/northwind.answer-benchmark-approval.yml` with
  local offline evaluation enabled and live provider, upload, and training
  disabled.
- Validated the complete package as `ready_for_offline_evaluation`, then ran the
  13 cases through recorded Stage 5D, exact Stage 5A request gating, and fixed-
  limit read-only Stage 5B execution.
- Repeated the evaluator against the same output path and confirmed byte-
  idempotent evidence reuse.
- Created authority commit `3536ddc` (`feat(benchmarks): approve northwind
  answer pack`).

### Validation

- Approval dry-run/apply: `ready_for_apply`, zero blockers; repeated apply
  reported `Approval changed: False` and `Outputs changed: False`.
- Package validation: `ready_for_offline_evaluation`, 13 cases, 12 exact
  comparisons, one numeric-tolerance comparison, 13 approved relationships,
  zero blockers.
- Recorded offline evaluation: `passed`, 13/13 overall, pipeline, request,
  result, and control checks; 12/12 exact and 1/1 numeric tolerance; zero
  contract blockers.
- Repeated evaluation: `Outputs changed: False`.
- Focused benchmark suites: 39 passed in 9.40 seconds.
- Full offline suite: 206 passed and one opt-in live-provider test skipped in
  36.64 seconds.
- Internal links: 103 checked, zero broken.
- Completed-review SHA-256:
  `deaa274d7a015071896d91788a7ca8f2d7c2f358e416f4e9b40833242493630f`.
- Approval SHA-256:
  `b1ceda6e675448d3fc808d21af2a919c26de4f2016e7d68dfbb6b32b019016b0`.
- Evaluation-manifest SHA-256:
  `e03fa9de299fc1bf946b6b19d4ee1f0b5b24e3fa6c1103fb46a520938cfea3e8`.
- No live Ollama call, external network, credential, upload, publication,
  narration, model training, migration, import, synchronization, or database
  write was used.

### State For Next Agent

- The Northwind pack plus its separate immutable approval is now the first real-
  dataset recorded offline answer authority. The pack remains mechanically
  `candidate_for_review`; the approval remains separate. Together they prove
  deterministic request, pipeline, execution, comparison, and safety controls
  for these 13 recorded cases.
- It is not evidence that `gpt-oss:20b` can translate the 13 live questions.
  The local provider still has only one isolated live smoke pass.
- Generated dry-run, apply, validation, and evaluation evidence remains local
  under the corresponding `outputs/benchmarks/northwind-phase5-*` directories;
  `outputs/` is ignored by design.

### Next Logical Step

- Define and review a bounded Phase 5 live-comparison contract, including case
  isolation, prompt minimization, latency/token/memory evidence, sanitized
  failures, no persisted case content, and explicit loopback-only invocation.
- Obtain separate live-provider authority before invoking Ollama across the 13
  cases, then compare live semantic intent and downstream answers with this
  approved recorded baseline.

### Do Not Do Yet

- Do not infer live-model quality or live-provider permission from the 13/13
  recorded result.
- Do not invoke Ollama for the comparative pack, enable dynamic dispatch or
  concurrency, add live narration, connect external providers, upload/publish
  data, or train model parameters before their separate gates.

## 2026-07-15 - Codex - Governed Northwind live Ollama development evaluation

### Initial Context

- Branch: `main` at `1b8d648`; worktree clean and synchronized with
  `origin/main`.
- The recorded Northwind answer authority and its 13/13 offline baseline were
  already complete. The project owner then explicitly approved continuation
  with the bounded 13-case local Ollama comparison.
- That approval did not extend to an external provider, upload, training,
  narration, publication, concurrency, dynamic dispatch, or production use.

### Work Performed

- Added `analytics-dataset-benchmark-evaluate-ollama` and its version-1 Python
  contract with offline dry-run default, separate hash-bound live authority,
  exact literal-loopback provider matching, double invocation opt-in,
  sequential cases, timeout circuit breaker, immutable rehashing, ordinary
  Stage 5A/5B controls, and sanitized evidence.
- Added provider token/duration/request telemetry and prompt contract
  `ollama_semantic_intent_v2`, requiring complete structured output and general
  deterministic ordering/limit/path policies.
- Kept v1, v2, and v3 live authorizations as additive historical authority.
  Older files cannot silently authorize the newer prompt or alias policy.
- Added reviewed alias-only canonicalization after all non-alias request fields
  match. Literal and semantic metrics remain separate; tables, columns,
  functions, relationship paths, filters/values, ordering directions, and
  limits are never repaired.
- Added atomic evidence publication, divergent/unknown-output protection, and
  conservative network reporting for unexpected failures after entering the
  provider boundary.
- Added fake-provider offline tests and an isolated opt-in real 13-case test.
- Created commit `8b1ecbe` (`feat(ai): add governed live benchmark
  evaluation`).

### Live Evidence

- v1 strict comparison completed 13 provider calls but executed no queries; it
  exposed missing aliases, arrays, stable tie-breaks, and default limits rather
  than a deterministic-pipeline defect.
- After the general prompt refinement and explicitly authorized alias-only
  policy, v3 ran all 13 cases sequentially and passed 9/13 end to end with zero
  contract blockers.
- Provider acceptance: 11/13. Semantic request agreement after alias-only
  normalization: 9/13. Literal request agreement: 2/13. Result/control
  agreement: 9/13.
- The four failures were two provider rejections, one filter mismatch, and one
  scalar alias/limit mismatch. All four stopped before Stage 5A/5B query
  execution.
- Exact result accuracy was 8/12 and the reviewed numeric-tolerance case passed
  1/1.
- The 13 calls reported 80,804 prompt tokens, 1,638 completion tokens, and
  429.073 seconds total provider wall time; median was 31.759 seconds and p95
  was 43.220 seconds. Hosted API cost was USD 0.
- Point-in-time resource evidence observed up to 7,461/8,192 MB GPU memory and a
  fall in available system RAM from 18,462.6 MB before the run to a minimum of
  8,041.5 MB after a case.
- Authorization v3 SHA-256:
  `a47ffac89f91eaa1e48a1024c5d206887e0c1a2e2269d7f1e6617d1d1e70ba81`.
- v3 evaluation-manifest SHA-256:
  `745f0a533956307be6d58056fb219e7efa489386a739a44e47b1c3c0ebc442ff`.
- Generated preflight/live evidence remains local under
  `outputs/benchmarks/northwind-phase5-live-evaluation-*`; `outputs/` remains
  ignored by design.

### Validation

- Focused live-evaluator/provider suites: 62 passed in 10.46 seconds.
- Full offline suite: 217 passed and 2 opt-in online tests skipped in 39.58
  seconds.
- Isolated loopback Ollama smoke after prompt v2: 1 passed in 37.97 seconds.
- Internal links: 106 checked, zero broken.
- `git diff --check`: no whitespace errors.
- No external provider, credential, upload, publication, narration, model
  training, migration, import, synchronization, or database write was used.

### State For Next Agent

- The live-evaluation contract is implemented and measured, but Phase 5 provider
  selection is not complete. A 9/13 development result is not a production gate
  pass.
- Northwind influenced prompt and alias-policy refinement, so its pack is now a
  development set rather than a holdout. Preserve its gold authority unchanged.
- Persistent evaluator evidence intentionally contains no questions, provider
  responses, SQL, parameters, filter values, expected rows, or actual rows.

### Next Logical Step

- Fix Phase 5 acceptance thresholds before new live results are visible.
- Design, collect, independently review, and approve a fresh holdout pack whose
  cases do not reuse the Northwind development questions.
- Obtain a new exact live invocation authority, then compare the local provider
  without tuning prompts or policy on that holdout.

### Do Not Do Yet

- Do not call the 9/13 Northwind result provider selection or production
  readiness, and do not change approved answers to fit model output.
- Do not reuse any prior live authorization for a changed provider, prompt,
  case pack, timeout, or execution policy.
- Do not enable external providers, upload, training, narration, publication,
  concurrency, dynamic dispatch, automatic execution, or a UI before their
  separate gates.

## 2026-07-15 - Codex - Guarded local Ollama overnight soak launched

### Initial Context

- Branch: `main` at `1cc76e7`; worktree clean and synchronized with
  `origin/main`.
- The user explicitly requested an unattended local test that could use the
  available GPU and RAM overnight without consuming Codex tokens after launch.
- The workstation exposed an RTX 3070 Ti with 8,192 MB VRAM, approximately
  31.9 GB total RAM with 16.8 GB available, and 533.8 GB free disk before work.

### Alignment And Hardware Decision

- The installed `gpt-oss:20b` artifact is about 13 GB. A real canary used 7,309
  MB VRAM and Ollama reported a 57% CPU / 43% GPU split.
- Model-call concurrency was fixed at one. The GPU performs tensor work in
  parallel internally; simultaneous model requests on this hardware would add
  KV-cache/context and system-memory pressure rather than useful throughput.
- The approved scope is repeated Northwind development evaluation only. It does
  not authorize training, fine-tuning, a hosted provider, upload, narration,
  publication, production use, or holdout/provider-selection claims.

### Work Performed

- Added `analytics-ollama-soak`, a standalone dry-run/live command that reuses
  the governed live evaluator instead of duplicating Stage 5D/5A/5B logic.
- Added a separate SHA-256-bound authorization permitting 12 hours or 96
  cycles, 45 seconds cooldown, provider concurrency one, and no more than two
  consecutive technical cycle errors.
- Added fail-closed limits: 78 degrees Celsius GPU temperature, 6,144 MB minimum
  available system memory, 20,480 MB minimum free disk, immediate stop after a
  provider timeout, and a `STOP` file.
- Extended the live evaluator with an optional fail-closed guard checked before
  each provider case. A running request remains bounded by the 120-second
  provider timeout.
- Added atomic root checkpoints, per-cycle evidence, aggregate case-stability
  counts, PID/heartbeat/stop state, local token/latency totals, and GPU/RAM/disk
  extrema without copying questions, responses, SQL, parameters, filter values,
  or rows.
- Created and pushed commit `10d16df` (`feat(ai): add guarded local ollama
  soak`).

### Validation

- Focused dataset/live/soak suite: 45 passed in 11.51 seconds.
- Full offline suite after final source changes: 224 passed and 2 opt-in online
  tests skipped in 37.33 seconds.
- Internal links: 109 checked, zero broken.
- Real soak preflight: `ready_for_overnight_soak`, zero provider calls, zero
  blockers, and no DuckDB access.
- Real one-question local Ollama canary: 1 passed in 39.48 seconds with no
  DuckDB or SQL execution.
- `git diff --check`: no whitespace errors.

### Active Run

- Started at `2026-07-15T17:16:46+02:00` in a hidden background process.
- Effective Python PID: `12720`; virtual-environment launcher PID: `24684`.
- Output:
  `outputs/benchmarks/northwind-ollama-overnight-soak-20260715-171646/`.
- Standard logs use the same path with `.stdout.log` and `.stderr.log` suffixes.
- Initial manifest status: `running`; zero contract blockers.
- During the first cycle, the observed GPU reached 98% utilization, 7,284 MB
  VRAM, 58 degrees Celsius, and approximately 172 W.
- The runtime manifest explicitly records
  `codex_or_hosted_model_api_used_by_runtime: false`.

### How To Inspect Or Stop

- Inspect
  `outputs/benchmarks/northwind-ollama-overnight-soak-20260715-171646/analytics_ollama_soak.yml`
  and `analytics_ollama_soak_report.md` for the latest atomic checkpoint.
- Run `nvidia-smi` for a current device sample.
- Create an empty file named `STOP` inside the run directory for a graceful
  stop before the next model call or during cooldown.
- If the process has already finished, trust the final manifest status and stop
  reason rather than the historical PIDs.

### State For Next Agent

- Do not start a second soak while PIDs `12720`/`24684` or another
  `analytics-ollama-soak` process is active.
- The active results are development stability evidence. They cannot alter the
  approved Northwind pack or replace the still-required fresh holdout.
- Generated soak outputs and logs remain under ignored `outputs/` paths.

### Next Logical Step

- After completion, validate final status, stop reason, cycle count, provider
  calls, per-case stability, total local tokens/latency, peak GPU temperature,
  peak VRAM/power, minimum RAM/disk, and empty error log.
- Record the final evidence hash and interpret variations without tuning against
  a future holdout.

### Do Not Do Yet

- Do not treat repeated Northwind cases as additional independent accuracy
  samples or as a holdout.
- Do not enable parallel model requests, training, external providers, upload,
  narration, publication, dynamic dispatch, or production use.

## 2026-07-16 - Codex - Completed soak analyzed and reliability hardened

### Initial Context

- Branch: `main` at `d9ef918`; worktree clean and synchronized with
  `origin/main`.
- The user requested the final overnight result, accepted the recommendation to
  correct the isolated publication failure, and approved the necessary fix.
- No soak process remained active. Ollama had unloaded the model and the GPU had
  returned to idle.

### Final Soak Evidence

- The run stopped safely at `2026-07-15T23:55:08+02:00` on
  `available_system_memory_below_limit`, after approximately 6 hours 38 minutes.
- It wrote 57 cycle records. Fifty-six cycles produced case evidence; the final
  cycle made 11 provider calls and skipped its final two cases when the RAM
  guard triggered.
- Recorded totals: 726 provider calls, 728 case rows including two guard skips,
  558 passed cases, 4,531,904 prompt tokens, 91,091 completion tokens, and
  20,701,794.162 ms provider wall time.
- There were zero provider timeouts, zero contract blockers, and an empty
  standard-error log. Generated evidence occupied about 0.596 MB.
- Fifty-four evidenced cycles passed 10/13; the first and final evidenced cycles
  passed 9/13.
- Seven cases passed 56/56. `total_order_count` and
  `products_by_category` passed 55/56. `average_discount_by_category` passed
  every one of its 55 actual provider calls.
- Persistent gaps: `customers_without_region` passed 0/56 because its limit
  never matched; `orders_placed_in_1997` passed 0/56 because its filter never
  matched; `no_orders_for_atlantis` passed 1/55 actual calls because order/limit
  usually did not match.
- Periodic samples recorded at most 52 degrees Celsius and 7,297 MB VRAM; a
  separate launch observation saw 58 degrees, 98% GPU utilization, and about
  172 W. Periodic device samples are not continuous peaks.
- Available RAM recovered above 14 GB after the process ended and Ollama
  unloaded. The old evidence cannot attribute the gradual decline to Ollama,
  Python, Windows cache, Chrome, or another process.
- Final soak-manifest SHA-256:
  `72b5e7c7808b3439dd679f62563516e178850a0c3999facfa7fd1747cf371f62`.

### Isolated Technical Failure

- Cycle 27 ran for 375.551 seconds, similar to a full cycle, but returned
  `PermissionError` before its cycle directory was published.
- Because the result object/evidence was unavailable, provider calls, tokens,
  and case outcomes for that cycle were conservatively excluded. It is an
  inference, not proven evidence, that inference likely occurred before the
  final publication failure.
- The harness recovered and completed cycle 28 onward. The error log remained
  empty because the cycle-level failure was intentionally sanitized and
  checkpointed.

### Correction Implemented

- Added bounded retries for transient Windows `PermissionError` during final
  live-evaluation directory publication: delays of 0.1, 0.25, 0.5, 1.0, and
  2.0 seconds.
- If the destination appears during retry, publication fails closed and
  preserves that destination; divergent/unknown evidence is never overwritten.
- Added separate bounded retries for soak-owned root checkpoint file
  replacement.
- Added Windows process-memory attribution without a new dependency:
  effective soak-process working set/private memory plus aggregate Ollama
  process count, working set, and private memory.
- Added those metrics to per-cycle CSV, final aggregate manifest, and report.
- Preserved the 6,144 MB system-memory guard, concurrency one, existing
  authority, and all external/training non-authorizations.
- Created commit `4f6150c` (`fix(ai): harden soak evidence and memory
  telemetry`).

### Validation

- Permission-retry and soak-focused checks: 10 passed.
- Complete dataset/live/soak test file: 49 passed in 12.11 seconds.
- Full offline suite after final source changes: 228 passed and 2 opt-in online
  tests skipped in 41.85 seconds.
- Internal links: 109 checked, zero broken.
- A direct local Windows telemetry probe returned separate Python and Ollama
  memory values without loading the model.
- `git diff --check`: no whitespace errors.

### State For Next Agent

- No long soak is active and no rerun was authorized in this session.
- The original completed evidence remains unchanged under
  `outputs/benchmarks/northwind-ollama-overnight-soak-20260715-171646/`.
- The retry fix prevents the observed class of transient publish loss, but its
  sustained Windows behavior and new memory attribution still need a future
  bounded diagnostic run for empirical confirmation.

### Next Logical Step

- If endurance diagnosis is still desired, obtain a new authorization for a
  shorter soak with Chrome closed, retain the 6 GB guard, and compare Ollama
  private/working memory against Python and system available RAM over time.
- Then return to fixed Phase 5 thresholds and a fresh holdout pack.

### Do Not Do Yet

- Do not lower the memory guard, infer a memory leak from available-RAM data
  alone, or enable parallel model requests.
- Do not reinterpret repeated Northwind runs as holdout/provider-selection
  evidence or authorize training/external services from this result.
