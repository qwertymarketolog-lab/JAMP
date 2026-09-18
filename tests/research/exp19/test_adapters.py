from .mock_adapters import adapters, make_signal


def test_identical_content_from_distinct_sources_preserves_source_ref():
    adapter = adapters()["text"]
    left = adapter.normalize(make_signal("sha256:source-a", "text", "X happened"))
    right = adapter.normalize(make_signal("sha256:source-b", "text", "X happened"))

    assert left["payload"] == right["payload"]
    assert left["source_ref"] != right["source_ref"]


def test_all_declared_mock_modalities_normalize_deterministically():
    for kind, adapter in adapters().items():
        signal = make_signal(f"sha256:{kind}", kind, "fixture")
        assert adapter.normalize(signal) == adapter.normalize(signal)
