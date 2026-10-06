"""Test events module."""

from datetime import datetime, timedelta

import pytest

from classify.config import UserConfig
from classify.events import Event, EventDetector, EventKind, MediaInfo, guess_home
from classify.geo import Geocoder, Location

LYON = Location(45.7640, 4.8357)
BIARRITZ = Location(43.4832, -1.5586)
CHAMONIX = Location(45.9237, 6.8694, 1800)
ANNECY = Location(45.8992, 6.1294)
ROME = Location(41.9028, 12.4964)
FLORENCE = Location(43.7696, 11.2558)
VENICE = Location(45.4408, 12.3155)


def series(
    tag: str,
    start: datetime,
    count: int,
    location: Location | None = None,
    step: timedelta = timedelta(hours=1),
) -> list[MediaInfo]:
    """Return files taken regularly from a date."""
    return [
        MediaInfo(f"{tag}-{index}.jpg", start + index * step, location)
        for index in range(count)
    ]


def daily(
    tag: str, first_day: datetime, days: int, location: Location | None
) -> list[MediaInfo]:
    """Return four files a day during several days."""
    return [
        info
        for day in range(days)
        for info in series(f"{tag}{day}", first_day + timedelta(days=day), 4, location)
    ]


def detect(
    infos: list[MediaInfo], home: Location | None = LYON, **config: object
) -> list[Event]:
    """Detect the events with an English configuration."""
    user_config = UserConfig(language=config.pop("language", "en"), **config)  # ty: ignore[invalid-argument-type]
    detector = EventDetector(user_config, Geocoder(user_config.language))
    return detector.detect(infos, home)


def test_guess_home() -> None:
    """Home is the location found on the most days, not with the most files."""
    infos = daily("home", datetime(2025, 3, 1), 3, LYON) + series(
        "away", datetime(2025, 3, 10), 20, BIARRITZ
    )

    assert guess_home(infos) == Location(45.76, 4.84)
    assert guess_home(series("none", datetime(2025, 3, 1), 3)) is None


def test_trip() -> None:
    """Files far from home during days are a trip, with files without location."""
    infos = (
        series("before", datetime(2025, 6, 30, 10), 2, LYON)
        + daily("trip", datetime(2025, 7, 1, 10), 5, BIARRITZ)
        + series("phone", datetime(2025, 7, 2, 20), 3)
        + series("after", datetime(2025, 7, 7, 10), 2, LYON)
    )

    events = detect(infos)

    assert len(events) == 1
    assert events[0].kind == EventKind.TRIP
    assert events[0].suggestion == "Holidays in Biarritz 2025"
    assert len(events[0].files) == 23


def test_trip_in_french() -> None:
    """Trip names follow the language preset."""
    events = detect(daily("trip", datetime(2025, 7, 1, 10), 5, BIARRITZ), language="fr")

    assert events[0].suggestion == "Vacances à Biarritz 2025"


def test_short_trip_ignored() -> None:
    """A single day far from home is not a trip."""
    assert detect(series("day", datetime(2025, 7, 1, 10), 12, BIARRITZ)) == []


def test_ski() -> None:
    """A winter trip in the mountains is a skiing trip."""
    events = detect(daily("ski", datetime(2025, 2, 10, 10), 5, CHAMONIX))

    assert events[0].kind == EventKind.SKI
    assert events[0].suggestion == "Skiing in Chamonix-Mont-Blanc 2025"


def test_weekend() -> None:
    """A short trip from Friday is a weekend."""
    # 2025-06-13 is a Friday
    events = detect(daily("weekend", datetime(2025, 6, 13, 10), 3, ANNECY))

    assert events[0].kind == EventKind.WEEKEND
    assert events[0].suggestion == "Weekend in Annecy 2025"


