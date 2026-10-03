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
) -> Path:
    """Write a self-contained immutable bundle and refuse overwrite."""
    root = Path(path)
    if root.exists():
        raise FileExistsError(f"immutable bundle already exists: {root}")
    root.mkdir(parents=True)
    records = {
        "execution_envelope.json": _json_record(envelope),
        "frozen_input.json": _json_record(frozen_input),
        "raw_output.json": _json_record(raw_output),
        "atomic_observation.json": _json_record(observation),
        "ledger_entry.json": _json_record(ledger_entry),
    }
    for name, record in records.items():
        (root / name).write_bytes(_canonical(record))
    (root / "raw_response.bin").write_bytes(raw_output.raw_response)
    manifest = {
        "bundle_version": "0.1",
        "execution_id": envelope.execution_id,
        "execution_envelope_digest": envelope.digest,
        "frozen_input_digest": frozen_input.digest,
        "raw_output_digest": raw_output.digest,
        "raw_response_digest": raw_output.raw_response_digest,
        "atomic_observation_ids": [observation.observation_id],
        "ledger_entry_id": ledger_entry.ledger_entry_id,
        "final_status": envelope.status,
    }
    manifest["bundle_digest"] = _digest(manifest)
    (root / "manifest.json").write_bytes(_canonical(manifest))
    return root
