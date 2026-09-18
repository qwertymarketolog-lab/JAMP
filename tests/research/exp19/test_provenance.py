import copy

from .mock_adapters import adapters, make_signal

REQUIRED = {"source_ref", "source_type", "adapter_id", "adapter_version"}


def test_ingested_signal_carries_required_provenance_fields():
    normalized = adapters()["text"].normalize(
        make_signal("sha256:source", "text", "X")
    )

    assert normalized.keys() >= REQUIRED
    assert normalized["source_ref"] == "sha256:source"


def test_source_mutation_does_not_mutate_normalized_signal():
    signal = make_signal("sha256:source", "text", "X")
    normalized = adapters()["text"].normalize(signal)
    original = copy.deepcopy(normalized)

    signal.payload["content"] = "MUTATED"
    signal.metadata["fixture"] = "MUTATED"

    assert normalized == original
