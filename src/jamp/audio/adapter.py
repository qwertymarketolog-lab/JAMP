"""Fail-closed adapter boundary for audio analyzer inference.

This module does not bundle or select a model. Callers must supply an explicit
inference function and a trusted weights digest from an independently managed
manifest. No inference is performed until weights and target bytes are verified.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
    metrics: Mapping[str, float] | None = None


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(
    *,
    target_path: str | Path,
    expected_target_sha256: str,
    weights_path: str | Path,
    expected_weights_sha256: str,
    model_id: str,
    model_version: str,
    infer: Callable[[Path, Path], Any],
) -> EvidenceResult:
    """Validate trusted hashes before calling infer, then preserve raw output."""
    weights = Path(weights_path)
    if not weights.is_file():
        return EvidenceResult(
            HOLD, "weights_missing", model_id=model_id, model_version=model_version
        )
    try:
        weights_digest = sha256_file(weights)
    except OSError:
        return EvidenceResult(
            HOLD, "weights_unreadable", model_id=model_id, model_version=model_version
        )
    if weights_digest.lower() != expected_weights_sha256.lower():
        return EvidenceResult(
            HOLD, "weights_sha256_mismatch", weights_sha256=weights_digest,
            model_id=model_id, model_version=model_version,
        )

    target = Path(target_path)
    if not target.is_file():
        return EvidenceResult(
            REFUSE, "target_missing", weights_sha256=weights_digest,
            model_id=model_id, model_version=model_version,
        )
    try:
        target_digest = sha256_file(target)
    except OSError:
        return EvidenceResult(
            REFUSE, "target_unreadable", weights_sha256=weights_digest,
            model_id=model_id, model_version=model_version,
        )
    if target_digest.lower() != expected_target_sha256.lower():
        return EvidenceResult(
            REFUSE, "target_sha256_mismatch", target_sha256=target_digest,
            weights_sha256=weights_digest,
            model_id=model_id,
            model_version=model_version,
        )

    try:
        raw = infer(target, weights)
    except Exception as exc:
        return EvidenceResult(
            INCONCLUSIVE, f"inference_error:{type(exc).__name__}",
            target_sha256=target_digest, weights_sha256=weights_digest,
            model_id=model_id, model_version=model_version,
        )
    if not isinstance(raw, Mapping) or not raw:
        return EvidenceResult(
            INCONCLUSIVE, "empty_or_invalid_model_output",
            target_sha256=target_digest, weights_sha256=weights_digest,
            model_id=model_id, model_version=model_version, raw_output=raw,
        )

    required = ("ai_generated_probability", "human_performance_probability")
    values: dict[str, float] = {}
    for key in required:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return EvidenceResult(
                INCONCLUSIVE, f"missing_or_invalid_metric:{key}",
                target_sha256=target_digest, weights_sha256=weights_digest,
                model_id=model_id, model_version=model_version, raw_output=raw,
            )
        number = float(value)
        if not math.isfinite(number):
            return EvidenceResult(
                REFUSE, f"non_finite_metric:{key}",
                target_sha256=target_digest, weights_sha256=weights_digest,
                model_id=model_id, model_version=model_version, raw_output=raw,
            )
        if not 0.0 <= number <= 1.0:
            return EvidenceResult(
                REFUSE, f"out_of_range_metric:{key}",
                target_sha256=target_digest, weights_sha256=weights_digest,
                model_id=model_id, model_version=model_version, raw_output=raw,
            )
        values[key] = number

    return EvidenceResult(
        VERIFIED, "hashes_and_metrics_valid", target_sha256=target_digest,
        weights_sha256=weights_digest, model_id=model_id, model_version=model_version,
        raw_output=raw, metrics=values,
    )
