"""Parser for the classify script"""

import argparse
import datetime
import importlib.metadata
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import UserConfig, default_config_path, load_config
from .const import (
    DEFAULT_COMMENT_MESSAGE,
    DEFAULT_EXIFTOOL_PATH,
    DEFAULT_FFMPEG_INPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_PATH,
    DEFAULT_FFPROBE_PATH,
    DEFAULT_NAME_FORMAT,
    DEFAULT_VIDEO_BITRATE_MBPS_LIMIT,
)
from .exception import ClassifyException
from .i18n import LANGUAGES

_LOGGER = logging.getLogger("classify")

LOCALTIME_PATH = "/etc/localtime"
TIMEZONE_PATH = "/etc/timezone"


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
    exclude: list[str]
    comment_message: str = DEFAULT_COMMENT_MESSAGE
    events: bool = False
    interactive: bool = True
    exiftool_path: str = DEFAULT_EXIFTOOL_PATH
    config_path: Path
    user_config: UserConfig

    def __init__(
        self,
        args: argparse.Namespace | None = None,
    ) -> None:
        """Init."""
        self.exclude = []
        self.user_config = UserConfig()
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
            self.comment_message = args.comment_message
            self.events = args.events
            self.interactive = not args.no_interactive
            self.exiftool_path = args.exiftool_path
            self.config_path = (
                Path(args.config) if args.config else default_config_path()
            )
            try:
                self.user_config = load_config(self.config_path, args.language)
            except ClassifyException as exc:
                # The configuration is only used to sort by event
                if self.events:
                    raise
                _LOGGER.warning("%s", exc)
            if (
                self.events
                and self.keep_original
                and (os.path.abspath(self.output) == os.path.abspath(self.directory))
            ):
                # Copies in the year folders would be detected again as new files
                raise ClassifyException(
                    "--events with --keep-original requires another --output directory"
                )

            if args.timezone:
                try:
                    self.user_timezone = ZoneInfo(args.timezone)
                    _LOGGER.info("User timezone set to: %s", args.timezone)
                except (ZoneInfoNotFoundError, ValueError) as exc:
                    raise ClassifyException(
                        f"Invalid timezone: {args.timezone}"
                    ) from exc
            else:
                self.user_timezone = system_timezone()
                _LOGGER.info("Timezone found: %s", self.user_timezone)


def system_timezone(
    localtime_path: str = LOCALTIME_PATH, timezone_path: str = TIMEZONE_PATH
) -> datetime.tzinfo:
    """Return the system timezone, with its daylight saving time rules.

    The name is read from the TZ variable, /etc/timezone or the /etc/localtime link.
    """
    names = []
    if tz_variable := os.environ.get("TZ"):
        names.append(tz_variable.removeprefix(":"))
    try:
        names.append(Path(timezone_path).read_text(encoding="utf-8").strip())
    except OSError:
        pass
    names.append(os.path.realpath(localtime_path))
    for name in names:
        # Paths like /usr/share/zoneinfo/Europe/Paris
        name = name.split("/zoneinfo/", 1)[-1]
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError, ValueError:
            continue

    # A fixed offset is wrong on the other side of daylight saving time
    timezone = datetime.datetime.now().astimezone().tzinfo or datetime.UTC
    _LOGGER.warning(
        "Timezone name not found, using the current offset %s for all dates "
        "(set it with --timezone, like Europe/Paris)",
        timezone,
    )
    return timezone


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
        help=(
            "Regular expressions matched against the start of the file paths "
            "relative to the directory, to exclude them from processing"
        ),
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
        default=DEFAULT_COMMENT_MESSAGE,
    )
    parser.add_argument(
        "--events",
        action="store_true",
        help=(
            "Sort the files in year folders, by detected event (trip, holiday...) "
            "or in a default folder"
        ),
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Never ask the event names, only warn about the detected events",
    )
    parser.add_argument(
        "--language",
        choices=LANGUAGES,
        help="Language of the event folder names (default: from the configuration)",
        default=None,
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file (default: ~/.config/memories-classify.yaml)",
        default=None,
    )
    parser.add_argument(
        "--exiftool-path",
        type=str,
        help="Path to exiftool, writing the event names in the metadata",
        default=DEFAULT_EXIFTOOL_PATH,
    )
    parser.add_argument(
        "--dry-run",
        help=(
            "Do not change any picture or video, only show what would be done "
            "(the configuration and the event names are still saved)"
        ),
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
