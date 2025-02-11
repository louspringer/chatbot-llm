#!/usr/bin/env python3
"""
Secret rotation script for Teams Bot components.
Handles rotation of:
- Snowflake keys
- Azure Key Vault secrets
- Bot credentials
- State encryption keys
"""

import os
import sys
import yaml
import logging
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

import azure.functions
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError

# Add project root to path
project_root = str(Path(__file__).parent.parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.key_vault import KeyVaultConfig
from config.settings import get_secret

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecretRotator:
    """Handles secret rotation for Teams Bot components."""

    def __init__(self, config_path: str):
        """Initialize the rotator with configuration."""
        self.config = self._load_config(config_path)
        self.key_vault = KeyVaultConfig()
        self.lock_file = Path("/tmp/secret_rotation.lock")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load rotation configuration from YAML."""
        with open(config_path) as f:
            return yaml.safe_load(f)

    async def acquire_lock(self) -> bool:
        """Acquire rotation lock to prevent concurrent runs."""
        try:
            if self.lock_file.exists():
                # Check if lock is stale (older than 1 hour)
                if (datetime.now() - datetime.fromtimestamp(
                    self.lock_file.stat().st_mtime
                )) < timedelta(hours=1):
                    logger.warning("Another rotation process is running")
                    return False
            
            # Create or update lock file
            self.lock_file.touch()
            return True
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False

    def release_lock(self) -> None:
        """Release rotation lock."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")

    async def rotate_snowflake_keys(self) -> bool:
        """Rotate Snowflake authentication keys."""
        try:
            # Generate new key pair
            key_path = Path("config/keys/snowflake_bot_key.pem")
            new_key_path = key_path.with_suffix(".new.pem")
            
            # Generate new RSA key pair
            os.system(
                f"openssl genrsa -out {new_key_path} "
                f"{self.config['compliance']['key_requirements']['rsa_key_size']}"
            )
            
            # Extract public key
            public_key = os.popen(
                f"openssl rsa -in {new_key_path} -pubout"
            ).read()
            
            # Update Snowflake using stored procedure
            # This is handled by a separate script that uses snowsql
            rotate_cmd = (
                f"snowsql -c bot -f deployment/snowflake/rotate_key.sql "
                f"-v public_key='{public_key}'"
            )
            if os.system(rotate_cmd) != 0:
                raise Exception("Failed to update Snowflake key")
            
            # Backup old key
            backup_dir = Path("config/keys/backup")
            backup_dir.mkdir(parents=True, exist_ok=True)
            if key_path.exists():
                backup_path = backup_dir / f"snowflake_bot_key.{datetime.now():%Y%m%d}.pem"
                key_path.rename(backup_path)
            
            # Move new key into place
            new_key_path.rename(key_path)
            
            logger.info("Successfully rotated Snowflake keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate Snowflake keys: {e}")
            return False

    async def rotate_keyvault_secret(
        self, 
        secret_name: str, 
        new_value: Optional[str] = None
    ) -> bool:
        """Rotate a Key Vault secret."""
        try:
            if new_value is None:
                # Generate a secure random value
                new_value = os.urandom(32).hex()
            
            # Update secret in Key Vault
            await self.key_vault.set_secret(secret_name, new_value)
            
            logger.info(f"Successfully rotated secret: {secret_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate secret {secret_name}: {e}")
            return False

    async def rotate_bot_credentials(self) -> bool:
        """Rotate Teams Bot credentials."""
        try:
            # Generate new credentials using Azure CLI
            result = os.popen(
                "az bot regenerate-key "
                f"--name {os.getenv('BOT_NAME')} "
                f"--resource-group {os.getenv('RESOURCE_GROUP')}"
            ).read()
            
            if "error" in result.lower():
                raise Exception(f"Failed to regenerate bot key: {result}")
            
            # Update Key Vault with new credentials
            await self.rotate_keyvault_secret(
                "bot-app-password",
                result.strip()
            )
            
            logger.info("Successfully rotated bot credentials")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate bot credentials: {e}")
            return False

    async def rotate_state_encryption(self) -> bool:
        """Rotate state encryption key."""
        try:
            # Generate new encryption key
            new_key = os.urandom(32).hex()
            
            # Update Key Vault
            await self.rotate_keyvault_secret(
                "state-encryption-key",
                new_key
            )
            
            logger.info("Successfully rotated state encryption key")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate state encryption key: {e}")
            return False

    async def send_notification(
        self, 
        level: str, 
        message: str
    ) -> None:
        """Send notification about rotation status."""
        try:
            webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
            if not webhook_url:
                logger.warning("No Teams webhook URL configured")
                return
            
            # Format message for Teams
            card = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "body": [{
                            "type": "TextBlock",
                            "text": f"Secret Rotation {level}",
                            "weight": "bolder",
                            "size": "medium"
                        }, {
                            "type": "TextBlock",
                            "text": message,
                            "wrap": True
                        }],
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "version": "1.2"
                    }
                }]
            }
            
            # Send to Teams webhook
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=card) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"Failed to send notification: {resp.status}"
                        )
                    
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def run(self, component: Optional[str] = None) -> None:
        """Run the rotation process."""
        if not await self.acquire_lock():
            return
        
        try:
            if component:
                # Rotate specific component
                if component == "snowflake":
                    await self.rotate_snowflake_keys()
                elif component == "bot":
                    await self.rotate_bot_credentials()
                elif component == "state":
                    await self.rotate_state_encryption()
                else:
                    logger.error(f"Unknown component: {component}")
            else:
                # Rotate all components
                components = {
                    "Snowflake keys": self.rotate_snowflake_keys,
                    "Bot credentials": self.rotate_bot_credentials,
                    "State encryption": self.rotate_state_encryption
                }
                
                for name, rotate_func in components.items():
                    logger.info(f"Rotating {name}...")
                    if await rotate_func():
                        await self.send_notification(
                            "SUCCESS",
                            f"Successfully rotated {name}"
                        )
                    else:
                        await self.send_notification(
                            "ERROR",
                            f"Failed to rotate {name}"
                        )
        
        finally:
            self.release_lock()

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Rotate secrets for Teams Bot components"
    )
    parser.add_argument(
        "-c", "--component",
        help="Specific component to rotate (snowflake, bot, state)"
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Show what would be rotated without making changes"
    )
    args = parser.parse_args()
    
    # Load config and create rotator
    config_path = Path(__file__).parent.parent / "config/rotation_config.yaml"
    rotator = SecretRotator(str(config_path))
    
    # Run rotation
    await rotator.run(args.component)

if __name__ == "__main__":
    asyncio.run(main()) 