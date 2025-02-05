#!/bin/bash

# Exit on error
set -e

echo "Starting deployment of Teams Bot..."

# Check if Azure Functions Core Tools is installed
if command -v func &> /dev/null; then
    echo "Using Azure Functions Core Tools for deployment..."
    
    # Build and publish using func tools
    func azure functionapp publish echo-bot-app-ls --python
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
    
    # Login to Azure if needed
    az account show &> /dev/null || az login
    
    # Deploy using Azure CLI
    echo "Deploying using Azure CLI..."
    az functionapp deployment source config-zip \
        -g teams-bot-rg \
        -n echo-bot-app-ls \
        --src ./deployment.zip
fi

echo "Deployment completed!" 