"""Minimal persisted evidence-acquisition primitives for PR-1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class ExecutionEnvelope:
    contract_version: str
    execution_id: str
    execution_created_at: str
    execution_started_at: str
    execution_finished_at: str | None
    git_sha: str
    probe_sha: str
    workflow_sha: str
    target_ref: str
    entrypoint: str
    pid: int
    process_started_at: str
    cwd: str
    runtime_identity: str
    environment_digest: str
    argv_digest: str
    input_digest: str
    spec_hash: str
    criterion_set_hash: str
    implementation_ref: str
    environment_ref: str
    status: str

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class FrozenInput:
    execution_id: str
    probe_id: str
    model_id: str
    canonical_task_input: Any
    encoding_version: str
    input_digest: str
    timestamp: str
    contract_version: str
    checker_version: str

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        probe_id: str,
        model_id: str,
        canonical_task_input: Any,
        encoding_version: str,
        timestamp: str,
        contract_version: str,
        checker_version: str,
    ) -> FrozenInput:
        return cls(
            execution_id,
            probe_id,
            model_id,
            canonical_task_input,
            encoding_version,
            _digest(canonical_task_input),
            timestamp,
            contract_version,
            checker_version,
        )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class RawOutput:
    execution_id: str
    input_digest: str
    provider_endpoint: str
    http_status: int | None
    allowlisted_headers: dict[str, str]
    raw_response: bytes
    raw_response_digest: str
    elapsed_transport_ms: float | None
    response_timestamp: str
    terminal_transport_state: str

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        input_digest: str,
        provider_endpoint: str,
        http_status: int | None,
        allowlisted_headers: dict[str, str],
        raw_response: bytes,
        elapsed_transport_ms: float | None,
        response_timestamp: str,
        terminal_transport_state: str,
    ) -> RawOutput:
        return cls(
            execution_id,
            input_digest,
            provider_endpoint,
            http_status,
            dict(allowlisted_headers),
            bytes(raw_response),
            sha256(raw_response).hexdigest(),
            elapsed_transport_ms,
            response_timestamp,
            terminal_transport_state,
        )

    @property
    def digest(self) -> str:
        return _digest({**asdict(self), "raw_response": self.raw_response.hex()})


@dataclass(frozen=True)
class AtomicObservation:
    execution_id: str
    frozen_input_digest: str
    raw_output_digest: str
    probe_id: str
    operator_id: str
    operator_version: str
    observation: Any
    observation_id: str

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class LedgerEntry:
    ledger_entry_id: str
    evidence_id: str
    evidence: dict[str, Any]
    record_digest: str
    previous_entry_digest: str | None
    creation_metadata: dict[str, Any]

    @classmethod
    def from_observation(
        cls,
        observation: AtomicObservation,
        *,
        previous_entry_digest: str | None,
        creation_metadata: dict[str, Any],
    ) -> LedgerEntry:
        evidence = asdict(observation)
        return cls(
            observation.observation_id,
            observation.observation_id,
            evidence,
            _digest(evidence),
            previous_entry_digest,
            dict(creation_metadata),
        )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


class EvidenceLedger:
    """Durable JSONL ledger with explicit append-only/hash-chain semantics."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _entries(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        return [
            LedgerEntry(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def append(
        self,
        observation: AtomicObservation,
        *,
        creation_metadata: dict[str, Any],
    ) -> LedgerEntry:
        entries = self._entries()
        if any(e.evidence_id == observation.observation_id for e in entries):
            raise ValueError(f"duplicate evidence identity: {observation.observation_id}")
        entry = LedgerEntry.from_observation(
            observation,
            previous_entry_digest=entries[-1].digest if entries else None,
            creation_metadata=creation_metadata,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    asdict(entry),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            )
        return entry

    def verify(self) -> None:
        previous = None
        seen: set[str] = set()
        for entry in self._entries():
            if entry.evidence_id in seen:
                raise ValueError("ledger duplicate evidence identity")
            if entry.previous_entry_digest != previous:
                raise ValueError("ledger previous-entry digest mismatch")
            if entry.record_digest != _digest(entry.evidence):
                raise ValueError("ledger record digest mismatch")
            if entry.digest != _digest(asdict(entry)):
                raise ValueError("ledger entry digest mismatch")
            seen.add(entry.evidence_id)
            previous = entry.digest


def _json_record(record: Any) -> dict[str, Any]:
    value = asdict(record)
    if isinstance(value.get("raw_response"), bytes):
        value["raw_response"] = value["raw_response"].hex()
    return value


def persist_bundle(
    path: str | Path,
    *,
    envelope: ExecutionEnvelope,
    frozen_input: FrozenInput,
    raw_output: RawOutput,
    observation: AtomicObservation,
    ledger_entry: LedgerEntry,
    checker_contract: dict[str, Any] | None = None,
    checker_output: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> Path:
    """Write a self-contained immutable bundle and refuse overwrite."""
    root = Path(path)
    if root.exists():
        raise FileExistsError(f"immutable bundle already exists: {root}")
    root.mkdir(parents=True)

    if checker_contract is None:
        checker_contract = {
            "checker_id": "unbound-persist",
            "checker_version": "0",
            "input_schema_version": "raw-output-v1",
            "canonicalization_rules": "json-sort-keys-separators-utf8",
            "required_input_digests": ["raw_response_digest"],
            "acceptance_predicate": "none",
            "rejection_predicate": "none",
            "inconclusive_predicate": "checker_not_supplied",
            "self_test_fixtures": [],
        }
    if checker_output is None:
        checker_output = {
            "checker_id": checker_contract["checker_id"],
            "checker_version": checker_contract["checker_version"],
            "input_digest": raw_output.raw_response_digest,
            "accepted": False,
            "status": "INCONCLUSIVE",
            "reason": "checker_not_supplied",
        }
    created_at = created_at or envelope.execution_finished_at or envelope.execution_created_at
    checker_id = checker_contract["checker_id"]
    checker_version = checker_contract["checker_version"]
    checker_digest = _digest(checker_contract)
    checker_input_digest = raw_output.raw_response_digest
    checker_output_digest = _digest(checker_output)

    records = {
        "execution_envelope.json": _json_record(envelope),
        "frozen_input.json": _json_record(frozen_input),
        "raw_output.json": _json_record(raw_output),
        "atomic_observation.json": _json_record(observation),
        "ledger_entry.json": _json_record(ledger_entry),
        "checker_contract.json": checker_contract,
        "checker_input.json": {
            "raw_response_digest": raw_output.raw_response_digest,
            "http_status": raw_output.http_status,
            "raw_response": raw_output.raw_response.hex(),
        },
        "checker.json": checker_output,
    }
    for name, record in records.items():
        (root / name).write_bytes(_canonical(record))
    (root / "raw_response.bin").write_bytes(raw_output.raw_response)

    manifest = {
        "bundle_version": "0.2",
        "execution_id": envelope.execution_id,
        "execution_envelope_digest": envelope.digest,
        "frozen_input_digest": frozen_input.digest,
        "raw_output_digest": raw_output.digest,
        "raw_response_digest": raw_output.raw_response_digest,
        "atomic_observation_ids": [observation.observation_id],
        "ledger_entry_id": ledger_entry.ledger_entry_id,
        "checker_id": checker_id,
        "checker_version": checker_version,
        "checker_digest": checker_digest,
        "checker_input_digest": checker_input_digest,
        "checker_output_digest": checker_output_digest,
        "final_status": envelope.status,
        "created_at": created_at,
        "provenance": {
            "git_sha": envelope.git_sha,
            "workflow_sha": envelope.workflow_sha,
            "execution_id": envelope.execution_id,
            "input_digest": frozen_input.input_digest,
            "raw_response_digest": raw_output.raw_response_digest,
            "atomic_observation_id": observation.observation_id,
            "checker_digest": checker_digest,
            "checker_output_digest": checker_output_digest,
        },
    }
    manifest["bundle_digest"] = _digest(manifest)
    (root / "manifest.json").write_bytes(_canonical(manifest))
    return root
