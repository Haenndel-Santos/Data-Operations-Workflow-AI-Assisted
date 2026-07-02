from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

from .io_utils import slugify
from .source_onboarding import backup_existing, ensure_dir, inspect_sources


CONFIG_DIR = Path("config/data_model")
STEP3_DIR = Path("outputs/originaldatabase_analysis/step3_modeling")
STEP3C_DIR = Path("outputs/originaldatabase_analysis/step3c_serial_reference_rules")
PENDING_REVIEW = "pending_review"
NEEDS_CONTEXT = "needs_business_context"


TRANSLATION_SEEDS = {
    "klant project": ("Customer Project", "customer_project"),
    "verkoop opdracht": ("Sales Order", "sales_order"),
    "inkoopopdrachten": ("Purchase Orders", "purchase_order"),
    "verkoopoffertes": ("Sales Quotations", "sales_quotation"),
    "verkoop factuur": ("Sales Invoice", "sales_invoice"),
    "uitgiftes (pakbonnen)": ("Delivery Notes", "delivery_note"),
    "ontvangsten": ("Goods Reception", "goods_reception"),
    "inkoopfacturen": ("Purchase Invoices", "purchase_invoice"),
    "inkoopaanvragen": ("Purchase RFQ", "purchase_rfq"),
    "verkoopkansen": ("Sales Opportunities", "sales_opportunity"),
    "debiteuren": ("Debtors / Customers", "debtor"),
    "crediteuren": ("Creditors / Suppliers", "creditor"),
    "product": ("Product", "product"),
    "organisaties": ("Organisations", "organisation"),
}

TABLE_NAMESPACE_HINTS = {
    "customerproject": "customer_project",
    "salesopportunity": "sales_opportunity",
    "salesopportunityline": "sales_opportunity",
    "salesquotation": "sales_quotation",
    "salesquotationline": "sales_quotation",
    "salesorder": "sales_order",
    "salesorderline": "sales_order",
    "deliverynote": "delivery_note",
    "deliverynoteline": "delivery_note",
    "salesinvoice": "sales_invoice",
    "salesinvoiceline": "sales_invoice",
    "purchasequotation": "purchase_rfq",
    "purchasequotationline": "purchase_rfq",
    "purchaseorder": "purchase_order",
    "purchaseorderline": "purchase_order",
    "goodsreception": "goods_reception",
    "goodsreceptionline": "goods_reception",
    "purchaseinvoice": "purchase_invoice",
    "purchaseinvoiceline": "purchase_invoice",
    "debtor": "debtor",
    "creditor": "creditor",
    "product": "product",
    "organisation": "organisation",
}


@dataclass(frozen=True)
class SerialRule:
    module_original: str
    module_normalized: str
    module_english: str
    company: str
    format_original: str
    prefix: str
    year_token: str
    sequence_token: str
    expected_regex: str
    current_ref_counter: str
    generate_on: str
    document_setting: str
    semantic_namespace: str
    semantic_ref_name: str
    status: str


