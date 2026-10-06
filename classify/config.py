"""User configuration file, created with default values on the first run."""

import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from .calendar_rules import validate_rule
from .const import (
    CONFIG_FILE_NAME,
    DEFAULT_BURST_MAX_GAP_HOURS,
    DEFAULT_BURST_MIN_FILES,
    DEFAULT_HOLIDAY_MIN_FILES,
    DEFAULT_HOME_RADIUS_KM,
    DEFAULT_PREVIEW_COUNT,
    DEFAULT_SKI_MIN_ALTITUDE_M,
    DEFAULT_TRIP_MAX_GAP_HOURS,
    DEFAULT_TRIP_MIN_DAYS,
    DEFAULT_TRIP_MIN_FILES,
)
from .exception import ClassifyException
from .geo import Location
from .i18n import HOLIDAY_PRESETS, LANGUAGES, NAME_PRESETS, system_language

_LOGGER = logging.getLogger("classify")

# Comments written above each key of the generated file
KEY_COMMENTS = {
    "language": (
        f"Language of the default folder names and holidays: {', '.join(LANGUAGES)}"
    ),
    "home": (
        "Home location [latitude, longitude], trips are detected farther than "
        "home_radius_km\n"
        "When empty, it is guessed from the files and confirmed on the first "
        "interactive run with --events"
    ),
    "home_radius_km": None,
    "trip_max_gap_hours": (
        "A trip is a series of files far from home, without a gap longer than "
        "trip_max_gap_hours,\n"
        "lasting trip_min_days days with trip_min_files files at least"
    ),
    "trip_min_days": None,
    "trip_min_files": None,
    "burst_max_gap_hours": (
        "A burst is a single day with burst_min_files files at least, without a gap "
        "longer than burst_max_gap_hours"
    ),
    "burst_min_files": None,
    "holiday_min_files": (
        "Holidays and recurring dates need holiday_min_files files on their days"
    ),
    "ski_min_altitude_m": (
        "A winter trip higher than ski_min_altitude_m meters is a skiing trip"
    ),
    "preview": (
        "Open preview_count pictures of each event in the file manager before "
        "asking its name"
    ),
    "preview_count": None,
    "write_metadata": (
        "Write the event name in the file metadata (keywords), requires exiftool"
    ),
    "names": None,  # Built from the language preset, see names_comment
    "holidays": (
        "Holidays naming the events on their days, remove the unwanted ones\n"
        "Date rules: fixed date 'MM-DD', range 'MM-DD..MM-DD', relative to Easter\n"
        "'easter', 'easter+N' or 'easter-N', weekday of a month '2nd-sun-05' or "
        "'last-sun-05'"
    ),
    "recurring": (
        "Personal recurring dates, like birthdays, with the same date rules\n"
        "Example:\n"
        "recurring:\n"
        "  Anniversaire Léa: '03-14'\n"
        "  Anniversaire de mariage: '06-21'"
    ),
}


@dataclass
class UserConfig:
    """User configuration of the event detection."""

    language: str = field(default_factory=system_language)
    home: Location | None = None
    home_radius_km: float = DEFAULT_HOME_RADIUS_KM
    trip_max_gap_hours: float = DEFAULT_TRIP_MAX_GAP_HOURS
    trip_min_days: int = DEFAULT_TRIP_MIN_DAYS
    trip_min_files: int = DEFAULT_TRIP_MIN_FILES
    burst_max_gap_hours: float = DEFAULT_BURST_MAX_GAP_HOURS
    burst_min_files: int = DEFAULT_BURST_MIN_FILES
    holiday_min_files: int = DEFAULT_HOLIDAY_MIN_FILES
    ski_min_altitude_m: float = DEFAULT_SKI_MIN_ALTITUDE_M
    preview: bool = True
    preview_count: int = DEFAULT_PREVIEW_COUNT
    write_metadata: bool = True
    names: dict[str, str] = field(default_factory=dict)
    holidays: dict[str, str] | None = None
    recurring: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Default to the holidays of the language."""
        if self.holidays is None:
            self.holidays = dict(HOLIDAY_PRESETS[self.language])

    @property
    def name_templates(self) -> dict[str, str]:
        """Return the folder name templates, the language preset overridden."""
        return {**NAME_PRESETS[self.language], **self.names}


def default_config_path() -> Path:
    """Return the configuration file path in the XDG config directory."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config_home) / CONFIG_FILE_NAME


def names_comment(language: str) -> str:
    """Return the comment listing the folder names to override."""
    lines = [
        "Folder names overriding the language preset, with their default value:",
        "names:",
    ]
    lines += [f"  {key}: {value}" for key, value in NAME_PRESETS[language].items()]
    return "\n".join(lines)


