#!/usr/bin/env python3
"""Tests for secret rotation functionality."""

import pytest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime

from ..scripts.rotate_secrets import (
    rotate_snowflake_keys,
    backup_key_files,
    run_command,
)


@pytest.fixture
def mock_paths(tmp_path):
    """Setup temporary test paths."""
    key_dir = tmp_path / "config" / "keys"
    key_dir.mkdir(parents=True)
    test_key = key_dir / "snowflake_bot_key.p8"
    test_key.write_text("TEST KEY CONTENT")
    return {
        "key_dir": key_dir,
        "key_path": test_key,
        "new_key_path": key_dir / "snowflake_bot_key.new.p8",
    }


@pytest.fixture
def mock_run_command():
    """Mock for run_command function."""
    with patch("teams_bot.scripts.rotate_secrets.run_command") as mock:
        # Default successful responses
        mock.side_effect = [
            # Generate key response
            (0, "", ""),
            # Extract public key response
            (
                0,
                (
                    "-----BEGIN PUBLIC KEY-----\n"
                    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n"
                    "-----END PUBLIC KEY-----\n"
                ),
                "",
            ),
            # Update Snowflake response
            (0, "Statement executed successfully.", ""),
        ]
        yield mock


@pytest.mark.asyncio
async def test_successful_key_rotation(mock_paths, mock_run_command):
    """Test successful key rotation with ACCOUNTADMIN role."""
    with patch("pathlib.Path.rename") as mock_rename:
        result = await rotate_snowflake_keys()

        assert result is True

        # Verify correct role and command used
        update_call = mock_run_command.mock_calls[2]
        cmd = update_call[1][0]
        assert "USE ROLE ACCOUNTADMIN" in cmd
        assert "ALTER USER TEAMS_BOT_USER SET RSA_PUBLIC_KEY" in cmd

        # Verify key backup and installation
        assert mock_rename.call_count == 2


@pytest.mark.asyncio
async def test_key_rotation_with_wrong_role(mock_paths, mock_run_command):
    """Test key rotation failure when using wrong role."""
    # Mock failure when using wrong role
    error_msg = (
        "SQL access control error: Insufficient privileges to operate "
        "on user 'TEAMS_BOT_USER'"
    )
    mock_run_command.side_effect = [
        (0, "", ""),  # Generate key success
        (0, "-----BEGIN PUBLIC KEY-----\nKEY\n-----END PUBLIC KEY-----\n", ""),
        (1, "", error_msg),
    ]

    result = await rotate_snowflake_keys()
    assert result is False


@pytest.mark.asyncio
async def test_key_rotation_with_invalid_key_format(mock_paths, mock_run_command):
    """Test key rotation with invalid public key format."""
    # Mock invalid key format
    mock_run_command.side_effect = [
        (0, "", ""),  # Generate key success
        (0, "INVALID KEY FORMAT", ""),  # Invalid key format
        (1, "", "SQL compilation error: Invalid public key format"),
    ]

    result = await rotate_snowflake_keys()
    assert result is False


@pytest.mark.asyncio
async def test_key_generation_failure(mock_paths, mock_run_command):
    """Test failure in key generation step."""
    mock_run_command.side_effect = [
        (1, "", "Unable to generate RSA key"),  # Generate key failure
    ]

    result = await rotate_snowflake_keys()
    assert result is False


def test_backup_key_files(mock_paths):
    """Test key backup functionality."""
    key_dir = mock_paths["key_dir"]
    timestamp = datetime.now().strftime("%Y%m%d")

    # Create test files
    test_files = [
        "snowflake_bot_key.p8",
        "snowflake_bot_key.pub",
        "snowflake_bot_key.der",
    ]
    for file in test_files:
        (key_dir / file).write_text("TEST CONTENT")

    backup_key_files(key_dir, timestamp)

    # Verify backups
    backup_dir = key_dir / "backup"
    assert backup_dir.exists()

    backup_path = f"snowflake_bot_key.{timestamp}"
    for file in test_files:
        backup_file = backup_dir / f"{backup_path}{Path(file).suffix}"
        assert backup_file.exists()
        assert backup_file.read_text() == "TEST CONTENT"


def test_run_command():
    """Test run_command function."""
    # Test successful command
    code, out, err = run_command("echo 'test'")
    assert code == 0
    assert "test" in out
    assert not err

    # Test failed command
    code, out, err = run_command("nonexistent-command")
    assert code != 0
    assert err


@pytest.mark.asyncio
async def test_key_rotation_with_stored_procedure(mock_paths, mock_run_command):
    """Test key rotation attempt using stored procedure instead of ALTER."""
    # Mock stored procedure failure
    error_msg = (
        "SQL access control error: Insufficient privileges to execute "
        "procedure 'ROTATE_BOT_KEY'"
    )
    mock_run_command.side_effect = [
        (0, "", ""),  # Generate key success
        (0, "-----BEGIN PUBLIC KEY-----\nKEY\n-----END PUBLIC KEY-----\n", ""),
        (1, "", error_msg),
    ]

    with patch("teams_bot.scripts.rotate_secrets.logger") as mock_logger:
        result = await rotate_snowflake_keys()
        assert result is False
        # Verify error was logged
        mock_logger.error.assert_called()
