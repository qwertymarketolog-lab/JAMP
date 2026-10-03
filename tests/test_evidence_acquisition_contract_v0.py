"""Fail-closed implementation-conformance contract for Evidence Acquisition v0.

This suite is intentionally separate from the PR-1 primitive tests. It tests
the normative v0 requirements against the implementation and E2E probe without
changing either implementation or Frozen Core.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from jamp.evidence import (
    AtomicObservation,
    ContractStateMachine,
    EvidenceLedger,
    ExecutionEnvelope,
    ExecutionState,
    FrozenInput,
    RawOutput,
    StateTransitionError,
    persist_bundle,
)
from jamp.evidence.checker import (
    check,
    checker_digest,
    checker_source_digest,
    compute_composite_checker_digest,
    replay_check,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/evidence/EVIDENCE-ACQUISITION-CONTRACT-v0.md"
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
    "manifest_version",
    "object_digests",
    "root_integrity_digest",
    "checker_source_digest",
    "checker_contract_digest",
    "state",
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


def _fixture_records():
    envelope = ExecutionEnvelope(
        contract_version="evidence-acquisition-v0",
        execution_id="exec-001",
        execution_created_at="2026-10-03T10:00:00Z",
        execution_started_at="2026-10-03T10:00:01Z",
        execution_finished_at="2026-10-03T10:00:02Z",
        git_sha="a" * 40,
        probe_sha="b" * 40,
        workflow_sha="c" * 40,
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
        implementation_ref=("a" * 40) + ":probe.py",
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


def _persist_fixture_bundle(tmp_path):
    envelope, frozen, raw, observation = _fixture_records()
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    entry = ledger.append(observation, creation_metadata={"created_at": "2026-10-03T10:00:02Z"})
    checker_contract = {
        "checker_id": "http-json-repo-checker",
        "checker_version": "1",
        "input_schema_version": "raw-output-v1",
        "canonicalization_rules": "json-sort-keys-separators-utf8",
        "required_input_digests": ["raw_response_digest"],
        "acceptance_predicate": "HTTP 200 JSON full_name equals qwertymarketolog-lab/JAMP",
        "rejection_predicate": "HTTP 200 valid JSON repository identity mismatch",
        "inconclusive_predicate": "missing transport status or required JSON evidence",
        "self_test_fixtures": [],
    }
    checker_output = check(
        raw_response=raw.raw_response,
        raw_response_digest=raw.raw_response_digest,
        http_status=raw.http_status,
    ).as_dict()
    return persist_bundle(
        tmp_path / "bundle",
        envelope=envelope,
        frozen_input=frozen,
        raw_output=raw,
        observation=observation,
        ledger_entry=entry,
        checker_contract=checker_contract,
        checker_output=checker_output,
        created_at="2026-10-03T10:00:02Z",
    )


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
    assert set(ExecutionEnvelope.__dataclass_fields__) >= REQUIRED_ENVELOPE


def test_derived_objects_are_bound_to_execution_and_digests():
    envelope, frozen, raw, observation = _fixture_records()
    assert (
        frozen.execution_id == raw.execution_id == observation.execution_id == envelope.execution_id
    )
    assert raw.input_digest == frozen.input_digest
    assert observation.frozen_input_digest == frozen.digest
    assert observation.raw_output_digest == raw.digest


def test_raw_output_preserves_exact_bytes_and_digest():
    _, _, raw, _ = _fixture_records()
    assert raw.raw_response == b'{"ok":true}'
    assert raw.raw_response_digest == hashlib.sha256(raw.raw_response).hexdigest()


def test_provenance_fixture_requires_concrete_sha_bindings():
    envelope, _, _, _ = _fixture_records()
    for name in ("git_sha", "probe_sha", "workflow_sha"):
        value = getattr(envelope, name)
        assert len(value) == 40
        assert all(char in "0123456789abcdef" for char in value)


def test_environment_fixture_contains_no_secret_material():
    envelope, _, _, _ = _fixture_records()
    serialized = json.dumps(envelope.__dict__, sort_keys=True)
    assert "API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "cookie" not in serialized.lower()


def test_checker_contract_is_behaviorally_versioned():
    response = b'{"full_name":"qwertymarketolog-lab/JAMP"}'
    result = check(
        raw_response=response,
        raw_response_digest=hashlib.sha256(response).hexdigest(),
        http_status=200,
    )
    assert result.status == "CHECKED"
    assert result.checker_version == "1"
    assert len(checker_digest()) == 64


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
    assert set(manifest) >= REQUIRED_MANIFEST


def test_manifest_commits_checker_and_bundle_objects_behaviorally(tmp_path):
    bundle = _persist_fixture_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    checker = json.loads((bundle / "checker.json").read_text(encoding="utf-8"))
    contract = json.loads((bundle / "checker_contract.json").read_text(encoding="utf-8"))
    assert manifest["checker_source_digest"] == checker_source_digest()
    assert manifest["checker_contract_digest"] == hashlib.sha256(
        json.dumps(
            contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    assert manifest["checker_digest"] == compute_composite_checker_digest(
        manifest["checker_source_digest"], contract
    )
    assert manifest["checker_output_digest"] == hashlib.sha256(
        json.dumps(
            checker, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    actual = {
        path.relative_to(bundle).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in bundle.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    assert manifest["object_digests"] == actual


def test_checker_rejects_corrupt_raw_response_digest():
    response = b'{"full_name":"qwertymarketolog-lab/JAMP"}'
    result = check(
        raw_response=response,
        raw_response_digest="0" * 64,
        http_status=200,
    )
    assert result.accepted is False
    assert result.status == "INCONCLUSIVE"
    assert result.reason == "raw_response_digest_mismatch"


def test_checker_fails_closed_on_missing_required_transport():
    response = b'{"full_name":"qwertymarketolog-lab/JAMP"}'
    result = check(
        raw_response=response,
        raw_response_digest=hashlib.sha256(response).hexdigest(),
        http_status=None,
    )
    assert result.accepted is False
    assert result.status == "INCONCLUSIVE"


def test_checker_does_not_smuggle_semantic_verdict_from_prose():
    response = b'{"message":"The repository qwertymarketolog-lab/JAMP is valid"}'
    result = check(
        raw_response=response,
        raw_response_digest=hashlib.sha256(response).hexdigest(),
        http_status=200,
    )
    assert result.accepted is False
    assert result.status == "FAILED"


def test_replay_tamper_of_frozen_input_is_inconclusive(tmp_path):
    bundle = _persist_fixture_bundle(tmp_path)
    (bundle / "frozen_input.json").write_text('{"tampered":true}', encoding="utf-8")
    from research.experiments.evidence_acquisition_e2e import replay_bundle

    assert replay_bundle(bundle) == "REPLAY_INCONCLUSIVE"


def test_replay_tamper_of_checker_output_is_inconclusive(tmp_path):
    bundle = _persist_fixture_bundle(tmp_path)
    checker_path = bundle / "checker.json"
    checker = json.loads(checker_path.read_text(encoding="utf-8"))
    checker["accepted"] = not checker["accepted"]
    checker_path.write_text(json.dumps(checker), encoding="utf-8")
    from research.experiments.evidence_acquisition_e2e import replay_bundle

    assert replay_bundle(bundle) == "REPLAY_INCONCLUSIVE"


def test_replay_checker_version_mismatch_is_inconclusive():
    response = b'{"full_name":"qwertymarketolog-lab/JAMP"}'
    result = replay_check(
        raw_response=response,
        raw_response_digest=hashlib.sha256(response).hexdigest(),
        http_status=200,
        declared_checker_version="999",
    )
    assert result["status"] == "REPLAY_INCONCLUSIVE"


def test_integrity_chain_is_behaviorally_bound(tmp_path):
    bundle = _persist_fixture_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["provenance"]["git_sha"]) == 40
    assert len(manifest["provenance"]["workflow_sha"]) == 40
    assert manifest["provenance"]["execution_id"] == manifest["execution_id"]
    assert manifest["provenance"]["checker_digest"] == manifest["checker_digest"]


def test_state_machine_rejects_skipped_execution_state():
    machine = ContractStateMachine()
    with pytest.raises(StateTransitionError):
        machine.transition_to(ExecutionState.CHECKED)
    assert machine.current_state is ExecutionState.INCONCLUSIVE
    assert machine.history == (
        ExecutionState.DESIGNED,
        ExecutionState.INCONCLUSIVE,
    )


def test_state_machine_accepts_only_contract_order():
    machine = ContractStateMachine()
    for state in (
        ExecutionState.PREFLIGHT_VERIFIED,
        ExecutionState.EXECUTING,
        ExecutionState.CAPTURED,
        ExecutionState.CHECKED,
        ExecutionState.BUNDLED,
        ExecutionState.REPLAY_VERIFIED,
    ):
        machine.transition_to(state)
    assert machine.current_state is ExecutionState.REPLAY_VERIFIED


def test_checker_source_digest_detects_one_byte_change(tmp_path):
    source = tmp_path / "checker.py"
    source.write_bytes((ROOT / "src/jamp/evidence/checker.py").read_bytes())
    original = checker_source_digest(source)
    source.write_bytes(source.read_bytes() + b"\n")
    assert checker_source_digest(source) != original


def test_bundle_object_bijection_rejects_extra_file(tmp_path):
    bundle = _persist_fixture_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    (bundle / "unexpected.bin").write_bytes(b"extra")
    from research.experiments.evidence_acquisition_e2e import verify_object_digests

    with pytest.raises(ValueError, match="object digest map mismatch"):
        verify_object_digests(bundle, manifest)


def test_bundle_object_bijection_rejects_tamper(tmp_path):
    bundle = _persist_fixture_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    (bundle / "checker.json").write_bytes(b"tampered")
    from research.experiments.evidence_acquisition_e2e import verify_object_digests

    with pytest.raises(ValueError, match="object digest map mismatch"):
        verify_object_digests(bundle, manifest)


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
