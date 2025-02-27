"""Tests for ontology validation.

# Ontology: test:OntologyValidation
# Implements: test:ValidationFramework
# Requirement: REQ-TEST-001 Ontology Validation
# Guidance: guidance:TestingPattern#OntologyValidation
# Description: Test suite for validating ontology file paths and URI patterns.
#   Ensures that ontology files use relative URIs and follow proper naming
#   conventions.
"""

from pathlib import Path

import pytest
from rdflib import Graph, Namespace


def load_query(query_name: str) -> str:
    """Load a SPARQL query from file."""
    query_path = Path(__file__).parent / "queries" / query_name
    with open(query_path) as f:
        return f.read()


def test_no_absolute_uris():
    """Test that no ontology files contain absolute URIs."""
    # Find all .ttl files
    ontology_dir = Path(__file__).parent.parent
    ttl_files = list(ontology_dir.glob("**/*.ttl"))
    assert ttl_files, "No .ttl files found"

    # Load validation query
    query = load_query("validate_uris.rq")

    # Files to exclude from validation
    excluded_files = {
        "session.ttl",  # Generated session state file
        "session_log.ttl",  # Generated session log file
        "test_session.ttl",  # Test session file
        "test_session_log.ttl",  # Test session log file
        "guidance.ttl",  # Guidance file
        "package_management.ttl",  # Package management
        "deployment.ttl",  # Deployment config
        "conversation.ttl",  # Conversation state
        "als.ttl",  # ALS config
        "langgraph.ttl",  # LangGraph config
        "stereo.ttl",  # Stereo config
    }

    # Directories to exclude from validation
    excluded_dirs = {
        "ontology-framework",  # Framework files
        "test",  # Test files
        "examples",  # Example files
        "docs",  # Documentation files
    }

    # Common prefixes to bind
    common_prefixes = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "sh": "http://www.w3.org/ns/shacl#",
        "dct": "http://purl.org/dc/terms/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "foaf": "http://xmlns.com/foaf/0.1/",
    }

    # Check each file
    for ttl_file in ttl_files:
        # Skip files in excluded directories
        excluded = False
        for d in excluded_dirs:
            if d in str(ttl_file):
                excluded = True
                break
        if excluded:
            continue

        # Skip excluded files
        if ttl_file.name in excluded_files:
            continue

        # Skip test files unless they end with _test.ttl
        is_test_file = "test" in str(ttl_file).lower()
        is_test_ttl = ttl_file.name.endswith("_test.ttl")
        if is_test_file and not is_test_ttl:
            continue

        # Load graph with relative base URI
        g = Graph()
        relative_path = ttl_file.relative_to(ontology_dir)
        base_uri = f"./{relative_path}"

        try:
            g.parse(ttl_file, format="turtle", publicID=base_uri)
        except Exception as e:
            pytest.fail(f"Failed to parse {ttl_file}: {str(e)}")

        # Bind common prefixes after parsing
        for prefix, uri in common_prefixes.items():
            g.bind(prefix, Namespace(uri))

        # Run validation and check results
        try:
            # Execute query and collect results
            query_result = g.query(query)

            # Convert results to list of tuples
            # rdflib's SPARQL results have dynamic attributes that can't be
            # type checked
            violations = [  # type: ignore[attr-defined]
                (
                    str(row.subject),  # type: ignore[attr-defined]
                    str(row.predicate),  # type: ignore[attr-defined]
                    str(row.object),  # type: ignore[attr-defined]
                )
                for row in query_result
            ]

            # Report any violations found
            if violations:
                header = f"\nFound absolute/user-specific URIs in {ttl_file}:"
                details = [f"  {s} {p} {o}" for s, p, o in violations]
                pytest.fail("\n".join([header] + details))
        except Exception as e:
            pytest.fail(f"Failed to validate {ttl_file}: {str(e)}")
