# Expert Panel Review - 2026-08-19

## Status

```yaml
kind: external_review_record
authority: none
date: 2026-08-19
repository_state: main at fbe6167 (D2 merged, README aligned, dataset readiness design open in PR #28)
```

This is a review record, not a decision. Five independent reviewer roles read
the repository at the state above and produced findings with contemporary
references. Decisions taken from it are recorded in `docs/decisions.md`; work
taken from it is tracked in `docs/progress.md`. Nothing here overrides code,
tests, contracts, or approved artifacts. References were supplied by the
reviewers and were not independently verified.

Roles: Senior Data Analyst; Senior Full-Stack Developer; Senior UI/UX Project
Manager; Technology/Operations Implementation Analyst; Python Backend and Data
Engineer.

## Convergent Findings (three or more roles, independently)

1. **Review burden is the primary product risk.** "Plan review when required"
   is never defined; the Stakeholder cannot approve a plan, so ask -> answer
   depends on a human reviewer per question. Needed: a risk-based review
   policy (`auto-execute` / `review-once` / `review-always`) and pre-authorized
   plan classes or verified answers.
2. **Evidence is shape, not meaning.** Facts carry `row_count`, `null_cells`,
   `no_rows`, `preview_truncated`; not metric definition, grain, resolved
   filters, period, join path and cardinality, freshness, rows dropped by
   cleaning. There is no deterministic definition of answer confidence.
   Needed: Facts v2 and a derived three-level trust badge, never a percentage.
3. **Machine vocabulary needs a versioned translation layer.** Blocker codes
   are excellent for tests and unusable as messages. Needed: a message catalog
   (code -> title, business explanation, resolving role, action) shared by API
   and UI; RFC 9457 as the API error shape.
4. **Dataset refresh has no contract.** A weekly ERP export changes every
   source hash. Needed in readiness: `source.refresh_compatibility` and
   versioned dataset expectations (uniqueness of approved keys, FK integrity,
   freshness, row-count anomaly).
5. **Engineering hygiene lags the domain.** Duplicated helpers across modules,
   three hashing conventions (one non-canonical), no type checker, no
   lockfile, a 1,035-line dispatch in `cli.py`, out-of-band `ValueError`
   where a 409 is meant.
6. **Zero delivery artifacts.** No Dockerfile, wheel, installer, hardware
   requirements, runbooks, backup/restore, or redacted support bundle.
7. **Parsing and profiling are shallow and Anglo-centric.** Number pattern
   accepts only `1,234.56`; three date formats; profiler without quantiles,
   top-N, outliers, temporal coverage.

## Findings Requiring Immediate Action

- Legacy `cleaner.py` under pandas 3 does not normalize freshly-read string
  columns (dtype `str` fails the `object`/`string` checks); only column-name
  normalization and name-based date parsing fire. README corrected in the same
  PR as this record. Open owner decision: repair (`is_string_dtype`, regenerate
  the golden under a recorded decision) or keep frozen.
- `logical_content_sha256` is O(n) pure Python (measured 25.3 s / 155 MB for
  300k rows x 5 columns). Must become Arrow/DuckDB-native and versioned
  (`LOGICAL_HASH_VERSION=2`) before dataset readiness depends on it.
- AdventureWorks holdout blocked for weeks on a local prerequisite; documented
  in `docs/adventureworks-sqlserver-export.md`.
- `docs/testing.md` said 675 taxonomy codes; registry is 751. Corrected.

## Per-Role Summaries

### Senior Data Analyst
Strengths: computed confidence; no `dayfirst`; three authority classes;
fan-out recognized in the validator; PT/EN semantic catalog with preserved
ambiguity; facts with citable IDs; key inference in DuckDB.
Weaknesses: shallow profiling; semantic type by column name; cleaning evidence
without failing/ambiguous samples; 50% proposal threshold hides mixed columns;
fan-out not blocked in the plan (approved N:1 also authorizes the inflating
direction; no grain/cardinality in the catalog); no calculated measures;
`samples/raw` too clean.
Recommendations: Profile v2 in DuckDB (S/M); per-candidate review pack with
hashable samples (S); locale/currency parsing + `interpret_decimal_separator`
in engine v2 (M); mechanical cardinality/grain + `fanout_join_blocked` (M);
Facts v2 (M); versioned expectations evaluated in readiness (M); restricted
calculated metrics (M/L); OpenLineage export (S); `samples/raw_dirty` (S).

