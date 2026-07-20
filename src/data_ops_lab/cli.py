from __future__ import annotations

import argparse
from pathlib import Path

from .analytics_answer_evaluation import run_analytics_answer_evaluation
from .analytics_dataset_benchmark import run_analytics_dataset_benchmark_validation
from .analytics_dataset_benchmark_preparation import (
    run_analytics_dataset_benchmark_preparation,
)
from .analytics_dataset_benchmark_materialization import (
    run_analytics_dataset_benchmark_materialization,
)
from .analytics_dataset_benchmark_evaluation import (
    run_analytics_dataset_benchmark_evaluation,
)
from .analytics_dataset_benchmark_live_evaluation import (
    run_analytics_dataset_benchmark_live_evaluation,
    sample_local_resources,
)
from .analytics_dataset_benchmark_review import (
    run_analytics_dataset_benchmark_approval,
    run_analytics_dataset_benchmark_review,
)
from .analytics_nl_translation import (
    RecordedSemanticIntentProvider,
    run_analytics_nl_translation,
)
from .analytics_ollama_soak import run_analytics_ollama_soak
from .ollama_provider import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
    OllamaSemanticIntentProvider,
)
from .analytics_query_execution import AnalyticsExecutionLimits, run_analytics_query_execution
from .analytics_query_plan import run_analytics_query_plan
from .analytics_result_narration import (
    RecordedResultNarrationProvider,
    run_analytics_result_narration,
)
from .analytics_result_presentation import run_analytics_result_presentation
from .analytics_session import run_analytics_session_prepare, run_analytics_session_resume
from .analytics_semantic_adapter import run_analytics_semantic_adapter
from .analytics_semantic_approval import run_analytics_semantic_approval
from .analytics_semantic_catalog import run_analytics_semantic_catalog
from .analytics_semantic_review import run_analytics_semantic_review
from .analytics_translation_evaluation import run_analytics_translation_evaluation
from .approval_spreadsheet import run_approval_spreadsheet
from .benchmark_sql_conversion import run_benchmark_sql_conversion
from .business_flow_mapping import run_business_flow_mapping
from .canonical_model import run_canonical_model_alignment
from .cli_commands import (
    register_analytics_dataset_benchmark_commands,
    register_analytics_query_session_commands,
    register_analytics_semantic_commands,
    register_reference_dataset_commands,
)
from .human_review import run_human_review, validate_approval_template
from .module_registry import run_module_registry_validation
from .performance_baseline import run_performance_baseline
from .product_canonical_promotion import run_product_canonical_promotion
from .product_materialization import run_product_materialization
from .product_reference_audit import run_product_reference_audit
from .product_reference_final_decision import run_product_reference_final_decision
from .product_reference_review_spreadsheet import run_product_reference_review_spreadsheet
from .product_refnr_application import run_product_refnr_application
from .product_refnr_decision_validation import run_validate_product_refnr_decisions
from .product_refnr_final_review_spreadsheet import run_product_refnr_final_review_spreadsheet
from .product_refnr_final_review_validation import run_validate_product_refnr_final_review
from .product_refnr_human_review import run_product_refnr_human_review
from .product_refnr_missing_notes_fix import run_product_refnr_missing_notes_fix
from .product_refnr_reconciliation import run_product_refnr_reconciliation
from .reference_dataset_validation import run_reference_dataset_validation
from .schema_overview import run_schema_overview
from .serial_aware_review import run_serial_aware_review
from .serial_rules import run_serial_rules
from .source_onboarding import run_source_onboarding
from .workflow import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataops",
        description="Run an AI-assisted data operations workflow for local CSV/XLSX files.",
    )
    subparsers = parser.add_subparsers(dest="command")

    analytics_module_registry = subparsers.add_parser(
        "analytics-module-registry-validate",
        help="Validate analytics module contracts and workflow dependencies without executing them.",
    )
    analytics_module_registry.add_argument(
        "--registry",
        type=Path,
        default=Path("config/orchestrator/analytics_module_registry.yml"),
        help="Version-1 declarative analytics module registry YAML.",
    )
    analytics_module_registry.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root used only to validate declared test-file paths.",
    )
    analytics_module_registry.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_module_registry_validation"),
        help="New or byte-identical directory for dry-run registry validation evidence.",
    )

    pipeline_performance_baseline = subparsers.add_parser(
        "pipeline-performance-baseline",
        help="Measure Pandas-heavy pipeline stages with generated synthetic Parquet only.",
    )
    pipeline_performance_baseline.add_argument(
        "--rows-per-table",
        type=int,
        default=50_000,
    )
    pipeline_performance_baseline.add_argument(
        "--table-count",
        type=int,
        default=3,
    )
    pipeline_performance_baseline.add_argument(
        "--stage-timeout-seconds",
        type=int,
        default=120,
    )
    pipeline_performance_baseline.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/pipeline_performance_baseline"),
        help="New or empty directory for run-specific synthetic measurement evidence.",
    )

    register_analytics_query_session_commands(subparsers)

    register_analytics_semantic_commands(subparsers)

    register_analytics_dataset_benchmark_commands(subparsers)

    analytics_ollama_soak = subparsers.add_parser(
        "analytics-ollama-soak",
        help="Preflight or run a separately authorized bounded local Ollama overnight soak.",
    )
    analytics_ollama_soak.add_argument("--dataset-manifest", type=Path, required=True)
    analytics_ollama_soak.add_argument("--database", type=Path, required=True)
    analytics_ollama_soak.add_argument("--semantic-state", type=Path, required=True)
    analytics_ollama_soak.add_argument("--relationships", type=Path, required=True)
    analytics_ollama_soak.add_argument("--pack", type=Path, required=True)
    analytics_ollama_soak.add_argument("--approval", type=Path, required=True)
    analytics_ollama_soak.add_argument("--live-authorization", type=Path, required=True)
    analytics_ollama_soak.add_argument("--soak-authorization", type=Path, required=True)
    analytics_ollama_soak.add_argument("--endpoint", default=DEFAULT_OLLAMA_ENDPOINT)
    analytics_ollama_soak.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    analytics_ollama_soak.add_argument(
        "--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS
    )
    analytics_ollama_soak.add_argument(
        "--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS
    )
    analytics_ollama_soak.add_argument("--timeout-seconds", type=int, default=120)
    analytics_ollama_soak.add_argument("--output", type=Path, required=True)
    analytics_ollama_soak.add_argument(
        "--execute",
        action="store_true",
        help="Run the authorized bounded soak after successful offline preflight.",
    )
    analytics_ollama_soak.add_argument(
        "--allow-network",
        action="store_true",
        help="Authorize literal-loopback Ollama HTTP for this invocation only.",
    )

    register_reference_dataset_commands(subparsers)

    onboard = subparsers.add_parser("source-onboard", help="Run Step 3 source onboarding and candidate modeling.")
    onboard.add_argument("--input", type=Path, required=True, help="Directory containing raw CSV/XLSX files.")
    onboard.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory for Step 3 generated outputs.",
    )
    onboard.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for data-model review files.",
    )

    review = subparsers.add_parser("human-review", help="Run Step 3B human review preparation.")
    review.add_argument(
        "--step3-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory containing Step 3 candidate CSVs.",
    )
    review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3b_human_review"),
        help="Directory for Step 3B human review outputs.",
    )
    review.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for data-model review files.",
    )

    apply_approvals = subparsers.add_parser(
        "apply-approvals",
        help="Validate a human approval template. This command does not modify approved files yet.",
    )
    apply_approvals.add_argument("--input", type=Path, required=True, help="Human approval template YAML.")

    serial_rules = subparsers.add_parser("serial-rules", help="Run Step 3C serial reference rule mapping.")
    serial_rules.add_argument("--input", type=Path, required=True, help="Path to originaldatabase/Serials.xlsx.")
    serial_rules.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing raw source exports to validate. Defaults to the input file parent.",
    )
    serial_rules.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3c_serial_reference_rules"),
        help="Directory for Step 3C generated outputs.",
    )
    serial_rules.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for generated serial rule configs.",
    )
    serial_rules.add_argument(
        "--step3-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory containing Step 3 key candidates.",
    )

    serial_review = subparsers.add_parser("serial-aware-review", help="Run Step 3D serial-aware approval preparation.")
    serial_review.add_argument(
        "--step3-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory containing Step 3 candidate CSVs.",
    )
    serial_review.add_argument(
        "--step3c-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3c_serial_reference_rules"),
        help="Directory containing Step 3C serial validation outputs.",
    )
    serial_review.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory containing semantic ref mapping and approval templates.",
    )
    serial_review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3d_serial_aware_review"),
        help="Directory for Step 3D generated outputs.",
    )
    serial_review.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing raw source exports for conflict metadata only.",
    )

    approval_sheet = subparsers.add_parser("approval-spreadsheet", help="Run Step 3E human approval spreadsheet generation.")
    approval_sheet.add_argument(
        "--step3d-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3d_serial_aware_review"),
        help="Directory containing Step 3D serial-aware review outputs.",
    )
    approval_sheet.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Step 3E spreadsheet outputs.",
    )
    approval_sheet.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Data model config directory. Approved files are not modified.",
    )

    canonical_model = subparsers.add_parser(
        "canonical-model",
        help="Run Step 3E.1 canonical model alignment and Product reference validation.",
    )
    canonical_model.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing raw source exports. Files are read only.",
    )
    canonical_model.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for canonical model config outputs. Approved files are not modified.",
    )
    canonical_model.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Step 3E.1 generated review reports.",
    )

    product_audit = subparsers.add_parser(
        "product-reference-audit",
        help="Run focused Product part_nr_sku duplicate and empty-reference audit.",
    )
    product_audit.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing Product.xlsx. Files are read only.",
    )
    product_audit.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Product duplicate audit report.",
    )

    product_review_sheet = subparsers.add_parser(
        "product-reference-review-spreadsheet",
        help="Generate an internal Product reference human review workbook with raw part_nr_sku values.",
    )
    product_review_sheet.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing Product.xlsx. Files are read only.",
    )
    product_review_sheet.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Product human review workbook.",
    )

    product_final_decision = subparsers.add_parser(
        "product-reference-final-decision",
        help="Consolidate completed Product human review workbook decisions into a final Markdown report.",
    )
    product_final_decision.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product human review workbook and final report output.",
    )
    product_final_decision.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_reference_human_review.xlsx. The workbook is read only.",
    )

    product_refnr_reconciliation = subparsers.add_parser(
        "product-refnr-reconciliation",
        help="Reconcile Product.xlsx against Product_ref.nr correction/enrichment source.",
    )
    product_refnr_reconciliation.add_argument(
        "--db-dir",
        type=Path,
        default=Path("db"),
        help="Directory expected to contain Product_ref.nr. Falls back to originaldatabase when needed.",
    )
    product_refnr_reconciliation.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing Product.xlsx and fallback Product_ref.nr location.",
    )
    product_refnr_reconciliation.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Product ref.nr reconciliation outputs.",
    )

    product_refnr_human_review = subparsers.add_parser(
        "product-refnr-human-review",
        help="Generate Product ref.nr reconciliation exception shortlist for human review.",
    )
    product_refnr_human_review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing reconciliation workbook and receiving shortlist outputs.",
    )
    product_refnr_human_review.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_reconciliation_review.xlsx. The workbook is read only.",
    )

    product_refnr_decision_validation = subparsers.add_parser(
        "validate-product-refnr-decisions",
        help="Validate completed Product ref.nr human review decisions without applying them.",
    )
    product_refnr_decision_validation.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product ref.nr human review shortlist and validation outputs.",
    )
    product_refnr_decision_validation.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_human_review_shortlist.xlsx. The workbook is read only.",
    )

    product_refnr_final_review = subparsers.add_parser(
        "product-refnr-final-review-spreadsheet",
        help="Generate Product final review spreadsheet containing only blocking Product RefNr issues.",
    )
    product_refnr_final_review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product ref.nr shortlist and receiving final review spreadsheet outputs.",
    )
    product_refnr_final_review.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_human_review_shortlist.xlsx. The workbook is read only.",
    )

    product_refnr_final_review_validation = subparsers.add_parser(
        "validate-product-refnr-final-review",
        help="Validate completed Product final review decisions without applying them.",
    )
    product_refnr_final_review_validation.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product final review workbook and validation outputs.",
    )
    product_refnr_final_review_validation.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_required.xlsx. The workbook is read only.",
    )

    product_refnr_application = subparsers.add_parser(
        "apply-product-refnr-decisions",
        help="Build or explicitly apply the validated Product reconciliation decision state.",
    )
    product_refnr_application.add_argument(
        "--workbook",
        type=Path,
        required=True,
        help="Validated Product final review workbook. The workbook is read only and revalidated.",
    )
    product_refnr_application.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e4_product_application"),
        help="Directory for the application plan and audit report.",
    )
    product_refnr_application.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Data model config directory containing the Product reconciliation state.",
    )
    product_refnr_application.add_argument(
        "--apply",
        action="store_true",
        help="Write product_reconciliation_state.yml. Without this flag, only a dry-run is performed.",
    )
    product_refnr_application.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace a different existing state after preserving a history copy. Requires --apply.",
    )

    product_materialization = subparsers.add_parser(
        "product-materialization-preview",
        help="Build a read-only Product preview from applied reconciliation state, or report blockers.",
    )
    product_materialization.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing read-only Product.xlsx and Product_ref.nr.xlsx sources.",
    )
    product_materialization.add_argument(
        "--workbook",
        type=Path,
        required=True,
        help="Validated Product final review workbook used by the applied state.",
    )
    product_materialization.add_argument(
        "--state",
        type=Path,
        default=Path("config/data_model/product_reconciliation_state.yml"),
        help="Applied Product reconciliation state.",
    )
    product_materialization.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e5_product_materialization"),
        help="New or byte-identical output directory for local preview artifacts.",
    )

    product_canonical_promotion = subparsers.add_parser(
        "product-canonical-promotion-plan",
        help="Validate Step 3E.5 artifacts and build a dry-run canonical Product promotion plan.",
    )
    product_canonical_promotion.add_argument(
        "--materialization",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e5_product_materialization"),
        help="Directory containing the complete Step 3E.5 materialization package.",
    )
    product_canonical_promotion.add_argument(
        "--state",
        type=Path,
        default=Path("config/data_model/product_reconciliation_state.yml"),
        help="Applied Product reconciliation state bound to the materialization package.",
    )
    product_canonical_promotion.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e6_product_canonical_promotion"),
        help="New or byte-identical output directory for the dry-run promotion plan.",
    )

    product_refnr_missing_notes_fix = subparsers.add_parser(
        "product-refnr-missing-notes-fix",
        help="Generate auxiliary spreadsheet for Product final review rows missing final_human_notes.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product final review validation files and receiving fix outputs.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_required.xlsx. The workbook is read only.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--validation-report",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_validation_report.md.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--validation-summary",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_validation_summary.csv.",
    )

    schema_overview = subparsers.add_parser(
        "schema-overview",
        help="Generate conceptual main database schema overview documentation and SQL.",
    )
    schema_overview.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/schema_overview"),
        help="Directory for conceptual schema overview outputs.",
    )

    business_flow_mapping = subparsers.add_parser(
        "business-flow-mapping",
        help="Register confirmed business-flow mapping as pending validation config and documentation.",
    )
    business_flow_mapping.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Data model config directory. Approved files are not modified.",
    )
    business_flow_mapping.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/schema_overview"),
        help="Directory for business-flow mapping outputs.",
    )

    parser.add_argument("--input", type=Path, help="Directory containing raw CSV/XLSX files.")
    parser.add_argument("--output", type=Path, default=Path("outputs/run"), help="Directory for generated outputs.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analytics-module-registry-validate":
        result = run_module_registry_validation(
            args.registry,
            args.output,
            project_root=args.project_root,
        )
        print("Analytics module registry validation complete")
        print(f"Status: {result.status}")
        print(f"Modules: {result.module_count}")
        print(f"Workflows: {result.workflow_count}")
        print(f"Stages: {result.stage_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Blockers CSV: {result.blockers_path}")
        print(f"Report: {result.report_path}")
        print("Dry-run only. Entrypoints were inspected statically and no workflow was executed.")
        return

    if args.command == "pipeline-performance-baseline":
        result = run_performance_baseline(
            args.output,
            rows_per_table=args.rows_per_table,
            table_count=args.table_count,
            stage_timeout_seconds=args.stage_timeout_seconds,
        )
        print("Synthetic pipeline performance baseline complete")
        print(f"Status: {result.status}")
        print(f"Stages completed: {result.completed_stage_count}/{result.stage_count}")
        print(f"Highest-memory stage: {result.highest_memory_stage or 'unavailable'}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Metrics: {result.metrics_path}")
        print(f"Report: {result.report_path}")
        print("Generated synthetic Parquet only; no real dataset, database, provider, or network was used.")
        return

    if args.command == "analytics-query-plan":
        result = run_analytics_query_plan(
            args.request,
            args.database,
            args.relationships,
            args.output,
        )
        print("Structured analytics query planning complete")
        print(f"Status: {result.status}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Plan: {result.plan_path}")
        print(f"Blockers CSV: {result.blockers_path}")
        print(f"Report: {result.report_path}")
        print("Dry-run only. No SQL was executed and no database or external system was modified.")
        return

    if args.command == "analytics-query-execute":
        result = run_analytics_query_execution(
            args.request,
            args.database,
            args.relationships,
            args.plan,
            args.output,
            AnalyticsExecutionLimits(
                max_rows=args.max_rows,
                max_result_bytes=args.max_result_bytes,
                max_runtime_seconds=args.max_runtime_seconds,
                memory_limit_mb=args.memory_limit_mb,
                threads=args.threads,
                max_temp_mb=args.max_temp_mb,
            ),
        )
        print("Controlled analytics query execution complete")
        print(f"Status: {result.status}")
        print(f"Rows: {result.row_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Elapsed seconds: {result.elapsed_seconds:.3f}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Result: {result.result_path or 'not written'}")
        print("DuckDB was opened read-only; no raw SQL or external access was accepted.")
        return

    if args.command == "analytics-result-present":
        result = run_analytics_result_presentation(
            args.request,
            args.execution_manifest,
            args.result,
            args.output,
        )
        print("Deterministic analytics result presentation complete")
        print(f"Status: {result.status}")
        print(f"Rows: {result.row_count}")
        print(f"Preview rows: {result.preview_row_count}")
        print(f"Preview columns: {result.preview_column_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Presentation: {result.presentation_path}")
        print(f"Facts: {result.facts_path or 'not written'}")
        print("Validated Stage 5B evidence only; no database, query, provider, or network was used.")
        return

    if args.command == "analytics-result-narrate-recorded":
        result = run_analytics_result_narration(
            args.presentation_manifest,
            args.facts,
            args.output,
            RecordedResultNarrationProvider(args.provider_response),
            timeout_seconds=args.timeout_seconds,
        )
        print("Offline analytics result narration validation complete")
        print(f"Status: {result.status}")
        print(f"Provider called: {result.provider_called}")
        print(f"Claims: {result.claim_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Narrative: {result.narrative_path or 'not written'}")
        print("Recorded response only; facts remain authoritative and no query or network was used.")
        return

    if args.command == "analytics-session-prepare-recorded":
        result = run_analytics_session_prepare(
            args.question_file,
            args.semantic_state,
            args.translation_response,
            args.database,
            args.relationships,
            args.output,
        )
        print("Recorded local analytics session preparation complete")
        print(f"Status: {result.status}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Execution review: {result.review_template_path or 'not written'}")
        print("Preparation stops before Stage 5B; a separate exact human review is required.")
        return

    if args.command == "analytics-session-resume-recorded":
        result = run_analytics_session_resume(
            args.prepare_manifest,
            args.review,
            args.database,
            args.relationships,
            args.narration_response,
            args.output,
        )
        print("Recorded local analytics session resume complete")
        print(f"Status: {result.status}")
        print(f"Last valid checkpoint: {result.last_valid_checkpoint}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print("Reviewed local execution and recorded narration only; no network was used.")
        return

    if args.command == "analytics-semantic-catalog":
        result = run_analytics_semantic_catalog(
            args.catalog,
            args.database,
            args.relationships,
            args.output,
        )
        print("Analytics semantic catalog validation complete")
        print(f"Status: {result.status}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Ambiguities: {result.ambiguity_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Catalog: {result.catalog_path}")
        print(f"Blockers CSV: {result.blockers_path}")
        print(f"Report: {result.report_path}")
        print("Metadata validation only. No data rows, SQL plans, or queries were executed.")
        return

    if args.command == "analytics-semantic-review":
        result = run_analytics_semantic_review(args.catalog, args.output)
        print("Analytics semantic human review preparation complete")
        print(f"Entities: {result.entity_count}")
        print(f"Ambiguities: {result.ambiguity_count}")
        print(f"Output changed: {result.output_changed}")
        print(f"Review: {result.review_path}")
        print("Pending review only. No semantic definition or adapter use was approved.")
        return

    if args.command == "analytics-semantic-approval":
        result = run_analytics_semantic_approval(
            args.catalog,
            args.review,
            args.output,
            args.config,
            apply=args.apply,
            replace_existing=args.replace_existing,
        )
        print("Analytics semantic approval validation complete")
        print(f"Status: {result.status}")
        print(f"Mode: {'dry-run' if result.dry_run else 'apply'}")
        print(f"Blockers: {result.blocker_count}")
        print(f"State changed: {result.state_changed}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Plan: {result.plan_path}")
        print(f"State: {result.state_path}")
        print("No data rows, SQL, database connection, model API, import, or sync was used.")
        return

    if args.command == "analytics-semantic-adapter":
        result = run_analytics_semantic_adapter(
            args.intent,
            args.semantic_state,
            args.output,
        )
        print("Analytics semantic intent compilation complete")
        print(f"Status: {result.status}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Clarifications: {result.clarification_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Request: {result.request_path or 'not written'}")
        print(f"Clarifications file: {result.clarifications_path or 'not written'}")
        print("No raw SQL, model API, database connection, query, import, or sync was used.")
        return

    if args.command == "analytics-nl-translate-recorded":
        result = run_analytics_nl_translation(
            args.question_file,
            args.semantic_state,
            args.output,
            RecordedSemanticIntentProvider(args.provider_response),
            timeout_seconds=args.timeout_seconds,
        )
        print("Offline natural-language translation validation complete")
        print(f"Status: {result.status}")
        print(f"Provider called: {result.provider_called}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Clarifications: {result.clarification_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Intent: {result.intent_path or 'not written'}")
        request_path = result.adapter_result.request_path if result.adapter_result else None
        print(f"Stage 5A request: {request_path or 'not written'}")
        print("Recorded offline response only. No network, model API, database, or query was used.")
        return

    if args.command == "analytics-nl-translate-ollama":
        provider = OllamaSemanticIntentProvider(
            endpoint=args.endpoint,
            model=args.model,
            context_tokens=args.context_tokens,
            max_output_tokens=args.max_output_tokens,
        )
        result = run_analytics_nl_translation(
            args.question_file,
            args.semantic_state,
            args.output,
            provider,
            timeout_seconds=args.timeout_seconds,
            allow_network=args.allow_network,
        )
        print("Local Ollama semantic translation complete")
        print(f"Status: {result.status}")
        print(f"Provider called: {result.provider_called}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Clarifications: {result.clarification_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Intent: {result.intent_path or 'not written'}")
        request_path = result.adapter_result.request_path if result.adapter_result else None
        print(f"Stage 5A request: {request_path or 'not written'}")
        print("Loopback Ollama only. No database connection, query, import, or sync was used.")
        return

    if args.command == "analytics-translation-evaluate":
        result = run_analytics_translation_evaluation(
            args.pack,
            args.semantic_state,
            args.output,
        )
        print("Synthetic translation evaluation complete")
        print(f"Status: {result.status}")
        print(f"Cases: {result.case_count}")
        print(f"Passed: {result.passed_count}")
        print(f"Failed: {result.failed_count}")
        print(f"Contract blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print("Synthetic offline providers only. No network, model API, database, or query was used.")
        return

    if args.command == "analytics-answer-evaluate":
        result = run_analytics_answer_evaluation(
            args.pack,
            args.semantic_state,
            args.output,
        )
        print("Synthetic expected-answer evaluation complete")
        print(f"Status: {result.status}")
        print(f"Cases: {result.case_count}")
        print(f"Passed: {result.passed_count}")
        print(f"Failed: {result.failed_count}")
        print(f"Contract blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print("Temporary synthetic DuckDB only. No live model, network, or external database was used.")
        return

    if args.command == "analytics-dataset-benchmark-validate":
        result = run_analytics_dataset_benchmark_validation(
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack,
            args.approval,
            args.output,
        )
        print("Dataset-backed benchmark contract validation complete")
        print(f"Status: {result.status}")
        print(f"Cases: {result.case_count}")
        print(f"Exact comparisons: {result.exact_case_count}")
        print(f"Numeric tolerances: {result.tolerance_case_count}")
        print(f"Approved relationships: {result.relationship_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print("Dry-run only. The database was hashed but never opened or queried.")
        return

    if args.command == "analytics-dataset-benchmark-answer-prepare":
        result = run_analytics_dataset_benchmark_preparation(
            args.design,
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.output,
        )
        print("Dataset benchmark answer preparation complete")
        print(f"Status: {result.status}")
        print(f"Cases: {result.case_count}")
        print(f"Review-ready plans: {result.ready_case_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Execution review: {result.review_path or 'not written'}")
        print("Preparation stops before Stage 5B; no table rows or answers were read.")
        return

    if args.command == "analytics-dataset-benchmark-answer-materialize":
        result = run_analytics_dataset_benchmark_materialization(
            args.design,
            args.dataset_manifest,
            args.preparation_manifest,
            args.execution_review,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack_output,
            args.output,
        )
        print("Dataset benchmark answer materialization complete")
        print(f"Status: {result.status}")
        print(f"Cases: {result.case_count}")
        print(f"Completed: {result.completed_count}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Candidate pack: {result.pack_path or 'not written'}")
        print("Local read-only Stage 5B only; final expected-answer review remains pending.")
        return

    if args.command == "analytics-dataset-benchmark-review":
        result = run_analytics_dataset_benchmark_review(
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack,
            args.output,
        )
        print("Dataset benchmark human review preparation complete")
        print(f"Cases: {result.case_count}")
        print(f"Output changed: {result.output_changed}")
        print(f"Review: {result.review_path}")
        print("Pending review only. No benchmark use, provider, upload, or training was approved.")
        return

    if args.command == "analytics-dataset-benchmark-approval":
        result = run_analytics_dataset_benchmark_approval(
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack,
            args.review,
            args.output,
            args.approval_output,
            apply=args.apply,
        )
        print("Dataset benchmark approval validation complete")
        print(f"Status: {result.status}")
        print(f"Mode: {'dry-run' if result.dry_run else 'apply'}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Approval changed: {result.approval_changed}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Plan: {result.plan_path}")
        print(f"Approval: {result.approval_path}")
        print("No database connection, query, live provider, network, upload, or training was used.")
        return

    if args.command == "analytics-dataset-benchmark-evaluate":
        result = run_analytics_dataset_benchmark_evaluation(
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack,
            args.approval,
            args.output,
        )
        print("Dataset-backed offline benchmark evaluation complete")
        print(f"Status: {result.status}")
        print(f"Cases: {result.case_count}")
        print(f"Passed: {result.passed_count}")
        print(f"Failed: {result.failed_count}")
        print(f"Contract blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print("Approved local DuckDB only; read-only queries, recorded responses, and no network.")
        return

    if args.command == "analytics-dataset-benchmark-evaluate-ollama":
        provider = OllamaSemanticIntentProvider(
            endpoint=args.endpoint,
            model=args.model,
            context_tokens=args.context_tokens,
            max_output_tokens=args.max_output_tokens,
        )
        result = run_analytics_dataset_benchmark_live_evaluation(
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack,
            args.approval,
            args.live_authorization,
            args.output,
            provider,
            timeout_seconds=args.timeout_seconds,
            execute=args.execute,
            allow_network=args.allow_network,
            resource_sampler=sample_local_resources if args.execute else None,
        )
        print("Dataset-backed Ollama benchmark evaluation complete")
        print(f"Status: {result.status}")
        print(f"Mode: {result.mode}")
        print(f"Cases: {result.case_count}")
        print(f"Provider calls: {result.provider_call_count}")
        print(f"Passed: {result.passed_count}")
        print(f"Failed: {result.failed_count}")
        print(f"Contract blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print("Loopback Ollama and approved local read-only DuckDB only; no external provider or upload.")
        return

    if args.command == "analytics-ollama-soak":
        provider = OllamaSemanticIntentProvider(
            endpoint=args.endpoint,
            model=args.model,
            context_tokens=args.context_tokens,
            max_output_tokens=args.max_output_tokens,
        )
        result = run_analytics_ollama_soak(
            args.dataset_manifest,
            args.database,
            args.semantic_state,
            args.relationships,
            args.pack,
            args.approval,
            args.live_authorization,
            args.soak_authorization,
            args.output,
            provider,
            timeout_seconds=args.timeout_seconds,
            execute=args.execute,
            allow_network=args.allow_network,
        )
        print("Local Ollama overnight soak complete")
        print(f"Status: {result.status}")
        print(f"Mode: {result.mode}")
        print(f"Cycles: {result.cycle_count}")
        print(f"Provider calls: {result.provider_call_count}")
        print(f"Contract blockers: {result.blocker_count}")
        print(f"Stop reason: {result.stop_reason or 'none'}")
        print(f"Manifest: {result.manifest_path}")
        print("Runtime is local Ollama plus read-only DuckDB; model-call concurrency is fixed at one.")
        return

    if args.command == "benchmark-convert-sql":
        result = run_benchmark_sql_conversion(args.source, args.dataset, args.output)
        print("Local benchmark SQL conversion complete")
        print(f"Status: {result.status}")
        print(f"Tables: {result.table_count}")
        print(f"Rows: {result.row_count}")
        print(f"Relationship candidates: {result.relationship_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"DuckDB: {result.database_path}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Parquet directory: {result.output_dir / 'parquet'}")
        print("No source file, external database, credential, or remote system was modified.")
        return

    if args.command == "reference-dataset-validate":
        result = run_reference_dataset_validation(
            args.manifest,
            args.output,
            review_path=args.review,
        )
        print("Reference dataset validation complete")
        print(f"Status: {result.status}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Tables: {result.table_count}")
        print(f"Rows: {result.row_count}")
        print(f"Primary keys: {result.primary_key_count}")
        print(f"Relationship candidates: {result.relationship_count}")
        print(f"Approved relationships: {result.approved_relationship_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Relationship review: {result.review_path}")
        print(f"Approved relationships: {result.approved_relationships_path}")
        print("DuckDB profiling was read-only; relationship decisions were not automated.")
        return

    if args.command == "source-onboard":
        result = run_source_onboarding(args.input, args.output, args.config)
        print("Step 3 source onboarding complete")
        print(f"Run ID: {result['run_id']}")
        print(f"Sources inspected: {result['source_count']}")
        print(f"Key candidates: {result['key_candidate_count']}")
        print(f"Relationship candidates: {result['relationship_candidate_count']}")
        print(f"Output: {result['output_dir']}")
        print(f"Config: {result['config_dir']}")
        return

    if args.command == "human-review":
        result = run_human_review(args.step3_dir, args.output, args.config)
        print("Step 3B human review preparation complete")
        print(f"Decisions: {result.decision_count}")
        print(f"Source canonical decisions: {result.source_decision_count}")
        print(f"Key decisions: {result.key_decision_count}")
        print(f"Relationship decisions: {result.relationship_decision_count}")
        print(f"Output: {result.output_dir}")
        print(f"Config: {result.config_dir}")
        return

    if args.command == "apply-approvals":
        counts = validate_approval_template(args.input)
        print("Approval template validation complete")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        for status, count in sorted(counts.items()):
            print(f"{status}: {count}")
        return

    if args.command == "serial-rules":
        if not args.input.exists():
            parser.error(f"Serial rules input file not found: {args.input}")
        result = run_serial_rules(args.input, args.data_dir, args.output, args.config, args.step3_dir)
        print("Step 3C serial reference rule mapping complete")
        print(f"Serial rules: {result.rules_count}")
        print(f"Translation rows: {result.translation_count}")
        print(f"Table mappings: {result.table_mapping_count}")
        print(f"Ref validations: {result.validation_count}")
        print(f"Key enrichments: {result.enrichment_count}")
        print(f"Output: {result.output_dir}")
        print(f"Config: {result.config_dir}")
        return

    if args.command == "serial-aware-review":
        result = run_serial_aware_review(args.step3_dir, args.step3c_dir, args.config, args.output, args.data_dir)
        print("Step 3D serial-aware approval preparation complete")
        print(f"Key review rows: {result.key_review_count}")
        print(f"Relationship review rows: {result.relationship_review_count}")
        print(f"Conflict tables: {result.conflict_count}")
        print(f"Template decisions: {result.template_decision_count}")
        print(f"Output: {result.output_dir}")
        print(f"Config: {result.config_dir}")
        return

    if args.command == "approval-spreadsheet":
        result = run_approval_spreadsheet(args.step3d_dir, args.output, args.config)
        print("Step 3E human approval spreadsheet complete")
        print(f"Decisions: {result.decision_count}")
        print(f"Primary keys: {result.primary_key_count}")
        print(f"Relationships: {result.relationship_count}")
        print(f"Technical line keys: {result.technical_key_count}")
        print(f"Needs business context: {result.needs_context_count}")
        print(f"Conflicts: {result.conflict_count}")
        print(f"XLSX: {result.xlsx_path}")
        print(f"CSV: {result.csv_path}")
        return

    if args.command == "canonical-model":
        result = run_canonical_model_alignment(args.data_dir, args.config, args.output)
        print("Step 3E.1 canonical model alignment complete")
        print(f"Canonical tables: {result.canonical_count}")
        print(f"Complement tables: {result.complement_count}")
        print(f"Product status: {result.product_status}")
        print(f"Organisation status: {result.organisation_status}")
        print(f"Canonical review XLSX: {result.canonical_review_xlsx}")
        print(f"Output: {result.output_dir}")
        print(f"Config: {result.config_dir}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "product-reference-audit":
        result = run_product_reference_audit(args.data_dir, args.output)
        print("Product reference duplicate audit complete")
        print(f"Total products: {result.total_products}")
        print(f"Duplicate groups: {result.duplicate_group_count}")
        print(f"Duplicate occurrences: {result.duplicate_occurrence_count}")
        print(f"Empty part_nr_sku rows: {result.empty_reference_count}")
        print(f"Product status: {result.product_status}")
        print(f"Report: {result.report_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "product-reference-review-spreadsheet":
        result = run_product_reference_review_spreadsheet(args.data_dir, args.output)
        print("Product reference human review spreadsheet complete")
        print(f"Duplicate rows: {result.duplicate_rows}")
        print(f"Empty part_nr_sku rows: {result.empty_rows}")
        print(f"Non-PD pattern rows: {result.non_pd_rows}")
        print(f"Rows requiring human review: {result.rows_requiring_human_review}")
        print(f"XLSX: {result.xlsx_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "product-reference-final-decision":
        result = run_product_reference_final_decision(args.output, args.workbook)
        print("Product reference final decision report complete")
        print(f"Reviewed rows: {result.total_reviewed_rows}")
        print(f"Unresolved rows: {result.unresolved_rows}")
        print(f"Requires more investigation: {result.more_investigation_rows}")
        print(f"Distinct products sharing reference: {result.distinct_same_reference_rows}")
        print(f"part_nr_sku primary key recommended: {result.part_nr_sku_unique_key_recommended}")
        print(f"Report: {result.report_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "product-refnr-reconciliation":
        result = run_product_refnr_reconciliation(args.db_dir, args.data_dir, args.output)
        print("Product ref.nr reconciliation complete")
        print(f"Source: {result.source_path}")
        print(f"Original Product rows: {result.original_rows}")
        print(f"Product_ref.nr rows: {result.product_refnr_rows}")
        print(f"Matched rows: {result.matched_rows}")
        print(f"Corrected ref_nr rows: {result.corrected_refnr_rows}")
        print(f"Conflicts: {result.conflict_rows}")
        print(f"Unmatched original Product rows: {result.unmatched_original_rows}")
        print(f"Unmatched Product_ref.nr rows: {result.unmatched_refnr_rows}")
        print(f"Product final decision finalized: {result.product_finalized}")
        print(f"Workbook: {result.workbook_path}")
        print(f"Report: {result.report_path}")
        print(f"Schema report: {result.schema_report_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "product-refnr-human-review":
        result = run_product_refnr_human_review(args.output, args.workbook)
        print("Product ref.nr human review shortlist complete")
        print(f"Conflicts: {result.conflict_count}")
        print(f"Unmatched original Product rows: {result.unmatched_original_count}")
        print(f"Unmatched Product_ref.nr rows: {result.unmatched_refnr_count}")
        print(f"Duplicate Product_ref.nr review rows: {result.duplicate_count}")
        print(f"Product final decision finalized: {result.product_finalized}")
        print(f"XLSX: {result.shortlist_xlsx}")
        print(f"Markdown: {result.shortlist_md}")
        print(f"Modeling recommendation: {result.modeling_recommendation_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "validate-product-refnr-decisions":
        result = run_validate_product_refnr_decisions(args.output, args.workbook)
        print("Product ref.nr human decisions validation complete")
        print(f"Total decisions read: {result.total_decisions}")
        print(f"Valid decisions: {result.valid_decisions}")
        print(f"Pending decisions: {result.pending_decisions}")
        print(f"Invalid decisions: {result.invalid_decisions}")
        print(f"Missing notes: {result.missing_notes}")
        print(f"Recommended next step: {result.recommended_next_step}")
        print(f"Report: {result.report_path}")
        print(f"Summary CSV: {result.summary_csv_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "product-refnr-final-review-spreadsheet":
        result = run_product_refnr_final_review_spreadsheet(args.output, args.workbook)
        print("Product ref.nr final review spreadsheet complete")
        print(f"Required Review rows: {result.required_review_count}")
        print(f"Missing Notes rows: {result.missing_notes_count}")
        print(f"Inconsistency rows: {result.inconsistency_count}")
        print(f"All Product Exceptions rows: {result.all_exceptions_count}")
        print(f"XLSX: {result.xlsx_path}")
        print(f"CSV: {result.csv_path}")
        print(f"README: {result.readme_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "validate-product-refnr-final-review":
        result = run_validate_product_refnr_final_review(args.output, args.workbook)
        print("Product ref.nr final review validation complete")
        print(f"Total decisions read: {result.total_decisions}")
        print(f"Valid decisions: {result.valid_decisions}")
        print(f"Empty final decisions: {result.empty_decisions}")
        print(f"Pending decisions: {result.pending_decisions}")
        print(f"Invalid final decisions: {result.invalid_decisions}")
        print(f"Missing final notes: {result.missing_notes}")
        print(f"Unresolved inconsistencies: {result.inconsistencies}")
        print(f"Ready for apply: {result.ready_for_apply}")
        print(f"Report: {result.report_path}")
        print(f"Summary CSV: {result.summary_csv_path}")
        if result.validated_workbook_path:
            print(f"Validated workbook: {result.validated_workbook_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "apply-product-refnr-decisions":
        result = run_product_refnr_application(
            args.workbook,
            args.output,
            args.config,
            apply=args.apply,
            replace_existing=args.replace_existing,
        )
        print("Product ref.nr decision application complete")
        print(f"Mode: {'dry-run' if result.dry_run else 'apply'}")
        print(f"Total decisions: {result.total_decisions}")
        print(f"Approved decisions: {result.approved_decisions}")
        print(f"Rejected decisions: {result.rejected_decisions}")
        print(f"Decision digest: {result.decision_digest}")
        print(f"State: {result.state_path}")
        print(f"State changed: {result.state_changed}")
        print(f"Plan CSV: {result.plan_csv_path}")
        print(f"Report: {result.report_path}")
        print("Raw sources, review workbooks, approved_keys.yml, and approved_relationships.yml were not modified.")
        return

    if args.command == "product-materialization-preview":
        result = run_product_materialization(args.data_dir, args.workbook, args.state, args.output)
        print("Product materialization validation complete")
        print(f"Status: {result.status}")
        print(f"Original Product rows: {result.original_rows}")
        print(f"Product_ref.nr rows: {result.product_refnr_rows}")
        print(f"Target preview rows: {result.target_rows}")
        print(f"Excluded identifiers: {result.excluded_identifiers}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Report: {result.report_path}")
        if result.preview_path:
            print(f"Preview CSV: {result.preview_path}")
            print(f"Lineage CSV: {result.lineage_path}")
            print(f"Exclusions CSV: {result.exclusions_path}")
        else:
            print(f"Blockers CSV: {result.blockers_path}")
            print("No Product preview was generated.")
        print("No raw source, approved state, database, import, migration, or external system was modified.")
        return

    if args.command == "product-canonical-promotion-plan":
        result = run_product_canonical_promotion(args.materialization, args.state, args.output)
        print("Product canonical promotion plan validation complete")
        print(f"Status: {result.status}")
        print(f"Candidate canonical Product rows: {result.target_rows}")
        print(f"Excluded identifiers: {result.excluded_identifiers}")
        print(f"Blockers: {result.blocker_count}")
        print(f"Outputs changed: {result.outputs_changed}")
        print(f"Plan: {result.plan_path}")
        print(f"Blockers CSV: {result.blockers_path}")
        print(f"Report: {result.report_path}")
        print("Dry-run only. No canonical state, database, import, migration, or external system was modified.")
        return

    if args.command == "product-refnr-missing-notes-fix":
        result = run_product_refnr_missing_notes_fix(
            args.output,
            args.workbook,
            args.validation_report,
            args.validation_summary,
        )
        print("Product ref.nr missing notes fix spreadsheet complete")
        print(f"Missing notes included: {result.missing_notes_count}")
        print(f"XLSX: {result.xlsx_path}")
        print(f"CSV: {result.csv_path}")
        print(f"README: {result.readme_path}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "schema-overview":
        result = run_schema_overview(args.output)
        print("Main database schema overview complete")
        print(f"Conceptual tables: {result.conceptual_table_count}")
        print(f"Overview: {result.overview_md}")
        print(f"SQL: {result.conceptual_sql}")
        print(f"Relationship map: {result.relationship_map_md}")
        print(f"Pending questions: {result.pending_questions_md}")
        print(f"Summary CSV: {result.summary_csv}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.command == "business-flow-mapping":
        result = run_business_flow_mapping(args.config, args.output)
        print("Business flow mapping complete")
        print(f"Config: {result.config_path}")
        print(f"Mapping: {result.mapping_md}")
        print(f"Relationship candidates CSV: {result.relationship_candidates_csv}")
        print(f"Supplier flow relationships: {result.supplier_flow_count}")
        print(f"Sales/customer flow relationships: {result.sales_flow_count}")
        print(f"Line rules: {result.line_rule_count}")
        print(f"Relationship candidates: {result.relationship_candidate_count}")
        print("No approvals were applied. approved_keys.yml and approved_relationships.yml were not modified.")
        return

    if args.input is None:
        parser.error("--input is required unless a subcommand is used")

    result = run_workflow(args.input, args.output)

    print("AI-Assisted Data Operations Workflow complete")
    print(f"Tables: {', '.join(result.tables)}")
    print(f"DuckDB: {result.database_path}")
    print(f"Metadata: {result.metadata_dir}")
    print(f"Tableau export: {result.tableau_dir}")


if __name__ == "__main__":
    main()
