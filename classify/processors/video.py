"""Video processor."""

import logging
import os
import re
import shlex
import subprocess
from datetime import UTC, datetime

from classify.const import VIDEO_CODEC
from classify.exception import ClassifyEncodingException
from classify.processors.files import FileProcessor
from classify.settings import ClassifySettings

_LOGGER = logging.getLogger("classify")

FILENAME_REGEX = {
    r"(\d{8}_\d{9})": "%Y%m%d_%H%M%S%f",
    r"(\d{8}-\d{9})": "%Y%m%d-%H%M%S%f",
    r"(\d{14})": "%Y%m%d%H%M%S",
}


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
        if creation_time_metadata := self.get_metadata(path, "creation_time"):
            _LOGGER.debug("Date taken from metadata: %s", creation_time_metadata)
            date_metadata = datetime.strptime(
                creation_time_metadata, "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=UTC)
            local_time = date_metadata.astimezone(self.settings.user_timezone)
            return local_time

        for regex, date_format in FILENAME_REGEX.items():
            if date_match := re.search(regex, path):
                _LOGGER.debug("Date taken from filename: %s", date_match.group(0))
                date_str = date_match.group(0)
                date_src = datetime.strptime(date_str, date_format).replace(tzinfo=UTC)
                local_time = date_src.astimezone(self.settings.user_timezone)
                return local_time

        _LOGGER.debug("Date taken from file date")
        return datetime.fromtimestamp(
            os.path.getctime(path), tz=self.settings.user_timezone
        )

    def _run_ffprobe(self, args: list[str]) -> str:
        """Run ffprobe with the given arguments and return its stripped output."""
        result = subprocess.run(
            [self.settings.ffprobe_path, *args],
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.stdout.strip()

    def get_bitrate(self, path: str) -> float:
        """Get the bitrate of a video in Mbps."""
        bitrate = self._run_ffprobe(
            [
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=bit_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        )
        return round(int(bitrate) / 1000 / 1000, 2)

    def get_codec(self, path: str) -> str:
        """Get the codec of a video."""
        codec = self._run_ffprobe(
            [
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        )
        return codec.lower()

    def get_metadata(self, path: str, metadata: str) -> str:
        """Get the comment metadata of a video."""
        return self._run_ffprobe(
            [
                "-v",
                "error",
                "-show_entries",
                f"format_tags={metadata}",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        )

    def get_location(self, path: str) -> tuple[float, float] | None:
        """Get the location of a video."""
        output = self._run_ffprobe(
            [
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format_tags=location",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        )
        match = re.match(r"([+-]?\d+\.\d+)([+-]\d+\.\d+)", output)

        if match:
            latitude = float(match.group(1))
            longitude = float(match.group(2))
            return (latitude, longitude)
        _LOGGER.error("Location not found in video")
        return None

    def is_already_reencoded(self, path: str) -> bool:
        """Check if a video has already been encoded."""

        # Check if filename matches the date format
        comment_metadata = self.get_metadata(path, "comment")
        if self.settings.comment_message in comment_metadata:
            _LOGGER.debug("%s found in comment metadata", self.settings.comment_message)
            return True

        use_name_format = self.fp.is_date_named(path)
        _LOGGER.debug("Filename matches the date format: %s", use_name_format)

        # Check if video codec and bitrate are correct
        video_codec = self.get_codec(path)
        video_bitrate = self.get_bitrate(path)
        _LOGGER.debug("Video codec: %s (wanted: %s)", video_codec, VIDEO_CODEC)
        _LOGGER.debug(
            "Video bitrate: %s (wanted: %s max)",
            f"{video_bitrate:,}",
            f"{self.settings.video_bitrate_limit:,}",
        )

        return (
            video_codec == VIDEO_CODEC
            and use_name_format
            and video_bitrate <= self.settings.video_bitrate_limit
        )

    def choose_between_original_and_reencoded(
        self, video_path: str, encoded_file_path: str, recorded_date: datetime
    ) -> None:
        """Choose between the original and the encoded video."""
        original_size = os.path.getsize(video_path)

        if self.settings.dry_run:
            encoded_size = original_size * 0.8  # fake encoded size
        elif not os.path.exists(encoded_file_path):
            _LOGGER.error(
                "Encoded file %s does not exist.",
                os.path.basename(encoded_file_path),
            )
            return
        else:
            encoded_size = os.path.getsize(encoded_file_path)

        size_ratio = encoded_size / original_size

        _LOGGER.info(
            "New file space reduces by %s%% (%s GB)",
            round((1 - size_ratio) * 100),
            round(encoded_size / 1e9, 3),
        )

        if size_ratio > 0.90:
            if not self.settings.dry_run:
                os.remove(encoded_file_path)
            _LOGGER.warning(
                "Encoding file %s deleted because space too close from original file.",
                os.path.basename(encoded_file_path),
            )

            # Keep the original container, it may not be an mp4
            original_dest_path = self.fp.get_available_filepath_from_date(
                dest_dir=os.path.dirname(encoded_file_path),
                date_taken=recorded_date,
                extension=os.path.splitext(video_path)[1].lower(),
                source_file=video_path,
            )
            if not self.settings.dry_run:
                os.rename(video_path, original_dest_path)
            _LOGGER.info(
                "Original file %s renamed to %s.",
                os.path.basename(video_path),
                os.path.basename(original_dest_path),
            )
        else:
            if not self.settings.dry_run:
                os.remove(video_path)
            _LOGGER.info("Original file %s deleted.", os.path.basename(video_path))

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
        recorded_date: datetime,
    ) -> None:
        """Encode a video."""
        command = [
            self.settings.ffmpeg_path,
            "-nostdin",
            "-y",
            *shlex.split(self.settings.ffmpeg_input_extra_args),
            "-i",
            input_path,
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
            "-metadata",
            f"creation_time={recorded_date.strftime('%Y-%m-%d %H:%M:%S')}",
            "-metadata",
            f"comment={self.settings.comment_message}",
            "-loglevel",
            "warning",
            *shlex.split(self.settings.ffmpeg_output_extra_args),
            output_path,
        ]
        _LOGGER.debug(shlex.join(command))
        if self.settings.dry_run:
            return
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        _LOGGER.debug("Encoding started")
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except KeyboardInterrupt:
            self.remove_partial_file(output_path)
            raise
        if result.returncode != 0:
            self.remove_partial_file(output_path)
            raise ClassifyEncodingException(f"{result.stderr} {result.stdout}")

    def remove_partial_file(self, path: str) -> None:
        """Remove an incomplete encoded file."""
        if os.path.exists(path):
            _LOGGER.debug("Remove incomplete file %s", path)
            os.remove(path)

    def test(self, path: str) -> bool:
        """Test if a file is a correct video."""
        if self.settings.dry_run:
            return True
        result = subprocess.run(
            [
                self.settings.ffmpeg_path,
                "-nostdin",
                "-v",
                "error",
                "-i",
                path,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stderr:
            _LOGGER.error("Error while checking video: %s", result.stderr)
            return False
        return True

    def process(self, path: str) -> None:
        """Process a video."""

        # check if video has already been encoded
        if self.is_already_reencoded(path):
            _LOGGER.debug("Video already encoded")
            return

        # get date taken from video
        video_date_taken = self.get_date_taken(path)
        _LOGGER.debug("Video taken on %s", video_date_taken)
        # The encoded file must never overwrite the source, even if already named
        dest_file_path = self.fp.get_available_filepath_from_date(
            dest_dir=self.fp.get_output_path(path),
            date_taken=video_date_taken,
            extension=".mp4",
        )

        _LOGGER.info("Encoding video %s to %s", path, dest_file_path)
        try:
            self.encode(
                input_path=path,
                output_path=dest_file_path,
                recorded_date=video_date_taken,
            )
        except ClassifyEncodingException as e:
            _LOGGER.error("Error while encoding video: %s", e)
            return

        if not self.test(dest_file_path):
            if not self.settings.dry_run:
                self.remove_partial_file(dest_file_path)
            return

        if not self.settings.keep_original:
            self.choose_between_original_and_reencoded(
                video_path=path,
                encoded_file_path=dest_file_path,
                recorded_date=video_date_taken,
            )
