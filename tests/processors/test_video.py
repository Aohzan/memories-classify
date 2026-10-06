"""Test processor/video.py module."""

import logging
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from classify.classify import Classify
from classify.geo import Location
from tests.conftest import ClassifyFactory


def test_get_location(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_location method."""
    assert classify_dry_run.vp.get_location(str(input_dir / "dir1/video.mp4")) is None


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ("+45.7640+004.8357/", Location(45.764, 4.8357)),
        ("+45.7640+004.8357+250.000/", Location(45.764, 4.8357, 250)),
        ("\n+43.4832-001.5586+010.000/", Location(43.4832, -1.5586, 10)),
        ("", None),
    ],
)
def test_get_location_iso6709(
    classify_dry_run: Classify,
    monkeypatch: pytest.MonkeyPatch,
    tags: str,
    expected: Location | None,
) -> None:
    """Android and Apple ISO 6709 locations are parsed, with their altitude."""
    monkeypatch.setattr(classify_dry_run.vp, "_run_ffprobe", lambda _args: tags)

    assert classify_dry_run.vp.get_location("video.mp4") == expected


def test_get_location_from_metadata(
    classify_dry_run: Classify, input_dir: Path, tmp_path: Path
) -> None:
    """The location tag written by phones is read with ffprobe."""
    video = tmp_path / "location.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(input_dir / "dir1/video.mp4"),
            "-t",
            "1",
            "-c",
            "copy",
            "-metadata",
            "location=+45.7640+004.8357/",
            str(video),
        ],
        check=True,
    )

    assert classify_dry_run.vp.get_location(str(video)) == Location(45.764, 4.8357)


def test_get_metadata(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_metadata method."""
    metadata = classify_dry_run.vp.get_metadata(
        str(input_dir / "dir1/video.mp4"), "creation_time"
    )
    assert metadata == "2015-08-07T09:13:02.000000Z"


def test_get_date_taken(classify_dry_run: Classify, input_dir: Path) -> None:
    """Test get_date_taken method."""
    date_taken = classify_dry_run.vp.get_date_taken(str(input_dir / "dir1/video.mp4"))
    assert date_taken == datetime(2015, 8, 7, 9, 13, 2, tzinfo=UTC)


def test_encode_special_characters(
    classify_copy: Classify,
    input_dir: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File names are passed to ffmpeg as is, without a shell."""
    monkeypatch.chdir(input_dir)
    video = input_dir / "dir1" / 'it\'s "a" $(touch pwned) `id`.mp4'
    (input_dir / "dir1/video.mp4").rename(video)

    classify_copy.vp.encode(
        input_path=str(video),
        output_path=str(output_dir / "encoded.mp4"),
        recorded_date=datetime(2015, 8, 7, 9, 13, 2),
    )

    assert (output_dir / "encoded.mp4").exists()
    assert not (input_dir / "pwned").exists()


def test_encode_extra_args_position(
    make_classify: ClassifyFactory,
    input_dir: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Input extra args are set before the input, output ones before the output."""
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    classify = make_classify(
        "--output",
        str(output_dir),
        "--ffmpeg-input-extra-args=-hwaccel auto",
        "--ffmpeg-output-extra-args=-tag:v hvc1",
    )
    output = str(output_dir / "encoded.mp4")
    classify.vp.encode(
        input_path=str(input_dir / "dir1/video.mp4"),
        output_path=output,
        recorded_date=datetime(2015, 8, 7, 9, 13, 2),
    )

    command = commands[0]
    assert command.index("-hwaccel") < command.index("-i")
    assert command.index("-tag:v") < command.index(output)
    assert command[-1] == output


def test_encode_failure_removes_partial_file(
    make_classify: ClassifyFactory, input_dir: Path
) -> None:
    """A failed encoding leaves neither a partial file nor deletes the original."""
    classify = make_classify("--ffmpeg-output-extra-args=-c:v unknown_encoder")
    video = input_dir / "dir1/video.mp4"

    classify.vp.process(str(video))

    assert video.exists()
    assert not (input_dir / "dir1/2015-08-07-09h13m02.mp4").exists()


def test_keep_original_container_when_not_smaller(
    make_classify: ClassifyFactory, input_dir: Path, output_dir: Path
) -> None:
    """The original keeps its extension when the encoded file is not smaller."""
    classify = make_classify("--output", str(output_dir))
    original = input_dir / "dir1/video.mov"
    (input_dir / "dir1/video.mp4").rename(original)
    encoded = output_dir / "dir1/2015-08-07-09h13m02.mp4"
    encoded.parent.mkdir(parents=True)
    shutil.copy(original, encoded)

    classify.vp.choose_between_original_and_reencoded(
        video_path=str(original),
        encoded_file_path=str(encoded),
        recorded_date=datetime(2015, 8, 7, 9, 13, 2),
    )

    assert not original.exists()
    assert not encoded.exists()
    assert (output_dir / "dir1/2015-08-07-09h13m02.mov").exists()


@pytest.mark.parametrize(
    ("creation_time", "expected"),
    [
        ("2015-08-07T09:13:02Z", datetime(2015, 8, 7, 9, 13, 2, tzinfo=UTC)),
        ("2015-08-07 09:13:02", datetime(2015, 8, 7, 9, 13, 2, tzinfo=UTC)),
        (
            "2015-08-07T09:13:02.000000Z;2015-08-07T09:13:02.000000Z",
            datetime(2015, 8, 7, 9, 13, 2, tzinfo=UTC),
        ),
        # placeholder dates fall back to the file name
        (
            "1904-01-01T00:00:00.000000Z",
            datetime(2024, 10, 10, 17, 41, 18, 780000, UTC),
        ),
        ("invalid", datetime(2024, 10, 10, 17, 41, 18, 780000, UTC)),
    ],
)
def test_get_date_taken_from_creation_time(
    classify_dry_run: Classify,
    monkeypatch: pytest.MonkeyPatch,
    creation_time: str,
    expected: datetime,
) -> None:
    """Creation time metadata is parsed, invalid values are ignored."""
    monkeypatch.setattr(
        classify_dry_run.vp, "get_metadata", lambda _path, _name: creation_time
    )

    assert (
        classify_dry_run.vp.get_date_taken("/20250101/PXL_20241010_174118780.mp4")
        == expected
    )


def test_encode_keeps_creation_time_in_utc(
    make_classify: ClassifyFactory, input_dir: Path, output_dir: Path
) -> None:
    """The creation time does not depend on the system or user timezone."""
    classify = make_classify(
        "--output", str(output_dir), "--keep-original", "--timezone", "Asia/Tokyo"
    )

    classify.vp.process(str(input_dir / "dir1/video.mp4"))

    encoded = output_dir / "dir1/2015-08-07-18h13m02.mp4"
    creation_times = classify.vp.get_metadata(str(encoded), "creation_time")
    assert set(creation_times.split(";")) == {"2015-08-07T09:13:02.000000Z"}
    assert (
        encoded.stat().st_mtime
        == datetime(2015, 8, 7, 9, 13, 2, tzinfo=UTC).timestamp()
    )


def test_already_encoded_video_placed_in_output(
    make_classify: ClassifyFactory, input_dir: Path, output_dir: Path
) -> None:
    """An already encoded video is moved to the output directory."""
    make_classify("--keep-original").vp.process(str(input_dir / "dir1/video.mp4"))
    encoded = input_dir / "dir1/2015-08-07-09h13m02.mp4"
    assert encoded.exists()

    make_classify("--output", str(output_dir)).vp.process(str(encoded))

    assert not encoded.exists()
    assert (output_dir / "dir1/2015-08-07-09h13m02.mp4").exists()


def make_shifted_video(input_dir: Path) -> Path:
    """Replace the sample by a video encoded by an old version.

    Old versions wrote the local time (11:13 in Paris) as UTC in the creation time.
    """
    sample = input_dir / "dir1/video.mp4"
    video = input_dir / "dir1/2015-08-07-11h13m02.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(sample),
            "-c",
            "copy",
            "-metadata",
            "creation_time=2015-08-07T11:13:02Z",
            "-metadata",
            "comment=Processed by memories-classify",
            str(video),
        ],
        check=True,
    )
    sample.unlink()
    return video