def test_road_trip() -> None:
    """A trip through several cities is a road trip, named from the country."""
    infos = (
        daily("rome", datetime(2025, 8, 1, 10), 3, ROME)
        + daily("florence", datetime(2025, 8, 4, 10), 3, FLORENCE)
        + daily("venice", datetime(2025, 8, 7, 10), 3, VENICE)
    )

    events = detect(infos)
    assert events[0].kind == EventKind.ROAD_TRIP
    assert events[0].suggestion == "Road trip Italy 2025"

    events = detect(infos, language="fr")
    assert events[0].suggestion == "Road trip Italie 2025"


def test_no_trip_without_home() -> None:
    """Trips are not detected without home."""
    assert detect(daily("trip", datetime(2025, 7, 1, 10), 5, BIARRITZ), home=None) == []


def test_christmas() -> None:
    """Files on holidays are named from the holiday."""
    infos = series("christmas", datetime(2025, 12, 24, 18), 6, LYON)

    events = detect(infos)

    assert len(events) == 1
    assert events[0].kind == EventKind.HOLIDAY
    assert events[0].suggestion == "Christmas 2025"


def test_new_year_over_two_years() -> None:
    """A holiday over two years is named from its first year."""
    infos = series("new-year", datetime(2025, 12, 31, 20), 6)

    events = detect(infos)

    assert [event.suggestion for event in events] == ["New Year 2025"]
    assert events[0].files[-1].date.year == 2026


def test_mothers_day_in_french() -> None:
    """The French preset uses the French date of Mother's day."""
    infos = series("mother", datetime(2025, 5, 25, 12), 5)

    assert [event.suggestion for event in detect(infos, language="fr")] == [
        "Fête des mères 2025"
    ]
    assert detect(infos) == []


def test_recurring_before_holiday() -> None:
    """Personal recurring dates win over the holidays of the same day."""
    infos = series("birthday", datetime(2025, 12, 25, 12), 6)

    events = detect(infos, recurring={"Léa's birthday": "12-25"})

    assert len(events) == 1
    assert events[0].kind == EventKind.RECURRING
    assert events[0].suggestion == "Léa's birthday 2025"


def test_holiday_with_few_files_ignored() -> None:
    """A holiday needs enough files."""
    assert detect(series("halloween", datetime(2025, 10, 31, 18), 4)) == []


def test_burst() -> None:
    """Many files in a few hours are an event without suggestion."""
    infos = series(
        "party", datetime(2025, 3, 14, 12), 15, LYON, step=timedelta(minutes=10)
    ) + series("ordinary", datetime(2025, 3, 20, 12), 4, LYON)

    events = detect(infos)

    assert len(events) == 1
    assert events[0].kind == EventKind.BURST
    assert events[0].suggestion is None
    assert len(events[0].files) == 15


def test_burst_split_on_gap() -> None:
    """Files of a day far apart in time are not a burst."""
    infos = series("morning", datetime(2025, 3, 14, 8), 8, step=timedelta(minutes=5))
    infos += series("evening", datetime(2025, 3, 14, 20), 8, step=timedelta(minutes=5))

    assert detect(infos) == []


def test_trip_wins_over_holiday() -> None:
    """Holidays during a trip belong to the trip."""
    infos = daily("trip", datetime(2025, 12, 22, 10), 6, BIARRITZ)

    events = detect(infos)

    assert [event.kind for event in events] == [EventKind.TRIP]


@pytest.mark.parametrize("threshold", [3, 30])
def test_configured_threshold(threshold: int) -> None:
    """Thresholds come from the configuration."""
    infos = series("party", datetime(2025, 3, 14, 12), 10, step=timedelta(minutes=10))

    events = detect(infos, burst_min_files=threshold)

    assert len(events) == (1 if threshold <= 10 else 0)


def test_holiday_without_threshold() -> None:
    """Holidays without files are not events, whatever the threshold."""
    infos = series("day", datetime(2025, 3, 20, 12), 1)

    assert detect(infos, holiday_min_files=0) == []
