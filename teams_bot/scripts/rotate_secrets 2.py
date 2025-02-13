#!/usr/bin/env python3
"""
Secret rotation script for Teams Bot components.
Handles rotation of:
- Snowflake keys
- Azure Key Vault secrets
- Bot credentials
- State encryption keys
"""

import argparse
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, and stderr."""
    process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return process.returncode, process.stdout, process.stderr


def backup_key_files(key_dir: Path, timestamp: str) -> None:
    """Backup all key files with given timestamp."""
    backup_dir = key_dir / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Key file patterns to backup
    patterns = ["*.pem", "*.p8", "*.der", "*.pub"]

    for pattern in patterns:
        for key_file in key_dir.glob(pattern):
            if key_file.is_file() and "new" not in key_file.name:
                suffix = key_file.suffix
                backup_name = f"snowflake_bot_key.{timestamp}{suffix}"
                backup_path = backup_dir / backup_name
                logger.info(f"Backing up {key_file.name} to {backup_path}")
                if key_file.exists():
                    key_file.rename(backup_path)


async def rotate_snowflake_keys() -> bool:
    """Rotate Snowflake authentication keys."""
    try:
        # Setup paths
        script_dir = Path(__file__).parent
        key_dir = script_dir.parent / "config" / "keys"
        key_dir.mkdir(parents=True, exist_ok=True)
        key_path = key_dir / "snowflake_bot_key.p8"
        new_key_path = key_dir / "snowflake_bot_key.new.p8"

        # Generate new RSA key pair in PKCS#8 PEM format
        logger.info("Generating new RSA key pair in PKCS#8 format...")
        cmd = (
            f"openssl genrsa 2048 | "
            f"openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt "
            f"-out {new_key_path}"
        )
        returncode, stdout, stderr = run_command(cmd)
        if returncode != 0:
            raise Exception(f"Failed to generate key: {stderr}")

        # Extract and format public key for Snowflake
        logger.info("Extracting and formatting public key...")
        returncode, stdout, stderr = run_command(
            f"openssl rsa -in {new_key_path} -pubout -outform PEM"
        )
        if returncode != 0:
            raise Exception(f"Failed to extract public key: {stderr}")

        # Format public key - remove headers and newlines
        public_key = "".join(
            line
            for line in stdout.splitlines()
            if not line.startswith("-----") and line.strip()
        )

        # Update Snowflake with new key using ACCOUNTADMIN role
        logger.info("Updating Snowflake with new key...")
        rotate_cmd = (
            'snowsql -c louspringer -q "'
            "USE ROLE ACCOUNTADMIN; "
            f"ALTER USER TEAMS_BOT_USER SET RSA_PUBLIC_KEY = '{public_key}';\""
        )
        returncode, stdout, stderr = run_command(rotate_cmd)
        if returncode != 0:
            raise Exception(f"Failed to update Snowflake key: {stderr}")

        # Backup existing keys
        timestamp = datetime.now().strftime("%Y%m%d")
        backup_key_files(key_dir, timestamp)

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
    parser = argparse.ArgumentParser(description="Rotate secrets for Teams Bot")
    parser.add_argument(
        "--component",
        choices=["snowflake", "bot", "all"],
        help="Component to rotate secrets for",
    )
    args = parser.parse_args()

    if args.component in ["snowflake", "all"]:
        await rotate_snowflake_keys()


if __name__ == "__main__":
    asyncio.run(main())
