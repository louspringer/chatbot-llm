#!/usr/bin/env python3
"""
Validation utilities for ontology files.
"""

import sys
from pathlib import Path
from rdflib import Graph
from pyshacl import validate


def validate_ontology(ontology_path: str) -> bool:
    """
    Validate an ontology file using SHACL shapes.
    Returns True if validation passes, False otherwise.
    """
    try:
        g = Graph()
        g.parse(ontology_path, format="turtle")

        # Get the shapes graph from the same directory
        shapes_path = Path(ontology_path).parent / "shapes.ttl"
        if not shapes_path.exists():
            print(f"No shapes file found at {shapes_path}")
            return False

        shapes_graph = Graph()
        shapes_graph.parse(shapes_path, format="turtle")

        # Validate using PyShacl
        conforms, _, _ = validate(g, shacl_graph=shapes_graph)
        return conforms

    except Exception as e:
        print(f"Error validating {ontology_path}: {str(e)}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: validate.py <ontology_file>")
        sys.exit(1)

    ontology_path = sys.argv[1]
    if validate_ontology(ontology_path):
        print(f"✓ {ontology_path} is valid")
        sys.exit(0)
    else:
        print(f"✗ {ontology_path} failed validation")
        sys.exit(1)


if __name__ == "__main__":
    main()