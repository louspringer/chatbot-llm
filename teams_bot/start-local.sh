#!/bin/bash

# Exit on error
set -e

echo "Starting Teams Bot locally with environment validation..."

# Check if environment is set up
if ! command -v conda &> /dev/null; then
    echo "Conda not found. Please run setup_local_env.sh first."
    exit 1
fi

# Activate conda environment
conda activate chatbot-llm

# Validate environment
echo "Validating environment..."
python tools/validate_local_env.py

# Check if Bot Framework Emulator is installed
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! [ -d "/Applications/Bot Framework Emulator.app" ]; then
        echo "Bot Framework Emulator not found. Installing..."
        brew install --cask bot-framework-emulator
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! command -v botframework-emulator &> /dev/null; then
        echo "Please install Bot Framework Emulator manually from:"
        echo "https://github.com/Microsoft/BotFramework-Emulator/releases"
        read -p "Press enter to continue after installing the emulator..."
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Azure Storage Emulator if not running
if ! curl -s http://127.0.0.1:10000 &> /dev/null; then
    echo "Starting Azurite..."
    npx azurite --silent --location ./.azurite &
    sleep 2
fi

# Check port availability
if lsof -i:3978 &> /dev/null; then
    echo "Port 3978 is already in use. Stopping existing process..."
    lsof -ti:3978 | xargs kill -9
fi

# Start the bot with 1Password secret injection
echo "Starting Teams Bot..."
echo "Bot will be available at: http://localhost:3978/api/messages"
echo "Use Bot Framework Emulator to connect to this endpoint"

# Launch Bot Framework Emulator if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Launching Bot Framework Emulator..."
    open -a "Bot Framework Emulator"
fi

# Start the bot with environment variables
op run --env-file=".env" -- func start | tee logs/bot.log

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    echo "Azure Functions Core Tools is not installed"
    echo "Install with: npm install -g azure-functions-core-tools@4"
    exit 1
fi

# Start the function app
echo "Starting Teams Bot Function App..."
func start --verbose 