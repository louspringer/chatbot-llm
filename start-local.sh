#!/bin/bash

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    echo "Azure Functions Core Tools is not installed"
    echo "Install with: npm install -g azure-functions-core-tools@4"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the function app with environment variables
echo "Starting Teams Bot Function App..."
func start --verbose | tee logs/bot.log 