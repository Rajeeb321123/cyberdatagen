# nlp2opt/utils/logger_config.py

import logging
import os
from datetime import datetime


LOG_LEVEL = LOG_LEVEL = logging.INFO


timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


def setup_logger():
    """
    Sets up a logger with both console and file handlers.

    Args:
        LOG_LEVEL (int): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger("nlp2opt")  # Use 'omnisage' as the root logger name
    logger.setLevel(LOG_LEVEL)

    # Prevent duplicate handlers if logger is reloaded
    if logger.hasHandlers():
        logger.handlers.clear()

    # Define formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s() - %(message)s"
    )

    # # Define formatter
    # formatter = logging.Formatter(
    #     "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # )
    # formatter = logging.Formatter(
    #     "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s"
    # )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)

    return logger
