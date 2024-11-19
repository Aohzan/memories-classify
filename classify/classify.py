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

            self.ip.process(picture_path)

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

            self.vp.process(video_path)

            print_progress_bar(
                idx,
                len(self.fp.videos),
                prefix="Processed ",
                suffix=f"of total videos ({len(self.fp.videos)})",
                length=50,
            )

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
