# flake8: noqa: E501
"""
# Ontology: cortexteams:StateManagement
# Implements: cortexteams:StateManager
# Requirement: REQ-BOT-001 Conversation state management
# Guidance: guidance:BotPatterns#StateManagement
# Description: Manages bot state using FSM with persistence and checkpointing

State management for the Teams bot using transitions FSM.
"""
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, cast, Union, Protocol, TypeVar, Type, Sequence, AsyncIterator, Awaitable
import logging
import os
import json
import base64

from azure.cosmos import CosmosClient, ContainerProxy, DatabaseProxy
from azure.cosmos.aio import ContainerProxy as AsyncContainerProxy
from botbuilder.core import TurnContext, Storage, StoreItem
from cryptography.fernet import Fernet
from transitions.extensions.asyncio import AsyncMachine

from .conversation_state import ConversationState
from .conversation_data import ConversationData
from .user_profile import UserProfile

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Constants
DEFAULT_TIMEOUT = 5  # Default timeout in minutes
STATE_TIMEOUTS = {
    ConversationState.AUTHENTICATING.value: 10,
    ConversationState.QUERYING.value: 5,
    ConversationState.PROCESSING.value: 15,
    ConversationState.RESPONDING.value: 5,
}

# Maximum error count before forcing reset
MAX_ERROR_COUNT = 3

@dataclass
class StateMetadata:
    """Metadata for state transitions."""
    timestamp: str
    source_state: str
    target_state: str
    reason: Optional[str] = None
    error_details: Optional[str] = None

class ReadableBuffer(Protocol):
    """Protocol for objects that can be used as a buffer for reading."""
    def __buffer__(self) -> memoryview: ...

