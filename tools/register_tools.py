#!/usr/bin/env python3
"""Register tools with Cursor."""

from .sparql_query import register_tool as register_sparql_query


def register_all():
    """Register all available tools with Cursor."""
    # Register SPARQL query tool
    sparql_tool = register_sparql_query()

    # Return all registered tools
    return [sparql_tool]


if __name__ == "__main__":
    register_all()
