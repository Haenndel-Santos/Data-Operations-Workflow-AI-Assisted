# Customer Data Boundary

## Purpose

The Customer Data Boundary is the product rule that defines where customer data
may exist and which components may process it. It turns "local-first" from an
application preference into a verifiable deployment and governance property.

## Boundary Statement

Customer data must remain inside infrastructure controlled by the customer or
by an explicitly approved private deployment environment. No component may send
customer data outside that boundary unless a separate documented authorization
defines the exact data, destination, purpose, retention, owner, and rollback
plan.

```text
Internet / external services
        X no customer data by default
        X no prompts or result rows by default
        X no model-provider calls by default
------------------------------------------------
Customer-controlled environment
  - Web UI
  - Product API
  - Authentication and authorization
  - Local model runtime
  - Semantic engine
  - Analytics engine
  - DuckDB / Parquet analytical storage
  - Source connectors
  - Audit and support logs
  - Customer ERP, spreadsheets, and databases
```

## Data Covered By The Boundary

| Data type | Boundary status |
| --- | --- |
| Raw CSV, XLSX, SQL backup, database, and ERP exports | Inside only |
| Cleaned data, Parquet, DuckDB, previews, and result CSVs | Inside only |
| User questions and clarifications | Inside only |
| Prompts, semantic context, provider responses, and narration inputs | Inside only unless separately authorized |
| Approved semantic catalog containing private business meaning | Inside only |
| Generated reports, facts, histories, and saved analyses | Inside only |
| Logs with values, identifiers, hostnames, query parameters, or screenshots | Inside only |
| Embeddings, vector indexes, caches, temporary files, and backups | Inside only |
| Secrets, connection strings, tokens, and credentials | Never committed; managed by deployment secret controls |

The current repository already excludes `originaldatabase/`, `outputs/`,
`.env*`, DuckDB files, and benchmark raw/derived artifacts from Git. This
document extends that repository practice into the future product deployment
model.

## Trust Zones

| Zone | Examples | Rule |
| --- | --- | --- |
| Public-capable repository | Source code, tests, docs, safe manifests, non-sensitive fixtures | Must contain no customer data, generated private outputs, completed sensitive reviews, or secrets |
| Customer runtime | API, UI, local model, DuckDB, connectors, audit service | May process customer data under identity, authorization, and audit controls |
| Private artifact store | Raw inputs, generated outputs, review workbooks, backups | Access controlled separately from the public-capable repository |
| External internet | Package registries, hosted providers, SaaS APIs, telemetry endpoints | Denied by default for customer data paths |

## Default Egress Policy

For a customer-hosted deployment, data-processing components should run with
deny-by-default outbound network access:

- model runtime: no external egress by default;
- analytics engine: no external egress by default;
- database connectors: allow only configured internal sources;
- application API: allow only required internal services and approved update
  channels;
- observability: sanitize before emission and keep local by default;
- support bundles: export only through an explicit redaction and approval flow.

This is a target deployment property. The current Python modules already
enforce local provider and read-only database boundaries in several places, but
the container/network enforcement layer is not implemented yet.

## Logging And Error Reporting

Logs and error reports are customer data when they contain values, questions,
screenshots, identifiers, paths, hostnames, stack traces with parameters, or
source context. Product error reporting must therefore:

- separate technical error codes from sensitive payloads;
- capture screenshots only inside the customer boundary;
- redact row values, prompts, SQL parameters, credentials, and provider
  responses by default;
- attach hashes, module names, status, and blocker codes as safe metadata;
- require explicit user action before sharing any support bundle externally.

## Repository Implications

- Continue versioning only safe metadata, hashes, schemas without private
  values, contracts, commands, and approvals that do not expose source rows.
- Keep raw sources, generated results, completed sensitive workbooks, local
  model outputs, and logs outside Git.
- Before any public visibility change, run the inventory workflow in
  [Private Artifact Governance](private-artifact-governance.md).
- Do not treat a private GitHub repository as the permanent storage model for
  customer data.

## Open Implementation Gaps

- Deployment-level egress deny rules are not implemented.
- Product API identity and authorization are not implemented.
- Tenant isolation and row-level security are not implemented.
- Central audit logging is not implemented.
- Error-reporting UI/support workflow is not implemented.
- Secret manager integration and key rotation are not implemented.
- Backup, retention, deletion, and restore tests are not implemented.

