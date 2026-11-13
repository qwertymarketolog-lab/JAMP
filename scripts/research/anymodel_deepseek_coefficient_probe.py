#!/usr/bin/env python3
"""One-request AnyModel DeepSeek coefficient probe.

The default mode performs one catalog GET and at most one chat-completions POST.
It never retries or follows redirects. Balance reconciliation is a separate,
offline operation so the operator can inspect the dashboard after the request.
This probe is billing/transport evidence only; it never qualifies or routes a model.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

OUT = pathlib.Path("artifacts/research/deepseek_coefficient_probe")
CATALOG_URL = os.environ.get("ANYMODEL_CATALOG_URL", "https://anymodel.org/v1/models")
CHAT_URL = os.environ.get("ANYMODEL_CHAT_URL", "https://anymodel.org/v1/chat/completions")
MODEL_ID = "ds/deepseek-v4-pro"
FROZEN_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
PROMPT = "Reply with the word OK."
def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(serialized + "\n", encoding="utf-8")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, new_url: str
    ) -> None:
        return None


def request_once(
    url: str,
    method: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int | None, bytes, dict[str, str], float, str | None]:
    data = (
        None
        if payload is None
        else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "JAMP-DeepSeek-Coefficient-Probe/1.0",
        },
    )
    opener = urllib.request.build_opener(NoRedirect)
    started = time.monotonic()
    try:
        with opener.open(request, timeout=45) as response:
            return (
                response.status,
                response.read(),
                dict(response.headers.items()),
                round(time.monotonic() - started, 6),
                None,
            )
    except urllib.error.HTTPError as exc:
        return (
            exc.code,
            exc.read(),
            dict(exc.headers.items()) if exc.headers else {},
            round(time.monotonic() - started, 6),
            None,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, b"", {}, round(time.monotonic() - started, 6), f"{type(exc).__name__}: {exc}"


def parse_coefficient(billing: dict[str, Any]) -> tuple[float, float] | None:
    """Normalize scalar or per-direction billing coefficients; reject ambiguity."""
    coefficient = billing.get("coefficient")

    def valid_number(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )

    if valid_number(coefficient):
        value = float(coefficient)
        return value, value
    if isinstance(coefficient, dict):
        input_value = coefficient.get("input")
        output_value = coefficient.get("output")
        if valid_number(input_value) and valid_number(output_value):
            return float(input_value), float(output_value)
    return None


def finalize(manifest: dict[str, Any], events: list[dict[str, Any]]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest["finished_at"] = now()
    write_json(OUT / "run_manifest.json", manifest)
    write_json(OUT / "decision.json", {
        "experiment_id": "jamp-anymodel-deepseek-coefficient-probe",
        "status": manifest["status"],
        "outcome": manifest["outcome"],
        "reason": manifest["reason"],
        "model_qualification": "NOT_STARTED",
        "routing_eligibility": "REFUSE",
        "stage_b_authorized": False,
        "balance_reconciliation": manifest.get("balance_reconciliation", "MANUAL_REQUIRED"),
        "frozen_core_delta_zero": manifest["frozen_core"]["delta_zero"],
    })
    (OUT / "events.jsonl").write_text(
        "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    checks = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checks.append(f"{sha256(path.read_bytes())}  {path.name}")
    (OUT / "checksums.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
    summary = {
        "status": manifest["status"],
        "outcome": manifest["outcome"],
        "reason": manifest["reason"],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def run_probe(balance_before: str | None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()
    events: list[dict[str, Any]] = []

    def event(name: str, **fields: Any) -> None:
        events.append(
            {
                "observed_at": now(),
                "event_type": name,
                "evidence_class": "RAW_OBSERVATION",
                **fields,
            }
        )

    try:
        frozen = subprocess.check_output(
            ["git", "rev-parse", "HEAD:src/jamp/run.py"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        frozen = None
    frozen_ok = frozen == FROZEN_BLOB
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_id": "jamp-anymodel-deepseek-coefficient-probe",
        "status": "RUNNING",
        "outcome": "INCONCLUSIVE",
        "created_at": now(),
        "github": {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "ref": os.getenv("GITHUB_REF"),
            "sha": os.getenv("GITHUB_SHA"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        },
        "provider": {"name": "AnyModel", "catalog_url": CATALOG_URL, "chat_url": CHAT_URL},
        "model": {"requested_id": MODEL_ID, "provider_response_model": None},
        "request": {
            "method": "POST",
            "max_tokens": 16,
            "temperature": 0,
            "prompt": PROMPT,
            "retry_count": 0,
            "redirects_followed": 0,
            "max_chat_posts": 1,
        },
        "balance_before_units": (
            int(balance_before)
            if balance_before and balance_before.isdigit()
            else None
        ),
        "balance_after_units": None,
        "balance_reconciliation": "MANUAL_REQUIRED",
        "frozen_core": {
            "path": "src/jamp/run.py",
            "expected_blob": FROZEN_BLOB,
            "observed_blob": frozen,
            "delta_zero": frozen_ok,
        },
        "qualification": "NOT_STARTED",
        "routing_eligibility": "REFUSE",
    }
    event(
        "RUN_STARTED",
        frozen_core_blob=frozen,
        frozen_core_delta_zero=frozen_ok,
        balance_before_units=manifest["balance_before_units"],
    )

    if not frozen_ok:
        manifest.update(
            status="BLOCKED",
            outcome="INCONCLUSIVE",
            reason="Frozen Core baseline mismatch; no API calls made",
        )
        event("BLOCKED", reason=manifest["reason"])
        return finalize(manifest, events)

    api_key = os.getenv("ANYMODEL_API_KEY", "")
    if not api_key:
        manifest.update(
            status="BLOCKED",
            outcome="FAILED",
            reason="ANYMODEL_API_KEY secret missing; no API calls made",
        )
        event("BLOCKED", reason=manifest["reason"])
        return finalize(manifest, events)
    if manifest["balance_before_units"] is None:
        manifest.update(
            status="BLOCKED",
            outcome="INCONCLUSIVE",
            reason=(
                "A numeric pre-request balance in balance units is required; "
                "no API calls made"
            ),
        )
        event("BLOCKED", reason=manifest["reason"])
        return finalize(manifest, events)

    status, raw, headers, elapsed, error = request_once(CATALOG_URL, "GET", api_key)
    (OUT / "catalog_raw.json").write_bytes(raw)
    event(
        "CATALOG_RESPONSE",
        http_status=status,
        elapsed_seconds=elapsed,
        response_sha256=sha256(raw),
        transport_error=error,
    )
    if error or status != 200:
        manifest.update(
            status="FAILED",
            outcome="FAILED",
            reason=f"Catalog GET failed: {error or status}",
        )
        return finalize(manifest, events)
    try:
        catalog = json.loads(raw.decode("utf-8"))
        rows = catalog.get("data", catalog) if isinstance(catalog, dict) else catalog
        if not isinstance(rows, list):
            raise ValueError("catalog root is not a list")
        candidates = [r for r in rows if isinstance(r, dict) and r.get("id") == MODEL_ID]
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        manifest.update(
            status="FAILED",
            outcome="INCONCLUSIVE",
            reason=f"Catalog parse failed: {type(exc).__name__}",
        )
        return finalize(manifest, events)
    manifest["catalog"] = {
        "http_status": status,
        "response_sha256": sha256(raw),
        "model_count": len(rows),
        "exact_match_count": len(candidates),
    }
    if len(candidates) != 1:
        manifest.update(
            status="BLOCKED",
            outcome="INCONCLUSIVE",
            reason=(
                f"Expected exactly one exact catalog ID; found {len(candidates)}. "
                "No POST made."
            ),
        )
        event("CATALOG_MATCH", exact_match_count=len(candidates))
        return finalize(manifest, events)
    billing = candidates[0].get("billing")
    coefficients = parse_coefficient(billing) if isinstance(billing, dict) else None
    coefficient_evidence = (
        {"billing.coefficient.input": coefficients[0],
         "billing.coefficient.output": coefficients[1]}
        if coefficients is not None else {}
    )
    manifest["catalog"]["coefficient_evidence"] = coefficient_evidence
    manifest["catalog"]["coefficient"] = (
        {"input": coefficients[0], "output": coefficients[1]}
        if coefficients is not None else None
    )
    event(
        "CATALOG_MATCH",
        model_id=MODEL_ID,
        coefficient=manifest["catalog"]["coefficient"],
        coefficient_evidence=coefficient_evidence,
    )
    if coefficients is None:
        manifest.update(
            status="BLOCKED",
            outcome="INCONCLUSIVE",
            reason="Catalog coefficient absent, conflicting, or invalid. No POST made.",
        )
        return finalize(manifest, events)

    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 16,
        "temperature": 0,
    }
    chat_status, chat_raw, chat_headers, chat_elapsed, chat_error = request_once(
        CHAT_URL, "POST", api_key, payload
    )
    (OUT / "chat_raw.json").write_bytes(chat_raw)
    event(
        "CHAT_RESPONSE",
        http_status=chat_status,
        elapsed_seconds=chat_elapsed,
        response_sha256=sha256(chat_raw),
        transport_error=chat_error,
    )
    parsed: Any = None
    with contextlib.suppress(UnicodeDecodeError, json.JSONDecodeError):
        parsed = json.loads(chat_raw.decode("utf-8")) if chat_raw else None
    usage_value = parsed.get("usage") if isinstance(parsed, dict) else None
    usage = usage_value if isinstance(usage_value, dict) else {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if (
        isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool)
        and isinstance(completion_tokens, int) and not isinstance(completion_tokens, bool)
        and coefficients is not None
    ):
        computed_total = prompt_tokens + completion_tokens
        expected = (
            prompt_tokens * coefficients[0]
            + completion_tokens * coefficients[1]
        )
    else:
        computed_total = None
        expected = None
    choices = parsed.get("choices") if isinstance(parsed, dict) else None
    message = (
        choices[0].get("message", {})
        if isinstance(choices, list) and choices and isinstance(choices[0], dict)
        else {}
    )
    manifest["model"]["provider_response_model"] = (
        parsed.get("model") if isinstance(parsed, dict) else None
    )
    manifest["chat"] = {
        "http_status": chat_status,
        "elapsed_seconds": chat_elapsed,
        "response_sha256": sha256(chat_raw),
        "response_id": parsed.get("id") if isinstance(parsed, dict) else None,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "computed_total_tokens": computed_total,
        "expected_balance_units": expected,
        "assistant_content": message.get("content") if isinstance(message, dict) else None,
    }
    if chat_error or chat_status != 200:
        manifest.update(
            status="FAILED",
            outcome="FAILED",
            reason=f"Chat POST failed: {chat_error or chat_status}",
        )
    elif expected is None or total_tokens != computed_total:
        manifest.update(
            status="COMPLETED",
            outcome="INCONCLUSIVE",
            reason=(
                "Response usage missing or internally inconsistent; "
                "balance reconciliation unavailable"
            ),
        )
    else:
        manifest.update(
            status="COMPLETED",
            outcome="INCONCLUSIVE",
            reason=(
                "One request completed; waiting for post-request dashboard balance "
                "to verify coefficient"
            ),
        )
    event(
        "PROBE_COMPLETED",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        expected_balance_units=expected,
    )
    return finalize(manifest, events)


def verify_balance(after_units: str) -> int:
    path = OUT / "run_manifest.json"
    if not path.exists():
        raise SystemExit("run_manifest.json not found; run probe first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    before = manifest.get("balance_before_units")
    expected = manifest.get("chat", {}).get("expected_balance_units")
    if (
        not isinstance(before, int)
        or not isinstance(expected, (int, float))
        or not after_units.isdigit()
    ):
        manifest["balance_reconciliation"] = "AMBIGUOUS"
        manifest["outcome"] = "INCONCLUSIVE"
        manifest["reason"] = "Balance inputs or expected debit are missing/invalid"
    else:
        after = int(after_units)
        actual = before - after
        manifest["balance_after_units"] = after
        manifest["actual_balance_debit_units"] = actual
        manifest["balance_reconciliation"] = "MATCH" if actual == expected else "AMBIGUOUS"
        manifest["outcome"] = manifest["balance_reconciliation"]
        manifest["reason"] = (
            "Exact balance debit matches catalog coefficient"
            if actual == expected
            else "Actual balance debit differs from coefficient-based expected debit"
        )
    events_path = OUT / "events.jsonl"
    events = (
        [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
        ]
        if events_path.exists()
        else []
    )
    events.append(
        {
            "observed_at": now(),
            "event_type": "BALANCE_RECONCILIATION",
            "evidence_class": "OPERATOR_SUPPLIED_OBSERVATION",
            "balance_after_units": (
                int(after_units) if after_units.isdigit() else None
            ),
            "result": manifest["balance_reconciliation"],
        }
    )
    manifest["updated_at"] = now()
    return finalize(manifest, events)


def run_self_tests() -> int:
    import io
    import unittest
    from unittest.mock import patch

    class ProbeTests(unittest.TestCase):
        def test_coefficient_as_number(self) -> None:
            self.assertEqual(parse_coefficient({"coefficient": 4}), (4.0, 4.0))

        def test_coefficient_as_object(self) -> None:
            self.assertEqual(
                parse_coefficient({"coefficient": {"input": 0.5, "output": 0.5}}),
                (0.5, 0.5),
            )

        def test_coefficient_missing_input_fails_closed(self) -> None:
            self.assertIsNone(
                parse_coefficient({"coefficient": {"output": 0.5}})
            )

        def test_coefficient_malformed_fails_closed(self) -> None:
            self.assertIsNone(parse_coefficient({"coefficient": "0.5"}))

        def test_redirect_is_not_followed_and_request_is_single(self) -> None:
            class FakeOpener:
                calls = 0
                def open(self, request: Any, timeout: int = 45) -> Any:
                    self.calls += 1
                    self.asserted_method = request.get_method()
                    raise urllib.error.HTTPError(
                        request.full_url, 302, "redirect", {}, io.BytesIO(b"redirect")
                    )

            fake = FakeOpener()
            with patch("urllib.request.build_opener", return_value=fake):
                status, body, _, _, error = request_once(
                    "https://example.invalid/probe", "POST", "not-a-real-key",
                    {"model": MODEL_ID},
                )
            self.assertEqual(status, 302)
            self.assertEqual(body, b"redirect")
            self.assertIsNone(error)
            self.assertEqual(fake.calls, 1)
            self.assertEqual(fake.asserted_method, "POST")

        def test_redirect_handler_refuses_redirect(self) -> None:
            handler = NoRedirect()
            self.assertIsNone(
                handler.redirect_request(
                    None, None, 302, "Found", {}, "https://example.invalid"
                )
            )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProbeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--balance-before-units", default=os.getenv("ANYMODEL_BALANCE_BEFORE_UNITS")
    )
    parser.add_argument(
        "--verify-balance-after-units",
        help="Offline reconciliation; does not call AnyModel",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run offline mock tests; never calls AnyModel",
    )
    args = parser.parse_args()
    if args.self_test:
        return run_self_tests()
    if args.verify_balance_after_units is not None:
        return verify_balance(args.verify_balance_after_units)
    return run_probe(args.balance_before_units)


if __name__ == "__main__":
    raise SystemExit(main())
