"""Opt-in PostgreSQL database foundation for JAMP."""

from jamp.db.connection import get_connection, get_pool, release_connection
from jamp.db.init import init_schema
from jamp.db.models import AuditTraceRecord, Organization
from jamp.db.traces import (
    OrganizationMismatchError,
    fetch_trace_for_organization,
    insert_trace,
)

__all__ = [
    "AuditTraceRecord",
    "Organization",
    "OrganizationMismatchError",
    "fetch_trace_for_organization",
    "get_connection",
    "get_pool",
    "init_schema",
    "insert_trace",
    "release_connection",
]
