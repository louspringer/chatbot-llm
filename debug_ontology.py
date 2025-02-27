#!/usr/bin/env python3
# Ontology: tools:OntologyDebugger
# Implements: debug:OntologyInspector
# Requirement: REQ-DBG-001 Ontology Debugging
# Guidance: guidance:ModelFirstPrinciple#debuggingTools
# Description: Debug tool for inspecting ontology relationships and dependencies

from typing import Optional

from rdflib import Graph, Namespace

# Define namespaces
DEPLOY = Namespace("./deployment#")


def load_ontology(file_path: str, base_uri: Optional[str] = None) -> Graph:
    """Load an ontology file with proper namespace binding.

    Args:
        file_path: Path to the ontology file
        base_uri: Optional base URI for relative paths

    Returns:
        Loaded RDF graph
    """
    g = Graph()

    # Use relative paths by default
    if base_uri is None:
        base_uri = "./"

    # Bind common namespaces
    g.bind("", Namespace(f"{base_uri}#"))
    g.bind("chatbot", Namespace(f"{base_uri}chatbot#"))
    g.bind("guidance", Namespace(f"{base_uri}guidance#"))
    g.bind("deploy", DEPLOY)

    g.parse(file_path, format="turtle")
    return g


def get_local_name(uri):
    """Extract local name from URIRef, handling both relative and absolute URIs."""
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[1]
    return uri_str.split("/")[-1]


# Load the ontology
g = load_ontology("deployment_validation.ttl")

print("Dependencies:")
for s, p, o in g.triples((None, DEPLOY.dependsOn, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nConfigurations:")
for s, p, o in g.triples((None, DEPLOY.configures, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nEmulations:")
for s, p, o in g.triples((None, DEPLOY.emulates, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nUsed In:")
for s, p, o in g.triples((None, DEPLOY.usedIn, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nImplemented By:")
for s, p, o in g.triples((None, DEPLOY.implementedBy, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")
