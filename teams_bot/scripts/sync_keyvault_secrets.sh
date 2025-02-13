#!/usr/bin/env bash

# Script to sync secrets from environment to Azure Key Vault
# Usage: sync_keyvault_secrets.sh [-d|--dry-run]

# Set required environment variables from our deployment
export AZURE_SUBSCRIPTION_ID="dae16755-7832-4e6d-bae2-c49ff833042f"
export AZURE_TENANT_ID="919dd520-6ef0-476a-90ce-edb9b6eb39a3"
export AZURE_KEY_VAULT_NAME="teams-bot-kv"
export AZURE_KEY_VAULT_URL="https://teams-bot-kv.vault.azure.net/"

# Exit on error
set -e

# Parse command line arguments
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: sync_keyvault_secrets.sh [-d|--dry-run]"
            echo
            echo "Options:"
            echo "  -d, --dry-run    Preview changes without applying them"
            echo "  -h, --help       Show this help message"
            echo
            echo "Note: Environment variables should be injected by 1Password"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required environment variables
required_vars=(
    "AZURE_SUBSCRIPTION_ID"
    "AZURE_TENANT_ID"
    "AZURE_KEY_VAULT_NAME"
    "AZURE_KEY_VAULT_URL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "Error: The following required environment variables are not set:"
    printf '%s\n' "${missing_vars[@]}"
    echo "Please ensure these are injected by 1Password"
    exit 1
fi

# Verify Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Error: Azure CLI is not installed"
    exit 1
fi

# Verify Azure login status
if ! az account show &> /dev/null; then
    echo "Error: Not logged into Azure. Please run 'az login' first"
    exit 1
fi

# Verify subscription access
if ! az account show --subscription "$AZURE_SUBSCRIPTION_ID" &> /dev/null; then
    echo "Error: Cannot access subscription $AZURE_SUBSCRIPTION_ID"
    exit 1
fi

# Verify Key Vault access
if ! az keyvault show --name "$AZURE_KEY_VAULT_NAME" &> /dev/null; then
    echo "Error: Cannot access Key Vault $AZURE_KEY_VAULT_NAME"
    echo "Please verify the Key Vault exists and you have proper access"
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    echo "🔍 DRY RUN: Would sync secrets to Key Vault"
else
    echo "Loading secrets into Key Vault..."
fi

# Define the secrets to load
# This array maps environment variable names to their Key Vault secret names
declare -A secrets=(
    ["TEAMS_BOT_ID"]="bot-app-id"
    ["TEAMS_BOT_PASSWORD"]="bot-app-password"
    ["SNOWFLAKE_USER"]="snowflake-user"
    ["SNOWFLAKE_PASSWORD"]="snowflake-password"
    ["STATE_ENCRYPTION_KEY"]="state-encryption-key"
    ["COSMOS_DB_KEY"]="cosmos-db-key"
)

# Load each secret into Key Vault
for env_var in "${!secrets[@]}"; do
    secret_name="${secrets[$env_var]}"
    secret_value="${!env_var}"

    if [ -z "$secret_value" ]; then
        echo "⚠️  Warning: $env_var is not set in environment, skipping..."
        continue
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "🔍 Would sync $env_var to secret '$secret_name'"
    else
        echo "Syncing $secret_name..."
        if az keyvault secret set --vault-name "$AZURE_KEY_VAULT_NAME" --name "$secret_name" --value "$secret_value" &> /dev/null; then
            echo "✅ Successfully synced $secret_name"
        else
            echo "❌ Failed to sync $secret_name"
        fi
    fi
done

if [ "$DRY_RUN" = true ]; then
    echo "🔍 DRY RUN: Completed preview of secret sync"
else
    echo "✅ Secret sync complete"
fi

echo "Key Vault URL: $AZURE_KEY_VAULT_URL"
echo "Key Vault Name: $AZURE_KEY_VAULT_NAME"
