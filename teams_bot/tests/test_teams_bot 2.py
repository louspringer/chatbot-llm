"""
# Ontology: cortexteams:Testing
# Implements: cortexteams:TeamsBotTests
# Requirement: REQ-TEST-001 Bot functionality testing
# Guidance: guidance:TestingPatterns#UnitTesting
# Description: Unit tests for Teams bot implementation
"""

from unittest.mock import MagicMock

import pytest
from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ChannelAccount, ConversationAccount

from ..bot.state_manager import StateManager
from ..bot.teams_bot import TeamsBot


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    return MagicMock()


@pytest.fixture
def mock_state_manager(mock_storage):
    """Create mock state manager."""
    return StateManager(mock_storage, "test_conversation")


@pytest.fixture
def mock_context():
    """Create mock turn context."""
    context = MagicMock(spec=TurnContext)
    context.activity = Activity()
    context.activity.conversation = ConversationAccount(id="test_conversation")
    context.activity.from_property = ChannelAccount(id="test_user")
    return context


@pytest.fixture
def bot(mock_state_manager):
    """Create a bot instance for testing."""
    config = {
        "app_id": "test_app_id",
        "app_password": "test_password",
    }
    return TeamsBot(config=config, state_manager=mock_state_manager)


@pytest.mark.asyncio
async def test_bot_initialization(mock_state_manager):
    """Test bot initialization."""
    config = {
        "app_id": "test_app_id",
        "app_password": "test_password",
    }
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    assert bot._config == config
    assert bot._state_manager == mock_state_manager
    assert bot._error_middleware is not None


@pytest.mark.asyncio
async def test_validate_conversation_context(bot, mock_context):
    """Test conversation context validation."""
    conversation_id = await bot._validate_conversation_context(mock_context)
    assert conversation_id == "test_conversation"


@pytest.mark.asyncio
async def test_validate_conversation_context_no_conversation(bot):
    """Test validation with missing conversation."""
    context = MagicMock(spec=TurnContext)
    context.activity = Activity()
    context.activity.conversation = None

    with pytest.raises(ValueError, match="No conversation context available"):
        await bot._validate_conversation_context(context)


@pytest.mark.asyncio
async def test_handle_message_activity(bot, mock_context):
    """Test message activity handling."""
    mock_context.activity.text = "test message"
    conversation_id = "test_conversation"

    await bot._handle_message_activity(mock_context, conversation_id)

    # Verify conversation reference was saved
    assert conversation_id in bot._conversation_references

    # Verify acknowledgment was sent
    mock_context.send_activity.assert_called_once()
    call_args = mock_context.send_activity.call_args[0][0]
    assert "Processing your message: test message" in str(call_args)


@pytest.mark.asyncio
async def test_process_message(bot):
    """Test message processing."""
    message = "test message"
    response = await bot._process_message(message)

    assert response.type == "message"
    assert response.text == "Received: test message"


@pytest.mark.asyncio
async def test_on_members_added_activity(bot, mock_context):
    """Test handling of members added activity."""
    member = ChannelAccount(id="new_member")
    mock_context.activity.recipient = ChannelAccount(id="bot_id")

    await bot.on_members_added_activity([member], mock_context)

    mock_context.send_activity.assert_called_once_with("Welcome to the Teams bot!")


if __name__ == "__main__":
    pytest.main([__file__])
