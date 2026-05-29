import logging


def setup_logging(console_log_level: int = logging.INFO) -> None:
    """
    Configure logging for the AutomataII application.
    Sets up both file and console logging with appropriate formatting.

    Args:
        console_log_level (int): The logging level for the console handler.
                                 Defaults to logging.INFO.
    """
    # Create logs directory if it doesn't exist
    from .paths import get_app_data_dir

    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)

    # Configure file handler (always DEBUG)
    file_handler = logging.FileHandler(
        log_dir / "automataii.log", mode="a"
    )  # Append mode
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(name)-25s - %(module)-20s - %(funcName)-25s - L%(lineno)-4d - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_log_level)  # Use passed level
    console_formatter = logging.Formatter(
        "%(levelname)s: [%(name)s] %(message)s"
    )  # Slightly more info for console
    console_handler.setFormatter(console_formatter)

    # Get root logger and configure it
    # Set root logger to the lowest level of its handlers to capture all messages
    root_logger_level = min(logging.DEBUG, console_log_level)
    root_logger = logging.getLogger()  # Get the root logger
    root_logger.setLevel(root_logger_level)

    # Remove any existing handlers to avoid duplicate logging if this is called multiple times
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # logging.info("Logging system initialized") # This will log with the new settings
    # Initial log to confirm setup, will go to both handlers based on their levels.
    # logging.getLogger(__name__).info(f"Logging configured. Console level: {logging.getLevelName(console_log_level)}, File level: DEBUG")

    # Configure dedicated telemetry logger for structured span output
    telemetry_logger = logging.getLogger("automataii.telemetry")
    telemetry_logger.setLevel(logging.INFO)
    telemetry_logger.handlers.clear()

    telemetry_handler = logging.FileHandler(log_dir / "telemetry.log", mode="a")
    telemetry_handler.setLevel(logging.INFO)
    telemetry_handler.setFormatter(logging.Formatter("%(message)s"))
    telemetry_logger.addHandler(telemetry_handler)
    telemetry_logger.propagate = False
