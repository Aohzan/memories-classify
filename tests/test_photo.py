import logging
from datetime import datetime

from classify.processors.image import ImageProcessor

from .common import tests_classify_settings

_LOGGER = logging.getLogger("classify")

photo_processor = ImageProcessor(tests_classify_settings())


def test_get_date_taken_from_photo():
    """Test get_date_taken_from_photo."""
    date_taken = photo_processor.get_date_taken("tests/photos/dir1/IMG_1001.jpg")
    assert date_taken == datetime(2017, 11, 11, 15, 18, 17)  # 2017-11-11-15h18m17.jpg

    date_taken_2 = photo_processor.get_date_taken("tests/photos/dir2/IMG_2201.jpg")
    assert date_taken_2 == datetime(2020, 2, 24, 12, 29, 52)  # 2020-02-24-12h29m52.jpg


def test_rename_photo_from_date_taken(caplog):
    """Test rename_photo_from_date_taken."""
    with caplog.at_level(logging.DEBUG):
        photo_processor.rename_from_date_taken("tests/photos/dir1/IMG_1001.jpg")
        assert "Rename picture IMG_1001.jpg to 2017-11-11-15h18m17.jpg" in caplog.text

        photo_processor.rename_from_date_taken("tests/photos/dir2/IMG_2201.jpg")
        assert "Rename picture IMG_2201.jpg to 2020-02-24-12h29m52.jpg" in caplog.text
