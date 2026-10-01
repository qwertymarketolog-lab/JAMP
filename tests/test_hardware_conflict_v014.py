from copy import deepcopy

import pytest

from jamp.hardware_conflict import (
    build_conflict_record,
    calculate_conflict_id,
    canonical_timestamp,
    classify_scope,
    is_duplicate_evidence,
    verify_conflict_id,
)

SUBJECT = {
    "run_id": "RUN-001",
    "hardware_id": "HW-1",
    "firmware_version": "FW-1",
    "driver_commit": "sha256:" + "1" * 64,
    "model_weights_sha256": "sha256:" + "2" * 64,
    "quantization_spec": "FP16",
    "runtime_env": "Bare-Metal",
    "workload_identity_digest": "sha256:" + "3" * 64,
}
A = {
    "artifact_sha256": "sha256:" + "a" * 64,
    "evidence_type": "AUTHORITATIVE",
    "source": "thermal.sensor",
    "timestamp": "2026-10-01T19:00:00Z",
}
B = {
    "artifact_sha256": "sha256:" + "b" * 64,
    "evidence_type": "AUTHORITATIVE",
    "source": "thermal.guard",
    "timestamp": "2026-10-01T19:01:00Z",
}

def make_record(a=A, b=B):
    return build_conflict_record(
        predicate_id="P4",
        conflict_type="THERMAL_CONTRADICTION",
        subject_identity=SUBJECT,
        evidence_a=a,
        evidence_b=b,
        observed_a=False,
        observed_b=True,
    )

def test_ab_conflict_and_deterministic_id():
    record = make_record()
    assert verify_conflict_id(record)
    assert record["conflict_id"] == "sha256:b232ab9086547af333dfb982cde3b29112d42ad4c42ddec2842af8c496abea2c"

def test_reordered_evidence_has_same_id():
    assert calculate_conflict_id(make_record(A, B)) == calculate_conflict_id(make_record(B, A))

def test_duplicate_evidence_is_not_a_conflict():
    assert is_duplicate_evidence(A, A)
    with pytest.raises(ValueError, match="duplicate evidence"):
        make_record(A, A)

def test_scope_mismatch_is_not_conflict():
    other = deepcopy(make_record())
    other["subject_identity"]["run_id"] = "RUN-002"
    assert classify_scope(make_record(), other) == "DIFFERENT_SCOPE"

def test_tamper_changes_identity():
    record = make_record()
    record["observed_values"]["b"] = False
    assert not verify_conflict_id(record)

def test_timestamp_normalization_is_deterministic():
    assert canonical_timestamp("2026-10-01T21:00:00+02:00") == "2026-10-01T19:00:00.000000Z"