def render_config(config: UserConfig) -> str:
    """Return the content of the configuration file, with comments."""
    content = (
        "# memories-classify configuration, used with the --events option\n"
        "# Created with the default values, edit it to fit your needs\n"
    )
    for config_field in fields(config):
        key = config_field.name
        value = getattr(config, key)
        if key == "home" and value is not None:
            value = [value.lat, value.lon]
        comment = (
            names_comment(config.language) if key == "names" else KEY_COMMENTS[key]
        )
        # A blank line before each commented group of keys
        if comment:
            content += "\n" + "".join(f"# {line}\n" for line in comment.splitlines())
        if key == "home" and value is not None:
            # Inline [latitude, longitude], easier to read and edit
            content += f"home: [{value[0]}, {value[1]}]\n"
            continue
        content += yaml.safe_dump(
            {key: value}, allow_unicode=True, sort_keys=False, width=1000
        )
    return content


def save_config(config: UserConfig, path: Path) -> None:
    """Write the configuration file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_config(config), encoding="utf-8")


def check_type(key: str, value: Any, expected: type | tuple[type, ...]) -> None:
    """Raise a ClassifyException if a configuration value has a wrong type."""
    # bool is a subclass of int, but a boolean is never a valid number
    if not isinstance(value, expected) or (
        isinstance(value, bool) and expected is not bool
    ):
        raise ClassifyException(f"Invalid value {value!r} for {key} in configuration")


def check_positive(key: str, value: float) -> None:
    """Raise a ClassifyException if a threshold is not positive."""
    if value <= 0:
        raise ClassifyException(
            f"Invalid value {value!r} for {key} in configuration, expected > 0"
        )


def check_str_dict(key: str, value: Any) -> dict[str, str]:
    """Return a dictionary of strings from the configuration."""
    if value is None:
        return {}
    check_type(key, value, dict)
    for item_key, item_value in value.items():
        check_type(f"{key}.{item_key}", item_key, (str, int))
        check_type(f"{key}.{item_key}", item_value, str)
    return {str(item_key): item_value for item_key, item_value in value.items()}


def parse_config(data: dict[str, Any], language: str | None) -> UserConfig:
    """Return the configuration from the parsed file, checking each value."""
    known_keys = {config_field.name for config_field in fields(UserConfig)}
    for key in data.keys() - known_keys:
        _LOGGER.warning("Unknown key %s in configuration ignored", key)

    values: dict[str, Any] = {}
    for config_field in fields(UserConfig):
        key = config_field.name
        if key not in data:
            continue
        value = data[key]
        match key:
            case "language":
                if value not in LANGUAGES:
                    raise ClassifyException(
                        f"Invalid language {value!r} in configuration, "
                        f"expected one of {', '.join(LANGUAGES)}"
                    )
            case "home":
                if value is not None:
                    check_type(key, value, list)
                    if len(value) != 2:
                        raise ClassifyException(
                            f"Invalid home {value!r} in configuration, "
                            "expected [latitude, longitude]"
                        )
                    for coordinate in value:
                        check_type(key, coordinate, (int, float))
                    value = Location(float(value[0]), float(value[1]))
            case "names" | "holidays" | "recurring":
                value = check_str_dict(key, value)
            case "preview" | "write_metadata":
                check_type(key, value, bool)
            case "ski_min_altitude_m":
                check_type(key, value, (int, float))
            case _ if config_field.type is int:
                check_type(key, value, int)
                check_positive(key, value)
            case _:
                check_type(key, value, (int, float))
                check_positive(key, value)
        values[key] = value

    if language is not None:
        values["language"] = language
    config = UserConfig(**values)

    for key, template in config.names.items():
        if key not in NAME_PRESETS[config.language]:
            _LOGGER.warning("Unknown name %s in configuration ignored", key)
        try:
            template.format(city="", country="", year=0)
        except (KeyError, IndexError, ValueError) as exc:
            raise ClassifyException(
                f"Invalid name {template!r} for names.{key} in configuration: {exc}"
            ) from exc
    for key in ("holidays", "recurring"):
        for name, rule in (getattr(config, key) or {}).items():
            try:
                validate_rule(rule)
            except ValueError as exc:
                raise ClassifyException(
                    f"Invalid date rule {rule!r} for {key}.{name} in configuration"
                ) from exc
    return config


def load_config(path: Path, language: str | None = None) -> UserConfig:
    """Load the configuration file, creating it with default values if missing.

    The language argument overrides the configured language.
    """
    if not path.exists():
        config = UserConfig() if language is None else UserConfig(language=language)
        try:
            save_config(config, path)
        except OSError as exc:
            _LOGGER.warning("Cannot create configuration file %s: %s", path, exc)
            return config
        _LOGGER.warning(
            "Configuration file created at %s with default values, edit it if needed",
            path,
        )
        return config

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ClassifyException(f"Cannot read configuration {path}: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ClassifyException(f"Invalid configuration {path}, expected a mapping")
    _LOGGER.debug("Configuration loaded from %s", path)
    return parse_config(data, language)
