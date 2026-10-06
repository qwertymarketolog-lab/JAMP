from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class AuditPersistence:
    """Synchronous append-only JSONL persistence with fsync durability."""

    def __init__(
        self,
        storage_path: str | Path = "artifacts/audit/provenance_traces.jsonl",
    ) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def write_trace(self, trace_payload: dict[str, Any]) -> str:
        trace_id = trace_payload.get("trace_id", "")
        if not trace_id:
            raise ValueError("Trace payload missing required 'trace_id' field.")

        serialized_entry = json.dumps(
            trace_payload,
            ensure_ascii=False,
            sort_keys=True,
        ) + "\n"
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(serialized_entry)
            handle.flush()
            os.fsync(handle.fileno())
        return trace_id

    def read_trace_by_id(self, trace_id: str) -> dict[str, Any] | None:
        if not self.storage_path.exists():
            return None

        with self.storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("trace_id") == trace_id:
                    return record
        return None
