"""Deterministic R18-R22 claim pipeline; provider verification is delegated to E4 adapters."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from jamp.provider.coingecko_verify import verify_claim_with_coingecko
from jamp.provider.moex_verify import verify_claim_with_moex

CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "USDT", "USDC", "BNB", "XRP", "ADA", "DOGE"}
VERDICT_MAP = {
    "E4_VERIFIED": "supported",
    "E4_CONTRADICTED": "contradicted",
    "E4_OUT_OF_SCOPE": "ambiguous",
    "E4_INCONCLUSIVE": "inconclusive",
}
PREDICTION_MARKERS = ("будет", "вырастет", "упадёт", "упадет", "к 20", "прогноз")
CAUSAL_MARKERS = ("из-за", "потому что", "в связи с", "вследствие")
TICKER_RE = re.compile(r"\b[A-Z]{3,5}\b")
PRICE_RE = re.compile(r"(\d[\d\s]*[.,]?\d*)\s*[₽$]?")
CHANGE_PCT_RE = re.compile(
    r"(упал|вырос|потерял|прибавил)[^\d]*(\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s,;)»]+")
DEFAULT_SAMPLE = (
    "Согласно https://iss.moex.com/iss/engines/stock/markets/shares/boards/"
    "TQBR/securities/SBER.json, "
    "SBER достиг 5000 рублей. "
    "VKCO потерял 93% капитализации. "
    "FakeTech объявила IPO. "
    "SBER вырастет из-за дивидендов."
)


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    ticker: str | None
    claim_type: str
    cited_value: float | None
    citation_url: str | None


def _parse_value(raw: str) -> float | None:
    normalized = raw.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def extract_claims(text: str) -> list[Claim]:
    """Extract candidate claims with stable IDs; this is not a verdict."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    claims: list[Claim] = []
    urls: list[str] = []

    def replace_url(match: re.Match[str]) -> str:
        urls.append(match.group(0))
        return "__URLTOKEN__"

    text_without_urls = URL_RE.sub(replace_url, text)
    sentences = (part.strip() for part in re.split(r"(?<=[.!?])\s+", text_without_urls))
    url_index = 0
    for index, sentence in enumerate(sentences, 1):
        if not sentence:
            continue
        sentence_urls: list[str] = []

        def restore_url(
            _match: re.Match[str], _sentence_urls: list[str] = sentence_urls
        ) -> str:
            nonlocal url_index
            url = urls[url_index]
            url_index += 1
            _sentence_urls.append(url)
            return url

        restored_sentence = re.sub(r"__URLTOKEN__", restore_url, sentence)
        # Preserve the agreed mixed-case company example before uppercase acronyms such as IPO.
        proper_name = re.search(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", sentence)
        ticker_match = TICKER_RE.search(sentence)
        ticker = (
            proper_name.group(1).upper()
            if proper_name
            else ticker_match.group(0)
            if ticker_match
            else None
        )
        change_match = CHANGE_PCT_RE.search(sentence)
        price_match = None if change_match else PRICE_RE.search(sentence)
        cited_value = (
            _parse_value(change_match.group(2))
            if change_match
            else _parse_value(price_match.group(1))
            if price_match
            else None
        )
        citation_url = sentence_urls[0] if sentence_urls else None
        lowered = sentence.lower()
        if change_match:
            claim_type = "change_percent"
        elif any(marker in lowered for marker in PREDICTION_MARKERS):
            claim_type = "prediction"
        elif any(marker in lowered for marker in CAUSAL_MARKERS):
            claim_type = "causal"
        elif ticker and cited_value is not None:
            claim_type = "price"
        elif ticker:
            claim_type = "existence"
        else:
            claim_type = "other"
        claims.append(
            Claim(
                id=f"claim-{index:04d}",
                text=restored_sentence,
                ticker=ticker,
                claim_type=claim_type,
                cited_value=cited_value if claim_type in {"price", "change_percent"} else None,
                citation_url=citation_url,
            )
        )

    return claims


def check_citation(url: str) -> tuple[bool, str | None]:
    """Check citation URL syntax and reachability; allow known APIs deterministically."""
    if not isinstance(url, str):
        return False, "malformed_url"
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
            return False, "malformed_url"
        # Force validation of malformed ports and reject whitespace/control characters.
        _ = parsed.port
        if any(char.isspace() or ord(char) < 32 for char in url):
            return False, "malformed_url"
    except (ValueError, TypeError):
        return False, "malformed_url"

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"iss.moex.com", "api.coingecko.com"}:
        return True, None

    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "JAMP-CitationChecker/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            return True, None
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except Exception as exc:  # Network errors are reportable evidence, not PASS.
        return False, type(exc).__name__


