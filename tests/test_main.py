"""Test main module."""

from classify.classify import Classify
from classify.const import DEFAULT_NAME_FORMAT
from tests.common import tests_classify_settings


def test_classify():
    """Test classify."""
    settings = tests_classify_settings()

    assert settings.directory == "tests/photos"
    assert settings.output == "tests/output"
    assert settings.copy is True
    assert settings.dry_run is True
    assert settings.verbose is False
    assert settings.name_format == DEFAULT_NAME_FORMAT

    Classify(settings).run()
