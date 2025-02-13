#!/usr/bin/env python3
"""SPARQL query tool for Cursor."""

from typing import Any, Dict, List

from .jena_tools import JenaTools


def run_sparql_query(ttl_file: str, query: str) -> List[Dict[str, Any]]:
    """Run a SPARQL query against a Turtle file.

    Args:
        ttl_file: Path to the Turtle file to query
        query: SPARQL query to execute

    Returns:
        List of dictionaries containing query results
    """
    jena = JenaTools()

    # Validate the TTL file first
    valid, msg = jena.validate_ttl(ttl_file)
    if not valid:
        raise ValueError(f"Invalid TTL file: {msg}")

    # Run the query
    try:
        results = jena.run_sparql(ttl_file, query)
        return results
    except Exception as e:
        raise RuntimeError(f"Error executing SPARQL query: {str(e)}")


def register_tool() -> Dict[str, Any]:
    """Register the SPARQL query tool with Cursor."""
    return {
        "name": "run_sparql_query",
        "description": "Execute SPARQL queries against ontology files",
        "function": run_sparql_query,
        "parameters": {
            "ttl_file": {
                "type": "string",
                "description": "Path to the Turtle file to query",
            },
            "query": {
                "type": "string",
                "description": "SPARQL query to execute",
            },
        },
        "returns": {
            "type": "array",
            "items": {"type": "object"},
            "description": "Query results as a list of dictionaries",
        },
    }


if __name__ == "__main__":
    register_tool()
