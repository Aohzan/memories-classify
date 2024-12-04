"""Main function to classify pictures and videos."""

import logging
import os

from classify.logger import print_progress_bar

from .processors.files import FileProcessor
from .processors.image import ImageProcessor
from .processors.video import VideoProcessor
from .settings import ClassifySettings

_LOGGER = logging.getLogger("classify")

classify_settings: ClassifySettings


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

        _LOGGER.info("")
        _LOGGER.info("##### Pictures #####")
        print_progress_bar(
            0,
            len(self.fp.pictures),
            prefix="Processed ",
            suffix=f"of total pictures ({len(self.fp.pictures)})",
            length=50,
        )
        for idx, picture_path in enumerate(self.fp.pictures):
            _LOGGER.debug(
                "Process picture %s",
                picture_path,
            )

            try:
                self.ip.process(picture_path)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Error processing picture %s: %s", picture_path, exc)

            print_progress_bar(
                idx + 1,
                len(self.fp.pictures),
                prefix="Processed ",
                suffix=f"of total pictures ({len(self.fp.pictures)})",
                length=50,
            )

        _LOGGER.info("")
        _LOGGER.info("##### Videos #####")
        print_progress_bar(
            0,
            len(self.fp.videos),
            prefix="Processed ",
            suffix=f"of total videos ({len(self.fp.videos)})",
            length=50,
        )
        for idx, video_path in enumerate(self.fp.videos):
            _LOGGER.debug(
                "Process video %s (%s GB)",
                video_path,
                round(os.path.getsize(video_path) / 1e9, 3),
            )

            try:
                self.vp.process(video_path)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Error processing video %s: %s", video_path, exc)

            print_progress_bar(
                idx,
                len(self.fp.videos),
                prefix="Processed ",
                suffix=f"of total videos ({len(self.fp.videos)})",
                length=50,
            )

        _LOGGER.info("")
