#!/usr/bin/env python3
# Ontology: tools:OntologyValidation
# Implements: validation:OntologyIntegrityCheck
# Requirement: REQ-VAL-001 Ontology Validation
# Guidance: guidance:ModelFirstPrinciple#ontologyValidation
# Description: Validates ontology files for required components and structure

import re
import sys
from pathlib import Path


def check_required_prefixes(content: str) -> set[str]:
    """Check for required prefixes in the ontology file."""
    required_prefixes = {
        "meta",
        "metameta",
        "problem",
        "solution",
        "conversation",
        "guidance",
        "rdf",
        "rdfs",
        "owl",
        "sh",
    }
    found_prefixes = set()
    prefix_pattern = re.compile(r"@prefix\s+(\w+):\s*<.*>")

    for match in prefix_pattern.finditer(content):
        found_prefixes.add(match.group(1))

    return required_prefixes - found_prefixes


def check_required_components(content: str) -> dict[str, list[str]]:
    """Check for required ontology components."""
    issues = {"classes": [], "properties": [], "individuals": [], "validation": []}

    # Check for class definitions with required attributes
    class_pattern = re.compile(r":\w+\s+a\s+owl:Class\s*;")
    label_pattern = re.compile(r'rdfs:label\s+"[^"]+"\s*;')
    comment_pattern = re.compile(r'rdfs:comment\s+"[^"]+"\s*;')
    version_pattern = re.compile(r'owl:versionInfo\s+"[^"]+"\s*;')

    if not class_pattern.search(content):
        issues["classes"].append("No owl:Class definitions found")
    if not label_pattern.search(content):
        issues["classes"].append("Missing rdfs:label for classes")
    if not comment_pattern.search(content):
        issues["classes"].append("Missing rdfs:comment for classes")
    if not version_pattern.search(content):
        issues["classes"].append("Missing owl:versionInfo for classes")

    # Check for property definitions
    property_pattern = re.compile(
        r":\w+\s+a\s+(?:owl:ObjectProperty|owl:DatatypeProperty)\s*;",
    )
    domain_pattern = re.compile(r"rdfs:domain\s+:\w+\s*;")
    range_pattern = re.compile(r"rdfs:range\s+:\w+\s*;")

    if not property_pattern.search(content):
        issues["properties"].append("No property definitions found")
    if not domain_pattern.search(content):
        issues["properties"].append("Missing rdfs:domain for properties")
    if not range_pattern.search(content):
        issues["properties"].append("Missing rdfs:range for properties")

    # Check for individuals
    individual_pattern = re.compile(r":\w+\s+a\s+:\w+\s*;")
    if len(list(individual_pattern.finditer(content))) < 2:
        issues["individuals"].append("Less than two instances per class")

    # Check for SHACL validation
    shacl_pattern = re.compile(r":\w+Shape\s+a\s+sh:NodeShape\s*;")
    if not shacl_pattern.search(content):
        issues["validation"].append("No SHACL shapes defined")

    return issues


def validate_ontology_file(file_path: str) -> bool:
    """Validate a single ontology file."""
    try:
        content = Path(file_path).read_text()

        # Check for required prefixes
        missing_prefixes = check_required_prefixes(content)
        if missing_prefixes:
            print(
                f"Missing required prefixes in {file_path}: "
                f'{", ".join(missing_prefixes)}',
            )
            return False

        # Check for required components
        issues = check_required_components(content)
        has_issues = False

        for component, component_issues in issues.items():
            if component_issues:
                has_issues = True
                print(f"\nIssues with {component} in {file_path}:")
                for issue in component_issues:
                    print(f"  - {issue}")

        return not has_issues

    except Exception as e:
        print(f"Error validating {file_path}: {e!s}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: validate_ontology.py <ontology_file> [ontology_file2 ...]")
        sys.exit(1)

    exit_code = 0
    for file_path in sys.argv[1:]:
        if not file_path.endswith((".ttl", ".turtle")):
            continue

        if not validate_ontology_file(file_path):
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
