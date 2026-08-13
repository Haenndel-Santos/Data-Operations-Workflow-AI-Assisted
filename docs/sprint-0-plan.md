# Sprint 0 Product And Security Baseline

## Status

```yaml
version: 1
status: ready_for_owner_review
documented_at: 2026-08-13
review_state: pending_owner_review
authority:
  product_vision_documented: true
  security_architecture_documented: true
  customer_data_boundary_documented: true
  documentation_scope_completed: true
  implementation_authority_granted: false
non_authorizations:
  sql_server_connection: false
  duckdb_real_data_query: false
  ollama_live_call: false
  hosted_provider_call: false
  relationship_approval: false
  semantic_approval: false
  product_canonical_apply: false
  upload_publication_training: false
  production_deployment: false
```

Sprint 0 formalizes the product and security architecture needed before API/UI
or commercial packaging work. It does not change executable code, generated
outputs, private data, approved YAML state, or completed reviews.

## Deliverables

| Deliverable | File |
| --- | --- |
| Product vision for PME/stakeholder users | [Product Vision](product-vision.md) |
| Customer Data Boundary | [Customer Data Boundary](customer-data-boundary.md) |
| Security architecture baseline | [Security Architecture Baseline](security-architecture.md) |
| Product threat model | [Product Threat Model](threat-model.md) |
| AI authority split | [AI Analytical Capability Matrix](ai-analytical-capability-matrix.md) |
| MVP/API/UI architecture | [MVP Architecture](mvp-architecture.md) |
| Updated source-of-truth docs | [Project Master](project-master.md), [Architecture](architecture.md), [AI Roadmap](ai-implementation-roadmap.md), [Progress](progress.md) |

## Parallelization Model

| Front | Can run in parallel? | Notes |
| --- | --- | --- |
| Product vision and MVP workflow | Yes | Independent documentation while technical gates remain unchanged |
| Security architecture and threat model | Yes | Can be drafted from current docs without executing systems |
| Phase 5.2 operational readiness check | Yes for inventory; no for export | Export depends on local admin service and local artifacts |
| API/UI design | Partially | Can define contracts now; implementation should wait for security baseline review |
| Provider/live evaluation | No | Depends on AdventureWorks export, relationship review, semantic approval, pack design, and live authority |
| Relationship/semantic approvals | No | Require exact generated evidence and human review |
| Product canonical apply | No | Requires separate apply contract and authority |

## Immediate Next Steps

1. Review Sprint 0 docs and adjust product/security language if needed.
2. Repair current state documentation around the latest verified commit.
3. Restore or make available the ignored local AdventureWorks raw artifact and
   default SQL Server service if Phase 5.2 should resume.
4. Execute Phase 5.2 only through the existing read-only export contract.
5. Stop Phase 5.2 at `ready_for_relationship_review`.
6. Continue Phase 5.3 relationship and semantic authority after exact review
   evidence exists.
7. Start Product API/UI implementation only after the owner accepts the security
   baseline and MVP contract.

## Step 1-7 Execution Pattern

| Step | Work | Execution mode |
| --- | --- | --- |
| 1 | Product vision and security baseline | Completed as documentation |
| 2 | Current state hygiene | Linear; update docs from Git and local artifact inventory |
| 3 | Phase 5.2 AdventureWorks export | Linear after local admin/artifact prerequisites |
| 4 | Relationship and semantic authority | Linear review gates, with parallel doc/test prep possible |
| 5 | Holdout packs and provider selection | Mostly linear because results must stay unseen until frozen |
| 6 | Product API and UI | Parallelizable by disjoint write scopes after API/security contracts |
| 7 | Enterprise hardening | Parallelizable by controls, but release gate is linear |

## Stop Conditions

- Missing local source artifacts.
- SQL Server service unavailable or wrong instance.
- Any database not reported as exact `ONLINE` and `READ_ONLY`.
- Missing or pending relationship/semantic/execution review.
- Provider/network authority absent.
- Any proposed change requiring secrets, external upload, production data, or
  destructive filesystem/database action.
