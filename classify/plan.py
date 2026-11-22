"""Plan of the folders of the files, written to be reviewed then applied.

A plan is a JSON file listing groups of files (events, or days out of any event)
with a suggested folder. Other tools or people may add a "proposal" to a group or
to a file: it wins over the suggestion. Folders are relative to the output
directory, like "2025/Christmas 2025".
"""

import json
import logging
import os
import re
from datetime import timedelta
from typing import Any

from .events import Event, MediaInfo, split_on_gaps
from .exception import ClassifyException
from .organizer import EventOrganizer, sanitize_name

_LOGGER = logging.getLogger("classify")

PLAN_VERSION = 1
YEAR_FOLDER_REGEX = re.compile(r"^\d{4}$")

# Kinds of the groups that are not detected events
DAY_GROUP = "day"
UNDATED_GROUP = "undated"


def write_json(data: dict[str, Any], path: str) -> None:
    """Write a plan."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=1)
        file.write("\n")


def read_json(path: str) -> dict[str, Any]:
    """Read a plan or exported decisions."""
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError) as exc:
        raise ClassifyException(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ClassifyException(f"Invalid content in {path}, expected a mapping")
    return data


def check_folder(folder: Any) -> str:
    """Return a decided folder as a safe path relative to the output directory."""
    if not isinstance(folder, str):
        raise ClassifyException(f"Invalid folder {folder!r}, expected a string")
    parts = [sanitize_name(part) for part in folder.replace("\\", "/").split("/")]
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ClassifyException(
            f"Invalid folder {folder!r}, expected a path relative to the output"
        )
    return os.path.join(*parts)


def resolve_decisions(data: dict[str, Any]) -> dict[str, str]:
    """Return the folder of each file path, from exported decisions or from a plan.

    In a plan, the proposal of a file wins over the one of its group, then come
    their suggestions. Files without any of them are left out.
    """
    if "decisions" in data:
        decisions = data["decisions"]
        if not isinstance(decisions, dict):
            raise ClassifyException("Invalid decisions, expected a mapping")
        return {
            str(path): check_folder(folder)
            for path, folder in decisions.items()
            if folder
        }

    try:
        return {
            file["path"]: check_folder(folder)
            for group in data["groups"]
            for file in group["files"]
            if (
                folder := file.get("proposal")
                or group.get("proposal")
                or file.get("suggestion")
                or group.get("suggestion")
            )
        }
    except (KeyError, TypeError) as exc:
        raise ClassifyException(f"Invalid plan: {exc!r}") from exc


def existing_folders(output: str) -> dict[str, dict[str, int]]:
    """Return the number of files of each folder of the year folders."""
    folders: dict[str, dict[str, int]] = {}
    if not os.path.isdir(output):
        return folders
    for year in sorted(os.listdir(output)):
        year_path = os.path.join(output, year)
        if not YEAR_FOLDER_REGEX.match(year) or not os.path.isdir(year_path):
            continue
        folders[year] = {
            entry.name: sum(item.is_file() for item in os.scandir(entry.path))
            for entry in sorted(os.scandir(year_path), key=lambda entry: entry.name)
            if entry.is_dir()
        }
    return folders


def build_plan(organizer: EventOrganizer) -> dict[str, Any]:
    """Return the plan of the files of the directory, without changing them."""
    settings = organizer.settings
    infos, events = organizer.analyze()

    located = [info for info in infos if info.location]
    cities = {
        info.path: place.city
        for info, place in zip(
            located,
            organizer.geocoder.places(
                [info.location for info in located if info.location]
            ),
            strict=True,
        )
    }

    def relative(path: str) -> str:
        return os.path.relpath(path, settings.directory)

    def describe(info: MediaInfo) -> dict[str, Any]:
        rule_folder = organizer.rule_folders.get(info.path)
        return {
            "path": relative(info.path),
            "date": info.date.isoformat(),
            "city": cities.get(info.path),
            "camera": info.camera,
            "suggestion": (
                f"{info.date.year}/{sanitize_name(rule_folder)}"
                if rule_folder
                else None
            ),
        }

    def describe_event(event: Event) -> dict[str, Any]:
        decision = organizer.state.find(event)
        name = decision.name if decision else event.suggestion
        return {
            "kind": str(event.kind),
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "place": event.place,
            "suggestion": (
                f"{event.start.year}/{sanitize_name(name)}" if name else None
            ),
            # The files of an event follow it, whatever their own rules
            "files": [{**describe(info), "suggestion": None} for info in event.files],
        }

    groups = [describe_event(event) for event in events]
    in_events = {info.path for event in events for info in event.files}
    others = sorted(
        (info for info in infos if info.path not in in_events),
        key=lambda info: info.date,
    )
    max_gap = timedelta(hours=organizer.config.burst_max_gap_hours)
    days: dict[Any, list[MediaInfo]] = {}
    for info in others:
        days.setdefault(info.date.date(), []).append(info)
    for day_files in days.values():
        for files in split_on_gaps(day_files, max_gap):
            groups.append(
                {
                    "kind": DAY_GROUP,
                    "start": files[0].date.isoformat(),
                    "end": files[-1].date.isoformat(),
                    "place": None,
                    "suggestion": None,
                    "files": [describe(info) for info in files],
                }
            )
    groups.sort(key=lambda group: group["start"])
    if organizer.undated:
        groups.append(
            {
                "kind": UNDATED_GROUP,
                "start": None,
                "end": None,
                "place": None,
                "suggestion": None,
                "files": [
                    {
                        "path": relative(path),
                        "date": None,
                        "city": None,
                        "camera": None,
                        "suggestion": None,
                    }
                    for path in sorted(organizer.undated)
                ],
            }
        )
    for number, group in enumerate(groups, start=1):
        group["id"] = f"g{number:03d}"

    return {
        "version": PLAN_VERSION,
        "directory": os.path.abspath(settings.directory),
        "output": os.path.abspath(settings.output),
        "default_folder": sanitize_name(organizer.config.name_templates["default"]),
        "folders": existing_folders(settings.output),
        "groups": groups,
    }
