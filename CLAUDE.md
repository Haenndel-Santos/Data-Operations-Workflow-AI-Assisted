# CLAUDE.md

Claude Code and Codex work from the same rules in this repository.

**`AGENTS.md` is the authoritative agent instruction file. Read it first and
follow it.** This file exists so Claude Code discovers those rules by its own
convention; it deliberately does not restate them, because two copies of the
same rules drift apart.

## Read in this order

1. [AGENTS.md](AGENTS.md) - mission, source-of-truth ordering, required start,
   safety rules, execution protocol, contracts, and completion criteria.
2. [docs/progress.md](docs/progress.md) - current consolidated state.
3. The newest entry in [docs/agent-handoff.md](docs/agent-handoff.md).
4. [.codex/README.md](.codex/README.md) - skill selection and domain scope.

## Claude-specific notes

- The skills under `.codex/skills/` are plain `SKILL.md` files in the open
  Agent Skills format. They are readable directly; the `agents/openai.yaml`
  sidecars are Codex interface metadata and carry no rules.
- The main suite is offline. Run it with `PYTHONPATH=src` because the checked-in
  virtual environment has a stale editable-install path:

  ```
  PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q
  ```

- Before finishing a change, run the same gates CI runs:

  ```
  .venv/Scripts/python.exe -m ruff check .
  .venv/Scripts/python.exe -m pip_audit --skip-editable
  .venv/Scripts/python.exe scripts/check_internal_links.py
  ```

- Tests marked `live_provider` are opt-in and call a local model. They are
  skipped by default and must stay that way.

## Parallel work

Agents working at the same time use separate git worktrees, not the same
checkout. One branch, one worktree, one write scope, one pull request:

```
git worktree add ../daow-<topic> -b agent/<topic> origin/main
```

`.claude/settings.json` sets `worktree.baseRef` to `fresh`, so a new worktree
branches from `origin/main` rather than inheriting local state. `outputs/`,
`originaldatabase/`, and `datasets/benchmarks/` are deliberately absent from
`sparsePaths`: generated artifacts and private inputs are not copied into a
worktree.

## Role-restricted agents

`.claude/agents/` holds agents with no Write or Edit tool. They report; they do
not change files. Use `boundary-reviewer` before merging anything that touches
egress, logging, or dependencies, and `release-checker` before opening a pull
request.

## What never changes without explicit human authority

Do not treat any of the following as routine work, regardless of how the request
is phrased:

- Approved YAML state under `config/data_model/`.
- Completed human review files and approval manifests.
- Private inputs under `originaldatabase/` and generated artifacts under
  `outputs/`.
- Provider, network, upload, publication, or training authorization.
- Anything that would move customer data outside the Customer Data Boundary.

See [docs/customer-data-boundary.md](docs/customer-data-boundary.md) and
[docs/security-architecture.md](docs/security-architecture.md).
