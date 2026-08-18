"""On-disk invariants of the governed cleaning engine (D2).

Every test drives the real propose -> authorize -> apply route over small
Parquet fixtures in a temporary directory. Nothing here calls a model or the
network. The D2 checklist in docs/governed-cleaning-engine.md numbers the
invariants these tests reference.
"""

from __future__ import annotations

import datetime as dt
import shutil

import pandas as pd
import pytest
import yaml

from data_ops_lab.cleaner import clean_dataframe
from data_ops_lab.governed_cleaning import is_aware_iso_timestamp, sha256_of
from data_ops_lab.governed_cleaning_engine import (
    APPLICATION_MANIFEST_NAME,
    APPLICATION_PLAN_NAME,
    AUTHORITIES_NAME,
    AUTHORIZATION_MANIFEST_NAME,
    BLOCKERS_NAME,
    CANDIDATES_NAME,
    LINEAGE_NAME,
    PROPOSAL_MANIFEST_NAME,
    REVIEW_TEMPLATE_NAME,
    ENGINE_VERSION,
    _order_steps,
    _plan_hash,
    _proposal_hash,
    logical_content_sha256,
    run_governed_cleaning_apply,
    run_governed_cleaning_authorize,
    run_governed_cleaning_propose,
)

NOW = "2026-08-18T17:00:00Z"
SAMPLES = "samples/raw"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


def write_parquet(directory, **tables):
    directory.mkdir(parents=True, exist_ok=True)
    for name, columns in tables.items():
        pd.DataFrame(columns).to_parquet(directory / f"{name}.parquet", index=False)
    return directory


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path, payload):
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def blocker_types(directory):
    text = (directory / BLOCKERS_NAME).read_text(encoding="utf-8").splitlines()[1:]
    return {line.split(",")[1] for line in text if line}


def dataset(tmp_path):
    """orders: a date column, a numeric-as-text column with one bad value, a
    padded code, and a notes column with sentinels."""
    return write_parquet(
        tmp_path / "src",
        orders={
            "order_id": pd.Series(["O1", "O2", "O3", "O4"], dtype=object),
            "order_date": pd.Series(["2025-01-05", "2025-01-07", "2025-02-11", "2025-02-15"], dtype=object),
            "amount": pd.Series(["100", "2,500", "300.5", "ABC"], dtype=object),
            "customer_code": pd.Series([" C1 ", "C2", " C3", "C4 "], dtype=object),
            "notes": pd.Series(["ok", "N/A", "-", "fine"], dtype=object),
        },
    )


def full_review(proposal_dir, path, decision="approved", reviewer="owner", overrides=None):
    template = read_yaml(proposal_dir / REVIEW_TEMPLATE_NAME)
    template["reviewer"] = reviewer
    for entry in template["decisions"]:
        entry["decision"] = decision
        entry["reviewed_at"] = NOW
        if overrides and entry["candidate_id"] in overrides:
            entry.update(overrides[entry["candidate_id"]])
    write_yaml(path, template)
    return path


def policy_file(path, operations=None):
    write_yaml(
        path,
        {
            "policy_version": 1,
            "dataset_id": "orders_dataset",
            "configured_by": "owner",
            "configured_at": "2026-08-18T14:00:00Z",
            "operations": operations
            if operations is not None
            else [
                {"operation": "trim_whitespace", "table": "orders", "columns": ["customer_code"]},
                {"operation": "normalize_blank_sentinel", "table": "orders", "columns": ["notes"], "parameters": {"sentinels": ["N/A"]}},
            ],
        },
    )
    return path


def full_cycle(tmp_path, *, with_policy=True):
    src = dataset(tmp_path)
    proposal = run_governed_cleaning_propose(src, tmp_path / "proposal")
    assert proposal.status == "ready_for_review", read_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME)
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    policy = policy_file(tmp_path / "policy.yml") if with_policy else None
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review, policy_path=policy)
    assert auth.status == "authorized", blocker_types(tmp_path / "auth")
    return src, tmp_path / "proposal", tmp_path / "auth"


# --------------------------------------------------------------------------- #
# PROPOSE
# --------------------------------------------------------------------------- #


def test_propose_never_changes_source_data(tmp_path):
    """D2-1. Proposal is read-only on the source."""
    src = dataset(tmp_path)
    before = {p.name: p.read_bytes() for p in src.glob("*.parquet")}
    result = run_governed_cleaning_propose(src, tmp_path / "proposal")
    assert result.status == "ready_for_review"
    assert {p.name: p.read_bytes() for p in src.glob("*.parquet")} == before


