---
name: customer-data-boundary
description: Review any change that could move customer data, prompts, results, logs, or artifacts outside customer-controlled infrastructure. Use for work touching network calls, providers, connectors, file writes, logging, telemetry, error reporting, support bundles, exports, backups, screenshots, or repository visibility.
---

# Customer Data Boundary

## Purpose

The product promise is that customer data stays inside infrastructure the
customer controls. This skill reviews whether a change keeps that promise. It
does not restate the rules; the versioned documents below are authority and
this skill points at them.

## When to use this skill

Trigger on any change that touches:

network calls, model providers, database connectors, file writes outside the
run's output directory, logging, telemetry, metrics, error reporting, support
bundles, exports, caches, embeddings, temporary files, backups, screenshots,
new dependencies, or repository visibility.

If unsure whether a change qualifies, it qualifies.

## Required sources

- `docs/customer-data-boundary.md` - what the boundary covers and the trust zones.
- `docs/security-architecture.md` - controls and their implementation state.
- `docs/threat-model.md` - assets, attacker-controlled inputs, and invariants.
- `docs/private-artifact-governance.md` - before any visibility change.

## Required checks

- `tests/network_boundary_test.py` - fails when network-capable code appears
  outside the allowlist, and when the allowlist goes stale.
- `ruff check .` - carries the versioned security rule selection.
- Gitleaks in CI - working tree and full history.
- The offline suite for the modules the change touches.

## Review output

State these explicitly before approving a change:

```text
DATA BOUNDARY REVIEW
Data touched:      <question text, rows, metadata, prompts, results, logs, none>
Egress introduced: <none | module + destination + who authorized it>
Persistence:       <local only | new artifact + location + retention>
New risk:          <what could now leak that could not before>
Enforced by:       <test or CI gate that would catch a regression>
Decision:          <approved | blocked until X exists>
```

A review that cannot name the enforcing check is not finished. Add the check.

## Never do

- Never add a network-capable dependency without adding it to the allowlist in
  `tests/network_boundary_test.py` with a stated boundary.
- Never authorize egress, upload, publication, or training on your own. That is
  owner authority, granted per invocation.
- Never widen an existing provider or connector gate as a side effect.
- Never write customer rows, prompts, provider responses, SQL parameters,
  credentials, or private identifiers into logs, errors, or committed files.
- Never treat a private repository as storage for customer data.
- Never send a support bundle, screenshot, or diagnostic outside the boundary
  without explicit user action and redaction.
