#!/usr/bin/env python3
"""One-request, read-only transport probe for Google's Gemini 4 Argon API.

This records API availability evidence only. It does not qualify the model or
change JAMP routing. Missing credentials or a Frozen Core mismatch fail closed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

OUT = pathlib.Path("artifacts/research/google_gemini_argon_probe")
MODEL_ID = "gemini-4-argon"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent"
EXPECTED_FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
TIMEOUT_S = 20
PROMPT = "Reply with exactly: JAMP_GOOGLE_GEMINI_API_PROBE_OK"


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_path = OUT / "response_raw.json"
    events_path = OUT / "events.jsonl"
    manifest_path = OUT / "run_manifest.json"
    decision_path = OUT / "decision.json"

    for path in (raw_path, events_path, manifest_path, decision_path):
        path.unlink(missing_ok=True)
    raw_path.write_bytes(b"")

    try:
        observed_blob = subprocess.check_output(
            ["git", "rev-parse", "HEAD:src/jamp/run.py"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        observed_blob = None
    frozen_ok = observed_blob == EXPECTED_FROZEN_CORE_BLOB

    manifest = {
        "schema_version": "1.0",
        "experiment_id": "jamp-google-gemini-argon-api-probe",
        "status": "BLOCKED",
        "created_at": now(),
        "provider": "Google Gemini API",
        "endpoint": API_URL,
        "model_id": MODEL_ID,
        "limits": {"max_api_requests": 1, "timeout_seconds": TIMEOUT_S},
        "request": {"prompt": PROMPT, "temperature": 0, "max_output_tokens": 32},
        "frozen_core": {
            "path": "src/jamp/run.py",
            "expected_git_blob": EXPECTED_FROZEN_CORE_BLOB,
            "observed_git_blob": observed_blob,
            "delta_zero": frozen_ok,
        },
        "http_status": None,
        "latency_seconds": None,
        "response_sha256": sha256(b""),
        "transport_error": None,
        "decision": "HOLD",
        "reason": "Probe not completed",
    }

    def event(name: str, **fields: object) -> None:
        row = {"schema_version": "1.0", "observed_at": now(),
               "event_type": name, "evidence_class": "RAW_OBSERVATION", **fields}
        with events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    event("RUN_STARTED", frozen_core_blob=observed_blob, frozen_core_delta_zero=frozen_ok)

    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not frozen_ok:
        manifest["reason"] = "Frozen Core blob mismatch; no API request sent"
        event("BLOCKED", reason=manifest["reason"])
    elif not api_key:
        manifest["reason"] = "GOOGLE_GEMINI_API_KEY secret is not configured; no API request sent"
        event("BLOCKED", reason=manifest["reason"])
    else:
        payload = {
            "contents": [{"parts": [{"text": PROMPT}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 32},
        }
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "JAMP-Google-Gemini-Argon-Probe/1.0",
            },
        )
        started = time.perf_counter()
        status = None
        raw = b""
        error = None
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = type(exc).__name__
        elapsed = round(time.perf_counter() - started, 6)
        raw_path.write_bytes(raw)
        manifest.update(
            status="COMPLETED" if status == 200 and error is None else "BLOCKED",
            http_status=status,
            latency_seconds=elapsed,
            response_sha256=sha256(raw),
            transport_error=error,
        )
        if status == 200 and error is None:
            manifest["decision"] = "INCONCLUSIVE"
            manifest["reason"] = "One Google API response received; transport evidence only, not model qualification"
        else:
            manifest["reason"] = f"Google API request did not return HTTP 200: {error or status}"
        event("API_RESPONSE", http_status=status, latency_seconds=elapsed,
              response_sha256=sha256(raw), transport_error=error)

    manifest["finished_at"] = now()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decision = {
        "experiment_id": manifest["experiment_id"],
        "outcome": manifest["decision"],
        "status": manifest["status"],
        "reason": manifest["reason"],
        "routing_eligibility": "REFUSE",
        "frozen_core_delta_zero": frozen_ok,
        "qualification": "NOT_PERFORMED",
        "terminal_bench": "NOT_STARTED",
        "source_artifacts": ["run_manifest.json", "events.jsonl", "response_raw.json"],
    }
    decision_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksums.append(f"{sha256(path.read_bytes())}  {path.name}")
    (OUT / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "decision": manifest["decision"],
        "reason": manifest["reason"],
        "frozen_core_delta_zero": frozen_ok,
        "http_status": manifest["http_status"],
        "latency_seconds": manifest["latency_seconds"],
        "response_sha256": manifest["response_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
