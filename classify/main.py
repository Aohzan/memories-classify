"""Classify."""

import logging
import os
import sys
from subprocess import DEVNULL, STDOUT, CalledProcessError, check_call

from .classify import Classify
from .exception import ClassifyException
from .logger import CustomFormatter
from .settings import ClassifySettings, parse_args

_LOGGER = logging.getLogger("classify")


def main(arg_list: list[str] | None = None):
    """Call from cli."""

    args = parse_args(arg_list)

    settings = ClassifySettings(args=args)

    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())
    _LOGGER.addHandler(handler)
    if settings.verbose:
        _LOGGER.setLevel(logging.DEBUG)
    else:
        _LOGGER.setLevel(logging.INFO)

    _LOGGER.info("Classify pictures and videos tool")

    if settings.dry_run:
        _LOGGER.warning("Dry run mode activated")

    if not os.path.isdir(settings.directory):
        _LOGGER.error("Directory %s does not exist", settings.directory)
        sys.exit(1)

    _LOGGER.info("Process directory: %s", settings.directory)

    # check if ffmpeg is installed
    try:
        check_call([args.ffmpeg_path, "-version"], stdout=DEVNULL, stderr=STDOUT)
    except CalledProcessError:
        _LOGGER.error(
            "ffmpeg not found (install ffmpeg or set path with --ffmpeg-path)"
        )
        sys.exit(1)

    try:
        Classify(settings).run()
        _LOGGER.info("End")
    except ClassifyException as exc:
        _LOGGER.info("End with error %s", exc)
        sys.exit(1)
