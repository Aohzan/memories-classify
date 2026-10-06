"""Test main module."""

from pathlib import Path

from classify.classify import Classify
from classify.const import DEFAULT_NAME_FORMAT


def test_settings(classify_copy: Classify, input_dir: Path, output_dir: Path) -> None:
    """Test settings."""
    settings = classify_copy.settings

    assert settings.directory == str(input_dir)
    assert settings.output == str(output_dir)
    assert settings.keep_original is True
    assert settings.dry_run is False
    assert settings.verbose is False
    assert settings.name_format == DEFAULT_NAME_FORMAT


def test_run(classify_copy: Classify, input_dir: Path, output_dir: Path) -> None:
    """Test complete run."""
    classify_copy.run()

    # original files still exist (keep_original=True)
    assert (input_dir / "dir1/IMG_1001.jpg").exists()
    assert (input_dir / "dir1/IMG_1002.jpg").exists()
    assert (input_dir / "dir1/video.mp4").exists()
    assert (input_dir / "dir2/IMG_2201.jpg").exists()
    # classified files in output directory
    assert (output_dir / "dir1/2017-11-11-15h18m17.jpg").exists()
    assert (output_dir / "dir1/2017-11-11-15h18m17a.jpg").exists()
    assert (output_dir / "dir2/2020-02-24-12h29m52.jpg").exists()
    assert (output_dir / "dir1/2015-08-07-09h13m02.mp4").exists()
    # check exclude
    assert not (output_dir / "custom").exists()
    # check if video has been reencoded and is playable
    encoded_video = str(output_dir / "dir1/2015-08-07-09h13m02.mp4")
    assert classify_copy.vp.test(encoded_video)
    assert classify_copy.vp.is_already_reencoded(encoded_video)
