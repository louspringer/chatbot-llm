# Ontology: meta:ValidationComponent
# Implements: meta:OntologyIntegrityCheck
# Requirement: REQ-VAL-003 Ontology Integrity Validation
# Guidance: guidance:ValidationPatterns#IntegrityCheck
# Description: Validates ontology metadata and constraints

import logging
from pathlib import Path

import rdflib
from rdflib import OWL, RDF, RDFS
from rdflib.term import Node

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_all_subclass_instances(g: rdflib.Graph, cls: Node) -> set[Node]:
    """Get all instances of a class including instances of its subclasses."""
    instances = set(g.subjects(RDF.type, cls))

    # Get all subclasses
    for subclass in g.subjects(RDFS.subClassOf, cls):
        instances.update(get_all_subclass_instances(g, subclass))

    return instances


def check_property_integrity(graph, property_uri):
    """Validate property definitions and constraints."""
    # Validate property definitions
    has_domain = False
    has_range = False

    # Check direct definitions
    domain_objects = graph.objects(property_uri, RDFS.domain)
    range_objects = graph.objects(property_uri, RDFS.range)

    if any(domain_objects):
        has_domain = True
    if any(range_objects):
        has_range = True

    # Check inherited definitions
    if not (has_domain and has_range):
        for superprop in graph.objects(property_uri, RDFS.subPropertyOf):
            domain_objects = graph.objects(superprop, RDFS.domain)
            range_objects = graph.objects(superprop, RDFS.range)

            if any(domain_objects):
                has_domain = True
            if any(range_objects):
                has_range = True

    return has_domain, has_range


def check_ontology_integrity(file_path: str) -> list[str]:
    """Check ontology file for integrity issues."""
    issues = []
    g = rdflib.Graph()

    try:
        g.parse(file_path, format="turtle")
        logger.debug(f"Successfully parsed ontology file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to parse ontology file {file_path}: {e}")
        return [f"Failed to parse ontology file: {e}"]

    # Check classes
    classes = list(g.subjects(RDF.type, OWL.Class))
    logger.debug(f"Found {len(classes)} classes in {file_path}")

    for cls in classes:
        # Skip checking version info for imported classes
        if str(cls).startswith(str(g.namespace_manager.store.namespace(""))):
            version_info = list(g.objects(cls, OWL.versionInfo))
            if not version_info:
                logger.debug(f"Class {cls} missing versionInfo")
                issues.append(f"Missing owl:versionInfo for class {cls}")

    # Check properties
    properties = list(g.subjects(RDF.type, OWL.DatatypeProperty)) + list(
        g.subjects(RDF.type, OWL.ObjectProperty),
    )
    logger.debug(f"Found {len(properties)} properties in {file_path}")

    for prop in properties:
        # Skip checking imported properties
        if str(prop).startswith(str(g.namespace_manager.store.namespace(""))):
            issues.extend(check_property_integrity(g, prop))

    # Check instances per class
    for cls in classes:
        # Skip checking imported classes
        if not str(cls).startswith(str(g.namespace_manager.store.namespace(""))):
            continue

        all_instances = get_all_subclass_instances(g, cls)
        logger.debug(
            f"Class {cls} has {len(all_instances)} total instances (including subclasses)",
        )

        if len(all_instances) < 2:
            # Check if it's an abstract class
            is_abstract = g.value(cls, RDF.type) == OWL.Class and not any(
                g.subjects(RDF.type, cls),
            )

            if not is_abstract:
                issues.append(f"Less than two instances for class {cls}")

    return issues


def main():
    """Main function to check ontology files."""
    ontology_files = Path().glob("**/*.ttl")

    for file_path in ontology_files:
        logger.info(f"Checking ontology file: {file_path}")
        issues = check_ontology_integrity(str(file_path))

        if issues:
            logger.warning(f"Found {len(issues)} issues in {file_path}:")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info(f"No issues found in {file_path}")


if __name__ == "__main__":
    main()
