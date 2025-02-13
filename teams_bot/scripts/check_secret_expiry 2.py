#!/usr/bin/env python3
"""
Check expiry of secrets and send notifications if they are approaching rotation time.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Add project root to path
project_root = str(Path(__file__).parent.parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.key_vault import KeyVaultConfig
from config.settings import get_secret

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SecretExpiryChecker:
    """Check expiry of secrets and send notifications."""

    def __init__(self, config_path: str):
        """Initialize the checker with configuration."""
        self.config = self._load_config(config_path)
        self.key_vault = KeyVaultConfig()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load rotation configuration from YAML."""
        with open(config_path) as f:
            return yaml.safe_load(f)

    async def check_snowflake_key_age(self) -> Tuple[bool, int]:
        """Check age of Snowflake key."""
        try:
            key_path = Path("config/keys/snowflake_bot_key.pem")
            if not key_path.exists():
                logger.error("Snowflake key not found")
                return False, 0

            # Get key age in days
            key_age = (
                datetime.now() - datetime.fromtimestamp(key_path.stat().st_mtime)
            ).days

            # Check against threshold
            max_age = self.config["schedule"]["snowflake_keys"]["interval_days"]
            return key_age >= max_age, key_age

        except Exception as e:
            logger.error(f"Failed to check Snowflake key age: {e}")
            return False, 0

    async def check_keyvault_secret_age(self, secret_name: str) -> Tuple[bool, int]:
        """Check age of a Key Vault secret."""
        try:
            # Get secret metadata
            secret = await self.key_vault.client.get_secret(secret_name)

            # Calculate age in days
            created_on = secret.properties.created_on
            if not created_on:
                logger.error(f"No creation date for secret: {secret_name}")
                return False, 0

            age = (datetime.now(created_on.tzinfo) - created_on).days

            # Check against threshold
            max_age = self.config["schedule"]["keyvault_secrets"]["interval_days"]
            return age >= max_age, age

        except Exception as e:
            logger.error(f"Failed to check secret age: {e}")
            return False, 0

    async def send_notification(self, component: str, age: int, max_age: int) -> None:
        """Send notification about expiring secrets."""
        try:
            webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
            if not webhook_url:
                logger.warning("No Teams webhook URL configured")
                return

            # Calculate days until expiry
            days_left = max_age - age

            # Format message for Teams
            card = {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "type": "AdaptiveCard",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "text": "Secret Rotation Required",
                                    "weight": "bolder",
                                    "size": "medium",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"{component} is {age} days old "
                                    f"(expires in {days_left} days)",
                                    "wrap": True,
                                },
                                {
                                    "type": "TextBlock",
                                    "text": "Please schedule rotation soon.",
                                    "wrap": True,
                                },
                            ],
                            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                            "version": "1.2",
                        },
                    }
                ],
            }

            # Send to Teams webhook
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=card) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to send notification: {resp.status}")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def check_all(self) -> None:
        """Check all secrets for expiry."""
        # Check Snowflake key
        expired, age = await self.check_snowflake_key_age()
        if expired:
            await self.send_notification(
                "Snowflake key",
                age,
                self.config["schedule"]["snowflake_keys"]["interval_days"],
            )

        # Check Key Vault secrets
        secrets_to_check = ["bot-app-password", "state-encryption-key"]

        for secret_name in secrets_to_check:
            expired, age = await self.check_keyvault_secret_age(secret_name)
            if expired:
                await self.send_notification(
                    f"Key Vault secret: {secret_name}",
                    age,
                    self.config["schedule"]["keyvault_secrets"]["interval_days"],
                )


async def main():
    """Main entry point."""
    # Load config and create checker
    config_path = Path(__file__).parent.parent / "config/rotation_config.yaml"
    checker = SecretExpiryChecker(str(config_path))

    # Run checks
    await checker.check_all()


if __name__ == "__main__":
    asyncio.run(main())
