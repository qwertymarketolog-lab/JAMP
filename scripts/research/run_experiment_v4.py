"""Guarded AnyModel E2 -> Extractor -> E4 experiment v4."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from jamp.provider.anymodel import (
    COST_PER_MILLION_TOKENS_USD,
    DEFAULT_MAX_INPUT_TOKENS,
    AnyModelBudgetError,
    AnyModelChatExecutor,
    AnyModelError,
)
from jamp.provider.coingecko_verify import verify_claim_with_coingecko
from jamp.provider.moex_verify import E4_CONTRADICTED, E4_VERIFIED, verify_claim_with_moex
from jamp.runtime.claim_adapter import to_verdict_claim
from jamp.runtime.claim_extractor import extract_claims

DEFAULT_MODEL = "ag/claude-sonnet-4-6"
LIVE_E4_PROMPT = (
    "You are a financial data assistant. Provide your best estimate of the current "
    "price of SBER stock in RUB. Do not say you cannot access live data; just provide "
    "your most accurate guess. Reply exactly: 'The price of SBER is [X] RUB'."
)
LIVE_E4_MAX_TOKENS = 256
LIVE_E4_MAX_BUDGET_USD = 0.01
MOCK_ID_RE = re.compile(r"^chatcmpl-abc123$", re.IGNORECASE)
MOCK_MODEL_IDS = {"openai/gpt-5", "gpt-5"}
MOCK_TEXT = "i'm an ai assistant"
COINGECKO_TICKER_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "USDT": "tether",
    "USDC": "usd-coin", "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
    "DOGE": "dogecoin", "DOT": "polkadot", "AVAX": "avalanche-2", "MATIC": "matic-network",
}


class _CapturedResponse:
    """Transparent response wrapper recording the complete response body."""
    def __init__(self, response: Any, capture: dict[str, Any]) -> None:
        self._response = response
        self._capture = capture

    def __enter__(self) -> _CapturedResponse:
        self._response.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return self._response.__exit__(exc_type, exc, tb)

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        body = self._response.read(*args, **kwargs)
        self._capture["body"] = body
        return body

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)


def _capturing_opener(capture: dict[str, Any], opener: Any = urlopen):
    def open_request(request: Any, timeout: float) -> _CapturedResponse:
        response = opener(request, timeout=timeout)
        capture.update(
            status_code=int(getattr(response, "status", 200)),
            reason=str(getattr(response, "reason", "")),
            headers=list(response.headers.items()),
            http_version="1.1" if getattr(response, "version", 11) == 11 else "other",
        )
        return _CapturedResponse(response, capture)
    return open_request


def _finalize_raw(capture: dict[str, Any]) -> dict[str, Any]:
    body = capture.get("body")
    if not isinstance(body, bytes):
        raise AnyModelError("AnyModel response body was not captured")
    status_line = (
        f"HTTP/{capture.get('http_version', '1.1')} "
        f"{capture.get('status_code', 0)} {capture.get('reason', '')}\r\n"
    )
    headers = "".join(f"{key}: {value}\r\n" for key, value in capture.get("headers", []))
    raw_http = (status_line + headers + "\r\n").encode("iso-8859-1") + body
    return {
        "status_code": capture.get("status_code"),
        "headers": capture.get("headers", []),
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "http_representation_base64": base64.b64encode(raw_http).decode("ascii"),
        "http_representation_sha256": hashlib.sha256(raw_http).hexdigest(),
        "capture_note": (
            "Complete headers/body exposed by urllib; HTTP representation is reconstructed "
            "from the response API, not a packet-level wire capture."
        ),
    }


_PROVIDER_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def _redact_diagnostic(value: Any, api_key: str | None) -> str:
    text = str(value)
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    return _PROVIDER_SECRET_RE.sub("[REDACTED]", text)


def _safe_error_headers(headers: Any, api_key: str | None) -> list[list[str]]:
    if headers is None:
        return []
    try:
        items = headers.items()
    except AttributeError:
        return []
    return [
        [_redact_diagnostic(name, api_key), _redact_diagnostic(value, api_key)]
        for name, value in items
    ]


def _http_error_evidence(exc: HTTPError, api_key: str | None) -> dict[str, Any]:
    try:
        body = exc.read()
    except OSError as read_error:
        body = f"[ERROR_BODY_READ_FAILED:{type(read_error).__name__}]".encode()
    error_body = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    return {
        "status": "INCONCLUSIVE",
        "reason": f"ANYMODEL_HTTP_ERROR:{exc.code}",
        "http_request_made": True,
        "error_type": "HTTPError",
        "http_status": int(exc.code),
        "http_reason": _redact_diagnostic(exc.reason, api_key),
        "error_body": _redact_diagnostic(error_body, api_key),
        "error_headers": _safe_error_headers(exc.headers, api_key),
    }


def preflight_response(
    requested_model: str, provider_result: dict[str, Any]
) -> tuple[str, str | None]:
    """Reject known mock signatures and model substitution before extraction."""
    actual_model = provider_result.get("provider_model_id")
    response_id = provider_result.get("provider_response_id") or provider_result.get("id")
    content = provider_result.get("content")
    if not isinstance(actual_model, str) or not actual_model.strip():
        return "REFUSE", "MODEL_ID_MISSING"
    if (
        (isinstance(response_id, str) and MOCK_ID_RE.fullmatch(response_id.strip()))
        or actual_model.strip().lower() in MOCK_MODEL_IDS
        or (isinstance(content, str) and MOCK_TEXT in content.lower())
    ):
        return "REFUSE", "MOCK_DETECTED"
    if actual_model != requested_model:
        return "REFUSE", "MODEL_MISMATCH"
    if not isinstance(content, str) or not content.strip():
        return "REFUSE", "EMPTY_MODEL_CONTENT"
    return "PREFLIGHT_OK", None


def _price_attestation(
    confirmed: bool, price_source: str | None, confirmed_price_usd: float | None
) -> dict[str, Any] | None:
    if not confirmed or not isinstance(price_source, str) or not price_source.strip():
        return None
    if (
        isinstance(confirmed_price_usd, bool)
        or not isinstance(confirmed_price_usd, (int, float))
        or confirmed_price_usd <= 0
    ):
        return None
    return {
        "manual_confirmation": True,
        "price_source": price_source.strip(),
        "confirmed_price_usd": float(confirmed_price_usd),
    }


def _e4_verify(
    content: str, trace_id: str, *, moex_verifier: Any | None = None
) -> dict[str, Any]:
    try:
        candidates = extract_claims(content, trace_id=trace_id)
    except (TypeError, ValueError):
        return {"verdict": "INCONCLUSIVE", "reason": "CLAIM_EXTRACTION_FAILED",
                "extracted_claim": None, "raw_evidence": []}
    extracted_claims = [to_verdict_claim(item, trace_id) for item in candidates]
    price_candidates = [
        item for item in candidates
        if item.claim_type == "price"
        and (not item.ticker or item.ticker.upper() == "SBER")
    ]
    if not price_candidates:
        return {
            "verdict": "INCONCLUSIVE", "reason": "NO_PRICE_CLAIM",
            "extracted_claim": extracted_claims, "raw_evidence": [],
        }
    if len(price_candidates) > 1:
        return {
            "verdict": "AMBIGUOUS", "reason": "MULTIPLE_PRICE_CLAIMS",
            "extracted_claim": [
                to_verdict_claim(item, trace_id) for item in price_candidates
            ],
            "raw_evidence": [],
        }
    candidate = price_candidates[0]
    claim = to_verdict_claim(candidate, trace_id)
    if candidate.claim_type != "price":
        return {"verdict": "INCONCLUSIVE", "reason": "CLAIM_TYPE_NOT_SUPPORTED",
                "extracted_claim": claim, "raw_evidence": []}
    if not candidate.ticker or candidate.cited_value is None or candidate.currency is None:
        return {"verdict": "INCONCLUSIVE", "reason": "MISSING_TICKER_VALUE_OR_CURRENCY",
                "extracted_claim": claim, "raw_evidence": []}
    try:
        if candidate.currency == "RUB":
            verifier = moex_verifier or verify_claim_with_moex
            raw_status, details = verifier(
                candidate.ticker, "price", candidate.cited_value,
                price_tolerance=0.01, capture_raw=True,
            )
        elif candidate.currency == "USD":
            coin_id = COINGECKO_TICKER_MAP.get(candidate.ticker.upper())
            if coin_id is None:
                return {"verdict": "INCONCLUSIVE", "reason": "UNKNOWN_COINGECKO_TICKER",
                        "extracted_claim": claim, "raw_evidence": []}
            raw_status, details = verify_claim_with_coingecko(
                coin_id, "price", candidate.cited_value, threshold_pct=1.0, capture_raw=True,
            )
        else:
            return {"verdict": "INCONCLUSIVE", "reason": "UNSUPPORTED_CURRENCY",
                    "extracted_claim": claim, "raw_evidence": []}
    except Exception as exc:
        return {"verdict": "INCONCLUSIVE", "reason": f"PROVIDER_ERROR:{type(exc).__name__}",
                "extracted_claim": claim, "raw_evidence": []}
    raw_evidence = details.get("raw_evidence", []) if isinstance(details, dict) else []
    raw_valid = bool(raw_evidence)
    for item in raw_evidence:
        try:
            body = base64.b64decode(item["raw_body_base64"], validate=True)
            raw_valid = raw_valid and (
                item.get("body_complete") is True and item.get("status_code") == 200
                and hashlib.sha256(body).hexdigest() == item.get("sha256_body")
            )
        except (KeyError, TypeError, ValueError):
            raw_valid = False
    if raw_status in {E4_VERIFIED, E4_CONTRADICTED} and not raw_valid:
        verdict, reason = "INCONCLUSIVE", "RAW_EVIDENCE_MISSING_OR_INVALID"
    elif raw_status == E4_VERIFIED:
        verdict, reason = "VERIFIED", None
    elif raw_status == E4_CONTRADICTED:
        verdict, reason = "CONTRADICTED", None
    else:
        verdict = "INCONCLUSIVE"
        reason = details.get("reason", raw_status) if isinstance(details, dict) else raw_status
    return {"verdict": verdict, "reason": reason, "extracted_claim": claim,
            "details": details, "raw_evidence": raw_evidence}


def _safe_raw(capture: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _finalize_raw(capture)
    except AnyModelError:
        return None


def run_live_cycle(
    prompt: str, model: str, *, price_confirmed: bool, price_source: str | None,
    confirmed_price_usd: float | None, full_cycle: bool = False,
    api_key: str | None = None, max_tokens: int | None = None,
    max_budget_usd: float | None = None,
    executor_factory: Any | None = None,
    transport_opener: Any | None = None,
    moex_verifier: Any | None = None,
) -> dict[str, Any]:
    """Run one manually priced AnyModel request; E4 is downstream of preflight."""
    attestation = _price_attestation(price_confirmed, price_source, confirmed_price_usd)
    if attestation is None:
        return {"status": "REFUSE", "reason": "PRICE_NOT_CONFIRMED",
                "http_request_made": False}
    if not isinstance(prompt, str) or not prompt.strip():
        return {"status": "REFUSE", "reason": "PROMPT_EMPTY", "http_request_made": False}
    if not isinstance(model, str) or not model.strip():
        return {"status": "REFUSE", "reason": "MODEL_ID_EMPTY", "http_request_made": False}
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        return {"status": "REFUSE", "reason": "MAX_TOKENS_REQUIRED",
                "http_request_made": False}
    if (
        isinstance(max_budget_usd, bool)
        or not isinstance(max_budget_usd, (int, float))
        or not math.isfinite(max_budget_usd)
        or max_budget_usd <= 0
    ):
        return {"status": "REFUSE", "reason": "MAX_BUDGET_REQUIRED",
                "http_request_made": False}
    estimated_cost = (
        (DEFAULT_MAX_INPUT_TOKENS + max_tokens)
        * COST_PER_MILLION_TOKENS_USD
        / 1_000_000
    )
    if estimated_cost > max_budget_usd:
        return {
            "status": "REFUSE", "reason": "BUDGET_EXCEEDED",
            "estimated_cost_usd": estimated_cost, "max_budget_usd": max_budget_usd,
            "http_request_made": False,
        }
    key = api_key if api_key is not None else os.environ.get("ANYMODEL_API_KEY")
    if not key:
        return {"status": "REFUSE", "reason": "PROVIDER_NOT_CONFIGURED",
                "http_request_made": False}
    capture: dict[str, Any] = {}
    executor_class = executor_factory or AnyModelChatExecutor
    executor = executor_class(
        key, opener=_capturing_opener(capture, transport_opener or urlopen)
    )
    try:
        result = executor.execute(
            model, {"prompt": prompt}, max_tokens=max_tokens,
            max_budget_usd=max_budget_usd,
            max_input_tokens=DEFAULT_MAX_INPUT_TOKENS,
        )
        raw = _finalize_raw(capture)
    except AnyModelBudgetError as exc:
        return {
            "status": "REFUSE", "reason": str(exc),
            "estimated_cost_usd": estimated_cost, "max_budget_usd": max_budget_usd,
            "http_request_made": False, "price_attestation": attestation,
        }
    except HTTPError as exc:
        failure = _http_error_evidence(exc, key)
        failure["price_attestation"] = attestation
        return failure
    except TimeoutError as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": "ANYMODEL_REQUEST_TIMEOUT",
            "http_request_made": True,
            "error_type": "socket.timeout",
            "error_reason": _redact_diagnostic(exc, key),
            "raw_anymodel": _safe_raw(capture),
            "price_attestation": attestation,
        }
    except URLError as exc:
        error_type = "socket.timeout" if isinstance(exc.reason, TimeoutError) else "URLError"
        return {
            "status": "INCONCLUSIVE",
            "reason": "ANYMODEL_TRANSPORT_ERROR",
            "http_request_made": True,
            "error_type": error_type,
            "error_reason": _redact_diagnostic(exc.reason, key),
            "raw_anymodel": _safe_raw(capture),
            "price_attestation": attestation,
        }
    except AnyModelError as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": f"ANYMODEL_REQUEST_FAILED:{type(exc).__name__}",
            "http_request_made": True,
            "error_type": type(exc).__name__,
            "error_reason": _redact_diagnostic(exc, key),
            "raw_anymodel": _safe_raw(capture),
            "price_attestation": attestation,
        }
    preflight, reason = preflight_response(model, result)
    evidence: dict[str, Any] = {
        "status": "OBSERVED" if preflight == "PREFLIGHT_OK" else "REFUSE",
        "reason": reason, "requested_model": model,
        "response_model": result.get("provider_model_id") or result.get("model"),
        "response_id": result.get("provider_response_id"),
        "content": result.get("content") if preflight == "PREFLIGHT_OK" else None,
        "raw_anymodel": raw, "price_attestation": attestation,
        "http_request_made": True, "e2_preflight": preflight, "e4": None,
    }
    if preflight != "PREFLIGHT_OK":
        return evidence
    if full_cycle:
        trace_id = "v4_" + hashlib.sha256(
            str(result["content"]).encode("utf-8")
        ).hexdigest()[:16]
        if moex_verifier is None:
            evidence["e4"] = _e4_verify(str(result["content"]), trace_id)
        else:
            evidence["e4"] = _e4_verify(
                str(result["content"]), trace_id, moex_verifier=moex_verifier
            )
    else:
        evidence["reason"] = "PREFLIGHT_OK_PROBE_ONLY"
    return evidence


def run_mock() -> dict[str, Any]:
    """Network-free mock scenarios for local and PR-CI execution."""
    scenarios = [
        ("mock_id", {"provider_model_id": DEFAULT_MODEL,
                     "provider_response_id": "chatcmpl-abc123", "content": "OK"}),
        ("mock_model", {"provider_model_id": "openai/gpt-5",
                        "provider_response_id": "chatcmpl-real-001", "content": "OK"}),
        ("mock_text", {"provider_model_id": DEFAULT_MODEL,
                       "provider_response_id": "chatcmpl-real-002",
                       "content": "Hi! I'm an AI assistant"}),
        ("non_mock_shape", {"provider_model_id": DEFAULT_MODEL,
                            "provider_response_id": "chatcmpl-real-003",
                            "content": "The price of BTC is $65000."}),
    ]
    return {
        "mode": "MOCK", "network": "DISABLED",
        "results": [
            {"scenario": name, "status": preflight_response(DEFAULT_MODEL, item)[0],
             "reason": preflight_response(DEFAULT_MODEL, item)[1]}
            for name, item in scenarios
        ],
    }


def run_mock_e4() -> dict[str, Any]:
    """Exercise the real extractor/adapter/E4 path with network-free provider doubles."""
    from email.message import Message

    mock_moex_body = b'{"mock":true,"ticker":"SBER","last":300.0}'

    class FakeResponse:
        status = 200
        reason = "OK"
        version = 11
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, *args: Any, **kwargs: Any) -> bytes:
            return (
                b'{"id":"cmpl-mock-e2e","model":"ag/claude-sonnet-4-6",'
                b'"choices":[{"message":{"content":"The price of SBER is 300 RUB"}}]}'
            )

    def fake_transport_opener(request: Any, timeout: float) -> FakeResponse:
        return FakeResponse()

    def mock_moex_verifier(ticker: str, claim_type: str, claimed_value: float,
                           **kwargs: Any) -> tuple[str, dict[str, Any]]:
        assert ticker == "SBER"
        assert claim_type == "price"
        assert claimed_value == 300.0
        assert kwargs.get("capture_raw") is True
        return E4_VERIFIED, {
            "result": "VERIFIED",
            "checked_source": "MOEX_MOCK",
            "observed_last": 300.0,
            "raw_evidence": [{
                "status_code": 200,
                "body_complete": True,
                "raw_body_base64": base64.b64encode(mock_moex_body).decode("ascii"),
                "sha256_body": hashlib.sha256(mock_moex_body).hexdigest(),
            }],
        }

    result = run_live_cycle(
        LIVE_E4_PROMPT, DEFAULT_MODEL, price_confirmed=True,
        price_source="MOCK_ONLY", confirmed_price_usd=LIVE_E4_MAX_BUDGET_USD,
        full_cycle=True, api_key="mock-key", max_tokens=LIVE_E4_MAX_TOKENS,
        max_budget_usd=LIVE_E4_MAX_BUDGET_USD,
        transport_opener=fake_transport_opener, moex_verifier=mock_moex_verifier,
    )
    result["mode"] = "MOCK_E2_E4"
    result["network"] = "DISABLED"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--mock", action="store_true")
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--live-e4", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--price-confirmed", action="store_true")
    parser.add_argument("--price-source")
    parser.add_argument("--confirmed-price-usd", type=float)
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default="Say exactly: OK")
    parser.add_argument("--full-cycle", action="store_true")
    parser.add_argument("--output-dir", default="artifacts/research/experiment_v4")
    args = parser.parse_args()
    if args.mock:
        result = run_mock()
        result["e2_e4"] = run_mock_e4()
    elif not args.confirm_live:
        result = {"status": "REFUSE", "reason": "LIVE_NOT_CONFIRMED",
                  "http_request_made": False}
    else:
        live_e4 = args.live_e4
        result = run_live_cycle(
            LIVE_E4_PROMPT if live_e4 else args.prompt, args.model,
            price_confirmed=args.price_confirmed,
            price_source=args.price_source, confirmed_price_usd=args.confirmed_price_usd,
            full_cycle=args.full_cycle or live_e4,
            max_tokens=LIVE_E4_MAX_TOKENS if live_e4 else args.max_tokens,
            max_budget_usd=LIVE_E4_MAX_BUDGET_USD if live_e4 else args.max_budget_usd,
        )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw = result.get("raw_anymodel") if isinstance(result, dict) else None
    if isinstance(raw, dict) and isinstance(raw.get("http_representation_base64"), str):
        (output / "anymodel_raw_http.bin").write_bytes(
            base64.b64decode(raw["http_representation_base64"])
        )
    e4 = result.get("e4") if isinstance(result, dict) else None
    if isinstance(e4, dict):
        for index, item in enumerate(e4.get("raw_evidence", [])):
            encoded = item.get("raw_body_base64") if isinstance(item, dict) else None
            if isinstance(encoded, str):
                (output / f"moex_raw_http_{index}.bin").write_bytes(
                    base64.b64decode(encoded, validate=True)
                )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"REFUSE", "INCONCLUSIVE"} else 1


if __name__ == "__main__":
    sys.exit(main())
