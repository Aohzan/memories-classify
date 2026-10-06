"""Locations and offline reverse geocoding."""

import gettext
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

_LOGGER = logging.getLogger("classify")

EARTH_RADIUS_KM = 6371


class Location(NamedTuple):
    """GPS location of a picture or a video."""

    lat: float
    lon: float
    altitude: float | None = None


@dataclass(frozen=True)
class Place:
    """Nearest city of a location."""

    city: str
    country_code: str
    location: Location


def distance_km(first: Location, second: Location) -> float:
    """Return the great-circle distance between two locations."""
    lat1, lon1, lat2, lon2 = map(
        math.radians, (first.lat, first.lon, second.lat, second.lon)
    )
    haversine = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(haversine))


class Geocoder:
    """Offline reverse geocoder, based on the GeoNames cities database."""

    def __init__(self, language: str) -> None:
        """Init."""
        self.language = language

    def places(self, locations: Sequence[Location]) -> list[Place]:
        """Return the nearest city of each location."""
        if not locations:
            return []
        # Imported on demand, loading the cities database takes a while
        import reverse_geocoder

        results = reverse_geocoder.search(
            [(location.lat, location.lon) for location in locations],
            mode=1,
            verbose=False,
        )
        return [
            Place(
                city=result["name"],
                country_code=result["cc"],
                location=Location(float(result["lat"]), float(result["lon"])),
            )
            for result in results
        ]

    def place(self, location: Location) -> Place:
        """Return the nearest city of a location."""
        return self.places([location])[0]

    def country_name(self, country_code: str) -> str:
        """Return the country name in the configured language."""
        import pycountry

        country = pycountry.countries.get(alpha_2=country_code)
        if country is None:
            return country_code
        name = getattr(country, "common_name", country.name)
        translation = gettext.translation(
            "iso3166-1",
            pycountry.LOCALES_DIR,
            languages=[self.language],
            fallback=True,
        )
        return translation.gettext(name)
