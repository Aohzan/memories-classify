"""Sort the files in year folders, by event or in a default folder."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .config import load_config, save_config
from .const import EVENTS_STATE_FILE_NAME, PICTURE_EXTENSIONS
from .events import Event, EventDetector, EventKind, MediaInfo, guess_home
from .exception import ClassifyException
from .geo import Geocoder, Location
from .processors.files import FileProcessor
from .settings import ClassifySettings

_LOGGER = logging.getLogger("classify")

SKIP_ANSWER = "-"
SAMPLE_FILES_COUNT = 3


def is_interactive() -> bool:
    """Check if the user can answer questions."""
    return sys.stdin.isatty()


def open_folder(path: str) -> None:
    """Open a folder in the file manager, without waiting for it."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen(
                [opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except OSError:
        _LOGGER.debug("Cannot open folder %s", path, exc_info=True)


def sanitize_name(name: str) -> str:
    """Return a name usable as a folder name."""
    name = name.replace("/", "-").replace("\\", "-")
    name = "".join(char for char in name if unicodedata.category(char) != "Cc")
    # Windows does not allow folder names ending with a dot or a space
    return name.strip().rstrip(". ")


@dataclass
class Decision:
    """Name given to an event, None when skipped."""

    kind: EventKind
    start: datetime
    end: datetime
    name: str | None

    def matches(self, event: Event) -> bool:
        """Check if the decision was taken for an event, same kind and dates."""
        return (
            self.kind == event.kind
            and self.start <= event.end
            and event.start <= self.end
        )


class EventsState:
    """Decisions taken on events, saved in the output directory."""

    def __init__(self, path: Path) -> None:
        """Init."""
        self.path = path
        self.decisions: list[Decision] = []
        if not path.exists():
            return
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            self.decisions = [
                Decision(
                    kind=EventKind(item["kind"]),
                    start=datetime.fromisoformat(str(item["start"])),
                    end=datetime.fromisoformat(str(item["end"])),
                    name=item["name"],
                )
                for item in data
            ]
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
            raise ClassifyException(f"Invalid events file {path}: {exc}") from exc

    def find(self, event: Event) -> Decision | None:
        """Return the decision taken for an event, extended to its dates."""
        for decision in self.decisions:
            if decision.matches(event):
                decision.start = min(decision.start, event.start)
                decision.end = max(decision.end, event.end)
                return decision
        return None

    def add(self, event: Event, name: str | None) -> None:
        """Record the decision taken for an event."""
        self.decisions.append(Decision(event.kind, event.start, event.end, name))

    def save(self) -> None:
        """Write the decisions."""
        data = [
            {
                "kind": str(decision.kind),
                "start": decision.start.isoformat(),
                "end": decision.end.isoformat(),
                "name": decision.name,
            }
            for decision in sorted(self.decisions, key=lambda item: item.start)
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )


class EventOrganizer:
    """Detect the events, ask their names, and set the output folders."""

    def __init__(
        self,
        settings: ClassifySettings,
        file_processor: FileProcessor,
        get_picture_info: Callable[[str], tuple[datetime | None, Location | None]],
        get_video_info: Callable[[str], tuple[datetime | None, Location | None]],
    ) -> None:
        """Init."""
        self.settings = settings
        self.config = settings.user_config
        self.fp = file_processor
        self.get_picture_info = get_picture_info
        self.get_video_info = get_video_info
        self.geocoder = Geocoder(self.config.language)
        self.interactive = settings.interactive and is_interactive()
        self.state = EventsState(Path(settings.output) / EVENTS_STATE_FILE_NAME)

    def organize(self) -> None:
        """Set the output folder of each file."""
        _LOGGER.info("")
        _LOGGER.info("##### Events #####")
        infos = self.collect_infos()
        home = self.resolve_home(infos)
        events = EventDetector(self.config, self.geocoder).detect(infos, home)
        _LOGGER.info("%d events detected", len(events))

        named: list[tuple[Event, str | None]] = []
        pending: list[Event] = []
        for event in events:
            if (decision := self.state.find(event)) is not None:
                _LOGGER.debug("Event %s already decided", decision.name)
                named.append((event, decision.name))
            else:
                pending.append(event)

        total = len(pending)
        for number, event in enumerate(list(pending), start=1):
            if not self.interactive:
                break
            try:
                name = self.ask_name(event, f"{number}/{total}")
            except EOFError:
                _LOGGER.warning("No more answers, stop asking event names")
                self.interactive = False
                break
            self.state.add(event, name)
            named.append((event, name))
            pending.remove(event)

        if pending:
            _LOGGER.warning(
                "%d events detected, run interactively to name them", len(pending)
            )
            for event in pending:
                _LOGGER.warning("  %s", self.describe(event))
        # Files of the events to name are left untouched until named
        pending_paths = {info.path for event in pending for info in event.files}
        self.fp.pictures = [
            path for path in self.fp.pictures if path not in pending_paths
        ]
        self.fp.videos = [path for path in self.fp.videos if path not in pending_paths]

        # Event files are in the year of the event start, even New Year
        event_folders = {
            info.path: (event.start.year, name)
            for event, name in named
            if name
            for info in event.files
        }
        default_name = sanitize_name(self.config.name_templates["default"])
        for info in infos:
            if info.path in pending_paths:
                continue
            year, name = event_folders.get(info.path, (info.date.year, None))
            self.fp.event_dirs[info.path] = os.path.join(
                str(year), name or default_name
            )
            if name:
                self.fp.event_names[info.path] = name

        if not self.settings.dry_run:
            self.state.save()

    def collect_infos(self) -> list[MediaInfo]:
        """Return the date and location of the pictures and videos."""
        infos = []
        files = [(path, self.get_picture_info) for path in self.fp.pictures] + [
            (path, self.get_video_info) for path in self.fp.videos
        ]
        with (
            logging_redirect_tqdm(loggers=[_LOGGER]),
            tqdm(files, desc="Dates and locations", unit="file") as progress,
        ):
            for path, get_info in progress:
                try:
                    date_taken, location = get_info(path)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.error("Error reading %s: %s", path, exc)
                    continue
                if date_taken is None:
                    continue
                if date_taken.tzinfo is not None:
                    date_taken = date_taken.astimezone(
                        self.settings.user_timezone
                    ).replace(tzinfo=None)
                infos.append(MediaInfo(path, date_taken, location))
        return infos

    def resolve_home(self, infos: list[MediaInfo]) -> Location | None:
        """Return the configured home, or guess it and ask to confirm it."""
        if self.config.home is not None:
            return self.config.home
        guess = guess_home(infos)
        if guess is None:
            _LOGGER.debug("No location found, trips are not detected")
            return None
        if not self.interactive:
            _LOGGER.warning(
                "Home location not configured, trips are not detected "
                "(run interactively or set home in %s)",
                self.settings.config_path,
            )
            return None

        city = self.geocoder.place(guess).city
        try:
            answer = input(
                f"Home detected near {city} ({guess.lat}, {guess.lon}), "
                "is it correct? [Y/n] "
            )
            home: Location | None = guess
            if answer.strip().lower() not in ("", "y", "yes", "o", "oui"):
                home = self.ask_home()
        except EOFError:
            _LOGGER.warning("No more answers, trips are not detected")
            self.interactive = False
            return None
        if home is not None and not self.settings.dry_run:
            # Reload the file to not save the language set from the command line
            config = load_config(self.settings.config_path)
            config.home = home
            save_config(config, self.settings.config_path)
            _LOGGER.info("Home saved in %s", self.settings.config_path)
        return home

    def ask_home(self) -> Location | None:
        """Ask the home location until it is valid or empty."""
        while True:
            answer = input(
                "Home location as 'latitude, longitude' (empty to not detect trips): "
            ).strip()
            if not answer:
                return None
            try:
                latitude, longitude = (float(value) for value in answer.split(","))
            except ValueError:
                _LOGGER.warning("Invalid location %s", answer)
                continue
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return Location(latitude, longitude)
            _LOGGER.warning("Location out of range %s", answer)

    def describe(self, event: Event) -> str:
        """Return a summary of an event."""
        pictures = sum(
            os.path.splitext(info.path)[1].lower() in PICTURE_EXTENSIONS
            for info in event.files
        )
        description = (
            f"{event.start:%Y-%m-%d %H:%M} -> {event.end:%Y-%m-%d %H:%M}, "
            f"{pictures} pictures and {len(event.files) - pictures} videos"
        )
        if event.place:
            description += f", {event.place}"
        if event.suggestion:
            description += f" ({event.suggestion})"
        return description

    def ask_name(self, event: Event, number: str) -> str | None:
        """Ask the name of an event, None to skip it."""
        _LOGGER.info("")
        _LOGGER.info("Event %s: %s", number, self.describe(event))
        samples = ", ".join(
            os.path.basename(info.path) for info in event.files[:SAMPLE_FILES_COUNT]
        )
        _LOGGER.info("Files: %s...", samples)
        preview_dir = self.open_preview(event)
        try:
            prompt = (
                f"Name [{event.suggestion}] ('{SKIP_ANSWER}' to skip): "
                if event.suggestion
                else f"Name (empty or '{SKIP_ANSWER}' to skip): "
            )
            answer = input(prompt).strip()
        finally:
            if preview_dir:
                shutil.rmtree(preview_dir, ignore_errors=True)
        if answer == SKIP_ANSWER:
            return None
        return sanitize_name(answer or event.suggestion or "") or None

    def open_preview(self, event: Event) -> str | None:
        """Open some pictures of an event in the file manager."""
        if not self.config.preview or self.config.preview_count < 1:
            return None
        pictures = [
            info.path
            for info in event.files
            if os.path.splitext(info.path)[1].lower() in PICTURE_EXTENSIONS
        ]
        if not pictures:
            return None
        count = min(self.config.preview_count, len(pictures))
        # Pictures spread over the event
        selected = [
            pictures[round(index * (len(pictures) - 1) / max(count - 1, 1))]
            for index in range(count)
        ]
        preview_dir = tempfile.mkdtemp(prefix="memories-classify-")
        for index, path in enumerate(selected):
            link = os.path.join(preview_dir, f"{index:02d}-{os.path.basename(path)}")
            if os.name == "nt":
                # Symbolic links need privileges on Windows
                shutil.copy(path, link)
            else:
                os.symlink(os.path.abspath(path), link)
        open_folder(preview_dir)
        return preview_dir
