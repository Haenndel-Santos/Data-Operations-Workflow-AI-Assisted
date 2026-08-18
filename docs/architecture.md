# Architecture

## Runtime Layers

```text
Future product surface
  -> browser UI
  -> product API
     -> identity, RBAC, tenant policy, feature flags, audit, support reporting
     -> existing governed analytics and data-preparation entrypoints

CLI
  -> default workflow coordinator
     -> conversion -> profiling -> cleaning -> schema/key inference
     -> relationship validation -> SQL suggestions -> DuckDB/Tableau export
     -> generated documentation

  -> staged ERP modeling commands
     -> source onboarding -> serial rules -> review preparation
     -> canonical/Product reconciliation -> final review validation
     -> explicitly approved Product reconciliation state
     -> read-only Product materialization preview or blocker checkpoint
     -> hash-bound dry-run canonical Product promotion plan
     -> schema and business-flow documentation

  -> AI-assisted analytics backend
     -> static declarative module-registry validation
     -> two-phase local recorded session coordinator
     -> natural-language translation boundary
     -> synthetic offline translation evaluation
     -> structured analytics request
     -> local catalog and approved-relationship validation
     -> review-ready semantic catalog and ambiguity index
     -> parameterized SELECT dry-run plan
     -> exact plan revalidation
     -> controlled read-only execution and result evidence
     -> deterministic bounded result presentation and facts
     -> cited recorded result narration
     -> synthetic exact-answer and control-total evaluation
     -> exact-plan reviewed sequential answer materialization
     -> hash-bound benchmark human review and approval
     -> immutable dataset-backed benchmark validation (dry-run)
     -> approved dataset-backed offline evaluation

  -> public benchmark onboarding
     -> ignored immutable raw source
     -> restricted T-SQL parsing
     -> local DuckDB and Parquet artifacts
     -> versioned provenance, license, checksums, and permitted uses
     -> independent conversion equivalence
     -> read-only schema/key/relationship validation
     -> separate exact human relationship review
     -> review-ready semantic candidate
     -> separate exact human semantic review
     -> applied approved semantic registry
```

The product API/UI layer is a Sprint 0 target architecture, not an implemented
runtime surface. Current execution remains through explicit CLI/Python
entrypoints.

## Boundaries