def test_propose_derives_source_hash_from_actual_files_and_bundle_is_self_bound(tmp_path):
    src = dataset(tmp_path)
    result = run_governed_cleaning_propose(src, tmp_path / "proposal")
    manifest = read_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME)
    expected = sha256_of([{"path": "orders.parquet", "sha256": __import__("data_ops_lab.contracts.hashing", fromlist=["file_sha256"]).file_sha256(src / "orders.parquet")}])
    assert result.source_sha256 == manifest["source_sha256"] == expected
    candidates = read_yaml(tmp_path / "proposal" / CANDIDATES_NAME)
    assert candidates["proposal_sha256"] == manifest["proposal_sha256"]
    # governed candidates are pending_review; nothing is approved
    assert {c["review_state"] for c in candidates["candidates"]} == {"pending_review"}
    ids = {c["candidate_id"] for c in candidates["candidates"]}
    assert ids == {"orders.order_date.parse_date", "orders.amount.parse_number"}
    ops = {(s["operation"], s["column"]) for s in manifest["configured"]}
    assert ops == {("trim_whitespace", "customer_code"), ("normalize_blank_sentinel", "notes")}
    assert manifest["automatic"] == []  # column names are already normalized


def test_propose_records_evidence_and_computed_confidence_for_the_ninety_percent_case(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    candidates = {c["candidate_id"]: c for c in read_yaml(tmp_path / "proposal" / CANDIDATES_NAME)["candidates"]}
    amount = candidates["orders.amount.parse_number"]
    assert amount["evidence"]["success_count"] == 3 and amount["evidence"]["failure_count"] == 1
    assert amount["computed_confidence"] == 0.75


def test_propose_refuses_when_source_manifest_disagrees_with_actual_parquet(tmp_path):
    """Manifest says A, files say B -> blocker, zero candidates published."""
    src = dataset(tmp_path)
    write_yaml(tmp_path / "source_manifest.yml", {"files": [{"path": "orders.parquet", "sha256": "0" * 64}]})
    result = run_governed_cleaning_propose(src, tmp_path / "proposal", source_manifest_path=tmp_path / "source_manifest.yml")
    assert result.status == "blocked" and result.candidate_count == 0
    assert "source_manifest_hash_mismatch" in blocker_types(tmp_path / "proposal")
    assert read_yaml(tmp_path / "proposal" / CANDIDATES_NAME)["candidates"] == []


def test_propose_refuses_when_source_manifest_lists_a_different_inventory(tmp_path):
    src = dataset(tmp_path)
    write_yaml(tmp_path / "source_manifest.yml", {"files": [{"path": "other.parquet", "sha256": "0" * 64}]})
    result = run_governed_cleaning_propose(src, tmp_path / "proposal", source_manifest_path=tmp_path / "source_manifest.yml")
    assert result.status == "blocked"
    assert "source_manifest_inventory_mismatch" in blocker_types(tmp_path / "proposal")


def test_propose_accepts_a_manifest_that_matches_and_still_derives_the_hash_from_files(tmp_path):
    from data_ops_lab.contracts.hashing import file_sha256
    src = dataset(tmp_path)
    write_yaml(tmp_path / "source_manifest.yml", {"files": [{"path": "orders.parquet", "sha256": file_sha256(src / "orders.parquet")}]})
    result = run_governed_cleaning_propose(src, tmp_path / "proposal", source_manifest_path=tmp_path / "source_manifest.yml")
    assert result.status == "ready_for_review"


def test_propose_proposes_automatic_rename_only_when_column_is_not_normalized(tmp_path):
    src = write_parquet(tmp_path / "src", t={"Order Date": pd.Series(["2025-01-05"], dtype=object), "ok_col": pd.Series(["x"], dtype=object)})
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    manifest = read_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME)
    assert manifest["automatic"] == [{"operation": "normalize_column_name", "table": "t", "column": "Order Date", "target": "order_date"}]
    # a non-identifier column receives only the rename in this cycle
    assert all(c["column"] != "Order Date" for c in read_yaml(tmp_path / "proposal" / CANDIDATES_NAME)["candidates"])


