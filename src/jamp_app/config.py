"""Minimal application configuration boundary for JAMP MVP."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Minimal immutable application configuration."""

    name: str = "JAMP"
    version: str = "0.1.0"
