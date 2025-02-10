"""Tests for checkpoint validation and output with LLM guidance."""

import pytest
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
from tools.get_checkpoint import (
    clean_uri,
    format_component_value,
    collect_requirements,
    validate_prompt_state,
    get_checkpoint_prompt,
    get_checkpoint_components,
)


# Expected output templates for LLM guidance
EXPECTED_OUTPUT_TEMPLATES = {
    "checkpoint_prompt": """=== Current Checkpoint Prompt ===
{prompt_text}

=== Checkpoint Components ===

{component_sections}""",  # noqa: E501
    "component_section": """{label} (Priority: {priority})
{details}""",
    "component_detail": "  • {detail}",
}


# Example valid checkpoint data
VALID_CHECKPOINT_DATA = {
    "prompt": (
        "Continue implementing the test framework with proper validation..."  # noqa: E501
    ),
    "components": {
        "Test Framework": [
            (1, "File: test_framework.py"),
            (1, "Branch: feature/test-framework"),  # noqa: E501
            (1, "Issue #42"),
        ],
        "Documentation": [
            (2, "File: README.md"),
            (2, "Title: Test Framework Documentation"),  # noqa: E501
        ],
    },
}


@pytest.fixture
def test_graph():
    """Create a test RDF graph with sample checkpoint data."""
    g = Graph()

    # Create test namespace - use relative paths
    SESSION = Namespace("./session#")
    g.bind("session", SESSION)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)

    # Add checkpoint with expected data structure
    checkpoint = URIRef(str(SESSION) + "currentCheckpoint")
    g.add((checkpoint, RDF.type, SESSION.Checkpoint))
    g.add(
        (checkpoint, SESSION.resumptionPrompt, Literal(VALID_CHECKPOINT_DATA["prompt"]))  # noqa: E501
    )

    # Add prompt state with current timestamp
    prompt_state = URIRef(str(SESSION) + "promptState1")
    g.add((checkpoint, SESSION.hasPromptState, prompt_state))
    g.add((prompt_state, RDF.type, SESSION.PromptState))
    g.add(
        (
            prompt_state,
            SESSION.lastUpdated,
            Literal(datetime.now(timezone.utc).isoformat()),
        )
    )

    # Add current task
    task = URIRef(str(SESSION) + "task1")
    g.add((prompt_state, SESSION.linkedTask, task))
    g.add((task, RDF.type, SESSION.Task))
    g.add((task, SESSION.requiresPromptUpdate, Literal(False)))

    # Add components with expected structure
    for label, details in VALID_CHECKPOINT_DATA["components"].items():
        component = URIRef(str(SESSION) + clean_uri(label.lower()))
        g.add((checkpoint, SESSION.hasComponent, component))
        g.add((component, RDF.type, SESSION.Component))
        g.add((component, RDFS.label, Literal(label)))

        # Add details with proper predicates
        for priority, detail in details:
            g.add((component, SESSION.componentPriority, Literal(priority)))
            if "File:" in detail:
                file_path = detail.replace("File: ", "")
                g.add((component, SESSION.requiredFiles, Literal(file_path)))
            elif "Branch:" in detail:
                branch = detail.replace("Branch: ", "")
                g.add((component, SESSION.branch, Literal(branch)))
            elif "Issue" in detail:
                issue = detail.replace("Issue #", "")
                g.add((component, SESSION.issue, Literal(issue)))
            elif "Title:" in detail:
                title = detail.replace("Title: ", "")
                g.add((component, SESSION.issueTitle, Literal(title)))

    return g, SESSION


def format_expected_output(data: Dict) -> str:
    """Format the expected output string based on templates."""
    component_sections = []
    for label, details in data["components"].items():
        # Format each detail line
        detail_template = EXPECTED_OUTPUT_TEMPLATES["component_detail"]
        detail_lines = [
            detail_template.format(detail=detail[1])
            for detail in details
        ]
        
        # Format section with details
        section = EXPECTED_OUTPUT_TEMPLATES["component_section"].format(
            label=label,
            priority=details[0][0],
            details="\n".join(detail_lines)
        )
        component_sections.append(section)

    # Format complete output
    return EXPECTED_OUTPUT_TEMPLATES["checkpoint_prompt"].format(
        prompt_text=data["prompt"],
        component_sections="\n\n".join(component_sections)
    )


def test_clean_uri():
    """Test URI cleaning function with LLM guidance."""
    # Test UUID cleaning
    assert clean_uri("n123e4567890123456789012345678901b1") == "<internal-reference>"
    assert clean_uri("123e4567-e89b-12d3-a456-426614174000") == "<internal-reference>"

    # Test relative path cleaning
    assert clean_uri("./path/to/file#component") == "component"
    assert clean_uri("./session#test") == "test"

    # Test simple fragment
    assert clean_uri("http://example.com#test") == "test"


def test_format_component_value():
    """Test component value formatting with LLM guidance."""
    # Test prefix declaration
    prefix = "@prefix test: <http://example.com> .\n@prefix other: <http://other.com> ."  # noqa: E501
    formatted = format_component_value(prefix)
    assert all(line.startswith("    @prefix") for line in formatted.split("\n"))  # noqa: E501

    # Test file reference
    assert format_component_value("test.py", "requiredFiles") == "File: test.py"  # noqa: E501

    # Test branch reference
    assert format_component_value("main", "branch") == "Branch: main"

    # Test issue reference
    assert format_component_value("123", "issue") == "Issue #123"

    # Test issue title
    assert format_component_value("Bug fix", "issueTitle") == "Title: Bug fix"


