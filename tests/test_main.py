""" Test main module. """

from classify.classify import classify
from classify.const import DEFAULT_NAME_FORMAT
from classify.settings import ClassifySettings, parse_args


def test_classify():
    """Test classify."""
    args = parse_args(
        [
            "-d",
            "tests/photos",
            "--dry-run",
        ]
    )
    settings = ClassifySettings(args=args)

    assert settings.directory == "tests/photos"
    assert settings.dry_run is True
    assert settings.verbose is False
    assert settings.name_format == DEFAULT_NAME_FORMAT
    
    classify(settings)