def test_raw_column_name_is_proposed_authorized_and_renamed_end_to_end(tmp_path):
    """Blocker 1: the case the proposer detects must be authorizable and
    applicable. "Order Date" -> AutomaticAuthority -> "order_date" in output;
    source unchanged; lineage names the operation table."""
    src = write_parquet(tmp_path / "src", t={"Order Date": pd.Series(["2025-01-05", "2025-02-11"], dtype=object), "amount": pd.Series(["1", "2"], dtype=object)})
    before = (src / "t.parquet").read_bytes()
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    manifest = read_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME)
    assert [(s["column"], s["target"]) for s in manifest["automatic"]] == [("Order Date", "order_date")]
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml", decision="rejected")  # keep it to the rename
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "authorized", blocker_types(tmp_path / "auth")
    records = read_yaml(tmp_path / "auth" / AUTHORITIES_NAME)["authorities"]
    assert [(r["authority_kind"], r["column"], r["operation"]) for r in records] == [("operation_table", "Order Date", "normalize_column_name")]
    result = run_governed_cleaning_apply(tmp_path / "auth", src, tmp_path / "out")
    assert result.status == "applied" and result.step_count == 1
    out = pd.read_parquet(tmp_path / "out" / "parquet" / "t.parquet")
    assert "order_date" in out.columns and "Order Date" not in out.columns
    assert out["order_date"].tolist() == ["2025-01-05", "2025-02-11"]     # values untouched by a rename
    assert (src / "t.parquet").read_bytes() == before
    lineage = read_yaml(tmp_path / "out" / LINEAGE_NAME)["lineage"]
    assert [(r["authority_kind"], r["column"], r["operation"], r["rows_changed"]) for r in lineage] == [("operation_table", "Order Date", "normalize_column_name", 0)]


def test_two_raw_names_that_normalize_to_the_same_target_are_refused_at_authorize(tmp_path):
    src = write_parquet(tmp_path / "src", t={"Order Date": pd.Series(["x"], dtype=object), "order date": pd.Series(["y"], dtype=object)})
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth")
    assert auth.status == "blocked" and "rename_target_collision" in blocker_types(tmp_path / "auth")


def test_propose_refuses_to_overwrite_an_existing_output_directory(tmp_path):
    src = dataset(tmp_path)
    (tmp_path / "proposal").mkdir()
    result = run_governed_cleaning_propose(src, tmp_path / "proposal")
    assert result.status == "blocked" and result.blocker_count == 1


# --------------------------------------------------------------------------- #
# AUTHORIZE
# --------------------------------------------------------------------------- #


def test_missing_disposition_yields_incomplete_not_a_blocker_and_no_apply_ready_bundle(tmp_path):
    """D2-4. Everything proposed needs an explicit disposition."""
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    payload = read_yaml(review)
    payload["decisions"] = payload["decisions"][:1]  # drop one
    write_yaml(review, payload)
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "authorization_incomplete" and auth.incomplete_count == 1 and auth.blocker_count == 0
    manifest = read_yaml(tmp_path / "auth" / AUTHORIZATION_MANIFEST_NAME)
    assert manifest["application_plan_sha256"] == "" and read_yaml(tmp_path / "auth" / APPLICATION_PLAN_NAME)["steps"] == []
    assert {d["disposition"] for d in manifest["dispositions"] if d["governance_class"] == "governed"} == {"approved", "missing"}
    apply = run_governed_cleaning_apply(tmp_path / "auth", src, tmp_path / "out")
    assert apply.status == "blocked" and "authorization_not_ready" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_rejected_is_a_valid_disposition_with_zero_authority(tmp_path):
    """D2-3."""
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml", decision="rejected")
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "authorized" and auth.authority_count == 0
    manifest = read_yaml(tmp_path / "auth" / AUTHORIZATION_MANIFEST_NAME)
    assert {d["disposition"] for d in manifest["dispositions"] if d["governance_class"] == "governed"} == {"rejected"}
    # apply with an authorized-but-empty plan changes nothing and writes lineage-free output
    apply = run_governed_cleaning_apply(tmp_path / "auth", src, tmp_path / "out")
    assert apply.status == "applied" and apply.step_count == 0
    assert read_yaml(tmp_path / "out" / LINEAGE_NAME)["lineage"] == []
    assert pd.read_parquet(tmp_path / "out" / "parquet" / "orders.parquet")["amount"].tolist() == ["100", "2,500", "300.5", "ABC"]


