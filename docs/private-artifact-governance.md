# Private Artifact Governance

This project may keep local files that are operationally necessary but unsafe to
publish. The default rule is: **do not commit private source data, generated
outputs, secrets, credentials, completed local review workbooks, or row-level
artifacts to this repository**. A private GitHub repository is only an access
control layer; if the repository later becomes public, every committed blob in
its visible history can become public too.

## What can be versioned safely

Prefer committing reproducible, non-sensitive metadata instead of the files
it describes:

| Artifact type | Versioned representation | Keep out of Git |
| --- | --- | --- |
| Private source exports | Manifest with filename category, byte size, SHA-256, provenance note, owner, and approval state | Raw CSV/XLSX/DB/backup files and row values |
| Generated analysis outputs | Contract docs, schemas without private values, blocker codes, aggregate counts, hashes, and reproduction commands | `outputs/` run folders, result CSVs, DuckDB/Parquet artifacts, logs with values |
| Human review workbooks | Decision schema, reviewer workflow, safe summaries, hashes, and explicit approval state | Completed local workbooks when they contain source rows, comments, or identities |
| Secrets and environment settings | `.env.example` with placeholder names only | `.env`, tokens, connection strings, hostnames that identify private systems |
| Public/reference datasets | Source URL, SPDX license, manifest, conversion recipe, hash, and approved use scope | Downloaded archives or derived artifacts unless license and size policy approve them |

## Safe promotion workflow

Use this checklist before adding any local-only file or making the GitHub
repository public:

1. **Inventory local-only paths** with Git-aware commands such as
   `git status --ignored --short`, `git check-ignore -v <path>`, and a manual
   review of `originaldatabase/`, `outputs/`, local `.env*`, downloaded dataset
   folders, notebooks, and ad-hoc reports.
2. **Classify each file** as one of: source data, generated output, approval
   evidence, secret/configuration, public licensed input, or safe metadata.
3. **Extract only safe metadata** into versioned manifests or documentation:
   hashes, counts, schemas, contract versions, commands, provenance, license,
   and approval status. Do not copy row values, questions, provider responses,
   SQL parameters, personal names, customer/vendor identifiers, or credentials.
4. **Keep sensitive artifacts outside the public repository** using a private
   storage system with explicit access controls, for example a separate private
   repository, private object storage, encrypted archive, or local backup.
5. **If Git synchronization is required for sensitive artifacts**, use a
   separate private repository or private submodule whose contents are never
   assumed safe for publication. Do not rely on a public repository path plus
   `.gitignore`: `.gitignore` prevents future adds only; it does not protect
   files already committed.
6. **If encrypted artifacts must be committed**, commit only encrypted blobs and
   keep keys out of GitHub. Treat this as a separate security decision requiring
   named owners, key rotation, restore testing, and review before public release.
7. **Scan before changing visibility**: verify `git log --all --stat`,
   `git log --all -- <sensitive-path>`, `git ls-files`, and a secret scanner.
   If private files were ever committed, remove them from history before making
   the repository public and rotate any exposed credentials.
8. **Record the decision** in project docs: what stayed local, what metadata was
   committed, where the private artifact is stored, who may access it, and what
   approval allows future use.

## Recommended repository split

For the planned cloud-first workflow, keep this repository as the public-capable
code, contracts, tests, docs, fixtures, and safe manifests repository. Store
private data and heavy generated artifacts elsewhere:

```text
Data-Operations-Workflow-AI-Assisted/      # public-capable code/docs/tests
private-data-operations-artifacts/         # private repository or storage bucket
  originaldatabase/                        # raw private inputs
  outputs/                                 # generated runs and local evidence
  reviews/                                 # completed sensitive workbooks
  secrets/                                 # never commit; prefer secret manager
```

The public-capable repository may reference private artifacts by stable
metadata, for example:

```yaml
artifact_id: eds_source_export_2026_07
storage_location: private-artifact-store/originaldatabase/  # no public URL
sha256: <hash>
byte_size: <bytes>
approval_state: private_local_use_only
publication: not_authorized
```

## Visibility decision rule

Before switching GitHub from private to public, the safe answer is **do not
upload sensitive local project files into this repository**. Upload only safe
manifests and documentation. Keep the real files in a separate private store, or
commit encrypted artifacts only after a deliberate security design and key
management review. Anything committed unencrypted to this repository should be
assumed publishable if the repository becomes public.
