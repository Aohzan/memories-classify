"""Date rules of holidays and recurring personal events.

A rule is one day or a range of two days separated by "..", each day being:
- a fixed date "MM-DD", like "10-31"
- a day relative to Easter "easter", "easter+N" or "easter-N"
- a weekday of a month "Nth-ddd-MM" or "last-ddd-MM", like "2nd-sun-05"
"""

import re
from datetime import date, timedelta

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ORDINALS = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "last": -1}

FIXED_DAY_REGEX = re.compile(r"^(\d{2})-(\d{2})$")
EASTER_DAY_REGEX = re.compile(r"^easter([+-]\d+)?$")
WEEKDAY_REGEX = re.compile(
    rf"^({'|'.join(ORDINALS)})-({'|'.join(WEEKDAYS)})-(\d{{2}})$"
)


def easter(year: int) -> date:
    """Return the Easter Sunday of a year (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    """Return the nth weekday of a month, the last one when nth is -1."""
    if nth == -1:
        next_month = date(year + month // 12, month % 12 + 1, 1)
        last_day = next_month - timedelta(days=1)
        return last_day - timedelta(days=(last_day.weekday() - weekday) % 7)
    first_day = date(year, month, 1)
    day = first_day + timedelta(days=(weekday - first_day.weekday()) % 7)
    day += timedelta(weeks=nth - 1)
    if day.month != month:
        raise ValueError(f"No {nth}th weekday {weekday} in {year}-{month:02d}")
    return day


def parse_day(token: str, year: int) -> date:
    """Return the day of a year matching a single day rule."""
    token = token.strip().lower()
    if match := FIXED_DAY_REGEX.match(token):
        return date(year, int(match.group(1)), int(match.group(2)))
    if match := EASTER_DAY_REGEX.match(token):
        return easter(year) + timedelta(days=int(match.group(1) or 0))
    if match := WEEKDAY_REGEX.match(token):
        return nth_weekday(
            year,
            int(match.group(3)),
            WEEKDAYS.index(match.group(2)),
            ORDINALS[match.group(1)],
        )
    raise ValueError(f"Invalid date rule: {token}")


def dates_for(rule: str, year: int) -> set[date]:
    """Return the days of a rule starting in a year.

    A range ending before its start ends the next year, like "12-31..01-01".
    """
    if ".." not in rule:
        return {parse_day(rule, year)}
    start_token, end_token = rule.split("..", 1)
    start = parse_day(start_token, year)
    end = parse_day(end_token, year)
    if end < start:
        end = parse_day(end_token, year + 1)
    return {start + timedelta(days=offset) for offset in range((end - start).days + 1)}


def validate_rule(rule: str) -> None:
    """Raise a ValueError if a rule is invalid."""
    # A leap year accepts the 02-29 fixed date
    dates_for(rule, 2024)
