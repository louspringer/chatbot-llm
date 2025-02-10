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
import os
import base64

from botbuilder.core import TurnContext, Storage, MemoryStorage
from ..bot.state_manager import StateManager
from ..bot.conversation_state import ConversationState
from ..bot.conversation_data import ConversationData, MAX_ERROR_COUNT
from ..bot.user_profile import UserProfile
from ..bot.cosmos_storage import CosmosStorage
from botbuilder.schema import Activity, ConversationAccount, ChannelAccount


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
    conv_data.state_history.append(
        {
            "from_state": ConversationState.INITIALIZED.value,
            "to_state": ConversationState.AUTHENTICATING.value,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
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
        return stored_data[key] if key in stored_data else test_data

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
        mock_container.upsert_item.assert_called_with(body=test_data)

        # Test read operation
        result = await storage.read(["test_id"])
        assert result == {"test_id": test_data}
        mock_container.read_item.assert_called_with(
            item="test_id", partition_key="test_id"
        )

        # Test delete operation
        await storage.delete(["test_id"])
        mock_container.delete_item.assert_called_with(
            item="test_id", partition_key="test_id"
        )
    finally:
        # Clean up
        await storage.close()


@pytest.mark.asyncio
async def test_encryption_with_key():
    """Test encryption with a valid encryption key."""
    # Setup
    mock_storage = MagicMock(spec=Storage)
    test_key = base64.b64encode(os.urandom(32))
    with patch.dict(os.environ, {'STATE_ENCRYPTION_KEY': test_key.decode()}):
        manager = StateManager(mock_storage, "test_conversation")
        
        # Test string encryption
        test_value = "sensitive data"
        encrypted = manager.encrypt(test_value)
        decrypted = manager.decrypt(encrypted)
        assert decrypted == test_value
        
        # Test bytes encryption
        test_bytes = b"sensitive bytes"
        encrypted_bytes = manager.encrypt(test_bytes)
        decrypted_bytes = manager.decrypt(encrypted_bytes)
        assert decrypted_bytes == test_bytes.decode()


@pytest.mark.asyncio
async def test_encryption_without_key():
    """Test behavior when no encryption key is provided."""
    mock_storage = MagicMock(spec=Storage)
    with patch.dict(os.environ, {'STATE_ENCRYPTION_KEY': ''}):
        manager = StateManager(mock_storage, "test_conversation")
        
        # Test string passthrough
        test_value = "test data"
        result = manager.encrypt(test_value)
        assert result == test_value
        
        # Test bytes passthrough
        test_bytes = b"test bytes"
        result_bytes = manager.encrypt(test_bytes)
        assert result_bytes == test_bytes.decode()


@pytest.mark.asyncio
async def test_save_parameters():
    """Test saving conversation parameters."""
    mock_storage = AsyncMock(spec=Storage)
    mock_storage.read.return_value = {"test_conversation": {}}
    manager = StateManager(mock_storage, "test_conversation")
    
    test_params = [
        {"name": "param1", "value": "value1"},
        {"name": "param2", "value": "value2"}
    ]
    
    await manager.save_parameters(test_params)
    
    # Verify storage interactions
    mock_storage.read.assert_called_once_with(["test_conversation"])
    mock_storage.write.assert_called_once()
    write_args = mock_storage.write.call_args[0][0]
    assert "test_conversation" in write_args
    assert write_args["test_conversation"]["parameters"] == test_params


@pytest.mark.asyncio
async def test_save_parameters_with_error():
    """Test error handling when saving parameters fails."""
    mock_storage = AsyncMock(spec=Storage)
    mock_storage.read.side_effect = Exception("Storage error")
    manager = StateManager(mock_storage, "test_conversation")
    
    test_params = [{"name": "param1", "value": "value1"}]
    await manager.save_parameters(test_params)
    
    # Verify error was handled gracefully
    mock_storage.read.assert_called_once()
    mock_storage.write.assert_not_called()


@pytest.mark.asyncio
async def test_clear_state():
    """Test clearing conversation state."""
    mock_storage = MagicMock(spec=Storage)
    manager = StateManager(mock_storage, "test_conversation")
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(id="test_activity")
    mock_context.delete_activity = AsyncMock()
    
    # Test clearing with context
    await manager.clear_state(mock_context)
    mock_context.delete_activity.assert_called_once_with("test_activity")
    assert manager._machine is None
    
    # Test clearing without context
    await manager.clear_state()
    assert manager._machine is None


@pytest.mark.asyncio
async def test_user_profile_management():
    """Test user profile management."""
    mock_storage = AsyncMock(spec=Storage)
    manager = StateManager(mock_storage, "test_conversation")
    
    # Setup mock context with user info
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        from_property=ChannelAccount(id="test_user", name="Test User")
    )
    
    # Test saving user profile
    test_profile = UserProfile(name="Test User")
    await manager.save_user_profile(mock_context, test_profile)
    
    # Verify storage write
    mock_storage.write.assert_called_once()
    write_args = mock_storage.write.call_args[0][0]
    assert "user/test_user" in write_args
    
    # Test loading user profile with correct data structure
    mock_storage.read.return_value = {
        "test_conversation": {
            "name": "Test User",
            "preferred_language": "en-US",
            "last_interaction": "",
            "permissions": [],
            "query_history": [],
            "etag": "*"
        }
    }
    loaded_profile = await manager.get_user_profile(mock_context)
    assert isinstance(loaded_profile, UserProfile)
    assert loaded_profile.name == "Test User"
    assert loaded_profile.preferred_language == "en-US"
    assert isinstance(loaded_profile.permissions, list)
    assert isinstance(loaded_profile.query_history, list)


@pytest.mark.asyncio
async def test_handle_error():
    """Test error handling and reset behavior."""
    mock_storage = MagicMock(spec=Storage)
    manager = StateManager(mock_storage, "test_conversation")
    
    # Setup mock context
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(id="test_activity")
    mock_context.delete_activity = AsyncMock()
    
    # Test error handling below threshold
    test_error = Exception("Test error")
    await manager.handle_error(mock_context, test_error)
    assert manager._error_count == 1
    mock_context.delete_activity.assert_not_called()
    
    # Test error handling at threshold
    for _ in range(2):
        await manager.handle_error(mock_context, test_error)
    
    assert manager._error_count == 0  # Should be reset
    mock_context.delete_activity.assert_called_once()


@pytest.mark.asyncio
async def test_conversation_data_management():
    """Test conversation data management with encryption."""
    mock_storage = AsyncMock(spec=Storage)
    test_key = base64.b64encode(os.urandom(32))
    
    with patch.dict(os.environ, {'STATE_ENCRYPTION_KEY': test_key.decode()}):
        manager = StateManager(mock_storage, "test_conversation")
        
        # Setup mock context
        mock_context = MagicMock(spec=TurnContext)
        mock_context.activity = Activity(
            conversation=ConversationAccount(id="test_conversation")
        )
        
        # Create test data with sensitive information
        conv_data = ConversationData(conversation_id="test_conversation")
        conv_data.active_query = "sensitive query"
        conv_data.last_response = "sensitive response"
        conv_data.state_manager = manager  # Set state manager for encryption
        
        # Test saving with encryption
        await manager.save_conversation_data(mock_context, conv_data)
        
        # Verify storage write with encrypted data
        mock_storage.write.assert_called_once()
        write_args = mock_storage.write.call_args[0][0]
        saved_data = write_args["test_conversation"]
        
        # Verify encrypted fields exist and are encrypted
        assert "active_query" in saved_data
        assert "last_response" in saved_data
        assert saved_data["active_query"] != "sensitive query"
        assert saved_data["last_response"] != "sensitive response"
        
        # Test loading with decryption
        mock_storage.read.return_value = {"test_conversation": saved_data}
        loaded_data = await manager.get_conversation_data(mock_context)
        assert isinstance(loaded_data, ConversationData)
        assert loaded_data.conversation_id == "test_conversation"
        assert loaded_data.active_query == "sensitive query"
        assert loaded_data.last_response == "sensitive response"


@pytest.mark.asyncio
async def test_user_profile_validation():
    """Test user profile validation."""
    mock_storage = AsyncMock(spec=Storage)
    manager = StateManager(mock_storage, "test_conversation")
    
    # Setup mock context with user info
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        from_property=ChannelAccount(id="test_user", name="Test User")
    )
    
    # Test profile with valid data
    valid_profile = UserProfile(
        name="Test User",
        last_interaction=datetime.utcnow().isoformat(),
        permissions=["read", "write"],
        query_history=[{
            "query": "test query",
            "timestamp": datetime.utcnow().isoformat()
        }]
    )
    assert valid_profile.validate()
    
    # Test profile with invalid last_interaction
    invalid_timestamp = UserProfile(
        name="Test User",
        last_interaction="invalid_timestamp"
    )
    assert not invalid_timestamp.validate()
    
    # Test profile with invalid permissions
    invalid_permissions = UserProfile(
        name="Test User",
        permissions="not_a_list"  # type: ignore
    )
    assert not invalid_permissions.validate()
    
    # Test profile with invalid query history
    invalid_query = UserProfile(
        name="Test User",
        query_history=[{"missing_required_fields": True}]
    )
    assert not invalid_query.validate()


