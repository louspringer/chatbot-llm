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
import types

from transitions.extensions.asyncio import AsyncMachine
from transitions.core import MachineError

from .conversation_state import ConversationState

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)

# Maximum error count before forcing reset
MAX_ERROR_COUNT = 3

@dataclass
class ConversationData:
    """Class to manage conversation data and state transitions."""

    conversation_id: str
    current_state: ConversationState = ConversationState.INITIALIZED
    last_message_id: Optional[str] = None
    active_query: Optional[str] = None
    last_response: Optional[str] = None
    conversation_references: Dict[str, Any] = field(default_factory=dict)
    last_activity: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    state_history: List[Dict[str, str]] = field(default_factory=list)
    checkpoint_data: Optional[Dict[str, Any]] = None
    checkpoint_timestamp: Optional[str] = None
    error_count: int = 0
    _machine: Optional[AsyncMachine] = None
    state_manager: Optional[Any] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        """Initialize the state machine."""
        if not self.conversation_id:
            raise ValueError("conversation_id cannot be None or empty")
        self._initialize_state_machine()

    def _initialize_state_machine(self) -> None:
        """Initialize the state machine with states and transitions."""
        if self._machine is not None:
            return

        # Define transitions
        transitions = [
            {
                "trigger": "start_auth",
                "source": ConversationState.INITIALIZED,
                "dest": ConversationState.AUTHENTICATING,
                "after": ["_after_state_change"],
            },
            {
                "trigger": "auth_complete",
                "source": ConversationState.AUTHENTICATING,
                "dest": ConversationState.AUTHENTICATED,
                "after": ["_after_state_change"],
            },
            {
                "trigger": "start_query",
                "source": ConversationState.AUTHENTICATED,
                "dest": ConversationState.QUERYING,
                "after": ["_after_state_change"],
            },
            {
                "trigger": "query_complete",
                "source": ConversationState.QUERYING,
                "dest": ConversationState.AUTHENTICATED,
                "after": ["_after_state_change"],
            },
            {
                "trigger": "error",
                "source": "*",
                "dest": ConversationState.ERROR,
                "after": ["_after_state_change"],
            },
            {
                "trigger": "reset",
                "source": "*",
                "dest": ConversationState.INITIALIZED,
                "before": ["_handle_reset"],
                "after": ["_after_state_change"],
            },
        ]

        # Create the state machine
        self._machine = AsyncMachine(
            states=list(ConversationState),
            transitions=transitions,
            initial=self.current_state,
            before_state_change=self._before_state_change,
            after_state_change=self._after_state_change,
            prepare_event=self._before_event,
            send_event=True,
            queued=True,
        )

        # Bind the machine to self
        self._machine.add_model(self)

    def _before_event(self, event_data):
        """Called before any event is triggered."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
            
        valid_triggers = self._machine.get_triggers(event_data.state.name)
        if event_data.event.name not in valid_triggers:
            self.error_count += 1
            msg = f"Invalid transition attempted: Cannot trigger {event_data.event.name} from state {event_data.state.name}"
            logger.warning(msg)
            raise MachineError(msg)
            
        return True

    def _before_state_change(self, event_data):
        """Called before state changes to update last activity time."""
        self.last_activity = datetime.utcnow().isoformat()

    def _after_state_change(self, event_data):
        """Called after state changes to update state history."""
        # Only add to state history if it's a new state
        if not self.state_history or self.state_history[-1]["state"] != event_data.state.name:
            self.state_history.append({
                "state": event_data.state.name,
                "timestamp": datetime.utcnow().isoformat(),
                "trigger": event_data.event.name if event_data.event else "",
            })
        # Update current state
        self.current_state = ConversationState(event_data.state.name)

    def _handle_reset(self, event_data):
        """Called before reset to clear error count and state history."""
        self.error_count = 0
        self.state_history = []

    async def create_checkpoint(self) -> None:
        """Create a checkpoint of the current state."""
        timestamp = datetime.utcnow().isoformat()
        self.checkpoint_data = {
            "current_state": self.current_state.value,
            "conversation_references": self.conversation_references.copy(),
            "active_query": self.active_query,
            "last_response": self.last_response,
            "error_count": self.error_count,
            "last_activity": self.last_activity,
            "state_history": self.state_history.copy(),
            "last_message_id": self.last_message_id,
        }
        self.checkpoint_timestamp = timestamp

    async def restore_checkpoint(self) -> bool:
        """Restore from the last checkpoint."""
        if not self.checkpoint_data:
            return False

        try:
            self.current_state = ConversationState(self.checkpoint_data["current_state"])
            self.conversation_references = self.checkpoint_data["conversation_references"].copy()
            self.active_query = self.checkpoint_data["active_query"]
            self.last_response = self.checkpoint_data["last_response"]
            self.error_count = self.checkpoint_data["error_count"]
            self.last_activity = self.checkpoint_data["last_activity"]
            self.state_history = self.checkpoint_data["state_history"].copy()
            self.last_message_id = self.checkpoint_data["last_message_id"]
            return True
        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {e}")
            return False

    def to_dict(self) -> dict:
        """Convert conversation data to dictionary."""
        data = {
            "conversation_id": self.conversation_id,
            "current_state": self.current_state.value,
            "last_activity": self.last_activity,
            "last_checkpoint_timestamp": self.checkpoint_timestamp,
            "error_count": self.error_count,
            "state_history": self.state_history,
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
                        json_str = json.dumps({"value": value})
                        # Encrypt and store
                        data[field] = self.state_manager.encrypt(json_str)
                    except Exception as e:
                        logger.error(f"Failed to encrypt {field}: {e}")
                        data[field] = None
                else:
                    data[field] = None
        else:
            data.update({
                "active_query": self.active_query,
                "last_response": self.last_response,
                "conversation_references": {},  # Empty dict when no state manager
                "last_message_id": self.last_message_id,
            })

        return data

    @classmethod
    def from_dict(cls, data: dict, state_manager: Optional[Any] = None) -> "ConversationData":
        """Create conversation data from dictionary."""
        instance = cls(
            conversation_id=data["conversation_id"],
            current_state=ConversationState(data["current_state"]),
        )
        instance.state_manager = state_manager
        instance.last_activity = data["last_activity"]
        instance.checkpoint_timestamp = data.get("last_checkpoint_timestamp")
        instance.error_count = data.get("error_count", 0)
        instance.state_history = data.get("state_history", [])

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
                        # Parse JSON string and extract value
                        value_dict = json.loads(decrypted)
                        value = value_dict.get("value")
                        setattr(instance, field, value)
                    except Exception as e:
                        logger.error(f"Failed to decrypt {field}: {e}")
                        setattr(instance, field, None)
                else:
                    setattr(instance, field, None)
        else:
            instance.active_query = data.get("active_query")
            instance.last_response = data.get("last_response")
            instance.conversation_references = {}  # Empty dict when no state manager
            instance.last_message_id = data.get("last_message_id")

        return instance

    async def _update_last_activity(self, event_data: Any) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow().isoformat()

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

            # Update current state
            self.current_state = target_state_enum

            # Record state transition in history
            self.state_history.append(
                {
                    "from_state": event_data.transition.source.upper(),
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
            elif timeout > 600:  # Global timeout of 10 minutes
                logger.error("Global timeout")
                return False

            return True

        except Exception as e:
            logger.error(f"Timeout check failed: {e}")
            return False

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

    def _on_invalid_trigger(self, event_data: Any) -> None:
        """Handle invalid transitions."""
        self.error_count += 1
        msg = f"Cannot trigger event {event_data.event.name} from state {event_data.state.name}!"
        logger.warning(msg)
        raise MachineError(msg)

    async def trigger(self, trigger: str, *args: Any, **kwargs: Any) -> None:
        """Trigger a state transition.
        
        Args:
            trigger: The name of the trigger to execute.
            *args: Positional arguments to pass to the trigger.
            **kwargs: Keyword arguments to pass to the trigger.
            
        Raises:
            ValueError: If state machine is not initialized.
            MachineError: If the transition is not valid.
            TimeoutError: If the transition times out.
        """
        if self._machine is None:
            raise ValueError("State machine not initialized")
        
        # Acquire the lock with a timeout
        try:
            async with self._lock:
                # Execute the transition with a timeout
                try:
                    await asyncio.wait_for(
                        self._machine.dispatch(trigger, *args, **kwargs),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Timeout during transition {trigger}")
                    raise
                except Exception as e:
                    logger.error(f"Error during transition {trigger}: {e}")
                    raise
        except Exception as e:
            logger.error(f"Error during transition {trigger}: {e}")
            raise

    # Public methods for triggering state transitions
    async def start_authentication(self) -> None:
        """Start the authentication process."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
        try:
            await self.start_auth()
        except MachineError as e:
            logger.error(f"Failed to start authentication: {e}")
            self.error_count += 1
            await self.handle_error()
            raise

    async def authentication_complete(self) -> None:
        """Handle successful authentication."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
        try:
            await self.auth_complete()
        except MachineError as e:
            logger.error(f"Failed to complete authentication: {e}")
            self.error_count += 1
            await self.handle_error()
            raise

    async def start_querying(self) -> None:
        """Start processing a query."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
        try:
            await self.start_query()
        except MachineError as e:
            logger.error(f"Failed to start query: {e}")
            self.error_count += 1
            await self.handle_error()
            raise

    async def querying_complete(self) -> None:
        """Handle query completion."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
        try:
            await self.query_complete()
        except MachineError as e:
            logger.error(f"Failed to complete query: {e}")
            self.error_count += 1
            await self.handle_error()
            raise

    async def handle_error(self) -> None:
        """Handle error state."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
        try:
            await self.error()
        except Exception as e:
            logger.error(f"Failed to handle error: {e}")
            raise

    async def reset_state(self) -> None:
        """Reset the state machine."""
        if self._machine is None:
            raise ValueError("State machine not initialized")
        try:
            await self.reset()
        except Exception as e:
            logger.error(f"Failed to reset state: {e}")
            raise

    async def cleanup(self) -> None:
        """Clean up resources."""
        # Nothing to clean up in this implementation
        pass
