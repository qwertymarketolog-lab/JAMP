"""Bounded factual verification against the public CoinGecko API.

This adapter verifies current existence, USD price, and USD market capitalization.
Historical price movements and predictions are outside its evidence scope.
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from typing import Any

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
E4_VERIFIED = "E4_VERIFIED"
E4_CONTRADICTED = "E4_CONTRADICTED"
E4_OUT_OF_SCOPE = "E4_OUT_OF_SCOPE"
E4_INCONCLUSIVE = "E4_INCONCLUSIVE"
CACHE_TTL_SECONDS = 60.0
FREE_TIER_REQUESTS_PER_MINUTE = 30
REQUEST_TIMEOUT_SECONDS = 5.0
_DEFAULT_THRESHOLDS = {"price": 10.0, "market_cap": 20.0}
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_REQUEST_TIMES: deque[float] = deque()
_LOCK = threading.Lock()


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    """Fetch a JSON object using the unauthenticated public API."""
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(url)
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
        if cached is not None:
            del _CACHE[url]
        while _REQUEST_TIMES and now - _REQUEST_TIMES[0] >= 60.0:
            _REQUEST_TIMES.popleft()
        if len(_REQUEST_TIMES) >= FREE_TIER_REQUESTS_PER_MINUTE:
            raise RuntimeError("LOCAL_RATE_LIMIT")
        _REQUEST_TIMES.append(now)

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "JAMP-Trust-Layer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CoinGecko response must be a JSON object")
    with _LOCK:
        _CACHE[url] = (time.monotonic(), payload)
    return payload


def _coin_url(coin_id: str) -> str:
    return f"{COINGECKO_BASE}/coins/{urllib.parse.quote(coin_id, safe='')}"


def verify_claim_with_coingecko(
    coin_id: str,
    claim_type: str,
    claimed_value: float | int | None,
    threshold_pct: float | None = None,
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> tuple[str, dict[str, Any]]:
    """Verify an explicit CoinGecko claim and return bounded source evidence.

    threshold_pct is expressed as a percentage (10 means 10%). Defaults are 10%
    for price and 20% for market capitalization. A missing coin contradicts an
    existence claim; for numeric claims, a missing coin is out of scope.
    """
    normalized_id = coin_id.strip().lower() if isinstance(coin_id, str) else ""
    if (
        not normalized_id
        or len(normalized_id) > 120
        or not all(char.isalnum() or char in "-_" for char in normalized_id)
    ):
        return E4_INCONCLUSIVE, {
            "reason": "INVALID_COIN_ID", "checked_source": "coingecko", "coin_id": coin_id
        }
    if claim_type == "prediction":
        return E4_OUT_OF_SCOPE, {
            "reason": "PREDICTION_NOT_VERIFIABLE_BY_E4",
            "claim_type": claim_type,
            "coin_id": normalized_id,
            "checked_source": "coingecko",
        }
    if claim_type not in {"existence", "price", "market_cap"}:
        return E4_INCONCLUSIVE, {
            "reason": "UNSUPPORTED_CLAIM_TYPE",
            "claim_type": claim_type,
            "coin_id": normalized_id,
            "checked_source": "coingecko",
        }
    if timeout <= 0 or not math.isfinite(timeout):
        return E4_INCONCLUSIVE, {"reason": "INVALID_TIMEOUT", "checked_source": "coingecko"}

    threshold = _DEFAULT_THRESHOLDS.get(claim_type) if threshold_pct is None else threshold_pct
    if claim_type in {"price", "market_cap"} and (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not 0 <= float(threshold) < 100
    ):
        return E4_INCONCLUSIVE, {
            "reason": "INVALID_THRESHOLD_PCT",
            "claim_type": claim_type,
            "threshold_pct": threshold_pct,
            "checked_source": "coingecko",
        }
    if claim_type in {"price", "market_cap"} and (
        isinstance(claimed_value, bool)
        or not isinstance(claimed_value, (int, float))
        or not math.isfinite(float(claimed_value))
        or float(claimed_value) <= 0
    ):
        return E4_INCONCLUSIVE, {
            "reason": "INVALID_CLAIMED_VALUE",
            "claim_type": claim_type,
            "claimed_value": claimed_value,
            "checked_source": "coingecko",
        }

    if claim_type == "price":
        params = urllib.parse.urlencode({"ids": normalized_id, "vs_currencies": "usd"})
        url = f"{COINGECKO_BASE}/simple/price?{params}"
    else:
        url = _coin_url(normalized_id)

    try:
        payload = _get_json(url, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            status = E4_CONTRADICTED if claim_type == "existence" else E4_OUT_OF_SCOPE
            return status, {
                "reason": "COIN_NOT_FOUND",
                "claim_type": claim_type,
                "coin_id": normalized_id,
                "http_status": exc.code,
                "checked_source": "coingecko",
            }
        return E4_INCONCLUSIVE, {
            "reason": "COINGECKO_HTTP_ERROR",
            "error_type": type(exc).__name__,
            "http_status": exc.code,
            "checked_source": "coingecko",
        }
    except RuntimeError as exc:
        reason = "LOCAL_RATE_LIMIT" if str(exc) == "LOCAL_RATE_LIMIT" else "COINGECKO_REQUEST_FAILED"
        return E4_INCONCLUSIVE, {"reason": reason, "checked_source": "coingecko"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return E4_INCONCLUSIVE, {
            "reason": "COINGECKO_SOURCE_UNAVAILABLE_OR_INVALID",
            "error_type": type(exc).__name__,
            "checked_source": "coingecko",
        }

    if claim_type == "existence":
        return E4_VERIFIED, {
            "result": "VERIFIED",
            "claim_type": claim_type,
            "coin_id": normalized_id,
            "checked_source": "coingecko",
            "name": payload.get("name"),
            "symbol": payload.get("symbol"),
        }
    if claim_type == "price":
        coin_data = payload.get(normalized_id)
        observed_value = coin_data.get("usd") if isinstance(coin_data, dict) else None
    else:
        market_data = payload.get("market_data")
        values = market_data.get("market_cap") if isinstance(market_data, dict) else None
        observed_value = values.get("usd") if isinstance(values, dict) else None

    if (
        isinstance(observed_value, bool)
        or not isinstance(observed_value, (int, float))
        or not math.isfinite(float(observed_value))
        or float(observed_value) <= 0
    ):
        return E4_OUT_OF_SCOPE, {
            "reason": "COIN_OR_VALUE_NOT_FOUND",
            "claim_type": claim_type,
            "coin_id": normalized_id,
            "checked_source": "coingecko",
        }
    claimed = float(claimed_value)
    observed = float(observed_value)
    relative_delta_pct = abs(claimed - observed) / observed * 100.0
    details = {
        "claim_type": claim_type,
        "coin_id": normalized_id,
        "claimed_value": claimed,
        "observed_value": observed,
        "relative_delta_pct": relative_delta_pct,
        "threshold_pct": float(threshold),
        "checked_source": "coingecko",
    }
    if relative_delta_pct > float(threshold):
        return E4_CONTRADICTED, {**details, "result": "CONTRADICTED"}
    return E4_VERIFIED, {**details, "result": "VERIFIED"}
