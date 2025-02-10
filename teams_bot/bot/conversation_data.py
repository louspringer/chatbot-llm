# flake8: noqa: E501
"""
# Ontology: cortexteams:ConversationData
# Implements: cortexteams:ConversationDataManagement
# Requirement: REQ-BOT-004 Conversation data management
# Guidance: guidance:BotPatterns#ConversationData
# Description: Manages conversation data and state

Conversation data management for the Teams bot.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, cast, TYPE_CHECKING
import json
import logging
import asyncio

from transitions.extensions.asyncio import AsyncMachine

from .conversation_state import ConversationState

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)

# Maximum error count before forcing reset
MAX_ERROR_COUNT = 3


@dataclass
class ConversationData:
    """Class to store conversation data."""

    conversation_id: str
    current_state: ConversationState = ConversationState.INITIALIZED
    last_message_id: Optional[str] = None
    active_query: Optional[str] = None
    last_response: Optional[str] = None
    conversation_references: Dict[str, Any] = field(default_factory=dict)
    last_activity: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    state_history: List[Dict[str, str]] = field(default_factory=list)
    state_manager: Optional["StateManager"] = None
    checkpoint_data: Optional[Dict[str, Any]] = None
    checkpoint_timestamp: Optional[str] = None
    error_count: int = 0
    _machine: Optional[AsyncMachine] = None

    def __post_init__(self) -> None:
        """Initialize the state machine."""
        if not self.conversation_id:
            raise ValueError("conversation_id cannot be None or empty")
        self._initialize_state_machine()

    def _initialize_state_machine(self) -> None:
        """Initialize the state machine."""
        try:
            # Create list of states from enum
            states = [state.value.lower() for state in ConversationState]

            # Create state machine
            machine = AsyncMachine(
                model=self,
                states=states,
                initial=self.current_state.value.lower(),
                auto_transitions=False,
                send_event=True,
                queued=True,
            )

            # Add transitions
            transitions = [
                {
                    "trigger": "start_auth",
                    "source": "initialized",
                    "dest": "authenticating",
                    "prepare": ["validate_transition"],
                },
                {
                    "trigger": "auth_success",
                    "source": "authenticating",
                    "dest": "authenticated",
                    "prepare": ["validate_transition"],
                },
                {
                    "trigger": "start_query",
                    "source": ["authenticated", "idle"],
                    "dest": "querying",
                    "prepare": ["validate_transition"],
                },
                {
                    "trigger": "process_query",
                    "source": "querying",
                    "dest": "processing",
                    "prepare": ["validate_transition"],
                },
                {
                    "trigger": "send_response",
                    "source": "processing",
                    "dest": "responding",
                    "prepare": ["validate_transition"],
                },
                {
                    "trigger": "complete",
                    "source": "responding",
                    "dest": "idle",
                    "prepare": ["validate_transition"],
                },
                {"trigger": "error", "source": "*", "dest": "error"},
                {"trigger": "reset", "source": "*", "dest": "initialized"},
            ]

            machine.add_transitions(transitions)
            self._machine = machine
        except Exception as e:
            logger.error(f"Failed to initialize state machine: {e}")
            self._machine = None

    async def validate_transition(self, event_data: Any) -> bool:
        """Validate state transition."""
        if event_data is None or not hasattr(event_data, "transition"):
            logger.error("Invalid event data")
            return False

        try:
            # Get target state from transition
            target_state = event_data.transition.dest
            target_state_enum = ConversationState(target_state.upper())

            # Validate state invariants
            if not await self.check_state_timeout():
                return False

            # Record state transition in history
            self.state_history.append(
                {
                    "from_state": self.current_state.value,
                    "to_state": target_state_enum.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            return True

        except Exception as e:
            logger.error(f"Transition validation failed: {e}")
            self.error_count += 1

            if self._machine is not None:
                try:
                    # Transition to error state
                    await self._machine.trigger("error")

                    # Reset if max errors reached
                    if self.error_count >= MAX_ERROR_COUNT:
                        self.error_count = 0
                        await self._machine.trigger("reset")
                except Exception as e2:
                    logger.error(f"Failed to handle error state: {e2}")

            return False

    async def check_state_timeout(self) -> bool:
        """Check if the current state has timed out."""
        try:
            if not self.last_activity:
                return True

            last_activity = datetime.fromisoformat(self.last_activity)
            now = datetime.utcnow()
            timeout = (now - last_activity).total_seconds()

            # Different timeouts for different states
            if self.current_state == ConversationState.AUTHENTICATING and timeout > 300:
                logger.error("Authentication timeout")
                return False
            elif self.current_state == ConversationState.QUERYING and timeout > 60:
                logger.error("Query timeout")
                return False
            elif self.current_state == ConversationState.PROCESSING and timeout > 120:
                logger.error("Processing timeout")
                return False

            return True

        except Exception as e:
            logger.error(f"Timeout check failed: {e}")
            return False

    async def create_checkpoint(self) -> None:
        """Create a checkpoint of the current state."""
        timestamp = datetime.utcnow().isoformat()
        self.checkpoint_data = {
            "current_state": self.current_state.value,
            "conversation_references": (
                self.conversation_references.copy()
                if self.conversation_references
                else {}
            ),
            "active_query": self.active_query,
            "last_response": self.last_response,
            "error_count": self.error_count,
            "last_activity": self.last_activity,
            "state_history": self.state_history.copy() if self.state_history else [],
            "last_message_id": self.last_message_id,
        }
        self.checkpoint_timestamp = timestamp

    def has_valid_checkpoint(self) -> bool:
        """Check if there is a valid checkpoint."""
        if not self.checkpoint_data or not self.checkpoint_timestamp:
            return False
        try:
            checkpoint_time = datetime.fromisoformat(self.checkpoint_timestamp)
            age = (datetime.utcnow() - checkpoint_time).total_seconds()
            return age <= 86400  # 24 hours
        except Exception as e:
            logger.error(f"Failed to validate checkpoint: {e}")
            return False

    async def restore_checkpoint(self) -> bool:
        """Restore from checkpoint."""
        if not self.has_valid_checkpoint():
            return False
        try:
            if self.checkpoint_data:
                # Restore all fields from checkpoint
                for key, value in self.checkpoint_data.items():
                    if hasattr(self, key):
                        if key == "current_state":
                            self.current_state = ConversationState(value)
                        elif key in ["conversation_references", "state_history"]:
                            setattr(self, key, value.copy())
                        else:
                            setattr(self, key, value)

                # Reset the state machine to match
                if self._machine is not None and hasattr(self._machine, "set_state"):
                    try:
                        state = self.current_state.value.lower()
                        if asyncio.iscoroutinefunction(self._machine.set_state):
                            await self._machine.set_state(state)
                        else:
                            logger.warning("State machine set_state is not async")
                    except Exception as e:
                        logger.error(f"Failed to set state machine state: {e}")

                return True
            return False
        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with encryption of sensitive fields."""
        data = {
            "conversation_id": self.conversation_id,
            "current_state": self.current_state.value,
            "last_activity": self.last_activity,
            "state_history": self.state_history,
            "error_count": self.error_count,
        }

        # Encrypt sensitive fields if state manager is available
        if self.state_manager:
            sensitive_fields = {
                "active_query": self.active_query,
                "last_response": self.last_response,
                "conversation_references": self.conversation_references,
                "last_message_id": self.last_message_id,
            }

            for field, value in sensitive_fields.items():
                if value is not None:
                    try:
                        # Convert to JSON string first
                        json_str = json.dumps(value)
                        # Encrypt and encode as base64
                        encrypted = self.state_manager.encrypt(json_str.encode())
                        data[field] = encrypted
                    except Exception as e:
                        logger.error(f"Failed to encrypt {field}: {e}")
                        data[field] = None
                else:
                    data[field] = None

        return data

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], state_manager: Optional["StateManager"] = None
    ) -> "ConversationData":
        """Create from dictionary with decryption of sensitive fields."""
        if not data or "conversation_id" not in data:
            raise ValueError("Invalid data dictionary")

        instance = cls(conversation_id=data["conversation_id"])
        instance.state_manager = state_manager

        # Set non-sensitive fields
        if "current_state" in data:
            instance.current_state = ConversationState(data["current_state"])
        if "last_activity" in data:
            instance.last_activity = data["last_activity"]
        if "state_history" in data:
            instance.state_history = data["state_history"]
        if "error_count" in data:
            instance.error_count = data["error_count"]

        # Decrypt sensitive fields if state manager is available
        if state_manager:
            sensitive_fields = [
                "active_query",
                "last_response",
                "conversation_references",
                "last_message_id",
            ]

            for field in sensitive_fields:
                if field in data and data[field]:
                    try:
                        # Decrypt value
                        decrypted = state_manager.decrypt(data[field])
                        # Parse JSON string
                        value = json.loads(decrypted)
                        setattr(instance, field, value)
                    except Exception as e:
                        logger.error(f"Failed to decrypt {field}: {e}")
                        setattr(instance, field, None)
                else:
                    setattr(instance, field, None)

        return instance
