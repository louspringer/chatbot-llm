#!/bin/bash

# Exit on error
set -e

echo "Starting deployment of Teams Bot..."

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Check if Azure Functions Core Tools is installed
if command -v func &> /dev/null; then
    echo "Using Azure Functions Core Tools for deployment..."
    
    # Build and publish using func tools
    # Using --no-build flag to skip Docker build
    func azure functionapp publish echo-bot-func-test-lou --python --no-build
else
    echo "Azure Functions Core Tools not found, using Azure CLI..."
    
    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        echo "Error: Neither Azure Functions Core Tools nor Azure CLI is installed."
        echo "Please install either:"
        echo "  - Azure Functions Core Tools: npm install -g azure-functions-core-tools@4"
        echo "  - Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
    
    # Create deployment package
    echo "Creating deployment package..."
    # Create a temporary directory for the package
    TEMP_DIR=$(mktemp -d)
    cp -r * "$TEMP_DIR/"
    cd "$TEMP_DIR"
    
    # Install dependencies to the package directory
    python -m pip install --target=".python_packages/lib/site-packages" -r requirements.txt
    
    # Create deployment zip including dependencies
    zip -r deployment.zip . \
        --exclude "*.git*" "*.venv*" "*.pytest_cache*" "__pycache__*" "*.vscode*"
    
    # Move zip back to original directory
    mv deployment.zip ../deployment.zip
    cd ..
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    
    # Login to Azure if needed
    az account show &> /dev/null || az login
    
    # Deploy using Azure CLI
    echo "Deploying using Azure CLI..."
    az functionapp deployment source config-zip \
        -g teams-bot-rg \
        -n echo-bot-func-test-lou \
        --src ./deployment.zip
fi

echo "Deployment completed!" 