"""Configuration for tests."""

import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image
from PIL.ExifTags import GPS, IFD, Base
from PIL.TiffImagePlugin import IFDRational

from classify import organizer
from classify.classify import Classify
from classify.geo import Location
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

EXIFTOOL_PATH = shutil.which("exiftool")


def degrees_to_dms(value: float) -> tuple[float, float, float]:
    """Convert decimal degrees to EXIF degrees, minutes and seconds."""
    value = abs(value)
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = round((value - degrees - minutes / 60) * 3600, 4)
    return (float(degrees), float(minutes), seconds)


def make_picture(
    path: Path, date_taken: datetime, location: Location | None = None
) -> Path:
    """Write a small picture with an EXIF date and an optional GPS location."""
    exif = Image.Exif()
    exif[Base.DateTime] = date_taken.strftime("%Y:%m:%d %H:%M:%S")
    if location:
        gps: dict[int, Any] = {
            GPS.GPSLatitudeRef: "N" if location.lat >= 0 else "S",
            GPS.GPSLatitude: degrees_to_dms(location.lat),
            GPS.GPSLongitudeRef: "E" if location.lon >= 0 else "W",
            GPS.GPSLongitude: degrees_to_dms(location.lon),
        }
        if location.altitude is not None:
            gps[GPS.GPSAltitudeRef] = b"\x00" if location.altitude >= 0 else b"\x01"
            gps[GPS.GPSAltitude] = IFDRational(abs(location.altitude))
        exif[IFD.GPSInfo] = gps
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8)).save(path, exif=exif)
    return path


def write_config(config_home: Path, **values: Any) -> Path:
    """Write a user configuration file."""
    path = config_home / "memories-classify.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(values, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the user configuration file from the real one."""
    directory = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(directory))
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    for name in ("LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(name, raising=False)
    return directory


@pytest.fixture(autouse=True)
def opened_folders(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record the files of the folders opened in the file manager."""
    folders: list[list[str]] = []
    monkeypatch.setattr(
        organizer,
        "open_folder",
        lambda path: folders.append(sorted(p.name for p in Path(path).iterdir())),
    )
    return folders


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
