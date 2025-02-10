# flake8: noqa: E501
"""
# Ontology: cortexteams:UserProfile
# Implements: cortexteams:UserProfileManagement
# Requirement: REQ-BOT-002 User profile management
# Guidance: guidance:BotPatterns#UserProfile
# Description: Manages user profile data and preferences

User profile management for the Teams bot.
"""

from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional

from botbuilder.core import StoreItem


@dataclass
class UserProfile(StoreItem):
    """Data stored for each user."""

    name: str = ""
    preferred_language: str = "en-US"
    last_interaction: str = ""
    permissions: List[str] = field(default_factory=list)
    query_history: List[Dict[str, Any]] = field(default_factory=list)
    etag: str = "*"

    def validate(self) -> bool:
        """Validate user profile data."""
        try:
            # Validate last interaction timestamp
            if self.last_interaction:
                datetime.fromisoformat(self.last_interaction)

            # Validate permissions
            if not isinstance(self.permissions, list):
                return False

            # Validate query history
            for query in self.query_history:
                if not isinstance(query, dict) or "query" not in query or "timestamp" not in query:
                    return False
                datetime.fromisoformat(query["timestamp"])

            return True
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
