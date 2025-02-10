"""
Configure pytest for async testing.
"""

import pytest
from botbuilder.core import Storage, MemoryStorage
from ..bot.state_manager import StateManager


# Configure asyncio to use auto mode
@pytest.fixture(autouse=True)
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def memory_storage() -> Storage:
    """Create memory storage instance for testing."""
    return MemoryStorage()


@pytest.fixture
def state_manager_memory(storage):
    """Create a state manager instance with memory storage."""
    return StateManager(storage, "test_conversation")
