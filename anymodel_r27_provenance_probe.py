#!/usr/bin/env python3
"""Read-only R27 provenance probe for the v3 candidate HOLD set.

This probe does not modify the v3 audit or Frozen Core. It derives the target
set from the committed v3 analysis + N=3 availability evidence, then records
the complete R27 HTTP response and provenance metadata for every target.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import time
from typing import Any

import requests

ROOT = pathlib.Path(__file__).resolve().parent
ANALYSIS = ROOT / "artifacts/research/anymodel_identity_capability_v3_analysis.json"
AVAILABILITY = ROOT / "artifacts/research/anymodel_availability_n3.json"
DEFAULT_OUTPUT = ROOT / "artifacts/research/r27_provenance_probe.json"
CHAT_URL = "https://anymodel.org/v1/chat/completions"
TIMEOUT_S = 30.0
CANARY = "JAMP-CANARY-7F4A9C2E"
EXPECTED_CANDIDATES = 36
EXPECTED_HOLD = 17


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256_bytes(raw)


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def target_models() -> list[str]:
    analysis = load_json(ANALYSIS)
    availability = load_json(AVAILABILITY)

    required = ["R01", "R05", "R06", "R09", "R11"]
    verified = [{x["model_id"] for x in analysis["checks"][check]["VERIFIED"]} for check in required]
    available = {
        row["model"] for row in availability["results"] if row.get("availability") == "AVAILABLE"
    }
    candidates = sorted(available.intersection(*verified))
    contradicted = {x["model_id"] for x in analysis["checks"]["R27"]["CONTRADICTED"]}
    hold = sorted(set(candidates).intersection(contradicted))

    if len(candidates) != EXPECTED_CANDIDATES:
        raise RuntimeError(
            f"candidate gate drift: expected {EXPECTED_CANDIDATES}, observed {len(candidates)}"
        )
    if len(hold) != EXPECTED_HOLD:
        raise RuntimeError(f"R27 HOLD count drift: expected {EXPECTED_HOLD}, observed {len(hold)}")
    return hold


def response_text(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    return None


def safe_headers(headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, str]:
    excluded = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
    return {str(k).lower(): str(v) for k, v in headers.items() if str(k).lower() not in excluded}


def probe(model: str, api_key: str) -> dict[str, Any]:
    request_payload = {
        "model": model,
        "messages": [{"role": "user", "content": CANARY}],
        "temperature": 0,
    }
    started = time.perf_counter()
    observed_at = now()

    try:
        response = requests.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=TIMEOUT_S,
        )
        elapsed_s = time.perf_counter() - started
        raw = response.content
        raw_sha256 = sha256_bytes(raw)
        try:
            body = response.json()
            body_kind = "json"
        except ValueError:
            body = {"raw_text": response.text}
            body_kind = "non_json"

        text = response_text(body)
        detected = CANARY in (text or "")
        status = "CONTRADICTED" if detected else "VERIFIED"

        evidence = {
            "check_id": "R27",
            "model_id": model,
            "probe": "canary-provenance-v1",
            "observed_at": observed_at,
            "request": request_payload,
            "http": {
                "status_code": response.status_code,
                "elapsed_s": elapsed_s,
                "headers": safe_headers(response.headers),
            },
            "response": {
                "body_kind": body_kind,
                "body": body,
                "text": text,
                "raw_sha256": raw_sha256,
            },
            "canary": CANARY,
            "detected": detected,
        }
        return {
            **evidence,
            "status": status,
            "response_sha256": canonical_digest(body),
            "evidence_digest": canonical_digest(evidence),
        }
    except requests.RequestException as exc:
        elapsed_s = time.perf_counter() - started
        evidence = {
            "check_id": "R27",
            "model_id": model,
            "probe": "canary-provenance-v1",
            "observed_at": observed_at,
            "request": request_payload,
            "http": {
                "status_code": None,
                "elapsed_s": elapsed_s,
                "headers": {},
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            "response": None,
            "canary": CANARY,
            "detected": None,
        }
        return {
            **evidence,
            "status": "INCONCLUSIVE",
            "response_sha256": None,
            "evidence_digest": canonical_digest(evidence),
        }


def main() -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        raise SystemExit("ANYMODEL_API_KEY is required")

    models = target_models()
    records = []
    for index, model in enumerate(models, 1):
        print(f"[{index}/{len(models)}] {model}", flush=True)
        records.append(probe(model, api_key))

    payload = {
        "probe_id": "anymodel-r27-provenance-v1",
        "contract": "anymodel-identity-capability-v3",
        "created_at": now(),
        "chat_url": CHAT_URL,
        "canary": CANARY,
        "timeout_s": TIMEOUT_S,
        "selection": {
            "candidate_gate": [
                "N3 AVAILABLE",
                "R01 VERIFIED",
                "R05 VERIFIED",
                "R06 VERIFIED",
                "R09 VERIFIED",
                "R11 VERIFIED",
            ],
            "candidate_count": EXPECTED_CANDIDATES,
            "r27_hold_count": len(models),
            "source_analysis": str(ANALYSIS),
            "source_availability": str(AVAILABILITY),
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    contradicted = sum(x["status"] == "CONTRADICTED" for x in records)
    verified = sum(x["status"] == "VERIFIED" for x in records)
    inconclusive = sum(x["status"] == "INCONCLUSIVE" for x in records)
    print(
        f"WROTE {args.output}; VERIFIED={verified} "
        f"CONTRADICTED={contradicted} INCONCLUSIVE={inconclusive}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
