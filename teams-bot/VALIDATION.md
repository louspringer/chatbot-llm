# Teams Bot Validation Guide

## SHACL Validation Rules

### 1. Activity Validation

```turtle
# Validate basic activity structure
guidance:ActivityValidation a sh:NodeShape ;
    sh:targetClass meta:Activity ;
    sh:property [
        sh:path conversation:hasType ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
    ] ;
    sh:property [
        sh:path meta:hasContext ;
        sh:minCount 1 ;
        sh:class meta:Context ;
    ] .
```

### 2. Message Content Validation

```turtle
# Validate message content
guidance:MessageContentValidation a sh:NodeShape ;
    sh:targetClass conversation:Message ;
    sh:property [
        sh:path conversation:hasText ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:maxLength 4000 ;  # Teams message limit
    ] .
```

### 3. Error Response Validation

```turtle
# Validate error responses
guidance:ErrorResponseValidation a sh:NodeShape ;
    sh:targetClass problem:BotError ;
    sh:property [
        sh:path problem:hasErrorMessage ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .
```

## Validation Examples

### 1. Valid Bot Configuration

```turtle
:myBot a solution:TeamsBot ;
    solution:hasAdapter [
        a solution:BotAdapter ;
        solution:hasErrorHandler [
            a solution:ErrorHandler
        ]
    ] .
```

### 2. Valid Message Flow

```turtle
:myMessage a conversation:Message ;
    conversation:hasText "User query" ;
    conversation:hasType "message" ;
    meta:hasContext [
        a meta:Context
    ] .

:myResponse a conversation:Response ;
    conversation:hasText "Bot response" ;
    conversation:inConversation "conversation-id" .
```

### 3. Valid Error Handling

```turtle
:myError a problem:ValidationError ;
    problem:hasErrorCode "400"^^xsd:integer ;
    problem:hasErrorMessage "Invalid request format" .
```

## Validation Checklist

### Component Validation
- [ ] Bot has required adapter configuration
- [ ] Error handler is properly linked
- [ ] Activity processors are defined

### Message Validation
- [ ] Message has required type
- [ ] Text content within limits
- [ ] Conversation context present

### Error Handling
- [ ] Error types properly categorized
- [ ] Status codes mapped correctly
- [ ] Error messages are descriptive

### Logging
- [ ] Trace activities properly formatted
- [ ] Context included in logs
- [ ] Sensitive data masked

## Common Validation Issues

1. Missing Context
```turtle
# Invalid - missing context
:invalidMessage a conversation:Message ;
    conversation:hasText "Text" .  # Missing meta:hasContext

# Valid
:validMessage a conversation:Message ;
    conversation:hasText "Text" ;
    meta:hasContext [ a meta:Context ] .
```

2. Invalid Error Codes
```turtle
# Invalid - wrong datatype
:invalidError a problem:RequestError ;
    problem:hasErrorCode "400" .  # Missing ^^xsd:integer

# Valid
:validError a problem:RequestError ;
    problem:hasErrorCode "400"^^xsd:integer .
```

3. Incomplete Bot Setup
```turtle
# Invalid - missing error handler
:invalidBot a solution:TeamsBot ;
    solution:hasAdapter [ a solution:BotAdapter ] .

# Valid
:validBot a solution:TeamsBot ;
    solution:hasAdapter [
        a solution:BotAdapter ;
        solution:hasErrorHandler [ a solution:ErrorHandler ]
    ] .
```

## Validation Tools

1. Use PyShacl for validation:
```python
from pyshacl import validate
validate(data_graph, shacl_graph, ont_graph=None)
```

2. Use RDFLib for graph manipulation:
```python
from rdflib import Graph, Namespace
g = Graph()
g.parse("teams-bot/guidance.ttl", format="turtle")
```

## Validation Process

1. Load ontology files
2. Create instance data
3. Run SHACL validation
4. Check validation results
5. Fix any violations
6. Revalidate until clean 