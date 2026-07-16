from __future__ import annotations

import hashlib

from data_ops_lab import (
    analytics_query_execution,
    analytics_query_plan,
    analytics_semantic_approval,
    analytics_semantic_catalog,
    product_refnr_application,
    reference_dataset_validation,
    source_onboarding,
)
from data_ops_lab.contracts.blockers import (
    STANDARD_BLOCKER_FIELDS,
    add_blocker,
)
from data_ops_lab.contracts.hashing import FILE_HASH_CHUNK_SIZE, file_sha256


def test_file_sha256_preserves_legacy_exports_and_digest(tmp_path):
    content = b"phase-two-contract\n" * ((FILE_HASH_CHUNK_SIZE // 19) + 10)
    source = tmp_path / "source.bin"
    source.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()

    assert file_sha256(source) == expected
    assert source_onboarding.file_sha256 is file_sha256
    assert product_refnr_application.file_sha256 is file_sha256
    assert reference_dataset_validation.file_sha256 is file_sha256


def test_standard_blocker_preserves_legacy_exports_and_shape():
    blockers: list[dict[str, str]] = []

    add_blocker(
        blockers,
        "required_input_missing",
        "A required local input is missing.",
        field="dataset_manifest",
    )
    add_blocker(
        blockers,
        "invalid_yaml",
        "The required local input is not valid UTF-8 YAML.",
    )

    assert blockers == [
        {
            "blocker_id": "BLOCKER_001",
            "blocker_type": "required_input_missing",
            "field": "dataset_manifest",
            "explanation": "A required local input is missing.",
        },
        {
            "blocker_id": "BLOCKER_002",
            "blocker_type": "invalid_yaml",
            "field": "",
            "explanation": "The required local input is not valid UTF-8 YAML.",
        },
    ]
    assert tuple(blockers[0]) == STANDARD_BLOCKER_FIELDS
    assert analytics_query_plan.add_blocker is add_blocker
    assert analytics_query_execution.add_blocker is add_blocker
    assert analytics_semantic_approval.add_blocker is add_blocker
    assert analytics_semantic_catalog.add_blocker is add_blocker
