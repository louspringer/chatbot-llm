"""
Teams Bot implementation.
"""

from botbuilder.core import (
    ActivityHandler,
    TurnContext,
    ConversationState,
    UserState
)
from botbuilder.schema import Activity
import logging
from datetime import datetime
from .state_manager import StateManager, UserProfile

logger = logging.getLogger(__name__)


class TeamsBot(ActivityHandler):
    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState
    ):
        if conversation_state is None:
            raise TypeError(
                "[TeamsBot]: conversation_state is required but None was given"
            )
        if user_state is None:
            raise TypeError(
                "[TeamsBot]: user_state is required but None was given"
            )

        self.conversation_state = conversation_state
        self.user_state = user_state
        self.state_manager = StateManager()
        logger.info("TeamsBot initialized")

    async def on_turn(self, turn_context: TurnContext):
        logger.info(f"Processing activity: {turn_context.activity.type}")
        await super().on_turn(turn_context)

        # Save state changes after the turn
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages."""
        logger.info("Processing message activity")
        
        # Get state data
        conversation_data = await self.state_manager.get_conversation_data(
            turn_context
        )
        user_profile = await self.state_manager.get_user_profile(turn_context)
        
        # Update state
        if turn_context.activity.id:
            conversation_data.last_message_id = turn_context.activity.id
        user_profile.last_interaction = datetime.utcnow().isoformat()
        
        # Get the input text
        text = turn_context.activity.text.lower() if turn_context.activity.text else ""
        response_text = f"Echo: {text}"

        # Create proper Activity for Teams
        if turn_context.activity.channel_id != "emulator":
            response = Activity(
                type="message",
                text=response_text,
                service_url=turn_context.activity.service_url
            )
        else:
            response = Activity(
                type="message",
                text=response_text
            )

        # Save state before sending response
        await self.state_manager.save_conversation_data(
            turn_context,
            conversation_data
        )
        await self.state_manager.save_user_profile(turn_context, user_profile)

        # Send response
        await turn_context.send_activity(response)
        logger.info(f"Sent response: {response.text}")

    async def on_members_added_activity(
        self,
        members_added,
        turn_context: TurnContext
    ):
        """Handle members being added to the conversation."""
        for member in members_added:
            if member.id and turn_context.activity.recipient:
                if member.id != turn_context.activity.recipient.id:
                    # Initialize user profile
                    user_profile = UserProfile(
                        name=member.name or "User"
                    )
                    await self.state_manager.save_user_profile(
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

    async def on_conversation_update_activity(self, turn_context: TurnContext):
        """Handle conversation update activities."""
        if turn_context.activity.members_added:
            await self.on_members_added_activity(
                turn_context.activity.members_added,
                turn_context
            )
        elif turn_context.activity.members_removed:
            # Clean up state for removed members
            await self.state_manager.clear_state(turn_context)
            logger.info("Cleared state for removed members")
