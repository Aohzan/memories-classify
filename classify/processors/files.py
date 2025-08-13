"""Files management for Classify."""

import logging
import os
import re
from datetime import datetime

from classify.settings import ClassifySettings

from ..const import PICTURE_EXTENSIONS, VIDEO_EXTENSIONS
from ..exception import ClassifyException

_LOGGER = logging.getLogger("classify")


class FileProcessor:
    """Files processor for Classify."""

    pictures: list[str] = []
    videos: list[str] = []

    def __init__(self, settings: ClassifySettings) -> None:
        """Init."""
        self.settings = settings

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
            # files_root_directory = sroot
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

    def remove_file(self, file: str) -> None:
        """Remove a file from the list."""
        if not self.settings.dry_run:
            full_path = os.path.join(self.settings.directory, file)
            if os.path.exists(full_path):
                _LOGGER.debug("Remove %s", full_path)
                os.remove(full_path)
        if self.settings.directory == self.settings.output:
            if file in self.pictures:
                self.pictures.remove(file)
            elif file in self.videos:
                self.videos.remove(file)
            else:
                raise ClassifyException(f"File {file} not found in the list")

    def get_output_path(self, file: str) -> str:
        """Get the output path for a file."""
        relpath = os.path.dirname(os.path.relpath(file, self.settings.directory))
        return os.path.join(self.settings.output, relpath)

    def get_available_filepath_from_date(
        self, source_file: str, dest_dir: str, date_taken: datetime
    ) -> str:
        """Get an available  filename from a date."""
        extension = os.path.splitext(source_file)[1].lower()
        if extension == ".jpeg":
            extension = ".jpg"

        new_file_name = "".join(
            [
                date_taken.strftime(self.settings.name_format),
                extension,
            ]
        )
        new_file_path = os.path.join(dest_dir, new_file_name)
        counter = 97  # ASCII code for 'a'
        while os.path.exists(new_file_path) and new_file_path != source_file:
            new_file_name = "".join(
                [
                    date_taken.strftime(self.settings.name_format),
                    chr(counter),
                    extension,
                ]
            )
            new_file_path = os.path.join(dest_dir, new_file_name)
            counter += 1
        return new_file_path

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
            if file_name.startswith(".trashed") or file_name.startswith(".pending"):
                _LOGGER.info("Delete %s", file_name)
                if not self.settings.dry_run:
                    os.remove(file_path)
                self.remove_file(file_path)
