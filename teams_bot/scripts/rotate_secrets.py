#!/usr/bin/env python3
"""
Secret rotation script for Teams Bot components.
Handles rotation of:
- Snowflake keys
- Azure Key Vault secrets
- Bot credentials
- State encryption keys
"""

import logging
import asyncio
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, and stderr."""
    process = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    return process.returncode, process.stdout, process.stderr


async def rotate_snowflake_keys() -> bool:
    """Rotate Snowflake authentication keys."""
    try:
        # Setup paths
        script_dir = Path(__file__).parent
        key_dir = script_dir.parent / "config" / "keys"
        key_dir.mkdir(parents=True, exist_ok=True)
        key_path = key_dir / "snowflake_bot_key.pem"
        new_key_path = key_dir / "snowflake_bot_key.new.pem"
        
        # Generate new RSA key pair
        logger.info("Generating new RSA key pair...")
        returncode, stdout, stderr = run_command(
            f"openssl genrsa -out {new_key_path} 2048"
        )
        if returncode != 0:
            raise Exception(f"Failed to generate key: {stderr}")
        
        # Extract public key
        logger.info("Extracting public key...")
        returncode, stdout, stderr = run_command(
            f"openssl rsa -in {new_key_path} -pubout"
        )
        if returncode != 0:
            raise Exception(f"Failed to extract public key: {stderr}")
        public_key = stdout
        
        # Call the ROTATE_BOT_KEY stored procedure
        logger.info("Updating Snowflake with new key...")
        rotate_cmd = (
            'snowsql -c bot -q "USE ROLE SECURITYADMIN; '
            'CALL TEAMS_BOT_DB.PUBLIC.'
            f"ROTATE_BOT_KEY('{public_key}')\""
        )
        returncode, stdout, stderr = run_command(rotate_cmd)
        if returncode != 0:
            raise Exception(f"Failed to update Snowflake key: {stderr}")
        
        # Backup old key if it exists
        if key_path.exists():
            backup_dir = key_dir / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d")
            backup_path = backup_dir / f"snowflake_bot_key.{timestamp}.pem"
            logger.info(f"Backing up old key to {backup_path}")
            key_path.rename(backup_path)
        
        # Move new key into place
        logger.info(f"Installing new key at {key_path}")
        new_key_path.rename(key_path)
        
        logger.info("Successfully rotated Snowflake keys")
        return True
            
    except Exception as e:
        logger.error(f"Failed to rotate Snowflake keys: {e}")
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

    if args.component in ['snowflake', 'all']:
        await rotate_snowflake_keys()


if __name__ == '__main__':
    asyncio.run(main()) 