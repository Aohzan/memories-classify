from classify.settings import ClassifySettings, parse_args


def tests_classify_settings():
    """Common settings."""
    args = parse_args(
        [
            "-d",
            "tests/photos",
            "--output",
            "tests/output",
            "--copy",
            "--dry-run",
        ]
    )
    return ClassifySettings(args=args)
