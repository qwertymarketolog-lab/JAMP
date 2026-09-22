# ARCHITECTURAL POLICY: Fixed canonical anchor for G4 regression stability.
#
# This fixture is intentionally decoupled from observed telemetry, p50
# calculations, sample bounds, and empirical tie-break heuristics.
# The anchor is a deterministic structural regression target.

CANONICAL_G4_FIXED_ANCHOR_NODE: int = 0
