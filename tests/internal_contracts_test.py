from __future__ import annotations

import hashlib
import os

import pytest
from data_ops_lab import (
    analytics_query_execution,
    analytics_query_plan,
    analytics_semantic_approval,
    analytics_semantic_catalog,
    product_refnr_application,
    reference_dataset_validation,
    source_onboarding,
)
from data_ops_lab.contracts.atomic_publish import (
    DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
    DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
    AtomicPublishTargetAppearedError,
    atomic_write_text,
    publish_new_directory,
)
from data_ops_lab.contracts.blockers import (
    STANDARD_BLOCKER_FIELDS,
    add_blocker,
)
from data_ops_lab.contracts.hashing import FILE_HASH_CHUNK_SIZE, file_sha256
from data_ops_lab.contracts.source_bindings import existing_file_sha256_bindings


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


def test_atomic_write_text_retries_and_cleans_temporary_file(tmp_path):
    path = tmp_path / "checkpoint.yml"
    path.write_text("old\n", encoding="utf-8")
    attempts = 0
    delays: list[float] = []

    def transient_replace(source: object, target: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("synthetic transient lock")
        os.replace(source, target)

    atomic_write_text(
        path,
        "new\n",
        retry_delays=DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
        sleep_fn=delays.append,
        replace_fn=transient_replace,
    )

    assert attempts == 2
    assert delays == [DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS[0]]
    assert path.read_text(encoding="utf-8") == "new\n"
    assert not list(tmp_path.glob(".checkpoint.yml.*.tmp"))


def test_atomic_write_text_cleans_temporary_file_after_retry_exhaustion(tmp_path):
    path = tmp_path / "checkpoint.yml"
    delays: list[float] = []

    def locked_replace(source: object, target: object) -> None:
        raise PermissionError("synthetic persistent lock")

    with pytest.raises(PermissionError, match="synthetic persistent lock"):
        atomic_write_text(
            path,
            "new\n",
            retry_delays=(0.01, 0.02),
            sleep_fn=delays.append,
            replace_fn=locked_replace,
        )

    assert delays == [0.01, 0.02]
    assert not path.exists()
    assert not list(tmp_path.glob(".checkpoint.yml.*.tmp"))


def test_publish_new_directory_preserves_target_that_appears_and_cleans_staging(
    tmp_path,
):
    staging = tmp_path / ".evidence.staging"
    staging.mkdir()
    (staging / "manifest.yml").write_text("version: 1\n", encoding="utf-8")
    output = tmp_path / "evidence"

    def colliding_replace(source, target):
        target.mkdir()
        (target / "human-notes.txt").write_text("preserve me\n", encoding="utf-8")
        raise PermissionError("synthetic target race")

    with pytest.raises(AtomicPublishTargetAppearedError) as error:
        publish_new_directory(
            staging,
            output,
            retry_delays=DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
            replace_fn=colliding_replace,
        )

    assert error.value.target == output
    assert (output / "human-notes.txt").read_text(encoding="utf-8") == "preserve me\n"
    assert not staging.exists()


def test_existing_file_sha256_bindings_preserves_order_and_omits_missing(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    missing = tmp_path / "missing.txt"
    directory = tmp_path / "directory"
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    directory.mkdir()

    bindings = existing_file_sha256_bindings(
        {
            "second_sha256": second,
            "missing_sha256": missing,
            "directory_sha256": directory,
            "first_sha256": first,
        }
    )

    assert list(bindings) == ["second_sha256", "first_sha256"]
    assert bindings == {
        "second_sha256": file_sha256(second),
        "first_sha256": file_sha256(first),
    }
