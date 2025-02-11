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
import logging
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.key_vault import KeyVaultConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Add project root to path
project_root = str(Path(__file__).parent.parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class SecretRotator:
    """Handles secret rotation for Teams Bot components."""

    def __init__(self):
        """Initialize the rotator."""
        self.key_vault = KeyVaultConfig()
        self.lock_file = Path("/tmp/secret_rotation.lock")

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
            key_dir = Path(project_root) / "config" / "keys"
            key_dir.mkdir(parents=True, exist_ok=True)
            key_path = key_dir / "snowflake_bot_key.pem"
            new_key_path = key_dir / "snowflake_bot_key.new.pem"
            
            # Generate new RSA key pair
            os.system(f"openssl genrsa -out {new_key_path} 2048")
            
            # Extract public key
            public_key = os.popen(
                f"openssl rsa -in {new_key_path} -pubout"
            ).read()
            
            # Call the ROTATE_BOT_KEY stored procedure
            rotate_cmd = (
                'snowsql -c bot -q "CALL TEAMS_BOT_DB.PUBLIC.'
                f"ROTATE_BOT_KEY('{public_key}')\""
            )
            if os.system(rotate_cmd) != 0:
                raise Exception("Failed to update Snowflake key")
            
            # Backup old key
            backup_dir = key_dir / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            if key_path.exists():
                backup_path = backup_dir / (
                    f"snowflake_bot_key.{datetime.now():%Y%m%d}.pem"
                )
                key_path.rename(backup_path)
            
            # Move new key into place
            new_key_path.rename(key_path)
            
            # Update Key Vault with new private key
            with open(key_path, 'r') as f:
                private_key = f.read()
            await self.key_vault.set_secret(
                'snowflake-private-key', private_key
            )
            
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


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Rotate secrets for Teams Bot')
    parser.add_argument(
        '--component', 
        choices=['snowflake', 'bot', 'all'],
        help='Component to rotate secrets for'
    )
    args = parser.parse_args()

    rotator = SecretRotator()
    if not await rotator.acquire_lock():
        sys.exit(1)

    try:
        if args.component in ['snowflake', 'all']:
            await rotator.rotate_snowflake_keys()
        if args.component in ['bot', 'all']:
            await rotator.rotate_bot_credentials()
    finally:
        rotator.release_lock()


if __name__ == '__main__':
    asyncio.run(main()) 