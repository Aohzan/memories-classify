"""Files management for Classify."""

import logging
import os
import re
import string
from datetime import datetime

from classify.settings import ClassifySettings

from ..const import PICTURE_EXTENSIONS, VIDEO_EXTENSIONS
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
        base_name = date_taken.strftime(self.settings.name_format)
        for suffix in ["", *string.ascii_lowercase]:
            file_path = os.path.join(dest_dir, f"{base_name}{suffix}{extension}")
            if source_file is not None and os.path.abspath(
                file_path
            ) == os.path.abspath(source_file):
                return file_path
            if not os.path.exists(file_path):
                return file_path
        raise ClassifyException(f"No available file name for {base_name} in {dest_dir}")

    def get_date_from_file_name(self, file_path: str) -> datetime | None:
        """Adjust creation and modification date of a file based on its name."""
        base_name = os.path.splitext(file_path)[0]
        if re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}h\d{2}m\d{2}[a-z]?$", base_name):
            return datetime.strptime(base_name[:19], self.settings.name_format)
        return None

    def delete_android_trash_files(self) -> None:
        """Delete Android trash files."""
        for file_path in self.pictures + self.videos:
            file_name = os.path.basename(file_path)
            if file_name.startswith((".trashed", ".pending")):
                _LOGGER.info("Delete %s", file_name)
                self.remove_file(file_path)
