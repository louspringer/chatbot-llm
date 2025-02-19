#!/usr/bin/env python3
"""
Tool to query and display checkpoint information from session.ttl

# Ontology: session.ttl
# Implements: SessionCheckpoint
# Requirement: REQ-CHECKPOINT-001
# Guidance: guidance.ttl#CheckpointManagement
# Description: Tools for managing and querying session checkpoints
"""

import logging
import re
from pathlib import Path

import rdflib
from rdflib import Namespace, URIRef
from rdflib.namespace import RDF, RDFS


def clean_uri(uri):
    """Clean a URI for display by removing paths and UUIDs."""
    # Convert to string if not already
    uri = str(uri)

    # Handle UUID-like strings
    uuid_pattern = r"^[a-f0-9]{32}b\d+$"
    n_uuid_pattern = r"^n[a-f0-9]{32}b\d+$"
    uuid_dash_pattern = (
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{12}$"
    )

    # Check for UUID matches
    uuid_matches = [
        uuid_pattern,
        n_uuid_pattern,
        uuid_dash_pattern,
    ]
    if any(re.match(pattern, uri) for pattern in uuid_matches):
        return "<internal-reference>"

    # Warn about absolute paths - they should never be used
    if uri.startswith("file:///"):
        logging.warning(
            "Found absolute path URI - these should be relative to project root"
        )

    # Handle paths - always use relative paths
    if "#" in uri:
        uri = uri.split("#")[-1]
    elif uri.startswith("./"):
        uri = uri.split("/")[-1]

    # Remove nonce identifiers (nc[32-hex]b[digits])
    if re.match(r".*nc[a-f0-9]{32}b\d+.*", uri):
        # If it's a nonce-only URI, return empty string
        if re.match(r"^nc[a-f0-9]{32}b\d+$", uri):
            return ""
        # Otherwise remove the nonce part
        uri = re.sub(r"nc[a-f0-9]{32}b\d+", "", uri)

    return uri.strip()


def get_list_items(g, subject, predicate):
    """Get items from an RDF list."""
    items = []
    current = g.value(subject, predicate)

    while current:
        # Try to get the item's label first
        item = g.value(current, RDF.first)
        if item:
            label = g.value(item, RDFS.label)
            if label:
                items.append(str(label))
            else:
                # If no label, try to get a readable string representation
                items.append(str(item))

        # Move to next item in the list
        current = g.value(current, RDF.rest)
        if current == RDF.nil:
            break

    return items


def clean_node_id(text):
    """Remove node IDs from text strings."""
    # Pattern to match node IDs (n followed by hex digits)
    node_pattern = r"n[0-9a-f]{32}b\d+"
    return re.sub(node_pattern, "", text).strip()


def get_readable_value(g, node):
    """Get a human-readable value from an RDF node."""
    if not node:
        return ""

    # If it's a literal, just return its string value
    if isinstance(node, rdflib.Literal):
        return str(node)

    # Try to get the label first
    label = g.value(node, RDFS.label)
    if label:
        return clean_node_id(str(label))

    # Try to get the comment if no label
    comment = g.value(node, RDFS.comment)
    if comment:
        return clean_node_id(str(comment))

    # Try to get a direct value if it's a sequence
    for i in range(1, 10):  # Check first 10 sequence items
        seq_value = g.value(node, RDF["_" + str(i)])
        if seq_value:
            if isinstance(seq_value, rdflib.Literal):
                return str(seq_value)
            # Recursively get readable value for sequence items
            return get_readable_value(g, seq_value)

    # If it's a URI, try to get the last part after #
    if isinstance(node, rdflib.URIRef):
        uri_str = str(node)
        if "#" in uri_str:
            return uri_str.split("#")[-1]

    # If all else fails, return a cleaned string representation
    return clean_node_id(str(node))


def collect_requirements(g, task, predicate):
    """Collect requirements from a task node using the specified predicate."""
    requirements = []
    for _, _, req_node in g.triples((task, predicate, None)):
        # Get the requirement text directly from the requirement node
        req_predicate = URIRef(
            str(predicate).replace("promptRequirements", "requirement")
        )
        req_text = g.value(req_node, req_predicate)
        if req_text:
            requirements.append(str(req_text))
    return requirements


