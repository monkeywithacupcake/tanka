"""Logging setup for HaikuBox downloader"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_old_logs(log_dir: Path, max_age_days: int = 7):
    """
    Delete log files older than max_age_days

    Args:
        log_dir: Directory containing log files
        max_age_days: Delete logs older than this many days (default 7)
    """
    if not log_dir or not log_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=max_age_days)

    for log_file in log_dir.glob("haikubox_*.log"):
        # Extract date from filename (format: haikubox_YYYYMMDD.log)
        try:
            date_str = log_file.stem.replace("haikubox_", "")
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if file_date < cutoff:
                log_file.unlink()
        except (ValueError, OSError):
            # Skip files that don't match expected format or can't be deleted
            pass


def setup_logging(log_level: str = "INFO", log_dir: Path = None):
    """
    Configure logging for the application

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. If None, only console logging is used
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log_dir specified)
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old logs
        cleanup_old_logs(log_dir)

        # Create log file with current date
        log_filename = f"haikubox_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = log_dir / log_filename

        file_handler = logging.FileHandler(log_filepath)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {log_filepath}")

    return root_logger
