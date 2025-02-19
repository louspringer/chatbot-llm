# Ontology: guidance.ttl

# Implements: guidance:OntologyEnhancement

# Requirement: REQ-ONTO-001

# Guidance: guidance:OntologyEvolution#PatternAddition

# Description: Add missing patterns for PR management and GitHub integration

## Overview

Based on lessons learned from PR creation process, we need to add several patterns to `guidance.ttl` to better guide PR creation, GitHub integration, and validation processes.

## Required Pattern Additions

### 1. PR Management Pattern

```turtle
guidance:PRManagementPattern rdf:type owl:Class ;
    rdfs:label "Pull Request Management Pattern" ;
    rdfs:subClassOf guidance:BestPractice ;
    rdfs:comment "Comprehensive pattern for managing pull requests" .

guidance:PRTemplate rdf:type owl:Class ;
    rdfs:label "PR Template" ;
    rdfs:subClassOf guidance:PRManagementPattern ;
    guidance:hasRequiredSections [
        rdf:_1 "Overview" ;
        rdf:_2 "Changes" ;
        rdf:_3 "Testing" ;
        rdf:_4 "Documentation" ;
        rdf:_5 "Validation" ;
    ] .
```

### 2. GitHub Integration Pattern

```turtle
guidance:GitHubPattern rdf:type owl:Class ;
    rdfs:label "GitHub Integration Pattern" ;
    rdfs:subClassOf guidance:BestPractice ;
    rdfs:comment "Pattern for GitHub-specific artifacts and workflows" .

guidance:GitHubDirectories rdf:type owl:Class ;
    rdfs:label "GitHub Directory Structure" ;
    rdfs:subClassOf guidance:GitHubPattern .
```

### 3. Validation Patterns

```turtle
guidance:PRValidation rdf:type owl:Class ;
    rdfs:label "PR Validation Pattern" ;
    rdfs:subClassOf guidance:ValidationPattern .
```

## Implementation Tasks

1. [ ] Add PR Management Pattern
   - [ ] PR Template structure
   - [ ] Naming conventions
   - [ ] Required sections
   - [ ] Emoji standards

2. [ ] Add GitHub Integration Pattern
   - [ ] Directory structure standards
   - [ ] File naming conventions
   - [ ] Gitignore patterns
   - [ ] Template locations

3. [ ] Add Validation Patterns
   - [ ] PR validation rules
   - [ ] Ontology reference checking
   - [ ] Test coverage reporting
   - [ ] Issue reference validation

4. [ ] Update Documentation
   - [ ] Add examples for each pattern
   - [ ] Update README
   - [ ] Add SPARQL queries for validation

## Validation

- Must pass SHACL validation
- Must maintain backward compatibility
- Must include example instances
- Must include validation rules

## Related

- PR #39 (lessons learned from PR creation process)
