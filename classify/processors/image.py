"""Image processor."""

import logging
import math
import os
from datetime import datetime
from typing import Any

from PIL import Image
from PIL.ExifTags import GPS, IFD
from PIL.ExifTags import Base as ExifBase

from ..geo import Location
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
        """Get the date taken from the exif or the file name of a picture"""
        if date_taken := self.get_exif_date_taken(path):
            return date_taken
        return self.fp.get_date_from_file_name(path)

    def get_exif_date_taken(self, path: str) -> datetime | None:
        """Get the date taken from the exif of a picture"""
        with Image.open(path) as img:
            exif = img.getexif()
        if not exif:
            return None

        date_taken = None

        # First check EXIF IFD for DateTimeOriginal
        try:
            exif_ifd = exif.get_ifd(0x8769)
            if int(ExifBase.DateTimeOriginal) in exif_ifd:
                date_taken = exif_ifd[int(ExifBase.DateTimeOriginal)]
        except Exception:
            _LOGGER.debug("Cannot read EXIF IFD of %s", path, exc_info=True)

        # Fallback to main EXIF for DateTime
        if not date_taken and int(ExifBase.DateTime) in exif:
            date_taken = exif[int(ExifBase.DateTime)]

        if not date_taken:
            return None

        try:
            return datetime.strptime(date_taken, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            _LOGGER.warning("Invalid EXIF date %s in %s", date_taken, path)
            return None

    def get_location(self, path: str) -> Location | None:
        """Get the GPS location of a picture, with its altitude if any."""
        with Image.open(path) as img:
            exif = img.getexif()
        try:
            gps = exif.get_ifd(IFD.GPSInfo)
        except Exception:
            _LOGGER.debug("Cannot read GPS IFD of %s", path, exc_info=True)
            return None

        latitude = dms_to_degrees(gps.get(GPS.GPSLatitude), gps.get(GPS.GPSLatitudeRef))
        longitude = dms_to_degrees(
            gps.get(GPS.GPSLongitude), gps.get(GPS.GPSLongitudeRef)
        )
        # Cameras without GPS fix may write a null location
        if latitude is None or longitude is None or latitude == longitude == 0:
            return None

        altitude = None
        if (raw_altitude := gps.get(GPS.GPSAltitude)) is not None:
            altitude = float(raw_altitude)
            # Reference 1 is below sea level
            if gps.get(GPS.GPSAltitudeRef) in (1, b"\x01"):
                altitude = -altitude
            if math.isnan(altitude):
                altitude = None
        return Location(latitude, longitude, altitude)

    def rename_from_date_taken(self, path: str) -> None:
        """Rename a picture from date taken"""
        picture_date_taken = self.get_date_taken(path)
        if not picture_date_taken:
            _LOGGER.warning("Cannot get date from picture %s", path)
            return

        _LOGGER.debug(
            "Picture %s taken on %s", os.path.basename(path), picture_date_taken
        )
        extension = os.path.splitext(path)[1].lower()
        if extension == ".jpeg":
            extension = ".jpg"
        self.fp.place_in_output(path, picture_date_taken, extension)

    def process(self, path: str) -> None:
        """Process a picture"""
        self.rename_from_date_taken(path)


def dms_to_degrees(dms: Any, reference: Any) -> float | None:
    """Convert EXIF degrees, minutes and seconds to signed decimal degrees."""
    try:
        degrees, minutes, seconds = (float(value) for value in dms)
    except TypeError, ValueError:
        return None
    value = degrees + minutes / 60 + seconds / 3600
    if math.isnan(value):
        return None
    if reference in ("S", "W", b"S", b"W"):
        value = -value
    return value
