"""
# Ontology: cortexteams:TeamsBotTests
# Implements: cortexteams:BotImplementation
# Requirement: REQ-TEST-001 Bot functionality testing
# Guidance: guidance:TestingPatterns#UnitTesting
# Description: Tests for Teams bot implementation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from botbuilder.core import TurnContext, Middleware
from botbuilder.schema import (
    Activity, 
    ActivityTypes, 
    ConversationAccount, 
    ChannelAccount
)
from ..bot.teams_bot import TeamsBot
from ..bot.state_manager import StateManager
from ..bot.cosmos_storage import CosmosStorage
from typing import cast


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
    
    await bot.on_members_added_activity(
        [member],
        mock_context
    )
    
    mock_context.send_activity.assert_called_once_with(
        "Welcome to the Teams bot!"
    )


@pytest.mark.asyncio
async def test_message_processing_with_error():
    """Test message processing with error handling."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {
        "app_id": "test_app_id",
        "app_password": "test_password",
    }
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=ConversationAccount(id="test_conversation")
    )
    mock_context.send_activity = AsyncMock()
    
    # Test normal message processing
    await bot._handle_message(mock_context)
    mock_context.send_activity.assert_called_once()
    
    # Test error in message processing
    mock_context.send_activity.side_effect = Exception("Test error")
    with pytest.raises(Exception):
        await bot._handle_message(mock_context)


@pytest.mark.asyncio
async def test_member_management():
    """Test member addition and removal handling."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    mock_state_manager.save_user_profile = AsyncMock()
    mock_state_manager.clear_state = AsyncMock()
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context for member addition
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.conversation_update,
        conversation=ConversationAccount(id="test_conversation"),
        recipient=ChannelAccount(id="bot_id"),
        members_added=[
            ChannelAccount(id="user_id", name="Test User")
        ]
    )
    mock_context.send_activity = AsyncMock()
    
    # Test member addition
    await bot.on_members_added_activity(
        mock_context.activity.members_added,
        mock_context
    )
    mock_context.send_activity.assert_called_once_with(
        "Welcome to the Teams bot!"
    )
    
    # Test member removal
    mock_context.activity.members_added = None
    mock_context.activity.members_removed = [
        ChannelAccount(id="user_id", name="Test User")
    ]
    
    await bot.on_conversation_update_activity(mock_context)
    mock_state_manager.clear_state.assert_called_once_with(mock_context)


@pytest.mark.asyncio
async def test_conversation_update_error_handling():
    """Test error handling in conversation updates."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    mock_state_manager.clear_state = AsyncMock(
        side_effect=Exception("Test error")
    )
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.conversation_update,
        conversation=ConversationAccount(id="test_conversation"),
        members_removed=[ChannelAccount(id="user_id")]
    )
    
    # Test error handling in conversation update
    with pytest.raises(Exception):
        await bot.on_conversation_update_activity(mock_context)


@pytest.mark.asyncio
async def test_middleware_configuration():
    """Test middleware configuration and adapter usage."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    # Create custom middleware
    custom_middleware = MagicMock(spec=Middleware)
    custom_middleware.on_turn = AsyncMock()
    
    # Create mock adapter before bot initialization
    mock_adapter = MagicMock()
    mock_adapter.use = MagicMock()
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(
        config=config,
        state_manager=mock_state_manager,
        middleware=[custom_middleware]
    )
    
    # Set adapter and verify middleware usage
    bot._adapter = mock_adapter  # type: ignore
    for middleware_instance in [custom_middleware, bot._error_middleware]:
        if middleware_instance:  # Check for None
            mock_adapter.use(middleware_instance)
    
    # Create a mock context to trigger middleware
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=ConversationAccount(id="test_conversation")
    )
    
    # Process a message to trigger middleware
    await bot._handle_message_activity(mock_context, "test_conversation")
    
    # Verify middleware was added and used
    assert bot._error_middleware is not None
    assert len(mock_adapter.use.mock_calls) == 2
    mock_adapter.use.assert_any_call(custom_middleware)
    mock_adapter.use.assert_any_call(bot._error_middleware)


@pytest.mark.asyncio
async def test_empty_message_handling():
    """Test handling of empty messages."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context with empty message
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="",
        conversation=ConversationAccount(id="test_conversation")
    )
    mock_context.send_activity = AsyncMock()
    
    # Test empty message handling
    await bot._handle_message_activity(mock_context, "test_conversation")
    mock_context.send_activity.assert_called_once_with(
        "I received an empty message."
    )


