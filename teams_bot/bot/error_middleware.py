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
from datetime import datetime
from typing import Callable, Awaitable, Optional
from botbuilder.core import Middleware, TurnContext
from botbuilder.schema import Activity, ActivityTypes

from .state_manager import StateManager

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(Middleware):
    """Error handling middleware for the Teams bot."""

    def __init__(self, state_manager: StateManager):
        """Initialize the middleware with state manager."""
        self._state_manager = state_manager

    async def on_turn(
        self, 
        context: TurnContext, 
        next: Callable[[TurnContext], Awaitable]
    ) -> None:
        """Handle errors during turn processing."""
        try:
            await next(context)
        except Exception as e:
            error_id = await self._log_error(context, e)
            error_type = self._categorize_error(e)
            
            # Create checkpoint for critical errors
            if error_type in ["system_error", "state_error"]:
                await self._state_manager.create_checkpoint()
                raise  # Re-raise critical errors after checkpoint
            
            # Transition to error state
            await self._state_manager.trigger_transition(
                context,
                "error",
                None
            )
            
            # Send error response with reference ID
            await context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=f"I encountered an error. Reference ID: {error_id}\n"
                         f"Please try again later."
                )
            )

    async def _log_error(self, context: TurnContext, error: Exception) -> str:
        """Log error with context and return reference ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        error_id = f"ERR-{timestamp}"
        
        error_details = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "conversation_id": context.activity.conversation.id,
            "user_id": context.activity.from_property.id,
            "activity_id": context.activity.id,
            "timestamp": timestamp
        }
        
        logger.error(
            "Bot Error: %s\nDetails: %s",
            error_id,
            error_details,
            exc_info=error
        )
        
        return error_id

    def _categorize_error(self, error: Exception) -> str:
        """Categorize the error type."""
        error_type = type(error).__name__
        
        if error_type in ["PermissionError", "UnauthorizedError"]:
            return "auth_error"
        elif error_type in ["TimeoutError", "AsyncTimeoutError"]:
            return "timeout_error"
        elif error_type in ["SystemError", "RuntimeError"]:
            return "system_error"
        elif error_type in ["ValueError", "TypeError"]:
            return "validation_error"
        elif error_type in ["StateError", "TransitionError"]:
            return "state_error"
        else:
            return "unknown_error" 