| Area | Responsibility | Important boundary |
| --- | --- | --- |
| Product API | Future versioned boundary for sessions, datasets, reviews, execution, evidence, exports, audit, and support reports | Planned only; must enforce identity, RBAC, tenant policy, feature flags, and the Customer Data Boundary before shared UI use. |
| Web UI | Future stakeholder/reviewer workspace for questions, clarification, plan review, results, and evidence | Planned only; must never talk directly to DuckDB, source databases, provider endpoints, or private artifact stores. |
| Customer Data Boundary | Keep customer data, prompts, results, logs, generated artifacts, embeddings, and backups in customer-controlled infrastructure | Target deployment rule; repository currently versions only safe code/docs/manifests. |
| `src/data_ops_lab/cli.py` | Parse commands and dispatch entrypoints | Do not absorb module business logic. |
| `src/data_ops_lab/workflow.py` | Coordinate the default analytical pipeline | Preserve `run_workflow` and `WorkflowResult` compatibility. |
| Analytics module registry | Describe and statically validate current session contracts and workflow order | No dynamic import, dispatch, execution, network, concurrency, or auto-approval. |
| Analytics session module | Coordinate the recorded analytics stages through an exact human plan-review checkpoint | Two separate immutable phases; reuse stage entrypoints; never self-approve or bypass blockers. |
| Conversion/profile/clean/schema modules | Transform and describe local data | Never modify raw input files. |
| Governed cleaning contract (`governed_cleaning.py`) | Define transformation candidates, deterministic evidence, computed confidence, hash-bound decisions, exact application authority, and lineage | Pure contract: no I/O, no DataFrame access; confidence is derived from evidence only; `candidate -> applied` does not exist; the legacy cleaner is unchanged and its behaviour is pinned by characterization tests. See [Governed Cleaning Contract](governed-cleaning.md). |
| Synthetic performance harness | Measure selected Pandas-heavy stages in isolated processes over generated Parquet | No external input, production threshold, dataset authority, or persistent synthetic rows. |
| Schema/key inference | Produce schema plus candidate PK/FK evidence from Parquet metadata and local DuckDB aggregates | Preserve candidate status and output compatibility; never promote relationships or keys. |
| Validation/SQL/export/documentation modules | Validate and publish analytical artifacts | Generated output is not approval evidence by itself. |
| ERP modeling/review modules | Produce candidates, review workbooks, and validation reports | Do not write approved model files unless an apply contract is explicitly authorized. |
| Product materialization module | Validate applied Product decisions and generate local preview/lineage artifacts | Fail closed without partial preview when approved source evidence is missing. |
| Product canonical promotion module | Validate the complete Product snapshot and produce a hash-bound dry-run plan | Report readiness only; never apply canonical state or copy private row values. |
| Analytics query-plan module | Compile a bounded structured request against a local DuckDB catalog | Never accept raw SQL, execute queries, expose filter values, or use unapproved joins. |
| Analytics query-execution module | Revalidate and execute an exact reviewed plan with bounded local resources | Read-only DuckDB only; disable external access; fail closed without partial results. |
| Analytics result-presentation module | Revalidate Stage 5B evidence and render bounded local facts and Markdown | Stage 5B remains numeric authority; no query, database connection, recomputation, network, or divergent overwrite. |
| Analytics result-narration module | Validate cited prose against exact deterministic facts | Exact numeric grounding and required controls; narration is non-authoritative and the CLI is recorded/offline only. |
| Analytics semantic-catalog module | Validate business terms, fields, measures, paths, and ambiguity against physical metadata | Metadata only; approved relationships only; never self-approve semantics or resolve ambiguity silently. |
| Local Ollama semantic provider | Translate one English question into schema-bounded semantic entity IDs through `127.0.0.1` | Explicit per-call socket opt-in; no proxy, credentials, external host, SQL, physical mappings, rows, retries, or automatic execution. |
| Analytics translation-evaluation module | Replay synthetic translation, clarification, rejection, timeout, and failure cases through Stage 5D | Offline in-memory providers only; evidence omits questions/responses and is not live-model quality evidence. |
| Analytics answer-evaluation module | Chain synthetic recorded translation through exact request, Stage 5A plan, Stage 5B execution, and expected-result controls | Temporary allowlisted DuckDB only; no setup SQL, real data, narration, or persisted case artifacts. |
| Dataset benchmark answer-preparation module | Compile bounded recorded real-dataset intents into exact Stage 5A plans and one aggregate pending review | Verified immutable package only; metadata-only read-only catalog access, no Stage 5B, table rows, answers, network, or review auto-approval. |
| Dataset benchmark answer-materialization module | Validate completed exact-plan authority, execute Stage 5B sequentially, and build a typed candidate pack | Fixed read-only limits and per-query hash checks; no live provider, network, auto-approval, upload, training, publication, or overwrite. |
| Dataset benchmark review/approval module | Prepare per-case human review and generate an immutable bounded approval | Dry-run by default; never self-approve, overwrite authority, query data, or expand into provider/upload/training permission. |
| Dataset benchmark-validation module | Bind immutable DuckDB, semantics, relationships, expected answers, tolerances, and separate approval by SHA-256 | Hash opaque local files only; never open/query the database or infer approval from conversion manifests. |
| Dataset benchmark-evaluation module | Replay an approved pack through recorded Stage 5D, exact request gating, Stage 5A, Stage 5B, and typed comparison | Recheck every authority hash before each query; fixed read-only limits; no live provider, network, persisted rows, or real dataset by default. |
| Dataset benchmark live-evaluation module | Compare an exact approved pack through loopback Ollama, Stage 5D, Stage 5A, and Stage 5B | Separate hash-bound live authority, double invocation opt-in, sequential cases, alias-only normalization after non-alias equality, fixed read-only limits, minimized evidence, and no external provider. |
| Local Ollama soak module | Repeat the exact approved development comparison for bounded unattended stability/resource evidence | Separate soak authority, provider concurrency one, per-case resource/STOP guards, atomic checkpoints, no hosted API, and no holdout or production authority. |
| Benchmark SQL conversion module | Parse local sample T-SQL table definitions and rows into DuckDB and Parquet | Never execute source SQL or external operations; output remains unapproved benchmark evidence. |
| Reference dataset-validation module | Bind official provenance/license, current and reproduced conversions, read-only key/relationship evidence, use scopes, and a separate exact review | Technical validity never approves relationships; only a completed review produces the derived approved registry; preflight blockers prevent database access; external/upload/training scopes stay closed. |
| `datasets/benchmarks/` | Separate ignored raw/derived data from versioned inventories and contracts | Dataset presence or conversion is not approval for training, upload, or relationship promotion. |
| `config/data_model/` | Version candidate state, domain mappings, and approvals | Keep candidate and approved files separate. |
| `originaldatabase/` | Private source exports | Read only; excluded from Git. |
| `outputs/` | Reproducible generated artifacts | Excluded from Git; do not hand-edit. |
| `.codex/` | Domain guidance, skills, and agent profiles | Guidance only; cannot override code, tests, or human approvals. |

Private source exports, generated outputs, completed local reviews with row-level evidence, and secrets must remain outside the public-capable repository. Version only safe manifests and hashes; see [Private Artifact Governance](private-artifact-governance.md).
The broader customer-hosted product boundary is defined in
[Customer Data Boundary](customer-data-boundary.md), with security controls in
[Security Architecture Baseline](security-architecture.md), the product threat
model in [Product Threat Model](threat-model.md), MVP requirements in
[MVP Product Requirements](mvp-prd.md), and initial RBAC targets in
[RBAC Matrix](rbac-matrix.md).

## Data Contracts

The default workflow accepts an input directory and output directory and returns `WorkflowResult` with output, database, table, metadata, and Tableau locations. Staged commands use explicit paths and return summaries or artifact locations from their module entrypoints.

