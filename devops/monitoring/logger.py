"""
==========================================================
MetricGuard - Logging Module
==========================================================

Purpose:
    Sets up a centralized logger for the entire monitoring
    system. All modules import `logger` from here to ensure
    consistent log formatting, file output, and console
    output.

What gets logged:
    - Collector startup and shutdown
    - Each metric collection cycle
    - API request successes and failures
    - Retry attempts
    - Backend connection issues
    - Unexpected errors

Log destinations:
    1. Console (stdout) — for real-time visibility
    2. File (logs/system.log) — for persistent history

Usage:
    from logger import logger
    logger.info("Collector started")
    logger.error("Backend unreachable: %s", error)
"""

import os
import logging
from config import Config


def setup_logger():
    """
    Create and configure the application-wide logger.

    Returns:
        logging.Logger: Configured logger instance.

    How it works:
        1. Creates a logger named 'MetricGuard'.
        2. Sets the log level from Config.LOG_LEVEL.
        3. Creates the logs/ directory if it doesn't exist.
        4. Adds a file handler  → logs/system.log
        5. Adds a console handler → stdout
        6. Both handlers use the same format:
           [timestamp] LEVEL - message
    """

    # Create the logger with a descriptive name
    app_logger = logging.getLogger("MetricGuard")

    # Convert the string level (e.g. "INFO") to a logging constant
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    app_logger.setLevel(log_level)

    # Prevent duplicate handlers if setup_logger() is called twice
    if app_logger.handlers:
        return app_logger

    # --------------------------------------------------
    # Log format: [2026-05-16 14:00:00] INFO - message
    # --------------------------------------------------
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------
    # File Handler — writes to logs/system.log
    # --------------------------------------------------
    # Ensure the logs directory exists
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # --------------------------------------------------
    # Console Handler — prints to terminal
    # --------------------------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Attach both handlers to the logger
    app_logger.addHandler(file_handler)
    app_logger.addHandler(console_handler)

    return app_logger


# --------------------------------------------------
# Create the logger instance on import
# --------------------------------------------------
# Other modules simply do:  from logger import logger
logger = setup_logger()
