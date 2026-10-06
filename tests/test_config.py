"""Test config module."""

from pathlib import Path

import pytest
import yaml

from classify.config import default_config_path, load_config, save_config
from classify.exception import ClassifyException
from classify.geo import Location
from classify.i18n import HOLIDAY_PRESETS, system_language
from classify.main import main
from tests.conftest import write_config


def test_default_config_path(config_home: Path) -> None:
    """The configuration is in the XDG config directory."""
    assert default_config_path() == config_home / "memories-classify.yaml"


def test_config_created_on_first_run(
    config_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing configuration is created with the default values."""
    path = config_home / "memories-classify.yaml"

    config = load_config(path)

    assert path.exists()
    assert "Configuration file created" in caplog.text
    assert config.language == "en"
    assert config.home is None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["language"] == "en"
    assert data["home"] is None
    assert data["holidays"] == HOLIDAY_PRESETS["en"]
    assert data["recurring"] == {}
    # The generated file loads to the same configuration
    assert load_config(path) == config


def test_config_created_in_system_language(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The created configuration uses the language of the system."""
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    path = config_home / "memories-classify.yaml"

    config = load_config(path)

    assert config.language == "fr"
    assert config.holidays == HOLIDAY_PRESETS["fr"]
    assert "Noël: 12-24..12-25" in path.read_text(encoding="utf-8")


def test_existing_config_not_overwritten(config_home: Path) -> None:
    """An existing configuration is kept, missing keys get their default value."""
    path = write_config(config_home, language="fr", home=[45.76, 4.83])
    content = path.read_text(encoding="utf-8")

    config = load_config(path)

    assert path.read_text(encoding="utf-8") == content
    assert config.home == Location(45.76, 4.83)
    save_config(config, path)
    assert "home: [45.76, 4.83]" in path.read_text(encoding="utf-8")
    assert load_config(path) == config
    assert config.home_radius_km == 50
    assert config.holidays == HOLIDAY_PRESETS["fr"]


def test_language_resolution(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command line language overrides the configured one."""
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert system_language() == "fr"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert system_language() == "en"

    path = write_config(config_home, language="fr")
    assert load_config(path).language == "fr"
    assert load_config(path, language="en").language == "en"


def test_names_override(config_home: Path) -> None:
    """Configured names override the language preset."""
    path = write_config(config_home, language="fr", names={"default": "Autres"})

    templates = load_config(path).name_templates

    assert templates["default"] == "Autres"
    assert templates["trip"] == "Vacances à {city} {year}"


@pytest.mark.parametrize(
    "values",
    [
        {"language": "xx"},
        {"home": [45.76]},
        {"home": "Lyon"},
        {"home_radius_km": "far"},
        {"trip_min_files": 2.5},
        {"preview": "yes"},
        {"holidays": {"Christmas": "christmas"}},
        {"recurring": ["03-14"]},
        {"names": {"trip": "Trip in {town}"}},
        {"holiday_min_files": 0},
        {"trip_max_gap_hours": -1},
    ],
)
def test_invalid_config(config_home: Path, values: dict) -> None:
    """Invalid values are rejected with a clear error."""
    path = write_config(config_home, **values)

    with pytest.raises(ClassifyException, match="configuration"):
        load_config(path)


def test_main_exits_on_invalid_config(
    config_home: Path, input_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An invalid configuration file stops the event sorting only."""
    path = config_home / "memories-classify.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("language: [", encoding="utf-8")

    main(["--directory", str(input_dir), "--dry-run"])
    assert "Cannot read configuration" in caplog.text

    with pytest.raises(SystemExit) as exc_info:
        main(["--directory", str(input_dir), "--dry-run", "--events"])
    assert exc_info.value.code == 1


def test_config_not_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A configuration that cannot be created falls back on the defaults."""
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(not_a_directory))

    config = load_config(default_config_path())

    assert config.language == "en"
    assert "Cannot create configuration file" in caplog.text
