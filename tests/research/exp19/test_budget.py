def ingest_with_budget(signal, *, token_budget, compute_budget):
    return {
        "signal": signal,
        "budget": {
            "token_budget": token_budget,
            "compute_budget": compute_budget,
        },
    }


def test_caller_budget_is_explicitly_propagated():
    result = ingest_with_budget("fixture", token_budget=100, compute_budget=7)
    assert result["budget"] == {"token_budget": 100, "compute_budget": 7}


def test_budget_exhaustion_is_controlled():
    result = ingest_with_budget("fixture", token_budget=0, compute_budget=0)
    assert result["budget"]["token_budget"] == 0
    assert result["budget"]["compute_budget"] == 0
