"""Pure, fail-closed checks for E2 OpenRouter generation provenance.

This module performs no network calls and does not qualify a model. It only
checks whether provider metadata matches identifiers recorded by JAMP.
"""

from __future__ import annotations

from typing import Any


def verify_generation_provenance(
    execution_details: Any,
    generation_response: Any,
) -> dict[str, str]:
    """Compare persisted JAMP provenance with a generation-metadata response.

    The provider response ID and served model ID must both be present and match
    exactly. Missing or malformed evidence is INCONCLUSIVE; mismatches are
    CONTRADICTED. A VERIFIED result is limited to this metadata comparison and
    is not model qualification.
    """
    if not isinstance(execution_details, dict):
        return {"status": "INCONCLUSIVE", "reason": "EXECUTION_DETAILS_INVALID"}

    if not isinstance(generation_response, dict):
        return {"status": "INCONCLUSIVE", "reason": "GENERATION_RESPONSE_INVALID"}

    metadata = generation_response.get("data", generation_response)
    if not isinstance(metadata, dict):
        return {"status": "INCONCLUSIVE", "reason": "GENERATION_METADATA_INVALID"}

    expected_id = execution_details.get("provider_response_id")
    observed_id = metadata.get("id")
    expected_model = execution_details.get("provider_model_id")
    observed_model = metadata.get("model")

    if not all(
        isinstance(value, str) and value.strip()
        for value in (expected_id, observed_id, expected_model, observed_model)
    ):
        return {"status": "INCONCLUSIVE", "reason": "REQUIRED_PROVENANCE_MISSING"}

    if expected_id != observed_id:
        return {"status": "CONTRADICTED", "reason": "PROVIDER_RESPONSE_ID_MISMATCH"}

    if expected_model != observed_model:
        return {"status": "CONTRADICTED", "reason": "PROVIDER_MODEL_ID_MISMATCH"}

    return {"status": "VERIFIED", "reason": "GENERATION_METADATA_MATCH"}
