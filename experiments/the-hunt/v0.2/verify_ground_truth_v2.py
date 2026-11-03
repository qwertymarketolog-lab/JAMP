"""Collect an immutable, timestamped PyPI Ground Truth snapshot for The Hunt v0.2.

This collector records PyPI distribution-name observations only. A 404 is
NOT_FOUND_ON_PYPI at observation time; it is not proof of global non-existence.
All network and parsing failures fail closed as INCONCLUSIVE or AMBIGUOUS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BENCHMARK_VERSION = "0.2"
SCHEMA_VERSION = "jamp-hunt-ground-truth-v0.2"
SEED = 42
TOP_PYPI_URL = (
    "https://hugovk.github.io/top-pypi-packages/"
    "top-pypi-packages-30-days.min.json"
)
GITHUB_API_URL = (
    "https://api.github.com/repos/hugovk/top-pypi-packages/commits/main"
)
RAW_SOURCE_TEMPLATE = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/"
    "{revision}/top-pypi-packages-30-days.min.json"
)
PYPI_API_TEMPLATE = "https://pypi.org/pypi/{name}/json"
USER_AGENT = "JAMP-The-Hunt/0.2 (evidence collection; contact: repository maintainers)"
REQUEST_DELAY_SECONDS = 0.1
TIMEOUT_SECONDS = 20.0

# Deterministic, programmatic candidate-name generation. Candidate origin is
# metadata only and never determines the observed Ground Truth.
FAKE_PREFIXES = (
    "pydata", "fastapi", "numpy", "pandas", "django",
    "asyncio", "json", "cloud", "secure", "vector",
)
FAKE_SUFFIXES = (
    "ai", "fast", "extra", "parser", "plus",
    "toolkit", "client", "utils", "engine", "adapter",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_distribution_name(name: str) -> str:
    """Apply the PEP 503 normalization rule."""
    return re.sub(r"[-_.]+", "-", name).lower()


def fetch_bytes(url: str, *, accept: str = "application/json") -> tuple[bytes, int]:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read(), int(response.status)


def resolve_source_revision() -> str:
    payload, status = fetch_bytes(GITHUB_API_URL)
    if status != 200:
        raise RuntimeError(f"Source revision lookup returned HTTP {status}")
    data = json.loads(payload)
    revision = data.get("sha") if isinstance(data, dict) else None
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("Could not resolve an immutable 40-character source revision")
    return revision


def extract_ranked_packages(snapshot: bytes) -> list[dict[str, Any]]:
    data = json.loads(snapshot)
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) < 1000:
        raise ValueError("Top PyPI snapshot must contain at least 1,000 rows")
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, row in enumerate(rows[:1000], start=1):
        if not isinstance(row, dict) or not isinstance(row.get("project"), str):
            raise ValueError(f"Malformed source row at rank {rank}")
        original = row["project"]
        normalized = normalize_distribution_name(original)
        if not normalized or normalized in seen:
            raise ValueError(f"Duplicate/empty normalized source name at rank {rank}")
        seen.add(normalized)
        selected.append(
            {
                "rank": rank,
                "original_name": original,
                "normalized_name": normalized,
            }
        )
    return selected


def stratified_sample(
    ranked: list[dict[str, Any]], *, seed: int = SEED
) -> list[dict[str, Any]]:
    if len(ranked) != 1000:
        raise ValueError("Sampling frame must contain exactly 1,000 ranked rows")
    rng = random.Random(seed)
    sampled: list[dict[str, Any]] = []
    for stratum_start in range(1, 1001, 100):
        stratum = ranked[stratum_start - 1 : stratum_start + 99]
        chosen = rng.sample(stratum, 10)
        sampled.extend(sorted(chosen, key=lambda item: item["rank"]))
    if len(sampled) != 100:
        raise AssertionError("Stratified sampler did not produce exactly 100 candidates")
    return sampled


def generate_fake_candidates(real_names: set[str]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    for prefix in FAKE_PREFIXES:
        for suffix in FAKE_SUFFIXES:
            name = f"{prefix}-{suffix}"
            normalized = normalize_distribution_name(name)
            if normalized in real_names:
                # Do not silently drop a collision. The fixed generation
                # algorithm fails closed so a revised method/version is explicit.
                raise ValueError(f"Generated fake candidate collides with Top-1000: {name}")
            generated.append({"original_name": name, "normalized_name": normalized})
    if len(generated) != 100 or len({x["normalized_name"] for x in generated}) != 100:
        raise AssertionError("Fake candidate generator did not produce 100 unique names")
    return generated


def observe_candidate(
    candidate: dict[str, str],
    *,
    candidate_origin: str,
    raw_dir: Path,
) -> dict[str, Any]:
    original = candidate["original_name"]
    normalized = normalize_distribution_name(original)
    candidate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"jamp-hunt-v0.2:{candidate_origin}:{normalized}"))
    url = PYPI_API_TEMPLATE.format(name=quote(normalized, safe=""))
    observed_at = utc_now()
    http_status: int | None = None
    response_name: str | None = None
    raw_digest: str | None = None
    raw_path: str | None = None
    error: str | None = None
    status = "INCONCLUSIVE"
    body = b""

    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            http_status = int(response.status)
            body = response.read()
    except HTTPError as exc:
        http_status = int(exc.code)
        body = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"

    if body:
        raw_digest = sha256_bytes(body)
        raw_filename = f"{candidate_id}-{raw_digest}.json"
        raw_file = raw_dir / raw_filename
        raw_file.write_bytes(body)
        raw_path = f"raw_responses/{raw_filename}"

    if http_status == 404:
        status = "NOT_FOUND_ON_PYPI"
    elif http_status == 200 and body:
        try:
            payload = json.loads(body)
            info = payload.get("info") if isinstance(payload, dict) else None
            response_name = info.get("name") if isinstance(info, dict) else None
            if not isinstance(response_name, str):
                status = "INCONCLUSIVE"
                error = "HTTP 200 response missing info.name"
            elif normalize_distribution_name(response_name) != normalized:
                status = "AMBIGUOUS"
                error = "Returned distribution identity does not match requested name"
            else:
                status = "EXISTS_ON_PYPI"
        except (json.JSONDecodeError, UnicodeDecodeError):
            status = "INCONCLUSIVE"
            error = "HTTP 200 response body is not valid JSON"
    elif http_status is not None:
        status = "INCONCLUSIVE"
        error = error or f"Non-definitive HTTP status: {http_status}"

    return {
        "candidate_id": candidate_id,
        "candidate_origin": candidate_origin,
        "original_name": original,
        "normalized_name": normalized,
        "requested_url": url,
        "http_status": http_status,
        "pypi_response_name": response_name,
        "timestamp_utc": observed_at,
        "status": status,
        "raw_response_sha256": raw_digest,
        "raw_response_path": raw_path,
        "error": error,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def collect(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw_responses"
    raw_dir.mkdir(parents=True, exist_ok=True)

    collection_started = utc_now()
    revision = resolve_source_revision()
    pinned_url = RAW_SOURCE_TEMPLATE.format(revision=revision)
    snapshot, snapshot_status = fetch_bytes(pinned_url)
    if snapshot_status != 200:
        raise RuntimeError(f"Pinned Top PyPI snapshot returned HTTP {snapshot_status}")
    snapshot_path = output_dir / "top-pypi-packages-30-days.min.json"
    snapshot_path.write_bytes(snapshot)

    ranked = extract_ranked_packages(snapshot)
    real = stratified_sample(ranked)
    real_names = {item["normalized_name"] for item in ranked}
    fake = generate_fake_candidates(real_names)

    candidates: list[tuple[dict[str, str], str]] = []
    candidates.extend(
        (
            {
                "original_name": item["original_name"],
                "normalized_name": item["normalized_name"],
                "source_rank": str(item["rank"]),
            },
            "TOP_PYPI_STRATIFIED_SAMPLE",
        )
        for item in real
    )
    candidates.extend((item, "PROGRAMMATIC_GENERATED_CANDIDATE") for item in fake)

    all_normalized = [item[0]["normalized_name"] for item in candidates]
    if len(all_normalized) != 200 or len(set(all_normalized)) != 200:
        raise ValueError("Candidate set must contain 200 unique normalized names")

    observations: list[dict[str, Any]] = []
    for index, (candidate, origin) in enumerate(candidates):
        observations.append(
            observe_candidate(candidate, candidate_origin=origin, raw_dir=raw_dir)
        )
        if index < len(candidates) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    observations_path = output_dir / "observations.jsonl"
    with observations_path.open("w", encoding="utf-8", newline="\n") as stream:
        for item in observations:
            stream.write(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n")

    raw_files = sorted(raw_dir.glob("*.json"))
    checksum_lines = [
        f"{sha256_bytes(path.read_bytes())}  raw_responses/{path.name}"
        for path in raw_files
    ]
    checksums_path = output_dir / "checksums.sha256"
    checksums_path.write_text(
        "".join(line + "\n" for line in checksum_lines),
        encoding="utf-8",
    )

    counts = {
        state: sum(item["status"] == state for item in observations)
        for state in ("EXISTS_ON_PYPI", "NOT_FOUND_ON_PYPI", "INCONCLUSIVE", "AMBIGUOUS")
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "experiment_run_id": str(uuid.uuid4()),
        "evidence_class": "LIVE_REGISTRY_OBSERVATIONS",
        "scope": "PyPI distribution-name presence at observation time only",
        "candidate_generation": {
            "real_method": "10 strata of 100 ranks; 10 sampled without replacement per stratum",
            "sampling_prng": "random.Random",
            "seed": SEED,
            "strata": [
                {"rank_start": start, "rank_end": start + 99, "sample_size": 10}
                for start in range(1, 1001, 100)
            ],
            "selected_real_ranks": [int(item["source_rank"]) for item, _ in candidates[:100]],
            "fake_method": "Cartesian product of fixed 10 prefixes and 10 suffixes",
            "fake_generator_version": "prefix-suffix-product-v1",
            "fake_prefixes": list(FAKE_PREFIXES),
            "fake_suffixes": list(FAKE_SUFFIXES),
        },
        "candidate_count": len(candidates),
        "unique_normalized_candidate_count": len(set(all_normalized)),
        "status_counts": counts,
        "collection_started_utc": collection_started,
        "collection_completed_utc": utc_now(),
        "source": {
            "published_endpoint": TOP_PYPI_URL,
            "repository": "https://github.com/hugovk/top-pypi-packages",
            "repository_revision": revision,
            "source_file_path": "top-pypi-packages-30-days.min.json",
            "pinned_raw_url": pinned_url,
            "retrieved_snapshot_path": snapshot_path.name,
            "snapshot_sha256": sha256_bytes(snapshot),
            "snapshot_http_status": snapshot_status,
        },
        "verification": {
            "endpoint_template": PYPI_API_TEMPLATE,
            "implementation": "verify_ground_truth_v2.py",
            "request_delay_seconds": REQUEST_DELAY_SECONDS,
            "timeout_seconds": TIMEOUT_SECONDS,
        },
        "raw_response_file_count": len(raw_files),
        "observations_file_sha256": sha256_bytes(observations_path.read_bytes()),
        "checksums_file_sha256": sha256_bytes(checksums_path.read_bytes()),
        "raw_response_missing_body_count": sum(
            item["raw_response_sha256"] is None for item in observations
        ),
        "collection_complete": len(observations) == 200,
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("ground_truth"),
        help="Output directory for the immutable Ground Truth evidence set",
    )
    args = parser.parse_args()
    print(json.dumps(collect(args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