def test_unknown_or_extra_review_decision_is_a_blocker(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    payload = read_yaml(review)
    payload["decisions"].append({"candidate_id": "orders.ghost.parse_number", "candidate_sha256": "0" * 64, "decision": "approved", "reviewed_at": NOW})
    write_yaml(review, payload)
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "blocked" and "unknown_review_candidate" in blocker_types(tmp_path / "auth")


def test_review_for_another_proposal_over_the_same_source_is_refused(tmp_path):
    """Blocker 5: two proposals over unchanged data carry identical candidate
    hashes and are still different artifacts; the review authorizes the exact
    proposal it was written against."""
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal_a")
    review_a = full_review(tmp_path / "proposal_a", tmp_path / "review_a.yml")
    run_governed_cleaning_propose(src, tmp_path / "proposal_b")
    a, b = read_yaml(tmp_path / "proposal_a" / PROPOSAL_MANIFEST_NAME), read_yaml(tmp_path / "proposal_b" / PROPOSAL_MANIFEST_NAME)
    assert a["source_sha256"] == b["source_sha256"] and a["governed"] == b["governed"]  # same candidates
    assert a["proposal_sha256"] != b["proposal_sha256"]                                   # different artifacts
    auth = run_governed_cleaning_authorize(tmp_path / "proposal_b", src, tmp_path / "auth", review_path=review_a)
    assert auth.status == "blocked" and "review_proposal_hash_mismatch" in blocker_types(tmp_path / "auth")
    assert read_yaml(tmp_path / "auth" / APPLICATION_PLAN_NAME)["steps"] == []


def test_hash_mismatched_decision_is_a_blocker(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    payload = read_yaml(review)
    payload["decisions"][0]["candidate_sha256"] = "f" * 64
    write_yaml(review, payload)
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "blocked" and "decision_hash_mismatch" in blocker_types(tmp_path / "auth")


def test_proposal_from_another_engine_version_is_refused_by_authorize(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    manifest = read_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME)
    manifest["engine_version"] = ENGINE_VERSION + 1
    manifest["proposal_sha256"] = _proposal_hash(manifest)  # keep the artifact self-consistent
    write_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME, manifest)
    candidates = read_yaml(tmp_path / "proposal" / CANDIDATES_NAME)
    candidates["proposal_sha256"] = manifest["proposal_sha256"]
    write_yaml(tmp_path / "proposal" / CANDIDATES_NAME, candidates)
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "blocked" and "unsupported_engine_version" in blocker_types(tmp_path / "auth")


def test_authorization_from_another_engine_version_is_refused_by_apply(tmp_path):
    src, _, auth_dir = full_cycle(tmp_path)
    manifest = read_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME)
    manifest["engine_version"] = ENGINE_VERSION + 1
    write_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME, manifest)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "unsupported_engine_version" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_proposal_artifact_changed_after_review_fails_authorization(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    manifest = read_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME)
    manifest["governed"] = manifest["governed"][:1]
    write_yaml(tmp_path / "proposal" / PROPOSAL_MANIFEST_NAME, manifest)
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "blocked" and "proposal_hash_mismatch" in blocker_types(tmp_path / "auth")


def test_source_changed_after_propose_fails_authorization(tmp_path):
    """D2-7."""
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    frame = pd.read_parquet(src / "orders.parquet")
    frame.loc[0, "amount"] = "101"
    frame.to_parquet(src / "orders.parquet", index=False)
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "blocked" and "source_changed_since_proposal" in blocker_types(tmp_path / "auth")


def test_configured_operation_outside_exact_policy_scope_gets_no_authority(tmp_path):
    """D2-14/15: configured needs the policy; a policy that does not name the
    scope grants nothing, and that is a disposition, not a blocker."""
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    policy = policy_file(tmp_path / "policy.yml", operations=[{"operation": "trim_whitespace", "table": "orders", "columns": ["customer_code"]}])
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review, policy_path=policy)
    assert auth.status == "authorized"
    dispositions = {(d.get("operation"), d.get("column")): d["disposition"] for d in read_yaml(tmp_path / "auth" / AUTHORIZATION_MANIFEST_NAME)["dispositions"] if d["governance_class"] == "configured_only"}
    assert dispositions == {("trim_whitespace", "customer_code"): "configured", ("normalize_blank_sentinel", "notes"): "not_configured"}


def test_no_policy_means_configured_steps_get_no_authority(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review)
    assert auth.status == "authorized" and auth.authority_count == 2  # only the two governed
    kinds = [a["authority_kind"] for a in read_yaml(tmp_path / "auth" / AUTHORITIES_NAME)["authorities"]]
    assert kinds == ["human_decision", "human_decision"]


def test_policy_that_lists_a_governed_operation_is_a_blocker(tmp_path):
    src = dataset(tmp_path)
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")
    policy = policy_file(tmp_path / "policy.yml", operations=[{"operation": "parse_date", "table": "orders", "columns": ["order_date"]}])
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review, policy_path=policy)
    assert auth.status == "blocked" and "policy_operation_not_configurable" in blocker_types(tmp_path / "auth")


