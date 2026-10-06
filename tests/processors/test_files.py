"""Test processor/files.py module."""

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from classify.classify import Classify
from tests.conftest import ClassifyFactory


def test_delete_android_trash_files(
    make_classify: ClassifyFactory, input_dir: Path, output_dir: Path
) -> None:
    """Trash files are deleted and not processed, even with an output directory."""
    trashed = input_dir / "dir1/.trashed-1700000000-IMG_1003.jpg"
    shutil.copy(input_dir / "dir1/IMG_1001.jpg", trashed)

    classify = make_classify("--output", str(output_dir))
    assert str(trashed) in classify.fp.pictures

    classify.fp.delete_android_trash_files()

    assert not trashed.exists()
    assert str(trashed) not in classify.fp.pictures
    assert len(classify.fp.pictures) == 3


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("2015-08-07-09h13m02.mp4", True),
        ("2015-08-07-09h13m02b.mp4", True),
        ("2015-08-07-09h13m02-1.mp4", False),
        ("PXL_20241010_174118780.TS.mp4", False),
    ],
)
def test_is_date_named(
    classify_dry_run: Classify, file_name: str, expected: bool
) -> None:
    """Date named files are detected, with or without a duplicate suffix."""
    assert classify_dry_run.fp.is_date_named(file_name) is expected


def test_get_available_filepath_from_date(
    classify_dry_run: Classify, tmp_path: Path
) -> None:
    """A letter is appended on conflicts, except for the source file itself."""
    date_taken = datetime(2015, 8, 7, 9, 13, 2)
    taken = tmp_path / "2015-08-07-09h13m02.mp4"
    taken.touch()

    get_path = classify_dry_run.fp.get_available_filepath_from_date
    assert get_path(str(tmp_path), date_taken, ".mp4") == str(
        tmp_path / "2015-08-07-09h13m02a.mp4"
    )
    assert get_path(str(tmp_path), date_taken, ".mp4", source_file=str(taken)) == str(
        taken
    )


def test_output_inside_input_is_skipped(
    make_classify: ClassifyFactory, input_dir: Path
) -> None:
    """Files already in an output directory inside the input are not listed."""
    output = input_dir / "sorted"
    output.mkdir()
    shutil.copy(input_dir / "dir1/IMG_1001.jpg", output / "2017-11-11-15h18m17.jpg")

    classify = make_classify("--output", str(output), "--dry-run")

    assert not any(path.startswith(str(output)) for path in classify.fp.pictures)


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        # Pixel names hold the UTC time
        ("PXL_20261006_083232945.jpg", datetime(2026, 10, 6, 10, 32, 32, 945000)),
        ("20260925_060641_oc7uf85qyhg.jpg", datetime(2026, 9, 25, 6, 6, 41)),
        ("20260925_060641.mp4", datetime(2026, 9, 25, 6, 6, 41)),
        ("010.IMG20260910101833.jpg", datetime(2026, 9, 10, 10, 18, 33)),
        ("img-20260924-wa0004_t79jwq3m4nj.jpg", datetime(2026, 9, 24, 12)),
        ("VID-20260924-WA0001.mp4", datetime(2026, 9, 24, 12)),
        ("IMG_1001.jpg", None),
        ("99999999_999999.jpg", None),
    ],
)
def test_get_date_from_file_name(
    make_classify: ClassifyFactory, file_name: str, expected: datetime | None
) -> None:
    """Dates are read from phone file names, in local time unless UTC."""
    paris = ZoneInfo("Europe/Paris")
    classify = make_classify("--timezone", "Europe/Paris", "--dry-run")

    date_taken = classify.fp.get_date_from_file_name(file_name)

    assert date_taken == (expected.replace(tzinfo=paris) if expected else None)
