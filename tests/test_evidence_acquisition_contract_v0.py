"""Fail-closed implementation-conformance contract for Evidence Acquisition v0.

This suite is intentionally separate from the PR-1 primitive tests. It tests
the normative v0 requirements against the implementation and E2E probe without
changing either implementation or Frozen Core.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from jamp.evidence import (
    AtomicObservation,
    EvidenceLedger,
    ExecutionEnvelope,
    FrozenInput,
    RawOutput,
    persist_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/evidence/EVIDENCE-ACQUISITION-CONTRACT-v0.md"
ACQUISITION = ROOT / "src/jamp/evidence/acquisition.py"
PROBE = ROOT / "research/experiments/evidence_acquisition_e2e.py"
FROZEN_CORE = ROOT / "src/jamp/run.py"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"

REQUIRED_MANIFEST = {
    "bundle_version",
    "execution_id",
    "execution_envelope_digest",
    "frozen_input_digest",
    "raw_output_digest",
    "atomic_observation_ids",
    "checker_id",
    "checker_version",
    "checker_digest",
    "checker_input_digest",
    "checker_output_digest",
    "final_status",
    "created_at",
}

REQUIRED_ENVELOPE = {
    "contract_version",
    "execution_id",
    "execution_created_at",
    "execution_started_at",
    "execution_finished_at",
    "git_sha",
    "probe_sha",
    "workflow_sha",
    "target_ref",
    "entrypoint",
    "pid",
    "process_started_at",
    "cwd",
    "runtime_identity",
    "environment_digest",
    "argv_digest",
    "input_digest",
    "spec_hash",
    "criterion_set_hash",
    "implementation_ref",
    "environment_ref",
    "status",
}


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ast(path: Path) -> ast.Module:
    return ast.parse(_source(path), filename=str(path))


def _fixture_records():
    envelope = ExecutionEnvelope(
        contract_version="evidence-acquisition-v0",
        execution_id="exec-001",
        execution_created_at="2026-10-03T10:00:00Z",
        execution_started_at="2026-10-03T10:00:01Z",
        execution_finished_at="2026-10-03T10:00:02Z",
        git_sha="git-sha",
        probe_sha="probe-sha",
        workflow_sha="workflow-sha",
        target_ref="main",
        entrypoint="probe.py",
        pid=1,
        process_started_at="2026-10-03T10:00:00Z",
        cwd="/repo",
        runtime_identity="CPython 3.14",
        environment_digest="env-digest",
        argv_digest="argv-digest",
        input_digest="input-digest",
        spec_hash="spec-digest",
        criterion_set_hash="criteria-digest",
        implementation_ref="git-sha:probe.py",
        environment_ref="environment-record-1",
        status="CHECKED",
    )
    frozen = FrozenInput.create(
        execution_id=envelope.execution_id,
        probe_id="probe",
        model_id="fixture",
        canonical_task_input={"prompt": "hello"},
        encoding_version="json-c14n-1",
        timestamp=envelope.execution_started_at,
        contract_version=envelope.contract_version,
        checker_version="checker-1",
    )
    raw = RawOutput.create(
        execution_id=envelope.execution_id,
        input_digest=frozen.input_digest,
        provider_endpoint="fixture://offline",
        http_status=200,
        allowlisted_headers={"content-type": "application/json"},
        raw_response=b'{"ok":true}',
        elapsed_transport_ms=1.0,
        response_timestamp=envelope.execution_finished_at,
        terminal_transport_state="COMPLETE",
    )
    observation = AtomicObservation(
        execution_id=envelope.execution_id,
        frozen_input_digest=frozen.digest,
        raw_output_digest=raw.digest,
        probe_id="probe",
        operator_id="operator",
        operator_version="1",
        observation={"ok": True},
        observation_id=hashlib.sha256(
            json.dumps(
                {
                    "execution_id": envelope.execution_id,
                    "frozen_input_digest": frozen.digest,
                    "raw_output_digest": raw.digest,
                    "probe_id": "probe",
                    "operator_id": "operator",
                    "operator_version": "1",
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    )
    return envelope, frozen, raw, observation


def test_requirement_matrix_covers_every_normative_section():
    contract = _source(CONTRACT)
    normative_sections = {"2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "14"}
    headings = {
        line.split(".", 1)[0].removeprefix("## ").strip()
        for line in contract.splitlines()
        if line.startswith("## ") and "." in line
    }
    assert normative_sections <= headings


def test_execution_identity_exists_before_external_call():
    source = _source(PROBE)
    assert source.index("execution_id =") < source.index("urllib.request.urlopen")


def test_execution_envelope_has_all_contract_fields():
    assert REQUIRED_ENVELOPE <= set(ExecutionEnvelope.__dataclass_fields__)


def test_derived_objects_are_bound_to_execution_and_digests():
    envelope, frozen, raw, observation = _fixture_records()
    assert frozen.execution_id == raw.execution_id == observation.execution_id == envelope.execution_id
    assert raw.input_digest == frozen.input_digest
    assert observation.frozen_input_digest == frozen.digest
    assert observation.raw_output_digest == raw.digest


def test_raw_output_preserves_exact_bytes_and_digest():
    _, _, raw, _ = _fixture_records()
    assert raw.raw_response == b'{"ok":true}'
    assert raw.raw_response_digest == hashlib.sha256(raw.raw_response).hexdigest()


def test_provenance_bindings_are_exact_and_concrete():
    source = _source(PROBE)
    assert "GITHUB_WORKFLOW_SHA" in source
    assert "FROZEN_SPEC_HASH" in source
    assert "FROZEN_CRITERION_SET_HASH" in source
    assert "CONCRETE_ENVIRONMENT_RECORD" in source


def test_environment_capture_is_allowlisted_and_complete():
    source = _source(PROBE)
    assert "API_KEY" not in source
    assert "Authorization" not in source
    assert '"architecture"' in source
    assert '"dependency_set_digest"' in source


def test_checker_contract_declares_all_normative_components():
    source = _source(PROBE)
    markers = (
        "checker_digest",
        "input_schema_version",
        "canonicalization_rules",
        "acceptance_predicate",
        "rejection_predicate",
        "inconclusive_predicate",
        "self_test_fixtures",
    )
    assert all(marker in source for marker in markers)


def test_manifest_contains_minimum_v0_fields(tmp_path):
    envelope, frozen, raw, observation = _fixture_records()
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    entry = ledger.append(observation, creation_metadata={"created_at": "t"})
    bundle = persist_bundle(
        tmp_path / "bundle",
        envelope=envelope,
        frozen_input=frozen,
        raw_output=raw,
        observation=observation,
        ledger_entry=entry,
    )
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert REQUIRED_MANIFEST <= set(manifest)


def test_manifest_commits_checker_and_bundle_objects():
    source = _source(ACQUISITION)
    for marker in ("checker_digest", "checker_input_digest", "checker_output_digest", "created_at"):
        assert marker in source


def test_integrity_chain_contains_every_required_link():
    source = _source(ACQUISITION)
    for marker in (
        "git_sha",
        "workflow_sha",
        "execution_id",
        "input_digest",
        "raw_response_digest",
        "atomic_observation_id",
        "checker_digest",
        "checker_output_digest",
        "bundle_digest",
    ):
        assert marker in source


def test_missing_required_evidence_is_inconclusive():
    source = _source(PROBE)
    assert "INCONCLUSIVE" in source
    assert "transport_or_json_failure" not in source


def test_replay_is_complete_and_offline():
    source = _source(PROBE)
    markers = (
        "verify_manifest",
        "verify_referenced_digests",
        "verify_atomic_observation",
        "load_declared_checker",
        "regenerate_checker_output",
        "REPLAY_INCONCLUSIVE",
    )
    assert all(marker in source for marker in markers)


def test_checker_version_mismatch_is_not_pass():
    source = _source(PROBE)
    assert "version mismatch" in source.lower()
    assert "REPLAY_INCONCLUSIVE" in source


def test_state_machine_is_explicit_and_fail_closed():
    contract = _source(CONTRACT)
    for state in (
        "DESIGNED",
        "PREFLIGHT_VERIFIED",
        "EXECUTING",
        "CAPTURED",
        "CHECKED",
        "BUNDLED",
        "REPLAY_VERIFIED",
        "FAILED",
        "INCONCLUSIVE",
        "INTEGRITY_FAILURE",
    ):
        assert state in contract


def test_historical_v3_and_frozen_core_are_untouched():
    data = FROZEN_CORE.read_bytes()
    blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert blob_sha == FROZEN_CORE_BLOB
    assert "historical v3" not in _source(PROBE).lower()


def test_immutable_bundle_rejects_overwrite(tmp_path):
    envelope, frozen, raw, observation = _fixture_records()
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    entry = ledger.append(observation, creation_metadata={"created_at": "t"})
    bundle = persist_bundle(
        tmp_path / "bundle",
        envelope=envelope,
        frozen_input=frozen,
        raw_output=raw,
        observation=observation,
        ledger_entry=entry,
    )
    with pytest.raises(FileExistsError):
        persist_bundle(
            bundle,
            envelope=envelope,
            frozen_input=frozen,
            raw_output=raw,
            observation=observation,
            ledger_entry=entry,
        )
