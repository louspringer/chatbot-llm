"""
# Ontology: cortexteams:StateManagement
# Implements: cortexteams:ConversationState
# Requirement: REQ-BOT-001 Conversation state management
# Description: Defines the states for the conversation FSM.
"""

from enum import Enum


class ConversationState(Enum):
    """Conversation states for the Teams bot."""

    IDLE = "IDLE"
    AUTHENTICATING = "AUTHENTICATING"
    QUERYING = "QUERYING"
    PROCESSING = "PROCESSING"
    RESPONDING = "RESPONDING"
    ERROR = "ERROR"
    COMPLETED = "COMPLETED"
    INITIALIZED = "INITIALIZED"
    AUTHENTICATED = "AUTHENTICATED"
