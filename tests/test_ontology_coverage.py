"""Tests for test coverage ontology using rdflib."""

import os

import pytest
from rdflib import Graph


def get_base_uri(path):
    """Convert relative path to base URI."""
    return f"file://{os.path.abspath(path)}"


@pytest.fixture
def test_graph():
    """Create a test graph with test_coverage.ttl loaded."""
    g = Graph()
    g.parse("ontologies/test_coverage.ttl", format="turtle")
    return g


def test_coverage_metric_ranges(test_graph):
    """Test that coverage metrics are properly defined and within valid
    ranges."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX tc: <{base_uri}/test_coverage.ttl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    SELECT ?metric ?coverage WHERE {{
        ?metric a tc:CoverageMetric ;
                tc:coveragePercentage ?coverage .
        # Convert to decimal for comparison
        BIND(xsd:decimal(?coverage) AS ?value)
        FILTER(?value < 0.0 || ?value > 100.0)
    }}
    """
    invalid_metrics = list(test_graph.query(query))
    assert (
        len(invalid_metrics) == 0
    ), f"Found metrics with invalid coverage values: {invalid_metrics}"


def test_coverage_metric_completeness(test_graph):
    """Test that coverage metrics have all required properties."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX tc: <{base_uri}/test_coverage.ttl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?metric WHERE {{
        ?metric a tc:CoverageMetric .
        FILTER NOT EXISTS {{ ?metric tc:coveragePercentage ?coverage }}
        FILTER NOT EXISTS {{ ?metric rdfs:label ?label }}
    }}
    """
    incomplete_metrics = list(test_graph.query(query))
    assert (
        len(incomplete_metrics) == 0
    ), f"Found metrics missing required properties: {incomplete_metrics}"


def test_coverage_metric_links(test_graph):
    """Test that coverage metrics are properly linked to test suites."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX tc: <{base_uri}/test_coverage.ttl#>
    SELECT ?metric WHERE {{
        ?metric a tc:CoverageMetric .
        FILTER NOT EXISTS {{
            ?suite a tc:TestSuite ;
                   tc:hasCoverageMetric ?metric .
        }}
    }}
    """
    unlinked_metrics = list(test_graph.query(query))
    assert (
        len(unlinked_metrics) == 0
    ), f"Found metrics not linked to any test suite: {unlinked_metrics}"


def test_coverage_metric_consistency(test_graph):
    """Test that test suites with all passing tests have high coverage."""
    base_uri = get_base_uri("ontologies")
    query = f"""
    PREFIX tc: <{base_uri}/test_coverage.ttl#>
    SELECT ?suite ?metric ?coverage WHERE {{
        ?suite a tc:TestSuite ;
               tc:hasCoverageMetric ?metric .
        ?metric tc:coveragePercentage ?coverage .
        # Check if all tests in the suite passed
        FILTER NOT EXISTS {{
            ?suite tc:hasTestCase ?case .
            ?case tc:hasResult ?result .
            ?result tc:testStatus ?status .
            FILTER(?status != "passed")
        }}
        # Convert to decimal for comparison
        BIND(xsd:decimal(?coverage) AS ?value)
        # Expecting high coverage for fully passing suites
        FILTER(?value < 80.0)
    }}
    """
    inconsistent_metrics = list(test_graph.query(query))
    assert len(inconsistent_metrics) == 0, (
        "Found test suites with all passing tests but low coverage: "
        f"{inconsistent_metrics}"
    )
