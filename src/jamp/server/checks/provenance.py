"""Deterministic PyPI provenance checks for The Hunt v0.3.

Only PyPI metadata is queried. No candidate distribution is installed or imported.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from .pypi_client import PYPI_JSON, TIMEOUT_SECONDS, fetch_pypi_json

def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_release_timestamp(releases: Any) -> datetime | None:
    if not isinstance(releases, dict):
        return None
    timestamps = []
    for release_files in releases.values():
        if not isinstance(release_files, list):
            continue
        for release_file in release_files:
            if not isinstance(release_file, dict):
                continue
            timestamp = _parse_timestamp(
                release_file.get("upload_time_iso_8601") or release_file.get("upload_time")
            )
            if timestamp is not None:
                timestamps.append(timestamp)
    return min(timestamps) if timestamps else None


def _has_repository(project_urls: Any) -> bool:
    if not isinstance(project_urls, dict):
        return False
    for value in project_urls.values():
        if not isinstance(value, str):
            continue
        hostname = (urlparse(value).hostname or "").lower()
        if hostname in {"github.com", "www.github.com", "gitlab.com", "www.gitlab.com"}:
            return True
    return False


def _score_metadata(
    package_name: str,
    payload: dict[str, Any],
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    info = payload.get("info")
    info = info if isinstance(info, dict) else {}
    first_release = _first_release_timestamp(payload.get("releases"))
    observed = (observed_at or datetime.now(UTC)).astimezone(UTC)

    if first_release is None:
        return {
            "package": package_name,
            "status": "INCONCLUSIVE",
            "reason": "missing_dates",
            "evidence": {
                "pypi_exists": True,
                "pypi_url": PYPI_JSON.format(package_name),
                "observation_timestamp_utc": observed.isoformat(),
                "raw_pypi_response": payload,
                "raw_pypi_response_sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            },
        }

    age_days = max(0.0, (observed - first_release).total_seconds() / 86400)
    age_penalty = 50 if age_days < 30 else 20 if age_days < 365 else 0
    project_urls = info.get("project_urls")
    repository_present = _has_repository(project_urls)
    author_present = any(
        isinstance(info.get(field), str) and info[field].strip()
        for field in ("author", "author_email")
    )
    repository_penalty = 0 if repository_present else 30
    author_penalty = 0 if author_present else 20
    score = max(0, 100 - age_penalty - repository_penalty - author_penalty)

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "package": package_name,
        "trust_score": score,
        "status": "SUSPICIOUS" if score < 50 else "TRUSTED",
        "evidence": {
            "pypi_exists": True,
            "pypi_url": PYPI_JSON.format(package_name),
            "observation_timestamp_utc": observed.isoformat(),
            "first_publication_timestamp_utc": first_release.isoformat(),
            "age_days": age_days,
            "age_penalty": age_penalty,
            "repository_present": repository_present,
            "repository_penalty": repository_penalty,
            "author_present": author_present,
            "author_penalty": author_penalty,
            "trust_score": score,
            "project_urls": project_urls if isinstance(project_urls, dict) else {},
            "raw_pypi_response": payload,
            "raw_pypi_response_sha256": hashlib.sha256(canonical).hexdigest(),
        },
    }


def check_provenance(package_name: str) -> dict[str, Any]:
    """Return a fail-closed provenance assessment for a PyPI distribution."""
    if not isinstance(package_name, str) or not package_name.strip():
        return {"package": package_name, "status": "INCONCLUSIVE", "reason": "invalid_name"}
    name = package_name.strip()
    try:
        status_code, payload = fetch_pypi_json(name)
        if status_code == 404:
            return {
                "package": name,
                "status": "NOT_FOUND",
                "evidence": {"pypi_exists": False, "http_status": 404},
            }
        if status_code != 200 or payload is None:
            return {
                "package": name,
                "status": "INCONCLUSIVE",
                "reason": "unexpected_http_status",
                "evidence": {"http_status": status_code},
            }
        return _score_metadata(name, payload)
    except Exception as exc:
        return {
            "package": name,
            "status": "INCONCLUSIVE",
            "reason": "pypi_request_failed",
            "evidence": {"error_type": type(exc).__name__},
        }
