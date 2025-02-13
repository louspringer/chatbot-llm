"""Tests for the test message framework."""

import json

import pytest

from tools.test_messages import (
    BotTester,
    RequirementCoverage,
    TestCase,
    TestResult,
)

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def test_config_file(tmp_path):
    """Create a temporary test configuration file."""
    config = {
        "metadata": {"version": "1.0.0", "description": "Test configuration"},
        "test_cases": [
            {
                "name": "Test Case 1",
                "input_message": "hello",
                "expected_patterns": ["hi", "hello"],
                "requirements": ["REQ-001"],
            }
        ],
        "requirement_traces": {
            "REQ-001": {
                "description": "Test requirement",
                "acceptance_criteria": ["Test criteria"],
            }
        },
    }

    config_file = tmp_path / "test_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f)
    return config_file


def test_test_case_creation():
    """Test creating a TestCase instance."""
    test_case = TestCase(
        name="Test", input_message="hello", expected_patterns=["hi"]
    )
    assert test_case.name == "Test"
    assert test_case.input_message == "hello"
    assert test_case.expected_patterns == ["hi"]
    assert test_case.conversation_type == "message"
    assert test_case.timeout_seconds == 5
    assert test_case.requirements == []
    assert test_case.description == ""


def test_test_result_creation():
    """Test creating a TestResult instance."""
    test_case = TestCase(
        name="Test", input_message="hello", expected_patterns=["hi"]
    )
    result = TestResult(
        test_case=test_case, success=True, actual_response="hi there"
    )
    assert result.success
    assert result.actual_response == "hi there"
    assert result.error is None
    assert result.response_time == 0.0


def test_requirement_coverage():
    """Test requirement coverage calculation."""
    coverage = RequirementCoverage(
        requirement_id="REQ-001",
        description="Test requirement",
        acceptance_criteria=["Test criteria"],
        test_cases=["Test 1", "Test 2"],
        passing_tests=["Test 1"],
        failing_tests=[],
    )
    assert coverage.coverage_percentage == 50.0


def test_bot_tester_initialization():
    """Test BotTester initialization."""
    tester = BotTester()
    assert tester.endpoint == "http://localhost:3978/api/messages"
    assert tester.results == []
    assert tester.test_config is None
    assert tester.requirement_coverage == {}


def test_load_test_config(test_config_file):
    """Test loading test configuration."""
    tester = BotTester()
    tester.load_test_config(test_config_file)

    assert tester.test_config is not None
    assert len(tester.requirement_coverage) == 1
    assert "REQ-001" in tester.requirement_coverage

    req = tester.requirement_coverage["REQ-001"]
    assert req.requirement_id == "REQ-001"
    assert req.description == "Test requirement"
    assert req.acceptance_criteria == ["Test criteria"]
    assert req.test_cases == ["Test Case 1"]


def test_load_test_cases(test_config_file):
    """Test loading test cases."""
    tester = BotTester()
    tester.load_test_config(test_config_file)
    test_cases = tester.load_test_cases()

    assert len(test_cases) == 1
    test_case = test_cases[0]
    assert test_case.name == "Test Case 1"
    assert test_case.input_message == "hello"
    assert test_case.expected_patterns == ["hi", "hello"]
    assert test_case.requirements == ["REQ-001"]


@pytest.mark.asyncio
async def test_send_message():
    """Test sending a message."""
    tester = BotTester()
    result = await tester.send_message("hello")

    # Since we're not actually connecting to a bot,
    # we expect this to fail
    assert not result["success"]
    assert "error" in result


@pytest.mark.asyncio
async def test_run_test_case():
    """Test running a test case."""
    tester = BotTester()
    test_case = TestCase(
        name="Test", input_message="hello", expected_patterns=["hi"]
    )
    result = await tester.run_test_case(test_case)

    # Since we're not actually connecting to a bot,
    # we expect this to fail
    assert not result.success
    assert result.error is not None


def test_generate_report(tmp_path, test_config_file):
    """Test report generation."""
    tester = BotTester()
    tester.load_test_config(test_config_file)

    # Add a mock test result
    test_case = TestCase(
        name="Test Case 1",
        input_message="hello",
        expected_patterns=["hi"],
        requirements=["REQ-001"],
    )
    tester.results.append(
        TestResult(
            test_case=test_case,
            success=True,
            actual_response="hi there",
            response_time=0.5,
        )
    )

    # Generate report
    report_file = tmp_path / "report.json"
    report = tester.generate_report(report_file)

    assert report["summary"]["total_tests"] == 1
    assert report["summary"]["passed_tests"] == 1
    assert report["summary"]["failed_tests"] == 0

    # Check that files were created
    assert report_file.exists()
    assert report_file.with_suffix(".html").exists()
