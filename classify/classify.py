"""Main function to classify pictures and videos."""

import logging
import os
from collections.abc import Callable

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .organizer import EventOrganizer, sanitize_name
from .plan import build_plan, read_json, resolve_decisions, write_json
from .processors.files import FileProcessor
from .processors.image import ImageProcessor
from .processors.video import VideoProcessor
from .review import write_review
from .settings import ClassifySettings

_LOGGER = logging.getLogger("classify")


class Classify:
    """Classify global class."""

    def __init__(self, settings: ClassifySettings):
        """Initialize the class."""
        self.settings = settings
        self.fp = FileProcessor(settings=settings)
        self.ip = ImageProcessor(settings=settings, file_processor=self.fp)
        self.vp = VideoProcessor(settings=settings, file_processor=self.fp)

    def organizer(self) -> EventOrganizer:
        """Return the event organizer reading the files with the processors."""
        return EventOrganizer(
            settings=self.settings,
            file_processor=self.fp,
            get_picture_info=lambda path: (
                self.ip.get_date_taken(path),
                self.ip.get_location(path),
            ),
            get_video_info=lambda path: (
                self.vp.get_date_taken(path),
                self.vp.get_location(path),
            ),
            get_camera=self.ip.get_camera,
        )

    def write_plan(self, path: str) -> None:
        """Write the plan of the files, without changing them."""
        # Trashed files are deleted on a normal run, they need no decision
        for files in (self.fp.pictures, self.fp.videos):
            files[:] = [file for file in files if not self.fp.is_android_trash(file)]
        plan = build_plan(self.organizer())
        write_json(plan, path)
        _LOGGER.info(
            "Plan of %d files in %d groups written in %s",
            sum(len(group["files"]) for group in plan["groups"]),
            len(plan["groups"]),
            path,
        )

    def apply_decisions(self, path: str) -> None:
        """Keep only the files with a decided folder, and set it as their output."""
        decisions = resolve_decisions(read_json(path))
        files = {
            os.path.relpath(file, self.settings.directory): file
            for file in self.fp.pictures + self.fp.videos
        }
        default_name = sanitize_name(
            self.settings.user_config.name_templates["default"]
        )
        decided = set()
        for relpath, folder in decisions.items():
            if (file := files.get(os.path.normpath(relpath))) is None:
                _LOGGER.warning("File %s of the decisions not found", relpath)
                continue
            decided.add(file)
            self.fp.event_dirs[file] = folder
            if (name := os.path.basename(folder)) != default_name:
                self.fp.event_names[file] = name
        self.fp.pictures = [file for file in self.fp.pictures if file in decided]
        self.fp.videos = [file for file in self.fp.videos if file in decided]
        _LOGGER.info("%d files to sort from %s", len(decided), path)

    def run(self) -> None:
        """Classify pictures and videos."""

        if self.settings.review:
            output = write_review(self.settings, self.settings.review)
            _LOGGER.info("Review page written in %s", output)
            return

        if not self.fp.pictures and not self.fp.videos:
            _LOGGER.info("No pictures or videos found")
            return

        if self.settings.plan:
            self.write_plan(self.settings.plan)
            return
        if self.settings.apply:
            self.apply_decisions(self.settings.apply)

        _LOGGER.info(
            "##### Clean Android Google Photo trashed and pending pictures uploaded #####"
        )
        self.fp.delete_android_trash_files()

        if self.settings.events:
            self.organizer().organize()

        self.process_files("picture", self.fp.pictures, self.ip.process)
        self.process_files("video", self.fp.videos, self.vp.process)

        _LOGGER.info("")

    def process_files(
        self, kind: str, paths: list[str], process: Callable[[str], None]
    ) -> None:
        """Process files of a kind, logging errors without stopping."""
        if not paths:
            return

        _LOGGER.info("")
        _LOGGER.info("##### %ss #####", kind.capitalize())
        # Iterate on a copy, processing may update the file lists
        with (
            logging_redirect_tqdm(loggers=[_LOGGER]),
            tqdm(list(paths), desc=f"{kind.capitalize()}s", unit=kind) as progress,
        ):
            for path in progress:
                _LOGGER.debug(
                    "Process %s %s (%s GB)",
                    kind,
                    path,
                    round(os.path.getsize(path) / 1e9, 3),
                )

                try:
                    process(path)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.error("Error processing %s %s: %s", kind, path, exc)
