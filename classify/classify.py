"""Main function to classify pictures and videos."""

import logging
import os

from classify.exception import ClassifyEncodingException

from .processors.files import FileProcessor
from .processors.photo import PhotoProcessor
from .settings import ClassifySettings
from .processors.video import (
    VideoProcessor,
)

_LOGGER = logging.getLogger("classify")

classify_settings: ClassifySettings


class Classify:
    """Classify global class."""

    def __init__(self, settings: ClassifySettings):
        """Initialize the class."""
        self.settings = settings
        self.files = FileProcessor(settings=settings)
        self.photo = PhotoProcessor(settings=settings)
        self.video = VideoProcessor(settings=settings)

    def run(self) -> None:
        """Classify pictures and videos."""

        if not self.files.pictures and not self.files.videos:
            return

        _LOGGER.info(
            "##### Clean Android Google Photo trashed and pending pictures uploaded #####"
        )
        self.files.delete_android_trash_files()

        _LOGGER.info("")
        _LOGGER.info("##### Pictures #####")
        _LOGGER.info("Rename pictures according to date taken")
        picture_count = 1
        for picture_path in self.files.pictures:
            _LOGGER.info(
                "[%s%%] Process picture %s",
                int(picture_count * 100 / len(self.files.pictures)),
                picture_path,
            )
            self.photo.rename_photo_from_date_taken(
                path=picture_path,
            )

            picture_count += 1

        _LOGGER.info("")
        _LOGGER.info("##### Videos #####")
        _LOGGER.info("Encode videos to HEVC with a preset to reduce file size")
        video_count = 1
        for video_path in self.files.videos:
            video_file_name = os.path.basename(video_path)
            _LOGGER.info(
                "[%s%%] Process video %s (%s GB)",
                int(video_count * 100 / len(self.files.videos)),
                video_file_name,
                round(os.path.getsize(video_path) / 1e9, 3),
            )
            video_count += 1

            # check if video has already been encoded
            if self.video.check_video_already_encoded(video_path):
                _LOGGER.debug("\tVideo already encoded")
                continue

            # get date taken from video
            video_date_taken = self.video.get_date_taken_from_video(video_path)
            _LOGGER.debug("\tVideo %s taken on %s", video_file_name, video_date_taken)
            encoded_file_name = (
                f"{video_date_taken.strftime(self.settings.name_format)}.mp4"
            )
            encoded_file_path = os.path.join(
                os.path.dirname(video_path), encoded_file_name
            )

            if os.path.exists(encoded_file_path):
                _LOGGER.warning("\tDelete existing target file %s", encoded_file_path)
                self.files.remove_file(encoded_file_path)

            # encode file
            _LOGGER.info(
                "\tEncoding video %s to %s", video_file_name, encoded_file_name
            )
            try:
                self.video.encode_video(
                    input_path=video_path, output_path=encoded_file_path
                )
            except ClassifyEncodingException as e:
                _LOGGER.error("\tError while encoding video: %s", e)
                continue

            self.video.choose_between_original_and_encoded(
                video_path=video_path,
                encoded_file_path=encoded_file_path,
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
