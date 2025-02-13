"""Tests for ontology accessibility framework using rdflib."""

import os

import pytest
from rdflib import Graph


def get_base_uri(path):
    """Convert relative path to base URI."""
    return f"file://{os.path.abspath(path)}"


@pytest.fixture
def test_graph():
    """Create a test graph with our ontologies loaded."""
    g = Graph()
    g.parse("ontologies/policy_driven_implementation.ttl", format="turtle")
    g.parse("ontologies/cognition_patterns.ttl", format="turtle")
    return g


def test_policy_structure(test_graph):
    """Test that policies drive requirements that influence decisions."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX pdi: <{base_uri}/policy_driven_implementation.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?policy ?req ?decision WHERE {{
        ?policy rdf:type pdi:Policy ;
                pdi:drivesRequirement ?req .
        ?req pdi:influencesDecision ?decision .
    }}
    """

    results = test_graph.query(query)
    assert any("OntologyAccessibilityPolicy" in str(r) for r in results)


def test_enforcement_mechanisms(test_graph):
    """Test that enforcement mechanisms are properly defined."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX pdi: <{base_uri}/policy_driven_implementation.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?mech ?impl ?pattern WHERE {{
        ?mech rdf:type pdi:EnforcementMechanism ;
              pdi:implementedIn ?impl ;
              pdi:usesPattern ?pattern .
    }}
    """

    results = test_graph.query(query)
    assert len(list(results)) >= 3


def test_cognitive_patterns(test_graph):
    """Test cognitive pattern definitions and relationships."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX cog: <{base_uri}/cognition_patterns.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?pattern ?context ?complexity WHERE {{
        ?pattern rdf:type ?type .
        ?type rdfs:subClassOf cog:Pattern .
        ?pattern cog:hasContext ?context ;
                cog:hasComplexity ?complexity .
    }}
    """

    results = test_graph.query(query)
    assert len(list(results)) >= 3


def test_meta_pattern_relationships(test_graph):
    """Test that meta patterns properly relate to other patterns."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX cog: <{base_uri}/cognition_patterns.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?meta ?related WHERE {{
        ?meta rdf:type cog:MetaPattern ;
              cog:relatesTo ?related .
    }}
    """

    results = test_graph.query(query)
    assert len(list(results)) >= 1


def test_pattern_complexity_validation(test_graph):
    """Test pattern complexity constraints."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX cog: <{base_uri}/cognition_patterns.ttl#>

    SELECT ?pattern ?complexity WHERE {{
        ?pattern cog:hasComplexity ?complexity .
        FILTER (?complexity >= 1 && ?complexity <= 5)
    }}
    """

    results = test_graph.query(query)
    assert len(list(results)) >= 1


def test_cross_references(test_graph):
    """Test cross-referencing between ontologies."""
    base_uri = get_base_uri("ontologies")

    # First check what enforcement mechanisms we have
    debug_query1 = f"""
    PREFIX pdi: <{base_uri}/policy_driven_implementation.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?mech ?pattern WHERE {{
        ?mech rdf:type pdi:EnforcementMechanism ;
              pdi:usesPattern ?pattern .
    }}
    """

    debug_results1 = test_graph.query(debug_query1)
    print("\nEnforcement mechanisms:", list(debug_results1))

    # Then check what emergent patterns we have
    debug_query2 = f"""
    PREFIX cog: <{base_uri}/cognition_patterns.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?pattern ?type WHERE {{
        ?pattern rdf:type ?type .
        ?type rdfs:subClassOf* cog:EmergentPattern .
    }}
    """

    debug_results2 = test_graph.query(debug_query2)
    print("\nEmergent patterns:", list(debug_results2))

    # Original query
    query = f"""
    PREFIX pdi: <{base_uri}/policy_driven_implementation.ttl#>
    PREFIX cog: <{base_uri}/cognition_patterns.ttl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?mech ?pattern WHERE {{
        ?mech rdf:type pdi:EnforcementMechanism ;
              pdi:usesPattern ?pattern .
        {{
            ?pattern rdf:type cog:EmergentPattern .
        }} UNION {{
            FILTER(?pattern = cog:EmergentPattern)
        }} UNION {{
            FILTER(CONTAINS(str(?pattern), "EmergentPattern"))
        }}
        FILTER(CONTAINS(str(?mech), "CrossRefTrackerMechanism"))
    }}
    """

    results = test_graph.query(query)
    print("\nCross-references:", list(results))
    assert any("CrossRefTrackerMechanism" in str(r) for r in results)


def test_validation_shapes(test_graph):
    """Test SHACL validation shapes are properly defined."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX pdi: <{base_uri}/policy_driven_implementation.ttl#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?shape WHERE {{
        ?shape rdf:type sh:NodeShape .
    }}
    """

    results = test_graph.query(query)
    assert len(list(results)) >= 4
