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
from botbuilder.schema import (
    ConversationReference,
    ActivityTypes,
    Activity,
    ChannelAccount,
)

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
        if not state_manager:
            raise ValueError("state_manager cannot be None")

        super().__init__()
        self._config = config
        self._state_manager = state_manager
        self._adapter = None
        self._conversation_references: Dict[str, ConversationReference] = {}
        self._error_middleware = None

        # Add error handling middleware
        if middleware is None:
            middleware = []
        self._error_middleware = ErrorHandlingMiddleware(state_manager)
        middleware.append(self._error_middleware)
        for middleware_instance in middleware:
            if self._adapter:
                self._adapter.use(middleware_instance)

    async def _validate_conversation_context(
        self, turn_context: TurnContext
    ) -> str:
        """Validate conversation context and return conversation ID."""
        if not turn_context.activity.conversation:
            raise ValueError("No conversation context available")

        conversation_id = turn_context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")
        return conversation_id

    async def _process_message_turn(
        self, turn_context: TurnContext, conversation_id: str
    ) -> None:
        """Process a message turn and save state."""
        # Get and save conversation data
        conv_data = await self._state_manager.get_conversation_data(
            turn_context
        )
        await self._state_manager.save_conversation_data(
            turn_context, conv_data
        )

    async def _handle_message_activity(
        self, turn_context: TurnContext, conversation_id: str
    ) -> None:
        """Handle a message activity."""
        message = turn_context.activity.text
        if not message:
            await turn_context.send_activity("I received an empty message.")
            return

        # Save the conversation reference
        self._conversation_references[conversation_id] = (
            TurnContext.get_conversation_reference(turn_context.activity)
        )

        # Send acknowledgment
        await turn_context.send_activity(
            f"Processing your message: {message}"
        )

    async def on_turn(self, turn_context: TurnContext) -> None:
        """Process each turn of the conversation."""
        await super().on_turn(turn_context)

        try:
            # Validate conversation context
            await self._validate_conversation_context(turn_context)

            # Process the message if it's a message activity
            if turn_context.activity.type == ActivityTypes.message:
                await self.on_message_activity(turn_context)
            elif (
                turn_context.activity.type == ActivityTypes.conversation_update
                and turn_context.activity.members_added
            ):
                await self.on_members_added_activity(
                    turn_context.activity.members_added,
                    turn_context
                )

        except Exception as error:
            logger.error("Error processing message: %s", str(error))
            raise

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle incoming message activity."""
        await self._handle_message(turn_context)

    async def _handle_message(self, turn_context: TurnContext):
        """Process incoming message."""
        message_text = turn_context.activity.text.strip()

        try:
            response = await self._process_message(message_text)
            await turn_context.send_activity(response)
        except Exception:
            # Let the error middleware handle it through on_turn
            raise

    async def _process_message(self, message: str) -> Activity:
        """Process message and generate response."""
        try:
            # Add message processing logic here
            return Activity(
                type=ActivityTypes.message,
                text=f"Received: {message}"
            )
        except Exception as error:
            logger.error("Error processing message: %s", str(error))
            raise

    def get_conversation_reference(
        self, conversation_id: str
    ) -> Optional[ConversationReference]:
        """Get the conversation reference for a conversation ID."""
        return self._conversation_references.get(conversation_id)

    async def _handle_member_added(
        self, member: Any, turn_context: TurnContext
    ) -> None:
        """Handle a new member being added."""
        # Initialize user profile
        user_profile = UserProfile(name=member.name or "User")
        await self._state_manager.save_user_profile(turn_context, user_profile)

        # Send welcome message
        welcome_text = (
            f"Welcome {user_profile.name}! "
            "I'm your Snowflake Cortex Teams Bot assistant."
        )
        await turn_context.send_activity(welcome_text)
        logger.info(f"Sent welcome message to {user_profile.name}")

    async def on_members_added_activity(
        self,
        members_added: List[ChannelAccount],
        turn_context: TurnContext
    ):
        """Handle members added to conversation."""
        for member in members_added:
            recipient = turn_context.activity.recipient
            if recipient and member.id != recipient.id:
                await turn_context.send_activity("Welcome to the Teams bot!")

    async def on_conversation_update_activity(
        self, turn_context: TurnContext
    ) -> None:
        """Handle conversation updates with state cleanup."""
        if turn_context.activity.members_added:
            await self.on_members_added_activity(
                turn_context.activity.members_added,
                turn_context
            )
        elif turn_context.activity.members_removed:
            try:
                await self._state_manager.clear_state(turn_context)
                logger.info("Cleared state for removed members")
            except Exception as error:
                logger.error(
                    "Error in conversation update processing: %s",
                    str(error)
                )
                raise
