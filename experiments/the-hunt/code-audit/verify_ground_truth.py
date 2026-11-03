"""Verify candidate package ground truth against the live PyPI JSON API.

A 404 means only that the normalized distribution name was not found on PyPI
at the observation time. It does not prove global non-existence or API safety.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PYPI_API_URL = "https://pypi.org/pypi/{package}/json"
REAL_PACKAGES = [
    "requests",
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "pandas",
    "numpy",
    "pytest",
    "httpx",
    "uvicorn",
    "jinja2",
    "boto3",
    "redis",
    "celery",
    "aiohttp",
    "beautifulsoup4",
]
FAKE_PACKAGES = [
    "requests-extra",
    "pyjson-parser-v2",
    "fastapi-auth-magic",
    "sqlalchemy-async-orm",
    "pandas-ml-extensions",
    "numpy-turbo",
    "pytest-ai-assert",
    "httpx-retry-plus",
    "uvicorn-worker-graceful",
    "jinja2-live-reload",
    "boto3-secure-vault",
    "redis-cluster-manager",
    "celery-supervisor",
    "aiohttp-cors-fix",
    "beautifulsoup5",
]


def normalize_distribution_name(package: str) -> str:
    """Normalize a distribution name according to the PyPI/PEP 503 rule."""
    return re.sub(r"[-_.]+", "-", package).lower()


def check_package(package: str, timeout: float = 5.0) -> dict[str, Any]:
    """Return a timestamped observation; network failures remain inconclusive."""
    normalized = normalize_distribution_name(package)
    url = PYPI_API_URL.format(package=quote(normalized, safe=""))
    request = Request(url, headers={"User-Agent": "JAMP-The-Hunt-GroundTruth/0.2"})
    observed_at = datetime.now(timezone.utc).isoformat()
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = response.status
            payload = json.loads(response.read())
            info = payload.get("info") if isinstance(payload, dict) else None
            if (
                status_code == 200
                and isinstance(info, dict)
                and isinstance(info.get("name"), str)
                and normalize_distribution_name(info["name"]) == normalized
            ):
                status = "EXISTS_ON_PYPI"
            else:
                status = "INCONCLUSIVE"
    except HTTPError as error:
        status_code = error.code
        status = "NOT_FOUND_ON_PYPI" if error.code == 404 else "INCONCLUSIVE"
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        status_code = None
        status = "INCONCLUSIVE"

    return {
        "candidate": package,
        "normalized_name": normalized,
        "status": status,
        "http_status": status_code,
        "observed_at_utc": observed_at,
        "source": url,
    }


def verify_ground_truth(output_dir: Path | None = None) -> dict[str, Any]:
    """Observe every candidate and persist machine-readable evidence."""
    destination = output_dir or Path(__file__).parent
    observations = [
        {**check_package(package), "candidate_class": "REAL_CANDIDATE"}
        for package in REAL_PACKAGES
    ]
    observations.extend(
        {**check_package(package), "candidate_class": "FAKE_CANDIDATE"}
        for package in FAKE_PACKAGES
    )

    by_name = {item["normalized_name"]: item for item in observations}
    verified_fakes = [
        package
        for package in FAKE_PACKAGES
        if by_name[normalize_distribution_name(package)]["status"]
        == "NOT_FOUND_ON_PYPI"
    ]
    conflicts = [
        item["candidate"]
        for item in observations
        if item["candidate_class"] == "FAKE_CANDIDATE"
        and item["status"] == "EXISTS_ON_PYPI"
    ]
    inconclusive = [
        item["candidate"]
        for item in observations
        if item["status"] == "INCONCLUSIVE"
    ]

    report: dict[str, Any] = {
        "schema_version": "jamp-hunt-ground-truth-v1",
        "evidence_class": "LIVE_PYPI_REGISTRY_OBSERVATIONS",
        "scope": "PyPI distribution-name presence only",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "https://pypi.org/pypi/{normalized_distribution}/json",
        "candidate_count": len(observations),
        "verified_fake_candidates": verified_fakes,
        "fake_candidate_conflicts": conflicts,
        "inconclusive_candidates": inconclusive,
        "observations": observations,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "ground_truth.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "chr(10)", encoding="utf-8"
    )
    (destination / "valid_fakes.json").write_text(
        json.dumps(verified_fakes, indent=2) + "chr(10)", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


if __name__ == "__main__":
    verify_ground_truth()
