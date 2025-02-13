#!/bin/bash
set -e

# Required environment variables with default values from our Azure environment
export AZURE_SUBSCRIPTION_ID="dae16755-7832-4e6d-bae2-c49ff833042f"
export AZURE_TENANT_ID="919dd520-6ef0-476a-90ce-edb9b6eb39a3"
export AZURE_RESOURCE_GROUP="teams-bot-rg"
export AZURE_KEY_VAULT_NAME="teams-bot-kv"
export AZURE_LOCATION="westus"
export AZURE_SERVICE_PRINCIPAL_ID="fa175945-53e2-4d35-9069-69ac97c75859"

# Function to display usage
usage() {
    echo "Usage: $0 [--dry-run] [--list]"
    echo "  --dry-run  Show what would be deployed without making changes"
    echo "  --list     List existing resources in the resource group"
    exit 1
}

# Parse command line arguments
DRY_RUN=0
LIST_RESOURCES=0
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --list)
            LIST_RESOURCES=1
            shift
            ;;
        *)
            usage
            ;;
    esac
done

# If listing resources, show what exists and exit
if [ $LIST_RESOURCES -eq 1 ]; then
    echo "Listing resources in resource group $AZURE_RESOURCE_GROUP..."
    az resource list --resource-group "$AZURE_RESOURCE_GROUP" --output table
    echo -e "\nListing Key Vaults specifically..."
    az keyvault list --resource-group "$AZURE_RESOURCE_GROUP" --output table
    exit 0
fi

# Validate required environment variables
REQUIRED_VARS=(
    "AZURE_SUBSCRIPTION_ID"
    "AZURE_TENANT_ID"
    "AZURE_RESOURCE_GROUP"
    "AZURE_KEY_VAULT_NAME"
    "AZURE_LOCATION"
    "AZURE_SERVICE_PRINCIPAL_ID"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required environment variable $var is not set"
        exit 1
    fi
done

# Ensure we're logged in and using the right subscription
echo "Verifying Azure CLI login status..."
az account show > /dev/null 2>&1 || {
    echo "Error: Not logged into Azure CLI. Please run 'az login' first."
    exit 1
}

echo "Setting subscription to $AZURE_SUBSCRIPTION_ID..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# Compile Bicep to ARM template
BICEP_FILE="teams_bot/deployment/azure/key_vault.bicep"
ARM_FILE="teams_bot/deployment/azure/key_vault.json"

echo "Compiling Bicep template to ARM template..."
bicep build "$BICEP_FILE"

if [ ! -f "$ARM_FILE" ]; then
    echo "Error: ARM template not found at $ARM_FILE"
    exit 1
fi

DEPLOY_CMD=(az deployment group create
    --resource-group "$AZURE_RESOURCE_GROUP"
    --template-file "$ARM_FILE"
    --parameters
    keyVaultName="$AZURE_KEY_VAULT_NAME"
    location="$AZURE_LOCATION"
    servicePrincipalObjectId="$AZURE_SERVICE_PRINCIPAL_ID"
    tenantId="$AZURE_TENANT_ID")

if [ $DRY_RUN -eq 1 ]; then
    echo "Dry run - would execute:"
    echo "${DEPLOY_CMD[*]} --what-if"
    "${DEPLOY_CMD[@]}" --what-if
else
    echo "Deploying Key Vault..."
    "${DEPLOY_CMD[@]}"

    # Get the Key Vault URI
    KV_URI=$(az keyvault show --name "$AZURE_KEY_VAULT_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query "properties.vaultUri" -o tsv)

    echo "Key Vault deployed successfully!"
    echo "Key Vault URI: $KV_URI"
fi
