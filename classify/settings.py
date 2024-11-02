"""Parser for the classify script"""

import argparse

from .const import (
    DEFAULT_FFMPEG_INPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_PATH,
    DEFAULT_NAME_FORMAT,
)


class ClassifySettings:
    """Classify settings."""

    def __init__(self) -> None:
        """Init."""
        args = parse_args()
        self.directory: str = args.directory
        self.dry_run: bool = args.dry_run
        self.verbose: bool = args.verbose
        self.ffmpeg_input_extra_args: str = args.ffmpeg_input_extra_args
        self.ffmpeg_output_extra_args: str = args.ffmpeg_output_extra_args
        self.ffmpeg_path: str = args.ffmpeg_path
        self.name_format: str = args.name_format


def parse_args() -> argparse.Namespace:
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
        "-f",
        "--name-format",
        type=str,
        help="Name format for renaming pictures",
        default=DEFAULT_NAME_FORMAT,
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
        "--dry-run",
        help="Do not perform any action, only show what would be done",
        action="store_true",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    return parser.parse_args()
