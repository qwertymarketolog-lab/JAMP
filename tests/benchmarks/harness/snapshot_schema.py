"""Deterministic JSON snapshot schema for P23.0-B cold replay."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jamp.research.evidence import EvidenceLedger
from jamp.research.hypothesis_formation import Hypothesis
from jamp.research.lineage_graph import LineageGraph

SCHEMA_VERSION = "P23.0-B-COLD-REPLAY-1.0.0"


def dump_snapshot(
    graph: LineageGraph,
    ledger: EvidenceLedger,
    hypotheses: list[Hypothesis],
    path: Path,
) -> None:
    """Persist exported domain artifacts to a versioned JSON envelope."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "graph": graph.export(),
        "ledger": ledger.export(),
        "hypotheses": [hypothesis.export() for hypothesis in hypotheses],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load and validate the versioned cold-replay envelope."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported cold replay snapshot schema")
    for key in ("graph", "ledger", "hypotheses"):
        if key not in payload:
            raise ValueError(f"cold replay snapshot missing {key}")
    return payload
