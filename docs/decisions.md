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
