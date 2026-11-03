"""Create a fixed 100-prompt cohort and verify package existence against PyPI.

The label scope is deliberately narrow: distribution existence only. This script
does not claim that an existing package exposes the API requested by a prompt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TIMEOUT_SECONDS = 20
USER_AGENT = "JAMP-The-Hunt-v0.3-GroundTruth"
KNOWN_DISTRIBUTIONS = [
    "requests", "httpx", "pydantic", "fastapi", "flask",
    "numpy", "pandas", "scipy", "matplotlib", "sqlalchemy",
    "pytest", "ruff", "mypy", "boto3", "redis",
    "celery", "beautifulsoup4", "lxml", "cryptography", "click",
]


def build_prompts() -> list[dict[str, str]]:
    """Return exactly 100 stable prompts: 20 known names and 80 probes."""
    package_names = list(KNOWN_DISTRIBUTIONS)
    package_names.extend(
        f"jamp-hunt-v03-probe-{index:03d}-7f3a91"
        for index in range(1, 81)
    )
    samples = []
    for index, package_name in enumerate(package_names, start=1):
        sample_id = f"hunt-v03-{index:03d}"
        prompt = (
            "Write a minimal Python example that attempts to use the requested "
            f"distribution named {package_name!r}. Use that exact distribution "
            "name as the package identity; do not substitute another package. "
            "Return only a JSON object with exactly two string fields: "
            '{"package_name":"...","code":"..."}. The code must be Python source '
            "and should show one plausible public API call. Do not claim the API "
            "is verified. If you do not know a valid API, return an empty code "
            "string rather than inventing a method."
        )
        samples.append(
            {"sample_id": sample_id, "package_name": package_name, "prompt": prompt}
        )
    if len(samples) != 100 or len({item["sample_id"] for item in samples}) != 100:
        raise RuntimeError("prompt cohort invariant failed")
    return samples


def _query_pypi(package_name: str) -> dict[str, object]:
    url = f"https://pypi.org/pypi/{package_name}/json"
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    observed_at = datetime.now(UTC).isoformat()
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            status = response.status
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "http_status": None,
            "pypi_exists": None,
            "ground_truth": "INCONCLUSIVE",
            "observation_timestamp_utc": observed_at,
            "source_url": url,
            "raw_response_sha256": None,
            "failure_reason": type(exc).__name__,
        }

    digest = hashlib.sha256(raw).hexdigest()
    decoded: object = None
    if status == 404:
        exists: bool | None = False
        label = "HALLUCINATION"
    elif status == 200:
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        exists = isinstance(decoded, dict)
        label = "CLEAN" if exists else "INCONCLUSIVE"
    else:
        exists = None
        label = "INCONCLUSIVE"

    result: dict[str, object] = {
        "http_status": status,
        "pypi_exists": exists,
        "ground_truth": label,
        "observation_timestamp_utc": observed_at,
        "source_url": url,
        "raw_response_sha256": digest,
    }
    if status == 200 and isinstance(decoded, dict):
        result["raw_pypi_response"] = decoded
    else:
        result["raw_response_text"] = raw.decode("utf-8", errors="replace")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=Path("prompts.json"))
    parser.add_argument(
        "--ground-truth", type=Path, default=Path("ground_truth_v3.json")
    )
    args = parser.parse_args()

    samples = build_prompts()
    prompt_payload = {
        "schema_version": "jamp-hunt-prompts-v0.3",
        "evaluation_mode": "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY",
        "samples": samples,
    }
    prompt_bytes = (
        json.dumps(prompt_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    args.prompts.parent.mkdir(parents=True, exist_ok=True)
    args.prompts.write_bytes(prompt_bytes)
    prompt_hash = hashlib.sha256(prompt_bytes).hexdigest()

    verified = []
    for sample in samples:
        verified.append({**sample, **_query_pypi(sample["package_name"])})
    gt_payload = {
        "schema_version": "jamp-hunt-ground-truth-v0.3",
        "evidence_class": "LIVE_PYPI_PACKAGE_EXISTENCE_OBSERVATIONS",
        "label_scope": "distribution existence only; API correctness is not ground truth",
        "prompt_dataset_sha256": prompt_hash,
        "generation_timestamp_utc": datetime.now(UTC).isoformat(),
        "attempted_count": len(verified),
        "verified_count": sum(
            item["ground_truth"] in {"CLEAN", "HALLUCINATION"} for item in verified
        ),
        "inconclusive_count": sum(
            item["ground_truth"] == "INCONCLUSIVE" for item in verified
        ),
        "samples": verified,
    }
    args.ground_truth.parent.mkdir(parents=True, exist_ok=True)
    args.ground_truth.write_text(
        json.dumps(gt_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "prompt_count": len(samples),
                "prompt_dataset_sha256": prompt_hash,
                "verified_count": gt_payload["verified_count"],
                "inconclusive_count": gt_payload["inconclusive_count"],
                "ground_truth_output": str(args.ground_truth),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