class StateManager:
    """Manages conversation state using a finite state machine with persistence."""
    
    def __init__(self, storage: Union[Storage, ContainerProxy, AsyncContainerProxy], conversation_id: str):
        """Initialize the state manager."""
        if not conversation_id or not isinstance(conversation_id, str):
            raise ValueError("conversation_id must be a non-empty string")
            
        self._storage = storage
        self._conversation_id = conversation_id
        self._error_count = 0
        self._machine = None
        self._encryption_key = os.getenv("STATE_ENCRYPTION_KEY", "").encode()
        self._fernet = Fernet(self._encryption_key) if self._encryption_key else None

    async def load_state(self) -> Optional[Dict[str, Any]]:
        """Load state from storage."""
        try:
            if isinstance(self._storage, (ContainerProxy, AsyncContainerProxy)):
                query = self._storage.query_items(
                    query="SELECT * FROM c WHERE c.id = @id",
                    parameters=[{"name": "@id", "value": self._conversation_id}],
                    enable_cross_partition_query=True
                )
                async for item in query:
                    return item
            else:
                # Handle Storage type
                data = await self._storage.read([self._conversation_id])
                return data.get(self._conversation_id)
            return None
        except Exception as e:
            logger.error(f"Failed to load state: {str(e)}")
            return None

    async def initialize(self) -> bool:
        """Initialize the state manager and load existing state if available."""
        try:
            state = await self.load_state()
            return bool(state)
        except Exception as e:
            logger.error(f"Failed to initialize state manager: {str(e)}")
            return False

    def encrypt(self, value: Union[str, bytes]) -> str:
        """Encrypt a value using Fernet encryption."""
        if not self._fernet:
            return value.decode() if isinstance(value, bytes) else str(value)
        if isinstance(value, str):
            value = value.encode()
        encrypted = self._fernet.encrypt(value)
        return base64.b64encode(encrypted).decode()

    def decrypt(self, value: str) -> str:
        """Decrypt a value using Fernet encryption."""
        if not self._fernet:
            return value
            
        try:
            decoded = base64.b64decode(value.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt value: {str(e)}")
            return value

    async def handle_error(self, context: TurnContext, error: Exception) -> None:
        """Handle errors by incrementing error count and potentially resetting state."""
        self._error_count += 1
        logger.error(f"Error in state manager: {str(error)}")
        
        if self._error_count >= MAX_ERROR_COUNT:
            logger.warning(f"Max error count ({MAX_ERROR_COUNT}) reached, resetting state")
            await self.clear_state(context)
            self._error_count = 0

    async def save_parameters(self, parameters: Optional[Sequence[Dict[str, Any]]] = None) -> None:
        """Save conversation parameters."""
        if not parameters:
            return
            
        try:
            if isinstance(self._storage, (ContainerProxy, AsyncContainerProxy)):
                query = self._storage.query_items(
                    query="SELECT * FROM c WHERE c.id = @id",
                    parameters=[{"name": "@id", "value": self._conversation_id}],
                    enable_cross_partition_query=True
                )
                async for item in query:
                    item["parameters"] = list(parameters)  # Convert Sequence to list
                    await self._storage.upsert_item(body=item)
                    break
            else:
                # Handle Storage type
                data = await self._storage.read([self._conversation_id])
                if self._conversation_id in data:
                    state_data = data[self._conversation_id]
                    state_data["parameters"] = list(parameters)  # Convert Sequence to list
                    changes = {self._conversation_id: state_data}
                    await self._storage.write(changes)
        except Exception as e:
            logger.error(f"Failed to save parameters: {str(e)}")

    async def clear_state(self, context: Optional[TurnContext] = None) -> None:
        """Clear the conversation state."""
        if context and context.activity:
            await context.delete_activity(context.activity.id)
        if self._machine:
            self._machine = None

    async def get_conversation_data(self, context: TurnContext) -> ConversationData:
        """Get conversation data from storage."""
        if not context.activity or not context.activity.conversation:
            raise ValueError("No conversation context available")

        conversation_id = context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")

        try:
            # Try to load from storage
            data = await self.load_state()
            if data and isinstance(data, dict):
                return ConversationData.from_dict(data, self)
            
            # Create new if not found
            conv_data = ConversationData(conversation_id=conversation_id)
            # Save the new data
            await self.save_conversation_data(context, conv_data)
            return conv_data
            
        except Exception as e:
            logger.error(f"Failed to load conversation data: {e}")
            # Create new on error
            return ConversationData(conversation_id=conversation_id)

    async def save_conversation_data(self, context: TurnContext, data: ConversationData) -> None:
        """Save conversation data to storage."""
        if not context.activity or not context.activity.conversation:
            raise ValueError("No conversation context available")

        conversation_id = context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")

        try:
            # Convert to dictionary and save
            data_dict = data.to_dict()
            if isinstance(self._storage, (ContainerProxy, AsyncContainerProxy)):
                await self._storage.upsert_item(body=data_dict)
            else:
                changes = {conversation_id: data_dict}
                await self._storage.write(changes)
        except Exception as e:
            logger.error(f"Failed to save conversation data: {e}")
            raise

    async def get_user_profile(self, context: TurnContext) -> UserProfile:
        """Get user profile from storage."""
        if not context.activity or not context.activity.from_property:
            return UserProfile()

        user_id = context.activity.from_property.id
        if not user_id:
            return UserProfile()

        try:
            # Try to load from storage
            data = await self.load_state()
            if data and isinstance(data, dict):
                return UserProfile(**data)
        except Exception as e:
            logger.error(f"Failed to load user profile: {e}")

        return UserProfile()

    async def save_user_profile(self, context: TurnContext, profile: UserProfile) -> None:
        """Save user profile to storage."""
        if not context.activity or not context.activity.from_property:
            raise ValueError("No user context available")

        user_id = context.activity.from_property.id
        if not user_id:
            raise ValueError("No user ID available")

        try:
            # Convert to dictionary and save
            data_dict = asdict(profile)
            if isinstance(self._storage, (ContainerProxy, AsyncContainerProxy)):
                await self._storage.upsert_item(body=data_dict)
            else:
                changes = {f"user/{user_id}": data_dict}
                await self._storage.write(changes)
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")
            raise

    async def create_checkpoint(self) -> None:
        """Create a checkpoint of the current state."""
        try:
            if not self._conversation_id:
                return
                
            data = await self.load_state()
            if data:
                data["checkpoint_timestamp"] = datetime.utcnow().isoformat()
                if isinstance(self._storage, (ContainerProxy, AsyncContainerProxy)):
                    await self._storage.upsert_item(body=data)
                else:
                    changes = {self._conversation_id: data}
                    await self._storage.write(changes)
                    
            logger.info(f"Created checkpoint for conversation {self._conversation_id}")
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {str(e)}")
            raise

    async def trigger_transition(
        self,
        context: TurnContext,
        transition: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Trigger a state transition."""
        try:
            if not context.activity or not context.activity.conversation:
                raise ValueError("No conversation context available")
                
            conversation_id = context.activity.conversation.id
            if not conversation_id:
                raise ValueError("No conversation ID available")
                
            conversation_data = await self.get_conversation_data(context)
            if conversation_data and conversation_data._machine:
                await conversation_data._machine.trigger(transition, data)
                await self.save_conversation_data(context, conversation_data)
                
            logger.info(
                f"Triggered transition {transition} for conversation {conversation_id}"
            )
        except Exception as e:
            logger.error(f"Failed to trigger transition: {str(e)}")
            raise
