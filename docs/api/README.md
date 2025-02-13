# API Documentation

## Overview
This directory contains the API documentation for the Cortex Teams Chatbot system.

## API Sections

### Teams Bot API
- Bot Framework endpoints
- Message handling
- Adaptive card interactions
- Authentication flows

### ML Service API
- Query processing
- Intent classification
- Entity extraction
- Response generation

### Data Access API
- Query execution
- Data validation
- Cache management
- Access control

## Documentation Structure
Each API section includes:
1. Endpoint specifications
2. Request/response formats
3. Authentication requirements
4. Example usage
5. Error handling

## Generation
API documentation is automatically generated from OpenAPI specifications using:
```bash
# Generate API documentation
python tools/generate_api_docs.py
```

## Testing
API endpoints can be tested using the provided Postman collection:
```bash
newman run tests/postman/cortex-teams-api.json
```

## Contributing
See [Contributing Guide](../../CONTRIBUTING.md) for guidelines on:
- Adding new endpoints
- Updating documentation
- Running tests
- Submitting changes
