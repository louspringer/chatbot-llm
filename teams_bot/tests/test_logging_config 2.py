"""
# Ontology: cortexteams:LoggingConfigTest
# Implements: cortexteams:Logging
# Requirement: REQ-BOT-005 Logging configuration
# Guidance: guidance:BotPatterns#Logging
# Description: Tests for logging configuration
"""

import io
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teams_bot.bot.logging_config import (
    ContextFilter,
    LogContext,
    TeamsLogFormatter,
    configure_logging,
    get_logger,
)


@pytest.fixture
def temp_log_file():
    """Create a temporary log file."""
    log_file = Path("test.log")
    yield log_file
    if log_file.exists():
        log_file.unlink()


@pytest.fixture
def capture_logs():
    """Capture log output for testing."""
    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    yield log_output

    logger.removeHandler(handler)
    logger.setLevel(logging.WARNING)


def test_configure_logging_basic():
    """Test basic logging configuration."""
    logger = configure_logging()
    assert logger.level == logging.INFO

    # Verify handler configuration
    assert len(logger.handlers) > 0
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert isinstance(handler.formatter, TeamsLogFormatter)


def test_configure_logging_with_file(temp_log_file):
    """Test logging configuration with file output."""
    logger = configure_logging(log_file=temp_log_file)

    # Verify file handler
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].baseFilename == str(temp_log_file)


def test_configure_logging_custom_format():
    """Test logging with custom format string."""
    custom_format = "%(levelname)s - %(message)s"
    logger = configure_logging(format_string=custom_format)

    # Verify formatter
    handler = logger.handlers[0]
    assert handler.formatter._fmt == custom_format


def test_get_logger():
    """Test logger retrieval."""
    logger = get_logger(__name__)
    assert logger.name == __name__


def test_log_context():
    """Test logging context manager."""
    with LogContext(correlation_id="test-id"):
        logger = get_logger(__name__)
        assert logger.handlers[0].formatter.correlation_id == "test-id"


def test_log_context_exception():
    """Test logging context with exception."""
    with pytest.raises(ValueError):
        with LogContext(correlation_id="test-id"):
            raise ValueError("Test error")


def test_context_filter():
    """Test context filter functionality."""
    context_filter = ContextFilter()
    record = logging.LogRecord(
        "test", logging.INFO, "test.py", 10, "Test message", None, None
    )

    # Test without context
    context_filter.filter(record)
    assert not hasattr(record, "correlation_id")

    # Test with context
    with LogContext(correlation_id="test-id"):
        context_filter.filter(record)
        assert record.correlation_id == "test-id"


def test_teams_log_formatter():
    """Test Teams log formatter."""
    formatter = TeamsLogFormatter()
    record = logging.LogRecord(
        "test", logging.INFO, "test.py", 10, "Test message", None, None
    )

    # Test basic formatting
    output = formatter.format(record)
    assert "Test message" in output
    assert "INFO" in output


def test_configure_logging_invalid_level():
    """Test logging configuration with invalid level."""
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging(log_level="INVALID")


def test_configure_logging_specific_loggers():
    """Test configuration of specific logger levels."""
    configure_logging()

    # Check specific logger levels
    assert logging.getLogger("azure").level == logging.WARNING
    assert logging.getLogger("botbuilder").level == logging.INFO
    assert logging.getLogger("aiohttp").level == logging.WARNING


def test_configure_logging_with_file(temp_log_file):
    """Test logging configuration with file output."""
    context_filter = configure_logging(log_file=temp_log_file)

    # Check log file creation
    assert Path(temp_log_file).exists()

    # Write test log and verify
    logger = logging.getLogger()
    test_message = "Test file message"
    with context_filter.context(correlation_id="TEST-123", conversation_id="CONV-123"):
        logger.info(test_message)

    with open(temp_log_file, "r") as f:
        content = f.read()
        assert test_message in content
        assert "TEST-123" in content
        assert "CONV-123" in content


def test_configure_logging_custom_format():
    """Test logging configuration with custom format."""
    # Create a string buffer to capture output
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    
    # Configure logging with custom format
    custom_format = "%(levelname)s - %(correlation_id)s - %(message)s"
    context_filter = configure_logging(log_format=custom_format)
    
    # Get the root logger and add our capture handler
    logger = logging.getLogger()
    handler.setFormatter(TeamsLogFormatter(custom_format))
    logger.addHandler(handler)
    
    # Log a test message with context
    test_message = "Test format"
    with context_filter.context(correlation_id="TEST-123"):
        logger.info(test_message)
    
    # Verify the output
    log_output = output.getvalue()
    assert "INFO - TEST-123 - Test format" in log_output
    
    # Clean up
    logger.removeHandler(handler)
    output.close()


def test_get_logger():
    """Test getting a logger."""
    logger_name = "test_logger"
    logger = get_logger(logger_name)

    assert isinstance(logger, logging.Logger)
    assert logger.name == logger_name


def test_log_context():
    """Test log context manager."""
    logger = logging.getLogger("test_context")
    original_level = logging.INFO
    temp_level = logging.DEBUG

    logger.setLevel(original_level)
    assert logger.level == original_level

    with LogContext(logger, temp_level):
        assert logger.level == temp_level

    assert logger.level == original_level


def test_log_context_exception():
    """Test log context manager with exception."""
    logger = logging.getLogger("test_context_exception")
    original_level = logging.INFO
    temp_level = logging.DEBUG

    logger.setLevel(original_level)

    try:
        with LogContext(logger, temp_level):
            assert logger.level == temp_level
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Level should be restored even after exception
    assert logger.level == original_level


def test_configure_logging_specific_loggers():
    """Test configuration of specific logger levels."""
    configure_logging()

    # Check specific logger levels
    assert logging.getLogger("azure").level == logging.WARNING
    assert logging.getLogger("botbuilder").level == logging.INFO
    assert logging.getLogger("aiohttp").level == logging.WARNING


def test_context_filter():
    """Test context filter functionality."""
    context_filter = ContextFilter()

    # Test empty context
    record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
    assert context_filter.filter(record)
    assert not hasattr(record, "custom_context")

    # Test with context
    with context_filter.context(custom_context="test_value"):
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test message", (), None
        )
        assert context_filter.filter(record)
        assert getattr(record, "custom_context") == "test_value"

    # Test context is cleared
    record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
    assert context_filter.filter(record)
    assert not hasattr(record, "custom_context")


def test_teams_log_formatter():
    """Test Teams log formatter."""
    formatter = TeamsLogFormatter("%(correlation_id)s - %(conversation_id)s")
    record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)

    # Test default values
    formatted = formatter.format(record)
    assert "NO-CORRELATION-ID" in formatted
    assert "NO-CONVERSATION-ID" in formatted

    # Test with custom values
    record.correlation_id = "TEST-123"
    record.conversation_id = "CONV-123"
    formatted = formatter.format(record)
    assert "TEST-123" in formatted
    assert "CONV-123" in formatted 
