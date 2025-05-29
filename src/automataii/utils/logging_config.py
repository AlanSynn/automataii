import logging
import os
from pathlib import Path

def setup_logging():
    """
    Configure logging for the AutomataII application.
    Sets up both file and console logging with appropriate formatting.
    """
    # Create logs directory if it doesn't exist
    log_dir = Path('./logs')
    log_dir.mkdir(exist_ok=True, parents=True)

    # Configure file handler
    file_handler = logging.FileHandler(log_dir / 'automataii.log')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Get root logger and configure it
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicate logging
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("Logging system initialized")
