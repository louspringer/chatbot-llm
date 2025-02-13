# Package Management Guide

## Overview

This document outlines the required procedures for adding or updating packages in the project. **FAILURE TO FOLLOW THESE PROCEDURES WILL RESULT IN IMMEDIATE REJECTION OF YOUR PULL REQUEST AND POSSIBLE HORSEWHIPPING.**

## Package Management Process

### 1. Dependency Evaluation
- [ ] Identify the type of dependency:
  - Core dependency (required for basic functionality)
  - Development dependency (required for development/testing)
  - Optional dependency (feature-specific)
- [ ] Document the justification for adding the package
- [ ] Verify no existing package already provides the functionality

### 2. Source Selection
- [ ] Always prefer conda packages over pip when available
- [ ] For pip packages, verify they are compatible with conda environment
- [ ] Document why conda alternative is not suitable (if using pip)

### 3. Version Requirements
- [ ] Specify minimum version with known security fixes
- [ ] Test compatibility with existing dependencies
- [ ] Document any version constraints and reasons

### 4. Update Process

#### For Conda Packages:
```bash
# 1. Add to environment.yml
conda env update -f environment.yml

# 2. Export updated environment
conda env export --no-builds > environment.lock.yml
```

#### For PyProject.toml Updates:
```bash
# 1. Add dependency to pyproject.toml
# 2. Update in development mode
pip install -e .

# 3. Generate requirements.txt
pip freeze > requirements.txt
```

### 5. Validation Steps

Before committing changes:
- [ ] Run all tests: `pytest`
- [ ] Check for security vulnerabilities: `safety check`
- [ ] Verify conda environment recreation: `conda env create -f environment.yml`
- [ ] Test clean pip install: `pip install -e .`
- [ ] Document any new dependencies in README.md

### 6. Documentation Updates

Update the following files:
- [ ] pyproject.toml (for pip dependencies)
- [ ] environment.yml (for conda environment)
- [ ] requirements.txt (for pip freeze)
- [ ] README.md (if adding major dependencies)
- [ ] docs/package_management.md (if changing procedures)

## Package Management Rules

1. **ALWAYS** use conda as the primary package manager
2. **ALWAYS** document dependency changes in commit messages
3. **ALWAYS** update both pyproject.toml and environment.yml
4. **NEVER** add packages without following this process
5. **NEVER** pin versions without documented reason
6. **NEVER** mix pip and conda for the same package

## Ontology Integration

This process is defined in `package_management.ttl`:

```turtle
pkg:PackageManagementProcess a owl:Class ;
    rdfs:label "Package Management Process" ;
    rdfs:comment "Process for adding or updating project dependencies" .
```

## Enforcement

Failure to follow these procedures will result in:
1. Immediate PR rejection
2. Required remediation steps
3. Documentation of violation
4. Mandatory review process for future package changes
5. Possible horsewhipping (severity based on infraction)

## Related Documentation

- [Development Setup Guide](development_setup.md)
- [Contribution Guidelines](../CONTRIBUTING.md)
- [Package Management Ontology](../package_management.ttl) 