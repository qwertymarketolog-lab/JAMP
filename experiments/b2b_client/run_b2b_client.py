"""Exercise the B2B Trust Layer over real loopback HTTP.

Uvicorn runs in a separate process. The client uses urllib.request and talks
to the server over TCP/HTTP, not FastAPI TestClient. E2 generation verification
is an explicit deterministic test fixture; HMAC signing and verification run
through the real API implementation. This is transport/contract evidence, not
proof of an external provider's evidence or model qualification.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
SIGNING_KEY = "stage8-real-network-test-signing-key"
PROMPT = "Извлеки данные: Выручка $1,000,000, Расходы $200,000."


def create_test_app():
    """Uvicorn factory with deterministic E2 fixture and the real API/HMAC path."""
    os.environ["JAMP_SIGNING_KEY"] = SIGNING_KEY
    os.environ["JAMP_ENV"] = "test"

    app_module = importlib.import_module("jamp.api.app")

    def deterministic_executor(model: str, payload: dict[str, Any]) -> dict[str, str]:
        del payload
        return {
            "provider": "openrouter",
            "model": model,
            "provider_response_id": "stage8-real-network-fixture",
            "provider_model_id": model,
            "content": "Выручка: $1,000,000; Расходы: $200,000.",
        }

    def deterministic_e2_fixture(output: dict[str, Any]) -> tuple[str, dict[str, str]]:
        del output
        return "VERIFIED", {"reason": "STAGE8_EXPLICIT_TEST_FIXTURE"}

    # This test fixture substitutes only the E2 provider-evidence boundary.
    # The API routes, verdict creation, HMAC-SHA256, and verification are real.
    app_module.verify_generation = deterministic_e2_fixture
    from jamp.api import create_app

    app = create_app(executor=deterministic_executor)

    # Pre-#463 main: jamp.api.auth not yet present. After #463 merges,
    # this guard becomes dead code — cleanup: issue #466.
    try:
        from jamp.api.auth import OrganizationContext, require_api_key
    except ImportError:
        return app

    app.dependency_overrides[require_api_key] = lambda: OrganizationContext("b2b-test", "b2b-test")
    return app


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
        body = exc.read()

    print(f"[HTTP CLIENT] {method} {path} -> HTTP {status}; Content-Type={content_type}")
    if status != 200:
        detail = body.decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} returned HTTP {status}: {detail}")
    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{method} {path} did not return a JSON object")
    return decoded


def _wait_for_server(proc: subprocess.Popen[bytes], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Uvicorn exited before readiness (exit={proc.returncode})")
        try:
            with urllib.request.urlopen(f"{BASE_URL}/openapi.json", timeout=1) as response:
                if response.status == 200:
                    print("[HTTP CLIENT] Uvicorn readiness confirmed over HTTP.")
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise TimeoutError(f"Uvicorn did not become ready within {timeout:.0f}s")


def run_e2e() -> int:
    print("=== JAMP STAGE 8: REAL NETWORK HTTP E2E ===")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(("src", "."))
    env["JAMP_SIGNING_KEY"] = SIGNING_KEY
    env["JAMP_ENV"] = "test"

    server_log_path = Path("uvicorn-server.log")
    with server_log_path.open("w", encoding="utf-8") as server_log:
        print("[*] Starting Uvicorn in a separate process...")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "experiments.b2b_client.run_b2b_client:create_test_app",
                "--factory",
                "--host",
                HOST,
                "--port",
                str(PORT),
                "--log-level",
                "info",
                "--access-log",
            ],
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_server(proc)

            payload = {
                "request_id": "b2b-real-network",
                "intent": "search_and_extraction",
                "prompt": PROMPT,
            }
            print("[*] Sending real HTTP POST /v1/execute...")
            response = _request_json("POST", "/v1/execute", payload)
            verdict = response.get("verdict")
            if not isinstance(verdict, dict):
                raise RuntimeError(
                    f"No verdict returned over HTTP (status={response.get('status')!r}, "
                    f"reason={response.get('reason')!r})"
                )
            if response.get("status") != "EXECUTE" or response.get("evidence_status") != "VERIFIED":
                raise RuntimeError(
                    "HTTP execution response did not satisfy the explicit E2 fixture contract"
                )
            if verdict.get("status") != "VERIFIED":
                raise RuntimeError("Returned verdict status was not VERIFIED")
            print(f"[B2B CLIENT] Received verdict over HTTP: {verdict['status']}.")

            print("[*] Verifying the original verdict over HTTP...")
            valid_result = _request_json("POST", "/v1/verify-verdict", verdict)
            if valid_result.get("valid") is not True:
                raise RuntimeError("HTTP signature verification rejected the original verdict")
            print("[B2B CLIENT] Cryptographic signature validation: VALID.")

            tampered = dict(verdict)
            signature = tampered.get("signature")
            if not isinstance(signature, str) or not signature:
                raise RuntimeError("Verdict did not contain a signature")
            tampered["signature"] = ("0" if signature[0] != "0" else "1") + signature[1:]
            print("[*] Verifying the tampered verdict over HTTP...")
            invalid_result = _request_json("POST", "/v1/verify-verdict", tampered)
            if invalid_result.get("valid") is not False:
                raise RuntimeError("HTTP signature verifier accepted the tampered signature")
            print("[B2B CLIENT] Tampered signature validation: INVALID.")
            print("RESULT: B2B TRUST LAYER REAL HTTP E2 VERIFIED")
            print(
                "SCOPE: real loopback HTTP + real HMAC verification; E2 evidence is a test fixture."
            )
            return 0
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            print(f"[*] Uvicorn stopped (exit={proc.returncode}).")


if __name__ == "__main__":
    raise SystemExit(run_e2e())
