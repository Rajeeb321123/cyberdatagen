# cyberdata/utils/logger_config.py

import logging
import os
from datetime import datetime
from pathlib import Path

# Get the project root directory (parent of parent of current file)
CURRENT_DIR = Path(__file__).parent  # utils/
CYBERDATA_DIR = CURRENT_DIR.parent   # src/cyberdata/
SRC_DIR = CYBERDATA_DIR.parent       # src/
PROJECT_ROOT = SRC_DIR.parent        # project root (parent of src/)

# Create logs directory at project root level (same level as src/)
LOGS_DIR = PROJECT_ROOT / "logs"

# Create logs directory if it doesn't exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Default log level
LOG_LEVEL = logging.INFO

def setup_logger(name="cyberdata", log_level=LOG_LEVEL):
    """
    Sets up a logger with both console and file handlers.

    Args:
        name (str): Logger name, used to organize logs by module.
        log_level (int): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers if logger is reloaded
    if logger.hasHandlers():
        logger.handlers.clear()

    # Define formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s() - %(message)s"
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # File Handler - use timestamp for unique log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"{name}_{timestamp}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logger initialized. Logs will be saved to {log_file}")
    logger.debug(f"Log directory: {LOGS_DIR}")
    
    return logger