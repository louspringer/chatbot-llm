"""
# Ontology: cortexteams:LoggingConfigTest
# Implements: cortexteams:Logging
# Requirement: REQ-BOT-004 Logging configuration
# Guidance: guidance:BotPatterns#Logging
# Description: Tests for logging configuration
"""

import logging
import os
import tempfile
from pathlib import Path
import io

import pytest

from teams_bot.bot.logging_config import (
    configure_logging,
    get_logger,
    LogContext,
    TeamsLogFormatter,
    ContextFilter
)


@pytest.fixture
def temp_log_file():
    """Create a temporary log file."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        yield f.name
    # Clean up after test
    try:
        os.unlink(f.name)
    except OSError:
        pass


@pytest.fixture
def capture_logs():
    """Capture log output."""
    # Create a string buffer to capture log output
    string_buffer = io.StringIO()
    
    # Create and configure a handler that writes to the buffer
    handler = logging.StreamHandler(string_buffer)
    handler.setLevel(logging.DEBUG)
    
    # Create a simple formatter that matches our test cases
    handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Add the handler to the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    # Yield both the buffer and handler for cleanup
    yield string_buffer
    
    # Clean up
    root_logger.removeHandler(handler)
    string_buffer.close()


def test_configure_logging_basic():
    """Test basic logging configuration."""
    configure_logging()
    logger = logging.getLogger()

    # Check root logger level
    assert logger.level == logging.INFO

    # Check that we have at least one handler
    assert logger.handlers
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    # Check that context filter is applied
    assert any(
        isinstance(f, ContextFilter)
        for h in logger.handlers
        for f in h.filters
    )


def test_configure_logging_with_file(temp_log_file):
    """Test logging configuration with file output."""
    context_filter = configure_logging(log_file=temp_log_file)

    # Check log file creation
    assert Path(temp_log_file).exists()

    # Write test log and verify
    logger = logging.getLogger()
    test_message = "Test file message"
    with context_filter.context(
        correlation_id="TEST-123",
        conversation_id="CONV-123"
    ):
        logger.info(test_message)

    with open(temp_log_file, "r") as f:
        content = f.read()
        assert test_message in content
        assert "TEST-123" in content
        assert "CONV-123" in content


def test_configure_logging_invalid_level():
    """Test logging configuration with invalid level."""
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging(log_level="INVALID")


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
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "test message", (), None
    )
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
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "test message", (), None
    )
    assert context_filter.filter(record)
    assert not hasattr(record, "custom_context")


def test_teams_log_formatter():
    """Test Teams log formatter."""
    formatter = TeamsLogFormatter("%(correlation_id)s - %(conversation_id)s")
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "test message", (), None
    )

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