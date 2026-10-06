"""Constants."""

PICTURE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

VIDEO_CODEC = "hevc"

# Dates in file names: regex capturing the date, its format, and whether it is UTC
# The first matching regex wins, longer formats come first
FILENAME_DATE_FORMATS: list[tuple[str, str, bool]] = [
    # Google Pixel, like PXL_20241014_165237438.jpg, in UTC
    (r"(\d{8}_\d{9})", "%Y%m%d_%H%M%S%f", True),
    (r"(\d{8}-\d{9})", "%Y%m%d-%H%M%S%f", True),
    # Samsung and others, like 20260925_060641.jpg, in local time
    (r"(\d{8}_\d{6})", "%Y%m%d_%H%M%S", False),
    # Oppo, OnePlus and others, like IMG20260910101833.jpg, in local time
    (r"(\d{14})", "%Y%m%d%H%M%S", False),
    # WhatsApp, like IMG-20260924-WA0004.jpg, without time
    (r"(\d{8})-WA\d+", "%Y%m%d", False),
]

# Time of the files named with a date only
DATE_ONLY_HOUR = 12

DEFAULT_NAME_FORMAT = "%Y-%m-%d-%Hh%Mm%S"

DEFAULT_COMMENT_MESSAGE = "Processed by memories-classify"

DEFAULT_VIDEO_BITRATE_MBPS_LIMIT = 30

DEFAULT_FFMPEG_PATH = "ffmpeg"
DEFAULT_FFMPEG_INPUT_EXTRA_ARGS = ""
DEFAULT_FFMPEG_OUTPUT_EXTRA_ARGS = ""
DEFAULT_FFPROBE_PATH = "ffprobe"
DEFAULT_EXIFTOOL_PATH = "exiftool"

CONFIG_FILE_NAME = "memories-classify.yaml"
EVENTS_STATE_FILE_NAME = ".memories-classify-events.yaml"

# Default values of the user configuration file
DEFAULT_HOME_RADIUS_KM = 50
DEFAULT_TRIP_MAX_GAP_HOURS = 48
DEFAULT_TRIP_MIN_DAYS = 2
DEFAULT_TRIP_MIN_FILES = 10
DEFAULT_BURST_MAX_GAP_HOURS = 3
DEFAULT_BURST_MIN_FILES = 15
DEFAULT_HOLIDAY_MIN_FILES = 5
DEFAULT_SKI_MIN_ALTITUDE_M = 1000
DEFAULT_PREVIEW_COUNT = 12

# Trip kinds detection
SKI_MONTHS = (12, 1, 2, 3, 4)
ROAD_TRIP_MIN_CITIES = 3
ROAD_TRIP_MIN_CITY_SHARE = 0.1
ROAD_TRIP_MIN_SPREAD_KM = 100
WEEKEND_MAX_DAYS = 3
# Friday and Saturday
WEEKEND_START_WEEKDAYS = (4, 5)
