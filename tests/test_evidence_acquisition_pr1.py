from dataclasses import asdict

import pytest

from jamp.evidence import (
    AtomicObservation,
    EvidenceLedger,
    ExecutionEnvelope,
    FrozenInput,
    RawOutput,
    persist_bundle,
)


@pytest.fixture
def envelope():
    return ExecutionEnvelope(
        contract_version="v0",
        execution_id="exec-001",
        execution_created_at="2026-10-03T10:00:00Z",
        execution_started_at="2026-10-03T10:00:01Z",
        execution_finished_at=None,
        git_sha="git",
        probe_sha="probe",
        workflow_sha="workflow",
        target_ref="main",
        entrypoint="tests/probe.py",
        pid=123,
        process_started_at="2026-10-03T10:00:01Z",
        cwd="/repo",
        runtime_identity="python-3.11",
        environment_digest="env",
        argv_digest="argv",
        input_digest="input",
        spec_hash="spec",
        criterion_set_hash="criteria",
        implementation_ref="impl",
        environment_ref="env-ref",
        status="CAPTURED",
    )


def records(envelope):
    frozen = FrozenInput.create(
        execution_id=envelope.execution_id,
        probe_id="probe-001",
        model_id="fixture/model",
        canonical_task_input={"prompt": "hello", "n": 1},
        encoding_version="json-c14n-1",
        timestamp="2026-10-03T10:00:01Z",
        contract_version="v0",
        checker_version="pending",
    )
    raw = RawOutput.create(
        execution_id=envelope.execution_id,
        input_digest=frozen.input_digest,
        provider_endpoint="fixture://offline",
        http_status=200,
        allowlisted_headers={"x-test": "1"},
        raw_response=b'{"ok":true}',
        elapsed_transport_ms=1.5,
        response_timestamp="2026-10-03T10:00:02Z",
        terminal_transport_state="COMPLETE",
    )
    observation = AtomicObservation(
        execution_id=envelope.execution_id,
        frozen_input_digest=frozen.digest,
        raw_output_digest=raw.digest,
        probe_id="probe-001",
        operator_id="fixture",
        operator_version="1",
        observation={"ok": True},
        observation_id="obs-001",
    )
    return frozen, raw, observation


def test_t1_execution_identity_binding(envelope):
    frozen, raw, observation = records(envelope)
    assert (
        frozen.execution_id == raw.execution_id == observation.execution_id == envelope.execution_id
    )


def test_t2_frozen_input_reproducibility(envelope):
    a = FrozenInput.create(
        execution_id="e",
        probe_id="p",
        model_id="m",
        canonical_task_input={"b": 2, "a": 1},
        encoding_version="json-c14n-1",
        timestamp="t",
        contract_version="v0",
        checker_version="c",
    )
    b = FrozenInput.create(
        execution_id="e",
        probe_id="p",
        model_id="m",
        canonical_task_input={"a": 1, "b": 2},
        encoding_version="json-c14n-1",
        timestamp="t",
        contract_version="v0",
        checker_version="c",
    )
    assert a.input_digest == b.input_digest


def test_t3_raw_output_execution_binding(envelope):
    frozen, raw, observation = records(envelope)
    assert raw.input_digest == frozen.input_digest
    assert observation.raw_output_digest == raw.digest


def test_t4_immutable_bundle_integrity(tmp_path, envelope):
    frozen, raw, observation = records(envelope)
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
    assert (bundle / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        persist_bundle(
            bundle,
            envelope=envelope,
            frozen_input=frozen,
            raw_output=raw,
            observation=observation,
            ledger_entry=entry,
        )


def test_t5_ledger_append_only_hash_chain(tmp_path, envelope):
    _, raw, first = records(envelope)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    second = AtomicObservation(
        **{**asdict(first), "observation_id": "obs-002", "raw_output_digest": raw.digest}
    )
    e1 = ledger.append(first, creation_metadata={"created_at": "1"})
    e2 = ledger.append(second, creation_metadata={"created_at": "2"})
    ledger.verify()
    assert e2.previous_entry_digest == e1.digest
    assert ledger.path.read_text(encoding="utf-8").count("\n") == 2


def test_t6_duplicate_evidence_identity_rejected(tmp_path, envelope):
    _, _, observation = records(envelope)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(observation, creation_metadata={"created_at": "t"})
    with pytest.raises(ValueError, match="duplicate evidence identity"):
        ledger.append(observation, creation_metadata={"created_at": "t2"})
