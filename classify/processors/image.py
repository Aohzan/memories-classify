"""Image processor."""

import logging
import os
from datetime import datetime

from shutil import copyfile
from PIL import Image
from PIL.ExifTags import Base as ExifBase

from ..settings import ClassifySettings
from .files import FileProcessor

_LOGGER = logging.getLogger("classify")


class ImageProcessor:
    """Image processor class"""

    def __init__(
        self, settings: ClassifySettings, file_processor: FileProcessor
    ) -> None:
        """Initialize the class"""
        self.settings = settings
        self.fp = file_processor

    def get_date_taken(self, path: str) -> datetime | None:
        """Get the date taken from the exif of a picture"""
        with Image.open(path) as img:
            exif = img._getexif()  # pylint: disable=protected-access
        if not exif:
            return None
        if int(ExifBase.DateTimeOriginal) in exif:
            date_taken = exif[int(ExifBase.DateTimeOriginal)]
        elif int(ExifBase.DateTime) in exif:
            date_taken = exif[int(ExifBase.DateTime)]
        else:
            return None

        return datetime.strptime(date_taken, "%Y:%m:%d %H:%M:%S")

    def rename_from_date_taken(self, path: str) -> None:
        """Rename a picture from date taken"""
        picture_file_name = os.path.basename(path)
        picture_date_taken = self.get_date_taken(path)
        if picture_date_taken:
            _LOGGER.debug(
                "\tPicture %s taken on %s", picture_file_name, picture_date_taken
            )
            dest_dir_path = self.fp.get_output_path(path)
            new_picture_path = self.fp.get_available_filepath_from_date(
                source_file=path,
                dest_dir=dest_dir_path,
                date_taken=picture_date_taken,
            )
            if new_picture_path != path:
                os.makedirs(dest_dir_path, exist_ok=True)
                if self.settings.keep_original:
                    _LOGGER.info(
                        "\tCopy picture %s to %s",
                        path,
                        new_picture_path,
                    )
                    if not self.settings.dry_run:
                        copyfile(path, new_picture_path)
                else:
                    _LOGGER.info(
                        "\tRename picture %s to %s",
                        path,
                        new_picture_path,
                    )
                    if not self.settings.dry_run:
                        os.rename(path, new_picture_path)
            else:
                _LOGGER.debug("\tAlready named correctly")

        else:
            _LOGGER.warning("\tCannot get date from picture %s", path)

    def process(self, path: str) -> None:
        """Process a picture"""
        self.rename_from_date_taken(path)
