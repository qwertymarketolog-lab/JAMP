"""JAMP-1C v0 deterministic atomic identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .tokenizer import canonicalize_bsl_query

SCHEMA_VERSION = "v0"
CANONICAL_DELIMITER = "||"
ALLOWED_STRUCTURAL_IDENTITY = frozenset({"extension_name", "module_type", "method_name"})
ATOM_TYPES = frozenset({"observation", "hypothesis", "evidence"})
PAYLOAD_KINDS = frozenset({"bsl_query", "extension_patch"})


def _json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value is not canonically JSON-serializable") from exc


def _source(source_ref: str) -> None:
    prefix = "1c://conf-sha256:"
    if not isinstance(source_ref, str) or not source_ref.startswith(prefix):
        raise ValueError("invalid source_ref")
    digest, sep, _ = source_ref[len(prefix) :].partition("/")
    if not sep or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("invalid configuration SHA-256")


def _identity(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("params must be a dictionary")
    return {
        k: params[k]
        for k in sorted(params)
        if k in ALLOWED_STRUCTURAL_IDENTITY and params[k] is not None
    }


def _content(content: dict[str, Any]) -> str:
    if not isinstance(content, dict) or content.get("kind") not in PAYLOAD_KINDS:
        raise ValueError("invalid content kind")
    normalized = dict(content)
    if normalized["kind"] == "bsl_query":
        if not isinstance(normalized.get("payload"), str):
            raise ValueError("query payload must be text")
        normalized["payload"] = canonicalize_bsl_query(normalized["payload"])
    return _json(normalized)


def compute_preimage(
    *,
    source_ref: str,
    atom_type: str,
    operator_id: str,
    operator_version: str,
    content: dict[str, Any],
    params: dict[str, Any],
) -> str:
    _source(source_ref)
    if atom_type not in ATOM_TYPES:
        raise ValueError("invalid atom_type")
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("invalid operator_id")
    if not isinstance(operator_version, str) or not operator_version:
        raise ValueError("invalid operator_version")
    return CANONICAL_DELIMITER.join(
        (
            SCHEMA_VERSION,
            source_ref,
            atom_type,
            operator_id,
            operator_version,
            _content(content),
            _json(_identity(params)),
        )
    )


@dataclass(frozen=True)
class JAMP1CAtom:
    id: str
    source_ref: str
    atom_type: str
    operator_id: str
    operator_version: str
    content: dict[str, Any]
    context: dict[str, Any]


def create_atom(
    *,
    source_ref: str,
    atom_type: str,
    operator_id: str,
    operator_version: str,
    content: dict[str, Any],
    context: dict[str, Any],
) -> JAMP1CAtom:
    preimage = compute_preimage(
        source_ref=source_ref,
        atom_type=atom_type,
        operator_id=operator_id,
        operator_version=operator_version,
        content=content,
        params=context,
    )
    return JAMP1CAtom(
        hashlib.sha256(preimage.encode("utf-8")).hexdigest(),
        source_ref,
        atom_type,
        operator_id,
        operator_version,
        dict(content),
        dict(context),
    )
