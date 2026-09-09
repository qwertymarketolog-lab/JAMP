"""P22.8 test-first contract for deterministic hypothesis formation.

The production module is intentionally absent at contract deployment time.
These gates define the immutable public boundary before implementation.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from jamp.research import evidence
from jamp.research import hypothesis_formation as hypothesis

FORBIDDEN = {
    "select", "select_node", "select_nodes", "rank", "sort", "sorted",
    "filter", "threshold", "heuristic", "estimate", "approximate",
    "goal", "objective", "utility", "fitness", "probability", "prediction",
    "confidence", "weight", "score", "score_hypothesis", "relevance",
    "priority", "optimize", "optimization", "bayesian",
}
HEX64 = "a" * 64
HEX64_B = "b" * 64

# P22.8 namespace-retarget barrier: production remains withheld.
