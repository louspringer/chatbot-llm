#!/usr/bin/env python3

"""
Test message script for Teams Bot local testing.
Simulates user interactions and validates bot responses.
Includes requirement tracing and coverage reporting.
"""

import argparse
import asyncio
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    name: str
    input_message: str
    expected_patterns: List[str]
    conversation_type: str = "message"
    timeout_seconds: int = 5
    requirements: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class TestResult:
    test_case: TestCase
    success: bool
    actual_response: Optional[str]
    error: Optional[str] = None
    response_time: float = 0.0


@dataclass
class RequirementCoverage:
    requirement_id: str
    description: str
    acceptance_criteria: List[str]
    test_cases: List[str]
    passing_tests: List[str]
    failing_tests: List[str]

    @property
    def coverage_percentage(self) -> float:
        total = len(self.test_cases)
        if total == 0:
            return 0.0
        return (len(self.passing_tests) / total) * 100


class BotTester:
    def __init__(
        self,
        endpoint: str = "http://localhost:3978/api/messages",
        conversation_id: Optional[str] = None,
    ):
        self.endpoint = endpoint
        conv_id = conversation_id or f"test_{datetime.now().timestamp()}"
        self.conversation_id = conv_id
        self.results: List[TestResult] = []
        self.test_config = None
        self.requirement_coverage: Dict[str, RequirementCoverage] = {}

    def load_test_config(self, test_file: Path) -> None:
        """Load test configuration including requirements."""
        with open(test_file) as f:
            self.test_config = json.load(f)

        # Initialize requirement coverage tracking
        for req_id, req_info in self.test_config[
            "requirement_traces"
        ].items():
            self.requirement_coverage[req_id] = RequirementCoverage(
                requirement_id=req_id,
                description=req_info["description"],
                acceptance_criteria=req_info["acceptance_criteria"],
                test_cases=[],
                passing_tests=[],
                failing_tests=[],
            )

        # Map test cases to requirements
        for test_case in self.test_config["test_cases"]:
            for req_id in test_case.get("requirements", []):
                if req_id in self.requirement_coverage:
                    self.requirement_coverage[req_id].test_cases.append(
                        test_case["name"]
                    )

    def load_test_cases(self) -> List[TestCase]:
        """Load test cases from the configuration."""
        if not self.test_config:
            raise ValueError("Test configuration not loaded")

        return [
            TestCase(
                name=case["name"],
                input_message=case["input_message"],
                expected_patterns=case["expected_patterns"],
                conversation_type=case.get("conversation_type", "message"),
                timeout_seconds=case.get("timeout_seconds", 5),
                requirements=case.get("requirements", []),
                description=case.get("description", ""),
            )
            for case in self.test_config["test_cases"]
        ]

    async def send_message(
        self,
        message: str,
        activity_type: str = "message",
        timeout: Optional[aiohttp.ClientTimeout] = None,
    ) -> dict:
        """Send a message to the bot and return the response."""
        if timeout is None:
            timeout = aiohttp.ClientTimeout(total=30)

        activity = {
            "type": activity_type,
            "channelId": "emulator",
            "conversation": {"id": self.conversation_id},
            "from": {"id": "test-user"},
            "recipient": {"id": "bot"},
            "text": message,
            "timestamp": datetime.utcnow().isoformat(),
            "localTimestamp": datetime.now().isoformat(),
        }

        async with aiohttp.ClientSession() as session:
            try:
                start_time = asyncio.get_event_loop().time()
                async with session.post(
                    self.endpoint, json=activity, timeout=timeout
                ) as response:
                    end_time = asyncio.get_event_loop().time()
                    if response.status == 200:
                        return {
                            "success": True,
                            "response": await response.text(),
                            "time": end_time - start_time,
                        }
                    return {
                        "success": False,
                        "error": (
                            f"HTTP {response.status}: "
                            f"{await response.text()}"
                        ),
                        "time": end_time - start_time,
                    }
            except Exception as e:
                return {"success": False, "error": str(e), "time": 0.0}

    async def run_test_case(self, test_case: TestCase) -> TestResult:
        """Run a single test case and return the result."""
        logger.info(f"Running test: {test_case.name}")

        timeout = aiohttp.ClientTimeout(total=test_case.timeout_seconds)
        result = await self.send_message(
            test_case.input_message, test_case.conversation_type, timeout
        )

        if not result["success"]:
            return TestResult(
                test_case=test_case,
                success=False,
                actual_response=None,
                error=result["error"],
                response_time=result["time"],
            )

        # Check response against expected patterns
        response_text = result["response"]
        matches_all = all(
            pattern.lower() in response_text.lower()
            for pattern in test_case.expected_patterns
        )

        test_result = TestResult(
            test_case=test_case,
            success=matches_all,
            actual_response=response_text,
            response_time=result["time"],
        )

        # Update requirement coverage
        for req_id in test_case.requirements or []:
            if req_id in self.requirement_coverage:
                if matches_all:
                    self.requirement_coverage[req_id].passing_tests.append(
                        test_case.name
                    )
                else:
                    self.requirement_coverage[req_id].failing_tests.append(
                        test_case.name
                    )

        return test_result

    async def run_tests(self, test_cases: List[TestCase]) -> bool:
        """Run all test cases and return overall success."""
        self.results = []
        all_passed = True

        for test_case in test_cases:
            result = await self.run_test_case(test_case)
            self.results.append(result)

            if not result.success:
                all_passed = False
                logger.error(
                    f"Test '{test_case.name}' failed:"
                    f"\n  Input: {test_case.input_message}"
                    f"\n  Expected: {test_case.expected_patterns}"
                    f"\n  Actual: {result.actual_response}"
                    f"\n  Error: {result.error or 'Pattern mismatch'}"
                    f"\n  Requirements: {test_case.requirements}"
                )
            else:
                logger.info(
                    f"Test '{test_case.name}' passed"
                    f" ({result.response_time:.2f}s)"
                )

        return all_passed

    def generate_report(self, output_file: Optional[Path] = None) -> dict:
        """Generate a comprehensive test report with requirement coverage."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        avg_response_time = (
            sum(r.response_time for r in self.results) / total_tests
            if total_tests > 0
            else 0
        )

        # Calculate requirement coverage
        requirement_coverage = {
            req_id: {
                "description": coverage.description,
                "acceptance_criteria": coverage.acceptance_criteria,
                "coverage_percentage": coverage.coverage_percentage,
                "test_cases": coverage.test_cases,
                "passing_tests": coverage.passing_tests,
                "failing_tests": coverage.failing_tests,
            }
            for req_id, coverage in self.requirement_coverage.items()
        }

        # Group requirements by category
        category_coverage = defaultdict(list)
        for req_id, coverage in requirement_coverage.items():
            category = req_id.split("-")[0]
            category_coverage[category].append(
                {"requirement_id": req_id, **coverage}
            )

        report = {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%",
                "average_response_time": f"{avg_response_time:.2f}s",
            },
            "test_results": [
                {
                    "test_name": r.test_case.name,
                    "description": r.test_case.description,
                    "success": r.success,
                    "input": r.test_case.input_message,
                    "expected_patterns": r.test_case.expected_patterns,
                    "actual_response": r.actual_response,
                    "error": r.error,
                    "response_time": f"{r.response_time:.2f}s",
                    "requirements": r.test_case.requirements,
                }
                for r in self.results
            ],
            "requirement_coverage": {
                "by_requirement": requirement_coverage,
                "by_category": dict(category_coverage),
            },
        }

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_file}")

            # Generate HTML report
            html_file = output_file.with_suffix(".html")
            self.generate_html_report(report, html_file)
            logger.info(f"HTML report saved to {html_file}")

        return report

    def generate_html_report(self, report: dict, output_file: Path) -> None:
        """Generate an HTML version of the test report."""
        styles = """
            body { font-family: Arial, sans-serif; margin: 20px; }
            .summary {
                background: #f5f5f5;
                padding: 20px;
                margin-bottom: 20px;
            }
            .test-case {
                border: 1px solid #ddd;
                margin: 10px 0;
                padding: 10px;
            }
            .test-case.failed { background: #fff0f0; }
            .test-case.passed { background: #f0fff0; }
            .requirement { margin: 20px 0; }
            .category { margin: 30px 0; }
            .progress-bar {
                background: #ddd;
                height: 20px;
                border-radius: 10px;
                margin: 10px 0;
            }
            .progress {
                background: #4CAF50;
                height: 100%;
                border-radius: 10px;
                text-align: center;
                color: white;
            }
        """

        summary = report["summary"]
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bot Test Report</title>
            <style>{styles}</style>
        </head>
        <body>
            <h1>Bot Test Report</h1>

            <div class="summary">
                <h2>Summary</h2>
                <p>Total Tests: {summary['total_tests']}</p>
                <p>Passed Tests: {summary['passed_tests']}</p>
                <p>Failed Tests: {summary['failed_tests']}</p>
                <p>Success Rate: {summary['success_rate']}</p>
                <p>Average Response Time: {summary['average_response_time']}</p>
            </div>

            <h2>Requirement Coverage by Category</h2>
        """

        # Add requirement coverage by category
        by_category = report["requirement_coverage"]["by_category"]
        for category, requirements in by_category.items():
            html_content += f"""
            <div class="category">
                <h3>{category} Requirements</h3>
            """

            for req in requirements:
                coverage = req["coverage_percentage"]
                criteria_list = "".join(
                    f"<li>{criterion}</li>"
                    for criterion in req["acceptance_criteria"]
                )
                html_content += f"""
                <div class="requirement">
                    <h4>{req['requirement_id']}: {req['description']}</h4>
                    <div class="progress-bar">
                        <div class="progress" style="width: {coverage}%">
                            {coverage:.1f}%
                        </div>
                    </div>
                    <p>Acceptance Criteria:</p>
                    <ul>{criteria_list}</ul>
                    <p>Test Cases: {", ".join(req['test_cases'])}</p>
                    <p>Passing Tests: {", ".join(req['passing_tests'])}</p>
                    <p>Failing Tests: {", ".join(req['failing_tests'])}</p>
                </div>
                """
            html_content += "</div>"

        # Add test results
        html_content += "<h2>Test Results</h2>"

        for result in report["test_results"]:
            status_class = "passed" if result["success"] else "failed"
            error_html = (
                f"<p><strong>Error:</strong> {result['error']}</p>"
                if result["error"]
                else ""
            )
            patterns = ", ".join(result["expected_patterns"])
            reqs = ", ".join(result["requirements"])
            resp_time = result["response_time"]

            html_content += f"""
            <div class="test-case {status_class}">
                <h3>{result['test_name']}</h3>
                <p><strong>Description:</strong> {result['description']}</p>
                <p><strong>Input:</strong> {result['input']}</p>
                <p><strong>Expected Patterns:</strong> {patterns}</p>
                <p><strong>Response Time:</strong> {resp_time}</p>
                <p><strong>Requirements:</strong> {reqs}</p>
                {error_html}
            </div>
            """

        html_content += """
        </body>
        </html>
        """

        with open(output_file, "w") as f:
            f.write(html_content)


def main():
    parser = argparse.ArgumentParser(description="Test Teams Bot messages")
    parser.add_argument(
        "--test-file",
        type=Path,
        help="JSON file containing test cases",
        default=Path(__file__).parent / "test_cases.json",
    )
    parser.add_argument(
        "--endpoint",
        help="Bot endpoint URL",
        default="http://localhost:3978/api/messages",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Output file for test report (JSON and HTML)",
        default=None,
    )

    args = parser.parse_args()

    if not args.test_file.exists():
        logger.error(f"Test file not found: {args.test_file}")
        sys.exit(1)

    tester = BotTester(endpoint=args.endpoint)
    tester.load_test_config(args.test_file)
    test_cases = tester.load_test_cases()

    success = asyncio.run(tester.run_tests(test_cases))
    if args.report:
        tester.generate_report(args.report)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
