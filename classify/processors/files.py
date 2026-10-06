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

from ..const import FILENAME_DATE_FORMATS, PICTURE_EXTENSIONS, VIDEO_EXTENSIONS
from ..exception import ClassifyException

_LOGGER = logging.getLogger("classify")


class FileProcessor:
    """Files processor for Classify."""

    pictures: list[str]
    videos: list[str]

    def __init__(self, settings: ClassifySettings) -> None:
        """Init."""
        self.settings = settings
        self.pictures = []
        self.videos = []

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
        for root, _, files in os.walk(self.settings.directory):
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
        relpath = os.path.dirname(os.path.relpath(file, self.settings.directory))
        return os.path.join(self.settings.output, relpath)

    def is_date_named(self, file_path: str) -> bool:
        """Check if a file is named from a date, with an optional duplicate suffix."""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        for name in (base_name, base_name[:-1]):
            try:
                datetime.strptime(name, self.settings.name_format)
            except ValueError:
                continue
            return name == base_name or base_name[-1] in string.ascii_lowercase
        return False

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

    def place_in_output(self, path: str, date_taken: datetime, extension: str) -> None:
        """Copy or move a file to its date name in the output directory."""
        dest_dir_path = self.get_output_path(path)
        if self.settings.keep_original and (
            existing_copy := self.find_existing_copy(
                dest_dir=dest_dir_path,
                date_taken=date_taken,
                extension=extension,
                is_copy=lambda file_path: (
                    os.path.abspath(file_path) != os.path.abspath(path)
                    and filecmp.cmp(file_path, path, shallow=False)
                ),
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
        if self.settings.dry_run:
            return
        os.makedirs(dest_dir_path, exist_ok=True)
        if self.settings.keep_original:
            shutil.copy2(path, new_path)
        else:
            # Unlike os.rename, works when the output is on another file system
            shutil.move(path, new_path)

    def get_date_from_file_name(self, file_path: str) -> datetime | None:
        """Get the date from a file name, like PXL_20241010_174118780.mp4."""
        file_name = os.path.basename(file_path)
        for regex, date_format in FILENAME_DATE_FORMATS.items():
            if date_match := re.search(regex, file_name):
                _LOGGER.debug("Date taken from filename: %s", date_match.group(0))
                # Phone file names hold the UTC time
                date_src = datetime.strptime(date_match.group(0), date_format).replace(
                    tzinfo=UTC
                )
                return date_src.astimezone(self.settings.user_timezone)
        return None

    def delete_android_trash_files(self) -> None:
        """Delete Android trash files."""
        for file_path in self.pictures + self.videos:
            file_name = os.path.basename(file_path)
            if file_name.startswith((".trashed", ".pending")):
                _LOGGER.info("Delete %s", file_name)
                self.remove_file(file_path)