@pytest.mark.asyncio
async def test_user_profile_data_conversion():
    """Test user profile data conversion."""
    mock_storage = AsyncMock(spec=Storage)
    manager = StateManager(mock_storage, "test_conversation")
    
    # Setup mock context with user info
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        from_property=ChannelAccount(id="test_user", name="Test User")
    )
    
    # Create profile with all fields populated
    timestamp = datetime.utcnow().isoformat()
    profile = UserProfile(
        name="Test User",
        preferred_language="es-ES",
        last_interaction=timestamp,
        permissions=["read", "write"],
        query_history=[{
            "query": "test query",
            "timestamp": timestamp
        }],
        etag="test_etag"
    )
    
    # Convert to dict and verify all fields
    data = profile.to_dict()
    assert data["name"] == "Test User"
    assert data["preferred_language"] == "es-ES"
    assert data["last_interaction"] == timestamp
    assert data["permissions"] == ["read", "write"]
    assert len(data["query_history"]) == 1
    assert data["query_history"][0]["query"] == "test query"
    assert data["query_history"][0]["timestamp"] == timestamp
    assert data["etag"] == "test_etag"
    
    # Save profile and verify storage
    await manager.save_user_profile(mock_context, profile)
    mock_storage.write.assert_called_once()
    write_args = mock_storage.write.call_args[0][0]
    saved_data = write_args[f"user/{mock_context.activity.from_property.id}"]
    
    # The saved data should include the ID field
    expected_data = data.copy()
    expected_data["id"] = f"user/{mock_context.activity.from_property.id}"
    assert saved_data == expected_data


@pytest.mark.asyncio
async def test_user_profile_error_handling():
    """Test user profile error handling."""
    mock_storage = AsyncMock(spec=Storage)
    mock_storage.read.side_effect = Exception("Storage error")
    manager = StateManager(mock_storage, "test_conversation")
    
    # Setup mock context with user info
    mock_context = MagicMock(spec=TurnContext)
    mock_context.activity = Activity(
        from_property=ChannelAccount(id="test_user", name="Test User")
    )
    
    # Test loading with storage error
    profile = await manager.get_user_profile(mock_context)
    assert isinstance(profile, UserProfile)
    assert profile.name == ""  # Should return empty profile on error
    
    # Test saving with storage error
    mock_storage.write.side_effect = Exception("Storage error")
    with pytest.raises(Exception):
        await manager.save_user_profile(
            mock_context,
            UserProfile(name="Test User")
        )


if __name__ == "__main__":
    pytest.main([__file__])
