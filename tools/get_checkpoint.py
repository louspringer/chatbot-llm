#!/usr/bin/env python3
"""
Tool to query and display checkpoint information from session.ttl
"""

import rdflib
from rdflib import Namespace, URIRef
from rdflib.namespace import RDF, RDFS
from pathlib import Path
import re
import logging


def clean_uri(uri):
    """Clean a URI for display by removing paths and UUIDs."""
    # Convert to string if not already
    uri = str(uri)

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
    node_pattern = r'n[0-9a-f]{32}b\d+'
    return re.sub(node_pattern, '', text).strip()


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
        seq_value = g.value(node, RDF['_' + str(i)])
        if seq_value:
            if isinstance(seq_value, rdflib.Literal):
                return str(seq_value)
            # Recursively get readable value for sequence items
            return get_readable_value(g, seq_value)
    
    # If it's a URI, try to get the last part after #
    if isinstance(node, rdflib.URIRef):
        uri_str = str(node)
        if '#' in uri_str:
            return uri_str.split('#')[-1]
    
    # If all else fails, return a cleaned string representation
    return clean_node_id(str(node))


def get_checkpoint_prompt(g, base_path):
    """Generate a checkpoint prompt from the graph."""
    SESSION = Namespace("file://" + base_path + "/session#")
    prompt_parts = []
    
    # Get current context
    current_context = g.value(None, RDF.type, SESSION.CurrentContext)
    
    # Get task progress
    if current_context:
        task_progress = []
        for s, p, o in g.triples((current_context, SESSION.taskProgress, None)):
            value = get_readable_value(g, o)
            if value:  # Only add non-empty values
                task_progress.append(value)
        
        if task_progress:
            prompt_parts.append("\nRecent Progress:")
            for item in task_progress:
                prompt_parts.append(f"- {item}")
    
    # Get blocking issues
    blocking_issues = []
    for s, p, o in g.triples((None, SESSION.blockingIssues, None)):
        value = get_readable_value(g, o)
        if value:  # Only add non-empty values
            blocking_issues.append(value)
    
    if blocking_issues:
        prompt_parts.append("\nBlocking Issues:")
        for issue in blocking_issues:
            prompt_parts.append(f"- {issue}")
    
    # Get next steps
    next_steps = []
    for s, p, o in g.triples((None, SESSION.nextSteps, None)):
        value = get_readable_value(g, o)
        if value:  # Only add non-empty values
            next_steps.append(value)
    
    if next_steps:
        prompt_parts.append("\nNext Steps:")
        for step in next_steps:
            prompt_parts.append(f"- {step}")
    
    # Get current task
    current_task = g.value(None, RDF.type, SESSION.Task)
    if current_task:
        task_label = get_readable_value(g, current_task)
        if task_label:  # Only add if we have a valid label
            prompt_parts.append(f"\nHow can I help you with: {task_label}")
    
    return "\n".join(prompt_parts)


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
        prompt = get_checkpoint_prompt(g, base_path)
    if prompt:
            print("\n=== Current Checkpoint Prompt ===\n")
        print(prompt)
    else:
        print("No checkpoint found")


if __name__ == "__main__":
    main()