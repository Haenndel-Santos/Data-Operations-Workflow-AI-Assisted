# Product Vision

## Purpose

Evolve the existing local-first analytics backend into a private Data
Intelligence product for small and medium-sized businesses that do not have a
dedicated data analyst. The product should let a business stakeholder ask a
plain-language operational question, review the interpreted analytical plan,
and receive a reproducible answer with evidence, confidence notes, and
actionable explanation without writing SQL.

This vision extends the current analyst-oriented workflow. It does not replace
the existing governance model, ERP evidence work, or deterministic execution
contracts.

## Product Definition

The product is a customer-hosted, AI-assisted Data Intelligence platform that
turns operational data into governed analysis:

```text
business data
  -> data understanding
  -> validation and review
  -> deterministic analysis
  -> grounded explanation
  -> decision support
```

The AI is an interpretation and explanation layer. Deterministic local code
remains the authority for schema resolution, SQL compilation, joins, filters,
statistics, numeric values, approvals, and evidence.

## Primary Users

| User | Need | Product response |
| --- | --- | --- |
| Business owner or manager | Understand what changed and what deserves attention | Simple answer, drivers, confidence, caveats, next analytical questions |
| Operations lead | Investigate process, product, customer, supplier, or logistics issues | Governed drill-down, filters, trends, comparisons, exportable evidence |
| Data or operations analyst | Review semantics, plans, relationships, and evidence | Advanced view with catalog, join paths, controls, hashes, and reproducibility |
| System administrator | Keep data private, access controlled, and auditable | Local deployment, identity, RBAC, audit logs, backup, and support controls |

Analysts remain important advanced users, but the default product experience is
for decision-makers who do not know SQL, schema design, or statistical tooling.

## Positioning

The product is not a generic chatbot over spreadsheets. It is a governed
analysis system with a conversational surface:

- The user asks business questions.
- The system clarifies ambiguous terms instead of guessing silently.
- The model proposes structured semantic intent, not executable SQL.
- Local validators and compilers decide whether a query is allowed.
- Local analytical engines compute the numbers.
- Narration cites deterministic facts and remains non-authoritative.
- Every promoted relationship, semantic definition, and answer benchmark is
  reviewable and hash-bound.

## Product Principles

| Principle | Meaning |
| --- | --- |
| Private by default | Customer data, prompts, results, logs, and generated artifacts stay inside the customer-controlled environment. |
| Deterministic authority | Code and approved contracts calculate and validate; the model interprets and explains. |
| Human control | Missing or pending review never becomes approval. Human decisions override automation. |
| Explainable answers | Every answer should expose the metric, filters, grain, dataset, controls, caveats, and evidence. |
| Progressive depth | Simple View gives the decision summary; Analytical View exposes the full evidence trail. |
| Fail closed | Ambiguity, drift, missing authority, unsafe output, or resource limit failures stop the workflow without partial authority. |
| Modular product | Features, connectors, providers, and UX surfaces should be independently enableable by customer and deployment policy. |

## Core User Journey

```text
1. Administrator connects or imports an authorized local dataset.
2. System profiles, cleans, detects schema, and proposes relationships.
3. Human reviewer approves relationships and semantic definitions.
4. Stakeholder asks a question in natural language.
5. AI translates the question into semantic intent.
6. System asks for clarification when terms are ambiguous or unsupported.
7. System compiles a deterministic plan and stops for review when required.
8. Approved plan executes locally with read-only limits.
9. User receives a Simple View answer plus confidence and caveats.
10. User can open Analytical View for facts, controls, query plan, and hashes.
11. Corrections become versioned feedback, not silent model or catalog changes.
```

## Simple View And Analytical View

| View | Audience | Contents |
| --- | --- | --- |
| Simple View | Business stakeholder | Plain-language answer, primary drivers, confidence, caveats, recommended next questions |
| Analytical View | Analyst/reviewer | Metric definition, period comparison, filters, dataset, tables, join path, sample size, missing values, controls, plan, hashes, evidence |

The two views must be backed by the same deterministic result evidence. Simple
View never creates a second, unverified interpretation of the result.

## Non-Goals For The Current Stage

- Do not train or fine-tune a model on customer data.
- Do not execute model-generated SQL.
- Do not call hosted or LAN model providers.
- Do not build a production UI before the security and product boundaries are
  versioned.
- Do not collapse review states into one approval flag.
- Do not treat Northwind development evidence as a fresh holdout.
- Do not promote AdventureWorks relationships or semantics until their exact
  review gates complete.

## Evidence

This vision is grounded in:

- [Project Master](project-master.md)
- [Architecture](architecture.md)
- [AI-Assisted Analytics Backend](ai-analytics-backend.md)
- [AI Platform Implementation Roadmap](ai-implementation-roadmap.md)
- [Private Artifact Governance](private-artifact-governance.md)
- the Sprint 0 user-provided product/security brief and screenshots

