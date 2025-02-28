#!/usr/bin/env python3
"""Register tools with Cursor.

Traceability:
    - Ontology: tools.ttl
    - Class: tools:ToolRegistry
    - Requirement: REQ-TOOL-001 Tool Registration
    - Guidance: guidance:ToolRegistration
    - Description: Manages tool integrations for the development environment
"""

from .guidance_links import main as guidance_links_main
from .sparql_query import register_tool as register_sparql_query


def register_guidance_links():
    """Register guidance links tool."""
    return {
        "name": "guidance_links",
        "description": "Create symlinks for guidance module files",
        "run": lambda: guidance_links_main(),
        "category": "ontology",
    }


def register_all():
    """Register all available tools with Cursor."""
    # Register SPARQL query tool
    sparql_tool = register_sparql_query()

    # Register guidance links tool
    guidance_links_tool = register_guidance_links()

    # Return all registered tools
    return [sparql_tool, guidance_links_tool]


if __name__ == "__main__":
    register_all()
