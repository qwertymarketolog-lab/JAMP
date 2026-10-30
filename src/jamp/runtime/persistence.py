from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

GENESIS_HASH = "sha256:" + "0" * 64
CHAIN_METADATA_KEYS = frozenset({"prev_hash", "record_hash"})


class ChainIntegrityError(RuntimeError):
    """Raised when a persisted JSONL hash chain is broken or inconsistent."""


def _record_canonical_bytes(record: dict[str, Any]) -> bytes:
    body = {k: v for k, v in record.items() if k != "record_hash"}
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _record_hash(record: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_record_canonical_bytes(record)).hexdigest()


def _strip_chain_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in CHAIN_METADATA_KEYS}


class AuditPersistence:
    """Synchronous append-only JSONL persistence with fsync durability.

    Every record carries a hash chain:
    - prev_hash points to the previous record's record_hash
      (or GENESIS_HASH for the first chained record)
    - record_hash is sha256 of the canonical record without record_hash

    Legacy files (created before hash chaining) have no chain metadata.
    New writes after legacy records start a fresh chain from GENESIS_HASH;
    legacy records are not retroactively chained. A legacy record that
    appears *after* the chain started is treated as corruption.

    Chain verification is O(N) per read; acceptable for v0.
    Multi-process concurrent writes are not serialized — single-writer
    assumption.
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
    ) -> None:
        if storage_path is None:
            default_dir = Path(tempfile.gettempdir()) / "jamp" / "audit"
            storage_path = os.environ.get(
                "JAMP_AUDIT_PATH", str(default_dir / "provenance_traces.jsonl")
            )
        self.storage_path = Path(storage_path)
        self.verdicts_path = self.storage_path.parent / "verdicts.jsonl"
        self.universal_verdicts_path = self.storage_path.parent / "universal_verdicts.jsonl"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- chain helpers ----

    def _read_all_records(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                out.append(json.loads(line))
        return out

    def _verify_chain(self, records: list[dict[str, Any]]) -> None:
        expected_prev = GENESIS_HASH
        chain_started = False
        for rec in records:
            has_chain = any(k in rec for k in CHAIN_METADATA_KEYS)
            if not has_chain:
                if chain_started:
                    raise ChainIntegrityError(
                        f"legacy record after chain started: "
                        f"trace_id={rec.get('trace_id')!r}"
                    )
                continue
            chain_started = True
            if rec.get("prev_hash") != expected_prev:
                raise ChainIntegrityError(
                    f"chain broken at trace_id={rec.get('trace_id')!r}"
                )
            if rec.get("record_hash") != _record_hash(rec):
                raise ChainIntegrityError(
                    f"record_hash mismatch at trace_id={rec.get('trace_id')!r}"
                )
            expected_prev = rec["record_hash"]

    def _head_hash(self, path: Path) -> str:
        records = self._read_all_records(path)
        self._verify_chain(records)
        head = GENESIS_HASH
        for rec in records:
            if rec.get("record_hash"):
                head = rec["record_hash"]
        return head

    def _append_chained(self, path: Path, payload: dict[str, Any]) -> None:
        prev = self._head_hash(path)
        record = {**payload, "prev_hash": prev}
        record["record_hash"] = _record_hash(record)
        serialized = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

    def _read_chained_by_id(
        self,
        path: Path,
        trace_id: str,
        *,
        last_wins: bool,
    ) -> dict[str, Any] | None:
        records = self._read_all_records(path)
        self._verify_chain(records)
        match: dict[str, Any] | None = None
        for rec in records:
            if rec.get("trace_id") != trace_id:
                continue
            if last_wins:
                match = rec
            else:
                return _strip_chain_metadata(rec)
        if match is not None:
            return _strip_chain_metadata(match)
        return None

    # ---- public write/read ----

    def write_trace(self, trace_payload: dict[str, Any]) -> str:
        trace_id = trace_payload.get("trace_id", "")
        if not trace_id:
            raise ValueError("Trace payload missing required 'trace_id' field.")
        self._append_chained(self.storage_path, trace_payload)
        return trace_id

    def read_trace_by_id(self, trace_id: str) -> dict[str, Any] | None:
        return self._read_chained_by_id(
            self.storage_path, trace_id, last_wins=False
        )

    def write_verdict(
        self,
        trace_id: str,
        verdict_payload: dict[str, Any],
    ) -> str:
        if not trace_id:
            raise ValueError("Verdict trace_id must not be empty.")
        record = {**verdict_payload, "trace_id": trace_id}
        self._append_chained(self.verdicts_path, record)
        return trace_id

    def read_verdict_by_id(self, trace_id: str) -> dict[str, Any] | None:
        if not trace_id:
            return None
        return self._read_chained_by_id(
            self.verdicts_path, trace_id, last_wins=False
        )

    def write_universal_verdict(self, trace_id: str, payload: dict[str, Any]) -> str:
        """Append-only persistence of a UniversalVerdict envelope.

        Re-POST with the same trace_id appends a new record;
        read_universal_verdict_by_id returns the last matching record.
        """
        if not trace_id:
            raise ValueError("write_universal_verdict requires non-empty trace_id")
        body = dict(payload)
        body["trace_id"] = trace_id
        self._append_chained(self.universal_verdicts_path, body)
        return trace_id

    def read_universal_verdict_by_id(self, trace_id: str) -> dict[str, Any] | None:
        return self._read_chained_by_id(
            self.universal_verdicts_path, trace_id, last_wins=True
        )
