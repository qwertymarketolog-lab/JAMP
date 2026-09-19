"""State Domain exceptions."""


class CausalConsistencyError(ValueError):
    """Raised when an EventDAG violates a formal causal invariant."""


class EventNotFoundError(LookupError):
    """Raised when a requested historical EventNode does not exist."""


class ReadonlyStateError(RuntimeError):
    """Raised when a historical Registry snapshot is mutated."""


class NonDeterministicEvaluationError(ValueError):
    """Raised when identical evaluator inputs produce different results."""
