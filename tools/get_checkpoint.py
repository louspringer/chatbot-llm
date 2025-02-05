#!/usr/bin/env python3
"""
Tool to query and display checkpoint information from session.ttl
"""

import rdflib
from rdflib import Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS
from pathlib import Path
from datetime import datetime
from typing import Set, List, Tuple, Optional, Dict
import re


def get_session_graph() -> Tuple[rdflib.Graph, Namespace]:
    """Load the session.ttl file into a graph"""
    g = rdflib.Graph()
    session_path = Path("session.ttl")
    g.parse(session_path, format="turtle")

    # Bind namespaces with absolute URIs
    base_path = session_path.resolve().parent
    SESSION = Namespace(f'file://{base_path}/session#')
    g.bind('session', SESSION)
    g.bind('rdf', RDF)
    g.bind('rdfs', RDFS)

    return g, SESSION


def clean_uri(uri: str) -> str:
    """Clean URI for display"""
    if uri.startswith('file://'):
        uri = uri.split('/')[-1].split('#')[-1]
    else:
        uri = uri.split('#')[-1]

    # Remove UUIDs - handle both formats
    uuid_patterns = [
        r'n[0-9a-f]{32}b\d+',  # Format 1
        # Format 2: standard UUID pattern
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    ]
    for pattern in uuid_patterns:
        if re.match(pattern, uri):
            return "<internal-reference>"

    return uri


def format_component_value(
    value: str,
    detail_type: Optional[str] = None
) -> str:
    """Format component value for display"""
    # Handle prefix declarations
    if '@prefix' in value:
        lines = value.strip().split('\n')
        return '\n'.join(f"    {line.strip()}" for line in lines)

    # Handle file references
    if detail_type and str(detail_type).endswith('requiredFiles'):
        return f"File: {value}"

    # Handle branch/issue references
    if detail_type:
        type_str = str(detail_type)
        # Check various reference types
        if type_str.endswith('branch'):
            return f"Branch: {value}"
        if type_str.endswith('issue'):
            return f"Issue #{value}"
        if type_str.endswith('issueTitle'):
            return f"Title: {value}"

    return value


def collect_requirements(
    g: rdflib.Graph,
    task: URIRef,
    prop: URIRef
) -> Set[str]:
    """Collect unique requirements from a task property"""
    requirements = set()
    for req in g.objects(task, prop):
        for _, _, value in g.triples((req, None, None)):
            if isinstance(value, Literal):
                requirements.add(str(value))
    return requirements


def validate_prompt_state(
    g: rdflib.Graph,
    checkpoint: URIRef,
    SESSION: Namespace
) -> Tuple[bool, List[str]]:
    """Validate the prompt state and check for required updates"""
    warnings = []

    # Check if prompt state exists
    prompt_state = g.value(checkpoint, SESSION.hasPromptState)
    if not prompt_state:
        warnings.append("Checkpoint missing prompt state")
        return False, warnings

    # Get current task
    current_task = g.value(prompt_state, SESSION.linkedTask)
    if not current_task:
        warnings.append("No linked task in prompt state")
        return False, warnings

    # Check if task requires prompt update
    requires_update = g.value(current_task, SESSION.requiresPromptUpdate)
    if requires_update and requires_update.value:
        warnings.append("Current task requires prompt update")

        # Get unique prompt requirements
        requirements = collect_requirements(
            g, current_task, SESSION.promptRequirements
        )
        if requirements:
            warnings.append("Required updates:")
            warnings.extend(f"  • {req}" for req in sorted(requirements))
        return False, warnings

    # Validate prompt content
    prompt = g.value(checkpoint, SESSION.resumptionPrompt)
    if not prompt:
        warnings.append("Missing resumption prompt")
        return False, warnings

    # Check last update timestamp
    last_updated = g.value(prompt_state, SESSION.lastUpdated)
    if last_updated:
        try:
            # Parse the timestamp
            update_time = datetime.fromisoformat(
                str(last_updated).replace('Z', '+00:00')
            )
            # Use a reference date for comparison
            ref_date = datetime(2024, 3, 20, tzinfo=update_time.tzinfo)
            days_diff = abs((ref_date - update_time).days)
            
            if days_diff > 7:
                warnings.append(
                    f"Prompt state may be stale "
                    f"(Last updated: {last_updated})"
                )
        except ValueError:
            warnings.append("Invalid last update timestamp")

    return len(warnings) == 0, warnings


def get_checkpoint_prompt(
    g: rdflib.Graph,
    SESSION: Namespace
) -> Optional[str]:
    """Get the current checkpoint's resumption prompt"""
    # Get current checkpoint
    checkpoint = URIRef(str(SESSION) + 'currentCheckpoint')

    if not any(g.triples((checkpoint, None, None))):
        print("No checkpoint found")
        return None

    # Validate prompt state
    is_valid, warnings = validate_prompt_state(g, checkpoint, SESSION)
    if not is_valid:
        print("\n⚠️  Validation Warnings:")
        for warning in warnings:
            print(f"  {warning}")
        print("\nPrompt validation failed - please update the prompt state")

    # Get the prompt text
    return g.value(checkpoint, SESSION.resumptionPrompt)


def get_checkpoint_components(
    g: rdflib.Graph,
    SESSION: Namespace
) -> Dict[str, List[Tuple[int, str]]]:
    """Get all checkpoint components in priority order"""
    query = f"""
    PREFIX session: <{str(SESSION)}>
    PREFIX rdf: <{str(RDF)}>
    PREFIX rdfs: <{str(RDFS)}>

    SELECT ?label ?priority ?details ?detail
    WHERE {{
        session:currentCheckpoint session:hasComponent ?component .
        ?component rdfs:label ?label ;
                  session:componentPriority ?priority .
        OPTIONAL {{
            ?component ?detail ?details .
            FILTER(?detail != rdf:type &&
                   ?detail != rdfs:label &&
                   ?detail != session:componentPriority)
        }}
    }}
    ORDER BY ?priority ?label ?detail
    """

    # Group components by label
    components: Dict[str, List[Tuple[int, str]]] = {}
    for row in g.query(query):
        if hasattr(row, 'details'):
            label = str(row.label)
            priority = int(row.priority)
            details = str(row.details)
            detail_type = str(row.detail) if hasattr(row, 'detail') else None

            if isinstance(row.details, URIRef):
                details = clean_uri(details)
            details = format_component_value(details, detail_type)

            if label not in components:
                components[label] = []
            components[label].append((priority, details))

    return components


def main() -> None:
    """Main entry point"""
    g, SESSION = get_session_graph()

    print("=== Current Checkpoint Prompt ===")
    prompt = get_checkpoint_prompt(g, SESSION)
    if prompt:
        print(prompt)
    else:
        print("No checkpoint prompt found")

    print("\n=== Checkpoint Components ===")
    components = get_checkpoint_components(g, SESSION)

    # Sort components by priority
    sorted_components = sorted(
        components.items(),
        key=lambda x: min(p for p, _ in x[1])
    )

    for label, details in sorted_components:
        priority = details[0][0]  # Use first detail's priority
        print(f"\n{label} (Priority: {priority})")

        # Group and format details
        for _, detail in details:
            if detail.strip():
                if '\n' in detail:
                    print("  •")
                    print(f"{detail}")
                else:
                    print(f"  • {detail}")


if __name__ == "__main__":
    main()
