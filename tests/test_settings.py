"""Test settings module."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from classify.settings import ClassifySettings, parse_args, system_timezone


@pytest.fixture(autouse=True)
def no_tz_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ignore the TZ variable of the test environment."""
    monkeypatch.delenv("TZ", raising=False)


def test_timezone_from_localtime_link(tmp_path: Path) -> None:
    """The timezone name is read from the /etc/localtime link."""
    zoneinfo = tmp_path / "usr/share/zoneinfo/America"
    zoneinfo.mkdir(parents=True)
    (zoneinfo / "New_York").write_bytes(b"")
    localtime = tmp_path / "localtime"
    localtime.symlink_to(zoneinfo / "New_York")

    timezone = system_timezone(str(localtime), str(tmp_path / "missing"))

    assert timezone == ZoneInfo("America/New_York")
    # The offset follows daylight saving time, unlike the offset of today
    assert (
        datetime(2026, 1, 15, tzinfo=timezone).utcoffset()
        != datetime(2026, 7, 15, tzinfo=timezone).utcoffset()
    )


def test_timezone_from_timezone_file(tmp_path: Path) -> None:
    """The timezone name is read from /etc/timezone."""
    timezone_file = tmp_path / "timezone"
    timezone_file.write_text("Europe/Paris\n", encoding="utf-8")

    assert system_timezone(str(tmp_path / "missing"), str(timezone_file)) == ZoneInfo(
        "Europe/Paris"
    )


def test_timezone_from_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TZ variable wins."""
    monkeypatch.setenv("TZ", ":Asia/Tokyo")

    assert system_timezone(str(tmp_path / "missing")) == ZoneInfo("Asia/Tokyo")


def test_timezone_fallback_on_offset(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Without timezone name, the current offset is used with a warning."""
    timezone = system_timezone(str(tmp_path / "missing"), str(tmp_path / "missing"))

    assert timezone == datetime.now().astimezone().tzinfo
    assert "--timezone" in caplog.text


def test_settings_use_system_timezone(
    input_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --timezone, the settings use the system timezone."""
    monkeypatch.setenv("TZ", "Europe/Paris")

    settings = ClassifySettings(args=parse_args(["--directory", str(input_dir)]))

    assert settings.user_timezone == ZoneInfo("Europe/Paris")
