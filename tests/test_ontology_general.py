"""Tests for ontology accessibility framework using rdflib."""

import os

import pytest
from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF, RDFS, XSD


def get_base_uri(path):
    """Convert relative path to base URI."""
    return f"file://{os.path.abspath(path)}"


@pytest.fixture
def test_graph():
    """Create a test graph with ontologies loaded."""
    g = Graph()

    # Bind common namespaces
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)
    g.bind("sh", Namespace("http://www.w3.org/ns/shacl#"))

    # Load ontologies in specific order
    ontologies = [
        "meta.ttl",
        "metameta.ttl",
        "conversation.ttl",
        "problem.ttl",
        "solution.ttl",
        "guidance.ttl",
        "cognition_patterns.ttl",
        "policy_driven_implementation.ttl",
        "package_management.ttl",
    ]

    for onto_file in ontologies:
        path = os.path.join("ontologies", onto_file)
        if os.path.exists(path):
            g.parse(path, format="turtle")

    return g


def test_ontology_metadata(test_graph):
    """Test that all ontologies have required metadata."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?ontology ?label ?comment ?version WHERE {
        ?ontology a owl:Ontology ;
                 rdfs:label ?label ;
                 rdfs:comment ?comment ;
                 owl:versionInfo ?version .
    }
    """

    results = list(test_graph.query(query))
    assert len(results) > 0, "No ontologies found with complete metadata"


def test_class_documentation(test_graph):
    """Test that all classes have labels and comments."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?class WHERE {
        ?class a owl:Class .
        FILTER NOT EXISTS { ?class rdfs:label ?label }
        FILTER NOT EXISTS { ?class rdfs:comment ?comment }
    }
    """

    results = list(test_graph.query(query))
    missing = len(results)
    assert (
        missing == 0
    ), f"Found {missing} classes without proper documentation"


def test_property_domains_ranges(test_graph):
    """Test that all properties have domains and ranges defined."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?prop WHERE {
        { ?prop a owl:ObjectProperty }
        UNION
        { ?prop a owl:DatatypeProperty }
        FILTER NOT EXISTS { ?prop rdfs:domain ?domain }
        FILTER NOT EXISTS { ?prop rdfs:range ?range }
    }
    """

    results = list(test_graph.query(query))
    missing = len(results)
    assert missing == 0, f"Found {missing} properties without domain/range"


def test_class_hierarchy(test_graph):
    """Test class hierarchy structure."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?class ?superclass (COUNT(?mid) as ?depth) WHERE {
        ?class rdfs:subClassOf+ ?superclass .
        OPTIONAL {
            ?class rdfs:subClassOf+ ?mid .
            ?mid rdfs:subClassOf+ ?superclass .
        }
    }
    GROUP BY ?class ?superclass
    ORDER BY DESC(?depth)
    """

    results = list(test_graph.query(query))
    assert len(results) > 0, "No class hierarchy found"


def test_shacl_constraints(test_graph):
    """Test SHACL shape definitions."""
    query = """
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?shape ?targetClass ?property ?constraint WHERE {
        ?shape a sh:NodeShape ;
               sh:targetClass ?targetClass ;
               sh:property ?property .
        ?property ?constraint ?value .
    }
    """

    results = list(test_graph.query(query))
    assert len(results) > 0, "No SHACL shapes found"


def test_instance_validation(test_graph):
    """Test that instances conform to their class definitions."""
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?instance ?class ?requiredProp WHERE {
        ?class a owl:Class .
        ?instance a ?class .
        ?requiredProp rdfs:domain ?class .
        FILTER NOT EXISTS { ?instance ?requiredProp ?value }
        # Exclude some common RDF/RDFS/OWL properties
        FILTER(?requiredProp NOT IN (
            rdf:type, rdfs:label, rdfs:comment,
            owl:versionInfo, owl:imports
        ))
    }
    ORDER BY ?instance ?requiredProp
    """

    results = list(test_graph.query(query))
    if len(results) > 0:
        error_msg = "Found instances missing required properties:\n"
        for r in results:
            instance = str(r[0])
            class_name = str(r[1])
            prop = str(r[2])
            error_msg += f"Instance {instance} of class {class_name} "
            error_msg += f"missing property {prop}\n"
        assert len(results) == 0, error_msg


def test_ontology_imports(test_graph):
    """Test ontology import relationships."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT ?ontology ?imported WHERE {
        ?ontology a owl:Ontology ;
                 owl:imports ?imported .
    }
    """

    results = list(test_graph.query(query))
    assert len(results) > 0, "No ontology imports found"


def test_cross_ontology_references(test_graph):
    """Test references between different ontologies."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?source ?target ?p WHERE {
        ?source ?p ?target .
        FILTER(STRSTARTS(STR(?source), ?sourceOnt))
        FILTER(STRSTARTS(STR(?target), ?targetOnt))
        FILTER(?sourceOnt != ?targetOnt)
        FILTER(?p NOT IN (rdf:type, rdfs:label, rdfs:comment, owl:imports))
        BIND(REPLACE(STR(?source), "/[^/]*$", "/") AS ?sourceOnt)
        BIND(REPLACE(STR(?target), "/[^/]*$", "/") AS ?targetOnt)
    }
    ORDER BY ?source ?target
    """

    results = list(test_graph.query(query))
    if len(results) == 0:
        print("No cross-ontology references found. Expected references like:")
        print("- EnforcementMechanism -> Pattern (usesPattern)")
        print("- EnforcementMechanism -> Class (implementedIn)")
    assert len(results) > 0, "No cross-ontology references found"


def test_deprecated_terms(test_graph):
    """Test for deprecated terms and their replacements."""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?deprecated ?replacement WHERE {
        ?deprecated owl:deprecated true .
        OPTIONAL { ?deprecated rdfs:seeAlso ?replacement }
    }
    """

    results = list(test_graph.query(query))
    # This is informational, not necessarily a failure
    if len(results) > 0:
        print(f"Found {len(results)} deprecated terms")