def map_e4_verdict(status: str) -> str:
    """Map the four E4 adapter statuses to the pipeline's four-verdict taxonomy."""
    return VERDICT_MAP.get(status, "inconclusive")


def _verify_claim(claim: Claim) -> tuple[str, dict[str, Any]]:
    if claim.ticker in CRYPTO_TICKERS:
        return verify_claim_with_coingecko(
            claim.ticker.lower(), claim.claim_type, claim.cited_value
        )
    adapter_type = "exists" if claim.claim_type == "existence" else claim.claim_type
    return verify_claim_with_moex(claim.ticker or "", adapter_type, claim.cited_value)


def run_pipeline(text: str) -> dict[str, Any]:
    claims = extract_claims(text)
    results: list[dict[str, Any]] = []
    for claim in claims:
        r_codes: list[str] = []
        evidence: dict[str, Any] = {}
        reason: str | None = None
        citation_evidence: dict[str, Any] = {}
        citation_failed = False
        if claim.citation_url:
            reachable, citation_reason = check_citation(claim.citation_url)
            citation_evidence = {
                "citation_url": claim.citation_url,
                "citation_check": "reachable" if reachable else "failed",
            }
            if not reachable:
                r_codes.extend(("R20", "R22"))
                verdict = "contradicted"
                reason = citation_reason or "citation_check_failed"
                evidence = citation_evidence
                citation_failed = True
            else:
                r_codes.append("R20")
        if not citation_failed and claim.claim_type == "change_percent":
            r_codes.extend(("R21", "R22"))
            verdict = "inconclusive"
            reason = "requires_E5_or_history"
            evidence = citation_evidence
        elif not citation_failed and claim.claim_type in {"price", "existence"} and claim.ticker:
            r_codes.append("R18")
            status, provider_evidence = _verify_claim(claim)
            verdict = (
                "not_found"
                if claim.claim_type == "existence" and status == "E4_OUT_OF_SCOPE"
                else map_e4_verdict(status)
            )
            evidence = {**provider_evidence, **citation_evidence}
            reason = evidence.get("reason")
            if verdict == "inconclusive" and not reason:
                reason = "e4_inconclusive_without_reason"
        elif not citation_failed:
            r_codes.extend(("R21", "R22"))
            verdict = "inconclusive"
            reason = "requires_E5_search"
            evidence = citation_evidence
        if verdict == "inconclusive" and not reason:
            reason = "inconclusive_reason_missing"
        results.append(
            {
                "id": claim.id,
                "text": claim.text,
                "ticker": claim.ticker,
                "claim_type": claim.claim_type,
                "r_codes": r_codes,
                "verdict": verdict,
                "evidence": evidence,
                "reason": reason,
            }
        )

    counts = {
        name: sum(item["verdict"] == name for item in results)
        for name in (
            "supported",
            "contradicted",
            "not_found",
            "ambiguous",
            "inconclusive",
        )
    }
    total = len(results)
    verified = counts["supported"] + counts["contradicted"] + counts["not_found"]
    coverage = {
        "total": total,
        **counts,
        "verified": verified,
        "verified_ratio": verified / total if total else None,
    }
    return {"schema_version": "r18-r22-report-v0", "coverage": coverage, "claims": results}


def main() -> int:
    # Explicit input is preferred; the default is an input fixture, not precomputed evidence.
    text = sys.stdin.read()
    if not text:
        text = DEFAULT_SAMPLE
    report = run_pipeline(text)
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
