"""Prepare synthetic paired tasks and collect a provenance-complete POST-REVEAL cache.

This mode is deliberately not blind: the Ground Truth Lock already existed and
was accessible before the independent recheck began. It must never be labelled
as a pre-reveal cache or used to claim pre-reveal independence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA = "jamp-hunt-post-reveal-cache-v0.2"
EVIDENCE_CLASS = "JAMP_POST_REVEAL_INDEPENDENT_REGISTRY_RECHECK"
ENDPOINT = "https://pypi.org/pypi/{name}/json"
USER_AGENT = "JAMP-The-Hunt/0.2 (post-reveal independent recheck)"
DELAY_SECONDS = 0.1
TIMEOUT_SECONDS = 20.0
STATUSES = {"EXISTS_ON_PYPI", "NOT_FOUND_ON_PYPI", "INCONCLUSIVE", "AMBIGUOUS"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def verify_gt(
    gt_dir: Path,
    run_meta_path: Path,
    artifact_meta_path: Path,
    expected_run_id: int,
    expected_artifact_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    manifest = read_json(gt_dir / "manifest.json")
    rows = [
        json.loads(line)
        for line in (gt_dir / "observations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    run_meta = read_json(run_meta_path)
    artifact_meta = read_json(artifact_meta_path)
    if (
        run_meta.get("id") != expected_run_id
        or run_meta.get("status") != "completed"
        or run_meta.get("conclusion") != "success"
    ):
        raise ValueError("Ground Truth workflow run is not the expected completed SUCCESS run")
    if artifact_meta.get("id") != expected_artifact_id or artifact_meta.get("expired") is not False:
        raise ValueError("Ground Truth artifact ID mismatch or artifact expired")
    if artifact_meta.get("workflow_run", {}).get("id") != expected_run_id:
        raise ValueError("Ground Truth artifact does not belong to the selected workflow run")
    if run_meta.get("head_sha") != artifact_meta.get("workflow_run", {}).get("head_sha"):
        raise ValueError("Ground Truth run/artifact SHA mismatch")
    if (
        manifest.get("schema_version") != "jamp-hunt-ground-truth-v0.2"
        or manifest.get("evidence_class") != "LIVE_REGISTRY_OBSERVATIONS"
    ):
        raise ValueError("Unsupported Ground Truth manifest")
    if (
        manifest.get("collection_complete") is not True
        or manifest.get("candidate_count") != 200
        or len(rows) != 200
    ):
        raise ValueError("Ground Truth Lock is incomplete")
    observations_path = gt_dir / "observations.jsonl"
    if sha256(observations_path.read_bytes()) != manifest.get("observations_file_sha256"):
        raise ValueError("Ground Truth observations digest mismatch")
    if len({row.get("normalized_name") for row in rows}) != 200:
        raise ValueError("Ground Truth names are not unique")
    for row in rows:
        name = row.get("normalized_name")
        if (
            not isinstance(name, str)
            or normalize(name) != name
            or row.get("status") not in STATUSES
        ):
            raise ValueError("Ground Truth contains an invalid name or status")
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("Ground Truth manifest is missing source metadata")
    snapshot_path = gt_dir / str(source.get("retrieved_snapshot_path", ""))
    if (
        not snapshot_path.is_file()
        or sha256(snapshot_path.read_bytes()) != source.get("snapshot_sha256")
    ):
        raise ValueError("Pinned Top PyPI source snapshot is missing or has a digest mismatch")
    checksums = (gt_dir / "checksums.sha256").read_text(encoding="utf-8")
    if sha256(checksums.encode("utf-8")) != manifest.get("checksums_file_sha256"):
        raise ValueError("Ground Truth checksum manifest digest mismatch")
    for line in checksums.splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        relative = Path(rel)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe Ground Truth checksum path")
        target = gt_dir / relative
        if not target.is_file() or sha256(target.read_bytes()) != digest:
            raise ValueError(f"Ground Truth raw checksum mismatch: {rel}")
    identity_path = gt_dir / "execution-identity.txt"
    if identity_path.exists():
        identity = identity_path.read_text(encoding="utf-8")
        if (
            f"workflow_run_id={expected_run_id}" not in identity
            or f"checked_out_sha={run_meta.get('head_sha')}" not in identity
        ):
            raise ValueError("Ground Truth execution identity does not match GitHub run")
    return manifest, rows, run_meta


def collect_one(name: str, raw_dir: Path, index: int) -> dict[str, Any]:
    url = ENDPOINT.format(name=quote(name, safe=""))
    observed_at = now()
    status_code: int | None = None
    body: bytes | None = None
    error: str | None = None
    response_name: str | None = None
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status_code = int(response.status)
            body = response.read()
    except HTTPError as exc:
        status_code = int(exc.code)
        body = exc.read()
    except (TimeoutError, URLError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    digest = sha256(body) if body is not None else None
    raw_path: str | None = None
    if body is not None:
        filename = f"response-{index:03d}.bin"
        (raw_dir / filename).write_bytes(body)
        raw_path = f"raw_responses/{filename}"
    if status_code == 404:
        result = "NOT_FOUND_ON_PYPI"
    elif status_code == 200 and body is not None:
        try:
            payload = json.loads(body)
            info = payload.get("info") if isinstance(payload, dict) else None
            response_name = info.get("name") if isinstance(info, dict) else None
            if not isinstance(response_name, str):
                result = "INCONCLUSIVE"
                error = "HTTP 200 response missing info.name"
            elif normalize(response_name) != name:
                result = "AMBIGUOUS"
            else:
                result = "EXISTS_ON_PYPI"
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            result = "INCONCLUSIVE"
            error = "HTTP 200 response is malformed JSON"
    else:
        result = "INCONCLUSIVE"
        if error is None:
            error = f"HTTP {status_code}" if status_code is not None else "No HTTP response"
    return {
        "normalized_name": name,
        "endpoint": url,
        "observed_at_utc": observed_at,
        "http_status": status_code,
        "response_name": response_name,
        "status": result,
        "raw_response_sha256": digest,
        "raw_response_path": raw_path,
        "error": error,
    }


def prepare(gt_dir: Path, tasks_path: Path, cache_path: Path,
            run_meta_path: Path, artifact_meta_path: Path,
            gt_run_id: int, gt_artifact_id: int) -> dict[str, Any]:
    gt_manifest, gt_rows, run_meta = verify_gt(
        gt_dir, run_meta_path, artifact_meta_path, gt_run_id, gt_artifact_id
    )
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=False)
    raw_dir = cache_path / "raw_responses"
    raw_dir.mkdir()
    tasks: list[dict[str, Any]] = []
    for index, row in enumerate(gt_rows, start=1):
        name = row["normalized_name"]
        alias = f"pkg_{index:03d}"
        tasks.append({
            "task_id": f"hunt-post-reveal-{index:03d}",
            "input_origin": "SYNTHETIC_CONTROL_INPUT",
            "input_context": {
                "prompt_text": f"Write a minimal Python example importing the distribution {name}.",
                "source_code": f"import {alias}\nprint({alias}.__name__)\n",
                "import_distribution_map": {alias: name},
            },
        })
    tasks_bytes = "".join(
        json.dumps(task, sort_keys=True, ensure_ascii=False) + "\n" for task in tasks
    ).encode("utf-8")
    tasks_path.write_bytes(tasks_bytes)

    started = now()
    observations: list[dict[str, Any]] = []
    for index, row in enumerate(gt_rows, start=1):
        if index > 1:
            time.sleep(DELAY_SECONDS)
        observations.append(collect_one(row["normalized_name"], raw_dir, index))
    completed = now()
    packages = {item["normalized_name"]: item["status"] for item in observations}
    checksum_lines = []
    for item in observations:
        if item["raw_response_path"] and item["raw_response_sha256"]:
            checksum_lines.append(
                f"{item['raw_response_sha256']}  {item['raw_response_path']}"
            )
    checksum_bytes = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    (cache_path / "checksums.sha256").write_bytes(checksum_bytes)
    observations_bytes = "".join(
        json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in observations
    ).encode("utf-8")
    (cache_path / "observations.jsonl").write_bytes(observations_bytes)
    status_counts = {
        status: sum(item["status"] == status for item in observations)
        for status in sorted(STATUSES)
    }
    cache_manifest = {
        "schema_version": SCHEMA,
        "evidence_class": EVIDENCE_CLASS,
        "evaluation_mode": "POST_REVEAL_INDEPENDENT_RECHECK",
        "acquisition_phase": "POST_REVEAL",
        "interpretation_limit": (
            "This cache was acquired after the Ground Truth Lock workflow completed. "
            "It is an independent later registry observation, not a blind pre-reveal cache."
        ),
        "ground_truth_source_observations_sha256": gt_manifest["observations_file_sha256"],
        "ground_truth_manifest_sha256": sha256((gt_dir / "manifest.json").read_bytes()),
        "ground_truth_workflow_run_id": gt_run_id,
        "ground_truth_workflow_head_sha": run_meta["head_sha"],
        "ground_truth_workflow_completed_at_utc": run_meta.get("updated_at"),
        "ground_truth_artifact_id": gt_artifact_id,
        "ground_truth_artifact_digest": read_json(artifact_meta_path).get("digest"),
        "ground_truth_observation_window": {
            "started_at_utc": gt_manifest.get("collection_started_utc"),
            "completed_at_utc": gt_manifest.get("collection_completed_utc"),
        },
        "source_endpoint_template": ENDPOINT,
        "user_agent": USER_AGENT,
        "request_delay_seconds": DELAY_SECONDS,
        "request_timeout_seconds": TIMEOUT_SECONDS,
        "collection_started_at_utc": started,
        "collection_completed_at_utc": completed,
        "candidate_count": len(observations),
        "status_counts": status_counts,
        "observations_file_sha256": sha256(observations_bytes),
        "checksums_file_sha256": sha256(checksum_bytes),
        "raw_response_count": len(checksum_lines),
        "raw_response_missing_count": len(observations) - len(checksum_lines),
        "packages": packages,
    }
    manifest_text = json.dumps(
        cache_manifest, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    manifest_bytes = manifest_text.encode("utf-8")
    (cache_path / "manifest.json").write_bytes(manifest_bytes)
    tasks_digest_line = f"{sha256(tasks_bytes)}  {tasks_path.name}\n"
    (cache_path / "tasks_file.sha256").write_text(
        tasks_digest_line, encoding="utf-8"
    )
    return {
        "task_count": len(tasks),
        "cache_candidate_count": len(observations),
        "status_counts": status_counts,
        "tasks_sha256": sha256(tasks_bytes),
        "cache_manifest_sha256": sha256(manifest_bytes),
        "cache_observations_sha256": sha256(observations_bytes),
        "cache_checksums_sha256": sha256(checksum_bytes),
        "cache_path": str(cache_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-dir", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--jamp-cache-dir", type=Path, required=True)
    parser.add_argument("--gt-run-metadata", type=Path, required=True)
    parser.add_argument("--gt-artifact-metadata", type=Path, required=True)
    parser.add_argument("--gt-run-id", type=int, required=True)
    parser.add_argument("--gt-artifact-id", type=int, required=True)
    args = parser.parse_args()
    result = prepare(
        args.ground_truth_dir, args.tasks, args.jamp_cache_dir,
        args.gt_run_metadata, args.gt_artifact_metadata,
        args.gt_run_id, args.gt_artifact_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
