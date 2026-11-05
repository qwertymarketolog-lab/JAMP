"""Fail-closed orchestration for provenance, signature, and temporal checks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .provenance import check_provenance
from .signature import check_signature
from .temporal import check_signature_from_snapshot, load_generation_snapshot


def _result(
    status: str, package_name: str, sample_id: str | None, **details: Any
) -> dict[str, Any]:
    return {
        "status": status,
        "package": package_name,
        "sample_id": sample_id,
        **details,
    }


def verify_code(
    code_str: str,
    package_name: str,
    temporal_snapshot: str | Path | None = None,
    sample_id: str | None = None,
) -> dict[str, Any]:
    """Verify generated code against package provenance and a wheel signature.

    When a temporal snapshot is supplied, its manifest and the selected wheel
    are verified before signature inspection. A wheel SHA mismatch is an
    integrity violation, never an ordinary inconclusive signature result.
    """
    if not isinstance(code_str, str) or not code_str.strip():
        return _result("INCONCLUSIVE", package_name, sample_id, reason="invalid_code")
    if not isinstance(package_name, str) or not package_name.strip():
        return _result("INCONCLUSIVE", package_name, sample_id, reason="invalid_package_name")
    if sample_id is not None and (not isinstance(sample_id, str) or not sample_id.strip()):
        return _result("INCONCLUSIVE", package_name, sample_id, reason="invalid_sample_id")

    try:
        provenance = check_provenance(package_name)
    except Exception as exc:  # fail closed at the orchestration boundary
        return _result(
            "INCONCLUSIVE", package_name, sample_id,
            reason="provenance_check_failed", error_type=type(exc).__name__,
        )
    if not isinstance(provenance, dict):
        return _result("INCONCLUSIVE", package_name, sample_id, reason="invalid_provenance_result")

    provenance_status = provenance.get("status")
    if provenance_status in {"NOT_FOUND", "SUSPICIOUS"}:
        return _result(
            "HALLUCINATION_CAUGHT", package_name, sample_id,
            reason=(
                "package_not_found"
                if provenance_status == "NOT_FOUND"
                else "provenance_suspicious"
            ),
            provenance=provenance,
        )

    if temporal_snapshot is None:
        try:
            signature = check_signature(code_str, package_name)
        except Exception as exc:  # fail closed at the orchestration boundary
            return _result(
                "INCONCLUSIVE", package_name, sample_id, provenance=provenance,
                reason="signature_check_failed", error_type=type(exc).__name__,
            )
    else:
        if not isinstance(temporal_snapshot, (str, Path)):
            return _result(
                "INCONCLUSIVE", package_name, sample_id, provenance=provenance,
                reason="invalid_temporal_snapshot_path",
            )
        snapshot_path = Path(temporal_snapshot)
        try:
            snapshot = load_generation_snapshot(snapshot_path)
            records = snapshot.get("_packages_by_sample")
            if not isinstance(records, dict):
                return _result(
                    "INCONCLUSIVE", package_name, sample_id, provenance=provenance,
                    reason="temporal_snapshot_index_missing",
                )
            if sample_id is not None:
                record = records.get(sample_id)
            else:
                matches = [
                    item for item in records.values()
                    if isinstance(item, dict) and item.get("package_name") == package_name
                ]
                record = matches[0] if len(matches) == 1 else None
            signature = check_signature_from_snapshot(
                code_str, package_name, record, snapshot_path.parent
            )
        except ValueError as exc:
            if "SHA-256 mismatch" in str(exc):
                return _result(
                    "INTEGRITY_VIOLATED", package_name, sample_id,
                    provenance=provenance, reason="temporal_snapshot_sha256_mismatch",
                    error_type=type(exc).__name__,
                )
            return _result(
                "INCONCLUSIVE", package_name, sample_id, provenance=provenance,
                reason="temporal_snapshot_invalid", error_type=type(exc).__name__,
            )
        except Exception as exc:
            return _result(
                "INCONCLUSIVE", package_name, sample_id, provenance=provenance,
                reason="temporal_snapshot_unavailable", error_type=type(exc).__name__,
            )

    if not isinstance(signature, dict):
        return _result(
            "INCONCLUSIVE", package_name, sample_id, provenance=provenance,
            reason="invalid_signature_result",
        )
    if signature.get("reason") == "temporal_wheel_sha256_mismatch":
        return _result(
            "INTEGRITY_VIOLATED", package_name, sample_id,
            provenance=provenance, signature=signature,
            reason="temporal_wheel_sha256_mismatch",
        )
    if signature.get("status") == "INVALID_SIGNATURE":
        return _result(
            "HALLUCINATION_CAUGHT", package_name, sample_id,
            provenance=provenance, signature=signature,
            reason="invalid_package_signature",
        )
    if provenance_status == "INCONCLUSIVE" or signature.get("status") == "INCONCLUSIVE":
        return _result(
            "INCONCLUSIVE", package_name, sample_id,
            provenance=provenance, signature=signature,
            reason=signature.get("reason", provenance.get("reason", "evidence_inconclusive")),
        )
    if provenance_status == "TRUSTED" and signature.get("status") == "EXISTS":
        return _result(
            "CLEAN", package_name, sample_id,
            provenance=provenance, signature=signature,
        )
    return _result(
        "INCONCLUSIVE", package_name, sample_id,
        provenance=provenance, signature=signature,
        reason="evidence_did_not_satisfy_clean_contract",
    )
