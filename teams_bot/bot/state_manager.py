"""
State management for the Teams bot.
"""

from typing import Dict, Any
from botbuilder.core import (
    TurnContext,
    Storage,
    MemoryStorage,
    StoreItem
)
from dataclasses import dataclass, asdict, field
import logging
from ..config.settings import (
    STATE_STORAGE_TYPE,
    COSMOS_DB_ENDPOINT,
    COSMOS_DB_KEY,
    COSMOS_DB_DATABASE,
    COSMOS_DB_CONTAINER
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationData(StoreItem):
    """Data stored for each conversation."""

    last_message_id: str = ""
    conversation_references: Dict[str, Any] = field(default_factory=dict)
    etag: str = "*"


@dataclass
class UserProfile(StoreItem):
    """Data stored for each user."""

    name: str = ""
    preferred_language: str = "en-US"
    last_interaction: str = ""
    etag: str = "*"


class StateManager:
    """Manages bot state storage and retrieval."""

    def __init__(self):
        """Initialize the state manager with appropriate storage."""
        self.storage = self._initialize_storage()
        logger.info(f"Initialized StateManager with {STATE_STORAGE_TYPE} storage")

    def _initialize_storage(self) -> Storage:
        """Initialize the appropriate storage type based on configuration."""
        # For local testing, always use MemoryStorage
        logger.info("Using in-memory storage for development")
        return MemoryStorage()

    async def get_conversation_data(self, context: TurnContext) -> ConversationData:
        """Get conversation data for the current context."""
        if not context.activity.conversation:
            return ConversationData()

        key = f"conversation/{context.activity.conversation.id}"
        items = await self.storage.read([key])

        if key not in items:
            items[key] = ConversationData()

        return ConversationData(**items[key])

    async def save_conversation_data(
        self, context: TurnContext, data: ConversationData
    ) -> None:
        """Save conversation data for the current context."""
        if not context.activity.conversation:
            return

        key = f"conversation/{context.activity.conversation.id}"
        changes = {key: asdict(data)}
        await self.storage.write(changes)
        logger.debug(f"Saved conversation data: {changes}")

    async def get_user_profile(self, context: TurnContext) -> UserProfile:
        """Get user profile for the current context."""
        if not context.activity.from_property:
            return UserProfile()

        key = f"user/{context.activity.from_property.id}"
        items = await self.storage.read([key])

        if key not in items:
            items[key] = UserProfile()

        return UserProfile(**items[key])

    async def save_user_profile(
        self, context: TurnContext, profile: UserProfile
    ) -> None:
        """Save user profile for the current context."""
        if not context.activity.from_property:
            return

        key = f"user/{context.activity.from_property.id}"
        changes = {key: asdict(profile)}
        await self.storage.write(changes)
        logger.debug(f"Saved user profile: {changes}")

    async def clear_state(self, context: TurnContext) -> None:
        """Clear all state data for the current context."""
        if not (context.activity.conversation and context.activity.from_property):
            return

        conv_id = context.activity.conversation.id
        user_id = context.activity.from_property.id
        conv_key = f"conversation/{conv_id}"
        user_key = f"user/{user_id}"
        await self.storage.delete([conv_key, user_key])
        logger.info(f"Cleared state for conversation {conv_id} and user {user_id}")
