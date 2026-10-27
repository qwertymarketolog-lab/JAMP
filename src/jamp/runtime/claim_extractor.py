"""Deterministic rule-based extraction of claims from text.

This module intentionally does not use an LLM. It extracts one Claim per
sentence-like segment and preserves the source text for later verification.
The output is a candidate structure, not a verdict or evidence of truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ClaimType = Literal["price", "existence", "prediction", "causal", "other"]


@dataclass(frozen=True)
class Claim:
    """A text span and the deterministic signals extracted from it."""

    id: str
    text: str
    ticker: str | None
    claim_type: ClaimType
    cited_value: float | None
    citation_url: str | None


_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
# Uppercase symbols are the primary ticker form. Common domain words and
# finance/reporting abbreviations are excluded to avoid treating them as tickers.
_TICKER_RE = re.compile(r"\b[A-Z]{3,5}\b")
_COMPANY_RE = re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b")
_NUMBER_RE = re.compile(r"(?<![\w/])\d+(?:[.,]\d+)?\s*₽?")
_PRICE_MARKER_RE = re.compile(
    r"(?:₽|\b(?:цена|стоит|торгуется|достиг(?:ла|ло)?|составляет|равен|равна)\b|=)",
    re.IGNORECASE,
)
_PREDICTION_MARKER_RE = re.compile(
    r"\b(?:будет|будут|вырастет|вырастут|снизится|упад[её]т|"
    r"прогноз(?:ирует|ируется)?|к\s+20\d{2})\b",
    re.IGNORECASE,
)
_CAUSAL_MARKER_RE = re.compile(
    r"\b(?:из-за|потому что|в связи с|благодаря|вследствие)\b",
    re.IGNORECASE,
)
_EXISTENCE_MARKER_RE = re.compile(
    r"\b(?:объявил[аио]?|объявляет|запустил[аио]?|основан[ао]?|"
    r"существует|объявила IPO|вышла на IPO|провела IPO)\b",
    re.IGNORECASE,
)
_NON_TICKERS = {
    "IPO",
    "USD",
    "EUR",
    "RUB",
    "HTTP",
    "HTTPS",
    "JSON",
    "TRUE",
    "FALSE",
    "NULL",
    "THE",
    "AND",
    "FOR",
    "WITH",
    "FROM",
    "THIS",
    "THAT",
    "WILL",
}
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


def _split_claim_text(text: str) -> list[str]:
    """Split on sentence punctuation without splitting URLs or decimal values."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9«\"'])", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _extract_ticker(text: str) -> str | None:
    for match in _TICKER_RE.finditer(text):
        candidate = match.group(0)
        if candidate not in _NON_TICKERS:
            return candidate

    # Company names such as FakeTech are normalized only as a candidate symbol;
    # the extractor does not claim that the name is a listed ticker.
    company_match = _COMPANY_RE.search(text)
    if company_match:
        candidate = company_match.group(0).upper()
        if candidate not in _NON_TICKERS:
            return candidate
    return None


def _extract_value(text: str) -> float | None:
    match = _NUMBER_RE.search(text)
    if not match or not _PRICE_MARKER_RE.search(text):
        return None
    raw_value = match.group(0).replace("₽", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw_value)
    except ValueError:
        return None


def _classify(text: str) -> ClaimType:
    # A future/prediction marker takes precedence over a causal phrase in the
    # same sentence; both signals remain recoverable from Claim.text.
    if _PREDICTION_MARKER_RE.search(text):
        return "prediction"
    if _CAUSAL_MARKER_RE.search(text):
        return "causal"
    if _PRICE_MARKER_RE.search(text) and _NUMBER_RE.search(text):
        return "price"
    if _EXISTENCE_MARKER_RE.search(text):
        return "existence"
    return "other"


def _extract_url(text: str) -> str | None:
    match = _URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(_TRAILING_URL_PUNCTUATION)


def extract_claims(text: str) -> list[Claim]:
    """Extract deterministic candidate claims from text.

    Returns an empty list for empty/whitespace-only input. IDs are stable and
    sequential within the supplied input (c1, c2, ...). No verification occurs.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    segments = _split_claim_text(text)
    claims: list[Claim] = []
    for segment in segments:
        claims.append(
            Claim(
                id=f"c{len(claims) + 1}",
                text=segment,
                ticker=_extract_ticker(segment),
                claim_type=_classify(segment),
                cited_value=_extract_value(segment),
                citation_url=_extract_url(segment),
            )
        )
    return claims