def format_component_value(value, predicate=None):
    """Format a component value based on its predicate."""
    if not value:
        return ""

    # Handle prefix declarations
    if value.startswith("@prefix"):
        return "\n".join("    " + line for line in value.split("\n"))

    # Format based on predicate type
    if predicate:
        if "requiredFiles" in predicate:
            return f"File: {value}"
        elif "branch" in predicate:
            return f"Branch: {value}"
        elif "issue" in predicate and "Title" not in predicate:
            return f"Issue #{value}"
        elif "issueTitle" in predicate:
            return f"Title: {value}"

    return str(value)


def get_checkpoint_components(g, namespace):
    """Get components and their details from a checkpoint."""
    components = {}

    # Get current checkpoint
    checkpoint = None
    for uri in [
        URIRef(str(namespace) + "currentCheckpoint"),
        URIRef("./session#currentCheckpoint"),
        URIRef("#currentCheckpoint"),
    ]:
        if any(g.triples((uri, None, None))):
            checkpoint = uri
            break

    if not checkpoint:
        return {}

    # Get all components linked to the checkpoint
    for _, _, component in g.triples((checkpoint, namespace.hasComponent, None)):
        # Get component label
        label = g.value(component, RDFS.label)
        if not label:
            continue

        label = str(label)
        components[label] = []

        # Get component priority
        priority = g.value(component, namespace.componentPriority)
        priority = int(priority) if priority else 999

        # Collect all predicates and values for this component
        for _, pred, obj in g.triples((component, None, None)):
            if pred in [RDF.type, RDFS.label, namespace.componentPriority]:
                continue

            value = format_component_value(str(obj), str(pred))
            if value:
                components[label].append((priority, value))

        # Sort details by priority
        components[label].sort(key=lambda x: x[0])

    return components


def validate_prompt_state(g, checkpoint, namespace):
    """Validate the prompt state of a checkpoint."""
    warnings = []
    is_valid = True

    # Check if checkpoint has a prompt state
    prompt_states = list(g.objects(checkpoint, namespace.hasPromptState))
    if not prompt_states:
        warnings.append("Checkpoint missing prompt state")
        return False, warnings

    prompt_state = prompt_states[0]

    # Check last updated timestamp
    last_updated = g.value(prompt_state, namespace.lastUpdated)
    if last_updated:
        from datetime import datetime, timedelta, timezone

        try:
            timestamp = datetime.fromisoformat(str(last_updated))
            if timestamp < datetime.now(timezone.utc) - timedelta(days=7):
                warnings.append("Prompt state is stale (>7 days old)")
        except ValueError:
            warnings.append("Invalid timestamp format")

    # Check linked task
    task = g.value(prompt_state, namespace.linkedTask)
    if not task:
        warnings.append("No task linked to prompt state")
    else:
        # Check if task requires prompt update
        requires_update = g.value(task, namespace.requiresPromptUpdate)
        if requires_update and str(requires_update).lower() == "true":
            warnings.append("Task requires prompt update")

    return is_valid, warnings


def get_checkpoint_prompt(g, namespace):
    """Generate a checkpoint prompt from the graph."""
    # Get current checkpoint
    checkpoint = None
    for uri in [
        URIRef(str(namespace) + "currentCheckpoint"),
        URIRef("./session#currentCheckpoint"),
        URIRef("#currentCheckpoint"),
    ]:
        if any(g.triples((uri, None, None))):
            checkpoint = uri
            break

    if not checkpoint:
        return None

    # Get resumption prompt
    prompt = g.value(checkpoint, namespace.resumptionPrompt)
    if not prompt:
        return None

    return str(prompt)


def main():
    """Main function to get and display the checkpoint prompt."""
    g = rdflib.Graph()
    g.parse("session.ttl", format="turtle")

    base_path = str(Path.cwd().absolute())
    SESSION = Namespace("file://" + base_path + "/session#")

    # Debug output
    print("\n=== Graph Structure ===\n")
    for s, p, o in g:
        print(f"Subject: {s}")
        print(f"Predicate: {p}")
        print(f"Object: {o}")
        print("---")

    # First try to find the checkpoint
    checkpoint = None
    checkpoint_uris = [
        URIRef(str(SESSION) + "currentCheckpoint"),
        URIRef("./session#currentCheckpoint"),
        URIRef("#currentCheckpoint"),
        URIRef("file://" + base_path + "/session#currentCheckpoint"),
    ]

    for uri in checkpoint_uris:
        if any(g.triples((uri, None, None))):
            checkpoint = uri
            break

    if checkpoint:
        prompt = get_checkpoint_prompt(g, SESSION)
        if prompt:
            print("\n=== Current Checkpoint Prompt ===\n")
            print(prompt)
        else:
            print("No checkpoint found")


if __name__ == "__main__":
    main()
