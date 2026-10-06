"""Test metadata module, writing the event names with exiftool."""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from classify import organizer
from tests.conftest import EXIFTOOL_PATH, ClassifyFactory, make_picture, write_config

needs_exiftool = pytest.mark.skipif(EXIFTOOL_PATH is None, reason="needs exiftool")


def read_tag(path: Path, tag: str) -> str:
    """Return a metadata tag of a file."""
    assert EXIFTOOL_PATH
    return subprocess.run(
        [EXIFTOOL_PATH, "-s3", f"-{tag}", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def events_input(
    input_dir: Path, config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Add a burst of pictures, named "Fête" without asking."""
    for index in range(15):
        make_picture(
            input_dir / f"party/IMG_{index}.jpg",
            datetime(2026, 3, 14, 10) + index * timedelta(minutes=10),
        )
    # The sample video is a recurring event too
    write_config(
        config_home,
        language="fr",
        recurring={"Vidéo": "08-07"},
        holiday_min_files=1,
    )
    # Events are asked in date order, the video first
    answers = iter(["", "Fête"])
    monkeypatch.setattr(organizer, "is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    return input_dir


@needs_exiftool
def test_event_written_in_copies(
    events_input: Path, make_classify: ClassifyFactory, output_dir: Path
) -> None:
    """Event names are written in the copies, the originals are untouched."""
    original = events_input / "party/IMG_0.jpg"
    original_content = original.read_bytes()
    assert EXIFTOOL_PATH

    make_classify(
        "--output",
        str(output_dir),
        "--keep-original",
        "--events",
        "--exiftool-path",
        EXIFTOOL_PATH,
    ).run()

    copy = output_dir / "2026/Fête/2026-03-14-10h00m00.jpg"
    assert read_tag(copy, "XMP-dc:Subject") == "Fête"
    assert read_tag(copy, "IPTC:Keywords") == "Fête"
    assert read_tag(copy, "XMP-iptcExt:Event") == "Fête"
    assert original.read_bytes() == original_content
    video = output_dir / "2015/Vidéo 2015/2015-08-07-09h13m02.mp4"
    assert read_tag(video, "XMP-dc:Subject") == "Vidéo 2015"
    # Files out of any event are not tagged
    assert not read_tag(output_dir / "2017/Divers/2017-11-11-15h18m17.jpg", "Subject")

    # The tagged copies are recognized, nothing is copied or encoded again
    files_after_first_run = sorted(output_dir.rglob("*"))
    make_classify(
        "--output",
        str(output_dir),
        "--keep-original",
        "--events",
        "--no-interactive",
        "--exiftool-path",
        EXIFTOOL_PATH,
    ).run()
    assert sorted(output_dir.rglob("*")) == files_after_first_run
    assert read_tag(copy, "XMP-dc:Subject") == "Fête"


def test_missing_exiftool(
    events_input: Path,
    make_classify: ClassifyFactory,
    output_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without exiftool, a single warning is logged and the files are sorted."""
    make_classify(
        "--output",
        str(output_dir),
        "--keep-original",
        "--events",
        "--exiftool-path",
        "/nonexistent/exiftool",
    ).run()

    assert caplog.text.count("/nonexistent/exiftool not found") == 1
    assert (output_dir / "2026/Fête/2026-03-14-10h00m00.jpg").exists()
