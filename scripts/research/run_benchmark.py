#!/usr/bin/env python3
"""Deterministic exact-match benchmark for JAMP claim extraction.

This measures extraction only. It does not verify claims or infer truth.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from jamp.runtime.claim_extractor import extract_claims  # noqa: E402

DEFAULT_DATASET = ROOT / "benchmarks" / "claim_extraction_v1.json"
VALID_TYPES = {"price", "entity_existence", "prediction", "causal"}


def normalize_text(value: str) -> str:
    """Apply the benchmark's published, deterministic text normalization."""
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.strip().split()).casefold()


def load_dataset(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("benchmark_id") != "claim-extraction-v1":
        raise ValueError("Unsupported benchmark document or benchmark_id")
    if data.get("schema_version") != "1.0":
        raise ValueError("Unsupported schema_version")
    if data.get("matching") != "one_to_one_exact_normalized_text_and_type":
        raise ValueError("Unsupported matching contract")
    documents = data.get("documents")
    if not isinstance(documents, list) or len(documents) != 10:
        raise ValueError("Dataset must contain exactly 10 documents")
    seen_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("Each document must be an object")
        doc_id = document.get("id")
        text = document.get("text")
        gold = document.get("gold_claims")
        if not isinstance(doc_id, str) or not doc_id or doc_id in seen_ids:
            raise ValueError(f"Invalid or duplicate document id: {doc_id!r}")
        seen_ids.add(doc_id)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{doc_id}: text must be a non-empty string")
        if not isinstance(gold, list):
            raise ValueError(f"{doc_id}: gold_claims must be a list")
        for claim in gold:
            if not isinstance(claim, dict):
                raise ValueError(f"{doc_id}: each gold claim must be an object")
            claim_text = claim.get("text")
            claim_type = claim.get("type")
            if not isinstance(claim_text, str) or not claim_text.strip():
                raise ValueError(f"{doc_id}: gold claim text must be non-empty")
            if claim_type not in VALID_TYPES:
                raise ValueError(f"{doc_id}: unsupported gold claim type {claim_type!r}")
    return data


def score_document(document: dict[str, Any], candidate_types: set[str]) -> dict[str, Any]:
    # A stable trace ID makes claim IDs reproducible between benchmark runs.
    extracted = extract_claims(document["text"], trace_id=document["id"])
    predicted = [
        {"text": claim.text, "type": claim.claim_type}
        for claim in extracted
        if claim.claim_type in candidate_types
    ]
    gold = document["gold_claims"]

    # Counter intersection implements one-to-one matching: each occurrence can
    # match at most one occurrence on the other side, including duplicate spans.
    predicted_keys = Counter((normalize_text(row["text"]), row["type"]) for row in predicted)
    gold_keys = Counter((normalize_text(row["text"]), row["type"]) for row in gold)
    matched = predicted_keys & gold_keys
    tp = sum(matched.values())
    fp = sum((predicted_keys - matched).values())
    fn = sum((gold_keys - matched).values())
    return {
        "document_id": document["id"],
        "predicted_count": sum(predicted_keys.values()),
        "gold_count": sum(gold_keys.values()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "unmatched_predictions": [
            {"text": text, "type": claim_type, "count": count}
            for (text, claim_type), count in sorted((predicted_keys - matched).items())
        ],
        "unmatched_gold": [
            {"text": text, "type": claim_type, "count": count}
            for (text, claim_type), count in sorted((gold_keys - matched).items())
        ],
    }


def calculate_metrics(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def run_benchmark(dataset_path: Path) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    candidate_types = set(dataset["candidate_types"])
    if candidate_types != VALID_TYPES:
        raise ValueError("candidate_types must exactly match the supported claim types")
    details = [
        score_document(document, candidate_types)
        for document in dataset["documents"]
    ]
    totals = {
        key: sum(row[key] for row in details)
        for key in ("tp", "fp", "fn")
    }
    return {
        "benchmark_id": dataset["benchmark_id"],
        "schema_version": dataset["schema_version"],
        "dataset": str(dataset_path),
        "document_count": len(details),
        "matching": dataset["matching"],
        "normalization": dataset["normalization"],
        "excluded_type": "other",
        "metrics": calculate_metrics(**totals),
        "documents": details,
        "interpretation": (
            "Extraction-only result on this fixed 10-document control corpus; "
            "not a claim-verification accuracy score or a broad quality guarantee."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for a JSON copy of the result; stdout is always emitted.",
    )
    args = parser.parse_args()
    result = run_benchmark(args.dataset)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
