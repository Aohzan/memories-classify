"""Classify."""

import logging
import os
import sys
from subprocess import DEVNULL, CalledProcessError, check_call

from .classify import Classify
from .exception import ClassifyException
from .logger import CustomFormatter
from .settings import ClassifySettings, parse_args

_LOGGER = logging.getLogger("classify")


def is_tool_available(path: str) -> bool:
    """Check that an ffmpeg tool can be executed."""
    try:
        check_call([path, "-version"], stdout=DEVNULL, stderr=DEVNULL)
    except OSError, CalledProcessError:
        return False
    return True


def main(arg_list: list[str] | None = None):
    """Call from cli."""

    args = parse_args(arg_list)

    if not _LOGGER.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())
        _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    _LOGGER.info("Classify pictures and videos tool")

    try:
        settings = ClassifySettings(args=args)
    except ClassifyException as exc:
        _LOGGER.error("%s", exc)
        sys.exit(1)

    if settings.dry_run:
        _LOGGER.warning("Dry run mode activated")

    if not os.path.isdir(settings.directory):
        _LOGGER.error("Directory %s does not exist", settings.directory)
        sys.exit(1)

    _LOGGER.info("Process directory: %s", settings.directory)

    for tool_path, option in (
        (settings.ffmpeg_path, "--ffmpeg-path"),
        (settings.ffprobe_path, "--ffprobe-path"),
    ):
        if not is_tool_available(tool_path):
            _LOGGER.error(
                "%s not found (install ffmpeg or set path with %s)", tool_path, option
            )
            sys.exit(1)

    try:
        Classify(settings).run()
        _LOGGER.info("End")
    except ClassifyException as exc:
        _LOGGER.error("End with error: %s", exc)
        sys.exit(1)
