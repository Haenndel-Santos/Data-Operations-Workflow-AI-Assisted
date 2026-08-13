# Product Threat Model

## Scope

This threat model covers the repository's target product direction: a
customer-hosted, AI-assisted operational analytics platform built from the
existing local-first data pipeline, governed semantic layer, deterministic
query planning/execution modules, local provider boundary, and future API/UI.

It is not a completed security audit and does not claim that future production
controls are implemented.

## Assets

| Asset | Why it matters |
| --- | --- |
| Raw operational exports and source databases | Contain customer, supplier, product, finance, logistics, and business-process data |
| Cleaned data, DuckDB/Parquet artifacts, result CSVs, and reports | Contain transformed customer data and analytical conclusions |
| User questions, prompts, semantic context, and provider responses | Can reveal business state even without raw rows |
| Approved relationships, semantic catalogs, and review decisions | Define what analysis is authorized and how business terms map to data |
| Credentials, connection strings, tokens, and local service configuration | Can grant access to private systems |
| Audit logs, error reports, screenshots, and support bundles | Can leak private values and operational context |
| Benchmark/holdout evidence | Determines provider selection and model-quality claims |
| Git repository history and manifests | Public-capable long-term project memory |

## Trusted Actors

| Actor | Trust assumption |
| --- | --- |
| Project owner | May approve product direction, dataset use, reviews, and stage authority |
| Human reviewer | May approve exact relationships, semantic definitions, execution plans, and benchmark decisions within assigned scope |
| Local administrator | May start/stop local services and configure customer-controlled infrastructure |
| Application backend | Trusted only after its inputs, contracts, and authority gates validate |
| LLM provider/runtime | Not trusted for facts, SQL, permissions, or calculations |
| End user | Authenticated identity is required in the future product; requests remain attacker-controlled input |

## Attacker-Controlled Inputs

- Uploaded CSV/XLSX/SQL-like files and metadata.
- Source database schemas, table names, column names, and row values.
- User questions and clarifications.
- Model/provider responses.
- Review files and approval manifests before validation.
- API requests, session IDs, dataset IDs, tenant IDs, filters, export requests,
  and filenames.
- Error reports, screenshots, logs, and support-bundle comments.
- Environment variables and local configuration when not protected by deployment
  controls.

## Main Threats

| Threat | Product-specific failure mode | Required invariant |
| --- | --- | --- |
| Data exfiltration | Customer rows, prompts, results, logs, or artifacts leave the boundary | Deny egress by default; explicit authorization and redaction before sharing |
| Prompt injection | User data or question convinces the model to bypass policy or reveal context | Model output is untrusted; validators accept only schema-bounded semantic intent |
| Raw SQL execution | Model or user submits executable SQL that reaches the database | Stage 5A/5B accept structured requests only and reject SQL-like output |
| Unauthorized write | Analytics or connector path mutates source or analytical data | Read-only access, explicit apply contracts, and no write-capable default execution |
| Cross-tenant leakage | User sees another customer's dataset, result, log, or support bundle | Tenant isolation, RBAC, row-level policies, and audit checks before access |
| Approval bypass | Candidate relationships, semantic terms, or execution plans become operational without review | Pending, blocked, or rejected state never becomes approval |
| Evidence drift | Results are trusted after source, plan, catalog, relationship, or provider configuration changes | SHA-256/source identity checks and fail-closed idempotency |
| Secret leakage | `.env`, tokens, connection strings, hostnames, or credentials enter Git/logs | Secret manager and repository scans; no secrets in source or generated docs |
| Poisoned benchmark evidence | Development cases are reused as holdout or tuned results are treated as independent | Frozen thresholds, fresh holdout, one-shot evaluation, separate human decision |
| Error-report leakage | Screenshots/logs reveal customer data to support or external tooling | Local capture, redaction, approval, and support role constraints |
| Resource exhaustion | Large files, expensive queries, or repeated provider calls overload the workstation/server | Runtime, memory, row, result-byte, provider timeout, and soak resource gates |

## Boundaries And Assumptions

- The current default test suite is offline and must remain so.
- Generated outputs and private inputs are not committed to Git.
- SQL Server is a temporary local read-only bridge for authorized public
  benchmark export, not a permanent production dependency.
- Ollama `gpt-oss:20b` is a local development provider candidate, not a
  production provider selection.
- Future API/UI, RBAC, tenant isolation, WAF, TLS, audit logging, and deployment
  packaging are not implemented yet.
- Deployment-level egress restrictions are target controls and must be verified
  separately from Python-level guards.

## Security Properties That Must Hold

1. Customer data remains inside the Customer Data Boundary by default.
2. The LLM never becomes authority for SQL, relationships, permissions,
   calculations, or facts.
3. Every operational relationship, semantic entity, execution plan, benchmark
   pack, and provider selection has explicit scoped authority.
4. Review states remain mechanically distinct: candidate, pending, approved,
   rejected, blocked, and conflicting.
5. Read-only analytical execution remains the default.
6. Error and narration outputs cannot smuggle SQL, altered numbers, missing
   citations, or private payloads past validators.
7. Product API and UI work must add identity, authorization, audit, and
   boundary enforcement before exposing shared or multi-user execution.

Repository: Data-Operations-Workflow-AI-Assisted
Baseline evidence commit: 13a8880
Document state: Sprint 0 product/security baseline; use Git history for the
exact committed document revision.
