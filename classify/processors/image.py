"""Image processor."""

import logging
import os
from datetime import datetime

from PIL import Image
from PIL.ExifTags import Base as ExifBase

from ..settings import ClassifySettings
from .files import FileProcessor

_LOGGER = logging.getLogger("classify")


class ImageProcessor:
    """Image processor class"""

    def __init__(self, settings: ClassifySettings):
        """Initialize the class"""
        self.settings = settings
        self.file_processor = FileProcessor(settings=settings)

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
        """Rename a picture"""
        picture_file_name = os.path.basename(path)
        picture_date_taken = self.get_date_taken(path)

        if picture_date_taken:
            _LOGGER.debug(
                "\tPicture %s taken on %s", picture_file_name, picture_date_taken
            )
            new_picture_path = self.file_processor.get_filepath_from_date(
                path, picture_date_taken
            )
            if new_picture_path != path:
                _LOGGER.info(
                    "\tRename picture %s to %s",
                    picture_file_name,
                    os.path.basename(new_picture_path),
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
