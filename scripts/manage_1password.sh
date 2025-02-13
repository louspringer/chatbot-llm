#!/usr/bin/env bash

# Exit on error
set -e

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

# Check if op CLI is installed
if ! command -v op &> /dev/null; then
    echo "Error: 1Password CLI (op) is not installed"
    exit 1
fi

# Check if logged in to 1Password
if ! op account get &> /dev/null; then
    echo "Please log in to 1Password CLI first"
    exit 1
fi

# Vault name
VAULT_NAME="cortex-analyst"

# Create vault if it doesn't exist
if ! op vault get "$VAULT_NAME" &> /dev/null; then
    echo "Creating vault: $VAULT_NAME"
    op vault create "$VAULT_NAME"
fi

# Function to create or update an item
create_or_update_item() {
    local title="$1"
    local category="$2"
    shift 2
    local fields=("$@")

    if op item get "$title" --vault "$VAULT_NAME" &> /dev/null; then
        echo "Updating item: $title"
        op item edit "$title" --vault "$VAULT_NAME" "${fields[@]}"
    else
        echo "Creating item: $title"
        op item create --vault "$VAULT_NAME" --category="$category" --title="$title" "${fields[@]}"
    fi
}

# Create/Update Snowflake account configuration
create_or_update_item "snowflake-account" "Server" \
    "account[text]=${SNOWFLAKE_ACCOUNT:-}" \
    "url[text]=https://${SNOWFLAKE_ACCOUNT:-}.snowflakecomputing.com"

# Create/Update Snowflake user credentials
create_or_update_item "snowflake-user" "Login" \
    "username[text]=${SNOWFLAKE_USER:-}" \
    "password[password]=${SNOWFLAKE_PASSWORD:-}"

# Create/Update database configuration
create_or_update_item "database-config" "Database" \
    "database-name[text]=${SNOWFLAKE_DATABASE:-}" \
    "schema-name[text]=${SNOWFLAKE_SCHEMA:-}"

# Create/Update warehouse configuration
create_or_update_item "warehouse-config" "Server" \
    "warehouse-name[text]=${SNOWFLAKE_WAREHOUSE:-}" \
    "warehouse-size[text]=${SNOWFLAKE_WAREHOUSE_SIZE:-}" \
    "auto-suspend[text]=${SNOWFLAKE_WAREHOUSE_AUTO_SUSPEND:-}"

# Create/Update security configuration
create_or_update_item "security-config" "Server" \
    "role-name[text]=${SNOWFLAKE_ROLE:-}" \
    "allowed-ips[text]=${SNOWFLAKE_ALLOWED_IPS:-}"

# Create/Update monitoring configuration
create_or_update_item "monitoring-config" "Server" \
    "credit-quota[text]=${SNOWFLAKE_CREDIT_QUOTA:-}" \
    "alert-threshold[text]=${SNOWFLAKE_ALERT_THRESHOLD:-}"

# Create/Update data configuration
create_or_update_item "data-config" "Database" \
    "stage-name[text]=${SNOWFLAKE_STAGE_NAME:-}"

echo "1Password items have been created/updated successfully"
