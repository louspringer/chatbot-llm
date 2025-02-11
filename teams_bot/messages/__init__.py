"""
Azure Functions app for Teams Bot.
Handles both Azure Functions deployment and local debugging.
"""

import json
import logging
import os
import sys
from aiohttp import web
import azure.functions as func
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity
from teams_bot.bot.cosmos_storage import CosmosStorage
from teams_bot.bot.state_manager import StateManager
from teams_bot.config.key_vault import KeyVaultConfig

# Add project root to path for local imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Key Vault if URL is provided
key_vault = None
if os.getenv("AZURE_KEY_VAULT_URL"):
    try:
        key_vault = KeyVaultConfig()
        logger.info("Successfully initialized Key Vault")
    except Exception as e:
        logger.error(f"Failed to initialize Key Vault: {e}")

async def get_secret(name: str, default: str = "") -> str:
    """Get secret from Key Vault or environment variable."""
    if key_vault:
        try:
            return await key_vault.get_secret(name)
        except Exception as e:
            logger.warning(f"Failed to get secret from Key Vault: {e}")
    return os.getenv(name, default)

# Initialize with default values
SETTINGS = BotFrameworkAdapterSettings(
    app_id="",
    app_password="",
)
ADAPTER = BotFrameworkAdapter(SETTINGS)
STATE_MANAGER = None

async def initialize_bot():
    """Initialize bot with secrets from Key Vault or environment."""
    global SETTINGS, ADAPTER, STATE_MANAGER

    # Update settings with secrets
    SETTINGS.app_id = await get_secret("BOT_APP_ID", "")
    SETTINGS.app_password = await get_secret("BOT_APP_PASSWORD", "")
    
    # Reinitialize adapter with updated settings
    ADAPTER = BotFrameworkAdapter(SETTINGS)

    # Initialize state manager with CosmosDB storage
    cosmos_uri = await get_secret("COSMOS_DB_ENDPOINT", "")
    cosmos_key = await get_secret("COSMOS_DB_KEY", "")
    database_id = os.getenv("COSMOS_DB_DATABASE", "bot-db")
    container_id = os.getenv("COSMOS_DB_CONTAINER", "bot-state")

    STATE_MANAGER = StateManager(
        storage=CosmosStorage(
            cosmos_uri=cosmos_uri,
            cosmos_key=cosmos_key,
            database_id=database_id,
            container_id=container_id,
        ),
        conversation_id="default"
    )

async def on_error(context: TurnContext, error: Exception):
    """Error handler for the bot."""
    logger.error(f"Bot encountered an error: {error}")
    logger.exception(error)

    # Send a message to the user
    await context.send_activity("Sorry, it looks like something went wrong!")

    # Ensure state is cleared for next turn
    if STATE_MANAGER:
        await STATE_MANAGER.clear_state(context)

ADAPTER.on_turn_error = on_error

async def process_message_activity(turn_context: TurnContext):
    """Process a message activity from Teams."""
    # Get the conversation data
    conversation_data = await STATE_MANAGER.get_conversation_data(turn_context)
    user_profile = await STATE_MANAGER.get_user_profile(turn_context)

    # Echo back the message
    await turn_context.send_activity(
        f"You said: {turn_context.activity.text}"
    )

    # Update state
    if turn_context.activity:
        conversation_data.last_message_id = turn_context.activity.id
        if turn_context.activity.timestamp:
            user_profile.last_interaction = (
                turn_context.activity.timestamp.isoformat()
            )

    await STATE_MANAGER.save_conversation_data(turn_context, conversation_data)
    await STATE_MANAGER.save_user_profile(turn_context, user_profile)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    """Process incoming webhook requests from Teams."""
    try:
        # Get the request body
        body = req.get_body()
        if not body:
            return func.HttpResponse("Request body is empty", status_code=400)

        # Parse the activity
        activity = Activity().deserialize(json.loads(body.decode()))

        # Process the activity
        if activity.type == "message":
            response = await ADAPTER.process_activity(
                activity, "", process_message_activity
            )
            if response:
                return func.HttpResponse(
                    json.dumps(response),
                    status_code=200,
                    mimetype="application/json"
                )

        return func.HttpResponse(status_code=200)

    except Exception as error:
        logger.exception(error)
        return func.HttpResponse(str(error), status_code=500)

# For local debugging
if __name__ == "__main__":
    async def messages(req):
        """Handle local bot messages."""
        try:
            body = await req.json()
            activity = Activity().deserialize(body)

            # For local testing, just echo back
            if activity.type == "message":
                return web.json_response({
                    "type": "message",
                    "text": f"Echo: {activity.text}"
                })
            return web.Response(status=200)

        except Exception as e:
            return web.json_response(
                data={"error": str(e)},
                status=500
            )

    app = web.Application()
    app.router.add_post("/api/messages", messages)

    web.run_app(app, host="localhost", port=3978)
