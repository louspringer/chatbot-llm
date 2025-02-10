"""
Bot package initialization.
"""

from .teams_bot import TeamsBot
from .state_manager import StateManager
from .error_middleware import ErrorHandlingMiddleware
from .conversation_state import ConversationState
from .user_profile import UserProfile

__all__ = [
    "TeamsBot",
    "StateManager",
    "ErrorHandlingMiddleware",
    "ConversationState",
    "UserProfile"
]