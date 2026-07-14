# Decisions

## 2026-07-13 - Human Approval Is Authoritative

**Decision:** Completed human review decisions override automated recommendations.

**Context:** ERP key, relationship, and Product reference inference can be ambiguous or conflict with business knowledge.

**Alternatives:** Allow automation to replace or normalize human decisions; treat missing review as approval.

**Reason:** Human control is a core integrity requirement and is already enforced by domain guidance and preservation tests.

**Impact:** Conflicts must be reported, missing evidence remains blocked, and review files cannot be changed silently.

## 2026-07-13 - Candidates Stay Separate From Approvals

**Decision:** Candidate keys/relationships and approved keys/relationships remain in separate files and states.

**Context:** Source onboarding generates evidence-backed candidates but does not establish business approval.

**Alternatives:** Promote high-confidence candidates automatically.

**Reason:** Confidence metrics alone do not prove ERP semantics.

**Impact:** `approved_keys.yml` and `approved_relationships.yml` remain unchanged until an explicit, validated apply step.

## 2026-07-13 - Product Uses A Technical Primary Key

**Decision:** The target Product model uses generated `product_id` as the primary key. `part_nr_sku` remains the main business/search/matching reference and may become a unique business constraint only after cleanup and revalidation. `pd_ref_nr` remains optional.

**Context:** Product references include duplicates, missing values, textual references, and optional PD-style values.

**Alternatives:** Use `part_nr_sku` or `pd_ref_nr` as the global primary key.

**Reason:** A technical key preserves identity and import stability while reference reconciliation remains incomplete.

**Impact:** Product reference fields cannot be promoted to a final primary key by automation.

## 2026-07-13 - Repository Files Are Shared Agent Memory

**Decision:** Agents use `AGENTS.md`, the `docs/` state files, Git, code, and tests for continuity instead of private conversation history.

**Context:** Codex, Claude Code, and other agents may work on the project at different times.

**Alternatives:** Depend on chat summaries or maintain one monolithic project document.

**Reason:** Versioned, responsibility-specific files are auditable and resilient across tools.

**Impact:** Every versioned change session updates the handoff and consolidated progress state; durable decisions are appended here.

## 2026-07-13 - Orchestrator Coordinates, Modules Own Domain Logic

**Decision:** Orchestration selects, orders, validates, records, and resumes module work; specialized transformation and ERP logic stays in modules.

**Context:** The current default workflow is a fixed sequence and staged CLI commands are dispatched independently.

**Alternatives:** Centralize all logic in the CLI/workflow or let modules call one another implicitly.

**Reason:** Explicit coordination and module contracts reduce coupling and make partial execution testable.

**Impact:** Future orchestration work must avoid duplicating business logic and should add capabilities incrementally behind preserved entrypoints.

## 2026-07-13 - Ten Blocking Product Review Items Are Invalid

**Decision:** Treat the 10 final Product review blockers as invalid Product records. Record each final decision as `rejected`, exclude the record from the future target Product model, and do not create a technical Product identity for the five unmatched original records.

**Context:** The user confirmed that Product approvals had already been reviewed and explicitly directed that the remaining 10 blocking items be considered invalid. The affected issue IDs are `CONFLICT_001`, `CONFLICT_004`, `CONFLICT_005`, `UNMATCHED_ORIGINAL_001` through `UNMATCHED_ORIGINAL_005`, `DUPLICATE_REFNR_001`, and `DUPLICATE_REFNR_004`.

**Alternatives:** Retain five unmatched records with generated `product_id`; preserve the prior rejected decisions without notes; delete or edit raw Product source rows.

**Reason:** The explicit human decision is authoritative. `rejected` is the valid project decision value that represents exclusion; notes make the intended Product-level outcome auditable.

**Impact:** Final review validation is clean with 28 valid decisions, 18 approved and 10 rejected. No raw records were deleted, no reconciliation was applied, and approved model YAML files remain unchanged. A future Step 3E.4 apply contract must consume these rejections as target-model exclusions.

## 2026-07-13 - Step 3E.4 State Is Minimal And Explicit

**Decision:** Represent applied Product reconciliation decisions in a separate `product_reconciliation_state.yml`. Keep raw Product values and notes in ignored local outputs; version only hashes, the model contract, counts, review IDs, decisions, and target actions.

**Context:** The clean workbook is ready for application, but Product exclusions need an auditable representation that does not mutate sources or overload the key and relationship approval schemas.

