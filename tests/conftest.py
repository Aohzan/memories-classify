"""Configuration for tests."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from classify.classify import Classify
from classify.settings import ClassifySettings, parse_args

SAMPLES_DIR = Path(__file__).parent / "photos"
# Only the tracked samples, tests/photos/custom may hold large local files
SAMPLE_FILES = [
    "dir1/IMG_1001.jpg",
    "dir1/IMG_1002.jpg",
    "dir1/video.mp4",
    "dir2/IMG_2201.jpg",
    "custom/IMG_1005.jpg",
]

type ClassifyFactory = Callable[..., Classify]


@pytest.fixture
def input_dir(tmp_path: Path) -> Path:
    """Return a temporary copy of the sample pictures and videos."""
    directory = tmp_path / "photos"
    for sample in SAMPLE_FILES:
        destination = directory / sample
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SAMPLES_DIR / sample, destination)
    return directory


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Return the temporary output directory."""
    return tmp_path / "output"


@pytest.fixture
def make_classify(input_dir: Path) -> ClassifyFactory:
    """Return a factory building a Classify instance on the sample copy."""

    def factory(*extra_args: str) -> Classify:
        args = parse_args(
            [
                "--directory",
                str(input_dir),
                "--exclude",
                "custom/",
                "--timezone",
                "UTC",
                *extra_args,
            ]
        )
        return Classify(settings=ClassifySettings(args=args))

    return factory


@pytest.fixture
def classify_copy(make_classify: ClassifyFactory, output_dir: Path) -> Classify:
    """Return a Classify instance copying files to the output directory."""
    return make_classify("--output", str(output_dir), "--keep-original")


@pytest.fixture
def classify_dry_run(make_classify: ClassifyFactory, output_dir: Path) -> Classify:
    """Return a Classify instance in dry-run mode."""
    return make_classify("--output", str(output_dir), "--dry-run")
