"""Fail-closed adapter boundary for audio analyzer inference.

Inference receives the exact immutable byte strings whose digests were checked.
The caller supplies analyzer provenance; its presence is structural metadata, not
independent proof that the analyzer actually ran.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

VERIFIED = "VERIFIED"
HOLD = "HOLD"
REFUSE = "REFUSE"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class EvidenceResult:
    status: str
    reason: str
    target_sha256: str | None = None
    weights_sha256: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    raw_output: Any = None
    metrics: Mapping[str, Any] | None = None
    provenance: Mapping[str, str] | None = None


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file's current bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def analyze(
    *,
    target_path: str | Path,
    expected_target_sha256: str,
    weights_path: str | Path,
    expected_weights_sha256: str,
    model_id: str,
    model_version: str,
    tool_id: str,
    tool_version: str,
    analyzed_at: str,
    infer: Callable[[bytes, bytes], Any],
) -> EvidenceResult:
    """Verify bytes, validate required provenance, then infer from those bytes."""
    provenance = {
        "tool_id": tool_id,
        "tool_version": tool_version,
        "model_version": model_version,
        "analyzed_at": analyzed_at,
    }
    if not all(isinstance(value, str) and value.strip() for value in provenance.values()):
        return EvidenceResult(
            INCONCLUSIVE,
            "analyzer_provenance_incomplete",
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )
    if not _valid_timestamp(analyzed_at):
        return EvidenceResult(
            INCONCLUSIVE,
            "analyzer_timestamp_invalid",
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )

    weights = Path(weights_path)
    if not weights.is_file():
        return EvidenceResult(
            HOLD,
            "weights_missing",
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )
    try:
        weights_bytes = weights.read_bytes()
    except OSError:
        return EvidenceResult(
            HOLD,
            "weights_unreadable",
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )
    weights_digest = hashlib.sha256(weights_bytes).hexdigest()
    if weights_digest.lower() != expected_weights_sha256.lower():
        return EvidenceResult(
            HOLD,
            "weights_sha256_mismatch",
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )

    target = Path(target_path)
    if not target.is_file():
        return EvidenceResult(
            REFUSE,
            "target_missing",
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )
    try:
        target_bytes = target.read_bytes()
    except OSError:
        return EvidenceResult(
            REFUSE,
            "target_unreadable",
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )
    target_digest = hashlib.sha256(target_bytes).hexdigest()
    if target_digest.lower() != expected_target_sha256.lower():
        return EvidenceResult(
            REFUSE,
            "target_sha256_mismatch",
            target_sha256=target_digest,
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )

    try:
        raw = infer(target_bytes, weights_bytes)
    except Exception as exc:
        return EvidenceResult(
            INCONCLUSIVE,
            f"inference_error:{type(exc).__name__}",
            target_sha256=target_digest,
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            provenance=provenance,
        )
    if not isinstance(raw, Mapping) or not raw:
        return EvidenceResult(
            INCONCLUSIVE,
            "empty_or_invalid_model_output",
            target_sha256=target_digest,
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            raw_output=raw,
            provenance=provenance,
        )

    probability_keys = (
        "synthetic_probability",
        "human_performance_probability",
        "confidence_score",
    )
    values: dict[str, Any] = {}
    for key in probability_keys:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return EvidenceResult(
                INCONCLUSIVE,
                f"missing_or_invalid_metric:{key}",
                target_sha256=target_digest,
                weights_sha256=weights_digest,
                model_id=model_id,
                model_version=model_version,
                raw_output=raw,
                provenance=provenance,
            )
        number = float(value)
        if not math.isfinite(number):
            return EvidenceResult(
                REFUSE,
                f"non_finite_metric:{key}",
                target_sha256=target_digest,
                weights_sha256=weights_digest,
                model_id=model_id,
                model_version=model_version,
                raw_output=raw,
                provenance=provenance,
            )
        if not 0.0 <= number <= 1.0:
            return EvidenceResult(
                REFUSE,
                f"out_of_range_metric:{key}",
                target_sha256=target_digest,
                weights_sha256=weights_digest,
                model_id=model_id,
                model_version=model_version,
                raw_output=raw,
                provenance=provenance,
            )
        values[key] = number

    artifacts = raw.get("detected_artifacts")
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        return EvidenceResult(
            INCONCLUSIVE,
            "missing_or_invalid_metric:detected_artifacts",
            target_sha256=target_digest,
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
            raw_output=raw,
            provenance=provenance,
        )
    values["detected_artifacts"] = list(artifacts)

    if "notes" in raw:
        if not isinstance(raw["notes"], str):
            return EvidenceResult(
                INCONCLUSIVE,
                "missing_or_invalid_metric:notes",
                target_sha256=target_digest,
                weights_sha256=weights_digest,
                model_id=model_id,
                model_version=model_version,
                raw_output=raw,
                provenance=provenance,
            )
        values["notes"] = raw["notes"]

    return EvidenceResult(
        VERIFIED,
        "hashes_metrics_and_provenance_valid",
        target_sha256=target_digest,
        weights_sha256=weights_digest,
        model_id=model_id,
        model_version=model_version,
        raw_output=raw,
        metrics=values,
        provenance=provenance,
    )