def test_authorization_emits_canonical_order_and_a_hash_bound_plan(tmp_path):
    """D2-5/6. The plan is authoritative only over order; every other fact
    about a step is read from the self-bound authority record it references."""
    _, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    assert all(set(s) == {"sequence", "authority_sha256"} for s in plan["steps"])
    assert [s["sequence"] for s in plan["steps"]] == [1, 2, 3, 4]
    authorities = {a["authority_sha256"]: a for a in read_yaml(auth_dir / AUTHORITIES_NAME)["authorities"]}
    order = [(authorities[s["authority_sha256"]]["table"], authorities[s["authority_sha256"]]["column"], authorities[s["authority_sha256"]]["operation"]) for s in plan["steps"]]
    assert order == sorted(order)
    assert plan["application_plan_sha256"] == read_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME)["application_plan_sha256"]
    assert {s["authority_sha256"] for s in plan["steps"]} == set(authorities)


def test_plan_step_with_extra_metadata_is_refused_before_transformation(tmp_path):
    """Blocker 4: a step may not carry table/column/operation/authority_kind
    that could disagree with the referenced authority; the authority record
    is the sole source of step semantics."""
    src, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    plan["steps"][0]["operation"] = "parse_date"
    plan["steps"][0]["column"] = "ssn"
    write_yaml(auth_dir / APPLICATION_PLAN_NAME, plan)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "invalid_application_plan" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_same_authorities_in_a_different_order_have_a_different_plan_hash(tmp_path):
    _, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    from data_ops_lab.governed_cleaning_engine import _plan_hash
    forward = _plan_hash(plan["source_sha256"], [s["authority_sha256"] for s in plan["steps"]])
    reverse = _plan_hash(plan["source_sha256"], [s["authority_sha256"] for s in reversed(plan["steps"])])
    assert forward == plan["application_plan_sha256"] and forward != reverse


