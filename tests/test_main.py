"""Test main module."""

from pathlib import Path

import pytest

from classify.classify import Classify
from classify.const import DEFAULT_NAME_FORMAT
from classify.main import main
from tests.conftest import ClassifyFactory


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
    # Both samples are identical, make them differ to get a name conflict
    with (input_dir / "dir1/IMG_1002.jpg").open("ab") as picture:
        picture.write(b"\0")
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


def test_run_dry_run(
    classify_dry_run: Classify, input_dir: Path, output_dir: Path
) -> None:
    """Dry run does not touch the file system."""
    files_before = sorted(input_dir.rglob("*"))

    classify_dry_run.run()

    assert sorted(input_dir.rglob("*")) == files_before
    assert not output_dir.exists()


def test_comment_message(make_classify: ClassifyFactory) -> None:
    """The comment message option is applied to the settings."""
    classify = make_classify("--dry-run", "--comment-message", "Custom comment")

    assert classify.settings.comment_message == "Custom comment"


@pytest.mark.parametrize(
    "extra_args",
    [
        ["--ffmpeg-path", "/nonexistent/ffmpeg"],
        ["--ffprobe-path", "/nonexistent/ffprobe"],
        ["--timezone", "Invalid/Timezone"],
    ],
)
def test_main_exits_on_invalid_setup(input_dir: Path, extra_args: list[str]) -> None:
    """Main exits cleanly on a missing tool or an invalid timezone."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--directory", str(input_dir), "--dry-run", *extra_args])

    assert exc_info.value.code == 1


def test_run_twice_with_copy(classify_copy: Classify, output_dir: Path) -> None:
    """A second run does not copy or encode the files again."""
    classify_copy.run()
    files_after_first_run = sorted(output_dir.rglob("*"))

    classify_copy.run()

    assert sorted(output_dir.rglob("*")) == files_after_first_run
