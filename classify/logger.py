"""Custom logger module"""

import logging


class CustomFormatter(logging.Formatter):
    """Custom log formatter"""

    grey = "\x1b[90;20m"
    white = "\x1b[97;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    log_format = "[%(asctime)s][%(levelname)s] %(message)s"

    FORMATS = {
        logging.DEBUG: grey + log_format + reset,
        logging.INFO: white + log_format + reset,
        logging.WARNING: yellow + log_format + reset,
        logging.ERROR: red + log_format + reset,
        logging.CRITICAL: bold_red + log_format + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record"""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def print_progress_bar(
    iteration: int,
    total: int,
    prefix: str = "",
    suffix: str = "",
    decimals: int = 1,
    length: int = 100,
    fill: str = "█",
    print_end: str = "\r",
) -> None:
    """Print progress bar."""
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    progess_bar = fill * filled_length + "-" * (length - filled_length)
    print(f"\r{prefix} |{progess_bar}| {percent}% {suffix}", end=print_end)
    if iteration == total:
        print()
