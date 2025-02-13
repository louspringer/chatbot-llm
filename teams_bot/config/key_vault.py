"""
# Ontology: cortexteams:KeyVaultConfig
# Implements: cortexteams:SecureCredentialManagement
# Requirement: REQ-SEC-002 Azure Key Vault integration
# Guidance: guidance:SecurityPatterns#SecretManagement
# Description: Azure Key Vault configuration and credential management
"""

import asyncio
import logging
import os
from typing import Dict, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class KeyVaultConfig:
    """Azure Key Vault configuration and management."""

    def __init__(self, vault_url: Optional[str] = None):
        """Initialize Key Vault configuration.

        Args:
            vault_url: Azure Key Vault URL. If not provided, uses
                AZURE_KEY_VAULT_URL env var.
        """
        self.vault_url = vault_url or os.getenv("AZURE_KEY_VAULT_URL")
        if not self.vault_url:
            raise ValueError(
                "Key Vault URL must be provided or set in AZURE_KEY_VAULT_URL"
            )

        # Try managed identity first, fall back to default credential
        try:
            self.credential = ManagedIdentityCredential()
            self.client = SecretClient(
                vault_url=self.vault_url, credential=self.credential
            )
            # Skip test connection in __init__ as it's synchronous
            # Connection will be tested on first secret retrieval
        except Exception as e:
            logger.info(
                "Managed identity not available: "
                f"{e}. Falling back to default credential."
            )
            self.credential = DefaultAzureCredential()
            self.client = SecretClient(
                vault_url=self.vault_url, credential=self.credential
            )

    async def get_secret(self, secret_name: str) -> str:
        """Get a secret from Key Vault.

        Args:
            secret_name: Name of the secret to retrieve

        Returns:
            The secret value

        Raises:
            ValueError: If secret not found
        """
        try:
            # Use asyncio.to_thread to run the synchronous get_secret in thread
            secret = await asyncio.to_thread(self.client.get_secret, secret_name)
            if secret and secret.value:
                return secret.value
            raise ValueError(f"Secret {secret_name} has no value")
        except ResourceNotFoundError:
            raise ValueError(f"Secret {secret_name} not found in Key Vault")
        except Exception as e:
            logger.error(f"Error retrieving secret {secret_name}: {e}")
            raise

    async def set_secret(self, secret_name: str, value: str) -> None:
        """Set a secret in Key Vault.

        Args:
            secret_name: Name of the secret
            value: Secret value to store
        """
        try:
            self.client.set_secret(secret_name, value)
        except Exception as e:
            logger.error(f"Error setting secret {secret_name}: {e}")
            raise

    async def delete_secret(self, secret_name: str) -> None:
        """Delete a secret from Key Vault.

        Args:
            secret_name: Name of the secret to delete
        """
        try:
            self.client.begin_delete_secret(secret_name)
        except Exception as e:
            logger.error(f"Error deleting secret {secret_name}: {e}")
            raise

    @staticmethod
    def get_required_secrets() -> Dict[str, str]:
        """Get list of required secrets and their descriptions."""
        return {
            "BOT_APP_ID": "Microsoft Teams Bot Application ID",
            "BOT_APP_PASSWORD": "Microsoft Teams Bot Application Password",
            "SNOWFLAKE_USER": "Snowflake username",
            "SNOWFLAKE_PASSWORD": "Snowflake password",
            "STATE_ENCRYPTION_KEY": "Key for encrypting bot state",
            "COSMOS_DB_KEY": "Cosmos DB access key",
        }

    async def validate_required_secrets(self) -> Dict[str, bool]:
        """Validate that all required secrets are present in Key Vault.

        Returns:
            Dictionary mapping secret names to their presence status
        """
        status = {}
        for secret_name in self.get_required_secrets().keys():
            try:
                await self.get_secret(secret_name)
                status[secret_name] = True
            except ValueError:
                status[secret_name] = False
            except Exception as e:
                logger.error(f"Error validating secret {secret_name}: {e}")
                status[secret_name] = False
        return status
