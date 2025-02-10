"""
# Ontology: cortexteams:CardActionsTest
# Implements: cortexteams:AdaptiveCards
# Requirement: REQ-BOT-003 Teams card actions
# Guidance: guidance:BotPatterns#CardActions
# Description: Tests for Teams Adaptive Card action handlers
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from botbuilder.core import TurnContext
from botbuilder.schema import Activity

from bot.card_actions import CardActionHandler


@pytest.fixture
def turn_context():
    """Create a mock turn context."""
    context = MagicMock(spec=TurnContext)
    context.send_activity = AsyncMock()
    return context


@pytest.fixture
def action_handler():
    """Create a card action handler."""
    return CardActionHandler()


@pytest.mark.asyncio
async def test_register_and_handle_action(turn_context, action_handler):
    """Test registering and handling an action."""
    # Create a mock handler
    mock_handler = AsyncMock(return_value=Activity(
        type="message",
        text="Action handled"
    ))

    # Register the handler
    action_handler.register_action("test_action", mock_handler)

    # Handle the action
    action_data = {"action": "test_action", "data": "test"}
    result = await action_handler.handle_action(turn_context, action_data)

    # Verify handler was called
    mock_handler.assert_called_once_with(turn_context, action_data)
    assert result.type == "message"
    assert result.text == "Action handled"


@pytest.mark.asyncio
async def test_handle_unknown_action(turn_context, action_handler):
    """Test handling an unknown action."""
    # Try to handle an unregistered action
    action_data = {"action": "unknown_action"}
    result = await action_handler.handle_action(turn_context, action_data)

    # Verify error card is returned
    assert result.type == "message"
    assert len(result.attachments) == 1
    card = result.attachments[0]
    assert card["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert "Unknown action" in str(card["content"])


@pytest.mark.asyncio
async def test_handle_missing_action(turn_context, action_handler):
    """Test handling missing action data."""
    # Try to handle action with no action field
    action_data = {"data": "test"}
    result = await action_handler.handle_action(turn_context, action_data)

    # Verify error card is returned
    assert result.type == "message"
    assert len(result.attachments) == 1
    card = result.attachments[0]
    assert card["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert "Unknown action" in str(card["content"])


@pytest.mark.asyncio
async def test_handle_action_error(turn_context, action_handler):
    """Test handling an action that raises an error."""
    # Create a handler that raises an exception
    async def error_handler(_, __):
        raise ValueError("Test error")

    # Register the handler
    action_handler.register_action("error_action", error_handler)

    # Handle the action
    action_data = {"action": "error_action"}
    result = await action_handler.handle_action(turn_context, action_data)

    # Verify error card is returned
    assert result.type == "message"
    assert len(result.attachments) == 1
    card = result.attachments[0]
    assert card["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert "Test error" in str(card["content"])
    assert "ERR-ACTION-FAILED" in str(card["content"]) 