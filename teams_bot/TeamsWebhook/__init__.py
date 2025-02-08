import azure.functions as func
import logging
import asyncio
import os
import traceback
from bot.teams_bot import TeamsBot
from botbuilder.core import (
    BotFrameworkAdapter,
    MemoryStorage,
    ConversationState,
    UserState
)
from opencensus.ext.azure.log_exporter import AzureLogHandler

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

if "APPINSIGHTS_INSTRUMENTATIONKEY" in os.environ:
    logger.addHandler(AzureLogHandler(
        connection_string=(
            f"InstrumentationKey="
            f"{os.environ['APPINSIGHTS_INSTRUMENTATIONKEY']}"
        )
    ))

# Create adapter
ADAPTER = BotFrameworkAdapter(
    credentials={
        "app_id": os.environ.get("MicrosoftAppId", ""),
        "app_password": os.environ.get("MicrosoftAppPassword", "")
    }
)

# Create storage and state
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Create bot instance
BOT = TeamsBot(CONVERSATION_STATE, USER_STATE)


async def on_error(context, error):
    """Error handler."""
    logger.error(f"Bot encountered error: {error}")
    logger.error(traceback.format_exc())

    # Send trace activity
    await context.send_trace_activity(
        f"Bot encountered error: {error}",
        f"Error details: {traceback.format_exc()}",
        "https://www.botframework.com/schemas/error",
        "TurnError"
    )

    # Send error message to user
    await context.send_activity(
        "The bot encountered an error. Please try again."
    )


ADAPTER.on_turn_error = on_error


async def process_request(req: func.HttpRequest) -> func.HttpResponse:
    """Main function app entry point."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return func.HttpResponse(
            "Invalid content type",
            status_code=415
        )

    body = await req.get_body()

    # Process activity
    async def callback(context):
        await BOT.on_turn(context)

    try:
        await ADAPTER.process_activity(body, req.headers, callback)
        return func.HttpResponse(status_code=200)
    except Exception as e:
        logger.error(f"Error processing activity: {e}")
        logger.error(traceback.format_exc())
        return func.HttpResponse(
            str(e),
            status_code=500
        )


async def teams_webhook_async(req: func.HttpRequest) -> func.HttpResponse:
    """Process incoming webhook requests from Teams."""
    return await process_request(req)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Functions entry point."""
    return asyncio.run(teams_webhook_async(req))