Backend Phase II has introduced the first shared internal contracts under
`src/data_ops_lab/contracts/`. File SHA-256 behavior is now shared by source
onboarding, Product application, and reference-dataset validation. The standard
four-field analytics blocker append behavior is shared by query planning,
query execution, semantic catalog validation, and semantic approval. Atomic
new-directory publication and atomic text-checkpoint replacement are shared by
the live dataset evaluator and Ollama soak with their existing retry schedules.
Existing-file and fully declared file SHA-256 binding maps are also shared,
while each module retains its own missing-file and equality policy. Legacy
module exports remain compatible. The two distinct Product materialization
blocker schemas now have exact construction and format provenance but remain
local to that consumer.
The reference-dataset blocker schema remains local but now has exact format
and consumer provenance. Deterministic `.building` directory workflows remain
separate because their stale-staging failure policy differs.

The additive error-taxonomy registry classifies 675 labels used by 22 complete
blocker consumers: query planning, query execution, semantic catalog,
semantic approval, the semantic adapter, the six-module dataset-benchmark
family, natural-language translation, its synthetic offline evaluator, and the
synthetic exact-answer evaluator, followed by deterministic result presentation
and recorded narration, the two-phase analytics-session coordinator, and the
static module-registry validator, the bounded local Ollama soak, and exact
reference-dataset validation, Product canonical promotion, and Product
materialization. All 10 dynamic call sites, both direct blocker-list reuses,
and the one direct blocker construction have exact provenance and disposition
metadata. Fifteen exact
flows record standard blockers inherited from the YAML and semantic-adapter
producer families. Thirty-three exact catch-site fallbacks have separate exception
provenance without persisted source exception messages. Translation, planning,
execution, evaluation, presentation, narration, session checkpoints, and live
`provider_outcome`, registry-validation, reference validation/review, and
Product promotion and materialization status fields remain separate text
surfaces. Soak mode/stop reason and Product decision/lineage actions are four
separate control-text surfaces. The soak's embedded lowercase blockers, the
reference validator's `code`/`message`/`field` blockers, Product promotion's
`artifact` blockers, and Product materialization's internal candidate and
persisted five-field blockers are five separately provenanced record formats.
The review-gated approved-relationship projection, Product promotion's no-apply
boundary, and Product materialization's applied-state and preview-only gates
also remain separate taxonomy metadata.
Callers may request category metadata separately, while unknown codes remain
unregistered and `unclassified`. This registry is not yet a common run-result
envelope and does not coerce exception messages, text statuses, authority
boundaries, approval projections, or module-specific blocker records into one
shape.

The additive run-result contract projects only `output_dir`, opaque `status`,
`blocker_count`, and `outputs_changed`. Twenty-three existing frozen result
classes expose that exact structural core without changing their inheritance,
return types, CLI output, persisted evidence, or module-specific fields. The
projection does not infer success, normalize status text, inspect blocker rows,
or combine artifact paths.

The first formal module registry now describes the two recorded analytics
session phases and validates inputs, outputs, dependencies, validation, tests,
failure policy, entrypoint signatures, and review gates without changing current
Python entrypoints or CLI commands. Other pipelines remain outside this
registry, and dynamic orchestration is not implemented.

## State Model

Modeling decisions use distinct states such as candidate, pending review, approved, rejected, blocked, and conflicting. Key and relationship approvals live in `approved_keys.yml` and `approved_relationships.yml`; both are currently empty. Product-specific reconciliation state lives separately in `product_reconciliation_state.yml`. Human review and promotion-plan reports can establish readiness but must not silently apply state.

## Current Gaps

- Shared hashing, the standard analytics blocker, two characterized
  atomic-publication variants, and two explicit source-binding absence
  semantics are implemented Backend Phase II primitives. Source-only error
  taxonomy coverage and the four-field run-result projection are implemented;
  runtime adoption and CLI decomposition remain pending.
- The analytics-session registry is validation-only; common discovery, dynamic
  dispatch, and a registry covering other pipelines remain pending.
- No generic dependency graph, checkpoint, resume, or dry-run engine; only the recorded analytics session has narrow tested checkpoint/resume semantics.
- CLI stage dispatch and the default workflow are not yet unified under one orchestration contract.
- Some generated summaries become stale when later review steps run; consolidated state must cite the newest validation evidence.
- Product API, browser UI, authentication, RBAC enforcement, tenant isolation,
  row-level security, feature flags, central audit logs, redacted error
  reporting, WAF/rate limiting, HTTPS/HSTS deployment, and backup/restore
  automation are planned product controls, not implemented runtime surfaces.
- Semantic governance, Stage 5D translation evaluation, a synthetic Stage 5E exact-answer harness, pre-execution real answer preparation, sequential candidate-answer materialization, dataset benchmark review/approval, dry-run binding validation, approved offline and separately authorized live dataset-backed execution, deterministic result presentation, and recorded narration validation exist. Northwind has the first applied real semantic registry, immutable 13-case answer authority, 13/13 recorded baseline, and 9/13 loopback Ollama development comparison. Because the pack informed prompt and alias-policy refinement, a fresh holdout and provider selection remain pending, together with dynamic provider dispatch, a live narration provider, and a user interface.
