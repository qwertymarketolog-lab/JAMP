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

from jamp.stock_audit_acceptance import evaluate_acceptance

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "experiments" / "crypto_audit" / "test_cases"
ARTIFACT_DIR = ROOT / "artifacts" / "crypto-audit-v1"
REQUEST_TIMEOUT = 120.0
STARTUP_TIMEOUT = 45.0
EXPECTED_IDS = [f"C{i:02d}" for i in range(1, 13)]


class AuditError(RuntimeError):
    """A required Crypto Audit v1 condition was not met."""


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
    files = sorted(CASES_DIR.glob("C*.json"))
    if len(files) != 12:
        raise AuditError(f"Expected exactly 12 JSON cases, found {len(files)}")
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
        if not isinstance(case.get("e4_claim"), dict):
            raise AuditError(f"Missing structured e4_claim in {path.name}")
        if case.get("expected_behavior") not in {
            "VERIFIED", "PARTIAL", "REFUSE", "INCONCLUSIVE", "INCONCLUSIVE/REFUSE"
        }:
            raise AuditError(f"Unsupported expected_behavior in {path.name}")
        if "acceptance_rule" in case and not isinstance(case["acceptance_rule"], dict):
            raise AuditError(f"Invalid acceptance_rule in {path.name}")
        cases.append(case)
    return cases


def _save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\\n",
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
        handle.write(
            json.dumps(
                {"case_trace_id": trace_id, "provenance": trace},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\\n"
        )
    return None


def _model_response_details(response: dict[str, Any]) -> dict[str, Any]:
    """Preserve the complete model response and CoinGecko evidence."""
    output = response.get("output")
    content = output.get("content") if isinstance(output, dict) else None
    model_response = content if isinstance(content, str) else None
    trace_id = response.get("trace_id")
    provenance_url = (
        f"/v1/provenance/{trace_id}"
        if isinstance(trace_id, str) and trace_id.startswith("trace_")
        else None
    )
    claims = response.get("claims")
    crypto_claims = (
        [
            claim for claim in claims
            if isinstance(claim, dict) and claim.get("source") == "E4_COINGECKO"
        ]
        if isinstance(claims, list)
        else []
    )
    statuses = {
        claim.get("status") for claim in crypto_claims
        if isinstance(claim.get("status"), str) and claim.get("status")
    }
    if not statuses:
        e4_status = "NOT_EVALUATED"
    elif len(statuses) == 1:
        e4_status = next(iter(statuses))
    else:
        e4_status = "MIXED"
    evidence = crypto_claims[0].get("evidence") if crypto_claims else None
    return {
        "model_response": model_response,
        "model_response_reason": None if model_response is not None else "model_response_unavailable",
        "provenance_url": provenance_url,
        "e4_status": e4_status,
        "e4_details": evidence if isinstance(evidence, dict) else None,
    }


def _markdown_cell(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("\\r", " ").replace("\\n", " ").replace("|", "\\\\|") or "—"


def _build_markdown_report(
    report: dict[str, Any], *, run_id: str, sha: str, generated_at_utc: str
) -> str:
    lines = [
        "# Crypto Audit v1 — отчёт",
        "",
        f"- Run ID: {run_id}",
        f"- SHA: {sha}",
        f"- Date (UTC): {generated_at_utc}",
        f"- Result: {report.get('result', 'UNKNOWN')}",
        "",
        "| ID | Вопрос | Статус | Полный ответ модели | E4 |",
        "| --- | --- | --- | --- | --- |",
    ]
    records = report.get("cases", [])
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(record.get("id")),
                    _markdown_cell(record.get("question")),
                    _markdown_cell(
                        f"{record.get('result', 'UNKNOWN')} / {record.get('status', 'UNKNOWN')}"
                    ),
                    _markdown_cell(record.get("model_response") or record.get("model_response_reason")),
                    _markdown_cell(record.get("e4_status")),
                )
            )
            + " |"
        )
    lines.extend(["", "## Диагностика", ""])
    for record in records if isinstance(records, list) else []:
        if isinstance(record, dict):
            evidence_json = json.dumps(record.get("e4_details"), ensure_ascii=False, sort_keys=True)
            lines.extend(
                [
                    f"### {record.get('id', 'UNKNOWN')}",
                    "",
                    f"- E4 details: {evidence_json}",
                    f"- Acceptance: {record.get('reason', 'UNKNOWN')}",
                    "",
                    "Полный ответ модели:",
                    "",
                    "<pre>",
                    str(record.get("model_response") or record.get("model_response_reason") or "UNKNOWN"),
                    "</pre>",
                    "",
                ]
            )
    return "\\n".join(lines) + "\\n"


def _git_sha() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    return sha if sha else "UNKNOWN"


