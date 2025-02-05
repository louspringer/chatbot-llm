#!/bin/bash

# Exit on error
set -e

echo "Starting Teams Bot locally with 1Password injection..."

# Use 1Password to inject secrets from home directory .env
op run --env-file="$HOME/.env" -- func start 