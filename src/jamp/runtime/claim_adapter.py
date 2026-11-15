"""Map extracted claim candidates into the E4 intermediate dictionary contract.

This adapter preserves extractor output only. It does not assign a verdict,
source, evidence, or criticality.
"""

from __future__ import annotations

from typing import Any

from jamp.runtime.claim_extractor import Claim as ExtractorClaim


def to_verdict_claim(extracted: ExtractorClaim, trace_id: str) -> dict[str, Any]:
    """Convert an extracted candidate into the explicit E4 intermediate shape."""
    if not trace_id or not trace_id.strip():
        raise ValueError("trace_id must be non-empty")

    return {
        "claim_id": f"{trace_id}_{extracted.id}",
        "type": extracted.claim_type,
        "value": extracted.cited_value,
        "unit": extracted.currency if extracted.currency is not None else "UNKNOWN",
        "raw_text": extracted.text,
        "citation_url": extracted.citation_url,
        "status": None,
        "source": None,
        "evidence": None,
        "critical": None,
    }