def test_authorization_never_stores_approved_as_free_standing_state(tmp_path):
    """approved is derived from decisions; candidates on disk stay pending_review."""
    src, proposal_dir, auth_dir = full_cycle(tmp_path)
    assert {c["review_state"] for c in read_yaml(proposal_dir / CANDIDATES_NAME)["candidates"]} == {"pending_review"}
    for name in (AUTHORITIES_NAME, APPLICATION_PLAN_NAME, AUTHORIZATION_MANIFEST_NAME):
        assert "review_state: approved" not in (auth_dir / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# APPLY
# --------------------------------------------------------------------------- #


def test_apply_writes_every_table_and_lineage_names_exactly_one_mechanism_per_step(tmp_path):
    """D2-12/13."""
    src, _, auth_dir = full_cycle(tmp_path)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "applied" and result.step_count == 4 and result.tables_written == 1
    lineage = read_yaml(tmp_path / "out" / LINEAGE_NAME)["lineage"]
    # canonical order is (table, column, operation): amount, customer_code, notes, order_date
    assert [(row["column"], row["authority_kind"]) for row in lineage] == [
        ("amount", "human_decision"), ("customer_code", "cleaning_policy"), ("notes", "cleaning_policy"), ("order_date", "human_decision"),
    ]
    assert all(len(row["authority_sha256"]) == 64 and len(row["output_sha256"]) == 64 for row in lineage)
    out = pd.read_parquet(tmp_path / "out" / "parquet" / "orders.parquet")
    assert out["amount"].tolist()[:3] == [100.0, 2500.0, 300.5] and pd.isna(out["amount"].iloc[3])
    assert out["order_date"].tolist()[0] == dt.date(2025, 1, 5)
    assert out["customer_code"].tolist() == ["C1", "C2", "C3", "C4"]
    notes = out["notes"].tolist()
    assert notes[0] == "ok" and pd.isna(notes[1]) and notes[2] == "-" and notes[3] == "fine"  # only N/A configured
    failed = {row["column"]: row["values_failed"] for row in lineage}
    assert failed["amount"] == 1  # the ABC value, recorded, not silent


def test_persisted_lineage_is_the_d1_contract_object_with_the_real_output_hash(tmp_path):
    """Blocker 2: lineage.yml rows are serialized TransformationLineage records
    built with the real logical output hash, plus D2 evidence beside them.
    No placeholder hash, no parallel schema."""
    src, _, auth_dir = full_cycle(tmp_path)
    run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    manifest = read_yaml(tmp_path / "out" / APPLICATION_MANIFEST_NAME)
    logical = {t["table"]: t["logical_content_sha256"] for t in manifest["tables"]}
    physical = {t["table"]: t["physical_sha256"] for t in manifest["tables"]}
    contract_fields = {"source_sha256", "authority_kind", "authority_sha256", "output_sha256", "table", "column",
                       "operation", "rows_examined", "rows_changed", "applied_at", "contract_version"}
    for row in read_yaml(tmp_path / "out" / LINEAGE_NAME)["lineage"]:
        assert contract_fields <= set(row), sorted(contract_fields - set(row))
        assert row["output_sha256"] == logical[row["table"]] and row["output_sha256"] != "0" * 64
        assert row["source_sha256"] == manifest["source_sha256"]
        assert is_aware_iso_timestamp(row["applied_at"])
        assert row["contract_version"] == 1
        assert "values_failed" in row and "sequence" in row               # D2 evidence beside the contract
        assert row["output_physical_sha256"] == physical[row["table"]]  # physical hash recorded, not promised
        assert row["output_sha256"] == logical_content_sha256(pd.read_parquet(tmp_path / "out" / "parquet" / f"{row['table']}.parquet"))


def test_apply_never_touches_the_source(tmp_path):
    src, _, auth_dir = full_cycle(tmp_path)
    before = (src / "orders.parquet").read_bytes()
    run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert (src / "orders.parquet").read_bytes() == before


def test_same_source_and_same_plan_produce_the_same_logical_output_and_lineage(tmp_path):
    """D2-11. Logical determinism; physical bytes are recorded, not promised."""
    src, _, auth_dir = full_cycle(tmp_path)
    run_governed_cleaning_apply(auth_dir, src, tmp_path / "out1")
    run_governed_cleaning_apply(auth_dir, src, tmp_path / "out2")
    m1, m2 = read_yaml(tmp_path / "out1" / APPLICATION_MANIFEST_NAME), read_yaml(tmp_path / "out2" / APPLICATION_MANIFEST_NAME)
    assert m1["logical_dataset_sha256"] == m2["logical_dataset_sha256"]
    l1, l2 = read_yaml(tmp_path / "out1" / LINEAGE_NAME)["lineage"], read_yaml(tmp_path / "out2" / LINEAGE_NAME)["lineage"]
    run_specific = {"applied_at", "output_physical_sha256"}   # timestamp is contract; bytes are not promised
    strip = lambda rows: [{k: v for k, v in r.items() if k not in run_specific} for r in rows]  # noqa: E731 - local comparator
    assert strip(l1) == strip(l2)
    assert all(is_aware_iso_timestamp(r["applied_at"]) for r in l1 + l2)
    a, b = pd.read_parquet(tmp_path / "out1" / "parquet" / "orders.parquet"), pd.read_parquet(tmp_path / "out2" / "parquet" / "orders.parquet")
    assert logical_content_sha256(a) == logical_content_sha256(b)


def test_source_changed_after_authorize_fails_before_transformation(tmp_path):
    """D2-7."""
    src, _, auth_dir = full_cycle(tmp_path)
    frame = pd.read_parquet(src / "orders.parquet")
    frame.loc[0, "notes"] = "changed"
    frame.to_parquet(src / "orders.parquet", index=False)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "source_changed_since_authorization" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_tampered_authority_bundle_fails_apply(tmp_path):
    """D2-8."""
    src, _, auth_dir = full_cycle(tmp_path)
    doc = read_yaml(auth_dir / AUTHORITIES_NAME)
    for record in doc["authorities"]:
        if record["operation"] == "normalize_blank_sentinel":
            record["effective_parameters"] = {"sentinels": ["N/A", "-", "ok"]}
    write_yaml(auth_dir / AUTHORITIES_NAME, doc)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "authority_bundle_hash_mismatch" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_tampered_or_reordered_application_plan_fails_apply_before_staging(tmp_path):
    """D2-9."""
    src, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    plan["steps"] = list(reversed(plan["steps"]))
    for i, s in enumerate(plan["steps"]):
        s["sequence"] = i + 1
    write_yaml(auth_dir / APPLICATION_PLAN_NAME, plan)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "application_plan_hash_mismatch" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def _rehash_plan_and_manifest(auth_dir, plan):
    plan["application_plan_sha256"] = _plan_hash(plan["source_sha256"], [s["authority_sha256"] for s in plan["steps"]])
    write_yaml(auth_dir / APPLICATION_PLAN_NAME, plan)
    manifest = read_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME)
    manifest["application_plan_sha256"] = plan["application_plan_sha256"]
    write_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME, manifest)


