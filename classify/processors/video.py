"""Video processor."""

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta

from classify.const import VIDEO_CODEC
from classify.exception import ClassifyEncodingException
from classify.geo import Location
from classify.processors.files import FileProcessor
from classify.settings import ClassifySettings

_LOGGER = logging.getLogger("classify")

MIN_VALID_YEAR = 1970

# ISO 6709 location, like +45.7640+004.8357+250.000/
ISO6709_REGEX = re.compile(r"([+-]?\d+\.\d+)([+-]\d+\.\d+)([+-]\d+(?:\.\d+)?)?")
# Android and Apple location tags
LOCATION_TAGS = ["location", "com.apple.quicktime.location.ISO6709"]


class VideoProcessor:
    """Video processor class"""

    def __init__(
        self, settings: ClassifySettings, file_processor: FileProcessor
    ) -> None:
        """Initialize the class"""
        self.settings = settings
        self.fp = file_processor

    def get_date_taken(self, path: str) -> datetime:
        """Get the date taken from the name, the metadata or the file of a video.

        The name given by this tool wins: old versions wrote the local time as
        UTC in the creation time.
        """
        if date_from_name := self.fp.get_date_from_name_format(path):
            _LOGGER.debug("Date taken from name: %s", date_from_name)
            return date_from_name

        if date_metadata := self.get_metadata_date(path):
            return date_metadata

        if date_from_file_name := self.fp.get_date_from_file_name(path):
            return date_from_file_name

        # ctime is the inode change time on Linux, mtime is closer to the capture
        _LOGGER.debug("Date taken from file modification date")
        return datetime.fromtimestamp(
            os.path.getmtime(path), tz=self.settings.user_timezone
        )

    def get_metadata_date(self, path: str) -> datetime | None:
        """Get the creation time metadata of a video, in the user timezone."""
        if creation_time_metadata := self.get_metadata(path, "creation_time"):
            _LOGGER.debug("Date taken from metadata: %s", creation_time_metadata)
            try:
                # ffprobe joins duplicated tags (mvhd and mdta atoms) with ";"
                date_metadata = datetime.fromisoformat(
                    creation_time_metadata.split(";")[0]
                )
            except ValueError:
                _LOGGER.warning(
                    "Invalid creation time %s in %s", creation_time_metadata, path
                )
            else:
                if date_metadata.tzinfo is None:
                    date_metadata = date_metadata.replace(tzinfo=UTC)
                # Cameras without a clock write the epoch (1970) or the mp4 epoch (1904)
                if date_metadata.year > MIN_VALID_YEAR:
                    return date_metadata.astimezone(self.settings.user_timezone)
                _LOGGER.debug("Ignore placeholder creation time")
        return None

    def fix_creation_time(self, path: str, date_taken: datetime) -> None:
        """Rewrite a wrong creation time, copying the streams without encoding."""
        date_metadata = self.get_metadata_date(path)
        if date_metadata is None or abs(date_metadata - date_taken) < timedelta(
            seconds=1
        ):
            return
        _LOGGER.info(
            "Fix creation time of %s from %s to %s", path, date_metadata, date_taken
        )
        if self.settings.dry_run:
            return
        creation_time = format_creation_time(date_taken)
        file_descriptor, fixed_path = tempfile.mkstemp(
            dir=os.path.dirname(path), suffix=os.path.splitext(path)[1]
        )
        os.close(file_descriptor)
        command = [
            self.settings.ffmpeg_path,
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            path,
            "-map",
            "0",
            "-c",
            "copy",
            "-movflags",
            "use_metadata_tags",
            "-metadata",
            f"creation_time={creation_time}",
            "-metadata:s",
            f"creation_time={creation_time}",
            fixed_path,
        ]
        _LOGGER.debug(shlex.join(command))
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except KeyboardInterrupt:
            self.remove_partial_file(fixed_path)
            raise
        if result.returncode != 0:
            self.remove_partial_file(fixed_path)
            _LOGGER.warning(
                "Cannot fix creation time of %s: %s", path, result.stderr.strip()
            )
            return
        os.utime(fixed_path, (date_taken.timestamp(), date_taken.timestamp()))
        os.replace(fixed_path, path)

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

    def get_location(self, path: str) -> Location | None:
        """Get the location of a video, with its altitude if any."""
        output = self._run_ffprobe(
            [
                "-v",
                "error",
                "-show_entries",
                f"format_tags={','.join(LOCATION_TAGS)}",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        )
        for line in output.splitlines():
            if match := ISO6709_REGEX.match(line.strip()):
                altitude = match.group(3)
                return Location(
                    float(match.group(1)),
                    float(match.group(2)),
                    float(altitude) if altitude else None,
                )
        _LOGGER.debug("Location not found in video %s", path)
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
    ) -> str | None:
        """Choose between the original and the encoded video, return the kept one."""
        original_size = os.path.getsize(video_path)

        if self.settings.dry_run:
            encoded_size = original_size * 0.8  # fake encoded size
        elif not os.path.exists(encoded_file_path):
            _LOGGER.error(
                "Encoded file %s does not exist.",
                os.path.basename(encoded_file_path),
            )
            return None
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
                shutil.move(video_path, original_dest_path)
            _LOGGER.info(
                "Original file %s renamed to %s.",
                os.path.basename(video_path),
                os.path.basename(original_dest_path),
            )
            return original_dest_path

        if not self.settings.dry_run:
            os.remove(video_path)
        _LOGGER.info("Original file %s deleted.", os.path.basename(video_path))
        return encoded_file_path

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
            f"creation_time={format_creation_time(recorded_date)}",
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
            date_taken = self.get_date_taken(path)
            # Copies are found from their content, the originals are never modified
            if not self.settings.keep_original:
                self.fix_creation_time(path, date_taken)
            if os.path.abspath(self.fp.get_output_path(path)) != os.path.abspath(
                os.path.dirname(path)
            ):
                self.fp.place_in_output(
                    path, date_taken, os.path.splitext(path)[1].lower()
                )
            return

        # get date taken from video
        video_date_taken = self.get_date_taken(path)
        _LOGGER.debug("Video taken on %s", video_date_taken)
        dest_dir_path = self.fp.get_output_path(path)
        if self.settings.keep_original and (
            existing_copy := self.fp.find_existing_copy(
                dest_dir=dest_dir_path,
                date_taken=video_date_taken,
                extension=".mp4",
                is_copy=lambda file_path: (
                    self.settings.comment_message
                    in self.get_metadata(file_path, "comment")
                    and self.get_date_taken(file_path) == video_date_taken
                ),
            )
        ):
            _LOGGER.debug("Video already encoded to %s", existing_copy)
            return

        # The encoded file must never overwrite the source, even if already named
        dest_file_path = self.fp.get_available_filepath_from_date(
            dest_dir=dest_dir_path,
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

        if not self.settings.dry_run:
            recorded_timestamp = video_date_taken.timestamp()
            os.utime(dest_file_path, (recorded_timestamp, recorded_timestamp))

        final_path: str | None = dest_file_path
        if not self.settings.keep_original:
            final_path = self.choose_between_original_and_reencoded(
                video_path=path,
                encoded_file_path=dest_file_path,
                recorded_date=video_date_taken,
            )
        if final_path:
            # Hashing videos is slow, their copies are found from their comment
            self.fp.tag_event(path, final_path, identifier=None)


def format_creation_time(date_taken: datetime) -> str:
    """Return the creation time metadata, in UTC with an offset.

    Without an offset ffmpeg reads the time in the system timezone.
    """
    return date_taken.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
