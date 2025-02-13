#!/usr/bin/env python3
"""Initialize Cursor tools."""

import os
import sys

from tools.register_tools import register_all

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Register all tools
tools = register_all()

# Make tools available to Cursor
for tool in tools:
    globals()[tool["name"]] = tool["function"]
