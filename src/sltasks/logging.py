"""Logging configuration for sltasks."""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path


def setup_logging(verbose: int = 0, log_file: Path | None = None) -> None:
    """Configure logging based on verbosity level and optional file output.

    Args:
        verbose: Verbosity level (0=off, 1=INFO, 2+=DEBUG)
        log_file: Optional path to write logs to file
    """
    if verbose == 0 and log_file is None:
        # No logging requested
        return

    # Determine log level
    if verbose >= 2:
        level = logging.DEBUG
    elif verbose >= 1:
        level = logging.INFO
    else:
        # Only file logging requested without verbosity
        level = logging.INFO

    # Configure root logger for sltasks namespace
    logger = logging.getLogger("sltasks")
    logger.setLevel(level)

    # Detailed format: timestamp - module - level - message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add stderr handler if verbose
    if verbose > 0:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(level)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)

    # Add file handler if log_file specified
    if log_file is not None:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Log startup delimiter with timestamp
    level_name = "DEBUG" if verbose >= 2 else "INFO"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info("")
    logger.info("=" * 60)
    logger.info("sltasks starting | %s | level=%s", timestamp, level_name)
    logger.info("=" * 60)
