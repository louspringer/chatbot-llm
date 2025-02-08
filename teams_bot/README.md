# Teams Bot Ontology Documentation

## Overview

This ontology defines the structure, behavior, and validation rules for a Microsoft Teams Bot implementation. The ontology is split into multiple files for better organization and maintainability.

## Core Files

### 1. meta.ttl

Core concepts and base classes:

- `meta:BotComponent`: Base class for all bot components
- `meta:Handler`: Components that handle specific events
- `meta:Activity`: Represents bot interactions
- `meta:Context`: Operational context for bot activities

### 2. problem.ttl

Error handling and problem scenarios:

- Error class hierarchy (`BotError` → `RequestError` → `ValidationError`)
- HTTP status code mappings
- Error message definitions
- Common error instances (ContentType, InvalidJson)

### 3. solution.ttl

Bot implementation components:

- `solution:TeamsBot`: Main bot class
- `solution:BotAdapter`: Activity processing
- `solution:ErrorHandler`: Error management
- Method definitions (onTurn, onError)

### 4. conversation.ttl

Message handling and conversation flow:

- Message types (Message, Response)
- Trace activities for debugging
- Conversation properties
- Message content validation

### 5. guidance.ttl

Best practices and validation rules:

- SHACL validation shapes
- Request/message validation
- Logging practices
- Error handling guidelines

## Validation Rules

### Request Validation

```turtle
guidance:RequestValidation a sh:NodeShape ;
    sh:targetClass meta:Activity ;
    sh:property [
        sh:path conversation:hasType ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .
```

### Message Validation

```turtle
guidance:MessageValidation a sh:NodeShape ;
    sh:targetClass conversation:Message ;
    sh:property [
        sh:path conversation:hasText ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .
```

## Best Practices

### Error Handling

1. Use trace activities for detailed error tracking
2. Implement structured error responses
3. Map HTTP status codes appropriately

### Logging

1. Use structured logging with custom dimensions
2. Include conversation context in logs
3. Avoid logging sensitive information

## Future Enhancements

- Authentication header validation
- Response format standardization
- Rate limiting implementation
- Security practice documentation

## Usage Example

```turtle
3# Define a bot instance
:myBot a solution:TeamsBot ;
    solution:hasAdapter :myAdapter .

# Configure error handling
:myAdapter solution:hasErrorHandler :myErrorHandler .

# Define message handling
:myMessage a conversation:Message ;
    conversation:hasText "Hello bot!" ;
    conversation:hasType "message" .
```

## Validation

To validate your bot implementation against this ontology:

1. Use a SHACL validator to check conformance
2. Ensure all required properties are present
3. Verify error handling patterns
4. Check logging implementation
