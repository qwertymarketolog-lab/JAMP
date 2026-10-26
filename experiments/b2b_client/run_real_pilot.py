#!/usr/bin/env python3
"""Run one real, fail-closed JAMP → OpenRouter → E2 → signed-verdict pilot."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PROMPT = "Извлеки данные: Выручка $1,000,000, Расходы $200,000."
EXPECTED_MODEL = "z-ai/glm-5.3-flash"
REQUEST_TIMEOUT = 45.0
STARTUP_TIMEOUT = 30.0


class PilotError(RuntimeError):
    """A required real-pilot condition was not met."""


def _http_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    allow_http_errors: bool = False,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read()
            status = response.status
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
        if not allow_http_errors:
            body = raw.decode("utf-8", errors="replace")[:500]
            raise PilotError(f"HTTP request failed: status={status}, body={body}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise PilotError(f"HTTP request failed: {type(exc).__name__}") from None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PilotError("HTTP response was not valid JSON") from None
    if not isinstance(decoded, dict):
        raise PilotError("HTTP response JSON was not an object")
    return status, decoded


def validate_execution_response(response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if response.get("status") != "EXECUTE":
        raise PilotError(f"JAMP refused execution: {response.get('reason', 'unknown reason')}")
    if response.get("evidence_status") != "VERIFIED":
        raise PilotError("JAMP E2 evidence status is not VERIFIED")
    output = response.get("output")
    if not isinstance(output, dict):
        raise PilotError("JAMP response has no provider output object")
    if output.get("provider") != "openrouter":
        raise PilotError("Execution did not report OpenRouter as the provider")
    actual_model = output.get("provider_model_id")
    if actual_model != EXPECTED_MODEL:
        raise PilotError(f"Unexpected actual provider model ID: {actual_model!r}")
    if output.get("provider_requested_model_id") != EXPECTED_MODEL:
        raise PilotError("Requested provider model ID does not match the approved direct model")
    if (
        not isinstance(output.get("provider_response_id"), str)
        or not output["provider_response_id"]
    ):
        raise PilotError("Provider response ID is missing; real-generation evidence unavailable")
    verdict = response.get("verdict")
    if not isinstance(verdict, dict):
        raise PilotError("JAMP response has no signed verdict")
    if verdict.get("status") != "VERIFIED":
        raise PilotError("Verdict status is not VERIFIED")
    if verdict.get("trace_id") != response.get("trace_id"):
        raise PilotError("Verdict trace_id does not match this execution")
    if verdict.get("provider_model_id") != actual_model:
        raise PilotError("Verdict model ID does not match the actual provider response")
    if not isinstance(verdict.get("evidence_hash"), str) or not verdict["evidence_hash"]:
        raise PilotError("Verdict is missing the output evidence hash")
    if not isinstance(output.get("content"), str) or not output["content"].strip():
        raise PilotError("Provider response content is empty")
    return actual_model, verdict


def _write_persisted_trace(trace_id: str, audit_path: Path) -> None:
    """Export the exact persisted trace object for this pilot as a diagnostic JSON file."""
    if not trace_id:
        raise PilotError("Execution response has no trace_id; provenance unavailable")
    if not audit_path.is_file():
        raise PilotError("Persisted AuditTrace JSONL file is missing")
    try:
        with audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if isinstance(record, dict) and record.get("trace_id") == trace_id:
                    output_path = audit_path.with_name("provenance.json")
                    output_path.write_text(
                        json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    print(f"[PILOT] Persisted AuditTrace exported: {output_path}", flush=True)
                    return
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PilotError(f"Could not read persisted AuditTrace: {type(exc).__name__}") from None
    raise PilotError(f"Persisted AuditTrace not found for trace_id={trace_id}")


def _write_remote_provenance(base_url: str, trace_id: str, audit_path: Path) -> None:
    """Fetch the server's persisted trace and save it before reporting execution refusal."""
    status, trace = _http_json(f"{base_url}/v1/provenance/{trace_id}")
    if status != 200:
        raise PilotError(f"Provenance lookup failed: status={status}, trace_id={trace_id}")
    if trace.get("trace_id") != trace_id:
        raise PilotError("Provenance lookup returned a mismatched trace_id")
    output_path = audit_path.with_name("provenance.json")
    try:
        output_path.write_text(
            json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise PilotError(f"Could not save provenance.json: {type(exc).__name__}") from None
    print(f"[PILOT] Persisted AuditTrace exported: {output_path}", flush=True)


def _execute_with_provenance(
    base_url: str, payload: dict[str, Any], audit_path: Path
) -> dict[str, Any]:
    """Keep non-200 refusal evidence before failing the pilot."""
    status, response = _http_json(
        f"{base_url}/v1/execute",
        payload=payload,
        allow_http_errors=True,
    )
    if status != 200:
        reason = response.get("reason", f"HTTP_{status}")
        trace_id = response.get("trace_id")
        has_trace_id = isinstance(trace_id, str) and bool(trace_id)
        if has_trace_id:
            try:
                _write_remote_provenance(base_url, trace_id, audit_path)
            except PilotError as exc:
                print(
                    f"[PILOT] REFUSE: {reason} (trace_id={trace_id}; "
                    f"provenance_export=FAILED: {exc})",
                    file=sys.stderr,
                    flush=True,
                )
                raise PilotError(
                    f"Execution refused: status={status}, reason={reason}; "
                    "provenance export failed"
                ) from None
        print(
            f"[PILOT] REFUSE: {reason}"
            + (
                f" (trace_id={trace_id}; provenance_export=UNAVAILABLE)"
                if not has_trace_id
                else ""
            ),
            file=sys.stderr,
            flush=True,
        )
        raise PilotError(f"Execution refused: status={status}, reason={reason}")
    return response


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_pilot() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise PilotError("Required environment variable OPENROUTER_API_KEY is missing")
    if not os.environ.get("JAMP_SIGNING_KEY"):
        raise PilotError("Required environment variable JAMP_SIGNING_KEY is missing")

    # Prevent development fallback signing and prohibit local model-ID overrides.
    os.environ["JAMP_ENV"] = "production"
    os.environ.pop("OPENROUTER_MODEL_ID_MAP", None)
    os.environ.pop("OPENROUTER_FALLBACK_MODELS", None)
    os.environ["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_dir = ROOT / "artifacts" / "real-pilot"
    log_dir.mkdir(parents=True, exist_ok=True)
    audit_path = log_dir / "provenance_traces.jsonl"
    os.environ["JAMP_AUDIT_PATH"] = str(audit_path)
    server_log_path = log_dir / "uvicorn.log"
    server_log = server_log_path.open("w", encoding="utf-8")
    process: subprocess.Popen[str] | None = None

    try:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "jamp.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ]
        print("[PILOT] Starting real Uvicorn process", flush=True)
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )

        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise PilotError(
                    f"Uvicorn exited before readiness (exit={process.returncode}); "
                    "inspect uvicorn.log"
                )
            try:
                status, _ = _http_json(f"{base_url}/openapi.json")
                if status == 200:
                    break
            except PilotError:
                time.sleep(0.25)
        else:
            raise PilotError("Uvicorn did not become ready before startup timeout")

        print("[PILOT] HTTP server ready; sending real /v1/execute request", flush=True)
        response = _execute_with_provenance(
            base_url,
            {
                "intent": "search_and_extraction",
                "prompt": PROMPT,
                "request_id": f"stage9-real-pilot-{int(time.time())}",
            },
            audit_path,
        )
        response_trace_id = response.get("trace_id")
        if isinstance(response_trace_id, str) and response_trace_id:
            _write_persisted_trace(response_trace_id, audit_path)
        actual_model, verdict = validate_execution_response(response)
        print(
            "[PILOT] Execution evidence: "
            + json.dumps(
                {
                    "trace_id": response["trace_id"],
                    "provider": response["output"]["provider"],
                    "provider_response_id": response["output"]["provider_response_id"],
                    "provider_requested_model_id": response["output"][
                        "provider_requested_model_id"
                    ],
                    "provider_model_id": actual_model,
                    "evidence_status": response["evidence_status"],
                    "qualification": response.get("qualification"),
                    "content": response["output"]["content"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )

        _, verification = _http_json(f"{base_url}/v1/verify-verdict", payload=verdict)
        if verification.get("valid") is not True:
            raise PilotError("API rejected verdict signature (valid is not true)")

        # Independently verify HMAC locally as well as through the public API.
        sys.path.insert(0, str(ROOT / "src"))
        from jamp.runtime.verdict import JampVerdict

        parsed_verdict = JampVerdict.from_dict(verdict)
        if not parsed_verdict.verify(os.environ["JAMP_SIGNING_KEY"]):
            raise PilotError("Independent local HMAC verification failed")
        print(f"[PILOT] Real Model ID: {actual_model}", flush=True)
        print("[PILOT] Evidence Status: VERIFIED", flush=True)
        print("[PILOT] Signature: VALID", flush=True)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        server_log.close()


def main() -> int:
    try:
        run_pilot()
    except Exception as exc:
        # Do not print environment values, request headers, or exception reprs.
        message = str(exc).replace(os.environ.get("OPENROUTER_API_KEY", "\0"), "[REDACTED]")
        message = message.replace(os.environ.get("JAMP_SIGNING_KEY", "\0"), "[REDACTED]")
        print(f"[PILOT] FAILED: {message}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
