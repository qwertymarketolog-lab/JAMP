#!/usr/bin/env python3
"""AnyModel N=3 availability evidence harness.

This harness is the prerequisite for AnyModel identity/capability audit v3.
It performs exactly three identical deterministic availability probes for
every model in the live 87-model catalog.

It does not modify src/jamp/run.py and does not alter the v3 contract.
Transport failures are recorded as observations, never converted into
model-quality verdicts. The process exits non-zero unless all 87 models have
exactly three completed attempts and the catalog contains exactly 87 unique
model IDs.

Usage:
  ANYMODEL_API_KEY=... python scripts/research/anymodel_availability_n3.py

Optional environment:
  ANYMODEL_CATALOG_URL
  ANYMODEL_CHAT_URL
  ANYMODEL_TIMEOUT_S
  ANYMODEL_AUTH_HEADER        default: Authorization
  ANYMODEL_AUTH_SCHEME        default: Bearer
  ANYMODEL_N3_OUTPUT          default:
      artifacts/research/anymodel_availability_n3.json
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
from typing import Any

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
CATALOG_URL = os.environ.get("ANYMODEL_CATALOG_URL", "https://anymodel.org/v1/models")
CHAT_URL = os.environ.get("ANYMODEL_CHAT_URL", "https://anymodel.org/v1/chat/completions")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "30"))
AUTH_HEADER = os.environ.get("ANYMODEL_AUTH_HEADER", "Authorization")
AUTH_SCHEME = os.environ.get("ANYMODEL_AUTH_SCHEME", "Bearer")
DEFAULT_OUTPUT = ROOT / "artifacts/research/anymodel_availability_n3.json"
PROBE_ID = "ANYMODEL-AVAILABILITY-N3-V3"
PROBE_TEXT = "Reply with exactly: OK"
TEMPERATURE = 0
EXPECTED_MODELS = 87
REPETITIONS = 3


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def auth_headers(api_key: str) -> dict[str, str]:
    value = f"{AUTH_SCHEME} {api_key}" if AUTH_SCHEME else api_key
    return {
        AUTH_HEADER: value,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "JAMP-anymodel-availability-n3/1.0",
    }


def catalog(headers: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    try:
        response = requests.get(CATALOG_URL, headers=headers, timeout=TIMEOUT_S)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        raw_text = response.text
        try:
            payload = response.json()
        except ValueError:
            payload = None

        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        valid_rows = (
            [row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)]
            if isinstance(rows, list)
            else []
        )

        observation = {
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "response_headers": {key.lower(): value for key, value in response.headers.items()},
            "raw_response": raw_text,
            "parsed_response": payload,
            "valid_model_count": len(valid_rows),
        }
        if response.status_code != 200:
            raise RuntimeError(f"catalog HTTP {response.status_code}; model list not trusted")
        if len(valid_rows) != EXPECTED_MODELS:
            raise RuntimeError(
                f"expected {EXPECTED_MODELS} catalog models, observed {len(valid_rows)}"
            )
        ids = [row["id"] for row in valid_rows]
        if len(set(ids)) != EXPECTED_MODELS:
            raise RuntimeError("catalog contains duplicate model IDs")
        return valid_rows, observation
    except requests.RequestException as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        raise RuntimeError(f"catalog request failed: {type(exc).__name__}: {exc}") from exc


def probe(
    headers: dict[str, str],
    model_id: str,
    attempt: int,
) -> dict[str, Any]:
    request_body = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROBE_TEXT}],
        "temperature": TEMPERATURE,
    }
    started = time.perf_counter()
    observed_at = now()

    try:
        response = requests.post(
            CHAT_URL,
            headers=headers,
            json=request_body,
            timeout=TIMEOUT_S,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        try:
            parsed = response.json()
            json_parse_ok = True
        except ValueError:
            parsed = None
            json_parse_ok = False

        observation: dict[str, Any] = {
            "probe_id": PROBE_ID,
            "attempt": attempt,
            "observed_at": observed_at,
            "model_id": model_id,
            "request": request_body,
            "transport": {
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "timed_out": False,
                "response_headers": {key.lower(): value for key, value in response.headers.items()},
            },
            "response": {
                "json_parse_ok": json_parse_ok,
                "raw_body": response.text,
                "parsed_body": parsed,
            },
        }
    except requests.Timeout as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        observation = {
            "probe_id": PROBE_ID,
            "attempt": attempt,
            "observed_at": observed_at,
            "model_id": model_id,
            "request": request_body,
            "transport": {
                "status_code": None,
                "elapsed_ms": elapsed_ms,
                "timed_out": True,
                "response_headers": {},
            },
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
    except requests.RequestException as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        observation = {
            "probe_id": PROBE_ID,
            "attempt": attempt,
            "observed_at": observed_at,
            "model_id": model_id,
            "request": request_body,
            "transport": {
                "status_code": None,
                "elapsed_ms": elapsed_ms,
                "timed_out": False,
                "response_headers": {},
            },
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }

    observation["evidence_digest"] = sha256_json(observation)
    return observation


def main() -> int:
    output = pathlib.Path(os.environ.get("ANYMODEL_N3_OUTPUT", str(DEFAULT_OUTPUT)))
    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        print("ERROR: ANYMODEL_API_KEY is required", file=sys.stderr)
        return 2

    headers = auth_headers(api_key)

    try:
        catalog_rows, catalog_observation = catalog(headers)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    catalog_snapshot = {
        "retrieved_at": now(),
        "endpoint": CATALOG_URL,
        "models": catalog_rows,
        "model_ids": [row["id"] for row in catalog_rows],
        "observation": catalog_observation,
    }
    catalog_digest = sha256_json(catalog_snapshot)

    manifest: dict[str, Any] = {
        "artifact_version": "anymodel-availability-n3-v1",
        "contract_version": "anymodel-identity-capability-v3",
        "probe_contract_version": "p0-probe-v0",
        "probe_id": PROBE_ID,
        "created_at": now(),
        "catalog": {
            "endpoint": CATALOG_URL,
            "count": EXPECTED_MODELS,
            "snapshot": catalog_snapshot,
            "evidence_digest": catalog_digest,
        },
        "probe": {
            "endpoint": CHAT_URL,
            "message": PROBE_TEXT,
            "temperature": TEMPERATURE,
            "timeout_s": TIMEOUT_S,
            "repetitions": REPETITIONS,
            "total_expected_attempts": EXPECTED_MODELS * REPETITIONS,
        },
        "models": [],
    }

    completed_attempts = 0
    for index, row in enumerate(catalog_rows, start=1):
        model_id = row["id"]
        print(
            f"[{index}/{EXPECTED_MODELS}] {model_id}: attempts 1/{REPETITIONS}",
            flush=True,
        )
        attempts = []
        for attempt in range(1, REPETITIONS + 1):
            if attempt > 1:
                print(
                    f"[{index}/{EXPECTED_MODELS}] {model_id}: attempt {attempt}/{REPETITIONS}",
                    flush=True,
                )
            attempts.append(probe(headers, model_id, attempt))
            completed_attempts += 1

        manifest["models"].append(
            {
                "model_id": model_id,
                "catalog_entry": row,
                "attempts": attempts,
            }
        )

    actual_attempts = sum(len(record["attempts"]) for record in manifest["models"])
    manifest["summary"] = {
        "models_expected": EXPECTED_MODELS,
        "models_observed": len(manifest["models"]),
        "attempts_expected": EXPECTED_MODELS * REPETITIONS,
        "attempts_observed": actual_attempts,
        "completed_attempts": completed_attempts,
        "complete": (
            len(manifest["models"]) == EXPECTED_MODELS
            and actual_attempts == EXPECTED_MODELS * REPETITIONS
        ),
    }
    manifest["evidence_digest"] = sha256_json(manifest)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"artifact={output} "
        f"attempts={actual_attempts}/{EXPECTED_MODELS * REPETITIONS} "
        f"complete={manifest['summary']['complete']}",
        flush=True,
    )

    # Fail closed: transport errors remain evidence, but an incomplete
    # execution can never be accepted as the prerequisite artifact.
    return 0 if manifest["summary"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
