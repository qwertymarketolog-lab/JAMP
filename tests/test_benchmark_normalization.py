from experiments.qualification_benchmark.run_benchmark import clean_quarter


def test_clean_quarter_normalizes_supported_labels():
    assert clean_quarter("Q3") == "3"
    assert clean_quarter("3") == "3"
    assert clean_quarter("квартал 1") == "1"
    assert clean_quarter("Q4 2026") == "4:2026"
    assert clean_quarter("4 2026") == "4:2026"


def test_clean_quarter_does_not_discard_year_or_guess_invalid_values():
    assert clean_quarter("Q4 2026") != clean_quarter("4")
    assert clean_quarter("Q5") is None
    assert clean_quarter(None) is None
