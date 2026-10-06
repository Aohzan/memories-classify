"""Test processor/files.py module."""

import shutil
from pathlib import Path

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
