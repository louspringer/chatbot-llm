# Ontology: meta:ValidationComponent
# Implements: meta:DebugValidation
# Requirement: REQ-VAL-004 Debug Validation Support
# Guidance: guidance:ValidationPatterns#DebugSupport
# Description: Debug support for ontology validation

import logging
import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, URIRef

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def debug_validate_ontology(file_path: str) -> None:
    """Debug validation of a single ontology file."""
    logger.debug(f"Validating file: {file_path}")

    # Check file exists
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return

    try:
        # Load the graph
        g = Graph()
        logger.debug("Loading graph...")
        g.parse(file_path, format="turtle")
        logger.debug(f"Graph loaded with {len(g)} triples")

        # Check for basic requirements
        logger.debug("Checking basic requirements...")

        # Check for ontology declaration
        ont_types = list(
            g.subjects(
                URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                URIRef("http://www.w3.org/2002/07/owl#Ontology"),
            ),
        )
        logger.debug(f"Found {len(ont_types)} ontology declarations: {ont_types}")

        # Check for classes
        classes = list(
            g.subjects(
                URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                URIRef("http://www.w3.org/2002/07/owl#Class"),
            ),
        )
        logger.debug(f"Found {len(classes)} classes")

        # Check for properties
        props = list(
            g.subjects(
                URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                URIRef("http://www.w3.org/2002/07/owl#ObjectProperty"),
            ),
        )
        logger.debug(f"Found {len(props)} object properties")

        # Try SHACL validation
        logger.debug("Running SHACL validation...")
        try:
            conforms, results_graph, results_text = validate(g)
            logger.debug(f"SHACL validation {'passed' if conforms else 'failed'}")
            if not conforms:
                logger.debug(f"Validation results:\n{results_text}")
        except Exception as e:
            logger.error(f"SHACL validation error: {e}")

    except Exception as e:
        logger.error(f"Error validating {file_path}: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_validate.py <ontology_file>")
        sys.exit(1)

    debug_validate_ontology(sys.argv[1])
