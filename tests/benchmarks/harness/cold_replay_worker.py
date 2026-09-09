"""Fresh-process worker for P23.0-B cold replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jamp.research.evidence import EvidenceRecord, build_evidence_ledger
from jamp.research.hypothesis_formation import Hypothesis
from jamp.research.hypothesis_scoring import score_hypothesis
from jamp.research.lineage_graph import LineageNode, build_lineage_graph
from tests.benchmarks.harness.snapshot_schema import load_snapshot


def _restore(payload: dict[str, object]):
    graph_data = payload["graph"]
    graph_nodes = tuple(
        LineageNode(item["node_hash"], tuple(item["parents"]))
        for item in graph_data["nodes"]
    )
    graph = build_lineage_graph(graph_nodes)

    ledger_data = payload["ledger"]
    records: list[EvidenceRecord] = []
    for item in ledger_data["records"]:
        record = EvidenceRecord(
            source_hash=item["source_hash"],
            payload_hash=item["payload_hash"],
            state_hash=item["state_hash"],
            sequence=item["sequence"],
        )
        if item["evidence_hash"] != record.evidence_hash:
            object.__setattr__(record, "evidence_hash", item["evidence_hash"])
        records.append(record)
    ledger = build_evidence_ledger(records)

    hypotheses = tuple(
        Hypothesis(
            evidence_refs=tuple(item["evidence_refs"]),
            state_hash=item["state_hash"],
            proposition=item["proposition"],
            sequence=item["sequence"],
        )
        for item in payload["hypotheses"]
    )
    return graph, ledger, hypotheses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        graph, ledger, hypotheses = _restore(load_snapshot(args.snapshot))
        scores = {
            f"H{index}": score_hypothesis(hypothesis, ledger, graph)
            for index, hypothesis in enumerate(hypotheses, start=1)
        }
        output = {"status": "OK", "scores": scores}
    except Exception as exc:  # transport exception across process boundary
        output = {
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