### Senior Full-Stack Developer
Strengths: file-in/file-out contracts are naturally RESTful; idempotent
`write_outputs` + atomic publish; hash-bound review is a free `If-Match`;
manifests are safe to log; literal taxonomy maps to RFC 9457; injectable
provider.
Weaknesses: no resource identity beyond `Path` (BOLA if the API accepts paths);
session coordinator works only with the recorded provider and `question_path`;
`database_identity` by size+mtime; heterogeneous status strings; free-text
`reviewed_by` forgeable without server-side signature; no logging, progress, or
cancellation.
Recommendations: `provider` + `question_text` in the session coordinator (S);
`RunStore` + tenant/dataset/session layout, never client paths (M); state enum
+ HTTP mapping (S); review as `POST /sessions/{id}/reviews` with
`Idempotency-Key` and HMAC (M); local job runner, no queue (M); FastAPI +
Pydantic v2 OpenAPI-first, HTMX+Jinja MVP1 UI (M/L); allowlist-only
observability with a test (S/M); hardened Compose (M); dispatch table in
`cli.py` (S).

### Senior UI/UX Project Manager
Strengths: three-valued states with `next_steps`; facts with IDs; computed
confidence; honest dispositions; RBAC states that hiding is not enforcement;
first screen is the workspace.
Weaknesses: no answer-confidence definition; clarification without memory;
plan review as a hard stop; leaking internal vocabulary; machine-shaped review
template; six roles for a company without an analyst; long onboarding without
a declared sandbox; no accessibility baseline; analytics blockers without
`next_steps`.
Recommendations: five-screen prototype over Northwind (M); versioned message
catalog (S/M); card queue for cleaning review with API-filled hashes/timestamps
(M); derived three-level trust badge (S); clarification with session memory
and "suggest as default" (M); verified answers / pre-authorized plan classes
(L, product decision); role stacking + solo mode (S); WCAG 2.2 AA + data-dense
design system with an AI label (S/M); "first answer in 30 minutes" onboarding
(M).

### Technology/Operations Implementation Analyst
Strengths: real fail-closed; honest designed-vs-implemented split; evidence
trail fit for a regulated pilot; agent hygiene; single-tenant customer-hosted
decided early.
Weaknesses: critical path underestimated (Phases 7 and 10 each larger than
everything since July); no delivery artifacts; `gpt-oss:20b` p95 43 s and RAM
stop exclude the typical SME workstation and are not stated as a commercial
prerequisite; refresh without contract; support-without-data declared, not
designed; bus factor 1 and a 231 KB handoff; EDS pilot without KPIs; holdout
blocked on a ten-minute prerequisite; compliance absent (GDPR processor/DPA/
retention; AI Act Art. 50 transparency for generated narration).
Recommendations: P0 risk-based review policy (M), roadmap re-estimate from
real throughput (S), refresh contract in readiness (M); P1 holdout
prerequisites (S), install target + wheel/image + `dataops doctor` + hardware
(L), runbooks + restore test (M), redacted support bundle with a leak test (M);
P2 Scorecard/SBOM/attestations/pinned actions (S), `compliance-map.md` (S),
EDS pilot KPIs (M); P3 monthly handoff archive, external monthly reviewer for
egress/security PRs (S).

