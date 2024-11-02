"""Photo related functions."""

import logging
import os
from datetime import datetime

from PIL import Image
from PIL.ExifTags import Base as ExifBase

from .files import get_filepath_from_date

_LOGGER = logging.getLogger("classify")


def get_date_taken_from_photo(path: str) -> datetime | None:
    """Get the date taken from the exif of a picture."""
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


def rename_photo_from_date_taken(
    path: str, name_format: str, dry_run: bool = False
) -> None:
    """Rename a picture."""
    picture_file_name = os.path.basename(path)
    picture_date_taken = get_date_taken_from_photo(path)

    if picture_date_taken:
        _LOGGER.debug("\tPicture %s taken on %s", picture_file_name, picture_date_taken)
        new_picture_path = get_filepath_from_date(path, picture_date_taken, name_format)
        if new_picture_path != path:
            _LOGGER.info(
                "\tRename picture %s to %s",
                picture_file_name,
                os.path.basename(new_picture_path),
            )
            if not dry_run:
                os.rename(path, new_picture_path)
        else:
            _LOGGER.debug("\tAlready named correctly")

    else:
        _LOGGER.warning("\tCannot get date from picture %s", path)
