"""Typed records used by the opt-in PostgreSQL persistence layer."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    api_key_hash: str
    plan: str
    created_at: datetime
    disabled: bool = False


@dataclass(frozen=True)
class AuditTraceRecord:
    id: str
    organization_id: str
    trace_id: str
    payload: dict[str, Any]
    created_at: datetime
