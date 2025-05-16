"""
This module provides a logger instance for the application.

When the main FastAPI application is run (via api.py), api.py configures
the root logger with handlers for console and file output (logs/app.log),
including a specific format. This logger module will detect that handlers
are already configured and will use that existing setup.

If modules using this logger (e.g., src.reader.reader) are run in a standalone
context where api.py has not configured global logging, this module will
set up a default console logger with a detailed format. This ensures that
logs are still visible during individual script execution or testing.
"""

import logging
import os
from dotenv import load_dotenv

load_dotenv()


def setup_logger():
    # Get log level from environment variable, default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Configure root logger
    logger = logging.getLogger()  # Get root logger

    # Only configure if no handlers are present, to avoid overriding api.py setup
    if not logger.hasHandlers():
        logger.setLevel(log_level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.info(
            "Default console logging configured by src.logger because no handlers were present."
        )
    else:
        # If handlers are already present (e.g., from api.py), just ensure the level is appropriate for this logger
        # Or, if api.py sets the root logger level, this specific logger instance will inherit it.
        # We can also choose to set a specific level for logs coming *through* this logger instance if desired.
        pass  # Assuming api.py has set levels and handlers appropriately

    return logger


# Create and configure the logger
logger = setup_logger()
