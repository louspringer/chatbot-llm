#!/usr/bin/env python3
"""
Test script for dry running session context management operations.
"""

import sys
from pathlib import Path

# Add tools directory to path
sys.path.append(str(Path(__file__).parent))

from session_context_manager import SessionContextManager


def main():
    print("Starting dry run tests...")
    manager = SessionContextManager(dry_run=True)

    print("\n=== Test 1: Check Current Context ===")
    manager.detect_context_mismatch()

    print("\n=== Test 2: Get Current Context ===")
    manager.get_current_context()

    print("\n=== Test 3: Try Creating New Context ===")
    manager.create_context(
        task_id="test_task",
        ontologies=["ChatbotLLM"],
        description="Dry run test",
    )

    print("\n=== Test 4: Token Usage Summary ===")
    manager.get_token_usage()


if __name__ == "__main__":
    main()
