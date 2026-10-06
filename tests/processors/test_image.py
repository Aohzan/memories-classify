"""Test processor/image.py module."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from classify.classify import Classify
from classify.geo import Location
from tests.conftest import make_picture


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


def test_get_location(classify_dry_run: Classify, tmp_path: Path) -> None:
    """The GPS location and altitude of a picture are read from EXIF."""
    picture = make_picture(
        tmp_path / "gps.jpg", datetime(2025, 2, 10), Location(-45.5, -4.8333, 1800)
    )

    location = classify_dry_run.ip.get_location(str(picture))

    assert location is not None
    assert location.lat == pytest.approx(-45.5, abs=1e-4)
    assert location.lon == pytest.approx(-4.8333, abs=1e-4)
    assert location.altitude == pytest.approx(1800)


def test_get_location_without_gps(classify_dry_run: Classify, input_dir: Path) -> None:
    """Pictures without GPS have no location."""
    assert (
        classify_dry_run.ip.get_location(str(input_dir / "dir1/IMG_1001.jpg")) is None
    )
