"""Test processor/image.py module."""

from datetime import datetime
from pathlib import Path

from classify.classify import Classify


def test_get_date_taken(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_date_taken_from_photo."""
    date_taken = classify_dry_run.ip.get_date_taken(
        str(input_dir / "dir1/IMG_1001.jpg")
    )
    assert date_taken == datetime(2017, 11, 11, 15, 18, 17)  # 2017-11-11-15h18m17.jpg

    date_taken_2 = classify_dry_run.ip.get_date_taken(
        str(input_dir / "dir2/IMG_2201.jpg")
    )
    assert date_taken_2 == datetime(2020, 2, 24, 12, 29, 52)  # 2020-02-24-12h29m52.jpg
