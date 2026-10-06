"""Event name written in the file metadata with exiftool."""

import hashlib
import logging
import subprocess

from .settings import ClassifySettings

_LOGGER = logging.getLogger("classify")

IDENTIFIER_PREFIX = "sha256:"


def file_identifier(path: str) -> str:
    """Return the identifier of a file content, written in its copies."""
    with open(path, "rb") as file:
        return IDENTIFIER_PREFIX + hashlib.file_digest(file, "sha256").hexdigest()


class MetadataWriter:
    """Write the event name in the metadata of pictures and videos."""

    def __init__(self, settings: ClassifySettings) -> None:
        """Init."""
        self.settings = settings
        self._available: bool | None = None

    @property
    def enabled(self) -> bool:
        """Return whether the metadata are written, warning once without exiftool."""
        if not self.settings.user_config.write_metadata:
            return False
        if self._available is None:
            try:
                subprocess.run(
                    [self.settings.exiftool_path, "-ver"],
                    capture_output=True,
                    check=True,
                )
                self._available = True
            except OSError, subprocess.CalledProcessError:
                _LOGGER.warning(
                    "%s not found, event names are not written in the metadata "
                    "(install exiftool, set its path with --exiftool-path or disable "
                    "write_metadata in the configuration)",
                    self.settings.exiftool_path,
                )
                self._available = False
        return self._available

    def tag_event(self, path: str, event_name: str, identifier: str | None) -> None:
        """Add the event name to the keywords of a file, keeping its dates."""
        _LOGGER.debug("Write event %s in %s metadata", event_name, path)
        if self.settings.dry_run:
            return
        command = [
            self.settings.exiftool_path,
            "-quiet",
            "-overwrite_original",
            # Keep the file modification date, set to the capture date
            "-preserve",
            "-codedcharacterset=utf8",
            # Remove then add, to not duplicate the keyword on a second run
            f"-XMP-dc:Subject-={event_name}",
            f"-XMP-dc:Subject+={event_name}",
            f"-IPTC:Keywords-={event_name}",
            f"-IPTC:Keywords+={event_name}",
            f"-XMP-iptcExt:Event={event_name}",
        ]
        if identifier:
            command.append(f"-XMP-dc:Identifier={identifier}")
        result = subprocess.run(
            [*command, path], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            _LOGGER.warning(
                "Cannot write event in %s metadata: %s", path, result.stderr.strip()
            )

    def read_identifier(self, path: str) -> str:
        """Return the source identifier written in a copy."""
        result = subprocess.run(
            [self.settings.exiftool_path, "-s3", "-XMP-dc:Identifier", path],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()
