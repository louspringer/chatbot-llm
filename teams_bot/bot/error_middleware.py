# flake8: noqa: E501
"""
# Ontology: cortexteams:ErrorHandling
# Implements: cortexteams:ErrorMiddleware
# Requirement: REQ-BOT-003 Error handling
# Guidance: guidance:BotPatterns#ErrorHandling
# Description: Error handling middleware for the Teams bot

Error handling middleware implementation.
"""

import logging
from typing import Callable, Awaitable
from botbuilder.core import Middleware, TurnContext

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(Middleware):
    """Error handling middleware for the Teams bot."""

    async def on_turn(
        self, 
        context: TurnContext, 
        next: Callable[[TurnContext], Awaitable]
    ) -> None:
        """Handle errors during turn processing."""
        try:
            await next(context)
        except Exception as e:
            logger.error(f"Error in middleware: {str(e)}")
            await context.send_activity(
                "I encountered an error. Please try again later."
            ) 