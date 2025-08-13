"""Parser for the classify script"""

import argparse
import datetime
import importlib.metadata
import logging

from pytz import UnknownTimeZoneError
from pytz import timezone as pytz_timezone

from .const import (
    DEFAULT_FFMPEG_INPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_PATH,
    DEFAULT_FFPROBE_PATH,
    DEFAULT_NAME_FORMAT,
    DEFAULT_VIDEO_BITRATE_MBPS_LIMIT,
)
from .exception import ClassifyException

_LOGGER = logging.getLogger("classify")


class ClassifySettings:
    """Classify settings."""

    directory: str
    output: str
    keep_original: bool
    dry_run: bool
    verbose: bool
    name_format: str
    video_bitrate_limit: int
    ffmpeg_lib: str = "libx265"
    ffmpeg_crf: int = 28
    ffmpeg_input_extra_args: str
    ffmpeg_output_extra_args: str
    ffmpeg_path: str
    ffprobe_path: str
    user_timezone: datetime.tzinfo
    exclude: list[str] = []
    comment_message: str = "Processed by memories-classify"

    def __init__(
        self,
        args: argparse.Namespace | None = None,
    ) -> None:
        """Init."""
        if args is not None:
            self.directory = args.directory
            self.exclude = args.exclude
            self.output = args.output if args.output else args.directory
            self.keep_original = args.keep_original
            self.dry_run = args.dry_run
            self.verbose = args.verbose
            self.name_format = args.name_format
            self.video_bitrate_limit = args.video_bitrate_limit
            self.ffmpeg_input_extra_args = args.ffmpeg_input_extra_args
            self.ffmpeg_output_extra_args = args.ffmpeg_output_extra_args
            self.ffmpeg_path = args.ffmpeg_path
            self.ffprobe_path = args.ffprobe_path

            if args.timezone:
                try:
                    self.user_timezone = pytz_timezone(args.timezone)
                    _LOGGER.info("User timezone set to: %s", args.timezone)
                except UnknownTimeZoneError as exc:
                    raise ClassifyException(
                        f"Invalid timezone: {args.timezone}"
                    ) from exc
            else:
                # Guess timezone from system
                try:
                    # Get the local timezone name, handling DST
                    dt_now = datetime.datetime.now().astimezone()
                    if dt_now.tzinfo is None:
                        raise Exception()
                    self.user_timezone = dt_now.tzinfo
                    _LOGGER.info("Timezone found: %s", str(self.user_timezone))
                except Exception as exc:
                    # Fallback to UTC if system timezone cannot be determined
                    self.user_timezone = pytz_timezone("UTC")
                    _LOGGER.warning(
                        "No valid timezone found, falling back to UTC because %s",
                        str(exc),
                    )


def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    """Return the parser for the classify script"""
    parser = argparse.ArgumentParser(
        prog="Classify pictures and videos",
        description="Sort, encode, rename and adjust date of pictures and videos",
    )

    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        help="Directory to process",
        required=True,
    )
    parser.add_argument(
        "-e",
        "--exclude",
        type=str,
        nargs="+",
        help="List of patterns to exclude from processing",
        default=[],
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output directory (default: same as input)",
        required=False,
    )
    parser.add_argument(
        "--keep-original",
        action="store_true",
        help="Copy files instead of moving/renaming them",
    )
    parser.add_argument(
        "-f",
        "--name-format",
        type=str,
        help="Name format for renaming pictures",
        default=DEFAULT_NAME_FORMAT,
    )
    parser.add_argument(
        "--video-bitrate-limit",
        type=int,
        help="Video bitrate limit in Mbps",
        default=DEFAULT_VIDEO_BITRATE_MBPS_LIMIT,
    )
    parser.add_argument(
        "--ffmpeg-path",
        type=str,
        help="Path to ffmpeg",
        default=DEFAULT_FFMPEG_PATH,
    )
    parser.add_argument(
        "--ffmpeg-input-extra-args",
        help="Additional arguments for ffmpeg input",
        default=DEFAULT_FFMPEG_INPUT_EXTRA_ARGS,
    )
    parser.add_argument(
        "--ffmpeg-output-extra-args",
        help="Additional arguments for ffmpeg output",
        default=DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS,
    )
    parser.add_argument(
        "--ffprobe-path",
        type=str,
        help="Path to ffprobe",
        default=DEFAULT_FFPROBE_PATH,
    )
    parser.add_argument(
        "--timezone",
        type=str,
        help="Timezone to use for date taken",
        default=None,
    )
    parser.add_argument(
        "--comment-message",
        type=str,
        help="Comment to add to the metadata",
        default="Processed by memories-classify",
    )
    parser.add_argument(
        "--dry-run",
        help="Do not perform any action, only show what would be done",
        action="store_true",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + importlib.metadata.version("memories-classify"),
    )

    args = parser.parse_args(arg_list)

    return args
