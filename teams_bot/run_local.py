#!/usr/bin/env python3
"""
Run the Teams bot locally for development and testing.
"""

import sys
from pathlib import Path
from aiohttp import web

# Add the project root to Python path before importing the app
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Now we can import the app
from teams_bot.app import APP  # noqa: E402

if __name__ == "__main__":
    try:
        # Ensure logs directory exists
        log_dir = project_root / "teams_bot" / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Run the app
        web.run_app(APP, host="localhost", port=3978)
    except Exception as error:
        print(f"Error running bot: {error}", file=sys.stderr)
        sys.exit(1) 