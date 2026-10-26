#!/usr/bin/env python3
"""Stage 10 n8n-style external workflow emulator; fail closed before CRM writes."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
FINANCIAL_TEXT = (
    "Quarterly report Q3: revenue $5,200,000.50, operating expenses $1,200,000, "
    "net income $4,000,000.50. Extract these exact values. Return ONLY one valid JSON "
    "object, with no Markdown fences, prose, prefix, or suffix, using exactly these keys: "
    "quarter (string), revenue (number), operating_expenses (number), net_income (number). "
    "Use JSON numbers without currency symbols. Do not add any other keys."
)
HTTP_TIMEOUT = 60.0
STARTUP_TIMEOUT = 30.0


class WorkflowAbort(RuntimeError):
    """A fail-closed admission gate rejected the workflow."""


def http_json(
    url: str, payload: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT) as response:
            raw = response.read()
            status = response.status
    except HTTPError as exc:
        raise WorkflowAbort(f"HTTP request rejected: status={exc.code}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise WorkflowAbort(f"HTTP transport failed: {type(exc).__name__}") from None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise WorkflowAbort("HTTP response is not valid JSON") from None
    if not isinstance(decoded, dict):
        raise WorkflowAbort("HTTP response JSON is not an object")
    return status, decoded


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise WorkflowAbort(reason)


def run_workflow() -> None:
    require(bool(os.environ.get("OPENROUTER_API_KEY")), "OPENROUTER_API_KEY is missing")
    require(bool(os.environ.get("JAMP_SIGNING_KEY")), "JAMP_SIGNING_KEY is missing")

    os.environ["JAMP_ENV"] = "production"
    os.environ.pop("OPENROUTER_MODEL_ID_MAP", None)
    os.environ.pop("OPENROUTER_FALLBACK_MODELS", None)
    os.environ["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    process: subprocess.Popen[str] | None = None
    with tempfile.TemporaryDirectory(prefix="jamp-n8n-") as temp_dir:
        log_path = Path(temp_dir) / "uvicorn.log"
        with log_path.open("w", encoding="utf-8") as server_log:
            try:
                command = [
                    sys.executable, "-m", "uvicorn", "jamp.api.app:create_app",
                    "--factory", "--host", "127.0.0.1", "--port", str(port),
                    "--log-level", "info",
                ]
                print("[n8n EMULATOR] Starting JAMP HTTP server", flush=True)
                process = subprocess.Popen(
                    command, cwd=ROOT, env=os.environ.copy(),
                    stdout=server_log, stderr=subprocess.STDOUT, text=True,
                )
                deadline = time.monotonic() + STARTUP_TIMEOUT
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise WorkflowAbort("JAMP server exited before readiness")
                    try:
                        status, _ = http_json(f"{base_url}/openapi.json")
                        if status == 200:
                            break
                    except WorkflowAbort:
                        time.sleep(0.25)
                else:
                    raise WorkflowAbort("JAMP server readiness timeout")

                print("[n8n EMULATOR] Trigger received; calling JAMP /v1/execute", flush=True)
                _, execution = http_json(
                    f"{base_url}/v1/execute",
                    {
                        "intent": "search_and_extraction",
                        "prompt": FINANCIAL_TEXT,
                        "request_id": f"stage10-n8n-{int(time.time())}",
                    },
                )

                require(execution.get("status") == "EXECUTE", "ABORT: JAMP status is not EXECUTE")
                require(
                    execution.get("evidence_status") == "VERIFIED",
                    "ABORT: evidence_status is not VERIFIED",
                )
                require(
                    execution.get("qualification") == "QUALIFIED",
                    "ABORT: qualification is not QUALIFIED",
                )
                verdict = execution.get("verdict")
                require(isinstance(verdict, dict), "ABORT: signed verdict is missing")
                require(verdict.get("status") == "VERIFIED", "ABORT: verdict status is not VERIFIED")
                require(
                    verdict.get("trace_id") == execution.get("trace_id"),
                    "ABORT: verdict trace_id mismatch",
                )

                output = execution.get("output")
                require(isinstance(output, dict), "ABORT: provider output is missing")
                content = output.get("content")
                require(isinstance(content, str) and content.strip(), "ABORT: output content is empty")
                try:
                    crm_record = json.loads(content)
                except json.JSONDecodeError:
                    raise WorkflowAbort("ABORT: extracted content is not valid JSON") from None
                require(isinstance(crm_record, dict), "ABORT: extracted content must be a JSON object")

                _, verification = http_json(f"{base_url}/v1/verify-verdict", verdict)
                if verification.get("valid") is not True:
                    print(
                        "[n8n EMULATOR] SECURITY_ALERT: Signature mismatch. Flow aborted.",
                        file=sys.stderr, flush=True,
                    )
                    raise WorkflowAbort("ABORT: authentic verdict signature is invalid")

                crm_record["_jamp_trace_id"] = execution["trace_id"]
                crm_record["_jamp_provider_model_id"] = output.get("provider_model_id")
                crm_record["_jamp_evidence_status"] = execution["evidence_status"]
                crm_dir = ROOT / "artifacts" / "n8n-emulator"
                crm_dir.mkdir(parents=True, exist_ok=True)
                crm_path = crm_dir / "crm.json"
                crm_path.write_text(
                    json.dumps(crm_record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(
                    "[n8n EMULATOR] Data verified and passed to CRM: "
                    + json.dumps(crm_record, ensure_ascii=False, sort_keys=True),
                    flush=True,
                )

                tampered = dict(verdict)
                signature = tampered.get("signature")
                require(isinstance(signature, str) and bool(signature), "ABORT: signature missing")
                tampered["signature"] = ("0" if signature[0] != "0" else "1") + signature[1:]
                _, negative = http_json(f"{base_url}/v1/verify-verdict", tampered)
                require(
                    negative.get("valid") is False,
                    "SECURITY_FAILURE: API accepted a deliberately tampered signature",
                )
                print(
                    "[n8n EMULATOR] SECURITY_ALERT: Signature mismatch. Flow aborted. "
                    "(expected negative-control branch; tampered data was not routed to CRM)",
                    flush=True,
                )
            finally:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def main() -> int:
    try:
        run_workflow()
    except Exception as exc:
        message = str(exc)
        for secret_name in ("OPENROUTER_API_KEY", "JAMP_SIGNING_KEY"):
            secret = os.environ.get(secret_name)
            if secret:
                message = message.replace(secret, "[REDACTED]")
        print(f"[n8n EMULATOR] ABORT: {message}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