@dataclass(frozen=True)
class SerialRulesResult:
    rules_count: int
    translation_count: int
    table_mapping_count: int
    validation_count: int
    enrichment_count: int
    output_dir: Path
    config_dir: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_yaml(path: Path, payload: dict[str, Any], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str, current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    path.write_text(text, encoding="utf-8")


def normalize_module(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def parse_serial_format(format_value: Any) -> dict[str, str]:
    if pd.isna(format_value):
        return {
            "format_original": "",
            "prefix": "",
            "year_token": "",
            "sequence_token": "",
            "expected_regex": "",
        }
    format_original = str(format_value).strip()
    first_token = len(format_original)
    for idx, char in enumerate(format_original):
        if char in {"Y", "M", "9"}:
            first_token = idx
            break
    prefix = format_original[:first_token]
    year_token = "YY" if "YY" in format_original else ""
    sequence_token = "".join(char for char in format_original if char == "9")
    regex_parts: list[str] = []
    idx = 0
    while idx < len(format_original):
        char = format_original[idx]
        if format_original.startswith("YY", idx):
            regex_parts.append(r"[0-9]{2}")
            idx += 2
            continue
        if format_original.startswith("MM", idx):
            regex_parts.append(r"[0-9]{2}")
            idx += 2
            continue
        if char == "9":
            count = 1
            while idx + count < len(format_original) and format_original[idx + count] == "9":
                count += 1
            regex_parts.append(rf"[0-9]{{{count}}}")
            idx += count
            continue
        regex_parts.append(re.escape(char))
        idx += 1
    return {
        "format_original": format_original,
        "prefix": prefix,
        "year_token": year_token,
        "sequence_token": sequence_token,
        "expected_regex": f"^{''.join(regex_parts)}$" if format_original else "",
    }


def semantic_ref_name(prefix: str) -> str:
    clean = slugify(prefix).replace("_", "")
    return f"{clean}_ref_nr" if clean else "needs_business_context_ref_nr"


def load_serials(serials_path: Path) -> pd.DataFrame:
    workbook = pd.ExcelFile(serials_path)
    sheet_name = workbook.sheet_names[0]
    return pd.read_excel(serials_path, sheet_name=sheet_name)


def build_translation_map(modules: list[str]) -> list[dict[str, str]]:
    rows = []
    for module in sorted(set(normalize_module(module) for module in modules if normalize_module(module))):
        english, namespace = TRANSLATION_SEEDS.get(module, ("needs_business_context", NEEDS_CONTEXT))
        rows.append(
            {
                "module_original_normalized": module,
                "module_english": english,
                "semantic_namespace": namespace,
                "status": PENDING_REVIEW if namespace != NEEDS_CONTEXT else NEEDS_CONTEXT,
            }
        )
    return rows


def build_rules(serials_df: pd.DataFrame, translation_rows: list[dict[str, str]]) -> list[SerialRule]:
    translation_lookup = {row["module_original_normalized"]: row for row in translation_rows}
    rules: list[SerialRule] = []
    for _, row in serials_df.iterrows():
        module_original = "" if pd.isna(row.get("Module")) else str(row.get("Module")).strip()
        module_normalized = normalize_module(module_original)
        parsed = parse_serial_format(row.get("Format"))
        if not module_normalized and not parsed["format_original"]:
            continue
        translation = translation_lookup.get(module_normalized, {})
        semantic_namespace = translation.get("semantic_namespace", NEEDS_CONTEXT)
        prefix = parsed["prefix"]
        rules.append(
            SerialRule(
                module_original=module_original,
                module_normalized=module_normalized,
                module_english=translation.get("module_english", "needs_business_context"),
                company="" if pd.isna(row.get("First linked company")) else str(row.get("First linked company")).strip(),
                format_original=parsed["format_original"],
                prefix=prefix,
                year_token=parsed["year_token"],
                sequence_token=parsed["sequence_token"],
                expected_regex=parsed["expected_regex"],
                current_ref_counter="" if pd.isna(row.get("Ref. nr.")) else str(row.get("Ref. nr.")).strip(),
                generate_on="" if pd.isna(row.get("Generate on")) else str(row.get("Generate on")).strip(),
                document_setting="" if pd.isna(row.get("document sett.")) else str(row.get("document sett.")).strip(),
                semantic_namespace=semantic_namespace,
                semantic_ref_name=semantic_ref_name(prefix),
                status=PENDING_REVIEW if semantic_namespace != NEEDS_CONTEXT else NEEDS_CONTEXT,
            )
        )
    return rules


def rule_to_dict(rule: SerialRule) -> dict[str, Any]:
    return {
        "module_original": rule.module_original,
        "module_normalized": rule.module_normalized,
        "module_english": rule.module_english,
        "company": rule.company,
        "format_original": rule.format_original,
        "prefix": rule.prefix,
        "year_token": rule.year_token,
        "sequence_token": rule.sequence_token,
        "expected_regex": rule.expected_regex,
        "current_ref_counter": rule.current_ref_counter,
        "generate_on": rule.generate_on,
        "document_setting": rule.document_setting,
        "semantic_namespace": rule.semantic_namespace,
        "semantic_ref_name": rule.semantic_ref_name,
        "status": rule.status,
    }


def namespace_rule_lookup(rules: list[SerialRule]) -> dict[str, SerialRule]:
    lookup: dict[str, SerialRule] = {}
    for rule in rules:
        if rule.semantic_namespace == NEEDS_CONTEXT or not rule.prefix:
            continue
        lookup.setdefault(rule.semantic_namespace, rule)
    return lookup


def canonical_table_name(table_name: str) -> str:
    text = slugify(table_name)
    if "_export_" in text:
        text = text.split("_export_")[-1]
    return text.replace("_3", "").replace("2_", "_").replace("3_", "_")


def infer_namespace_for_table(table_name: str) -> str:
    canonical = canonical_table_name(table_name)
    for hint, namespace in sorted(TABLE_NAMESPACE_HINTS.items(), key=lambda item: len(item[0]), reverse=True):
        if hint in canonical:
            return namespace
    return NEEDS_CONTEXT


def build_semantic_ref_mapping(observations: list[Any], rules: list[SerialRule]) -> dict[str, dict[str, str]]:
    rule_lookup = namespace_rule_lookup(rules)
    mapping: dict[str, dict[str, str]] = {}
    for obs in observations:
        if "ref_nr" not in obs.df.columns:
            continue
        namespace = infer_namespace_for_table(obs.table_name)
        rule = rule_lookup.get(namespace)
        mapping[obs.table_name] = {
            "expected_prefix": rule.prefix if rule else "",
            "semantic_namespace": namespace,
            "semantic_ref_name": rule.semantic_ref_name if rule else "needs_business_context_ref_nr",
            "raw_column": "ref_nr",
            "status": PENDING_REVIEW if rule else NEEDS_CONTEXT,
        }
    return mapping


def detected_prefix(value: Any) -> str:
    if pd.isna(value):
        return ""
    match = re.match(r"^([A-Za-z.]+)", str(value).strip())
    return match.group(1).replace(".", "") if match else ""


def validate_ref_pattern(df: pd.DataFrame, ref_column: str, expected_prefix: str, expected_regex: str) -> dict[str, Any]:
    working = pd.DataFrame({"ref_value": df[ref_column].astype("string")})
    working["detected_prefix"] = working["ref_value"].map(detected_prefix)
    con = duckdb.connect()
    con.register("refs", working)
    total_rows, non_null_count, prefix_match_count, regex_match_count, invalid_count = con.execute(
        """
        select
          count(*) as total_rows,
          count(*) filter (where ref_value is not null and ref_value != '') as non_null_count,
          count(*) filter (where ref_value is not null and ref_value != '' and detected_prefix = ?) as prefix_match_count,
          count(*) filter (where ref_value is not null and ref_value != '' and regexp_matches(ref_value, ?)) as regex_match_count,
          count(*) filter (where ref_value is not null and ref_value != '' and not regexp_matches(ref_value, ?)) as invalid_count
        from refs
        """,
        [expected_prefix, expected_regex or r"^$", expected_regex or r"^$"],
    ).fetchone()
    prefixes = con.execute(
        """
        select detected_prefix, count(*) as row_count
        from refs
        where detected_prefix != ''
        group by detected_prefix
        order by row_count desc, detected_prefix
        """
    ).fetchall()
    prefix_match_rate = round(prefix_match_count / max(non_null_count, 1) * 100, 2)
    regex_match_rate = round(regex_match_count / max(non_null_count, 1) * 100, 2)
    return {
        "total_rows": int(total_rows),
        "non_null_ref_count": int(non_null_count),
        "detected_prefixes": "; ".join(f"{prefix}:{count}" for prefix, count in prefixes),
        "prefix_match_rate": prefix_match_rate,
        "regex_match_rate": regex_match_rate,
        "invalid_ref_count": int(invalid_count),
        "multiple_prefixes_detected": len(prefixes) > 1,
    }


def confidence_from_validation(prefix_match_rate: float, regex_match_rate: float, namespace: str) -> str:
    if namespace == NEEDS_CONTEXT:
        return NEEDS_CONTEXT
    if prefix_match_rate == 100.0 and regex_match_rate >= 99.0:
        return "high"
    if prefix_match_rate >= 95.0 and regex_match_rate >= 95.0:
        return "medium"
    return NEEDS_CONTEXT


def build_ref_validation_rows(observations: list[Any], mapping: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obs in observations:
        ref_columns = [column for column in obs.df.columns if column == "ref_nr"]
        for ref_column in ref_columns:
            map_row = mapping.get(obs.table_name, {})
            expected_prefix = map_row.get("expected_prefix", "")
            expected_regex = ""
            semantic_namespace = map_row.get("semantic_namespace", NEEDS_CONTEXT)
            # expected_regex is resolved later from semantic namespace/prefix by caller if available.
            rows.append(
                {
                    "table_name": obs.table_name,
                    "source_file": obs.source_file,
                    "raw_ref_column": ref_column,
                    "expected_prefix": expected_prefix,
                    "expected_regex": expected_regex,
                    "semantic_namespace": semantic_namespace,
                    "semantic_ref_name": map_row.get("semantic_ref_name", "needs_business_context_ref_nr"),
                    "df": obs.df,
                }
            )
    return rows


def enrich_validation_rows(rows: list[dict[str, Any]], rules: list[SerialRule]) -> list[dict[str, Any]]:
    rule_lookup = namespace_rule_lookup(rules)
    final_rows: list[dict[str, Any]] = []
    for row in rows:
        rule = rule_lookup.get(row["semantic_namespace"])
        expected_regex = rule.expected_regex if rule else ""
        expected_prefix = rule.prefix if rule else row["expected_prefix"]
        validation = validate_ref_pattern(row["df"], row["raw_ref_column"], expected_prefix, expected_regex)
        confidence = confidence_from_validation(
            validation["prefix_match_rate"],
            validation["regex_match_rate"],
            row["semantic_namespace"],
        )
        final_rows.append(
            {
                "table_name": row["table_name"],
                "source_file": row["source_file"],
                "raw_ref_column": row["raw_ref_column"],
                "expected_prefix": expected_prefix,
                "detected_prefixes": validation["detected_prefixes"],
                "expected_regex": expected_regex,
                "total_rows": validation["total_rows"],
                "non_null_ref_count": validation["non_null_ref_count"],
                "prefix_match_rate": validation["prefix_match_rate"],
                "regex_match_rate": validation["regex_match_rate"],
                "invalid_ref_count": validation["invalid_ref_count"],
                "multiple_prefixes_detected": validation["multiple_prefixes_detected"],
                "confidence_level": confidence,
                "status": PENDING_REVIEW if confidence in {"high", "medium"} else NEEDS_CONTEXT,
                "notes": "Serial pattern validation only. No key or relationship approval implied.",
            }
        )
    return final_rows


def read_key_candidates(step3_dir: Path) -> list[dict[str, str]]:
    path = step3_dir / "key_candidates.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_key_enrichment_rows(key_rows: list[dict[str, str]], validation_rows: list[dict[str, Any]], mapping: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    validation_lookup = {row["table_name"]: row for row in validation_rows}
    rows: list[dict[str, Any]] = []
    for key in key_rows:
        if key.get("candidate_key") != "ref_nr":
            continue
        validation = validation_lookup.get(key["table_name"])
        map_row = mapping.get(key["table_name"], {})
        if not validation:
            continue
        new_confidence = key["confidence_level"]
        if (
            key["non_null_rate"] == "100.0"
            and key["uniqueness_rate"] == "100.0"
            and validation["prefix_match_rate"] == 100.0
            and validation["regex_match_rate"] >= 99.0
            and map_row.get("semantic_namespace") != NEEDS_CONTEXT
        ):
            new_confidence = "high"
        rows.append(
            {
                "table_name": key["table_name"],
                "candidate_key": key["candidate_key"],
                "previous_confidence_level": key["confidence_level"],
                "non_null_rate": key["non_null_rate"],
                "uniqueness_rate": key["uniqueness_rate"],
                "expected_prefix": validation["expected_prefix"],
                "prefix_match_rate": validation["prefix_match_rate"],
                "regex_match_rate": validation["regex_match_rate"],
                "semantic_namespace": map_row.get("semantic_namespace", NEEDS_CONTEXT),
                "semantic_ref_name": map_row.get("semantic_ref_name", "needs_business_context_ref_nr"),
                "new_confidence_suggestion": new_confidence,
                "status": PENDING_REVIEW if new_confidence in {"high", "medium"} else NEEDS_CONTEXT,
                "notes": "Serial evidence enrichment only. Human approval is still required.",
            }
        )
    return rows


def render_report(
    rules: list[SerialRule],
    translation_rows: list[dict[str, str]],
    validation_rows: list[dict[str, Any]],
    mapping: dict[str, dict[str, str]],
) -> str:
    matched = [row for row in validation_rows if row["status"] == PENDING_REVIEW and row["confidence_level"] in {"high", "medium"}]
    conflicts = [row for row in validation_rows if row["status"] == NEEDS_CONTEXT or row["prefix_match_rate"] < 95 or row["regex_match_rate"] < 95]
    multiple_prefix = [row for row in validation_rows if str(row["multiple_prefixes_detected"]) == "True" or row["multiple_prefixes_detected"] is True]
    mapped_namespaces = {row["semantic_namespace"] for row in mapping.values()}
    rules_without_tables = [rule for rule in rules if rule.semantic_namespace not in mapped_namespaces and rule.semantic_namespace != NEEDS_CONTEXT]
    tables_without_rule = [table for table, row in mapping.items() if row["semantic_namespace"] == NEEDS_CONTEXT or not row["expected_prefix"]]
    lines = [
        "# Step 3C Ref Pattern Validation Report",
        "",
        "This report imports serial reference rules and validates `ref_nr` patterns. It does not approve keys or relationships.",
        "",
        f"- Serial rules imported: {len(rules)}",
        f"- Translation rows generated: {len(translation_rows)}",
        f"- Tables with ref validation: {len(validation_rows)}",
        f"- Strong/medium pattern matches: {len(matched)}",
        f"- Conflicts or context-needed rows: {len(conflicts)}",
        "",
        "## Dutch -> English -> Semantic Namespace",
    ]
    for row in translation_rows:
        lines.append(
            f"- {row['module_original_normalized']} -> {row['module_english']} -> {row['semantic_namespace']} ({row['status']})"
        )
    lines.extend(["", "## Tables Matching Expected Prefix/Regex"])
    for row in matched:
        lines.append(
            f"- {row['table_name']}: expected_prefix={row['expected_prefix']}, prefix_match={row['prefix_match_rate']}%, regex_match={row['regex_match_rate']}%, status={row['status']}"
        )
    lines.extend(["", "## Tables With Prefix/Regex Conflict Or Missing Context"])
    for row in conflicts:
        lines.append(
            f"- {row['table_name']}: expected_prefix={row['expected_prefix']}, detected={row['detected_prefixes']}, prefix_match={row['prefix_match_rate']}%, regex_match={row['regex_match_rate']}%, status={row['status']}"
        )
    lines.extend(["", "## Tables With Multiple Prefixes"])
    for row in multiple_prefix:
        lines.append(f"- {row['table_name']}: {row['detected_prefixes']}")
    lines.extend(["", "## Rules Without Matching Table"])
    for rule in rules_without_tables:
        lines.append(f"- {rule.module_original} ({rule.semantic_namespace}, prefix={rule.prefix}, format={rule.format_original})")
    lines.extend(["", "## Tables With `ref_nr` But No Identified Serial Rule"])
    for table in tables_without_rule:
        lines.append(f"- {table}")
    lines.extend(
        [
            "",
            "## Questions For Human Review",
            "- Which `needs_business_context` module translations should be mapped to a business namespace?",
            "- Should line tables inherit the header namespace and prefix rule from their document header?",
            "- Are tables with multiple prefixes valid mixed-reference tables or should they be split/cleaned in a later metadata layer?",
            "- Which semantic ref names should be used in future SQL views?",
        ]
    )
    return "\n".join(lines)


def run_serial_rules(
    serials_path: Path,
    data_dir: Path | None = None,
    output_dir: Path = STEP3C_DIR,
    config_dir: Path = CONFIG_DIR,
    step3_dir: Path = STEP3_DIR,
) -> SerialRulesResult:
    current_run_id = run_id()
    data_dir = data_dir or serials_path.parent
    serials_df = load_serials(serials_path)
    translation_rows = build_translation_map(serials_df["Module"].tolist())
    rules = build_rules(serials_df, translation_rows)
    observations = inspect_sources(data_dir)
    mapping = build_semantic_ref_mapping(observations, rules)
    validation_input_rows = build_ref_validation_rows(observations, mapping)
    validation_rows = enrich_validation_rows(validation_input_rows, rules)
    key_rows = read_key_candidates(step3_dir)
    enrichment_rows = build_key_enrichment_rows(key_rows, validation_rows, mapping)

    write_yaml(
        config_dir / "reference_translation_map.yml",
        {"generated_at": now_iso(), "translations": translation_rows},
        current_run_id,
    )
    write_yaml(
        config_dir / "reference_serial_rules.yml",
        {"generated_at": now_iso(), "rules": [rule_to_dict(rule) for rule in rules]},
        current_run_id,
    )
    write_yaml(
        config_dir / "semantic_ref_mapping.yml",
        {"generated_at": now_iso(), "table_ref_mapping": mapping},
        current_run_id,
    )

    validation_fields = [
        "table_name",
        "source_file",
        "raw_ref_column",
        "expected_prefix",
        "detected_prefixes",
        "expected_regex",
        "total_rows",
        "non_null_ref_count",
        "prefix_match_rate",
        "regex_match_rate",
        "invalid_ref_count",
        "multiple_prefixes_detected",
        "confidence_level",
        "status",
        "notes",
    ]
    enrichment_fields = [
        "table_name",
        "candidate_key",
        "previous_confidence_level",
        "non_null_rate",
        "uniqueness_rate",
        "expected_prefix",
        "prefix_match_rate",
        "regex_match_rate",
        "semantic_namespace",
        "semantic_ref_name",
        "new_confidence_suggestion",
        "status",
        "notes",
    ]
    write_csv_rows(output_dir / "ref_pattern_validation.csv", validation_rows, validation_fields, current_run_id)
    write_csv_rows(output_dir / "key_candidate_serial_enrichment.csv", enrichment_rows, enrichment_fields, current_run_id)
    write_text(output_dir / "ref_pattern_validation_report.md", render_report(rules, translation_rows, validation_rows, mapping), current_run_id)

    return SerialRulesResult(
        rules_count=len(rules),
        translation_count=len(translation_rows),
        table_mapping_count=len(mapping),
        validation_count=len(validation_rows),
        enrichment_count=len(enrichment_rows),
        output_dir=output_dir,
        config_dir=config_dir,
    )
