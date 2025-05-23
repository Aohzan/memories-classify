"""Test processor/video.py module."""

import logging
from datetime import datetime

from classify.classify import Classify

_LOGGER = logging.getLogger("classify")


def test_get_location(test_classify_dry_run: Classify) -> None:
    """Test get_location method."""
    assert test_classify_dry_run.vp.get_location("tests/photos/dir1/video.mp4") is None


def test_get_metadata(test_classify_dry_run: Classify) -> None:
    """Test get_metadata method."""
    metadata = test_classify_dry_run.vp.get_metadata(
        "tests/photos/dir1/video.mp4", "creation_time"
    )
    assert metadata == "2015-08-07T09:13:02.000000Z"


def test_get_date_taken(test_classify_dry_run: Classify) -> None:
    """Test get_date_taken method."""
    date_taken = test_classify_dry_run.vp.get_date_taken("tests/photos/dir1/video.mp4")
    assert date_taken == datetime(2015, 8, 7, 9, 13, 2)
