#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    source .env
else
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.template to .env and fill in the values"
    exit 1
fi

# Verify required environment variables
required_vars=("SNOWFLAKE_ROLE" "SNOWFLAKE_DATABASE" "SNOWFLAKE_SCHEMA")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "Error: Missing required environment variables: ${missing_vars[*]}"
    exit 1
fi

# Create temporary SQL file for variable setting
TMP_SQL=$(mktemp)
trap "rm -f $TMP_SQL" EXIT

# Set up variables in SQL
cat << EOF > "$TMP_SQL"
-- Set Snowflake variables from environment
SET ROLE_NAME = '${SNOWFLAKE_ROLE}';
SET DATABASE_NAME = '${c}';
SET SCHEMA_NAME = '${SNOWFLAKE_SCHEMA}';

-- Log variable values for debugging
SELECT 
    \$ROLE_NAME as ROLE_NAME,
    \$DATABASE_NAME as DATABASE_NAME,
    \$SCHEMA_NAME as SCHEMA_NAME;

-- Execute main deployment script
!source scripts/deploy_snowflake.sql
EOF

# Execute deployment with snowsql
snowsql -f "$TMP_SQL"

echo -e "${GREEN}Snowflake resources deployed successfully${NC}"

# Main deployment process
main() {
    echo "Starting Cortex Analyst deployment..."
    
    # Check requirements
    check_requirements
    
    # Validate environment
    validate_env
    
    # Deploy Snowflake resources
    deploy_snowflake
    
    echo -e "${GREEN}Deployment completed successfully${NC}"
}

# Run main function
main 