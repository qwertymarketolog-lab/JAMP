from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "experiments" / "stock_audit" / "test_cases"
ARTIFACT_DIR = ROOT / "artifacts" / "stock-audit-v2"
REQUEST_TIMEOUT = 120.0
STARTUP_TIMEOUT = 45.0
EXPECTED_IDS = [f"T{i:02d}" for i in range(1, 25)]


class AuditError(RuntimeError):
    """A required Stock Audit v2 condition was not met."""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = REQUEST_TIMEOUT,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise AuditError(f"HTTP transport failed: {type(exc).__name__}") from None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AuditError(f"HTTP {status} response was not valid JSON") from None
    if not isinstance(decoded, dict):
        raise AuditError(f"HTTP {status} response JSON was not an object")
    return status, decoded


def _load_cases() -> list[dict[str, Any]]:
    if not CASES_DIR.is_dir():
        raise AuditError(f"Test case directory is missing: {CASES_DIR}")
    files = sorted(CASES_DIR.glob("T*.json"))
    if len(files) != 24:
        raise AuditError(f"Expected exactly 24 JSON cases, found {len(files)}")
    cases: list[dict[str, Any]] = []
    for expected_id, path in zip(EXPECTED_IDS, files, strict=True):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditError(f"Cannot load {path.name}: {type(exc).__name__}") from None
        if not isinstance(case, dict) or case.get("id") != expected_id:
            raise AuditError(f"Unexpected/missing case id in {path.name}")
        if not isinstance(case.get("text"), str) or not case["text"].strip():
            raise AuditError(f"Empty text in {path.name}")
        if not isinstance(case.get("note"), str) or not case["note"].strip():
            raise AuditError(f"Empty note in {path.name}")
        expected = case.get("expected_behavior")
        if expected not in {"VERIFIED", "INCONCLUSIVE", "INCONCLUSIVE/REFUSE"}:
            raise AuditError(f"Unsupported expected_behavior in {path.name}: {expected!r}")
        cases.append(case)
    return cases


def _save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _save_provenance(base_url: str, trace_id: Any, output_path: Path) -> str | None:
    if not isinstance(trace_id, str) or not trace_id.startswith("trace_"):
        return "missing or invalid trace_id"
    try:
        status, trace = _http_json(f"{base_url}/v1/provenance/{trace_id}", timeout=15)
    except AuditError as exc:
        return str(exc)
    if status != 200:
        return f"provenance HTTP status {status}"
    if trace.get("trace_id") != trace_id:
        return "provenance trace_id mismatch"
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"case_trace_id": trace_id, "provenance": trace},
                                ensure_ascii=False, sort_keys=True) + "\n")
    return None


def _check_case(case: dict[str, Any], base_url: str, provenance_path: Path) -> dict[str, Any]:
    case_id = case["id"]
    expected = case["expected_behavior"]
    record: dict[str, Any] = {
        "id": case_id,
        "expected_behavior": expected,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "http_status": None,
        "status": "UNKNOWN",
        "evidence_status": "UNKNOWN",
        "trace_id": None,
        "verdict_valid": None,
        "provenance_export": "NOT_ATTEMPTED",
        "result": "FAILED",
        "reason": None,
    }
    try:
        http_status, response = _http_json(
            f"{base_url}/v1/execute",
            payload={
                "intent": "search_and_extraction",
                "prompt": case["text"],
                "request_id": f"stock-audit-v2-{case_id}-{int(time.time())}",
            },
        )
        record["http_status"] = http_status
        record["status"] = response.get("status", "UNKNOWN")
        record["evidence_status"] = response.get("evidence_status", "UNKNOWN")
        record["trace_id"] = response.get("trace_id")
        if record["evidence_status"] == "UNKNOWN":
            output = response.get("output")
            if isinstance(output, dict):
                record["evidence_status"] = output.get("evidence_status", "UNKNOWN")

        export_error = _save_provenance(base_url, record["trace_id"], provenance_path)
        record["provenance_export"] = "SAVED" if export_error is None else "FAILED"
        if export_error is not None:
            record["reason"] = f"provenance export failed: {export_error}"
            return record

        if case_id == "T23":
            if record["status"] in {"REFUSE", "INCONCLUSIVE"}:
                record["result"] = "PASSED"
                record["reason"] = "explicit fail-closed response for adversarial prompt"
            else:
                record["reason"] = (
                    "adversarial case was not explicitly refused/inconclusive; "
                    f"status={record['status']!r}, evidence_status={record['evidence_status']!r}"
                )
            return record

        if expected == "INCONCLUSIVE":
            if record["status"] == "REFUSE" or record["evidence_status"] == "INCONCLUSIVE":
                record["result"] = "PASSED"
                record["reason"] = "uncertainty/refusal returned for high-uncertainty case"
            else:
                record["reason"] = (
                    "expected refusal/inconclusive, got "
                    f"status={record['status']!r}, evidence_status={record['evidence_status']!r}"
                )
            return record

        if http_status != 200:
            record["reason"] = f"expected HTTP 200, got {http_status}"
            return record
        if record["status"] != "EXECUTE":
            record["reason"] = f"expected EXECUTE, got {record['status']!r}"
            return record
        if record["evidence_status"] != "VERIFIED":
            record["reason"] = f"expected evidence_status VERIFIED, got {record['evidence_status']!r}"
            return record

        verdict = response.get("verdict")
        if not isinstance(verdict, dict):
            record["reason"] = "signed verdict object missing"
            return record
        if verdict.get("trace_id") != record["trace_id"]:
            record["reason"] = "verdict trace_id does not match execution trace_id"
            return record
        verify_status, verification = _http_json(
            f"{base_url}/v1/verify-verdict", payload=verdict, timeout=20
        )
        valid = verify_status == 200 and verification.get("valid") is True
        record["verdict_valid"] = valid
        if not valid:
            record["reason"] = (
                f"verdict verification failed: HTTP {verify_status}, "
                f"valid={verification.get('valid')!r}"
            )
            return record

        record["result"] = "PASSED"
        record["reason"] = (
            "HTTP execution, evidence_status, signed-verdict validation and provenance verified; "
            "factual correctness is not independently established by this harness"
        )
        return record
    except (AuditError, OSError, ValueError) as exc:
        record["reason"] = f"{type(exc).__name__}: {exc}"
        return record
    finally:
        record["finished_at_utc"] = datetime.now(UTC).isoformat()


