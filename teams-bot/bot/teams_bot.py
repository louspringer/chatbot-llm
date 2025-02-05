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

        logger.info("TeamsBot initialized")

    async def on_turn(self, turn_context: TurnContext):
        logger.info(f"Processing activity: {turn_context.activity.type}")
        await super().on_turn(turn_context)

        # Save state changes after the turn
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        logger.info("Processing message activity")
        text = turn_context.activity.text.lower()

        # For local testing, just send text response
        if turn_context.activity.channel_id == "emulator":
            await turn_context.send_activity(f"Echo: {text}")
            return

        # Create proper Activity for Teams
        response = Activity(
            type="message",
            text=f"Echo: {text}",
            service_url=turn_context.activity.service_url
        )

        await turn_context.send_activity(response)
        logger.info(f"Sent response: {response.text}")
