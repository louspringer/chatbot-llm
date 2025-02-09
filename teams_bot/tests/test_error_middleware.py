"""
# Ontology: cortexteams:Testing
# Implements: cortexteams:ErrorMiddlewareTests
# Requirement: REQ-TEST-002 Error handling testing
# Guidance: guidance:TestingPatterns#UnitTesting
# Description: Unit tests for error handling middleware

Tests for the error handling middleware implementation.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ActivityTypes
from ..bot.error_middleware import ErrorHandlingMiddleware
from ..bot.state_manager import StateManager


@pytest.fixture
def turn_context():
    """Create a mock turn context."""
    context = MagicMock(spec=TurnContext)
    context.activity = Activity(
        id="test_activity",
        type=ActivityTypes.message,
        conversation=MagicMock(id="test_conversation"),
        from_property=MagicMock(id="test_user")
    )
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
async def test_error_logging(error_middleware, turn_context):
    """Test error logging functionality."""
    error = ValueError("Test error")
    error_id = await error_middleware._log_error(turn_context, error)
    
    assert error_id.startswith("ERR-")
    assert datetime.strptime(error_id[4:], "%Y%m%d-%H%M%S")


@pytest.mark.asyncio
async def test_error_categorization(error_middleware):
    """Test error categorization."""
    # Test authentication error
    auth_error = PermissionError("Auth failed")
    assert error_middleware._categorize_error(auth_error) == "auth_error"
    
    # Test timeout error
    timeout_error = TimeoutError("Operation timed out")
    assert error_middleware._categorize_error(timeout_error) == "timeout_error"
    
    # Test unknown error
    unknown_error = Exception("Unknown error")
    assert error_middleware._categorize_error(unknown_error) == "unknown_error"


@pytest.mark.asyncio
async def test_error_handling(error_middleware, turn_context):
    """Test complete error handling flow."""
    # Mock the next middleware
    async def next_middleware(context):
        raise ValueError("Test error")
    
    # Handle the error
    await error_middleware.on_turn(turn_context, next_middleware)
    
    # Verify error response was sent
    turn_context.send_activity.assert_called_once()
    response = turn_context.send_activity.call_args[0][0]
    assert response.type == ActivityTypes.message
    assert "Reference ID: ERR-" in response.text


@pytest.mark.asyncio
async def test_checkpoint_creation(error_middleware, turn_context, state_manager):
    """Test checkpoint creation on critical errors."""
    # Mock the next middleware
    async def next_middleware(context):
        raise SystemError("Critical error")
    
    # Handle the error
    with pytest.raises(SystemError):
        await error_middleware.on_turn(turn_context, next_middleware)
    
    # Verify checkpoint was created
    state_manager.create_conversation_checkpoint.assert_called_once()


@pytest.mark.asyncio
async def test_error_state_transition(error_middleware, turn_context, state_manager):
    """Test state transition on error."""
    # Mock the next middleware
    async def next_middleware(context):
        raise ValueError("Test error")
    
    # Handle the error
    await error_middleware.on_turn(turn_context, next_middleware)
    
    # Verify error state transition
    state_manager.trigger_transition.assert_called_once_with(
        turn_context,
        "error",
        None
    )


if __name__ == "__main__":
    pytest.main([__file__]) 