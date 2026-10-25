from __future__ import annotations

from collections.abc import Mapping

# Entries may be promoted to QUALIFIED only when backed by an independently
# reviewed benchmark record. A successful execution/E2 verification is not a
# model-quality benchmark and must not promote qualification by itself.
QUALIFICATION_REGISTRY: dict[tuple[str, str], str] = {
    ("z-ai/glm-5.3-flash", "search_and_extraction"): "UNKNOWN",
}


def evaluate_model_qualification(model_id: str, task_type: str) -> str:
    """Return the recorded qualification for an exact model/task pair.

    Missing or malformed identities fail closed to UNKNOWN. This registry
    intentionally does not infer quality from a successful individual request.
    """
    if not isinstance(model_id, str) or not model_id:
        return "UNKNOWN"
    if not isinstance(task_type, str) or not task_type:
        return "UNKNOWN"
    status = QUALIFICATION_REGISTRY.get((model_id, task_type), "UNKNOWN")
    return status if status in {"QUALIFIED", "UNKNOWN"} else "UNKNOWN"
