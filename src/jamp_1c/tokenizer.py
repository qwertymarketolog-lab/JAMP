"""Fail-closed lexical canonicalizer for 1C BSL/query text."""
from __future__ import annotations
from dataclasses import dataclass

class BSLTokenizationError(ValueError):
    """Raised when canonicalization cannot be completed safely."""

@dataclass(frozen=True)
class Token:
    kind: str
    value: str

KEYWORDS = frozenset({"ВЫБРАТЬ", "ИЗ", "ГДЕ", "ИЛИ", "И", "НЕ", "КАК", "ПО", "ВЫБОР", "КОГДА", "ТОГДА", "ИНАЧЕ", "КОНЕЦ", "ОБЪЕДИНИТЬ", "ВСЕ", "ЛЕВОЕ", "ПРАВОЕ", "ВНУТРЕННЕЕ", "СОЕДИНЕНИЕ", "СГРУППИРОВАТЬ", "УПОРЯДОЧИТЬ", "ИМЕЮЩИЕ"})

def _identifier_start(ch: str) -> bool:
    return ch == "_" or ch.isalpha()

def _identifier_part(ch: str) -> bool:
    return ch == "_" or ch.isalnum()

def scan(text: str) -> list[Token]:
    if not isinstance(text, str):
        raise BSLTokenizationError("input must be text")
    slash, star = chr(47), chr(42)
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            while i < len(text) and text[i].isspace(): i += 1
            tokens.append(Token("WS", " "))
        elif i + 1 < len(text) and text[i:i + 2] == slash + slash:
            i += 2
            while i < len(text) and text[i] not in "\r\n": i += 1
        elif i + 1 < len(text) and text[i:i + 2] == slash + star:
            end = text.find(star + slash, i + 2)
            if end < 0: raise BSLTokenizationError("unterminated block comment")
            i = end + 2
        elif ch == chr(34):
            start = i; i += 1
            while i < len(text):
                if text[i] == chr(34) and i + 1 < len(text) and text[i + 1] == chr(34): i += 2; continue
                if text[i] == chr(34): i += 1; tokens.append(Token("STRING", text[start:i])); break
                i += 1
            else: raise BSLTokenizationError("unterminated string literal")
        elif _identifier_start(ch):
            start = i; i += 1
            while i < len(text) and _identifier_part(text[i]): i += 1
            value = text[start:i]; upper = value.upper()
            tokens.append(Token("KEYWORD", upper) if upper in KEYWORDS else Token("IDENT", value))
        else:
            tokens.append(Token("PUNCT", ch)); i += 1
    return tokens

def canonicalize_bsl_query(text: str) -> str:
    out: list[str] = []; pending = False
    for token in scan(text):
        if token.kind == "WS": pending = bool(out); continue
        if pending: out.append(" ")
        out.append(token.value); pending = False
    return "".join(out).strip()
