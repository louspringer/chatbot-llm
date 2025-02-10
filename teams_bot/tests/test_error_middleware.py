"""
# Ontology: cortexteams:Testing
# Implements: cortexteams:ErrorMiddlewareTests
# Requirement: REQ-TEST-002 Error handling testing
# Guidance: guidance:TestingPatterns#UnitTesting
# Description: Unit tests for error handling middleware

Tests for the error handling middleware implementation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from botbuilder.core import TurnContext
from botbuilder.schema import Activity
from ..bot.error_middleware import ErrorHandlingMiddleware
from ..bot.state_manager import StateManager


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    return MagicMock()


@pytest.fixture
def mock_context():
    """Create mock turn context."""
    context = MagicMock(spec=TurnContext)
    context.activity = Activity()
    context.activity.conversation = Activity()
    context.activity.conversation.id = "test_conversation"
    return context


@pytest.fixture
def state_manager():
    """Create a mock state manager."""
    return MagicMock(spec=StateManager)


@pytest.fixture
def error_middleware(state_manager):
    """Create an error handling middleware instance."""
    return ErrorHandlingMiddleware(state_manager)


@pytest.mark.asyncio
async def test_error_middleware_initialization(mock_storage):
    """Test error middleware initialization."""
    state_manager = StateManager(mock_storage, "test_conversation")
    middleware = ErrorHandlingMiddleware(state_manager)
    assert middleware._state_manager == state_manager


@pytest.mark.asyncio
async def test_error_middleware_logging(mock_storage, mock_context):
    """Test error logging functionality."""
    state_manager = StateManager(mock_storage, "test_conversation")
    middleware = ErrorHandlingMiddleware(state_manager)
    error = Exception("Test error")
    error_id = await middleware._log_error(mock_context, error)
    assert error_id.startswith("ERR-")


@pytest.mark.asyncio
async def test_error_categorization(mock_storage):
    """Test error categorization."""
    state_manager = StateManager(mock_storage, "test_conversation")
    middleware = ErrorHandlingMiddleware(state_manager)

    assert middleware._categorize_error(PermissionError()) == "auth_error"
    assert middleware._categorize_error(TimeoutError()) == "timeout_error"
    assert middleware._categorize_error(SystemError()) == "system_error"
    assert middleware._categorize_error(ValueError()) == "validation_error"
    assert middleware._categorize_error(Exception()) == "unknown_error"


@pytest.mark.asyncio
async def test_error_handling_with_checkpoint(mock_storage, mock_context):
    """Test error handling with checkpoint creation."""
    state_manager = StateManager(mock_storage, "test_conversation")
    state_manager.create_checkpoint = AsyncMock()
    middleware = ErrorHandlingMiddleware(state_manager)

    next_mock = AsyncMock(side_effect=SystemError("Critical error"))
    try:
        await middleware.on_turn(mock_context, next_mock)
    except SystemError:
        pass

    state_manager.create_checkpoint.assert_called_once()


@pytest.mark.asyncio
async def test_error_handling_with_state_transition(mock_storage, mock_context):
    """Test error handling with state transition."""
    state_manager = StateManager(mock_storage, "test_conversation")
    state_manager.trigger_transition = AsyncMock()
    middleware = ErrorHandlingMiddleware(state_manager)

    next_mock = AsyncMock(side_effect=ValueError("Validation error"))
    await middleware.on_turn(mock_context, next_mock)

    state_manager.trigger_transition.assert_called_once_with(
        mock_context, "error", None
    )


if __name__ == "__main__":
    pytest.main([__file__])