**Alternatives:** Edit raw Product rows; place Product exclusions in `approved_keys.yml`; commit full workbook values; update canonical model files directly without a decision digest.

**Reason:** A separate minimal state preserves privacy and ownership boundaries, supports idempotency, and makes the exact human-decision set verifiable before downstream model construction.

**Impact:** `apply-product-refnr-decisions` defaults to dry-run, revalidates its input, blocks unresolved context, and requires `--apply` for the state write. The real dry-run maps 10 rejected items to logical target-model exclusions. The representation remains unapplied until explicitly approved.

## 2026-07-13 - Step 3E.4 Product State Is Approved And Applied

**Decision:** Apply the documented `product_reconciliation_state.yml` representation using the validated Product workbook and decision digest `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`.

**Context:** The user reviewed the dry-run outcome and explicitly instructed Codex to proceed. The input contains 28 clean decisions: 18 approved and 10 rejected.

**Alternatives:** Keep the state at dry-run only; alter the state schema; apply decisions directly to raw files or a database.

**Reason:** The separate minimal state had already passed contract, preservation, privacy, rejection, and idempotency tests and matched the authoritative human decisions.

**Impact:** Product reconciliation state is now versioned and authoritative for downstream Product modeling. Rejected records map to logical exclusion and receive no target Product identity. Raw data, review workbooks, `approved_keys.yml`, and `approved_relationships.yml` remain unchanged.

## 2026-07-14 - Product Materialization Fails Closed

**Decision:** Product materialization v1 generates a local preview only when every retained exception has materializable source evidence. Exclusion takes precedence for repeated source identifiers, technical IDs are deterministic UUID5 values bound to the applied digest and source hashes, and no partial preview is written when blockers exist.

**Context:** Several review issues can reference the same source row, and applied human approval does not by itself create missing source values. The real applied state includes three approved `Product_ref.nr` rows that are completely empty.

**Alternatives:** Generate arbitrary identities for empty rows; preserve approvals but omit blocked rows from an otherwise partial preview; infer references from row position; overwrite prior generated evidence.

**Reason:** Those alternatives would silently override human decisions, invent Product records, or create an apparently complete but incomplete target model.

**Impact:** `product-materialization-preview` validates exact applied state, source-row range, same-row conflict evidence, corrected references, exclusions, IDs, and output idempotency. The real run is blocked pending human clarification for three issue IDs and produced no Product preview.

## 2026-07-14 - Empty Product RefNr Rows Are Invalid

**Decision:** Classify `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013` as `rejected`. Exclude `refnr_row_1731`, `refnr_row_1733`, and `refnr_row_1739` from the target Product model and do not assign Product identities to those empty records.

**Context:** The authoritative `Product_ref.nr` rows are completely empty, so the prior approvals could not supply a corrected reference, business reference, attributes, or defensible identity. The human owner explicitly instructed Codex to proceed with treating the rows as invalid.

**Alternatives:** Supply corrected source evidence; generate arbitrary identities; omit the rows without changing the approved decision state.

**Reason:** Explicit human authority resolves the conflict without inventing data. Rejection uses the existing reviewed decision and application contracts and remains auditable and reversible.

**Impact:** The applied state now contains 28 decisions, 15 approved and 13 rejected, with digest `4f14e2cb265d9729263ab5bd572a41365f4bbbceec7e007d930b539faa5fe260`. The prior state is preserved under `config/data_model/history/`. Product materialization is no longer blocked and produces a 1,733-row local preview with 13 exclusions.

## 2026-07-14 - Canonical Product Promotion Is Hash-Bound And Dry-Run First

**Decision:** Require a local, hash-bound promotion plan before any canonical Product state can be proposed for application. Step 3E.6 validates the complete Step 3E.5 package against applied reconciliation state and has no apply mode.

**Context:** The resolved Product preview is complete, but it contains private row values and does not itself define how canonical state should be versioned or applied.

**Alternatives:** Treat the preview as approved canonical state; copy Product rows directly into versioned configuration; mutate `canonical_tables.yml`; add database import behavior to the promotion check.

**Reason:** A separate dry-run checkpoint proves snapshot integrity and preserves the human approval boundary without exposing private values or combining model governance with operational writes.

**Impact:** `product-canonical-promotion-plan` records artifact hashes, schema, counts, and validation results only. The real plan is `ready_for_canonical_state_review` with 1,733 candidate rows, 13 exclusions, and zero blockers. No canonical state, approved key, approved relationship, database, import, migration, or synchronization was changed.
