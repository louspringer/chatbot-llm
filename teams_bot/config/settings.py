"""
Configuration settings for the Teams bot.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

from .key_vault import KeyVaultConfig

# Initialize logging
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Initialize Key Vault
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


# Bot Configuration
APP_ID = asyncio.run(get_secret("bot-app-id"))
APP_PASSWORD = asyncio.run(get_secret("bot-app-password"))

# Azure Configuration
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
KEYVAULT_NAME = os.getenv("AZURE_KEY_VAULT_NAME")

# Snowflake Configuration
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = asyncio.run(get_secret("snowflake-user"))
SNOWFLAKE_PRIVATE_KEY_PATH = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
SNOWFLAKE_DATABASE = "TEAMS_BOT_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Bot State Storage
STATE_STORAGE_TYPE = os.getenv("STATE_STORAGE_TYPE", "memory")
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = asyncio.run(get_secret("cosmos-db-key"))
COSMOS_DB_DATABASE = os.getenv("COSMOS_DB_DATABASE", "teams_bot_db")
COSMOS_DB_CONTAINER = os.getenv("COSMOS_DB_CONTAINER", "state")

# State encryption
STATE_ENCRYPTION_KEY = asyncio.run(get_secret("state-encryption-key"))


def get_snowflake_private_key() -> Optional[bytes]:
    """Load and format private key for Snowflake authentication."""
    if not SNOWFLAKE_PRIVATE_KEY_PATH:
        logger.error("SNOWFLAKE_PRIVATE_KEY_PATH not set")
        return None

    try:
        key_path = Path(SNOWFLAKE_PRIVATE_KEY_PATH)
        with key_path.open("rb") as key:
            p_key = serialization.load_pem_private_key(
                key.read(), password=None, backend=default_backend()
            )

        pkb = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        return pkb

    except Exception as e:
        logger.error(f"Failed to load Snowflake private key: {e}")
        return None
