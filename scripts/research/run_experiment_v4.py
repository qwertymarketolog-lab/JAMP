"""Guarded AnyModel E2 -> Extractor -> E4 experiment v4."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from jamp.provider.anymodel import AnyModelChatExecutor, AnyModelError
from jamp.provider.coingecko_verify import verify_claim_with_coingecko
from jamp.provider.moex_verify import E4_CONTRADICTED, E4_VERIFIED, verify_claim_with_moex
from jamp.runtime.claim_adapter import to_verdict_claim
from jamp.runtime.claim_extractor import extract_claims

DEFAULT_MODEL = "ag/claude-sonnet-4-6"
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

    def __enter__(self) -> "_CapturedResponse":
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


def _capturing_opener(capture: dict[str, Any]):
    def open_request(request: Any, timeout: float) -> _CapturedResponse:
        response = urlopen(request, timeout=timeout)
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


def _e4_verify(content: str, trace_id: str) -> dict[str, Any]:
    try:
        candidates = extract_claims(content, trace_id=trace_id)
    except (TypeError, ValueError):
        return {"verdict": "INCONCLUSIVE", "reason": "CLAIM_EXTRACTION_FAILED",
                "extracted_claim": None, "raw_evidence": []}
    if len(candidates) != 1:
        return {
            "verdict": "INCONCLUSIVE", "reason": "EXPECTED_EXACTLY_ONE_CLAIM",
            "extracted_claim": [to_verdict_claim(item, trace_id) for item in candidates],
            "raw_evidence": [],
        }
    candidate = candidates[0]
    claim = to_verdict_claim(candidate, trace_id)
    if candidate.claim_type != "price":
        return {"verdict": "INCONCLUSIVE", "reason": "CLAIM_TYPE_NOT_SUPPORTED",
                "extracted_claim": claim, "raw_evidence": []}
    if not candidate.ticker or candidate.cited_value is None or candidate.currency is None:
        return {"verdict": "INCONCLUSIVE", "reason": "MISSING_TICKER_VALUE_OR_CURRENCY",
                "extracted_claim": claim, "raw_evidence": []}
    try:
        if candidate.currency == "RUB":
            raw_status, details = verify_claim_with_moex(
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
    api_key: str | None = None,
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
    key = api_key if api_key is not None else os.environ.get("ANYMODEL_API_KEY")
    if not key:
        return {"status": "REFUSE", "reason": "PROVIDER_NOT_CONFIGURED",
                "http_request_made": False}
    capture: dict[str, Any] = {}
    executor = AnyModelChatExecutor(key, opener=_capturing_opener(capture))
    try:
        result = executor(model, {"prompt": prompt})
        raw = _finalize_raw(capture)
    except Exception as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": f"ANYMODEL_REQUEST_FAILED:{type(exc).__name__}",
            "http_request_made": True,
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
        evidence["e4"] = _e4_verify(str(result["content"]), trace_id)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--mock", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--price-confirmed", action="store_true")
    parser.add_argument("--price-source")
    parser.add_argument("--confirmed-price-usd", type=float)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default="Say exactly: OK")
    parser.add_argument("--full-cycle", action="store_true")
    parser.add_argument("--output-dir", default="artifacts/research/experiment_v4")
    args = parser.parse_args()
    if args.mock:
        result = run_mock()
    elif not args.confirm_live:
        result = {"status": "REFUSE", "reason": "LIVE_NOT_CONFIRMED",
                  "http_request_made": False}
    else:
        result = run_live_cycle(
            args.prompt, args.model, price_confirmed=args.price_confirmed,
            price_source=args.price_source, confirmed_price_usd=args.confirmed_price_usd,
            full_cycle=args.full_cycle,
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
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"REFUSE", "INCONCLUSIVE"} else 1


if __name__ == "__main__":
    sys.exit(main())
