"""Test processor/image.py module."""

from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

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


def test_get_date_taken_from_file_name(
    classify_dry_run: Classify, tmp_path: Path
) -> None:
    """Pictures without EXIF date fall back on the file name."""
    picture = tmp_path / "PXL_20241014_165237438.jpg"
    Image.new("RGB", (8, 8)).save(picture)

    assert classify_dry_run.ip.get_date_taken(str(picture)) == datetime(
        2024, 10, 14, 16, 52, 37, 438000, UTC
    )


def test_get_date_taken_without_date(
    classify_dry_run: Classify, tmp_path: Path
) -> None:
    """Pictures without any date are left untouched."""
    picture = tmp_path / "screenshot.jpg"
    Image.new("RGB", (8, 8)).save(picture)

    assert classify_dry_run.ip.get_date_taken(str(picture)) is None
