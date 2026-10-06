"""Test calendar_rules module."""

from datetime import date

import pytest

from classify.calendar_rules import dates_for, easter, validate_rule
from classify.i18n import HOLIDAY_PRESETS


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5))],
)
def test_easter(year: int, expected: date) -> None:
    """Easter Sunday is computed for any year."""
    assert easter(year) == expected


@pytest.mark.parametrize(
    ("rule", "year", "expected"),
    [
        ("10-31", 2026, {date(2026, 10, 31)}),
        ("easter-47", 2026, {date(2026, 2, 17)}),
        ("easter..easter+1", 2026, {date(2026, 4, 5), date(2026, 4, 6)}),
        ("last-sun-05", 2026, {date(2026, 5, 31)}),
        ("2nd-sun-05", 2026, {date(2026, 5, 10)}),
        ("4th-thu-11", 2026, {date(2026, 11, 26)}),
        ("12-31..01-01", 2026, {date(2026, 12, 31), date(2027, 1, 1)}),
        ("09-01..09-03", 2026, {date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)}),
    ],
)
def test_dates_for(rule: str, year: int, expected: set[date]) -> None:
    """Rules give the days of a year."""
    assert dates_for(rule, year) == expected


@pytest.mark.parametrize("rule", ["13-01", "02-30", "christmas", "5th-mon-02", ""])
def test_invalid_rule(rule: str) -> None:
    """Invalid rules are rejected."""
    with pytest.raises(ValueError):
        validate_rule(rule)


@pytest.mark.parametrize("language", HOLIDAY_PRESETS)
def test_holiday_presets_are_valid(language: str) -> None:
    """The holidays of every language have valid rules."""
    for rule in HOLIDAY_PRESETS[language].values():
        validate_rule(rule)
