#!/usr/bin/env python3
"""
Validate Teams Bot deployment against ontology rules.
"""

import logging
import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define namespaces
DEPLOYMENT = Namespace("./deployment#")
SHACL = Namespace("http://www.w3.org/ns/shacl#")


def load_ontologies(base_path: Path) -> tuple[Graph, Graph, Graph]:
    """
    Load all relevant ontology files.

    Args:
        base_path: Base path for ontology files

    Returns:
        Tuple of (data_graph, shacl_graph, ont_graph)
    """
    # Load deployment instance data
    data_graph = Graph()
    data_graph.parse(base_path / "deployment_instance.ttl", format="turtle")

    # Load SHACL validation rules
    shacl_graph = Graph()
    shacl_graph.parse(base_path / "../deployment_validation.ttl", format="turtle")
    shacl_graph.parse(base_path / "deployment_extensions.ttl", format="turtle")

    # Load ontology definitions
    ont_graph = Graph()
    ont_graph.parse(base_path / "../deployment.ttl", format="turtle")

    return data_graph, shacl_graph, ont_graph


def validate_deployment(
    data_graph: Graph, shacl_graph: Graph, ont_graph: Graph
) -> tuple[bool, Graph, str]:
    """
    Validate deployment data against SHACL rules.

    Args:
        data_graph: Graph containing deployment instances
        shacl_graph: Graph containing SHACL validation rules
        ont_graph: Graph containing ontology definitions

    Returns:
        Tuple of (is_valid, results_graph, results_text)
    """
    return validate(
        data_graph,
        shacl_graph=shacl_graph,
        ont_graph=ont_graph,
        inference="rdfs",
        debug=True,
    )


def check_required_components(data_graph: Graph) -> bool:
    """
    Check if all required components are present.

    Args:
        data_graph: Graph containing deployment instances

    Returns:
        True if all required components present
    """
    required_components = [
        (DEPLOYMENT.TeamsBotFunction, "Teams Bot Function"),
        (DEPLOYMENT.BotKeyVault, "Key Vault"),
        (DEPLOYMENT.BotAppInsights, "Application Insights"),
        (DEPLOYMENT.TeamsAuthComponent, "Teams Auth Component"),
        (DEPLOYMENT.TeamsChannelComponent, "Teams Channel Component"),
    ]

    all_present = True
    for component, name in required_components:
        if not (None, None, component) in data_graph:
            logger.error(f"Missing required component: {name}")
            all_present = False

    return all_present


def main():
    """Main validation function."""
    try:
        base_path = Path(__file__).parent

        # Load all graphs
        logger.info("Loading ontology files...")
        data_graph, shacl_graph, ont_graph = load_ontologies(base_path)

        # Check required components
        logger.info("Checking required components...")
        if not check_required_components(data_graph):
            logger.error("Missing required components")
            sys.exit(1)

        # Validate against SHACL rules
        logger.info("Validating against SHACL rules...")
        is_valid, results_graph, results_text = validate_deployment(
            data_graph, shacl_graph, ont_graph
        )

        if not is_valid:
            logger.error("Validation failed:")
            logger.error(results_text)
            sys.exit(1)

        logger.info("Validation successful!")
        return 0

    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
