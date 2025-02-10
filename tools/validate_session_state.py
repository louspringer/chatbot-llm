#!/usr/bin/env python3

"""
Validates session.ttl state requirements including checkpoint structure.
Ensures the session state matches test expectations and maintains consistency.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS


def setup_logging() -> logging.Logger:
    """Configure logging for the validator"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


def load_session_graph() -> Tuple[Graph, Namespace]:
    """Load the session.ttl file and return graph with namespace"""
    g = Graph()
    session_path = Path("session.ttl")
    if not session_path.exists():
        raise FileNotFoundError("session.ttl not found")

    g.parse(session_path, format="turtle")

    # Bind namespaces
    SESSION = Namespace("./session#")
    g.bind("session", SESSION)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)

    return g, SESSION


def validate_checkpoint(g: Graph, SESSION: Namespace) -> List[str]:
    """Validate checkpoint requirements"""
    errors = []

    # Check for current checkpoint
    checkpoint = URIRef(str(SESSION) + "currentCheckpoint")
    if not any(g.triples((checkpoint, RDF.type, SESSION.Checkpoint))):
        errors.append("❌ Missing current checkpoint definition")
        return errors

    # Check for resumption prompt
    if not any(g.triples((checkpoint, SESSION.resumptionPrompt, None))):
        errors.append("❌ Missing resumption prompt in checkpoint")

    # Check prompt state
    prompt_state = g.value(checkpoint, SESSION.hasPromptState)
    if not prompt_state:
        errors.append("❌ Missing prompt state in checkpoint")
        return errors

    # Validate prompt state structure
    if not any(g.triples((prompt_state, RDF.type, SESSION.PromptState))):
        errors.append("❌ Invalid prompt state type")

    # Check timestamp
    last_updated = g.value(prompt_state, SESSION.lastUpdated)
    if not last_updated:
        errors.append("❌ Missing lastUpdated timestamp in prompt state")
    else:
        try:
            # Validate timestamp format
            datetime.fromisoformat(str(last_updated).replace("Z", "+00:00"))
        except ValueError:
            errors.append("❌ Invalid timestamp format in prompt state")

    # Check task linkage
    task = g.value(prompt_state, SESSION.linkedTask)
    if not task:
        errors.append("❌ Missing linked task in prompt state")
    elif not any(g.triples((task, RDF.type, SESSION.Task))):
        errors.append("❌ Invalid task reference in prompt state")

    # Check task update flag
    requires_update = g.value(task, SESSION.requiresPromptUpdate) if task else None
    if requires_update is None:
        errors.append("❌ Missing requiresPromptUpdate flag in linked task")

    return errors


def validate_components(g: Graph, SESSION: Namespace) -> List[str]:
    """Validate checkpoint components"""
    errors = []
    checkpoint = URIRef(str(SESSION) + "currentCheckpoint")

    # Check for components
    components = list(g.objects(checkpoint, SESSION.hasComponent))
    if not components:
        errors.append("❌ No components found in checkpoint")
        return errors

    for component in components:
        # Check component type
        if not any(g.triples((component, RDF.type, SESSION.Component))):
            errors.append(f"❌ Invalid component type: {component}")
            continue

        # Check required properties
        label = g.value(component, RDFS.label)
        if not label:
            errors.append(f"❌ Missing label for component: {component}")

        priority = g.value(component, SESSION.componentPriority)
        if not priority:
            errors.append(f"❌ Missing priority for component: {component}")
        else:
            try:
                priority_val = int(str(priority))
                if not (1 <= priority_val <= 5):
                    errors.append(
                        f"❌ Invalid priority value for {label}: {priority_val}"
                    )
            except ValueError:
                errors.append(f"❌ Non-integer priority for {label}: {priority}")

    return errors


def main() -> None:
    """Main validation entry point"""
    logger = setup_logging()
    logger.info("Starting session.ttl validation...")

    try:
        g, SESSION = load_session_graph()

        # Run validations
        checkpoint_errors = validate_checkpoint(g, SESSION)
        component_errors = validate_components(g, SESSION)

        # Report results
        all_errors = checkpoint_errors + component_errors
        if all_errors:
            logger.error("Session validation failed:")
            for error in all_errors:
                logger.error(error)
            exit(1)
        else:
            logger.info("✅ Session validation successful!")
            exit(0)

    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
