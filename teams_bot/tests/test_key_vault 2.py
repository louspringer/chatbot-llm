"""
# Ontology: cortexteams:Testing
# Implements: cortexteams:KeyVaultTests
# Requirement: REQ-TEST-004 Key Vault integration tests
# Guidance: guidance:TestingPatterns#SecurityTesting
# Description: Tests for Azure Key Vault configuration and integration
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import ResourceNotFoundError

from teams_bot.config.key_vault import KeyVaultConfig
from teams_bot.config.settings import get_secret


@pytest.fixture
def mock_secret_client():
    """Create a mock SecretClient."""
    with patch("teams_bot.config.key_vault.SecretClient") as mock_client:
        client_instance = mock_client.return_value
        # Create a mock secret response
        mock_secret = MagicMock()
        mock_secret.value = "test-secret-value"
        # Configure the get_secret method to return our mock secret
        client_instance.get_secret.return_value = mock_secret
        yield client_instance


@pytest.fixture
def mock_managed_identity():
    """Create a mock ManagedIdentityCredential."""
    with patch("teams_bot.config.key_vault.ManagedIdentityCredential") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def mock_default_credential():
    """Create a mock DefaultAzureCredential."""
    with patch("teams_bot.config.key_vault.DefaultAzureCredential") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def azure_env():
    """Set up Azure environment variables."""
    os.environ["AZURE_TENANT_ID"] = "test-tenant-id"
    os.environ["AZURE_CLIENT_ID"] = "test-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "test-client-secret"
    yield
    del os.environ["AZURE_TENANT_ID"]
    del os.environ["AZURE_CLIENT_ID"]
    del os.environ["AZURE_CLIENT_SECRET"]


@pytest.fixture
def key_vault_url():
    """Set up test Key Vault URL."""
    url = "https://test-vault.vault.azure.net/"
    os.environ["AZURE_KEY_VAULT_URL"] = url
    yield url
    del os.environ["AZURE_KEY_VAULT_URL"]


@pytest.mark.asyncio
async def test_get_secret_from_key_vault(
    key_vault_url,
    mock_managed_identity,
    mock_secret_client,
    azure_env,
):
    """Test retrieving a secret from Key Vault."""
    # Set up test environment
    os.environ["TEST_SECRET"] = "fallback-value"

    # Create a mock Key Vault instance with async get_secret
    key_vault = KeyVaultConfig()
    async_mock = AsyncMock()
    async_mock.return_value = "test-secret-value"
    key_vault.get_secret = async_mock

    # Patch the key_vault module variable
    with patch("teams_bot.config.settings.key_vault", key_vault):
        # Test getting secret
        secret = await get_secret("test-secret")
        assert secret == "test-secret-value"

        # Verify Key Vault was called with the correct name
        key_vault.get_secret.assert_awaited_once_with("test-secret")


@pytest.mark.asyncio
async def test_get_secret_fallback_to_env(
    key_vault_url,
    mock_managed_identity,
    mock_secret_client,
    azure_env,
):
    """Test fallback to environment variable when Key Vault fails."""
    # Set up test environment
    os.environ["TEST_SECRET"] = "fallback-value"

    # Initialize Key Vault and patch it into settings
    with patch("teams_bot.config.settings.key_vault") as mock_settings_kv:
        key_vault = KeyVaultConfig()
        # Create an async mock that raises an error
        async_mock = AsyncMock(side_effect=ResourceNotFoundError())
        key_vault.get_secret = async_mock
        mock_settings_kv.return_value = key_vault

        # Test getting secret
        secret = await get_secret("TEST_SECRET")
        assert secret == "fallback-value"


@pytest.mark.asyncio
async def test_get_secret_with_default(
    key_vault_url,
    mock_managed_identity,
    mock_secret_client,
    azure_env,
):
    """Test getting secret with default value."""
    # Set up test environment

    # Initialize Key Vault and patch it into settings
    with patch("teams_bot.config.settings.key_vault") as mock_settings_kv:
        key_vault = KeyVaultConfig()
        # Create an async mock that raises an error
        async_mock = AsyncMock(side_effect=ResourceNotFoundError())
        key_vault.get_secret = async_mock
        mock_settings_kv.return_value = key_vault

        # Test getting secret with default
        secret = await get_secret("NONEXISTENT_SECRET", default="default-value")
        assert secret == "default-value"


@pytest.mark.asyncio
async def test_key_vault_initialization_error():
    """Test handling of Key Vault initialization error."""
    # Remove Key Vault URL from environment
    if "AZURE_KEY_VAULT_URL" in os.environ:
        del os.environ["AZURE_KEY_VAULT_URL"]

    with pytest.raises(ValueError, match="Key Vault URL must be provided"):
        KeyVaultConfig()


@pytest.mark.asyncio
async def test_managed_identity_fallback(
    key_vault_url,
    mock_managed_identity,
    mock_default_credential,
    mock_secret_client,
    azure_env,
):
    """Test fallback to default credential when managed identity fails."""
    # Make managed identity fail
    mock_managed_identity.side_effect = Exception("Managed identity not available")

    # Initialize Key Vault
    key_vault = KeyVaultConfig()

    # Verify fallback occurred
    mock_managed_identity.assert_called_once()
    mock_default_credential.assert_called_once()
    assert key_vault.client == mock_secret_client


if __name__ == "__main__":
    pytest.main([__file__])
