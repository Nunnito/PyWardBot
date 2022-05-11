import logging
import sys


# Idea taken from https://stackoverflow.com/a/56944256
class ColorFormatter(logging.Formatter):
    """ Logging Formatter to add colors """

    # Custom colors (Only works on Linux and macOS)
    if sys.platform.startswith("linux") or sys.platform.startswith("darwin"):
        red = "\x1b[31;21m"
        green = "\x1b[32;21m"
        blue = "\x1b[34;21m"
        yellow = "\x1b[33;21m"
        grey = "\x1b[38;21m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"
    else:
        red = ""
        green = ""
        blue = ""
        yellow = ""
        grey = ""
        bold_red = ""
        reset = ""

    format = "%(asctime)s - %(module)s:%(lineno)d - %(levelname)s: %(message)s"
    date_format = "%d-%m-%Y %H:%M:%S"

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt=self.date_format)
        return formatter.format(record)


# TODO: Use the config file log level

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(ColorFormatter())

# Create logger
logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
