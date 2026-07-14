# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model through a modular, traceable, human-controlled workflow.

## Current Stage

Stage 3E.5 blocked validation: the read-only Product materialization module and contract are implemented, but the real preview is blocked by three approved decisions whose `Product_ref.nr` source rows are completely empty.

## Last Completed Milestone

On 2026-07-14, Product materialization v1 was implemented and validated offline. A real run consumed the applied state and recomputed reconciliation from 1,734 original Product rows and 1,739 authoritative rows. It preserved 10 logical exclusions but correctly withheld the preview because `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013` point to completely empty approved source rows. Only deterministic blocker, manifest, and report artifacts were generated.

## Current Capabilities

- Convert and normalize local CSV/XLSX inputs.
- Profile, clean, infer schemas/keys, and validate relationships.
- Generate SQL suggestions, DuckDB datasets, Tableau exports, and data dictionaries.
- Onboard ERP sources and keep generated model candidates pending review.
- Import serial reference rules and prepare human approval packages.
- Reconcile Product references, validate staged human decisions, and persist explicitly approved Product reconciliation state.
- Produce a clean, validated Product review workbook and a revalidated Step 3E.4 application plan.
- Apply Product reconciliation state only through an explicit, idempotent, reversible command.
- Validate applied Product state and build deterministic local Product preview, lineage, exclusion, manifest, and blocker artifacts.
- Fail closed without a partial preview when approved decisions lack materializable source evidence.
- Generate conceptual schema and business-flow documentation.

## Test Status

- Automated suite: 38 tests passed offline on 2026-07-14; latest run completed in 3.75 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 12 checked, 0 broken on 2026-07-14.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.
- The relocated `.venv\Scripts\dataops.exe` launcher exits unsuccessfully because it still embeds the previous environment location; use `.venv\Scripts\python.exe -m data_ops_lab` with `PYTHONPATH=src`.

## Open Risks

- Reports under `outputs/originaldatabase_analysis/` are stale and still show earlier Product blockers; use the 2026-07-13 validation path cited above.
- `canonical_tables.yml` still describes the pre-application Product key candidate; downstream work must treat `product_reconciliation_state.yml` as the approved Product-specific contract until those representations are deliberately reconciled.
- The applied review state contains three retained `Product_ref.nr` decisions with no source values at all; they cannot produce `product_ref_nr`, `part_nr_sku`, attributes, or a defensible target identity.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Product materialization is blocked by `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013` until a human rejects those empty records or supplies corrected source evidence.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.

## Next Logical Milestone

Obtain an explicit human decision for the three empty approved rows: either classify them as invalid/rejected Product records or provide corrected source evidence. Then regenerate and reapply the reviewed decision state through the existing contract and rerun `product-materialization-preview`. Do not generate identities for the empty rows by assumption.

## Last Verified Commit

`668db5f` (`chore(product): apply approved reconciliation state`)

## Last Updated

2026-07-14 by Codex after fail-closed Product materialization validation.
