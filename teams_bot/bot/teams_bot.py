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
        if not state_manager:
            raise ValueError("state_manager cannot be None")
            
        super().__init__()
        self._config = config
        self._state_manager = state_manager
        self._adapter = None
        self._conversation_references: Dict[str, ConversationReference] = {}
        
        # Add error handling middleware
        if middleware is None:
            middleware = []
        error_middleware = ErrorHandlingMiddleware(state_manager)
        middleware.append(error_middleware)
        for middleware_instance in middleware:
            if self._adapter:
                self._adapter.use(middleware_instance)

    async def _validate_conversation_context(
        self,
        turn_context: TurnContext
    ) -> str:
        """Validate conversation context and return conversation ID."""
        if not turn_context.activity.conversation:
            raise ValueError("No conversation context available")
            
        conversation_id = turn_context.activity.conversation.id
        if not conversation_id:
            raise ValueError("No conversation ID available")
        return conversation_id

    async def _process_message_turn(
        self,
        turn_context: TurnContext,
        conversation_id: str
    ) -> None:
        """Process a message turn and save state."""
        # Get and save conversation data
        conv_data = await self._state_manager.get_conversation_data(
            turn_context
        )
        await self._state_manager.save_conversation_data(
            turn_context,
            conv_data
        )

    async def _handle_message_activity(
        self,
        turn_context: TurnContext,
        conversation_id: str
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
        await turn_context.send_activity(f"Processing your message: {message}")

    async def on_turn(self, turn_context: TurnContext) -> None:
        """Process each turn of the conversation."""
        await super().on_turn(turn_context)
        
        try:
            conversation_id = await self._validate_conversation_context(
                turn_context
            )
            
            # Process the message if it's a message activity
            if turn_context.activity.type == ActivityTypes.message:
                await self._handle_message_activity(
                    turn_context,
                    conversation_id
                )
                await self._process_message_turn(
                    turn_context,
                    conversation_id
                )
                
        except Exception as error:
            logger.error("Error processing message: %s", str(error))
            raise

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle message activities."""
        try:
            conversation_id = await self._validate_conversation_context(
                turn_context
            )
            await self._handle_message_activity(turn_context, conversation_id)
        except Exception as e:
            if self._state_manager:
                await self._state_manager.handle_error(turn_context, e)
            await turn_context.send_activity(
                "I encountered an error processing your message."
            )

    def get_conversation_reference(
        self,
        conversation_id: str
    ) -> Optional[ConversationReference]:
        """Get the conversation reference for a conversation ID."""
        return self._conversation_references.get(conversation_id)

    async def _handle_member_added(
        self,
        member: Any,
        turn_context: TurnContext
    ) -> None:
        """Handle a new member being added."""
        # Initialize user profile
        user_profile = UserProfile(name=member.name or "User")
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
        logger.info(f"Sent welcome message to {user_profile.name}")

    async def on_members_added_activity(
        self,
        members_added: List[Any],
        turn_context: TurnContext
    ) -> None:
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
                    await self._handle_member_added(member, turn_context)
                except Exception as e:
                    logger.error(
                        f"Error in members added processing: {str(e)}"
                    )
                    raise

    async def on_conversation_update_activity(
        self,
        turn_context: TurnContext
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
            except Exception as e:
                logger.error(
                    f"Error in conversation update processing: {str(e)}"
                )
                raise
