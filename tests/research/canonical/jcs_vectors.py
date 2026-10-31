"""JCS (RFC 8785) input/output vectors.

Vectors are parsed from JSON bytes before calling canonical_bytes. Reject cases
are exercised separately at the parser boundary in test_jcs_parsing.py.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vector:
    id: str
    input: bytes
    expected: bytes
    note: str


V1 = Vector("V1", b"1.0", b"1", "ECMAScript number serialization removes trailing .0")
V2 = Vector("V2", b"1e21", b"1e+21", "Exponent form is used at 1e21")
V4A = Vector("V4a", b'"\\u001f"', b'"\\u001f"', "U+001F must be escaped")
V4B = Vector(
    "V4b",
    b'"\\u007f"',
    b'"\x7f"',
    "U+007F is literal, not escaped",
)
V5 = Vector(
    "V5",
    b'"\\ud83d\\ude00"',
    '"😀"'.encode(),
    "A valid UTF-16 surrogate pair becomes one Unicode scalar value",
)
V6 = Vector(
    "V6",
    b'{"\\uFB33":1,"\\uD83D\\uDE00":2}',
    '{"😀":2,"דּ":1}'.encode(),
    "Object keys are ordered by UTF-16 code units, not Unicode code points",
)
V8 = Vector(
    "V8",
    b'{ "a" : 1, "b" : 2 }',
    b'{"a":1,"b":2}',
    "Whitespace is absent from canonical output",
)
V9 = Vector(
    "V9",
    b'{"k":"a\\r\\nb"}',
    b'{"k":"a\\r\\nb"}',
    "CR and LF in strings retain their required JSON escapes",
)

CONFORMANCE_VECTORS = (V1, V2, V4A, V4B, V5, V6, V8, V9)

# V3a (integer 2^53+1), V3b (1e400), and V7 (duplicate keys) are parser
# boundary rejection vectors, not values to silently coerce before hashing.
V3A_UNSAFE_INTEGER = b"9007199254740993"
V3B_FLOAT_OVERFLOW = b"1e400"
V7_DUPLICATE_KEYS = b'{"a":1,"a":2}'
