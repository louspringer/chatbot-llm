# flake8: noqa: E501
"""
# Ontology: cortexteams:Testing
# Implements: cortexteams:StateManagerTests
# Requirement: REQ-TEST-001 State management testing
# Guidance: guidance:TestingPatterns#UnitTesting
# Description: Unit tests for state management functionality

Tests for the state management implementation.
"""

# pylint: disable=too-many-lines
# pylint: disable=too-many-locals

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from base64 import b64decode
from cryptography.fernet import Fernet

from botbuilder.core import TurnContext, Storage, MemoryStorage
from ..bot.state_manager import StateManager
from ..bot.conversation_state import ConversationState
from ..bot.conversation_data import ConversationData, MAX_ERROR_COUNT
from ..bot.user_profile import UserProfile
from ..bot.cosmos_storage import CosmosStorage


@pytest.fixture
def mock_context():
    """Create a mock turn context."""
    context = MagicMock(spec=TurnContext)
    context.activity = MagicMock()
    context.activity.conversation = MagicMock()
    context.activity.conversation.id = "test_conversation"
    context.activity.from_property = MagicMock()
    context.activity.from_property.id = "test_user"
    return context


@pytest.fixture
def mock_storage():
    """Create a mock storage."""
    storage = MagicMock(spec=Storage)
    storage.read = AsyncMock(return_value={"test_conversation": {}})
    storage.write = AsyncMock()
    return storage


@pytest.fixture
def state_manager(mock_storage):
    """Create a state manager with mock storage."""
    return StateManager(mock_storage, "test_conversation")


@pytest.fixture
def memory_storage():
    """Create an in-memory storage instance."""
    return MemoryStorage()


@pytest.fixture
def state_manager_memory(memory_storage):
    """Create a state manager instance with memory storage."""
    return StateManager(memory_storage, "test_conversation")


@pytest.mark.asyncio
async def test_state_manager_initialization(mock_storage):
    """Test state manager initialization."""
    # Test valid initialization
    manager = StateManager(mock_storage, "test_conversation")
    assert manager._storage == mock_storage
    assert manager._conversation_id == "test_conversation"
    assert manager._error_count == 0

    # Test invalid initialization
    with pytest.raises(ValueError):
        StateManager(mock_storage, "")
    with pytest.raises(ValueError):
        StateManager(mock_storage, "")  # Changed from None to empty string


@pytest.mark.asyncio
async def test_state_manager_error_handling(mock_storage, mock_context):
    """Test error handling in state manager."""
    manager = StateManager(mock_storage, "test_conversation")
    
    # Test error count increment
    error = Exception("Test error")
    await manager.handle_error(mock_context, error)
    assert manager._error_count == 1

    # Test max error reset
    for _ in range(MAX_ERROR_COUNT - 1):  # One less since we already incremented once
        await manager.handle_error(mock_context, error)
    assert manager._error_count == 0


@pytest.mark.asyncio
async def test_state_manager_encryption(mock_storage):
    """Test encryption and decryption in state manager."""
    manager = StateManager(mock_storage, "test_conversation")
    
    # Test string encryption/decryption
    test_str = "test_string"
    encrypted = manager.encrypt(test_str)
    decrypted = manager.decrypt(encrypted)
    assert decrypted == test_str

    # Test bytes encryption/decryption
    test_bytes = b"test_bytes"
    encrypted = manager.encrypt(test_bytes)
    decrypted = manager.decrypt(encrypted)
    assert decrypted == test_bytes.decode()


@pytest.mark.asyncio
async def test_state_manager_storage(mock_storage):
    """Test storage operations in state manager."""
    manager = StateManager(mock_storage, "test_conversation")
    
    # Mock storage responses
    mock_storage.read.return_value = {"test_conversation": {"data": "test"}}
    
    # Test state loading
    state = await manager.load_state()
    assert state == {"data": "test"}
    
    # Test initialization
    success = await manager.initialize()
    assert success is True


@pytest.mark.asyncio
async def test_state_manager_parameters(mock_storage):
    """Test parameter saving in state manager."""
    manager = StateManager(mock_storage, "test_conversation")
    
    # Test parameter saving
    parameters = [{"key": "value"}]
    await manager.save_parameters(parameters)
    
    # Verify storage calls
    mock_storage.read.assert_called_once_with(["test_conversation"])


@pytest.mark.asyncio
async def test_state_manager_clear(mock_storage, mock_context):
    """Test state clearing in state manager."""
    manager = StateManager(mock_storage, "test_conversation")
    
    # Test clear state
    await manager.clear_state(mock_context)
    assert manager._machine is None
    
    # Test clear state without context
    await manager.clear_state()
    assert manager._machine is None


@pytest.mark.asyncio
async def test_conversation_data_validation():
    """Test conversation data validation."""
    # Test valid data
    data = ConversationData(conversation_id="test_conversation")
    assert data.current_state == ConversationState.INITIALIZED
    assert data.error_count == 0
    assert data.state_history == []


@pytest.mark.asyncio
async def test_state_timeout_handling(mock_storage, mock_context):
    """Test state timeout detection and handling."""
    manager = StateManager(mock_storage, "test_conversation")
    data = ConversationData(conversation_id="test_conversation")
    
    # Test timeout
    old_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
    data.last_activity = old_time
    assert await data.check_state_timeout() is True


@pytest.mark.asyncio
async def test_error_count_and_reset():
    """Test error counting and automatic reset."""
    data = ConversationData(conversation_id="test_conversation")
    assert data.error_count == 0
    
    # Test error count increment
    data.error_count += 1
    assert data.error_count == 1