def test_collect_requirements(test_graph):
    """Test requirement collection with LLM guidance."""
    g, SESSION = test_graph

    # Add test requirements
    task = URIRef(str(SESSION) + "task1")
    req1 = URIRef(str(SESSION) + "req1")
    req2 = URIRef(str(SESSION) + "req2")

    g.add((task, SESSION.promptRequirements, req1))
    g.add((task, SESSION.promptRequirements, req2))
    g.add((req1, SESSION.requirement, Literal("Update X")))
    g.add((req2, SESSION.requirement, Literal("Update Y")))

    reqs = collect_requirements(g, task, SESSION.promptRequirements)
    assert len(reqs) == 2
    assert "Update X" in reqs
    assert "Update Y" in reqs


def test_validate_prompt_state(test_graph):
    """Test prompt state validation with LLM guidance."""
    g, SESSION = test_graph
    checkpoint = URIRef(str(SESSION) + "currentCheckpoint")

    # Test valid state
    is_valid, warnings = validate_prompt_state(g, checkpoint, SESSION)
    assert is_valid  # Should be valid even with non-critical warnings
    assert not any("stale" in w for w in warnings)

    # Test missing prompt state
    g.remove((checkpoint, SESSION.hasPromptState, None))
    is_valid, warnings = validate_prompt_state(g, checkpoint, SESSION)
    assert not is_valid
    assert "Checkpoint missing prompt state" in warnings

    # Test stale prompt - create new graph and state
    g, SESSION = test_graph  # Reset graph
    checkpoint = URIRef(str(SESSION) + "currentCheckpoint")
    # Create new prompt state with old timestamp
    new_prompt_state = URIRef(str(SESSION) + "stalePromptState")
    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    # Remove existing prompt state
    g.remove((checkpoint, SESSION.hasPromptState, None))
    # Add new prompt state with stale timestamp
    g.add((checkpoint, SESSION.hasPromptState, new_prompt_state))
    g.add((new_prompt_state, RDF.type, SESSION.PromptState))
    timestamp = Literal(old_date.isoformat())
    g.add((new_prompt_state, SESSION.lastUpdated, timestamp))
    # Add required task link
    task = URIRef(str(SESSION) + "task1")
    g.add((new_prompt_state, SESSION.linkedTask, task))
    g.add((task, SESSION.requiresPromptUpdate, Literal(False)))

    is_valid, warnings = validate_prompt_state(g, checkpoint, SESSION)
    assert is_valid  # Should still be valid with stale warning
    assert any("stale" in w for w in warnings)


def test_get_checkpoint_prompt(test_graph):
    """Test checkpoint prompt retrieval with LLM guidance."""
    g, SESSION = test_graph

    # Test valid prompt
    prompt = get_checkpoint_prompt(g, SESSION)
    assert str(prompt) == VALID_CHECKPOINT_DATA["prompt"]

    # Test missing prompt
    g.remove((None, SESSION.resumptionPrompt, None))
    prompt = get_checkpoint_prompt(g, SESSION)
    assert prompt is None


def test_get_checkpoint_components(test_graph):
    """Test component retrieval and ordering with LLM guidance."""
    g, SESSION = test_graph

    components = get_checkpoint_components(g, SESSION)

    # Verify against expected data
    for label, expected_details in VALID_CHECKPOINT_DATA["components"].items():
        assert label in components

        # Check priorities
        comp_priority = min(p for p, _ in components[label])
        expected_priority = expected_details[0][0]
        assert comp_priority == expected_priority

        # Check details
        comp_details = [d for _, d in components[label]]
        expected_details_str = [d for _, d in expected_details]
        assert all(d in comp_details for d in expected_details_str)


def test_output_format(test_graph: Tuple[Graph, Namespace], capsys: Any) -> None:  # noqa: E501
    """Test the complete output format with LLM guidance."""
    g, SESSION = test_graph

    # Generate expected output
    expected_output = format_expected_output(VALID_CHECKPOINT_DATA)

    # Run the main function (simulated)
    prompt = get_checkpoint_prompt(g, SESSION)
    print("=== Current Checkpoint Prompt ===")
    print(str(prompt) if prompt else "No checkpoint prompt found")

    print("\n=== Checkpoint Components ===")
    components = get_checkpoint_components(g, SESSION)

    # Sort components by priority with explicit type hints
    sorted_components: List[Tuple[str, List[Tuple[int, str]]]] = sorted(
        components.items(),
        key=lambda x: min(p for p, _ in x[1]) if x[1] else float('inf')
    )

    for label, details in sorted_components:
        priority = details[0][0]
        print(f"\n{label} (Priority: {priority})")
        for _, detail in details:
            if detail.strip():
                print(f"  • {detail}")

    # Capture and verify output
    captured = capsys.readouterr()
    # Normalize line endings and whitespace
    captured_lines = [line.strip() for line in captured.out.strip().split('\n')]  # noqa: E501
    expected_lines = [line.strip() for line in expected_output.strip().split('\n')]  # noqa: E501
    assert captured_lines == expected_lines


def test_invalid_checkpoint(test_graph):
    """Test handling of invalid checkpoint data with LLM guidance."""
    g, SESSION = test_graph
    checkpoint = URIRef(str(SESSION) + "currentCheckpoint")

    # Remove all checkpoint data
    for s, p, o in g.triples((checkpoint, None, None)):
        g.remove((s, p, o))

    # Test component retrieval with missing data
    components = get_checkpoint_components(g, SESSION)
    assert not components

    # Test prompt retrieval with missing data
    prompt = get_checkpoint_prompt(g, SESSION)
    assert prompt is None
