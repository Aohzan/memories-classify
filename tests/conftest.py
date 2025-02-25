"""Configuration for tests."""

import os
import shutil

import pytest

from classify.classify import Classify
from classify.settings import ClassifySettings, parse_args

INPUT_DIR = "tests/photos"
OUTPUT_DIR = "tests/output"


@pytest.fixture  # noqa misc
def test_classify() -> Classify:
    """Return a TestClassify instance."""

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    args = parse_args(
        [
            "--directory",
            "tests/photos",
            "--output",
            "tests/output",
            "--keep-original",
            "--timezone",
            "UTC",
        ]
    )
    return Classify(settings=ClassifySettings(args=args))


@pytest.fixture
def test_classify_dry_run() -> Classify:
    """Return a TestClassify instance."""

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    args = parse_args(
        [
            "--directory",
            "tests/photos",
            "--output",
            "tests/output",
            "--dry-run",
            "--timezone",
            "UTC",
        ]
    )
    return Classify(settings=ClassifySettings(args=args))