def test_plan_that_omits_one_authorized_authority_is_refused_before_transformation(tmp_path):
    """Blocker 3: the plan is the exact executable projection of the complete
    authorized bundle. Dropping one genuine authority, renumbering, and
    rehashing plan and manifest consistently must still be refused."""
    src, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    assert len(plan["steps"]) == 4
    del plan["steps"][2]
    for i, s in enumerate(plan["steps"]):
        s["sequence"] = i + 1
    _rehash_plan_and_manifest(auth_dir, plan)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked"
    types = blocker_types(tmp_path / "out")
    assert "application_plan_authority_set_mismatch" in types and "unknown_plan_authority" not in types
    assert not (tmp_path / "out" / "parquet").exists()


def test_plan_reordered_with_every_hash_rehashed_is_still_refused(tmp_path):
    """Order is part of the authority over the result. Even a reorder that
    rehashes plan and manifest consistently is refused because the plan must
    equal the canonical projection of the bundle."""
    src, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    plan["steps"] = list(reversed(plan["steps"]))
    for i, s in enumerate(plan["steps"]):
        s["sequence"] = i + 1
    _rehash_plan_and_manifest(auth_dir, plan)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "application_plan_authority_set_mismatch" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_apply_recomputes_canonical_order_from_the_verified_bundle(tmp_path):
    src, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    from data_ops_lab.governed_cleaning_engine import _authority_from_record
    records = read_yaml(auth_dir / AUTHORITIES_NAME)["authorities"]
    expected = [a.authority_sha256 for a in _order_steps([_authority_from_record(r, [], "x") for r in records])]
    assert [s["authority_sha256"] for s in plan["steps"]] == expected


def test_unknown_authority_in_plan_fails_apply(tmp_path):
    from data_ops_lab.governed_cleaning_engine import _plan_hash
    src, _, auth_dir = full_cycle(tmp_path)
    plan = read_yaml(auth_dir / APPLICATION_PLAN_NAME)
    plan["steps"][0]["authority_sha256"] = "9" * 64
    plan["application_plan_sha256"] = _plan_hash(plan["source_sha256"], [s["authority_sha256"] for s in plan["steps"]])
    write_yaml(auth_dir / APPLICATION_PLAN_NAME, plan)
    manifest = read_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME)
    manifest["application_plan_sha256"] = plan["application_plan_sha256"]
    write_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME, manifest)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "unknown_plan_authority" in blocker_types(tmp_path / "out")


def test_one_authority_failing_verify_leaves_zero_output(tmp_path):
    """D2-8/10: an authority whose self-check fails blocks the whole apply."""
    from data_ops_lab.governed_cleaning import sha256_of as h
    src, _, auth_dir = full_cycle(tmp_path)
    doc = read_yaml(auth_dir / AUTHORITIES_NAME)
    doc["authorities"][0]["column"] = "customer_code"  # retarget one authority
    manifest = read_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME)
    manifest["authorities_sha256"] = h(doc["authorities"])  # forge the bundle hash too
    write_yaml(auth_dir / AUTHORITIES_NAME, doc)
    write_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME, manifest)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "authority_hash_mismatch" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_forged_authority_kind_on_disk_fails_the_per_authority_self_check(tmp_path):
    """D2-8, the review class from D1: a well-formed authority record whose
    authority_kind was changed on disk - with the bundle hash rehashed to
    match - must still be refused by the record's own self-check."""
    from data_ops_lab.governed_cleaning import sha256_of as h
    src, _, auth_dir = full_cycle(tmp_path)
    doc = read_yaml(auth_dir / AUTHORITIES_NAME)
    real_policy_sha = next(r["policy_sha256"] for r in doc["authorities"] if r["authority_kind"] == "cleaning_policy")
    for record in doc["authorities"]:
        if record["authority_kind"] == "human_decision":
            record["authority_kind"] = "cleaning_policy"
            record["policy_sha256"] = real_policy_sha
            record["dataset_id"] = "orders_dataset"
            for key in ("candidate_id", "candidate_sha256", "decision_sha256"):
                record.pop(key)
    manifest = read_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME)
    manifest["authorities_sha256"] = h(doc["authorities"])
    write_yaml(auth_dir / AUTHORITIES_NAME, doc)
    write_yaml(auth_dir / AUTHORIZATION_MANIFEST_NAME, manifest)
    result = run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert result.status == "blocked" and "authority_hash_mismatch" in blocker_types(tmp_path / "out")
    assert not (tmp_path / "out" / "parquet").exists()


