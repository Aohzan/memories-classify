"""Test processor/files.py module."""

import shutil
from datetime import datetime
from pathlib import Path

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
