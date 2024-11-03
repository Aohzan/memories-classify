"""Main function to classify pictures and videos."""

import logging
import os

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
        self.ip = ImageProcessor(settings=settings)
        self.vp = VideoProcessor(settings=settings)

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
        _LOGGER.info("Rename pictures according to date taken")
        picture_count = 1
        for picture_path in self.fp.pictures:
            _LOGGER.debug(
                "[%s%%] Process picture %s",
                int(picture_count * 100 / len(self.fp.pictures)),
                picture_path,
            )

            self.ip.process(picture_path)

            picture_count += 1

        _LOGGER.info("")
        _LOGGER.info("##### Videos #####")
        _LOGGER.info("Encode videos to HEVC with a preset to reduce file size")
        video_count = 1
        for video_path in self.fp.videos:
            _LOGGER.debug(
                "[%s%%] Process video %s (%s GB)",
                int(video_count * 100 / len(self.fp.videos)),
                video_path,
                round(os.path.getsize(video_path) / 1e9, 3),
            )

            self.vp.process(video_path)

            video_count += 1

        # TODO creation data not working
        # _LOGGER.info("")
        # _LOGGER.info("##### Files date adjustment #####")
        # for file_path in files.pictures + files.videos:
        #         file_extension = os.path.splitext(file)[1].lower()
        #         if file_extension in (PICTURE_EXTENSIONS + VIDEO_EXTENSIONS):
        #             if filename_date := get_date_from_file_name(file, args.name_format):
        #                 file_path = os.path.join(root, file)
        #                 _LOGGER.debug(filename_date)
        #                 _LOGGER.debug(datetime.fromtimestamp(os.path.getctime(file_path)))
        #                 _LOGGER.debug(datetime.fromtimestamp(os.path.getmtime(file_path)))
        #                 if filename_date.timestamp() != os.path.getctime(
        #                     file_path
        #                 ) or filename_date.timestamp() != os.path.getmtime(file_path):
        #                     # os.utime(
        #                     #     file_path, (filename_date.timestamp(), filename_date.timestamp())
        #                     # )
        #                     filedate_file = filedate.File(file_path)
        #                     filedate_file.created = filename_date
        #                     filedate_file.modified = filename_date
        #                     filedate_file.accessed = filename_date.strftime(
        #                         "%d.%m.%Y %H:%M"
        #                     )
        #                     _LOGGER.info(
        #                         "File date of %s updated to %s",
        #                         file,
        #                         filename_date,
        #                     )

        _LOGGER.info("")