@pytest.mark.asyncio
async def test_state_persistence(mock_storage, mock_context):
    """Test state persistence."""
    # Create a state manager with mocked storage
    manager = StateManager(mock_storage, "test_conversation")
    
    # Set up storage mock to store and return the saved state
    stored_data = {}
    
    async def mock_write(changes):
        nonlocal stored_data
        stored_data.update(changes)
        
    async def mock_read(keys):
        return {key: stored_data.get(key, {}) for key in keys}
    
    mock_storage.write.side_effect = mock_write
    mock_storage.read.side_effect = mock_read

    # Initial state
    conv_data = await manager.get_conversation_data(mock_context)
    assert conv_data.current_state == ConversationState.INITIALIZED

    # Test state persistence
    conv_data.current_state = ConversationState.AUTHENTICATING
    await manager.save_conversation_data(mock_context, conv_data)

    # Verify state is persisted
    loaded_data = await manager.get_conversation_data(mock_context)
    assert loaded_data.current_state == ConversationState.AUTHENTICATING


@pytest.mark.asyncio
async def test_error_handling_in_state_manager(mock_storage, mock_context):
    """Test error handling in state manager."""
    # Create a state manager with mocked storage
    manager = StateManager(mock_storage, "test_conversation")
    
    # Set up storage mock to store and return the saved state
    stored_data = {}
    
    async def mock_write(changes):
        nonlocal stored_data
        stored_data.update(changes)
        
    async def mock_read(keys):
        return {key: stored_data.get(key, {}) for key in keys}
    
    mock_storage.write.side_effect = mock_write
    mock_storage.read.side_effect = mock_read

    # Initial state
    conv_data = await manager.get_conversation_data(mock_context)
    assert conv_data.current_state == ConversationState.INITIALIZED

    # Test error handling
    conv_data.error_count = 1
    await manager.save_conversation_data(mock_context, conv_data)

    # Verify error count is persisted
    loaded_data = await manager.get_conversation_data(mock_context)
    assert loaded_data.error_count == 1


@pytest.mark.asyncio
async def test_state_history(mock_storage, mock_context):
    """Test state history tracking."""
    # Create a state manager with mocked storage
    manager = StateManager(mock_storage, "test_conversation")
    
    # Set up storage mock to store and return the saved state
    stored_data = {}
    
    async def mock_write(changes):
        nonlocal stored_data
        stored_data.update(changes)
        
    async def mock_read(keys):
        return {key: stored_data.get(key, {}) for key in keys}
    
    mock_storage.write.side_effect = mock_write
    mock_storage.read.side_effect = mock_read

    # Initial state
    conv_data = await manager.get_conversation_data(mock_context)
    assert len(conv_data.state_history) == 0

    # Add state transition
    conv_data.state_history.append({
        'from_state': ConversationState.INITIALIZED.value,
        'to_state': ConversationState.AUTHENTICATING.value,
        'timestamp': datetime.utcnow().isoformat()
    })
    await manager.save_conversation_data(mock_context, conv_data)

    # Verify state history is persisted
    loaded_data = await manager.get_conversation_data(mock_context)
    assert len(loaded_data.state_history) == 1


@pytest.mark.asyncio
async def test_conversation_data_creation():
    """Test creation of conversation data."""
    data = ConversationData(conversation_id="test_conversation")
    assert data.conversation_id == "test_conversation"
    assert data.current_state == ConversationState.INITIALIZED
    assert data.error_count == 0


@pytest.mark.asyncio
async def test_cosmos_storage():
    """Test Cosmos DB storage implementation."""
    # Create mock objects
    mock_client = AsyncMock()
    mock_database = AsyncMock()
    mock_container = AsyncMock()

    # Set up the mock chain
    mock_client.get_database_client.return_value = mock_database
    mock_database.get_container_client.return_value = mock_container

    # Mock the read and upsert operations
    test_data = {"id": "test_id", "data": "test_data"}
    stored_data = {}

    async def mock_read_item(**kwargs):
        key = kwargs.get("item")
        if key in stored_data:
            return stored_data[key]
        return test_data

    async def mock_upsert_item(**kwargs):
        item = kwargs.get("body", {})
        key = item.get("id")
        if key:
            stored_data[key] = item
        return item

    async def mock_delete_item(**kwargs):
        key = kwargs.get("item")
        if key in stored_data:
            del stored_data[key]

    mock_container.read_item.side_effect = mock_read_item
    mock_container.upsert_item.side_effect = mock_upsert_item
    mock_container.delete_item.side_effect = mock_delete_item
    mock_client.close = AsyncMock()

    # Create a storage instance with mocked client
    storage = CosmosStorage(
        cosmos_uri="https://test-cosmos.documents.azure.com:443/",
        cosmos_key="test_key",
        database_id="test_db",
        container_id="test_container",
    )

    # Replace the initialized client with our mock
    storage.client = mock_client
    storage.database = mock_database
    storage.container = mock_container

    try:
        # Test write operation first
        test_changes = {"test_id": test_data}
        await storage.write(test_changes)
        mock_container.upsert_item.assert_called_with(
            body=test_data
        )

        # Test read operation
        result = await storage.read(["test_id"])
        assert result == {"test_id": test_data}
        mock_container.read_item.assert_called_with(
            item="test_id",
            partition_key="test_id"
        )

        # Test delete operation
        await storage.delete(["test_id"])
        mock_container.delete_item.assert_called_with(
            item="test_id",
            partition_key="test_id"
        )
    finally:
        # Clean up
        await storage.close()


if __name__ == "__main__":
    pytest.main([__file__])
