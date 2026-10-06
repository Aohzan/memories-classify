"""Main function to classify pictures and videos."""

import logging
import os
from collections.abc import Callable

from classify.logger import print_progress_bar

from .processors.files import FileProcessor
from .processors.image import ImageProcessor
from .processors.video import VideoProcessor
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

    def run(self) -> None:
        """Classify pictures and videos."""

        if not self.fp.pictures and not self.fp.videos:
            _LOGGER.info("No pictures or videos found")
            return

        _LOGGER.info(
            "##### Clean Android Google Photo trashed and pending pictures uploaded #####"
        )
        self.fp.delete_android_trash_files()

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
        total = len(paths)
        progress_suffix = f"of total {kind}s ({total})"
        print_progress_bar(0, total, prefix="Processed ", suffix=progress_suffix)
        # Iterate on a copy, processing may update the file lists
        for idx, path in enumerate(list(paths)):
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

            print_progress_bar(
                idx + 1, total, prefix="Processed ", suffix=progress_suffix
            )