@pytest.mark.asyncio
async def test_conversation_reference_management():
    """Test conversation reference management."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=ConversationAccount(id="test_conversation")
    )
    mock_context.send_activity = AsyncMock()
    
    # Test conversation reference saving
    await bot._handle_message_activity(mock_context, "test_conversation")
    assert "test_conversation" in bot._conversation_references
    
    # Test conversation reference retrieval
    ref = bot.get_conversation_reference("test_conversation")
    assert ref is not None
    
    # Test non-existent reference
    ref = bot.get_conversation_reference("non_existent")
    assert ref is None


@pytest.mark.asyncio
async def test_process_message_turn():
    """Test message turn processing."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    mock_state_manager.get_conversation_data = AsyncMock()
    mock_state_manager.save_conversation_data = AsyncMock()
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=ConversationAccount(id="test_conversation")
    )
    
    # Test message turn processing
    await bot._process_message_turn(mock_context, "test_conversation")
    mock_state_manager.get_conversation_data.assert_called_once_with(
        mock_context
    )
    mock_state_manager.save_conversation_data.assert_called_once()


@pytest.mark.asyncio
async def test_handle_member_added():
    """Test member addition handling."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    mock_state_manager.save_user_profile = AsyncMock()
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.send_activity = AsyncMock()
    
    # Test member addition with name
    member = ChannelAccount(id="user_id", name="Test User")
    await bot._handle_member_added(member, mock_context)
    mock_state_manager.save_user_profile.assert_called_once()
    mock_context.send_activity.assert_called_once()
    
    # Test member addition without name
    mock_state_manager.save_user_profile.reset_mock()
    mock_context.send_activity.reset_mock()
    member = ChannelAccount(id="user_id")
    await bot._handle_member_added(member, mock_context)
    mock_state_manager.save_user_profile.assert_called_once()
    mock_context.send_activity.assert_called_once()


@pytest.mark.asyncio
async def test_validate_conversation_context_errors():
    """Test conversation context validation errors."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Test missing conversation
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(type=ActivityTypes.message)
    mock_context.activity.conversation = None
    
    with pytest.raises(ValueError, match="No conversation context available"):
        await bot._validate_conversation_context(mock_context)
    
    # Test missing conversation ID
    mock_context.activity.conversation = ConversationAccount(
        id=""  # Use empty string instead of None
    )
    with pytest.raises(ValueError, match="No conversation ID available"):
        await bot._validate_conversation_context(mock_context)


@pytest.mark.asyncio
async def test_on_turn_error_handling():
    """Test error handling in on_turn."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Setup mock context with invalid conversation
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=None
    )
    
    # Test error handling
    with pytest.raises(ValueError, match="No conversation context available"):
        await bot.on_turn(mock_context)
    
    # Test error in message processing
    mock_context.activity.conversation = ConversationAccount(
        id="test_conversation"
    )
    mock_context.send_activity = AsyncMock(
        side_effect=Exception("Test error")
    )
    
    with pytest.raises(Exception, match="Test error"):
        await bot.on_turn(mock_context)


@pytest.mark.asyncio
async def test_process_message_error_handling():
    """Test error handling in message processing."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Test error in message processing
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=ConversationAccount(id="test_conversation")
    )
    mock_context.send_activity = AsyncMock(side_effect=Exception("Test error"))
    
    with pytest.raises(Exception, match="Test error"):
        await bot._handle_message(mock_context)


@pytest.mark.asyncio
async def test_conversation_reference_edge_cases():
    """Test edge cases in conversation reference management."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Test getting non-existent reference
    assert bot.get_conversation_reference("non_existent") is None
    
    # Test saving reference with empty conversation ID
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.message,
        text="test message",
        conversation=None
    )
    
    with pytest.raises(ValueError, match="No conversation context available"):
        await bot._validate_conversation_context(mock_context)


@pytest.mark.asyncio
async def test_error_handling_edge_cases():
    """Test edge cases in error handling."""
    mock_storage = MagicMock(spec=CosmosStorage)
    mock_state_manager = StateManager(mock_storage, "test_conversation")
    
    config = {"app_id": "test_app_id", "app_password": "test_password"}
    bot = TeamsBot(config=config, state_manager=mock_state_manager)
    
    # Test error in state manager initialization
    with pytest.raises(ValueError, match="state_manager cannot be None"):
        TeamsBot(
            config=config,
            state_manager=cast(StateManager, None)  # type: ignore
        )
    
    # Test error in conversation update with no members
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        type=ActivityTypes.conversation_update,
        conversation=ConversationAccount(id="test_conversation")
    )
    
    # This should not raise an error but should handle gracefully
    await bot.on_conversation_update_activity(mock_context)
    
    # Test error in member removal
    mock_context.activity.members_removed = [ChannelAccount(id="user_id")]
    mock_state_manager.clear_state = AsyncMock(
        side_effect=Exception("Test error")
    )
    
    with pytest.raises(Exception, match="Test error"):
        await bot.on_conversation_update_activity(mock_context)


if __name__ == "__main__":
    pytest.main([__file__])
