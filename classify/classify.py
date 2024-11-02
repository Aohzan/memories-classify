"""Main function to classify pictures and videos."""

import logging
import os

from .files import ClassifyFiles, delete_trash_files
from .photo import rename_photo_from_date_taken
from .settings import ClassifySettings
from .video import (
    EncodingException,
    check_video_already_encoded,
    choose_between_original_and_encoded,
    encode_video,
    get_date_taken_from_video,
)

_LOGGER = logging.getLogger("classify")


def classify(settings: ClassifySettings) -> None:
    """Classify pictures and videos."""
    files = ClassifyFiles(directory=settings.directory)

    if not files.pictures and not files.videos:
        return

    _LOGGER.info("##### Clean Android Google Photo trashed and pending pictures uploaded #####")
    delete_trash_files(files, settings.dry_run)

    _LOGGER.info("")
    _LOGGER.info("##### Pictures #####")
    _LOGGER.info("Rename pictures according to date taken")
    picture_count = 1
    for picture_path in files.pictures:
        _LOGGER.info(
            "[%s%%] Process picture %s",
            int(picture_count * 100 / len(files.pictures)),
            picture_path,
        )
        rename_photo_from_date_taken(
            path=picture_path,
            name_format=settings.name_format,
            dry_run=settings.dry_run,
        )

        picture_count += 1

    _LOGGER.info("")
    _LOGGER.info("##### Videos #####")
    _LOGGER.info("Encode videos to HEVC with a preset to reduce file size")
    video_count = 1
    for video_path in files.videos:
        video_file_name = os.path.basename(video_path)
        _LOGGER.info(
            "[%s%%] Process video %s (%s GB)",
            int(video_count * 100 / len(files.videos)),
            video_file_name,
            round(os.path.getsize(video_path) / 1e9, 3),
        )
        video_count += 1

        # check if video has already been encoded
        if check_video_already_encoded(video_path):
            _LOGGER.debug("\tVideo already encoded")
            continue

        # get date taken from video
        video_date_taken = get_date_taken_from_video(video_path)
        _LOGGER.debug("\tVideo %s taken on %s", video_file_name, video_date_taken)
        encoded_file_name = f"{video_date_taken.strftime(settings.name_format)}.mp4"
        encoded_file_path = os.path.join(os.path.dirname(video_path), encoded_file_name)

        if os.path.exists(encoded_file_path):
            _LOGGER.warning("\tDelete existing target file %s", encoded_file_path)
            if not settings.dry_run:
                os.remove(encoded_file_path)
            files.remove_file(encoded_file_path)

        # encode file
        _LOGGER.info("\tEncoding video %s to %s", video_file_name, encoded_file_name)
        try:
            encode_video(
                input_path=video_path,
                output_path=encoded_file_path,
                ffmpeg_path=settings.ffmpeg_path,
                ffmpeg_input_extra_args=settings.ffmpeg_input_extra_args,
                ffmpeg_output_extra_args=settings.ffmpeg_output_extra_args,
                dry_run=settings.dry_run,
            )
        except EncodingException as e:
            _LOGGER.error("\tError while encoding video: %s", e)
            continue

        choose_between_original_and_encoded(
            video_path=video_path,
            encoded_file_path=encoded_file_path,
            dry_run=settings.dry_run,
        )

    # TODO creation data not working
    # _LOGGER.info("##### Files date adjustment #####")
    # for file_path in pictures + videos:
    #         file_extension = os.path.splitext(file)[1].lower()
    #         if file_extension in (PICTURE_EXTENSIONS + VIDEO_EXTENSIONS):
    #             if filename_date := get_date_from_file_name(file, args.name_format):
    #                 file_path = os.path.join(root, file)
    #                 _LOGGER.debug(filename_date)
    #                 _LOGGER.debug(datetime.fromtimestamp(os.path.getctime(file_path)))
    #                 _LOGGER.debug(datetime.fromtimestamp(os.path.getmtime(file_path)))
    #                 if filename_date.timestamp() != os.path.getctime(
    #                     file_path
    #                 ) or filename_date.timestamp() != os.path.getmtime(file_path):
    #                     # os.utime(
    #                     #     file_path, (filename_date.timestamp(), filename_date.timestamp())
    #                     # )
    #                     filedate_file = filedate.File(file_path)
    #                     filedate_file.created = filename_date
    #                     filedate_file.modified = filename_date
    #                     filedate_file.accessed = filename_date.strftime(
    #                         "%d.%m.%Y %H:%M"
    #                     )
    #                     _LOGGER.info(
    #                         "File date of %s updated to %s",
    #                         file,
    #                         filename_date,
    #                     )
