"""Detection of events (trips, holidays, bursts) from the files date and location."""

import logging
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from itertools import combinations

from .calendar_rules import dates_for
from .config import UserConfig
from .const import (
    ROAD_TRIP_MIN_CITIES,
    ROAD_TRIP_MIN_CITY_SHARE,
    ROAD_TRIP_MIN_SPREAD_KM,
    SKI_MONTHS,
    WEEKEND_MAX_DAYS,
    WEEKEND_START_WEEKDAYS,
)
from .geo import Geocoder, Location, distance_km

_LOGGER = logging.getLogger("classify")

# Rounding of the coordinates to guess home, about 1 km
HOME_GRID_DECIMALS = 2


class EventKind(StrEnum):
    """Kind of a detected event, also the key of its name template."""

    TRIP = "trip"
    WEEKEND = "weekend"
    SKI = "ski"
    ROAD_TRIP = "road_trip"
    RECURRING = "recurring"
    HOLIDAY = "holiday"
    BURST = "burst"


@dataclass(frozen=True)
class MediaInfo:
    """Date and location of a picture or a video."""

    path: str
    # Local time without timezone
    date: datetime
    location: Location | None = None


@dataclass
class Event:
    """Files detected as a single event."""

    kind: EventKind
    files: list[MediaInfo]
    suggestion: str | None = None
    place: str | None = None

    @property
    def start(self) -> datetime:
        """Return the date of the first file."""
        return min(info.date for info in self.files)

    @property
    def end(self) -> datetime:
        """Return the date of the last file."""
        return max(info.date for info in self.files)


def guess_home(infos: Iterable[MediaInfo]) -> Location | None:
    """Return the location found on the most days, rounded to about 1 km.

    Days are counted rather than files, trips give many files in a few days.
    """
    cell_days = {
        (
            round(info.location.lat, HOME_GRID_DECIMALS),
            round(info.location.lon, HOME_GRID_DECIMALS),
            info.date.date(),
        )
        for info in infos
        if info.location
    }
    cells = Counter((lat, lon) for lat, lon, _day in cell_days)
    if not cells:
        return None
    (lat, lon), _count = cells.most_common(1)[0]
    return Location(lat, lon)


def split_on_gaps(infos: list[MediaInfo], max_gap: timedelta) -> list[list[MediaInfo]]:
    """Split files sorted by date where two files are too far apart."""
    groups: list[list[MediaInfo]] = []
    for info in infos:
        if groups and info.date - groups[-1][-1].date <= max_gap:
            groups[-1].append(info)
        else:
            groups.append([info])
    return groups


