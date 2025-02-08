"""
Azure Functions app for Teams Bot.
Handles both Azure Functions deployment and local debugging.
"""

import azure.functions as func
import json
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    ConversationState,
    MemoryStorage,
    UserState
)
from botbuilder.schema import Activity
from bot.teams_bot import TeamsBot
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot settings
SETTINGS = BotFrameworkAdapterSettings("", "")  # App ID and App Password empty for local testing
ADAPTER = BotFrameworkAdapter(SETTINGS)

# Create storage
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Create bot
BOT = TeamsBot(CONVERSATION_STATE, USER_STATE)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Functions entry point."""
    # Convert the request body to Activity
    body = req.get_body().decode()
    activity = Activity().deserialize(json.loads(body))

    # Process activity
    auth_header = req.headers.get("Authorization", "")

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return func.HttpResponse(
            json.dumps(response.body),
            status_code=response.status,
            headers=response.headers
        )
    return func.HttpResponse(status_code=200)

# For local debugging
if __name__ == "__main__":
    import asyncio
    from aiohttp import web

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