def test_partial_failure_publishes_nothing(tmp_path, monkeypatch):
    """D2-10. A failure mid-application leaves zero promoted output and no
    staging residue."""
    src, _, auth_dir = full_cycle(tmp_path)
    import data_ops_lab.governed_cleaning_engine as engine
    original = engine._apply_parse_date

    def explode(*args, **kwargs):
        raise RuntimeError("simulated failure during application")

    monkeypatch.setattr(engine, "_apply_parse_date", explode)
    with pytest.raises(RuntimeError):
        run_governed_cleaning_apply(auth_dir, src, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not any(p.name.startswith(".out.") for p in tmp_path.iterdir())
    monkeypatch.setattr(engine, "_apply_parse_date", original)
    assert run_governed_cleaning_apply(auth_dir, src, tmp_path / "out").status == "applied"


def test_apply_refuses_to_overwrite_an_existing_output_directory(tmp_path):
    src, _, auth_dir = full_cycle(tmp_path)
    (tmp_path / "out").mkdir()
    assert run_governed_cleaning_apply(auth_dir, src, tmp_path / "out").status == "blocked"


def test_two_value_changing_operations_on_one_column_are_refused_before_apply(tmp_path):
    """Engine v1 composition rule."""
    src = write_parquet(tmp_path / "src", t={"code": pd.Series([" 100 ", " 200 "], dtype=object)})
    run_governed_cleaning_propose(src, tmp_path / "proposal")
    review = full_review(tmp_path / "proposal", tmp_path / "review.yml")  # approves parse_number on code
    policy = policy_file(tmp_path / "policy.yml", operations=[{"operation": "trim_whitespace", "table": "t", "columns": ["code"]}])
    auth = run_governed_cleaning_authorize(tmp_path / "proposal", src, tmp_path / "auth", review_path=review, policy_path=policy)
    assert auth.status == "blocked" and "unsupported_operation_composition" in blocker_types(tmp_path / "auth")


# --------------------------------------------------------------------------- #
# Legacy path unchanged; engine is opt-in
# --------------------------------------------------------------------------- #


def test_legacy_workflow_matches_the_fixed_golden_baseline(tmp_path):
    """D2-17/18. run_workflow output over samples/raw must equal the committed
    logical baseline captured from origin/main before the engine existed. The
    expected values are static in tests/fixtures/legacy_cleaner/
    legacy_cleaner_golden.yml; nothing here computes them at test time. A
    deterministic change to cleaner.py would fail this test even though two
    fresh runs would still agree with each other."""
    from pathlib import Path

    from data_ops_lab.workflow import run_workflow
    golden = read_yaml(Path("tests/fixtures/legacy_cleaner/legacy_cleaner_golden.yml"))
    assert golden["version"] == 1 and golden["hash"] == "logical_content_sha256"
    assert set(golden["tables"]) == {"customers", "order_items", "orders"}
    result = run_workflow(Path(SAMPLES), tmp_path / "wf")
    actual = {name: logical_content_sha256(pd.read_parquet(result.output_dir / "02_cleaned" / f"{name}.parquet")) for name in golden["tables"]}
    expected = {name: entry["logical_content_sha256"] for name, entry in golden["tables"].items()}
    assert actual == expected, {k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]}
    # the legacy cleaner still coerces silently - the engine did not change it
    coerced = clean_dataframe(pd.DataFrame({"amount": pd.Series(["100"] * 9 + ["ABC"], dtype=object)}))
    assert pd.isna(coerced["amount"].iloc[9])


def test_golden_fixture_values_are_static_hex_digests():
    """Guard against someone turning the baseline into a computed value."""
    import re
    from pathlib import Path
    text = Path("tests/fixtures/legacy_cleaner/legacy_cleaner_golden.yml").read_text(encoding="utf-8")
    digests = re.findall(r"logical_content_sha256: ([0-9a-f]{64})$", text, re.M)
    assert len(digests) == 3 and len(set(digests)) == 3


def test_engine_is_opt_in_and_run_workflow_does_not_call_it(tmp_path, monkeypatch):
    """D2-19."""
    import data_ops_lab.governed_cleaning_engine as engine
    from data_ops_lab.workflow import run_workflow
    from pathlib import Path
    called = []
    monkeypatch.setattr(engine, "run_governed_cleaning_propose", lambda *a, **k: called.append("propose"))
    run_workflow(Path(SAMPLES), tmp_path / "wf")
    assert called == []


def test_engine_imports_no_network_capable_module():
    """D2-20."""
    import ast
    from pathlib import Path
    tree = ast.parse(Path("src/data_ops_lab/governed_cleaning_engine.py").read_text(encoding="utf-8"))
    roots = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    roots |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
    assert not roots & {"socket", "urllib", "requests", "http", "httpx", "aiohttp"}


def teardown_module(module):  # keep tmp usage tidy on Windows
    shutil.rmtree("outputs/tmp-engine-test", ignore_errors=True)
