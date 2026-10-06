"""Constants."""

PICTURE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

VIDEO_CODEC = "hevc"

FILENAME_DATE_FORMATS = {
    r"(\d{8}_\d{9})": "%Y%m%d_%H%M%S%f",
    r"(\d{8}-\d{9})": "%Y%m%d-%H%M%S%f",
    r"(\d{14})": "%Y%m%d%H%M%S",
}

DEFAULT_NAME_FORMAT = "%Y-%m-%d-%Hh%Mm%S"

DEFAULT_COMMENT_MESSAGE = "Processed by memories-classify"

DEFAULT_VIDEO_BITRATE_MBPS_LIMIT = 30

DEFAULT_FFMPEG_PATH = "ffmpeg"
DEFAULT_FFMPEG_INPUT_EXTRA_ARGS = ""
DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS = ""
DEFAULT_FFPROBE_PATH = "ffprobe"
