"""Classify."""

import logging
import os
import sys


from .logger import CustomFormatter
from .settings import ClassifySettings
from .exception import ClassifyException
from .classify import classify

_LOGGER = logging.getLogger("classify")


def main():
    """Main."""
    settings = ClassifySettings()

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

    try:
        classify(settings)
        _LOGGER.info("End")
    except ClassifyException as exc:
        _LOGGER.info("End with error %s", exc)
        sys.exit(1)
