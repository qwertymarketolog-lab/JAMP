from decimal import Decimal

from experiments.financial_audit.run_experiment import clean_number, values_match


def test_clean_number_handles_currency_and_grouping() -> None:
    assert clean_number("$4,250,000.50") == Decimal("4250000.50")
    assert clean_number("USD 50,000") == Decimal("50000")


def test_clean_number_handles_russian_million_magnitude() -> None:
    assert clean_number("1.2 миллиона долларов") == Decimal("1200000.0")
    assert clean_number("1.2 million") == Decimal("1200000.0")


def test_clean_number_rejects_ambiguous_or_invalid_text_instead_of_zero() -> None:
    assert clean_number("about fifteen percent and $1,015,000") is None
    assert clean_number("not a number") is None
    assert clean_number(True) is None
    assert clean_number(None) is None


def test_values_match_keeps_quarter_as_exact_string_and_parses_financial_values() -> None:
    expected = {
        "quarter": "Q3 2026",
        "revenue": 4250000.50,
        "operating_expenses": 1200000,
        "net_income": 1015000,
        "legal_fees": 50000,
    }
    actual = {
        "quarter": "Q3 2026",
        "revenue": "$4,250,000.50",
        "operating_expenses": "1.2 миллиона долларов",
        "net_income": "$1,015,000",
        "legal_fees": "USD 50,000",
    }
    assert values_match(actual, expected) == (True, [])


def test_values_match_fails_closed_for_unparseable_financial_values() -> None:
    expected = {
        "quarter": "Q3 2026",
        "revenue": 4250000.50,
        "operating_expenses": 1200000,
        "net_income": 1015000,
        "legal_fees": 50000,
    }
    actual = {
        "quarter": "Q3 2026",
        "revenue": "not available",
        "operating_expenses": "1.2 million",
        "net_income": "$1,015,000",
        "legal_fees": "$50,000",
    }
    matched, mismatches = values_match(actual, expected)
    assert not matched
    assert any("revenue: not a valid financial number" in item for item in mismatches)
