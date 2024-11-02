"""Video related functions."""

import logging
import os
import re
import subprocess
from datetime import datetime, timezone

_LOGGER = logging.getLogger("classify")


def get_date_taken_from_video(path: str) -> datetime:
    """Get the date taken from the exif of a video."""
    if date_match := re.search(r"(\d{8}_\d{9})", path):
        date_str = date_match.group(0)
        date_src = datetime.strptime(date_str, "%Y%m%d_%H%M%S%f").replace(
            tzinfo=timezone.utc
        )
        local_time = date_src.astimezone()
        return local_time
    return datetime.fromtimestamp(os.path.getctime(path))


def get_video_bitrate(path: str) -> int:
    """Get the bitrate of a video."""
    command = os.popen(
        " ".join(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=bit_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                f'"{path}"',
            ]
        )
    )
    bitrate = command.read().strip()
    return int(bitrate)


def get_video_codec(path: str) -> str:
    """Get the codec of a video."""
    command = os.popen(
        " ".join(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                f'"{path}"',
            ]
        )
    )
    codec = command.read().strip()
    return codec


def check_video_already_encoded(path: str) -> bool:
    """Check if a video has already been encoded."""
    return (
        get_video_codec(path) == "hevc" and get_video_bitrate(path) <= 10 * 1000 * 1000
    )


def choose_between_original_and_encoded(
    video_path: str, encoded_file_path: str, dry_run: bool = False
) -> None:
    """Choose between the original and the encoded video."""
    original_size = os.path.getsize(video_path)

    if dry_run:
        encoded_size = original_size * 0.8  # fake encoded size
    elif not os.path.exists(encoded_file_path):
        _LOGGER.error(
            "\tEncoded file %s does not exist.",
            os.path.basename(encoded_file_path),
        )
        return
    else:
        encoded_size = os.path.getsize(encoded_file_path)

    size_ratio = encoded_size / original_size

    _LOGGER.info(
        "\tNew file space reduces by %s%% (%s GB)",
        round((1 - size_ratio) * 100),
        round(encoded_size / 1e9, 3),
    )

    if size_ratio > 0.90:
        if not dry_run:
            os.remove(encoded_file_path)
        _LOGGER.warning(
            "\tEncoding file %s deleted because space too close from original file.",
            os.path.basename(encoded_file_path),
        )

        if not dry_run:
            os.rename(video_path, encoded_file_path)
        _LOGGER.info(
            "\tOriginal file %s renamed to %s.",
            os.path.basename(video_path),
            os.path.basename(encoded_file_path),
        )
    else:
        if not dry_run:
            os.remove(video_path)
        _LOGGER.info("\tOriginal file %s deleted.", os.path.basename(video_path))

        if not dry_run:
            os.utime(
                encoded_file_path,
                (
                    os.path.getatime(encoded_file_path),
                    os.path.getmtime(encoded_file_path),
                ),
            )


def encode_video(
    input_path: str,
    output_path: str,
    ffmpeg_path: str = "ffmpeg",
    ffmpeg_lib: str = "libx265",
    ffmpeg_crf: int = 28,
    ffmpeg_input_extra_args: str = "",
    ffmpeg_output_extra_args: str = "",
    dry_run: bool = False,
) -> None:
    """Encode a video."""
    command = " ".join(
        [
            ffmpeg_path,
            "-y",
            "-i",
            f'"{input_path}"',
            "-movflags",
            "use_metadata_tags",
            "-c:v",
            ffmpeg_lib,
            "-crf",
            str(ffmpeg_crf),
            "-preset",
            "medium",
            "-acodec",
            "copy",
            "-loglevel",
            "quiet",
            "-stats",
            ffmpeg_input_extra_args,
            f'"{output_path}"',
            ffmpeg_output_extra_args,
        ]
    )
    _LOGGER.debug(command)
    if dry_run:
        return
    encode_process = subprocess.run(
        command,
        shell=True,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if encode_process.returncode != 0:
        raise EncodingException(encode_process.stderr.decode("utf-8"))


class EncodingException(Exception):
    """Exception raised when encoding fails."""
