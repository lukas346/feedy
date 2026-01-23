"""Logging configuration with rotating file handlers."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    name: str = "reader",
    log_dir: Optional[str] = None,
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure logging with both console and rotating file handlers.

    Args:
        name: Logger name and base name for log files.
        log_dir: Directory for log files. Defaults to /app/logs or ./logs.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of backup files to keep.

    Returns:
        Configured logger instance.
    """
    # Determine log directory
    if log_dir is None:
        default_log_dir = "/app/logs" if Path("/app").exists() else "./logs"
        log_dir = os.environ.get("LOG_DIR", default_log_dir)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler for all logs
    all_log_file = log_path / f"{name}.log"
    file_handler = RotatingFileHandler(
        all_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Separate rotating file handler for errors only
    error_log_file = log_path / f"{name}.error.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Return named logger
    logger = logging.getLogger(name)
    logger.info(f"Logging configured: level={log_level}, log_dir={log_path}")

    return logger
