#!/bin/bash

# Base directory for all queries
QUERY_DIR="src/chatbot_llm/queries"

echo "Testing Security Requirements Query..."
arq --base=file://$(pwd)/ --data chatbot.ttl --data cortexteams.ttl --query $QUERY_DIR/security_reqs.rq

echo -e "\nTesting Business Needs Query..."
arq --base=file://$(pwd)/ --data chatbot.ttl --data cortexteams.ttl --query $QUERY_DIR/business_needs.rq

echo -e "\nTesting Interpretations Query..."
arq --base=file://$(pwd)/ --data chatbot.ttl --data cortexteams.ttl --query $QUERY_DIR/interpretations.rq

echo -e "\nTesting Core Integration Query..."
arq --base=file://$(pwd)/ --data chatbot.ttl --data cortexteams.ttl --query $QUERY_DIR/get_core_integration.rq 