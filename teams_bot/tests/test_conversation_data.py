"""
# Ontology: cortexteams:Testing
# Implements: cortexteams:ConversationDataTests
# Requirement: REQ-TEST-003 Conversation state testing
# Guidance: guidance:TestingPatterns#UnitTesting
# Description: Tests for conversation data management
"""

import asyncio
import logging
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from ..bot.conversation_data import ConversationData
from ..bot.conversation_state import ConversationState
from ..bot.state_manager import StateManager
from transitions.core import MachineError

# Configure logging
logging.basicConfig(level=logging.DEBUG)

TEST_TIMEOUT = 15


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    storage = MagicMock()
    storage.write = AsyncMock()
    storage.read = AsyncMock(return_value={})
    return storage


@pytest.fixture
def mock_state_manager(mock_storage):
    """Create mock state manager."""
    return StateManager(mock_storage, "test_conversation")


@pytest.fixture
async def conversation_data():
    """Create conversation data instance."""
    data = ConversationData(conversation_id="test_id")
    yield data


@pytest.mark.asyncio
async def test_conversation_data_initialization():
    """Test conversation data initialization."""
    data = ConversationData(conversation_id="test_id")
    assert data.conversation_id == "test_id"
    assert data.current_state == ConversationState.INITIALIZED
    assert data.error_count == 0


@pytest.mark.asyncio
async def test_conversation_data_invalid_init():
    """Test conversation data initialization with invalid ID."""
    with pytest.raises(ValueError):
        ConversationData(conversation_id="")


@pytest.mark.asyncio
async def test_state_machine_transitions(conversation_data):
    """Test state machine transitions."""
    data = await anext(conversation_data)
    
    # Test valid transitions
    await data.start_authentication()
    assert data.current_state == ConversationState.AUTHENTICATING
    
    await data.authentication_complete()
    assert data.current_state == ConversationState.AUTHENTICATED


@pytest.mark.asyncio
async def test_state_timeout_handling(conversation_data):
    """Test state timeout handling."""
    data = await anext(conversation_data)
    
    # Set old last activity
    old_time = datetime.utcnow() - timedelta(minutes=10)
    data.last_activity = old_time.isoformat()
    
    # Verify timeout check
    assert not await data.check_state_timeout()


@pytest.mark.asyncio
async def test_checkpoint_creation(conversation_data, mock_state_manager):
    """Test checkpoint creation."""
    data = await anext(conversation_data)
    data.state_manager = mock_state_manager
    
    await data.create_checkpoint()
    assert data.checkpoint_data is not None
    assert data.checkpoint_timestamp is not None
    assert data.has_valid_checkpoint()


@pytest.mark.asyncio
async def test_checkpoint_restoration(conversation_data, mock_state_manager):
    """Test checkpoint restoration."""
    data = await anext(conversation_data)
    data.state_manager = mock_state_manager
    
    # Create checkpoint
    await data.create_checkpoint()
    
    # Modify state
    data.error_count = 5
    initial = ConversationState.INITIALIZED
    data.current_state = ConversationState.ERROR
    
    # Restore and verify
    success = await data.restore_checkpoint()
    assert success
    assert data.error_count == 0
    assert data.current_state == initial


@pytest.mark.asyncio
async def test_data_encryption(conversation_data, mock_state_manager):
    """Test data encryption."""
    data = await anext(conversation_data)
    data.state_manager = mock_state_manager
    
    # Mock encryption methods
    mock_state_manager.encrypt = MagicMock(return_value="encrypted")
    mock_value = '{"value": "decrypted"}'
    mock_state_manager.decrypt = MagicMock(return_value=mock_value)
    
    # Test to_dict and from_dict with encryption
    encrypted_data = data.to_dict()
    assert "encrypted" in str(encrypted_data)


@pytest.mark.asyncio
async def test_error_handling(conversation_data):
    """Test error handling."""
    data = await anext(conversation_data)
    
    # Test invalid transition
    with pytest.raises(MachineError):
        await data.authentication_complete()
    
    assert data.error_count == 1
    assert data.current_state == ConversationState.ERROR


@pytest.mark.asyncio
async def test_state_history_tracking(conversation_data):
    """Test state history tracking."""
    data = await anext(conversation_data)
    
    # Perform transitions
    await data.start_authentication()
    await data.authentication_complete()
    
    # Verify history
    assert len(data.state_history) == 2
    first_state = ConversationState.AUTHENTICATING.value
    second_state = ConversationState.AUTHENTICATED.value
    assert data.state_history[0]["state"] == first_state
    assert data.state_history[1]["state"] == second_state


@pytest.mark.asyncio
async def test_invalid_transitions(conversation_data):
    """Test invalid state transitions."""
    data = await anext(conversation_data)
    
    # Test invalid transition sequence
    with pytest.raises(MachineError):
        await data.start_querying()
    
    assert data.error_count == 1
    assert data.current_state == ConversationState.ERROR


@pytest.mark.asyncio
async def test_conversation_references(conversation_data):
    """Test conversation references handling."""
    data = await anext(conversation_data)
    
    # Add reference
    ref = {"id": "test_ref"}
    data.conversation_references["test"] = ref
    
    # Verify reference
    assert data.conversation_references["test"] == ref


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_concurrent_state_changes(conversation_data):
    """Test concurrent state change handling."""
    # Create separate instances for each chain
    data1 = await anext(conversation_data)
    data2 = ConversationData(conversation_id="test_id_2")
    data3 = ConversationData(conversation_id="test_id_3")

    async def transition_chain(data: ConversationData, chain_id: str) -> None:
        try:
            await data.start_authentication()
            await data.authentication_complete()
            await data.start_querying()
            await data.querying_complete()
        except Exception as e:
            logging.error(f"Chain {chain_id} failed: {e}")
            raise

    # Run multiple transition chains concurrently
    await asyncio.gather(
        transition_chain(data1, "1"),
        transition_chain(data2, "2"),
        transition_chain(data3, "3")
    )

    # Verify final states
    assert data1.current_state == ConversationState.AUTHENTICATED
    assert data2.current_state == ConversationState.AUTHENTICATED
    assert data3.current_state == ConversationState.AUTHENTICATED


if __name__ == "__main__":
    pytest.main([__file__]) 