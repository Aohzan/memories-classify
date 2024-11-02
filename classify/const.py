"""Constants."""

PICTURE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

VIDEO_CODEC = "hevc"
VIDEO_BITRATE_LIMIT = 10 * 1000 * 1000

DEFAULT_NAME_FORMAT = "%Y-%m-%d-%Hh%Mm%S"

DEFAULT_FFMPEG_PATH = "ffmpeg"
DEFAULT_FFMPEG_INPUT_EXTRA_ARGS = ""
DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS = ""
DEFAULT_FFPROBE_PATH = "ffprobe"
