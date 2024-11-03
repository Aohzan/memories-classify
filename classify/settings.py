"""Parser for the classify script"""

import argparse

from .const import (
    DEFAULT_FFMPEG_INPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS,
    DEFAULT_FFMPEG_PATH,
    DEFAULT_FFPROBE_PATH,
    DEFAULT_NAME_FORMAT,
)


class ClassifySettings:
    """Classify settings."""

    directory: str
    output: str | None
    copy: bool
    dry_run: bool
    verbose: bool
    name_format: str
    ffmpeg_lib: str = "libx265"
    ffmpeg_crf: int = 28
    ffmpeg_input_extra_args: str
    ffmpeg_output_extra_args: str
    ffmpeg_path: str
    ffprobe_path: str

    def __init__(
        self,
        args: argparse.Namespace | None = None,
    ) -> None:
        """Init."""
        if args is not None:
            self.directory = args.directory
            self.output = args.output
            self.copy = args.copy
            self.dry_run = args.dry_run
            self.verbose = args.verbose
            self.name_format = args.name_format
            self.ffmpeg_input_extra_args = args.ffmpeg_input_extra_args
            self.ffmpeg_output_extra_args = args.ffmpeg_output_extra_args
            self.ffmpeg_path = args.ffmpeg_path
            self.ffprobe_path = args.ffprobe_path


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
        "--output",
        type=str,
        help="Output directory",
        required=False,
    )
    parser.add_argument(
        "--copy", action="store_true", help="Copy files instead of moving them"
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
        "--ffprobe-path",
        type=str,
        help="Path to ffprobe",
        default=DEFAULT_FFPROBE_PATH,
    )
    parser.add_argument(
        "--dry-run",
        help="Do not perform any action, only show what would be done",
        action="store_true",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(arg_list)

    return args
