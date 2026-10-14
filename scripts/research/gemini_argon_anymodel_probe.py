#!/usr/bin/env python3
"""Read-only AnyModel catalog + single-request probe for Gemini 4 Argon.

This is provider/API availability evidence only. It does not qualify a model,
modify AnyModel, or change JAMP routing. Missing/ambiguous model mappings are
recorded as BLOCKED/INCONCLUSIVE rather than guessed.
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
from typing import Any

OUT = pathlib.Path("artifacts/research/gemini_argon_api_probe")
CATALOG_URL = os.environ.get("ANYMODEL_CATALOG_URL", "https://anymodel.org/v1/models")
CHAT_URL = os.environ.get("ANYMODEL_CHAT_URL", "https://anymodel.org/v1/chat/completions")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "30"))
REQUESTED_ID = "gemini-4-argon"
EXPECTED_FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
PROBE_TEXT = "Reply with exactly: JAMP_ANYMODEL_API_PROBE_OK"


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(serialized.encode())


def append_event(events_path: pathlib.Path, event_type: str, **fields: Any) -> None:
    event = {
        "schema_version": "1.0",
        "observed_at": now(),
        "event_type": event_type,
        "evidence_class": "RAW_OBSERVATION",
        **fields,
    }
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def request_json(
    url: str,
    api_key: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int | None, bytes, dict[str, str], float, str | None]:
    body = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if payload is not None
        else None
    )
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "JAMP-Gemini-Argon-API-Probe/1.0",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            raw = response.read()
            headers = {
                k.lower(): v
                for k, v in response.headers.items()
                if k.lower() in {"content-type", "x-request-id", "request-id", "retry-after"}
            }
            return response.status, raw, headers, round(time.perf_counter() - started, 6), None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        headers = {
            k.lower(): v
            for k, v in exc.headers.items()
            if k.lower() in {"content-type", "x-request-id", "request-id", "retry-after"}
        }
        return exc.code, raw, headers, round(time.perf_counter() - started, 6), None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, b"", {}, round(time.perf_counter() - started, 6), type(exc).__name__


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    events_path = OUT / "events.jsonl"
    manifest_path = OUT / "run_manifest.json"
    metrics = json.dumps({"status": "NOT_CALCULATED"}, indent=2) + "\n"
    (OUT / "metrics.json").write_text(metrics, encoding="utf-8")
    for stale in (
        events_path,
        OUT / "catalog_raw.json",
        OUT / "chat_raw.json",
        OUT / "checksums.sha256",
        OUT / "decision.json",
    ):
        stale.unlink(missing_ok=True)
    (OUT / "catalog_raw.json").write_bytes(b"")
    (OUT / "chat_raw.json").write_bytes(b"")

    try:
        frozen_blob = subprocess.check_output(
            ["git", "rev-parse", "HEAD:src/jamp/run.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        frozen_blob = None
    frozen_ok = frozen_blob == EXPECTED_FROZEN_CORE_BLOB

    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_id": "jamp-gemini-argon-anymodel-api-probe",
        "status": "RUNNING",
        "created_at": now(),
        "github": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "ref": os.environ.get("GITHUB_REF"),
            "sha": os.environ.get("GITHUB_SHA"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        },
        "provider": {"name": "AnyModel", "catalog_url": CATALOG_URL, "chat_url": CHAT_URL},
        "model": {"requested_id": REQUESTED_ID, "resolved_anymodel_id": None},
        "benchmark": {"name": "Terminal-Bench", "version": "4.0", "status": "NOT_STARTED"},
        "limits": {"timeout_seconds": TIMEOUT_S, "max_chat_requests": 1},
        "frozen_core": {
            "path": "src/jamp/run.py",
            "expected_git_blob": EXPECTED_FROZEN_CORE_BLOB,
            "observed_git_blob": frozen_blob,
            "delta_zero": frozen_ok,
        },
        "decision": "INCONCLUSIVE",
        "reason": "API probe not completed",
    }
    append_event(
        events_path,
        "RUN_STARTED",
        experiment_id=manifest["experiment_id"],
        frozen_core_blob=frozen_blob,
        frozen_core_delta_zero=frozen_ok,
    )

    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        manifest.update(
            status="BLOCKED",
            decision="BLOCKED",
            reason="ANYMODEL_API_KEY secret is not configured",
        )
        append_event(events_path, "BLOCKED", reason=manifest["reason"])
        return finalize(manifest, events_path, manifest_path)

    status, raw, headers, elapsed, error = request_json(CATALOG_URL, api_key)
    (OUT / "catalog_raw.json").write_bytes(raw)
    append_event(
        events_path,
        "CATALOG_RESPONSE",
        http_status=status,
        elapsed_seconds=elapsed,
        response_sha256=sha256_bytes(raw),
        response_headers=headers,
        transport_error=error,
    )
    if error or status != 200:
        manifest.update(
            status="BLOCKED",
            decision="BLOCKED",
            reason=f"AnyModel catalog request failed: {error or f'HTTP {status}'}",
        )
        return finalize(manifest, events_path, manifest_path)

    try:
        payload = json.loads(raw.decode("utf-8"))
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("unexpected catalog shape")
        model_rows = [
            row for row in rows
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        ]
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        manifest.update(
            status="BLOCKED",
            decision="BLOCKED",
            reason=f"Invalid catalog response: {type(exc).__name__}",
        )
        append_event(events_path, "BLOCKED", reason=manifest["reason"])
        return finalize(manifest, events_path, manifest_path)

    candidates = [
        row for row in model_rows
        if REQUESTED_ID in row["id"].lower()
        or (isinstance(row.get("name"), str) and REQUESTED_ID in row["name"].lower())
    ]
    manifest["catalog"] = {
        "http_status": status,
        "response_sha256": sha256_bytes(raw),
        "model_count": len(model_rows),
        "unique_id_count": len({row["id"] for row in model_rows}),
        "candidate_count": len(candidates),
        "candidate_ids": [row["id"] for row in candidates],
    }
    append_event(
        events_path,
        "CATALOG_MATCH",
        model_count=len(model_rows),
        unique_id_count=len({row["id"] for row in model_rows}),
        candidate_ids=[row["id"] for row in candidates],
    )

    if not frozen_ok:
        manifest.update(
            status="BLOCKED",
            decision="BLOCKED",
            reason="Frozen Core blob does not match pinned baseline; no chat request made",
        )
        return finalize(manifest, events_path, manifest_path)
    if len(candidates) == 0:
        manifest.update(
            status="BLOCKED",
            decision="BLOCKED",
            reason="No Gemini 4 Argon ID/name found in AnyModel catalog; no model ID guessed",
        )
        return finalize(manifest, events_path, manifest_path)
    if len(candidates) > 1:
        manifest.update(
            status="INCONCLUSIVE",
            decision="INCONCLUSIVE",
            reason="Multiple possible AnyModel model IDs; no ambiguous selection made",
        )
        return finalize(manifest, events_path, manifest_path)

    model_id = candidates[0]["id"]
    manifest["model"]["resolved_anymodel_id"] = model_id
    chat_payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROBE_TEXT}],
        "temperature": 0,
    }
    chat_status, chat_raw, chat_headers, chat_elapsed, chat_error = request_json(
        CHAT_URL, api_key, "POST", chat_payload
    )
    (OUT / "chat_raw.json").write_bytes(chat_raw)
    append_event(
        events_path,
        "CHAT_RESPONSE",
        model_id=model_id,
        http_status=chat_status,
        elapsed_seconds=chat_elapsed,
        response_sha256=sha256_bytes(chat_raw),
        response_headers=chat_headers,
        transport_error=chat_error,
    )

    parsed: Any = None
    try:
        parsed = json.loads(chat_raw.decode("utf-8")) if chat_raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    text = None
    if isinstance(parsed, dict):
        choices = parsed.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                text = message["content"]
    manifest["chat"] = {
        "http_status": chat_status,
        "elapsed_seconds": chat_elapsed,
        "response_sha256": sha256_bytes(chat_raw),
        "response_id": parsed.get("id") if isinstance(parsed, dict) else None,
        "usage": (
            parsed.get("usage")
            if isinstance(parsed, dict) and isinstance(parsed.get("usage"), dict)
            else None
        ),
        "exact_probe_text": text == "JAMP_ANYMODEL_API_PROBE_OK",
    }
    if chat_error or chat_status != 200 or text is None:
        manifest.update(
            status="BLOCKED",
            decision="BLOCKED",
            reason=(
                f"AnyModel chat request failed contract: "
                f"{chat_error or f'HTTP {chat_status} or no text choice'}"
            ),
        )
    else:
        manifest.update(
            status="COMPLETED",
            decision="INCONCLUSIVE",
            reason=(
                "One AnyModel request completed; this confirms transport only, "
                "not independent model identity or JAMP capability"
            ),
        )
    return finalize(manifest, events_path, manifest_path)


def finalize(
    manifest: dict[str, Any], events_path: pathlib.Path, manifest_path: pathlib.Path
) -> int:
    manifest["finished_at"] = now()
    serialized_manifest = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
    manifest_path.write_text(serialized_manifest + "\n", encoding="utf-8")
    decision = {
        "experiment_id": manifest["experiment_id"],
        "outcome": manifest["decision"],
        "status": manifest["status"],
        "reason": manifest["reason"],
        "routing_eligibility": "REFUSE",
        "source_artifacts": [
            "run_manifest.json",
            "events.jsonl",
            "catalog_raw.json",
            "chat_raw.json",
            "metrics.json",
        ],
        "frozen_core_delta_zero": manifest["frozen_core"]["delta_zero"],
        "benchmark_status": manifest["benchmark"]["status"],
    }
    serialized_decision = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    (OUT / "decision.json").write_text(serialized_decision, encoding="utf-8")
    lines = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            lines.append(f"{sha256_bytes(path.read_bytes())}  {path.name}")
    (OUT / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "status": manifest["status"],
        "decision": manifest["decision"],
        "reason": manifest["reason"],
        "frozen_core_delta_zero": manifest["frozen_core"]["delta_zero"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
