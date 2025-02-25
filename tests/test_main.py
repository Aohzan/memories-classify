"""Test main module."""

import os

from classify.classify import Classify
from classify.const import DEFAULT_NAME_FORMAT

from .conftest import INPUT_DIR, OUTPUT_DIR


def test_settings(test_classify: Classify) -> None:
    """Test settings."""
    settings = test_classify.settings

    assert settings.directory == INPUT_DIR
    assert settings.output == OUTPUT_DIR
    assert settings.keep_original is True
    assert settings.dry_run is False
    assert settings.verbose is False
    assert settings.name_format == DEFAULT_NAME_FORMAT


def test_run(test_classify: Classify) -> None:
    """Test complete run."""
    test_classify.run()

    # original files steel exist (keep_original=True)
    assert os.path.exists("tests/photos/dir1/IMG_1001.jpg")
    assert os.path.exists("tests/photos/dir1/IMG_1002.jpg")
    assert os.path.exists("tests/photos/dir1/video.mp4")
    assert os.path.exists("tests/photos/dir2/IMG_2201.jpg")
    # classified files in output directory
    assert os.path.exists("tests/output/dir1/2017-11-11-15h18m17.jpg")
    assert os.path.exists("tests/output/dir1/2017-11-11-15h18m17a.jpg")
    assert os.path.exists("tests/output/dir2/2020-02-24-12h29m52.jpg")
    assert os.path.exists("tests/output/dir1/2015-08-07-09h13m02.mp4")
    # check if video has been reencoded and is playable
    assert test_classify.vp.test("tests/output/dir1/2015-08-07-09h13m02.mp4")
    assert test_classify.vp.is_already_reencoded(
        "tests/output/dir1/2015-08-07-09h13m02.mp4"
    )