class EventDetector:
    """Detect events from the files date and location."""

    def __init__(self, config: UserConfig, geocoder: Geocoder) -> None:
        """Init."""
        self.config = config
        self.geocoder = geocoder
        self.templates = config.name_templates

    def detect(self, infos: Iterable[MediaInfo], home: Location | None) -> list[Event]:
        """Return the events, trips first, then calendar events and bursts."""
        remaining = sorted(infos, key=lambda info: info.date)
        events: list[Event] = []
        if home is not None:
            events += self.detect_trips(remaining, home)
        for step in (self.detect_calendar_events, self.detect_bursts):
            taken = {info.path for event in events for info in event.files}
            remaining = [info for info in remaining if info.path not in taken]
            events += step(remaining)
        return sorted(events, key=lambda event: event.start)

    def detect_trips(self, infos: list[MediaInfo], home: Location) -> list[Event]:
        """Return the series of files far from home."""
        max_gap = timedelta(hours=self.config.trip_max_gap_hours)
        runs: list[list[MediaInfo]] = []
        previous_away = False
        for info in infos:
            if info.location is None:
                continue
            away = distance_km(info.location, home) > self.config.home_radius_km
            if away and previous_away and info.date - runs[-1][-1].date <= max_gap:
                runs[-1].append(info)
            elif away:
                runs.append([info])
            previous_away = away

        events = []
        for run in runs:
            start, end = run[0].date, run[-1].date
            days = (end.date() - start.date()).days + 1
            run_paths = {info.path for info in run}
            # Files without location taken during the trip belong to it
            files = [
                info
                for info in infos
                if start <= info.date <= end
                and (info.location is None or info.path in run_paths)
            ]
            if days < self.config.trip_min_days or len(files) < (
                self.config.trip_min_files
            ):
                continue
            events.append(self.name_trip(run, files, days))
        return events

    def name_trip(
        self, located: list[MediaInfo], files: list[MediaInfo], days: int
    ) -> Event:
        """Return a trip event, named from its kind and its places."""
        places = self.geocoder.places(
            [info.location for info in located if info.location]
        )
        cities = Counter(place.city for place in places)
        city = cities.most_common(1)[0][0]
        country_code = Counter(place.country_code for place in places).most_common(1)[
            0
        ][0]
        start = located[0].date
        altitudes = [
            info.location.altitude
            for info in located
            if info.location and info.location.altitude is not None
        ]
        main_cities = {
            place.city: place.location
            for place in places
            if cities[place.city] >= ROAD_TRIP_MIN_CITY_SHARE * len(places)
        }
        spread = max(
            (
                distance_km(first, second)
                for first, second in combinations(main_cities.values(), 2)
            ),
            default=0,
        )

        if (
            start.month in SKI_MONTHS
            and altitudes
            and statistics.median(altitudes) >= self.config.ski_min_altitude_m
        ):
            kind = EventKind.SKI
        elif (
            len(main_cities) >= ROAD_TRIP_MIN_CITIES
            and spread >= ROAD_TRIP_MIN_SPREAD_KM
        ):
            kind = EventKind.ROAD_TRIP
        elif days <= WEEKEND_MAX_DAYS and start.weekday() in WEEKEND_START_WEEKDAYS:
            kind = EventKind.WEEKEND
        else:
            kind = EventKind.TRIP

        country = self.geocoder.country_name(country_code)
        suggestion = self.templates[kind].format(
            city=city, country=country, year=start.year
        )
        place = country if kind == EventKind.ROAD_TRIP else city
        return Event(kind=kind, files=files, suggestion=suggestion, place=place)

    def detect_calendar_events(self, infos: list[MediaInfo]) -> list[Event]:
        """Return the files of the recurring dates, then of the holidays."""
        by_day: dict[date, list[MediaInfo]] = defaultdict(list)
        for info in infos:
            by_day[info.date.date()].append(info)
        # A range like New Year starts the year before its last day
        years = sorted({day.year for day in by_day} | {day.year - 1 for day in by_day})

        events = []
        taken: set[str] = set()
        for kind, rules in (
            (EventKind.RECURRING, self.config.recurring),
            (EventKind.HOLIDAY, self.config.holidays or {}),
        ):
            for name, rule in rules.items():
                for year in years:
                    try:
                        days = dates_for(rule, year)
                    except ValueError:
                        # Like 02-29 out of leap years
                        continue
                    files = [
                        info
                        for day in sorted(days)
                        for info in by_day.get(day, [])
                        if info.path not in taken
                    ]
                    if not files or len(files) < self.config.holiday_min_files:
                        continue
                    taken.update(info.path for info in files)
                    events.append(
                        Event(kind=kind, files=files, suggestion=f"{name} {year}")
                    )
        return events

    def detect_bursts(self, infos: list[MediaInfo]) -> list[Event]:
        """Return the days with many files close in time."""
        max_gap = timedelta(hours=self.config.burst_max_gap_hours)
        by_day: dict[date, list[MediaInfo]] = defaultdict(list)
        for info in infos:
            by_day[info.date.date()].append(info)
        return [
            Event(kind=EventKind.BURST, files=group)
            for day_files in by_day.values()
            for group in split_on_gaps(day_files, max_gap)
            if len(group) >= self.config.burst_min_files
        ]
