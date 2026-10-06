"""Files management for Classify."""

import filecmp
import logging
import os
import re
import shutil
import string
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from classify.settings import ClassifySettings

from ..const import (
    DATE_ONLY_HOUR,
    FILENAME_DATE_FORMATS,
    PICTURE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from ..exception import ClassifyException
from ..metadata import MetadataWriter, file_identifier

_LOGGER = logging.getLogger("classify")


class FileProcessor:
    """Files processor for Classify."""

    pictures: list[str]
    videos: list[str]
    # Output folders relative to the output directory, set by event sorting
    event_dirs: dict[str, str]
    # Event names to write in the metadata of the files
    event_names: dict[str, str]

    def __init__(self, settings: ClassifySettings) -> None:
        """Init."""
        self.settings = settings
        self.pictures = []
        self.videos = []
        self.event_dirs = {}
        self.event_names = {}
        self.metadata = MetadataWriter(settings)

        if not os.path.exists(self.settings.output):
            _LOGGER.info("Create missing output directory %s", self.settings.output)
            if not self.settings.dry_run:
                os.makedirs(self.settings.output)

        self.reload()

        _LOGGER.info(
            "Found %d pictures and %d videos",
            len(self.pictures),
            len(self.videos),
        )

    def reload(self) -> None:
        """Reload files from a directory."""
        output_path = os.path.abspath(self.settings.output)
        for root, dirs, files in os.walk(self.settings.directory):
            # Do not process again files classified in an output inside the input
            dirs[:] = [
                directory
                for directory in dirs
                if os.path.abspath(os.path.join(root, directory)) != output_path
            ]
            for file in files:
                file_path = os.path.join(root, file)
                file_relpath = os.path.relpath(file_path, self.settings.directory)
                if any(
                    re.match(pattern, file_relpath) for pattern in self.settings.exclude
                ):
                    _LOGGER.info("Exclude %s because of exclude pattern", file_relpath)
                    continue
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension in PICTURE_EXTENSIONS:
                    self.pictures.append(file_path)
                elif file_extension in VIDEO_EXTENSIONS:
                    self.videos.append(file_path)

    def remove_file(self, file_path: str) -> None:
        """Delete a file from disk and drop it from the lists to process."""
        if not self.settings.dry_run and os.path.exists(file_path):
            _LOGGER.debug("Remove %s", file_path)
            os.remove(file_path)
        if file_path in self.pictures:
            self.pictures.remove(file_path)
        elif file_path in self.videos:
            self.videos.remove(file_path)
        else:
            raise ClassifyException(f"File {file_path} not found in the list")

    def get_output_path(self, file: str) -> str:
        """Get the output path for a file."""
        if file in self.event_dirs:
            return os.path.join(self.settings.output, self.event_dirs[file])
        relpath = os.path.dirname(os.path.relpath(file, self.settings.directory))
        return os.path.join(self.settings.output, relpath)

    def get_date_from_name_format(self, file_path: str) -> datetime | None:
        """Get the date of a file named by this tool, with an optional suffix."""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        for name in (base_name, base_name[:-1]):
            try:
                date_taken = datetime.strptime(name, self.settings.name_format)
            except ValueError:
                continue
            if name == base_name or base_name[-1] in string.ascii_lowercase:
                # Names hold the local time
                return date_taken.replace(tzinfo=self.settings.user_timezone)
            return None
        return None

    def is_date_named(self, file_path: str) -> bool:
        """Check if a file is named from a date, with an optional duplicate suffix."""
        return self.get_date_from_name_format(file_path) is not None

    def iter_filepaths_from_date(
        self, dest_dir: str, date_taken: datetime, extension: str
    ) -> Iterator[str]:
        """Yield the file paths named from a date, then with a letter suffix."""
        base_name = date_taken.strftime(self.settings.name_format)
        for suffix in ["", *string.ascii_lowercase]:
            yield os.path.join(dest_dir, f"{base_name}{suffix}{extension}")

    def get_available_filepath_from_date(
        self,
        dest_dir: str,
        date_taken: datetime,
        extension: str,
        source_file: str | None = None,
    ) -> str:
        """Get an available file path named from a date.

        A letter is appended on name conflicts. The source file path is returned
        when it already has one of the candidate names.
        """
        for file_path in self.iter_filepaths_from_date(dest_dir, date_taken, extension):
            if source_file is not None and os.path.abspath(
                file_path
            ) == os.path.abspath(source_file):
                return file_path
            if not os.path.exists(file_path):
                return file_path
        raise ClassifyException(
            f"No available file name for {date_taken} in {dest_dir}"
        )

    def find_existing_copy(
        self,
        dest_dir: str,
        date_taken: datetime,
        extension: str,
        is_copy: Callable[[str], bool],
    ) -> str | None:
        """Find a file named from a date that is already a copy of the source."""
        for file_path in self.iter_filepaths_from_date(dest_dir, date_taken, extension):
            if os.path.exists(file_path) and is_copy(file_path):
                return file_path
        return None

    def tags_event(self, path: str) -> bool:
        """Check if the event name of a file is written in its metadata."""
        return path in self.event_names and self.metadata.enabled

    def tag_event(self, source: str, destination: str, identifier: str | None) -> None:
        """Write the event name of a source file in its destination metadata."""
        if self.tags_event(source):
            self.metadata.tag_event(destination, self.event_names[source], identifier)

    def is_copy(self, file_path: str, source: str) -> bool:
        """Check if a file is a copy of a source, maybe with an event name added."""
        if os.path.abspath(file_path) == os.path.abspath(source):
            return False
        if filecmp.cmp(file_path, source, shallow=False):
            return True
        return self.tags_event(source) and self.metadata.read_identifier(
            file_path
        ) == file_identifier(source)

    def place_in_output(self, path: str, date_taken: datetime, extension: str) -> None:
        """Copy or move a file to its date name in the output directory."""
        dest_dir_path = self.get_output_path(path)
        if self.settings.keep_original and (
            existing_copy := self.find_existing_copy(
                dest_dir=dest_dir_path,
                date_taken=date_taken,
                extension=extension,
                is_copy=lambda file_path: self.is_copy(file_path, path),
            )
        ):
            _LOGGER.debug("%s already copied to %s", path, existing_copy)
            return

        new_path = self.get_available_filepath_from_date(
            dest_dir=dest_dir_path,
            date_taken=date_taken,
            extension=extension,
            source_file=path,
        )
        if os.path.abspath(new_path) == os.path.abspath(path):
            _LOGGER.debug("Already named correctly")
            return

        if self.settings.keep_original:
            _LOGGER.info("Copy %s to %s", path, new_path)
        else:
            _LOGGER.info("Rename %s to %s", path, new_path)
        # The identifier recognizes the copy once its metadata changed
        identifier = file_identifier(path) if self.tags_event(path) else None
        if not self.settings.dry_run:
            os.makedirs(dest_dir_path, exist_ok=True)
            if self.settings.keep_original:
                shutil.copy2(path, new_path)
            else:
                # Unlike os.rename, works when the output is on another file system
                shutil.move(path, new_path)
        self.tag_event(path, new_path, identifier)

    def get_date_from_file_name(self, file_path: str) -> datetime | None:
        """Get the date from a file name, like PXL_20241010_174118780.mp4."""
        file_name = os.path.basename(file_path)
        for regex, date_format, is_utc in FILENAME_DATE_FORMATS:
            if not (date_match := re.search(regex, file_name, re.IGNORECASE)):
                continue
            _LOGGER.debug("Date taken from filename: %s", date_match.group(1))
            try:
                date_src = datetime.strptime(date_match.group(1), date_format)
            except ValueError:
                # Digits that are not a date, like a counter
                continue
            if "%H" not in date_format:
                date_src = date_src.replace(hour=DATE_ONLY_HOUR)
            if is_utc:
                return date_src.replace(tzinfo=UTC).astimezone(
                    self.settings.user_timezone
                )
            return date_src.replace(tzinfo=self.settings.user_timezone)
        return None

    def delete_android_trash_files(self) -> None:
        """Delete Android trash files."""
        for file_path in self.pictures + self.videos:
            file_name = os.path.basename(file_path)
            if file_name.startswith((".trashed", ".pending")):
                _LOGGER.info("Delete %s", file_name)
                self.remove_file(file_path)
