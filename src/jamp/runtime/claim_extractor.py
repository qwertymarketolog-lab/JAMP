"""Deterministic rule-based extraction of claims from text.

This module extracts candidate claims only. It does not verify claims or
produce verdicts. Ambiguous entities, currencies, and values remain unknown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

ClaimType = Literal["price", "entity_existence", "prediction", "causal", "other"]
Currency = Literal["RUB", "USD"]


@dataclass(frozen=True)
class Claim:
    """A text span and deterministic signals extracted from it."""

    id: str
    text: str
    ticker: str | None
    claim_type: ClaimType
    cited_value: float | None
    currency: Currency | None
    citation_url: str | None


_URL_RE = re.compile(r'''https?://[^\s<>"']+''', re.IGNORECASE)
_TICKER_RE = re.compile(r"\b[A-Z]{3,5}\b")
_COMPANY_RE = re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b")
_NUMBER_RE = re.compile(
    r"(?<![\w/])(?P<value>\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|"
    r"\d+(?:[.,]\d+)?)(?![\w/])"
)
_CURRENCY_RE = re.compile(
    r"₽|\bруб(?:\.|ля|лей|ль)?|\bRUB\b|\$|\bUSD\b|\bдоллар(?:а|ов)?\b",
    re.IGNORECASE,
)
_PRICE_WORD_RE = re.compile(
    r"\b(?:цен[ауы]|сто(?:ит|имость)|торгуется|достиг(?:ла|ло)?|"
    r"составляет|равен|равна)\b|=",
    re.IGNORECASE,
)
_YEAR_SUFFIX_RE = re.compile(r"^\s*(?:году|года|год|г\.)\b", re.IGNORECASE)
_PERCENT_SUFFIX_RE = re.compile(
    r"^\s*(?:%|процент(?:а|ов)?\b)", re.IGNORECASE
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
_RUB_CURRENCY_TOKENS = {"₽", "руб", "руб.", "рубля", "рублей", "рубль", "rub"}
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


def _split_claim_text(text: str) -> list[str]:
    """Split on sentence punctuation without splitting decimal values."""
    parts = re.split(r'''(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9«"'])''', text.strip())
    return [part.strip() for part in parts if part.strip()]


def _extract_ticker(text: str, claim_type: ClaimType) -> str | None:
    if claim_type == "entity_existence":
        return None

    for match in _TICKER_RE.finditer(text):
        candidate = match.group(0)
        if candidate not in _NON_TICKERS:
            return candidate

    company_match = _COMPANY_RE.search(text)
    if company_match:
        candidate = company_match.group(0).upper()
        if candidate not in _NON_TICKERS:
            return candidate
    return None


def _valid_number_matches(text: str) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for match in _NUMBER_RE.finditer(text):
        suffix = text[match.end():]
        if _YEAR_SUFFIX_RE.match(suffix) or _PERCENT_SUFFIX_RE.match(suffix):
            continue
        matches.append(match)
    return matches


def _extract_currency(text: str, number_match: re.Match[str]) -> Currency | None:
    nearby = text[max(0, number_match.start() - 8):number_match.end() + 8]
    currencies: set[Currency] = set()
    for match in _CURRENCY_RE.finditer(nearby):
        token = match.group(0).lower()
        currency_code = "RUB" if token in _RUB_CURRENCY_TOKENS else "USD"
        currencies.add(currency_code)
    if len(currencies) == 1:
        return currencies.pop()
    return None


def _extract_value_and_currency(
    text: str,
) -> tuple[float | None, Currency | None]:
    number_matches = _valid_number_matches(text)
    if not number_matches:
        return None, None

    currency_matches = list(_CURRENCY_RE.finditer(text))
    candidates: list[tuple[int, re.Match[str], Currency | None]] = []
    for number_match in number_matches:
        currency = _extract_currency(text, number_match)
        distance = min(
            (
                max(currency_match.start() - number_match.end(),
                    number_match.start() - currency_match.end(), 0)
                for currency_match in currency_matches
                if abs(currency_match.start() - number_match.end()) <= 8
                or abs(number_match.start() - currency_match.end()) <= 8
            ),
            default=10_000,
        )
        if currency is not None:
            candidates.append((distance, number_match, currency))

    if candidates:
        _, selected, currency = min(candidates, key=lambda item: item[0])
    else:
        price_markers = list(_PRICE_WORD_RE.finditer(text))
        if not price_markers:
            return None, None
        # A price value is expected after the closest price-language marker.
        after_markers = [
            (match.start() - marker.end(), match)
            for marker in price_markers
            for match in number_matches
            if match.start() >= marker.end()
        ]
        if not after_markers:
            return None, None
        _, selected = min(after_markers, key=lambda item: item[0])
        currency = None

    raw_value = selected.group("value").replace(" ", "").replace("\u00a0", "")
    raw_value = raw_value.replace(",", ".")
    try:
        return float(raw_value), currency
    except ValueError:
        return None, None


def _classify(text: str) -> ClaimType:
    if _PREDICTION_MARKER_RE.search(text):
        return "prediction"
    if _CAUSAL_MARKER_RE.search(text):
        return "causal"
    if _EXISTENCE_MARKER_RE.search(text):
        return "entity_existence"
    if _PRICE_WORD_RE.search(text) or _CURRENCY_RE.search(text):
        return "price"
    return "other"


def _extract_url(text: str) -> str | None:
    match = _URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(_TRAILING_URL_PUNCTUATION)


def extract_claims(text: str, trace_id: str | None = None) -> list[Claim]:
    """Extract candidate claims; no verification or verdict is performed.

    When a trace ID is supplied, claim IDs are trace-scoped and repeatable.
    Otherwise, UUID4 identifiers prevent collisions across independent calls.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if trace_id is not None and not trace_id.strip():
        raise ValueError("trace_id must be non-empty when supplied")

    claims: list[Claim] = []
    for index, segment in enumerate(_split_claim_text(text), start=1):
        claim_type = _classify(segment)
        cited_value, currency = _extract_value_and_currency(segment)
        claim_id = f"{trace_id}_c{index}" if trace_id else str(uuid4())
        claims.append(
            Claim(
                id=claim_id,
                text=segment,
                ticker=_extract_ticker(segment, claim_type),
                claim_type=claim_type,
                cited_value=cited_value,
                currency=currency,
                citation_url=_extract_url(segment),
            )
        )
    return claims
