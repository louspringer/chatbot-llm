"""
# Ontology: cortexteams:TeamsBot
# Implements: cortexteams:BotImplementation
# Requirement: REQ-BOT-000 Teams Bot Implementation
# Guidance: guidance:BotPatterns#Implementation
# Description: Main Teams bot implementation

Main implementation of the Teams bot.
"""

from typing import Dict, Optional, List
import logging

from botbuilder.core import (
    TurnContext,
    ConversationState,
    UserState,
    Storage,
    ActivityHandler,
    Middleware,
    BotAdapter
)
from botbuilder.schema import ConversationReference, ActivityTypes

from .state_manager import StateManager
from .error_middleware import ErrorHandlingMiddleware
from .user_profile import UserProfile


logger = logging.getLogger(__name__)


class TeamsBot(ActivityHandler):
    """Teams bot implementation."""

    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        storage: Storage,
        middleware: Optional[List[Middleware]] = None,
        adapter: Optional[BotAdapter] = None
    ) -> None:
        """Initialize the bot."""
        if not conversation_state:
            raise ValueError("conversation_state cannot be None")
        if not user_state:
            raise ValueError("user_state cannot be None")
        if not storage:
            raise ValueError("storage cannot be None")

        super().__init__()
        self.conversation_state = conversation_state
        self.user_state = user_state
        self._storage = storage
        self._conversation_references: Dict[str, ConversationReference] = {}
        self._adapter = adapter
        self._state_manager = None
        
        # Add error handling middleware
        if middleware is None:
            middleware = []
        error_middleware = ErrorHandlingMiddleware()
        middleware.append(error_middleware)
        for middleware_instance in middleware:
            if self._adapter:
                self._adapter.use(middleware_instance)

    async def on_turn(self, turn_context: TurnContext) -> None:
        """Handle bot framework turn."""
        if turn_context.activity.type == ActivityTypes.message:
            # Get conversation ID
            if not turn_context.activity.conversation:
                raise ValueError("No conversation context available")
                
            conversation_id = turn_context.activity.conversation.id
            if not conversation_id:
                raise ValueError("No conversation ID available")

            # Initialize state manager
            self._state_manager = StateManager(self._storage, conversation_id)
            await self._state_manager.initialize()

            try:
                # Process the message
                await self.on_message_activity(turn_context)

                # Save state changes
                await self.conversation_state.save_changes(turn_context)
                await self.user_state.save_changes(turn_context)

            except Exception as e:
                if self._state_manager:
                    await self._state_manager.handle_error(turn_context, e)
                await turn_context.send_activity(
                    "I encountered an error processing your request."
                )

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle message activities."""
        if not turn_context.activity.conversation:
            raise ValueError("No conversation context available")
            
        conversation_id = turn_context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")

        if not self._state_manager:
            self._state_manager = StateManager(self._storage, conversation_id)
            await self._state_manager.initialize()

        try:
            # Process the message
            message = turn_context.activity.text
            if not message:
                await turn_context.send_activity(
                    "I received an empty message."
                )
                return

            # Save the conversation reference
            self._conversation_references[conversation_id] = (
                TurnContext.get_conversation_reference(turn_context.activity)
            )

            # Send acknowledgment
            await turn_context.send_activity(
                f"Processing your message: {message}"
            )

        except Exception as e:
            if self._state_manager:
                await self._state_manager.handle_error(turn_context, e)
            await turn_context.send_activity(
                "I encountered an error processing your message."
            )

    def get_conversation_reference(
        self, conversation_id: str
    ) -> Optional[ConversationReference]:
        """Get the conversation reference for a conversation ID."""
        return self._conversation_references.get(conversation_id)

    async def on_members_added_activity(
        self,
        members_added,
        turn_context: TurnContext
    ):
        """Handle members being added with state initialization."""
        for member in members_added:
            if member.id and turn_context.activity.recipient:
                if member.id != turn_context.activity.recipient.id:
                    try:
                        # Initialize user profile
                        user_profile = UserProfile(
                            name=member.name or "User"
                        )
                        if self._state_manager:
                            await self._state_manager.save_user_profile(
                                turn_context,
                                user_profile
                            )
                        
                        # Send welcome message
                        welcome_text = (
                            f"Welcome {user_profile.name}! "
                            "I'm your Snowflake Cortex Teams Bot assistant."
                        )
                        await turn_context.send_activity(welcome_text)
                        logger.info(
                            f"Sent welcome message to {user_profile.name}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error in members added processing: {str(e)}"
                        )
                        raise

    async def on_conversation_update_activity(self, turn_context: TurnContext):
        """Handle conversation updates with state cleanup."""
        if turn_context.activity.members_added:
            await self.on_members_added_activity(
                turn_context.activity.members_added,
                turn_context
            )
        elif turn_context.activity.members_removed:
            try:
                # Clean up state for removed members
                if self._state_manager:
                    await self._state_manager.clear_state(turn_context)
                logger.info("Cleared state for removed members")
            except Exception as e:
                logger.error(
                    f"Error in conversation update processing: {str(e)}"
                )
                raise
