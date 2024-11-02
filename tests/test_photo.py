from datetime import datetime
from classify.photo import get_date_taken_from_photo, rename_photo_from_date_taken

import logging

_LOGGER = logging.getLogger("classify")


def test_get_date_taken_from_photo():
    date_taken = get_date_taken_from_photo("tests/photos/dir1/IMG_1001.jpg")
    assert date_taken == datetime(2017, 11, 11, 15, 18, 17)  # 2017-11-11-15h18m17.jpg

    date_taken_2 = get_date_taken_from_photo("tests/photos/dir2/IMG_2201.jpg")
    assert date_taken_2 == datetime(2020, 2, 24, 12, 29, 52)  # 2020-02-24-12h29m52.jpg


def test_rename_photo_from_date_taken(caplog):
    with caplog.at_level(logging.DEBUG):

        rename_photo_from_date_taken(
            "tests/photos/dir1/IMG_1001.jpg", "%Y-%m-%d-%Hh%Mm%S.jpg", dry_run=True
        )
        assert "Rename picture IMG_1001.jpg to 2017-11-11-15h18m17.jpg" in caplog.text

        rename_photo_from_date_taken(
            "tests/photos/dir2/IMG_2201.jpg", "%Y-%m-%d-%Hh%Mm%S.jpg", dry_run=True
        )
        assert "Rename picture IMG_2201.jpg to 2020-02-24-12h29m52.jpg" in caplog.text
