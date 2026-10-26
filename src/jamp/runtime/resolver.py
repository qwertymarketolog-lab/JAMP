from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CAPABILITY_MAP = {
    "search_and_extraction": ("C01", "C06"),
    "tool_execution_agent": ("C02", "C05"),
    "long_context_analysis": ("C03", "C08"),
    "strict_compliance_safety": ("C04", "C07", "C09"),
}

CANONICAL_ARTIFACT_ID = 11369355096
CANONICAL_RAW_EVIDENCE_SHA256 = "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
CANONICAL_ARCHIVE_SHA256 = "2f5282d40c087a0065dfbd9c59abc9c4cd79f2780f556ae5a18ef9ff1a75289f"
CANONICAL_MANIFEST_SHA256 = "e208f0e8565815020e5718191f61075f1eb95282052c75c4ca0a80ed07c12ed6"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
EXPECTED_MATRIX_GIT_BLOB_SHA = "ad5ac0d4cab10b64b0a629ec6433ad0dacd935c5"
STATUS_VALUES = {"VERIFIED", "CONTRADICTED", "INCONCLUSIVE"}
CAPABILITY_IDS = tuple(f"C{i:02}" for i in range(1, 11))
PILOT_MODEL_ID = "z-ai/glm-5.3-flash"
PILOT_BENCHMARK_VERSION = "v1"

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_MATRIX_PATH = (
    _REPOSITORY_ROOT
    / "artifacts"
    / "research"
    / "jamp_task_scoped_derived_matrix_v2.json"
)
_PILOT_MODELS_PATH = _REPOSITORY_ROOT / "data" / "projections" / "pilot_models.json"


