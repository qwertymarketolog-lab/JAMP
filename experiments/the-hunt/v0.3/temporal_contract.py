"""Immutable pre-generation PyPI wheel snapshots for The Hunt v0.3.

The PyPI release metadata is observed immediately before each model request.
The selected wheel is downloaded after the response and accepted only when its
SHA-256 matches the digest already observed before generation. No package code
is installed or executed.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from provenance_checker import fetch_pypi_json
from signature_checker import _imports_and_calls, inspect_wheel_bytes

MAX_WHEEL_BYTES = 25 * 1024 * 1024
USER_AGENT = "JAMP-The-Hunt-v0.3-Temporal-Lock"
SNAPSHOT_SCHEMA = "jamp-hunt-generation-snapshot-v0.1"


def _wheel_compatible_with_cpython311_linux_x86_64(filename: str) -> bool:
    """Fail closed unless a wheel tag is compatible with the captured CI target."""
    if (
        platform.python_implementation() != "CPython"
        or sys.version_info[:2] != (3, 11)
        or platform.system() != "Linux"
        or platform.machine().lower() not in {"x86_64", "amd64"}
        or not filename.endswith(".whl")
        or Path(filename).name != filename
    ):
        return False
    parts = filename[:-4].rsplit("-", 4)
    if len(parts) != 5:
        return False
    python_tags, abi_tags, platform_tags = (
        parts[2].split("."),
        parts[3].split("."),
        parts[4].split("."),
    )
    supported_platform = any(
        tag == "any"
        or tag == "linux_x86_64"
        or (tag.startswith("manylinux") and tag.endswith("_x86_64"))
        for tag in platform_tags
    )
    return (
        supported_platform
        and any(tag in {"cp311", "py311", "py3"} for tag in python_tags)
        and any(tag in {"cp311", "abi3", "none"} for tag in abi_tags)
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def capture_generation_environment() -> dict[str, Any]:
    distributions = []
    for distribution in importlib.metadata.distributions():
        try:
            name = distribution.metadata["Name"]
            version = distribution.version
        except (KeyError, ValueError):
            continue
        if name and version:
            distributions.append({"package_name": name, "pypi_version": version})
    distributions.sort(key=lambda item: (item["package_name"].lower(), item["pypi_version"]))
    return {
        "captured_at_utc": utc_now(),
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "installed_distributions": distributions,
    }


def _upload_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def capture_pre_generation_release(
    package_name: str, generation_environment: dict[str, Any] | None = None
) -> dict[str, Any]:
    installed_versions = {
        item.get("pypi_version")
        for item in (generation_environment or {}).get("installed_distributions", [])
        if isinstance(item, dict)
        and re.sub(r"[-_.]+", "-", str(item.get("package_name", ""))).lower()
        == re.sub(r"[-_.]+", "-", package_name).lower()
        and isinstance(item.get("pypi_version"), str)
    }
    record: dict[str, Any] = {
        "package_name": package_name,
        "pypi_version": None,
        "wheel_filename": None,
        "wheel_sha256": None,
        "metadata_observed_timestamp_utc": None,
        "artifact_download_timestamp_utc": None,
        "resolution_status": "UNRESOLVED",
        "temporal_provenance": "UNRESOLVED",
        "generation_environment_version": None,
        "wheel_url": None,
        "wheel_relative_path": None,
        "wheel_sha256_observed": None,
    }
    try:
        status, metadata = fetch_pypi_json(package_name)
        if status != 200 or not isinstance(metadata, dict):
            record["resolution_reason"] = "pypi_metadata_unavailable"
            return record
        record["metadata_observed_timestamp_utc"] = utc_now()
        metadata_bytes = json.dumps(
            metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        record["pypi_metadata_sha256"] = hashlib.sha256(metadata_bytes).hexdigest()
        record["pypi_metadata_hash_method"] = "canonical_json_utf8_sorted_compact"
        releases = metadata.get("releases")
        if not isinstance(releases, dict):
            record["resolution_reason"] = "pypi_releases_missing"
            return record
        if len(installed_versions) > 1:
            record["resolution_reason"] = "multiple_generation_environment_versions"
            return record
        installed_version = next(iter(installed_versions), None)
        if installed_version is not None:
            record["generation_environment_version"] = installed_version
            if installed_version not in releases:
                record["resolution_reason"] = "installed_generation_version_not_on_pypi"
                return record
            selected_releases = {installed_version: releases[installed_version]}
            provenance = "GENERATION_ENVIRONMENT"
        else:
            selected_releases = releases
            provenance = "PRE_GENERATION_REGISTRY_SNAPSHOT"
        candidates = []
        for version, files in selected_releases.items():
            if not isinstance(files, list):
                continue
            for item in files:
                if not isinstance(item, dict) or item.get("packagetype") != "bdist_wheel":
                    continue
                uploaded = _upload_time(
                    item.get("upload_time_iso_8601") or item.get("upload_time")
                )
                if uploaded is not None:
                    candidates.append((uploaded, version, item))
        if not candidates:
            record["resolution_reason"] = "wheel_not_found"
            return record
        _uploaded, version, wheel = max(candidates, key=lambda item: item[0])
        digest = wheel.get("digests", {}).get("sha256")
        url = wheel.get("url")
        filename = wheel.get("filename")
        parsed = urlparse(url) if isinstance(url, str) else None
        if (
            not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or parsed is None
            or parsed.scheme != "https"
            or parsed.hostname != "files.pythonhosted.org"
        ):
            record["resolution_reason"] = "wheel_metadata_invalid"
            return record
        record.update(
            {
                "pypi_version": version,
                "wheel_filename": filename,
                "wheel_sha256": digest.lower(),
                "wheel_url": url,
                "resolution_status": "PINNED_BEFORE_GENERATION",
                "temporal_provenance": provenance,
            }
        )
        return record
    except Exception as exc:
        record["resolution_reason"] = f"metadata_capture_failed:{type(exc).__name__}"
        return record


def finalize_wheel_snapshot(
    record: dict[str, Any], wheelhouse: Path, sample_id: str
) -> dict[str, Any]:
    result = dict(record)
    result.setdefault("wheel_relative_path", None)
    result.setdefault("wheel_sha256_observed", None)
    result.setdefault("artifact_download_timestamp_utc", None)
    if result.get("resolution_status") != "PINNED_BEFORE_GENERATION":
        return result
    try:
        request = Request(
            result["wheel_url"], headers={"User-Agent": USER_AGENT}
        )
        with urlopen(request, timeout=30) as response:
            wheel_bytes = response.read(MAX_WHEEL_BYTES + 1)
        result["artifact_download_timestamp_utc"] = utc_now()
        if len(wheel_bytes) > MAX_WHEEL_BYTES:
            raise ValueError("wheel_exceeds_size_limit")
        observed = hashlib.sha256(wheel_bytes).hexdigest()
        if observed != result["wheel_sha256"]:
            result["resolution_status"] = "UNRESOLVED"
            result["temporal_provenance"] = "UNRESOLVED"
            result["resolution_reason"] = "wheel_sha256_mismatch"
            return result
        wheelhouse.mkdir(parents=True, exist_ok=True)
        sample_token = hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:16]
        filename = f"{sample_token}-{result['wheel_filename']}"
        destination = wheelhouse / filename
        destination.write_bytes(wheel_bytes)
        result["wheel_relative_path"] = f"wheelhouse/{filename}"
        result["wheel_sha256_observed"] = observed
        result["resolution_status"] = "RESOLVED"
        return result
    except Exception as exc:
        result["resolution_status"] = "UNRESOLVED"
        result["temporal_provenance"] = "UNRESOLVED"
        result["resolution_reason"] = f"wheel_capture_failed:{type(exc).__name__}"
        return result
    finally:
        result.pop("wheel_url", None)


def write_generation_snapshot(
    path: Path,
    *,
    generation_timestamp_utc: str,
    provider_name: str,
    requested_model_id: str,
    provider_model_id: str | None,
    generation_environment: dict[str, Any],
    packages: list[dict[str, Any]],
) -> str:
    payload: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA,
        "generation_timestamp_utc": generation_timestamp_utc,
        "provider_name": provider_name,
        "requested_model_id": requested_model_id,
        "provider_model_id": provider_model_id,
        "generation_environment": generation_environment,
        "packages": packages,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    payload["snapshot_sha256"] = digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return digest


def load_generation_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SNAPSHOT_SCHEMA:
        raise ValueError("temporal snapshot schema is missing or unsupported")
    observed = payload.get("snapshot_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "snapshot_sha256"}
    expected = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    if not isinstance(observed, str) or observed != expected:
        raise ValueError("temporal snapshot SHA-256 mismatch")
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise ValueError("temporal snapshot packages must be a list")
    by_sample: dict[str, dict[str, Any]] = {}
    for item in packages:
        if not isinstance(item, dict) or not isinstance(item.get("sample_id"), str):
            raise ValueError("temporal package rows require sample_id")
        if item["sample_id"] in by_sample:
            raise ValueError("temporal snapshot contains duplicate sample_id")
        by_sample[item["sample_id"]] = item
    payload["_packages_by_sample"] = by_sample
    return payload


def check_signature_from_snapshot(
    code: str, package_name: str, record: dict[str, Any] | None, snapshot_root: Path
) -> dict[str, Any]:
    if record is None:
        return {"status": "INCONCLUSIVE", "reason": "TEMPORAL_EVIDENCE_MISSING"}
    if (
        record.get("resolution_status") != "RESOLVED"
        or record.get("temporal_provenance") not in {
            "GENERATION_ENVIRONMENT",
            "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }
    ):
        return {
            "status": "INCONCLUSIVE",
            "reason": "TEMPORAL_EVIDENCE_MISSING",
            "temporal_provenance": record.get("temporal_provenance", "UNRESOLVED"),
        }
    if record.get("package_name") != package_name:
        return {"status": "INCONCLUSIVE", "reason": "temporal_package_identity_mismatch"}
    relative = record.get("wheel_relative_path")
    if (
        not isinstance(relative, str)
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        return {"status": "INCONCLUSIVE", "reason": "temporal_wheel_path_invalid"}
    wheel_filename = record.get("wheel_filename")
    if (
        not isinstance(wheel_filename, str)
        or not _wheel_compatible_with_cpython311_linux_x86_64(wheel_filename)
    ):
        return {
            "status": "INCONCLUSIVE",
            "reason": "temporal_wheel_incompatible_with_cpython311_linux_x86_64",
            "wheel_filename": wheel_filename,
        }
    wheel_path = snapshot_root / relative
    if not wheel_path.is_file():
        return {"status": "INCONCLUSIVE", "reason": "temporal_wheel_missing"}
    wheel_bytes = wheel_path.read_bytes()
    observed = hashlib.sha256(wheel_bytes).hexdigest()
    if observed != record.get("wheel_sha256"):
        return {"status": "INCONCLUSIVE", "reason": "temporal_wheel_sha256_mismatch"}
    try:
        aliases, calls, unsupported = _imports_and_calls(code, package_name)
        if not aliases:
            return {"status": "INCONCLUSIVE", "reason": "package_import_not_found"}
        if unsupported:
            return {
                "status": "INCONCLUSIVE",
                "reason": "dynamic_call_receiver_unresolved",
                "unsupported_calls": unsupported,
                "calls": calls,
            }
        inspected = inspect_wheel_bytes(wheel_bytes, calls)
        if not isinstance(inspected, dict):
            return {
                "status": "INCONCLUSIVE",
                "reason": "temporal_wheel_inspection_invalid_result",
            }
        result: dict[str, Any] = inspected
        result.update(
            {
                "package": package_name,
                "pypi_version": record.get("pypi_version"),
                "wheel_filename": record.get("wheel_filename"),
                "wheel_sha256_expected": record.get("wheel_sha256"),
                "wheel_sha256_observed": observed,
                "temporal_provenance": record.get("temporal_provenance"),
            }
        )
        return result
    except Exception as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": "temporal_wheel_inspection_failed",
            "error_type": type(exc).__name__,
        }
