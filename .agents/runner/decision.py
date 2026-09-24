"""Shared decision type for Phase A policy gates."""

from __future__ import annotations

from enum import StrEnum


class Decision(StrEnum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    INCONCLUSIVE = "INCONCLUSIVE"
