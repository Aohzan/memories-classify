"""Test processor/video.py module."""

import logging
from datetime import datetime

from classify.classify import Classify


_LOGGER = logging.getLogger("classify")


def test_get_date_taken(test_classify_dry_run: Classify):
    date_taken = test_classify_dry_run.vp.get_date_taken("tests/photos/dir1/video.mp4")
    assert date_taken == datetime(2024, 11, 2, 14, 21, 46, 963817)


def test_get_location(test_classify_dry_run: Classify):
    assert test_classify_dry_run.vp.get_location("tests/photos/dir1/video.mp4") is None

    # TODO real video with metadata
