"""Video processor."""

import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Tuple

from classify.const import VIDEO_BITRATE_LIMIT, VIDEO_CODEC
from classify.exception import ClassifyEncodingException
from classify.processors.files import FileProcessor
from classify.settings import ClassifySettings

_LOGGER = logging.getLogger("classify")


class VideoProcessor:
    """Video processor class"""

    def __init__(self, settings: ClassifySettings):
        """Initialize the class"""
        self.settings = settings
        self.file_processor = FileProcessor(settings=settings)

    def get_date_taken(self, path: str) -> datetime:
        """Get the date taken from the exif of a video."""
        if date_match := re.search(r"(\d{8}_\d{9})", path):
            _LOGGER.debug("\tDate taken from filename: %s", date_match.group(0))
            date_str = date_match.group(0)
            date_src = datetime.strptime(date_str, "%Y%m%d_%H%M%S%f").replace(
                tzinfo=timezone.utc
            )
            local_time = date_src.astimezone()
            return local_time
        _LOGGER.debug("\tDate taken from file date")
        return datetime.fromtimestamp(os.path.getctime(path))

    def get_bitrate(self, path: str) -> int:
        """Get the bitrate of a video."""
        command = os.popen(
            " ".join(
                [
                    self.settings.ffprobe_path,
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

    def get_codec(self, path: str) -> str:
        """Get the codec of a video."""
        command = os.popen(
            " ".join(
                [
                    self.settings.ffprobe_path,
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
        return codec.lower()

    def get_location(self, path: str) -> Tuple[float, float] | None:
        """Get the location of a video."""
        command = os.popen(
            " ".join(
                [
                    self.settings.ffprobe_path,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "format_tags=location",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    f'"{path}"',
                ]
            )
        )
        match = re.match(r"([+-]?\d+\.\d+)([+-]\d+\.\d+)", command.read().strip())

        if match:
            latitude = float(match.group(1))
            longitude = float(match.group(2))
            return (latitude, longitude)
        _LOGGER.error("Location not found in video")
        return None

    def is_already_reencoded(self, path: str) -> bool:
        """Check if a video has already been encoded."""
        video_codec = self.get_codec(path)
        video_bitrate = self.get_bitrate(path)
        _LOGGER.debug("\tVideo codec: %s (wanted: %s)", video_codec, VIDEO_CODEC)
        _LOGGER.debug(
            "\tVideo bitrate: %s (wanted: %s max)",
            f"{video_bitrate:,}",
            f"{VIDEO_BITRATE_LIMIT:,}",
        )
        return video_codec == VIDEO_CODEC and video_bitrate <= VIDEO_BITRATE_LIMIT

    def choose_between_original_and_reencoded(
        self, video_path: str, encoded_file_path: str
    ) -> None:
        """Choose between the original and the encoded video."""
        original_size = os.path.getsize(video_path)

        if self.settings.dry_run:
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
            if not self.settings.dry_run:
                os.remove(encoded_file_path)
            _LOGGER.warning(
                "\tEncoding file %s deleted because space too close from original file.",
                os.path.basename(encoded_file_path),
            )

            if not self.settings.dry_run:
                os.rename(video_path, encoded_file_path)
            _LOGGER.info(
                "\tOriginal file %s renamed to %s.",
                os.path.basename(video_path),
                os.path.basename(encoded_file_path),
            )
        else:
            if not self.settings.dry_run:
                os.remove(video_path)
            _LOGGER.info("\tOriginal file %s deleted.", os.path.basename(video_path))

            if not self.settings.dry_run:
                os.utime(
                    encoded_file_path,
                    (
                        os.path.getatime(encoded_file_path),
                        os.path.getmtime(encoded_file_path),
                    ),
                )

    def reencode(
        self,
        input_path: str,
        output_path: str,
    ) -> None:
        """Encode a video."""
        command = [
            self.settings.ffmpeg_path,
            "-y",
            "-i",
            f'"{input_path}"',
            "-movflags",
            "use_metadata_tags",
            "-c:v",
            self.settings.ffmpeg_lib,
            "-crf",
            str(self.settings.ffmpeg_crf),
            "-preset",
            "medium",
            "-acodec",
            "copy",
            "-loglevel",
            "quiet",
            "-stats",
            self.settings.ffmpeg_input_extra_args,
            f'"{output_path}"',
            self.settings.ffmpeg_output_extra_args,
        ]
        _LOGGER.debug(" ".join(command))
        if self.settings.dry_run:
            return
        try:
            with subprocess.Popen(
                args=command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as encode_process:
                _LOGGER.debug("Encoding started")
                stdout, stderr = encode_process.communicate()
                if encode_process.returncode != 0:
                    raise ClassifyEncodingException(stderr + " " + stdout)
        except KeyboardInterrupt:
            encode_process.kill()
            sys.exit(1)

    def process(self, video_path) -> None:
        """Process a video."""

        video_file_name = os.path.basename(video_path)
        # check if video has already been encoded
        if self.is_already_reencoded(video_path):
            _LOGGER.debug("\tVideo already encoded")
            return

        # get date taken from video
        video_date_taken = self.get_date_taken(video_path)
        _LOGGER.debug("\tVideo %s taken on %s", video_file_name, video_date_taken)
        encoded_file_name = (
            f"{video_date_taken.strftime(self.settings.name_format)}.mp4"
        )
        encoded_file_path = os.path.join(os.path.dirname(video_path), encoded_file_name)

        if os.path.exists(encoded_file_path):
            _LOGGER.warning("\tDelete existing target file %s", encoded_file_path)
            self.file_processor.remove_file(encoded_file_path)

        # encode file
        _LOGGER.info("\tEncoding video %s to %s", video_file_name, encoded_file_name)
        try:
            self.reencode(input_path=video_path, output_path=encoded_file_path)
        except ClassifyEncodingException as e:
            _LOGGER.error("\tError while encoding video: %s", e)
            return

        self.choose_between_original_and_reencoded(
            video_path=video_path,
            encoded_file_path=encoded_file_path,
        )
