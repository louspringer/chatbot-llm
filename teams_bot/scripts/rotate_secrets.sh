#!/usr/bin/env bash

# Script to handle automated secret rotation for Teams Bot components
# Usage: rotate_secrets.sh [-d|--dry-run] [-c|--component component_name]

# Set strict error handling
set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# Default values
DRY_RUN=false
COMPONENT=""
ROTATION_LOG_FILE="rotation.log"
NOTIFICATION_WEBHOOK=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -c|--component)
            COMPONENT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: rotate_secrets.sh [-d|--dry-run] [-c|--component component_name]"
            echo
            echo "Options:"
            echo "  -d, --dry-run     Preview changes without applying them"
            echo "  -c, --component   Rotate specific component (snowflake|keyvault|state|bot)"
            echo "  -h, --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Logging setup
setup_logging() {
    local log_dir="logs/rotation"
    mkdir -p "$log_dir"
    ROTATION_LOG_FILE="${log_dir}/$(date +%Y%m%d_%H%M%S)_rotation.log"
    exec 1> >(tee -a "$ROTATION_LOG_FILE")
    exec 2> >(tee -a "$ROTATION_LOG_FILE" >&2)
}

# Notification function
send_notification() {
    local status="$1"
    local message="$2"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        curl -X POST "$NOTIFICATION_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{
                \"timestamp\": \"$timestamp\",
                \"status\": \"$status\",
                \"message\": \"$message\",
                \"component\": \"$COMPONENT\",
                \"log_file\": \"$ROTATION_LOG_FILE\"
            }"
    fi
}

# Rotate Snowflake keys
rotate_snowflake() {
    echo "Rotating Snowflake keys..."

    if [ "$DRY_RUN" = true ]; then
        echo "🔍 Would rotate Snowflake keys"
        return
    fi

    # Generate new key pair
    local key_dir="teams_bot/config/keys"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local new_private_key="${key_dir}/snowflake_bot_key_${timestamp}.pem"
    local new_public_key="${key_dir}/snowflake_bot_key_${timestamp}.pub"

    # Create backup of current keys
    if [ -f "${key_dir}/snowflake_bot_key.pem" ]; then
        cp "${key_dir}/snowflake_bot_key.pem" "${key_dir}/snowflake_bot_key.pem.bak"
        cp "${key_dir}/snowflake_bot_key.pub" "${key_dir}/snowflake_bot_key.pub.bak"
    fi

    # Generate new RSA key pair
    openssl genrsa -out "$new_private_key" 2048
    openssl rsa -in "$new_private_key" -pubout -out "$new_public_key"

    # Format public key for Snowflake
    local public_key_value
    public_key_value=$(cat "$new_public_key" | grep -v "PUBLIC KEY" | tr -d '\n')

    # Update Snowflake using stored procedure
    snowsql -c bot -q "CALL ROTATE_BOT_KEY('${public_key_value}');"

    # Update symlinks to current keys
    ln -sf "$new_private_key" "${key_dir}/snowflake_bot_key.pem"
    ln -sf "$new_public_key" "${key_dir}/snowflake_bot_key.pub"

    echo "✅ Snowflake key rotation complete"
}

# Rotate Azure Key Vault secrets
rotate_keyvault() {
    echo "Rotating Azure Key Vault secrets..."

    if [ "$DRY_RUN" = true ]; then
        echo "🔍 Would rotate Key Vault secrets"
        return
    fi

    # Get list of secrets to rotate
    local secrets=(
        "bot-app-password"
        "state-encryption-key"
        "cosmos-db-key"
    )

    for secret in "${secrets[@]}"; do
        # Generate new secret value
        local new_value
        new_value=$(openssl rand -base64 32)

        # Create new version in Key Vault
        az keyvault secret set \
            --vault-name "$AZURE_KEY_VAULT_NAME" \
            --name "$secret" \
            --value "$new_value"

        echo "✅ Rotated secret: $secret"
    done
}

# Rotate state encryption key
rotate_state() {
    echo "Rotating state encryption key..."

    if [ "$DRY_RUN" = true ]; then
        echo "🔍 Would rotate state encryption key"
        return
    fi

    # Generate new encryption key
    local new_key
    new_key=$(openssl rand -base64 32)

    # Store in Key Vault
    az keyvault secret set \
        --vault-name "$AZURE_KEY_VAULT_NAME" \
        --name "state-encryption-key" \
        --value "$new_key"

    echo "✅ State encryption key rotation complete"
}

# Rotate bot credentials
rotate_bot() {
    echo "Rotating bot credentials..."

    if [ "$DRY_RUN" = true ]; then
        echo "🔍 Would rotate bot credentials"
        return
    fi

    # Generate new password
    local new_password
    new_password=$(openssl rand -base64 32)

    # Update in Azure AD (requires Graph API permissions)
    az ad app credential reset \
        --id "$TEAMS_BOT_ID" \
        --append \
        --credential-description "Rotated $(date +%Y-%m-%d)"

    # Store new password in Key Vault
    az keyvault secret set \
        --vault-name "$AZURE_KEY_VAULT_NAME" \
        --name "bot-app-password" \
        --value "$new_password"

    echo "✅ Bot credentials rotation complete"
}

# Main rotation logic
main() {
    setup_logging
    echo "Starting secret rotation at $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    # Validate Azure login
    if ! az account show &> /dev/null; then
        echo "Error: Not logged into Azure. Please run 'az login' first."
        exit 1
    fi

    # Validate Snowflake connection
    if ! snowsql -c bot -q "SELECT CURRENT_TIMESTAMP();" &> /dev/null; then
        echo "Error: Cannot connect to Snowflake. Please check configuration."
        exit 1
    }

    # Create rotation lock
    if ! snowsql -c bot -q "CALL ACQUIRE_DEPLOYMENT_LOCK('rotation_$(date +%Y%m%d)');" | grep -q "SUCCESS"; then
        echo "Error: Could not acquire rotation lock. Another rotation might be in progress."
        exit 1
    fi

    # Perform rotation based on component
    case "$COMPONENT" in
        "snowflake")
            rotate_snowflake
            ;;
        "keyvault")
            rotate_keyvault
            ;;
        "state")
            rotate_state
            ;;
        "bot")
            rotate_bot
            ;;
        "")
            # Rotate all components
            rotate_snowflake
            rotate_keyvault
            rotate_state
            rotate_bot
            ;;
        *)
            echo "Error: Unknown component $COMPONENT"
            exit 1
            ;;
    esac

    # Release rotation lock
    snowsql -c bot -q "CALL RELEASE_DEPLOYMENT_LOCK('rotation_$(date +%Y%m%d)');"

    echo "Secret rotation completed successfully at $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    send_notification "SUCCESS" "Secret rotation completed successfully"
}

# Run main function
main
