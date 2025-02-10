"""
Azure Functions app for Teams Bot.
"""
import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path

# Add project root to path for local imports
project_root = str(Path(__file__).parent.parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Third party imports
import azure.functions as func  # noqa: E402
from botbuilder.core import (  # noqa: E402
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    MemoryStorage,
    ConversationState,
    UserState,
)
from teams_bot.bot.teams_bot import TeamsBot  # noqa: E402
from teams_bot.bot.state_manager import StateManager  # noqa: E402

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Create adapter with settings
SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MicrosoftAppId", ""),
    app_password=os.environ.get("MicrosoftAppPassword", ""),
)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# Create storage and state
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Create state manager
STATE_MANAGER = StateManager(MEMORY, "default")

# Create bot instance with proper configuration
BOT = TeamsBot(
    config={
        "app_id": os.environ.get("MicrosoftAppId", ""),
        "app_password": os.environ.get("MicrosoftAppPassword", ""),
    },
    state_manager=STATE_MANAGER,
)


async def on_error(context, error):
    """Error handler."""
    logger.error("Bot encountered error: %s", str(error))
    logger.error(traceback.format_exc())

    # Send trace activity
    await context.send_trace_activity(
        f"Bot encountered error: {error}",
        f"Error details: {traceback.format_exc()}",
        "https://www.botframework.com/schemas/error",
        "TurnError",
    )

    # Send error message to user
    await context.send_activity(
        "The bot encountered an error. Please try again."
    )


ADAPTER.on_turn_error = on_error


async def process_request(req: func.HttpRequest) -> func.HttpResponse:
    """Main function app entry point."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return func.HttpResponse("Invalid content type", status_code=415)

    body = req.get_body()

    # Process activity
    async def callback(context):
        await BOT.on_turn(context)

    try:
        auth_header = req.headers.get("Authorization", "")
        await ADAPTER.process_activity(body, auth_header, callback)
        return func.HttpResponse(status_code=200)
    except Exception as e:
        logger.error("Error processing activity: %s", str(e))
        logger.error(traceback.format_exc())
        return func.HttpResponse(str(e), status_code=500)


async def teams_webhook_async(req: func.HttpRequest) -> func.HttpResponse:
    """Process incoming webhook requests from Teams."""
    return await process_request(req)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Functions entry point."""
    return asyncio.run(teams_webhook_async(req))
