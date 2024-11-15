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

    def __init__(
        self, settings: ClassifySettings, file_processor: FileProcessor
    ) -> None:
        """Initialize the class"""
        self.settings = settings
        self.fp = file_processor

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

    def encode(
        self,
        input_path: str,
        output_path: str,
    ) -> None:
        """Encode a video."""
        command = " ".join(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-i",
                f'"{os.path.abspath(input_path)}"',
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
                "warning",
                "-stats",
                self.settings.ffmpeg_input_extra_args,
                f'"{os.path.abspath(output_path)}"',
                self.settings.ffmpeg_output_extra_args,
            ]
        )
        _LOGGER.debug(command)
        if self.settings.dry_run:
            return
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with subprocess.Popen(
                args=command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            ) as encode_process:
                _LOGGER.debug("Encoding started")
                stdout, stderr = encode_process.communicate()
                if encode_process.returncode != 0:
                    raise ClassifyEncodingException(
                        stderr.decode() + " " + stdout.decode()
                    )
        except KeyboardInterrupt:
            encode_process.kill()
            sys.exit(1)

    def test(self, path: str) -> bool:
        """Test if a file is a correct video."""
        with subprocess.Popen(
            args=f'{self.settings.ffmpeg_path} -v error -i "{path}" -f null -',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        ) as check_process:
            _, stderr = check_process.communicate()
            if check_process.returncode != 0 or stderr:
                _LOGGER.error("\tError while checking video: %s", stderr)
                return False
        return True

    def process(self, path: str) -> None:
        """Process a video."""

        # check if video has already been encoded
        if self.is_already_reencoded(path):
            _LOGGER.debug("\tVideo already encoded")
            return

        # get date taken from video
        video_date_taken = self.get_date_taken(path)
        _LOGGER.debug("\tVideo taken on %s", video_date_taken)
        encoded_file_name = (
            f"{video_date_taken.strftime(self.settings.name_format)}.mp4"
        )
        dest_dir_path = self.fp.get_output_path(path)
        dest_file_path = os.path.join(dest_dir_path, encoded_file_name)

        if os.path.exists(dest_file_path):
            _LOGGER.warning("\tDelete existing target file %s", dest_file_path)
            self.fp.remove_file(dest_file_path)

        # encode file
        _LOGGER.info("\tEncoding video %s to %s", path, dest_file_path)
        try:
            self.encode(input_path=path, output_path=dest_file_path)
        except ClassifyEncodingException as e:
            _LOGGER.error("\tError while encoding video: %s", e)
            return

        if not self.test(dest_file_path):
            return

        if not self.settings.keep_original:
            self.choose_between_original_and_reencoded(
                video_path=path,
                encoded_file_path=dest_file_path,
            )