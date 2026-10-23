"""Pure, fail-closed checks for E2 OpenRouter generation provenance.

This module performs no network calls and does not qualify a model. It only
checks whether provider metadata matches identifiers recorded by JAMP.
"""

from __future__ import annotations

import re
from typing import Any


def verify_generation_provenance(
    execution_details: Any,
    generation_response: Any,
) -> dict[str, str]:
    """Compare persisted JAMP provenance with a generation-metadata response.

    Provider response IDs must match exactly. Model IDs must either match
    exactly or the observed provider model may add a date suffix (YYYYMMDD) to
    the recorded base model ID. Missing or malformed evidence is INCONCLUSIVE;
    other mismatches are CONTRADICTED. VERIFIED is limited to metadata
    correspondence and is not model qualification.
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

    if expected_model == observed_model:
        return {"status": "VERIFIED", "reason": "GENERATION_METADATA_MATCH"}

    # OpenRouter was observed returning a date-stamped served model ID for
    # JAMP's base model ID. Accept only this explicit suffix shape, not an
    # arbitrary startswith/prefix match.
    versioned_model = re.fullmatch(
        re.escape(expected_model) + r"-[0-9]{8}",
        observed_model,
    )
    if versioned_model:
        return {"status": "VERIFIED", "reason": "MODEL_DATE_SUFFIX_MATCH"}

    return {"status": "CONTRADICTED", "reason": "PROVIDER_MODEL_ID_MISMATCH"}
