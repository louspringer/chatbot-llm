"""
# Ontology: cortexteams:TeamsBot
# Implements: cortexteams:BotImplementation
# Requirement: REQ-BOT-000 Teams Bot Implementation
# Guidance: guidance:BotPatterns#Implementation
# Description: Main Teams bot implementation

Main implementation of the Teams bot.
"""

from typing import Dict, Optional, List, Any
import logging

from botbuilder.core import ActivityHandler, TurnContext, Middleware
from botbuilder.schema import ConversationReference, ActivityTypes

from .state_manager import StateManager
from .error_middleware import ErrorHandlingMiddleware
from .user_profile import UserProfile


logger = logging.getLogger(__name__)


class TeamsBot(ActivityHandler):
    """Teams bot implementation."""

    def __init__(
        self,
        config: Dict[str, Any],
        state_manager: StateManager,
        middleware: Optional[List[Middleware]] = None,
    ):
        """Initialize the Teams bot.

        Args:
            config: Configuration dictionary
            state_manager: State manager instance
            middleware: Optional list of middleware to add
        """
        super().__init__()
        self._config = config
        self._state_manager = state_manager
        self._adapter = None
        self._conversation_references: Dict[str, ConversationReference] = {}
        
        # Add error handling middleware
        if middleware is None:
            middleware = []
        error_middleware = ErrorHandlingMiddleware(self._state_manager)
        middleware.append(error_middleware)
        for middleware_instance in middleware:
            if self._adapter:
                self._adapter.use(middleware_instance)

    async def on_turn(self, turn_context: TurnContext):
        """Save state on every turn."""
        await super().on_turn(turn_context)
        
        # Get conversation ID
        if not turn_context.activity.conversation:
            raise ValueError("No conversation context available")
            
        conversation_id = turn_context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")

        try:
            # Process the message
            if turn_context.activity.type == ActivityTypes.message:
                await self.on_message_activity(turn_context)
            
            # Get and save conversation data
            conv_data = await self._state_manager.get_conversation_data(
                turn_context
            )
            await self._state_manager.save_conversation_data(
                turn_context, conv_data
            )
            
        except Exception as error:
            logging.error("Error processing message: %s", str(error))
            raise

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle message activities."""
        if not turn_context.activity.conversation:
            raise ValueError("No conversation context available")
            
        conversation_id = turn_context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")

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
            # Check if the member added is not the bot itself
            is_not_bot = (
                member.id and 
                turn_context.activity.recipient and 
                member.id != turn_context.activity.recipient.id
            )
            if is_not_bot:
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
