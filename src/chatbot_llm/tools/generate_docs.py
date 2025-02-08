#!/usr/bin/env python3
"""Generate markdown documentation from ontology queries."""
import subprocess
import json
from pathlib import Path
import re


def clean_uri(uri: str) -> str:
    """Clean URI to show only the local name."""
    if not uri:
        return uri
    # Extract local name after last # or /
    match = re.search(r'[/#]([^/#]+)$', uri)
    return match.group(1) if match else uri


def run_query(query_file: str) -> dict:
    """Run a SPARQL query and return the results."""
    cmd = [
        "arq",
        "--base=file://$(pwd)/",
        "--data", "chatbot.ttl",
        "--query", query_file,
        "--results", "JSON"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        print(f"Warning for {query_file}:", result.stderr)
    return json.loads(result.stdout)


def generate_docs():
    """Generate markdown documentation."""
    md = ["# Chatbot Ontology Documentation\n"]

    # Overview section
    metadata = run_query("src/chatbot_llm/queries/get_metadata.rq")
    md.append("## Overview\n")
    meta = metadata["results"]["bindings"][0]
    md.append(f"**Title**: {meta['title']['value']}\n")
    md.append(f"**Version**: {meta['version']['value']}\n")
    md.append(f"**Description**: {meta['comment']['value']}\n\n")

    # Classes section
    classes = run_query("src/chatbot_llm/queries/get_classes.rq")
    md.append("## Classes\n")
    for cls in classes["results"]["bindings"]:
        name = clean_uri(cls["label"]["value"])
        comment = cls.get("comment", {}).get(
            "value", "No description available"
        )
        md.append(f"### {name}\n")
        md.append(f"{comment}\n\n")

    # Properties section
    props = run_query("src/chatbot_llm/queries/get_properties.rq")
    md.append("## Properties\n")
    for prop in props["results"]["bindings"]:
        name = clean_uri(prop["label"]["value"])
        domain = clean_uri(prop.get("domain", {}).get("value", "Any"))
        range_ = clean_uri(prop.get("range", {}).get("value", "Any"))
        comment = prop.get("comment", {}).get(
            "value", "No description available"
        )

        md.append(f"### {name}\n")
        md.append(f"- **Domain**: {domain}\n")
        md.append(f"- **Range**: {range_}\n")
        md.append(f"- **Description**: {comment}\n\n")

    # Instances section
    instances = run_query("src/chatbot_llm/queries/get_instances.rq")
    md.append("## Instances\n")
    current_type = None
    for inst in instances["results"]["bindings"]:
        type_name = clean_uri(inst["type"]["value"])
        if type_name != current_type:
            md.append(f"\n### {type_name}\n")
            current_type = type_name
        name = clean_uri(inst["label"]["value"])
        comment = inst.get("comment", {}).get("value", "")
        md.append(f"- **{name}**: {comment}\n")

    # SHACL Constraints section
    shapes = run_query("src/chatbot_llm/queries/get_shapes.rq")
    md.append("\n## Validation Rules\n")
    current_shape = None
    for shape in shapes["results"]["bindings"]:
        shape_name = clean_uri(shape["shape"]["value"])
        if shape_name != current_shape:
            md.append(f"\n### {shape_name}\n")
            current_shape = shape_name
        prop = clean_uri(shape["property"]["value"])
        constraint = shape.get("constraint", {}).get("value", "")
        message = shape.get("message", {}).get("value", "")
        md.append(f"- Property: {prop}\n")
        if constraint:
            md.append(f"  - Constraint: {constraint}\n")
        if message:
            md.append(f"  - Message: {message}\n")

    # Teams and Snowflake Integration section
    md.append("\n## Microsoft Teams and Snowflake Cortex Integration\n")
    integration = run_query(
        "src/chatbot_llm/queries/get_integration_details.rq"
    )
    for item in integration["results"]["bindings"]:
        name = clean_uri(item["label"]["value"])
        comment = item.get("comment", {}).get("value", "")
        context = item.get("context", {}).get("value", "")
        constraint = item.get("constraint", {}).get("value", "")

        md.append(f"### {name}\n")
        md.append(f"{comment}\n\n")
        if context:
            md.append(f"**Context**: {context}\n")
        if constraint:
            md.append(f"**Constraint**: {constraint}\n")
        md.append("\n")

    # Create docs directory if it doesn't exist
    Path("docs").mkdir(exist_ok=True)

    # Write to file
    with open("docs/ontology.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    generate_docs()