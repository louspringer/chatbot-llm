"""
# Ontology: cortexteams:CardActions
# Implements: cortexteams:AdaptiveCards
# Requirement: REQ-BOT-003 Teams card actions
# Guidance: guidance:BotPatterns#CardActions
# Description: Teams Adaptive Card action handlers
"""

from typing import Dict, Any, Callable, Awaitable
from botbuilder.core import TurnContext
from botbuilder.schema import Activity

from .card_templates import ErrorCard


class CardActionHandler:
    """Handler for Teams Adaptive Card actions."""

    def __init__(self):
        """Initialize the action handler."""
        self._action_handlers: Dict[str, Callable[
            [TurnContext, Dict[str, Any]], Awaitable[Activity]
        ]] = {}

    def register_action(
        self,
        action_name: str,
        handler: Callable[[TurnContext, Dict[str, Any]], Awaitable[Activity]]
    ) -> None:
        """Register an action handler.

        Args:
            action_name: The name of the action to handle
            handler: The async function to handle the action
        """
        self._action_handlers[action_name] = handler

    async def handle_action(
        self,
        turn_context: TurnContext,
        action_data: Dict[str, Any]
    ) -> Activity:
        """Handle an action from a card.

        Args:
            turn_context: The turn context
            action_data: The action data from the card

        Returns:
            The activity to respond with
        """
        action = action_data.get("action")
        if not action:
            return await self._handle_unknown_action(turn_context, action_data)

        handler = self._action_handlers.get(action)
        if not handler:
            return await self._handle_unknown_action(turn_context, action_data)

        try:
            return await handler(turn_context, action_data)
        except Exception as e:
            return await self._handle_action_error(turn_context, str(e))

    async def _handle_unknown_action(
        self,
        turn_context: TurnContext,
        action_data: Dict[str, Any]
    ) -> Activity:
        """Handle an unknown action.

        Args:
            turn_context: The turn context
            action_data: The action data from the card

        Returns:
            An error activity
        """
        error_card = ErrorCard.create(
            "Unknown action received",
            error_id="ERR-UNKNOWN-ACTION"
        )
        return Activity(
            type="message",
            attachments=[{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": error_card
            }]
        )

    async def _handle_action_error(
        self,
        turn_context: TurnContext,
        error_message: str
    ) -> Activity:
        """Handle an error during action processing.

        Args:
            turn_context: The turn context
            error_message: The error message

        Returns:
            An error activity
        """
        error_card = ErrorCard.create(
            error_message,
            error_id="ERR-ACTION-FAILED"
        )
        return Activity(
            type="message",
            attachments=[{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": error_card
            }]
        )
