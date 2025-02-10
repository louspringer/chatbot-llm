"""
# Ontology: cortexteams:ConversationDataTest
# Implements: cortexteams:ConversationState
# Requirement: REQ-BOT-001 Conversation state management
# Description: Tests for conversation data management
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ConversationReference

from teams_bot.bot.conversation_data import ConversationData, ConversationState


@pytest.fixture
def mock_turn_context():
    """Create a mock turn context."""
    context = MagicMock(spec=TurnContext)
    context.activity = Activity(
        id="test_activity_id",
        timestamp=datetime.now(timezone.utc),
        conversation=ConversationReference(id="test_conversation")
    )
    return context


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    manager = MagicMock()
    manager.encrypt = lambda x: x if isinstance(x, str) else x.decode()
    manager.decrypt = lambda x: x
    return manager


@pytest.fixture
def conversation_data():
    """Create a basic conversation data instance."""
    return ConversationData(conversation_id="test_conversation")


def test_conversation_data_initialization():
    """Test basic initialization of conversation data."""
    conv_data = ConversationData(conversation_id="test_id")
    
    assert conv_data.conversation_id == "test_id"
    assert conv_data.current_state == ConversationState.INITIALIZED
    assert conv_data.last_message_id is None
    assert conv_data.last_activity is not None
    assert not conv_data.conversation_references
    assert conv_data.error_count == 0


def test_conversation_data_to_dict(mock_state_manager):
    """Test conversion of conversation data to dictionary."""
    conv_data = ConversationData(conversation_id="test_id")
    conv_data.state_manager = mock_state_manager
    conv_data.current_state = ConversationState.QUERYING
    conv_data.last_message_id = "msg_123"
    conv_data.last_activity = "2024-03-20T12:00:00Z"
    conv_data.conversation_references = {"key": "value"}
    conv_data.error_count = 1

    data_dict = conv_data.to_dict()
    
    assert data_dict["conversation_id"] == "test_id"
    assert data_dict["current_state"] == ConversationState.QUERYING.value
    assert data_dict["last_message_id"] == '"msg_123"'
    assert data_dict["last_activity"] == "2024-03-20T12:00:00Z"
    assert data_dict["conversation_references"] == '{"key": "value"}'
    assert data_dict["error_count"] == 1


def test_conversation_data_from_dict(mock_state_manager):
    """Test creation of conversation data from dictionary."""
    data_dict = {
        "conversation_id": "test_id",
        "current_state": ConversationState.PROCESSING.value,
        "last_message_id": '"msg_456"',
        "last_activity": "2024-03-20T13:00:00Z",
        "conversation_references": '{"test": "data"}',
        "error_count": 2
    }
    
    conv_data = ConversationData.from_dict(data_dict, mock_state_manager)
    
    assert conv_data.conversation_id == "test_id"
    assert conv_data.current_state == ConversationState.PROCESSING
    assert conv_data.last_message_id == "msg_456"
    assert conv_data.last_activity == "2024-03-20T13:00:00Z"
    assert conv_data.conversation_references == {"test": "data"}
    assert conv_data.error_count == 2


def test_empty_conversation_id():
    """Test that empty conversation_id raises ValueError."""
    with pytest.raises(
        ValueError, 
        match="conversation_id cannot be None or empty"
    ):
        ConversationData(conversation_id="")


def test_state_machine_initialization():
    """Test that state machine is initialized."""
    conv_data = ConversationData(conversation_id="test_id")
    assert conv_data._machine is not None
    assert hasattr(conv_data._machine, "add_transitions")


@pytest.mark.asyncio
async def test_checkpoint_creation():
    """Test checkpoint creation and validation."""
    conv_data = ConversationData(conversation_id="test_id")
    
    # Create checkpoint
    await conv_data.create_checkpoint()
    
    # Verify checkpoint was created
    assert conv_data.checkpoint_data is not None
    assert conv_data.checkpoint_timestamp is not None
    assert conv_data.has_valid_checkpoint()


@pytest.mark.asyncio
async def test_checkpoint_restore():
    """Test checkpoint restoration."""
    conv_data = ConversationData(conversation_id="test_id")
    conv_data.current_state = ConversationState.QUERYING
    conv_data.last_message_id = "test_message"
    
    # Create and verify checkpoint
    await conv_data.create_checkpoint()
    assert conv_data.has_valid_checkpoint()
    
    # Change state
    conv_data.current_state = ConversationState.ERROR
    conv_data.last_message_id = "new_message"
    
    # Restore checkpoint
    success = await conv_data.restore_checkpoint()
    assert success
    assert conv_data.current_state == ConversationState.QUERYING
    assert conv_data.last_message_id == "test_message"


@pytest.mark.asyncio
async def test_state_transitions():
    """Test state machine transitions."""
    conv_data = ConversationData(conversation_id="test_conv_123")
    assert conv_data._machine is not None, "State machine not initialized"
    
    # Verify initial state
    assert conv_data.current_state == ConversationState.INITIALIZED
    
    # Test start_auth transition
    await conv_data._machine.dispatch("start_auth")
    assert conv_data.current_state == ConversationState.AUTHENTICATING
    
    # Test auth_success transition
    await conv_data._machine.dispatch("auth_success")
    assert conv_data.current_state == ConversationState.AUTHENTICATED
    
    # Test start_query transition
    await conv_data._machine.dispatch("start_query")
    assert conv_data.current_state == ConversationState.QUERYING
    
    # Test process_query transition
    await conv_data._machine.dispatch("process_query")
    assert conv_data.current_state == ConversationState.PROCESSING
    
    # Test send_response transition
    await conv_data._machine.dispatch("send_response")
    assert conv_data.current_state == ConversationState.RESPONDING
    
    # Test complete transition
    await conv_data._machine.dispatch("complete")
    assert conv_data.current_state == ConversationState.IDLE


@pytest.mark.asyncio
async def test_state_timeout():
    """Test state timeout checks."""
    conv_data = ConversationData(conversation_id="test_conv_123")
    assert conv_data._machine is not None, "State machine not initialized"
    
    # Set last activity to 5 minutes ago
    old_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    conv_data.last_activity = old_time
    
    # Start authentication
    await conv_data._machine.dispatch("start_auth")
    
    # Verify timeout check fails (auth timeout is 5 minutes)
    assert not await conv_data.check_state_timeout()
    
    # Update last activity to now
    conv_data.last_activity = datetime.utcnow().isoformat()
    
    # Verify timeout check passes
    assert await conv_data.check_state_timeout()


@pytest.mark.asyncio
async def test_error_handling():
    """Test error state transitions."""
    conv_data = ConversationData(conversation_id="test_conv_123")
    assert conv_data._machine is not None, "State machine not initialized"
    
    # Start with a valid transition
    await conv_data._machine.dispatch("start_auth")
    assert conv_data.current_state == ConversationState.AUTHENTICATING
    
    # Trigger validation failure by setting old activity timestamp
    old_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
    conv_data.last_activity = old_time
    
    # Try another transition - should fail validation and increment error count
    await conv_data._machine.dispatch("auth_success")
    assert conv_data.error_count == 1
    assert conv_data.current_state == ConversationState.ERROR
    
    # Reset state
    await conv_data._machine.dispatch("reset")
    assert conv_data.current_state == ConversationState.INITIALIZED
    assert conv_data.error_count == 0


@pytest.mark.asyncio
async def test_checkpoint_error_handling():
    """Test checkpoint error handling."""
    conv_data = ConversationData(conversation_id="test_conv_123")
    
    # Test invalid checkpoint timestamp
    conv_data.checkpoint_timestamp = "invalid_timestamp"
    assert not conv_data.has_valid_checkpoint()
    
    # Test missing checkpoint data
    conv_data.checkpoint_timestamp = datetime.utcnow().isoformat()
    conv_data.checkpoint_data = None
    assert not conv_data.has_valid_checkpoint()
    
    # Test expired checkpoint
    old_time = (datetime.utcnow() - timedelta(days=2)).isoformat()
    conv_data.checkpoint_timestamp = old_time
    assert not conv_data.has_valid_checkpoint()


@pytest.mark.asyncio
async def test_sensitive_field_encryption():
    """Test sensitive field encryption in to_dict."""
    # Create mock state manager
    mock_state_manager = MagicMock()
    mock_state_manager.encrypt.return_value = "encrypted_data"
    
    conv_data = ConversationData(
        conversation_id="test_conv_123",
        state_manager=mock_state_manager
    )
    
    # Set sensitive fields
    conv_data.active_query = "test query"
    conv_data.last_response = "test response"
    conv_data.conversation_references = {"ref1": "value1"}
    conv_data.last_message_id = "msg_123"
    
    # Convert to dict
    result = conv_data.to_dict()
    
    # Verify sensitive fields were encrypted
    assert result["active_query"] == "encrypted_data"
    assert result["last_response"] == "encrypted_data"
    assert result["conversation_references"] == "encrypted_data"
    assert result["last_message_id"] == "encrypted_data"
    
    # Verify non-sensitive fields were not encrypted
    assert isinstance(result["conversation_id"], str)
    assert isinstance(result["current_state"], str)
    assert isinstance(result["last_activity"], str)
    assert isinstance(result["state_history"], list)
    assert isinstance(result["error_count"], int) 