"""Test processor/video.py module."""

from datetime import UTC, datetime
from pathlib import Path

from classify.classify import Classify


def test_get_location(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_location method."""
    assert classify_dry_run.vp.get_location(str(input_dir / "dir1/video.mp4")) is None


def test_get_metadata(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_metadata method."""
    metadata = classify_dry_run.vp.get_metadata(
        str(input_dir / "dir1/video.mp4"), "creation_time"
    )
    assert metadata == "2015-08-07T09:13:02.000000Z"


def test_get_date_taken(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_date_taken method."""
    date_taken = classify_dry_run.vp.get_date_taken(str(input_dir / "dir1/video.mp4"))
    assert date_taken == datetime(2015, 8, 7, 9, 13, 2, tzinfo=UTC)