@pytest.mark.parametrize("keep_original", [False, True])
def test_shifted_creation_time(
    make_classify: ClassifyFactory,
    input_dir: Path,
    output_dir: Path,
    keep_original: bool,
) -> None:
    """Videos named by the tool keep their name, their creation time is fixed."""
    video = make_shifted_video(input_dir)
    args = ["--output", str(output_dir), "--timezone", "Europe/Paris"]
    classify = make_classify(*args, *(["--keep-original"] if keep_original else []))

    classify.run()

    moved = output_dir / "dir1/2015-08-07-11h13m02.mp4"
    assert moved.exists()
    creation_time = classify.vp.get_metadata(str(moved), "creation_time")
    if keep_original:
        # The original and its copy are left as is
        assert video.exists()
        assert creation_time == "2015-08-07T11:13:02.000000Z"
    else:
        assert set(creation_time.split(";")) == {"2015-08-07T09:13:02.000000Z"}
        assert classify.vp.is_already_reencoded(str(moved))
        assert classify.vp.test(str(moved))


def test_shifted_creation_time_dry_run(
    make_classify: ClassifyFactory,
    input_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dry run only reports the creation time to fix."""
    caplog.set_level(logging.INFO, logger="classify")
    video = make_shifted_video(input_dir)
    content = video.read_bytes()

    make_classify("--timezone", "Europe/Paris", "--dry-run").run()

    assert "Fix creation time" in caplog.text
    assert video.read_bytes() == content
