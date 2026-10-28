"""Bounded public-source search verification using Tavily.

E5 collects evidence candidates; it does not establish ground truth. Verdicts use
only whitelisted publisher domains and deliberately conservative snippet rules.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

E5_VERIFIED = "E5_VERIFIED"
E5_CONTRADICTED = "E5_CONTRADICTED"
E5_OUT_OF_SCOPE = "E5_OUT_OF_SCOPE"
E5_INCONCLUSIVE = "E5_INCONCLUSIVE"
WHITELIST_VERSION = "e5-authoritative-domains-v0"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
WHITELIST_PATH = Path(__file__).resolve().parents[3] / "data" / "e5_authoritative_domains_v0.json"

CAUSAL_MARKERS_EN = (
    "due to",
    "caused by",
    "because of",
    "as a result of",
    "led to",
    "triggered by",
    "driven by",
    "cause",
)
CAUSAL_MARKERS_RU = (
    "из-за",
    "в связи с",
    "потому что",
    "вследствие",
    "привело к",
    "стало причиной",
    "обусловлено",
)
NEGATION_MARKERS = (
    "not",
    "did not",
    "does not",
    "never",
    "denied",
    "не ",
    "нет ",
    "ни ",
)
OPPOSITION_MARKERS = (
    "contrary to",
    "instead of",
    "rather than",
    "did not cause",
    "not cause",
    "не выплачив",
    "не платил",
    "не привело",
    "не стало причиной",
    "без связи",
)


def _load_whitelist() -> dict[str, Any]:
    payload = json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != WHITELIST_VERSION:
        raise ValueError("Whitelist version mismatch")
    groups = payload.get("groups")
    if not isinstance(groups, dict):
        raise ValueError("Whitelist groups must be an object")
    return payload


def _domain_for_url(url: str, groups: dict[str, Any]) -> tuple[str | None, str | None]:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None, None
    host = parsed.hostname.lower().rstrip(".")
    for group, domains in groups.items():
        if not isinstance(domains, list):
            continue
        for domain in domains:
            if isinstance(domain, str) and (host == domain or host.endswith("." + domain)):
                return domain, group
    return None, None


def _query_for_claim(claim_text: str, ticker: str | None, claim_type: str) -> str:
    parts = [claim_text.strip()]
    if ticker and ticker.casefold() not in claim_text.casefold():
        parts.append(ticker)
    query_terms = {
        "causal": ("cause", "reason"),
        "change_percent": ("percentage", "period"),
        "existence": ("official", "company"),
    }.get(claim_type, ())
    parts.append(" ".join(query_terms))
    return " ".join(part for part in parts if part).strip()


def _has_causal_marker(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in (*CAUSAL_MARKERS_EN, *CAUSAL_MARKERS_RU))


def _claim_keywords(claim_text: str) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "from",
        "with",
        "that",
        "this",
        "was",
        "were",
        "will",
        "has",
        "have",
        "had",
        "into",
        "after",
        "before",
        "because",
        "due",
        "said",
        "акция",
        "акции",
        "вырос",
        "выросла",
        "выросли",
        "упал",
        "упала",
        "упали",
        "из-за",
        "вследствие",
        "потому",
        "что",
        "в",
        "на",
        "за",
        "для",
        "компания",
    }
    words = re.findall(r"[a-zа-яё0-9]{3,}", claim_text.casefold())
    return list(dict.fromkeys(word for word in words if word not in stopwords))


def _contains_ticker(snippet: str, ticker: str | None) -> bool:
    if not ticker:
        return False
    pattern = r"(?<![\w])" + re.escape(ticker) + r"(?![\w])"
    return re.search(pattern, snippet, re.IGNORECASE) is not None


def _is_negated(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in NEGATION_MARKERS)


def _claim_match(claim_text: str, claim_type: str, ticker: str | None, snippet: str) -> str:
    """Return support, contradict, or unrelated using intentionally narrow rules."""
    lowered_claim = claim_text.casefold()
    lowered_snippet = snippet.casefold()
    if claim_type == "causal":
        keywords = [word for word in _claim_keywords(claim_text) if len(word) >= 4]
        keyword_match = any(word in lowered_snippet for word in keywords)
        if (
            not _contains_ticker(snippet, ticker)
            or not keyword_match
            or not _has_causal_marker(snippet)
        ):
            return "unrelated"
        return (
            "contradict"
            if any(marker in lowered_snippet for marker in OPPOSITION_MARKERS)
            else "support"
        )

    if claim_type == "change_percent":
        claim_percentages = re.findall(r"\d+(?:[.,]\d+)?\s*%", lowered_claim)
        snippet_percentages = re.findall(r"\d+(?:[.,]\d+)?\s*%", lowered_snippet)
        if (
            not claim_percentages
            or not snippet_percentages
            or not _contains_ticker(snippet, ticker)
        ):
            return "unrelated"

        def normalize(value: str) -> float:
            return float(value.replace("%", "").replace(",", ".").strip())

        if any(
            normalize(a) == normalize(b) for a in claim_percentages for b in snippet_percentages
        ):
            return (
                "contradict"
                if any(marker in lowered_snippet for marker in OPPOSITION_MARKERS)
                else "support"
            )
        return "unrelated"

    if claim_type == "existence":
        if not ticker or not _contains_ticker(snippet, ticker):
            return "unrelated"
        if any(
            marker in lowered_snippet
            for marker in ("does not exist", "no such company", "не существует")
        ):
            return "contradict"
        return "support"

    # Generic explicit claims are supported only when ticker and meaningful terms match.
    if ticker and not _contains_ticker(snippet, ticker):
        return "unrelated"
    keywords = [word for word in _claim_keywords(claim_text) if len(word) >= 4]
    if not keywords or not any(word in lowered_snippet for word in keywords):
        return "unrelated"
    claim_negated = _is_negated(lowered_claim)
    source_negated = _is_negated(lowered_snippet)
    if claim_negated != source_negated:
        return "contradict"
    return "support"


def _base_evidence(
    claim_text: str,
    claim_type: str,
    ticker: str | None,
    query: str,
) -> dict[str, Any]:
    return {
        "checked_source": "tavily",
        "whitelist_version": WHITELIST_VERSION,
        "claim": {"text": claim_text, "type": claim_type, "ticker": ticker},
        "query": query,
        "results_count": 0,
        "authoritative_results_count": 0,
        "unique_domains_count": 0,
        "results": [],
        "verdict_basis": "no_authoritative_source",
        "conflicting": False,
        "result": E5_INCONCLUSIVE,
        "reason": None,
        "http_status": None,
        "parse_error": None,
        "independence_basis": "single",
    }


def _finish(
    evidence: dict[str, Any],
    status: str,
    reason: str | None,
    basis: str,
    independence_basis: str,
) -> tuple[str, dict[str, Any]]:
    evidence["result"] = status
    evidence["reason"] = reason
    evidence["verdict_basis"] = basis
    evidence["independence_basis"] = independence_basis
    return status, evidence


def verify_with_search(
    claim_text: str,
    claim_type: str,
    ticker: str | None = None,
    date_from: str | None = None,
    date_till: str | None = None,
    timeout: float = 10.0,
    api_key: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Search public sources and return a conservative E5 verdict plus bounded evidence."""
    normalized_type = claim_type.strip().lower() if isinstance(claim_type, str) else ""
    normalized_ticker = (
        ticker.strip().upper() if isinstance(ticker, str) and ticker.strip() else None
    )
    query = _query_for_claim(claim_text, normalized_ticker, normalized_type)
    evidence = _base_evidence(claim_text, normalized_type, normalized_ticker, query)
    attempts: list[dict[str, Any]] = []
    evidence["attempts"] = attempts

    if normalized_type == "prediction":
        return _finish(
            evidence,
            E5_OUT_OF_SCOPE,
            "future_prediction_not_searchable",
            "no_authoritative_source",
            "single",
        )
    if normalized_type == "historical_price":
        return _finish(
            evidence,
            E5_OUT_OF_SCOPE,
            "foreign_price_not_supported_v0",
            "no_authoritative_source",
            "single",
        )
    if normalized_type not in {"causal", "change_percent", "existence"}:
        return _finish(
            evidence,
            E5_OUT_OF_SCOPE,
            "claim_type_not_supported_v0",
            "no_authoritative_source",
            "single",
        )
    if normalized_type in {"causal", "existence"} and not normalized_ticker:
        return _finish(
            evidence, E5_INCONCLUSIVE, "ticker_not_extractable", "no_authoritative_source", "single"
        )
    if not isinstance(claim_text, str) or not claim_text.strip():
        return _finish(
            evidence, E5_INCONCLUSIVE, "empty_claim", "no_authoritative_source", "single"
        )
    if timeout <= 0:
        return _finish(evidence, E5_INCONCLUSIVE, "timeout", "no_authoritative_source", "single")

    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        return _finish(
            evidence, E5_INCONCLUSIVE, "api_key_missing", "no_authoritative_source", "single"
        )
    try:
        whitelist = _load_whitelist()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        evidence["parse_error"] = f"whitelist_error:{type(exc).__name__}"
        return _finish(
            evidence, E5_INCONCLUSIVE, "whitelist_unavailable", "no_authoritative_source", "single"
        )

    all_domains = sorted(
        {
            domain
            for domains in whitelist["groups"].values()
            if isinstance(domains, list)
            for domain in domains
            if isinstance(domain, str)
        }
    )
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "advanced",
        "include_domains": all_domains,
        "max_results": 10,
        "include_raw_content": False,
        "include_answer": False,
    }
    request = urllib.request.Request(
        TAVILY_SEARCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    attempt_started = time.monotonic()
    http_status: int | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            http_status = getattr(response, "status", None)
            evidence["http_status"] = http_status
            raw = response.read()
        attempts.append(
            {
                "attempt": 1,
                "http_status": http_status,
                "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
            }
        )
        parsed = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        attempts.append(
            {
                "attempt": 1,
                "http_status": exc.code,
                "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
            }
        )
        evidence["http_status"] = exc.code
        reason = (
            "api_auth_error"
            if exc.code in {401, 403}
            else (
                "rate_limit"
                if exc.code == 429
                else "api_server_error"
                if exc.code >= 500
                else "api_http_error"
            )
        )
        return _finish(evidence, E5_INCONCLUSIVE, reason, "no_authoritative_source", "single")
    except TimeoutError:
        attempts.append(
            {
                "attempt": 1,
                "http_status": None,
                "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
            }
        )
        return _finish(evidence, E5_INCONCLUSIVE, "timeout", "no_authoritative_source", "single")
    except (urllib.error.URLError, OSError):
        attempts.append(
            {
                "attempt": 1,
                "http_status": http_status,
                "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
            }
        )
        return _finish(
            evidence, E5_INCONCLUSIVE, "network_error", "no_authoritative_source", "single"
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        evidence["parse_error"] = type(exc).__name__
        return _finish(
            evidence, E5_INCONCLUSIVE, "malformed_response", "no_authoritative_source", "single"
        )

    if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
        evidence["parse_error"] = "results must be a list"
        return _finish(
            evidence, E5_INCONCLUSIVE, "malformed_response", "no_authoritative_source", "single"
        )

    raw_results = parsed["results"]
    evidence["results_count"] = len(raw_results)
    groups = whitelist["groups"]
    authoritative: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        snippet = item.get("content")
        if not isinstance(url, str):
            continue
        domain, group = _domain_for_url(url, groups)
        if domain is None:
            continue
        authoritative.append(
            {
                "url": url,
                "title": title[:500] if isinstance(title, str) else "",
                "snippet": snippet[:500] if isinstance(snippet, str) else "",
                "domain": domain,
                "source_group": group,
                "published_date": (
                    item.get("published_date")
                    if isinstance(item.get("published_date"), str)
                    else None
                ),
            }
        )
    evidence["results"] = authoritative
    evidence["authoritative_results_count"] = len(authoritative)
    unique_domains = sorted({result["domain"] for result in authoritative})
    evidence["unique_domains_count"] = len(unique_domains)
    if not authoritative:
        return _finish(
            evidence,
            E5_OUT_OF_SCOPE,
            "no_authoritative_source",
            "no_authoritative_source",
            "single",
        )

    supports = 0
    contradicts = 0
    for result in authoritative:
        stance = _claim_match(claim_text, normalized_type, normalized_ticker, result["snippet"])
        if stance == "support":
            supports += 1
        elif stance == "contradict":
            contradicts += 1

    if normalized_type == "causal" and supports == 0 and contradicts == 0:
        independence = "single" if len(unique_domains) == 1 else "different_domains"
        return _finish(
            evidence,
            E5_OUT_OF_SCOPE,
            "facts_without_causality",
            "facts_without_causality",
            independence,
        )
    if supports and contradicts:
        evidence["conflicting"] = True
        independence = "different_domains" if len(unique_domains) > 1 else "same_domain"
        return _finish(
            evidence,
            E5_INCONCLUSIVE,
            "conflicting_sources",
            "conflicting_sources",
            independence,
        )
    if contradicts:
        basis = "single_source" if len(unique_domains) == 1 else "multi_source_confirmed"
        independence = "single" if len(unique_domains) == 1 else "different_domains"
        return _finish(evidence, E5_CONTRADICTED, None, basis, independence)
    if supports:
        basis = "multi_source_confirmed" if len(unique_domains) >= 2 else "single_source"
        independence = "different_domains" if len(unique_domains) >= 2 else "single"
        return _finish(evidence, E5_VERIFIED, None, basis, independence)
    independence = "different_domains" if len(unique_domains) > 1 else "single"
    return _finish(
        evidence,
        E5_OUT_OF_SCOPE,
        "snippet_inconclusive",
        "snippet_inconclusive",
        independence,
    )
