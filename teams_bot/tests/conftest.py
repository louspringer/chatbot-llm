"""
Configure pytest for async testing.
"""
import pytest


# Enable async test functions
pytest_plugins = ["pytest_asyncio"]


# Configure asyncio to use auto mode
@pytest.fixture(autouse=True)
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 