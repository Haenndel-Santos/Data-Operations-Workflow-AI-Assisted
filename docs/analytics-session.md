# Local Analytics Session Contract

## Module

```yaml
name: analytics_session
version: 1
status: recorded_two_phase_workflow_implemented
entrypoints:
  - data_ops_lab.analytics_session.run_analytics_session_prepare
  - data_ops_lab.analytics_session.run_analytics_session_resume
inputs:
  prepare:
    - local_question_file
    - approved_semantic_state
    - recorded_translation_response
    - local_duckdb
    - approved_relationships
  resume:
    - exact_prepare_manifest
    - separate_completed_execution_review
    - unchanged_local_duckdb
    - unchanged_approved_relationships
    - recorded_narration_response
outputs:
  prepare:
    - immutable_prepare_manifest_blockers_and_report
    - nested_translation_and_query_plan_evidence
    - pending_execution_review_template_when_ready
  resume:
    - immutable_resume_manifest_blockers_and_report
    - nested_execution_presentation_and_narration_evidence_as_reached
dependencies:
  - analytics_nl_translation
  - analytics_semantic_adapter
  - analytics_query_plan
  - analytics_query_execution
  - analytics_result_presentation
  - analytics_result_narration
capabilities:
  - prepare_recorded_local_session
  - stop_for_exact_execution_review
  - resume_reviewed_session
  - preserve_last_valid_checkpoint
workflows:
  - recorded_local_prepare
  - exact_reviewed_local_resume
validation:
  - source_and_artifact_identity
  - exact_human_review_binding
  - ordered_stage_status
  - input_drift_and_non_overwrite
tests:
  - tests/analytics_session_test.py
failure_policy: fail_closed_stop_before_dependent_stages_and_never_overwrite_evidence
```

## Two-Phase Workflow

Preparation calls the existing recorded Stage 5D translation boundary and its
semantic adapter. If they produce a request, it calls Stage 5A and stops at
`awaiting_execution_review`. It never calls Stage 5B. Ambiguity remains
`clarification_required`; blocked translation or planning remains blocked.

Preparation writes an immutable checkpoint and a pending review template bound
to the exact checkpoint and Stage 5A plan SHA-256. Complete the review in a
separate file; do not edit the generated template in place:

```yaml
version: 1
status: completed
source:
  prepare_manifest_sha256: <exact SHA-256>
  reviewed_plan_sha256: <exact SHA-256>
review:
  decision: approved
  reviewed_by: <human identity>
  reviewed_at: <ISO-8601 timestamp with timezone>
  notes: <non-empty review evidence>
```

Resume validates the prepared request, plan, database identity, approved
relationships, checkpoint, and completed human review before Stage 5B. It then
calls the unchanged execution, deterministic presentation, and recorded
narration modules in order. A failed stage prevents dependent stages and records
the last valid checkpoint.

## Evidence And Resume Semantics

Preparation and resume use separate output directories. Every root checkpoint
and nested stage output is idempotent: byte-identical reruns are reused and
different evidence is never overwritten. A corrected review or provider
response must use a new resume output directory if a prior attempt wrote
different evidence. Resume preflights existing authority before starting any
dependent stage, preventing partial contamination of a blocked directory.

Session manifests contain stage states, hashes, database size/modification
identity, controls, and artifact paths. They omit question text, filter values,
SQL, parameters, result rows, and narrative text. Nested local artifacts still
contain the private content required by their existing contracts and belong
under ignored `outputs/` storage.

This workflow does not implement general module discovery, arbitrary dependency
graphs, concurrency, external databases, a live provider, or a user interface.

## Commands

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-session-prepare-recorded `
  --question-file "outputs\<run-id>\question.txt" `
  --semantic-state "config\analytics\approved_semantic_catalog.yml" `
  --translation-response "outputs\<run-id>\recorded_translation.yml" `
  --database "outputs\<run-id>\operations.duckdb" `
  --relationships "config\data_model\approved_relationships.yml" `
  --output "outputs\<run-id>\session_prepare"

.\.venv\Scripts\python.exe -m data_ops_lab analytics-session-resume-recorded `
  --prepare-manifest "outputs\<run-id>\session_prepare\analytics_session_prepare.yml" `
  --review "outputs\<run-id>\completed_execution_review.yml" `
  --database "outputs\<run-id>\operations.duckdb" `
  --relationships "config\data_model\approved_relationships.yml" `
  --narration-response "outputs\<run-id>\recorded_narration.yml" `
  --output "outputs\<run-id>\session_resume"
```

The CLI exposes no execution bypass, review auto-approval, raw SQL, network
switch, or live-provider selection.
