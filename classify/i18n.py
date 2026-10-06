"""Language presets of the event folder names and holidays."""

import locale
import os

DEFAULT_LANGUAGE = "en"

# Folder names of the detected events and of the files without event
NAME_PRESETS: dict[str, dict[str, str]] = {
    "en": {
        "trip": "Holidays in {city} {year}",
        "weekend": "Weekend in {city} {year}",
        "ski": "Skiing in {city} {year}",
        "road_trip": "Road trip {country} {year}",
        "default": "Misc",
    },
    "fr": {
        "trip": "Vacances à {city} {year}",
        "weekend": "Week-end à {city} {year}",
        "ski": "Ski à {city} {year}",
        "road_trip": "Road trip {country} {year}",
        "default": "Divers",
    },
}

# Holiday names and date rules, see calendar_rules for the syntax
HOLIDAY_PRESETS: dict[str, dict[str, str]] = {
    "en": {
        "New Year": "12-31..01-01",
        "Valentine's Day": "02-14",
        "Shrove Tuesday": "easter-47",
        "Easter": "easter..easter+1",
        "Mother's Day": "2nd-sun-05",
        "Father's Day": "3rd-sun-06",
        "Back to school": "09-01..09-05",
        "Halloween": "10-31",
        "Thanksgiving": "4th-thu-11",
        "Christmas": "12-24..12-25",
    },
    "fr": {
        "Nouvel An": "12-31..01-01",
        "Épiphanie": "01-06",
        "Chandeleur": "02-02",
        "Saint-Valentin": "02-14",
        "Mardi gras": "easter-47",
        "Fête des grands-mères": "1st-sun-03",
        "Pâques": "easter..easter+1",
        # The French Mother's Day moves to June when it falls on Pentecost
        "Fête des mères": "last-sun-05",
        "Fête des pères": "3rd-sun-06",
        "Fête de la musique": "06-21",
        "14 juillet": "07-14",
        "Rentrée scolaire": "09-01..09-05",
        "Halloween": "10-31",
        "Noël": "12-24..12-25",
    },
}

LANGUAGES = list(NAME_PRESETS)


def system_language() -> str:
    """Return the supported language of the system locale, English otherwise."""
    candidates = [os.environ.get(name) for name in ("LC_ALL", "LC_MESSAGES", "LANG")]
    candidates.append(locale.getlocale()[0])
    for candidate in candidates:
        if not candidate:
            continue
        language = candidate.split(".")[0].split("_")[0].lower()
        if language in NAME_PRESETS:
            return language
    return DEFAULT_LANGUAGE