def run() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = ARTIFACT_DIR / "stock_audit_v2_report.json"
    provenance_path = ARTIFACT_DIR / "stock_audit_v2_provenance.jsonl"
    server_log_path = ARTIFACT_DIR / "uvicorn.log"
    results_path = ARTIFACT_DIR / "stock_audit_v2_results.jsonl"
    provenance_path.write_text("", encoding="utf-8")
    results_path.write_text("", encoding="utf-8")

    if not os.environ.get("OPENROUTER_API_KEY"):
        raise AuditError("Required secret OPENROUTER_API_KEY is missing")
    if not os.environ.get("JAMP_SIGNING_KEY"):
        raise AuditError("Required secret JAMP_SIGNING_KEY is missing")

    cases = _load_cases()
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["JAMP_ENV"] = "production"
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["JAMP_AUDIT_PATH"] = str(ARTIFACT_DIR / "server_provenance_traces.jsonl")
    env.pop("OPENROUTER_MODEL_ID_MAP", None)
    env.pop("OPENROUTER_FALLBACK_MODELS", None)
    env["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    env["JAMP_SIGNING_KEY"] = os.environ["JAMP_SIGNING_KEY"]

    process: subprocess.Popen[str] | None = None
    results: list[dict[str, Any]] = []
    try:
        with server_log_path.open("w", encoding="utf-8") as server_log:
            command = [
                sys.executable, "-m", "uvicorn", "jamp.api.app:create_app", "--factory",
                "--host", "127.0.0.1", "--port", str(port), "--log-level", "info",
            ]
            print("[STOCK AUDIT V2] Starting real Uvicorn HTTP server", flush=True)
            process = subprocess.Popen(
                command, cwd=ROOT, env=env, stdout=server_log, stderr=subprocess.STDOUT,
                text=True,
            )
            deadline = time.monotonic() + STARTUP_TIMEOUT
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AuditError(
                        f"Uvicorn exited before readiness (exit={process.returncode}); inspect artifact log"
                    )
                try:
                    status, _ = _http_json(f"{base_url}/openapi.json", timeout=2)
                    if status == 200:
                        break
                except AuditError:
                    time.sleep(0.5)
            else:
                raise AuditError("Uvicorn did not become ready before startup timeout")

            print(f"[STOCK AUDIT V2] HTTP server ready at {base_url}", flush=True)
            for case in cases:
                result = _check_case(case, base_url, provenance_path)
                results.append(result)
                with results_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                print(
                    f"[{result['result']}] {case['id']} expected={case['expected_behavior']} "
                    f"status={result['status']} evidence={result['evidence_status']} "
                    f"trace={result['trace_id']} reason={result['reason']}",
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

    passed = sum(item["result"] == "PASSED" for item in results)
    failed = len(results) - passed
    report = {
        "schema_version": "stock-audit-v2-report-v1",
        "started_at_utc": results[0]["started_at_utc"] if results else None,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "expected_cases": 24,
        "observed_cases": len(results),
        "passed": passed,
        "failed": failed,
        "result": "STOCK AUDIT V2 PASSED" if len(results) == 24 and failed == 0 else "HOLD/FAILED",
        "scope_warning": (
            "This harness verifies HTTP execution/refusal behavior, JAMP evidence status, "
            "verdict signature validation, and persisted provenance. It does not independently "
            "verify the stock-price, IPO, market-share, financial-growth, or other factual claims "
            "inside the prompts. VERIFIED here is not a claim of financial-data correctness."
        ),
        "cases": results,
    }
    _save_json(report_path, report)
    print(f"[STOCK AUDIT V2] PASSED={passed} FAILED={failed} TOTAL={len(results)}", flush=True)
    print(f"[STOCK AUDIT V2] Report: {report_path}", flush=True)
    if len(results) == 24 and failed == 0:
        print("RESULT: STOCK AUDIT V2 PASSED", flush=True)
        return 0
    print("RESULT: STOCK AUDIT V2 FAILED/HOLD", flush=True)
    return 1


def main() -> int:
    try:
        return run()
    except Exception as exc:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        failure = {
            "result": "HOLD/FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }
        _save_json(ARTIFACT_DIR / "stock_audit_v2_report.json", failure)
        print(f"[STOCK AUDIT V2] HOLD/FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
