"""
Local bot server for development and testing.
"""

from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    UserState
)
from botbuilder.schema import Activity
import traceback
from datetime import datetime
import logging
from typing import Optional
from .config.settings import APP_ID, APP_PASSWORD
from .bot.teams_bot import TeamsBot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create adapter
SETTINGS = BotFrameworkAdapterSettings(
    app_id=APP_ID or "",  # Empty string for local testing
    app_password=APP_PASSWORD or ""  # Empty string for local testing
)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# Create storage
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Create bot
BOT = TeamsBot(CONVERSATION_STATE, USER_STATE)

# Error handler
async def on_error(context, error):
    """Handle errors in the adapter."""
    logger.error(f"Error: {error}")
    logger.error(f"Trace: {traceback.format_exc()}")
    
    # Send error message to user
    error_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    error_msg = f"Sorry, something went wrong at {error_time}."
    await context.send_activity(error_msg)
    
    # Ensure state is saved after error
    await CONVERSATION_STATE.save_changes(context)
    await USER_STATE.save_changes(context)

ADAPTER.on_turn_error = on_error

# Message handler
async def messages(req: web.Request) -> web.Response:
    """Handle incoming messages."""
    if "application/json" not in req.headers["Content-Type"]:
        return web.Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = (
        req.headers["Authorization"] if "Authorization" in req.headers else ""
    )

    try:
        response = await ADAPTER.process_activity(
            activity, auth_header, BOT.on_turn
        )
        if response:
            return web.json_response(
                data=response.body,
                status=response.status
            )
        return web.Response(status=201)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return web.Response(status=500)

# Create and configure app
APP = web.Application()
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(APP, host="localhost", port=3978)
    except Exception as error:
        logger.error(f"Error running app: {error}")
        raise 