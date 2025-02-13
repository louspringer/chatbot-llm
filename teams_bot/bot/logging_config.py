"""
# Ontology: cortexteams:LoggingConfig
# Implements: cortexteams:Logging
# Requirement: REQ-BOT-004 Logging configuration
# Guidance: guidance:BotPatterns#Logging
# Description: Logging configuration for the Teams bot
"""

import logging
import logging.handlers
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional


@dataclass
class LogContext:
    """Context manager for temporarily changing log level."""

    logger: logging.Logger
    level: int
    previous_level: int = field(init=False)

    def __post_init__(self):
        """Initialize previous level."""
        self.previous_level = self.logger.level

    def __enter__(self) -> logging.Logger:
        """Set temporary log level."""
        self.logger.setLevel(self.level)
        return self.logger

    def __exit__(self, *args) -> None:
        """Restore previous log level."""
        self.logger.setLevel(self.previous_level)


class ContextFilter(logging.Filter):
    """Filter that adds context data to log records."""

    def __init__(self):
        """Initialize the filter."""
        super().__init__()
        self._context = threading.local()
        self._context.data = {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context data to the record."""
        context_data = getattr(self._context, "data", {})
        for key, value in context_data.items():
            setattr(record, key, value)
        return True

    @contextmanager
    def context(self, **kwargs) -> Generator[None, None, None]:
        """Context manager for adding context data."""
        old_data = getattr(self._context, "data", {}).copy()
        self._context.data = {**old_data, **kwargs}
        try:
            yield
        finally:
            self._context.data = old_data


class TeamsLogFormatter(logging.Formatter):
    """Custom formatter for Teams bot logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the record with context data."""
        # Add correlation ID if not present
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "NO-CORRELATION-ID"

        # Add conversation ID if not present
        if not hasattr(record, "conversation_id"):
            record.conversation_id = "NO-CONVERSATION-ID"

        return super().format(record)


def configure_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = (
        "%(asctime)s [%(correlation_id)s] [%(conversation_id)s] "
        "%(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    ),
) -> ContextFilter:
    """Configure logging for the application.

    Args:
        log_level: The logging level (default: INFO)
        log_file: Optional path to log file
        log_format: The log message format

    Returns:
        The context filter for adding context data
    """
    # Convert string level to logging level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # Create context filter
    context_filter = ContextFilter()

    # Create formatter
    formatter = TeamsLogFormatter(log_format)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    # Add file handler if log file specified
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

    # Set logging level for specific loggers
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("botbuilder").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    return context_filter


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: The logger name

    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
