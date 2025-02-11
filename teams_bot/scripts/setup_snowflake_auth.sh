#!/bin/bash
set -e

# Create keys directory if it doesn't exist
KEYS_DIR="teams_bot/config/keys"
mkdir -p "$KEYS_DIR"

# Generate RSA key pair
echo "Generating RSA key pair..."
openssl genrsa -out "$KEYS_DIR/snowflake_bot_key.pem" 2048
openssl rsa -in "$KEYS_DIR/snowflake_bot_key.pem" -pubout -out "$KEYS_DIR/snowflake_bot_key.pub"

# Format public key for Snowflake
PUBLIC_KEY=$(cat "$KEYS_DIR/snowflake_bot_key.pub" | grep -v "PUBLIC KEY" | tr -d '\n')

# Create temporary SQL file with the public key
TMP_SQL=$(mktemp)
cat teams_bot/deployment/snowflake/create_bot_user.sql | sed "s|{{BOT_PUBLIC_KEY}}|${PUBLIC_KEY}|g" > "$TMP_SQL"

# Execute Snowflake SQL
echo "Creating bot user in Snowflake..."
snowsql -f "$TMP_SQL"
rm "$TMP_SQL"

# Update .env file with key path
if [ -f .env ]; then
    if grep -q "SNOWFLAKE_PRIVATE_KEY_PATH=" .env; then
        sed -i '' "s|SNOWFLAKE_PRIVATE_KEY_PATH=.*|SNOWFLAKE_PRIVATE_KEY_PATH=$KEYS_DIR/snowflake_bot_key.pem|" .env
    else
        echo "SNOWFLAKE_PRIVATE_KEY_PATH=$KEYS_DIR/snowflake_bot_key.pem" >> .env
    fi
else
    echo "SNOWFLAKE_PRIVATE_KEY_PATH=$KEYS_DIR/snowflake_bot_key.pem" > .env
fi

echo "✅ Snowflake bot user setup complete!"
echo "Private key location: $KEYS_DIR/snowflake_bot_key.pem"
echo "Public key location: $KEYS_DIR/snowflake_bot_key.pub"
echo
echo "To connect to Snowflake, use:"
echo "  User: TEAMS_BOT_USER"
echo "  Auth: Private Key"
echo "  Key Path: $KEYS_DIR/snowflake_bot_key.pem" 