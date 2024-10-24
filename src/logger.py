import logging
import os
from dotenv import load_dotenv

load_dotenv()


def setup_logger():
    # Get log level from environment variable, default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Create and configure the logger
logger = setup_logger()