def _git_blob_sha(data: bytes) -> str:
    """Return Git's content-addressed SHA-1 for a blob, including its header."""
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _validate_matrix(matrix: dict[str, Any]) -> None:
    """Validate provenance, the complete 17x10 matrix, and all derived profile pools."""
    if matrix.get("schema_version") != "jamp-task-scoped-derived-matrix-v2":
        raise ValueError("Unsupported task-scoped capability matrix")

    anchor = matrix.get("evidence_anchor")
    if not isinstance(anchor, dict) or (
        anchor.get("artifact_id"),
        anchor.get("artifact_sha256"),
        anchor.get("canonical_manifest_sha256"),
    ) != (CANONICAL_ARTIFACT_ID, CANONICAL_ARCHIVE_SHA256, CANONICAL_MANIFEST_SHA256):
        raise ValueError("Capability matrix canonical evidence anchor mismatch")

    frozen_core = matrix.get("frozen_core")
    if not isinstance(frozen_core, dict) or (
        frozen_core.get("path"),
        frozen_core.get("blob"),
        frozen_core.get("delta"),
    ) != ("src/jamp/run.py", FROZEN_CORE_BLOB, 0):
        raise ValueError("Frozen Core anchor mismatch")

    contract = matrix.get("source_contract")
    if not isinstance(contract, dict) or contract != {
        "expected_models": 17,
        "executed_models": 17,
        "expected_checks": 170,
        "executed_checks": 170,
    }:
        raise ValueError("Capability matrix source contract is incomplete")

    rows = matrix.get("matrix")
    if not isinstance(rows, list) or len(rows) != 17:
        raise ValueError("Capability matrix must contain exactly 17 models")

    ids: list[str] = []
    row_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Capability matrix row is invalid")
        model_id = row.get("model_id")
        if not isinstance(model_id, str) or "/" not in model_id or model_id.startswith("m"):
            raise ValueError("Capability matrix contains a non-canonical provider model ID")
        if model_id in row_by_id:
            raise ValueError("Capability matrix contains duplicate provider model IDs")
        ids.append(model_id)
        row_by_id[model_id] = row

        capabilities = row.get("capabilities")
        if not isinstance(capabilities, dict) or set(capabilities) != set(CAPABILITY_IDS):
            raise ValueError("Capability matrix row does not contain exactly C01-C10")
        if any(status not in STATUS_VALUES for status in capabilities.values()):
            raise ValueError("Capability matrix contains an unknown evidence status")

        row_profiles = row.get("task_profiles")
        if not isinstance(row_profiles, dict) or set(row_profiles) != set(CAPABILITY_MAP):
            raise ValueError("Capability matrix row has an incomplete task-profile projection")
        for profile, required in CAPABILITY_MAP.items():
            expected_action = (
                "EXECUTE"
                if all(capabilities.get(capability) == "VERIFIED" for capability in required)
                else "REFUSE"
            )
            if row_profiles.get(profile) != expected_action:
                raise ValueError("Capability matrix profile decision disagrees with raw statuses")

    if sorted(row.get("ordinal") for row in rows) != list(range(1, 18)):
        raise ValueError("Capability matrix ordinals are incomplete or duplicated")

    profiles = matrix.get("task_profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(CAPABILITY_MAP):
        raise ValueError("Capability matrix task profiles are incomplete")
    for profile, required in CAPABILITY_MAP.items():
        profile_doc = profiles.get(profile)
        if not isinstance(profile_doc, dict):
            raise ValueError("Capability matrix task profile is invalid")
        if profile_doc.get("required_capabilities") != list(required):
            raise ValueError("Capability matrix required capabilities disagree with resolver")
        expected_ids = [
            row["model_id"]
            for row in rows
            if all(row["capabilities"].get(capability) == "VERIFIED" for capability in required)
        ]
        if profile_doc.get("eligible_models") != expected_ids:
            raise ValueError(
                "Capability matrix eligible pool disagrees with canonical raw statuses"
            )
        if profile_doc.get("eligible_model_count") != len(expected_ids):
            raise ValueError("Capability matrix eligible pool count is inconsistent")


def _load_derived_matrix() -> dict[str, Any]:
    try:
        raw = _MATRIX_PATH.read_bytes()
    except OSError as exc:
        raise ValueError("Capability matrix is unavailable") from exc

    if _git_blob_sha(raw) != EXPECTED_MATRIX_GIT_BLOB_SHA:
        raise ValueError("Capability matrix integrity mismatch")

    try:
        matrix = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Capability matrix JSON is invalid") from exc
    if not isinstance(matrix, dict):
        raise ValueError("Capability matrix root must be an object")
    _validate_matrix(matrix)
    return matrix


def _load_pilot_models() -> dict[str, Any]:
    """Load the isolated pilot profile; malformed or missing data never authorizes routing."""
    try:
        document = json.loads(_PILOT_MODELS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Pilot model profile is unavailable or invalid") from exc
    if not isinstance(document, dict) or document.get("schema_version") != "jamp-pilot-models-v1":
        raise ValueError("Pilot model profile schema is invalid")
    models = document.get("models")
    if not isinstance(models, dict):
        raise ValueError("Pilot model profile models are invalid")
    model = models.get(PILOT_MODEL_ID)
    if not isinstance(model, dict) or model.get("provider") != "openrouter":
        raise ValueError("GLM pilot model entry is invalid")
    profiles = model.get("task_profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(CAPABILITY_MAP):
        raise ValueError("GLM pilot task profile set is invalid")
    search = profiles.get("search_and_extraction")
    if not isinstance(search, dict):
        raise ValueError("GLM search pilot profile is invalid")
    if (
        search.get("status") != "QUALIFIED"
        or search.get("benchmark_version") != PILOT_BENCHMARK_VERSION
        or search.get("score") != 1.0
        or model.get("evidence_ref")
        != "src/jamp/runtime/measured_benchmarks.json#/z-ai~1glm-5.3-flash/search_and_extraction"
    ):
        raise ValueError("GLM search pilot profile evidence reference is invalid")
    for profile in CAPABILITY_MAP:
        if profile != "search_and_extraction":
            item = profiles.get(profile)
            if not isinstance(item, dict) or item.get("status") != "NOT_APPROVED":
                raise ValueError("GLM pilot profile must deny unapproved tasks")
    return document


class CapabilityResolver:
    def get_required_capabilities(self, task_profile: str) -> tuple[str, ...]:
        try:
            return CAPABILITY_MAP[task_profile]
        except KeyError as exc:
            raise ValueError(f"Unknown task profile: {task_profile}") from exc

    def validate_projection(self, evidence_path: str | Path) -> None:
        """Fail closed unless all 170 fixture statuses match the pinned canonical matrix."""
        matrix = _load_derived_matrix()
        try:
            projection = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Runtime evidence projection is unavailable or invalid") from exc
        if not isinstance(projection, dict):
            raise ValueError("Runtime evidence projection root must be an object")

        source = projection.get("source")
        if not isinstance(source, dict) or (
            source.get("artifact_id"),
            source.get("sha256"),
            source.get("manifest_sha256"),
        ) != (
            CANONICAL_ARTIFACT_ID,
            CANONICAL_RAW_EVIDENCE_SHA256,
            CANONICAL_MANIFEST_SHA256,
        ):
            raise ValueError("Runtime evidence projection source identity mismatch")
        if projection.get("frozen_core_blob") != FROZEN_CORE_BLOB:
            raise ValueError("Runtime evidence projection Frozen Core mismatch")

        projected_rows = projection.get("models")
        canonical_rows = matrix["matrix"]
        if not isinstance(projected_rows, list) or len(projected_rows) != 17:
            raise ValueError("Runtime evidence projection must contain exactly 17 models")
        projected_ids = [
            row.get("model_id") if isinstance(row, dict) else None for row in projected_rows
        ]
        canonical_ids = [row["model_id"] for row in canonical_rows]
        if projected_ids != canonical_ids:
            raise ValueError(
                "Runtime evidence projection provider IDs disagree with canonical matrix"
            )

        for projected, canonical in zip(projected_rows, canonical_rows, strict=True):
            checks = projected.get("checks")
            if not isinstance(checks, dict) or set(checks) != set(CAPABILITY_IDS):
                raise ValueError("Runtime evidence projection does not contain exactly 170 checks")
            for capability in CAPABILITY_IDS:
                check = checks[capability]
                if (
                    not isinstance(check, dict)
                    or check.get("raw_status") != canonical["capabilities"][capability]
                ):
                    raise ValueError(
                        "Runtime evidence projection status disagrees with canonical matrix"
                    )

    def get_eligible_models(self, task_profile: str) -> tuple[str, ...]:
        self.get_required_capabilities(task_profile)
        matrix = _load_derived_matrix()
        try:
            models = tuple(matrix["task_profiles"][task_profile]["eligible_models"])
        except (KeyError, TypeError) as exc:
            raise ValueError("Capability matrix task profile is invalid") from exc

        # The pilot is an isolated, versioned route. It replaces one slot in the
        # search pool, preserving the canonical selector's expected pool size and
        # leaving the pinned 17-model/170-check matrix untouched.
        if task_profile == "search_and_extraction":
            pilot = _load_pilot_models()["models"][PILOT_MODEL_ID]
            search = pilot["task_profiles"]["search_and_extraction"]
            from jamp.runtime.qualification import evaluate_model_qualification

            if (
                search["status"] == "QUALIFIED"
                and evaluate_model_qualification(
                    PILOT_MODEL_ID,
                    task_profile,
                    required_benchmark_version=PILOT_BENCHMARK_VERSION,
                )
                == "QUALIFIED"
            ):
                if not models:
                    raise ValueError("Cannot select pilot model from an empty eligible pool")
                return (PILOT_MODEL_ID, *models[1:])
        return models