def _check_case(case: dict[str, Any], base_url: str, provenance_path: Path) -> dict[str, Any]:
    case_id = case["id"]
    record: dict[str, Any] = {
        "id": case_id,
        "question": case["text"],
        "expected_behavior": case["expected_behavior"],
        "started_at_utc": datetime.now(UTC).isoformat(),
        "http_status": None,
        "status": "UNKNOWN",
        "evidence_status": "UNKNOWN",
        "aggregate_status": "UNKNOWN",
        "verdict_valid": None,
        "provenance_export": "NOT_ATTEMPTED",
        "result": "FAILED",
        "response_reason": None,
    }
    try:
        http_status, response = _http_json(
            f"{base_url}/v1/execute",
            payload={
                "intent": "search_and_extraction",
                "prompt": case["text"],
                "e4_claim": case["e4_claim"],
                "request_id": f"crypto-audit-v1-{case_id}-{int(time.time())}",
            },
        )
        record["http_status"] = http_status
        record["status"] = response.get("status", "UNKNOWN")
        record["evidence_status"] = response.get("evidence_status", "UNKNOWN")
        record["aggregate_status"] = response.get("aggregate_status", "UNKNOWN")
        record["response_reason"] = response.get("reason")
        record["trace_id"] = response.get("trace_id")
        record.update(_model_response_details(response))
        export_error = _save_provenance(base_url, record["trace_id"], provenance_path)
        record["provenance_export"] = "SAVED" if export_error is None else "FAILED"
        if record["status"] == "EXECUTE" and record["evidence_status"] == "VERIFIED":
            record["verdict_valid"] = False
            verdict = response.get("verdict")
            if isinstance(verdict, dict) and verdict.get("trace_id") == record["trace_id"]:
                verify_status, verification = _http_json(
                    f"{base_url}/v1/verify-verdict", payload=verdict, timeout=20
                )
                record["verdict_valid"] = (
                    verify_status == 200 and verification.get("valid") is True
                )
        passed, reason = evaluate_acceptance(case, record)
        record["result"] = "PASSED" if passed else "FAILED"
        record["reason"] = reason
        return record
    except (AuditError, OSError, ValueError) as exc:
        record["reason"] = f"{type(exc).__name__}: {exc}"
        return record
    finally:
        record["finished_at_utc"] = datetime.now(UTC).isoformat()


def run() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = ARTIFACT_DIR / "crypto_audit_v1_report.json"
    markdown_report_path = ARTIFACT_DIR / "report.md"
    provenance_path = ARTIFACT_DIR / "crypto_audit_v1_provenance.jsonl"
    server_log_path = ARTIFACT_DIR / "uvicorn.log"
    results_path = ARTIFACT_DIR / "crypto_audit_v1_results.jsonl"
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

    process: subprocess.Popen[str] | None = None
    results: list[dict[str, Any]] = []
    try:
        with server_log_path.open("w", encoding="utf-8") as server_log:
            command = [
                sys.executable, "-m", "uvicorn", "jamp.api.app:create_app", "--factory",
                "--host", "127.0.0.1", "--port", str(port), "--log-level", "info",
            ]
            print("[CRYPTO AUDIT V1] Starting real Uvicorn HTTP server", flush=True)
            process = subprocess.Popen(
                command, cwd=ROOT, env=env, stdout=server_log,
                stderr=subprocess.STDOUT, text=True,
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

            print(f"[CRYPTO AUDIT V1] HTTP server ready at {base_url}", flush=True)
            for case in cases:
                result = _check_case(case, base_url, provenance_path)
                results.append(result)
                with results_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\\n")
                print(
                    f"[{result['result']}] {case['id']} expected={case['expected_behavior']} "
                    f"status={result['status']} e4={result['e4_status']} "
                    f"trace={result.get('trace_id')} reason={result.get('reason')}",
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
    finished_at_utc = datetime.now(UTC).isoformat()
    run_id = os.environ.get("GITHUB_RUN_ID", "UNKNOWN")
    run_sha = os.environ.get("GITHUB_SHA") or _git_sha()
    report = {
        "schema_version": "crypto-audit-v1-report-v1",
        "run_id": run_id,
        "sha": run_sha,
        "started_at_utc": results[0]["started_at_utc"] if results else None,
        "finished_at_utc": finished_at_utc,
        "expected_cases": 12,
        "observed_cases": len(results),
        "passed": passed,
        "failed": failed,
        "result": "CRYPTO AUDIT V1 PASSED" if len(results) == 12 and failed == 0 else "HOLD/FAILED",
        "scope_warning": (
            "This harness verifies JAMP execution/refusal behavior and bounded CoinGecko claims. "
            "Historical movements, predictions and multi-asset comparisons remain outside E4 scope. "
            "CoinGecko absence does not prove that a DEX-only token does not exist."
        ),
        "cases": results,
    }
    _save_json(report_path, report)
    markdown_report_path.write_text(
        _build_markdown_report(
            report, run_id=run_id, sha=run_sha, generated_at_utc=finished_at_utc
        ),
        encoding="utf-8",
    )
    print(f"[CRYPTO AUDIT V1] PASSED={passed} FAILED={failed} TOTAL={len(results)}", flush=True)
    print(f"[CRYPTO AUDIT V1] JSON report: {report_path}", flush=True)
    print(f"[CRYPTO AUDIT V1] Markdown report: {markdown_report_path}", flush=True)
    if len(results) == 12 and failed == 0:
        print("RESULT: CRYPTO AUDIT V1 PASSED", flush=True)
        return 0
    print("RESULT: CRYPTO AUDIT V1 FAILED/HOLD", flush=True)
    return 1


def main() -> int:
    try:
        return run()
    except Exception as exc:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        _save_json(
            ARTIFACT_DIR / "crypto_audit_v1_report.json",
            {
                "result": "HOLD/FAILED",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "timestamp_utc": datetime.now(UTC).isoformat(),
            },
        )
        print(
            f"[CRYPTO AUDIT V1] HOLD/FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