### Python Backend and Data Engineer
Strengths: `governed_cleaning.py` is an exemplary pure contract; engine
consistently fail-closed; `schema.py` pushdown; hardened DuckDB execution;
AST network-boundary test; Ruff `S/B/DTZ` at zero.
Weaknesses: legacy cleaner does not do what docs say under pandas 3;
`logical_content_sha256` O(n) pure Python; `apply` loads all tables and copies
per step; three hashing conventions; systematic helper duplication; hashed
artifact (canonical JSON) differs from persisted artifact (YAML); `cli.py`
without `set_defaults` or non-zero exit on `blocked`; 2,330-line hand-kept
taxonomy; weak typing without a checker; no lockfile and floating CI
resolution; `.map(lambda)` 15x slower than vectorized string ops; no
property-based tests.
Recommendations: fix or document the legacy cleaner for pandas 3 (S/M);
Arrow-native `logical_content_sha256` v2 (M); single
`contracts/serialization.py` (M); persist hashed artifacts as canonical JSON
(M); Pydantic v2 contracts (M); pyright starting at `contracts/` and
`governed_cleaning*` (S->L); uv + lock, pin `pyarrow<25`, `duckdb<2` (S);
`set_defaults(func=...)` per domain + `sys.exit(1)` on `blocked` (M);
per-table streaming and vectorized ops in `apply` (M); Hypothesis for the
contract (S); taxonomy as validated YAML (M); structlog + OpenLineage
`RunEvent` (L).

## Integrated Priority Proposal

P0 (with or before readiness): risk-based review policy; refresh contract and
versioned expectations in the readiness design; `logical_content_sha256` v2;
honest README/testing docs; holdout prerequisites; roadmap re-estimate.

P1 (prepares the Product API): `provider` + `question_text` in the session
coordinator; `contracts/serialization.py`; state enum + HTTP mapping; message
catalog; `RunStore` + opaque IDs; review as a signed resource; Pydantic v2
contracts; pyright on contracts; uv + lock and pins; Facts v2 + trust badge;
mechanical grain/cardinality and `fanout_join_blocked`.

P2 (product and operations): five-screen prototype; review card queue;
clarification memory; WCAG 2.2 AA; hardened Compose, wheel/image, `dataops
doctor`, runbooks + restore test, redacted support bundle; Profile v2, locale
parsing, `samples/raw_dirty`, restricted calculated metrics; Scorecard/SBOM/
attestations; compliance map; EDS pilot KPIs; handoff archive.

## References Cited By The Reviewers

Data: https://docs.getdbt.com/docs/build/join-logic ;
https://cube.dev/articles/semantic-layer-for-ai-agents-2026 ;
https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/distribution/ ;
https://docs.soda.io/sodacl-reference/metrics-and-checks ;
https://docs.profiling.ydata.ai/latest/getting-started/concepts/ ;
https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet/

Full-stack: https://www.rfc-editor.org/rfc/rfc9457.html ;
https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header ;
https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/ ;
https://opentelemetry.io/docs/security/handling-sensitive-data/ ;
https://evidence.dev/blog/why-we-built-usql ;
https://www.lightdash.com/blogpost/why-were-building-an-open-semantic-layer ;
https://lours.me/posts/compose-tip-043-read-only-rootfs/

UX: https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/ ;
https://pair.withgoogle.com/chapter/explainability-trust/ ;
https://carbondesignsystem.com/components/ai-label/usage/ ;
https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-prepare-data-ai-verified-answers ;
https://www.metabase.com/blog/official-collections-and-verification ;
https://www.thoughtspot.com/blog/introducing-spotter-ai-analyst

Operations: https://www.replicated.com/blog/introducing-the-state-of-self-hosted-survey-2025 ;
https://www.replicated.com/blog/distributing-ai-models-into-self-hosted-environments---lessons-from-replicated-and-h2o-ai ;
https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations ;
https://www.cisa.gov/resources-tools/services/openssf-scorecard ;
https://www.consilium.europa.eu/en/press/press-releases/2026/06/29/artificial-intelligence-council-gives-final-green-light-to-simplify-and-streamline-rules/ (to be confirmed before use in compliance material) ;
https://ai-act-service-desk.ec.europa.eu/en/ai-act/timeline/timeline-implementation-eu-ai-act

Backend: https://pandas.pydata.org/docs/user_guide/migration-3-strings.html ;
https://duckdb.org/2021/12/03/duck-arrow ;
https://docs.pydantic.dev/latest/concepts/performance/ ;
https://docs.astral.sh/uv/concepts/projects/sync/ ;
https://hypothesis.readthedocs.io/en/latest/numpy.html ;
https://openlineage.io/docs/spec/object-model/
