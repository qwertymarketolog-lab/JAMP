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
        if expected not in {"VERIFIED", "PARTIAL", "REFUSE", "INCONCLUSIVE", "INCONCLUSIVE/REFUSE"}:
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
        handle.write(
            json.dumps(
                {"case_trace_id": trace_id, "provenance": trace},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
    return None


def _model_response_details(response: dict[str, Any]) -> dict[str, Any]:
    """Extract model response and E4/provenance metadata without inventing evidence."""
    status = response.get("status")
    trace_id = response.get("trace_id")
    provenance_url = (
        f"/v1/provenance/{trace_id}"
        if isinstance(trace_id, str) and trace_id.startswith("trace_")
        else None
    )

    if status in {"REFUSE", "INCONCLUSIVE"}:
        model_response = None
        model_response_reason = "refused_before_generation"
    else:
        output = response.get("output")
        content = output.get("content") if isinstance(output, dict) else None
        if isinstance(content, str):
            model_response = content
            model_response_reason = None
        else:
            model_response = None
            model_response_reason = "model_response_unavailable"

    e4_status = response.get("e4_status")
    e4_details = response.get("e4_details")
    if not isinstance(e4_status, str) and isinstance(e4_details, dict):
        e4_status = e4_details.get("e4_status")

    if not isinstance(e4_status, str) or not e4_status:
        claims = response.get("claims")
        claim_statuses = (
            {
                claim.get("status")
                for claim in claims
                if isinstance(claim, dict)
                and claim.get("source") == "E4_MOEX"
                and isinstance(claim.get("status"), str)
                and claim.get("status")
            }
            if isinstance(claims, list)
            else set()
        )
        if not claim_statuses:
            e4_status = "NOT_EVALUATED"
        elif len(claim_statuses) == 1:
            e4_status = next(iter(claim_statuses))
        else:
            e4_status = "MIXED"

    return {
        "model_response": model_response,
        "model_response_reason": model_response_reason,
        "provenance_url": provenance_url,
        "e4_status": e4_status,
    }


def _markdown_cell(value: Any, *, limit: int | None = None) -> str:
    if value is None:
        return "—"
    cell = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    if limit is not None and len(cell) > limit:
        cell = cell[: limit - 1] + "…"
    return cell or "—"


def _build_markdown_report(
    report: dict[str, Any], *, run_id: str, sha: str, generated_at_utc: str
) -> str:
    lines = [
        "# Stock Audit v2 — отчёт",
        "",
        f"- Run ID: {run_id}",
        f"- SHA: {sha}",
        f"- Date (UTC): {generated_at_utc}",
        f"- Result: {report.get('result', 'UNKNOWN')}",
        "",
        "| ID | Вопрос | Статус | Ответ модели | Ссылка на provenance |",
        "| --- | --- | --- | --- | --- |",
    ]
    cases = report.get("cases", [])
    for record in cases if isinstance(cases, list) else []:
        if not isinstance(record, dict):
            continue
        status = f"{record.get('result', 'UNKNOWN')} / {record.get('status', 'UNKNOWN')}"
        provenance_url = record.get("provenance_url")
        provenance_cell = (
            f"[provenance]({provenance_url})"
            if isinstance(provenance_url, str) and provenance_url
            else "—"
        )
        answer = record.get("model_response")
        if answer is None and record.get("model_response_reason"):
            answer = f"— ({record['model_response_reason']})"
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(record.get("id")),
                    _markdown_cell(record.get("question")),
                    _markdown_cell(status),
                    _markdown_cell(answer, limit=200),
                    provenance_cell,
                )
            )
            + " |"
        )

    failures = (
        [
            record
            for record in cases
            if isinstance(record, dict) and record.get("result") == "FAILED"
        ]
        if isinstance(cases, list)
        else []
    )
    lines.extend(["", "## Провалы", ""])
    if not failures:
        lines.append("Нет.")
    else:
        for record in failures:
            reason = record.get("reason")
            full_reason = str(reason) if reason is not None else "failure reason missing"
            lines.append(f"- **{_markdown_cell(record.get('id'))}**: {full_reason}")
    lines.append("")
    return "\n".join(lines)


def _git_sha() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    return sha if sha else "UNKNOWN"


def _check_case(case: dict[str, Any], base_url: str, provenance_path: Path) -> dict[str, Any]:
    case_id = case["id"]
    record: dict[str, Any] = dict(
        id=case_id, question=case["text"], expected_behavior=case["expected_behavior"],
        started_at_utc=datetime.now(UTC).isoformat(), http_status=None,
        status="UNKNOWN", evidence_status="UNKNOWN", aggregate_status="UNKNOWN",
        trace_id=None, verdict_valid=None, provenance_export="NOT_ATTEMPTED",
        result="FAILED", reason=None, response_reason=None, model_response=None,
        model_response_reason=None, provenance_url=None, e4_status="NOT_EVALUATED",
    )
    try:
        http_status, response = _http_json(
            f"{base_url}/v1/execute",
            payload={
                "intent": "search_and_extraction",
                "prompt": case["text"],
                "request_id": f"stock-audit-v2-{case_id}-{int(time.time())}",
            },
        )
        record.update(
            {
                "http_status": http_status,
                "status": response.get("status", "UNKNOWN"),
                "evidence_status": response.get("evidence_status", "UNKNOWN"),
                "aggregate_status": response.get("aggregate_status", "UNKNOWN"),
                "response_reason": response.get("reason"),
                "trace_id": response.get("trace_id"),
            }
        )
        record.update(_model_response_details(response))
        if record["evidence_status"] == "UNKNOWN" and isinstance(response.get("output"), dict):
            record["evidence_status"] = response["output"].get("evidence_status", "UNKNOWN")
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
    report_path = ARTIFACT_DIR / "stock_audit_v2_report.json"
    markdown_report_path = ARTIFACT_DIR / "stock_audit_v2_report.md"
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
            print("[STOCK AUDIT V2] Starting real Uvicorn HTTP server", flush=True)
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            deadline = time.monotonic() + STARTUP_TIMEOUT
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AuditError(
                        f"Uvicorn exited before readiness (exit={process.returncode}); "
                        "inspect artifact log"
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
    finished_at_utc = datetime.now(UTC).isoformat()
    run_id = os.environ.get("GITHUB_RUN_ID", "UNKNOWN")
    run_sha = os.environ.get("GITHUB_SHA") or _git_sha()
    report = {
        "schema_version": "stock-audit-v2-report-v1",
        "run_id": run_id,
        "sha": run_sha,
        "started_at_utc": results[0]["started_at_utc"] if results else None,
        "finished_at_utc": finished_at_utc,
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
    markdown_report = _build_markdown_report(
        report,
        run_id=run_id,
        sha=run_sha,
        generated_at_utc=finished_at_utc,
    )
    markdown_report_path.write_text(markdown_report, encoding="utf-8")
    print(f"[STOCK AUDIT V2] PASSED={passed} FAILED={failed} TOTAL={len(results)}", flush=True)
    print(f"[STOCK AUDIT V2] Report: {report_path}", flush=True)
    print(f"[STOCK AUDIT V2] Markdown report: {markdown_report_path}", flush=True)
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
        print(
            f"[STOCK AUDIT V2] HOLD/FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
