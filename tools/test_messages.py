#!/usr/bin/env python3

# Ontology: chatbot:TestComponent
# Implements: chatbot:TestFramework
# Requirement: REQ-TEST-001 Automated test framework for Teams Bot
# Guidance: guidance:TestPatterns#TestFramework
# Description: Test message script for Teams Bot local testing.
#   Simulates user interactions and validates bot responses.
#   Includes requirement tracing and coverage reporting.

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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    name: str
    input_message: str
    expected_patterns: list[str]
    conversation_type: str = "message"
    timeout_seconds: int = 5
    requirements: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class TestResult:
    test_case: TestCase
    success: bool
    actual_response: str | None
    error: str | None = None
    response_time: float = 0.0


@dataclass
class RequirementCoverage:
    requirement_id: str
    description: str
    acceptance_criteria: list[str]
    test_cases: list[str]
    passing_tests: list[str]
    failing_tests: list[str]

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
        conversation_id: str | None = None,
    ):
        self.endpoint = endpoint
        conv_id = conversation_id or f"test_{datetime.now(tz=timezone.utc).timestamp()}"
        self.conversation_id = conv_id
        self.results: list[TestResult] = []
        self.test_config = None
        self.requirement_coverage: dict[str, RequirementCoverage] = {}

    def load_test_config(self, test_file: Path) -> None:
        """Load test configuration including requirements."""
        with test_file.open() as f:
            self.test_config = json.load(f)

        # Initialize requirement coverage tracking
        for req_id, req_info in self.test_config["requirement_traces"].items():
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
                        test_case["name"],
                    )

    def load_test_cases(self) -> list[TestCase]:
        """Load test cases from the configuration."""
        if not self.test_config:
            error_msg = "Test configuration not loaded"
            raise ValueError(error_msg)

        return [TestCase(**case) for case in self.test_config.get("test_cases", [])]

    async def send_message(
        self,
        message: str,
        conversation_type: str = "message",
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> dict:
        """Send a message to the bot and return the response."""
        activity = {
            "type": conversation_type,
            "text": message,
        }

        async with aiohttp.ClientSession() as session:
            try:
                start_time = time.time()
                async with session.post(
                    self.endpoint,
                    json=activity,
                    timeout=timeout,
                ) as response:
                    end_time = time.time()
                    if response.status == 200:
                        return {
                            "success": True,
                            "response": await response.text(),
                            "time": end_time - start_time,
                        }
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "time": end_time - start_time,
                    }
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                return {"success": False, "error": str(e), "time": 0.0}

    async def run_test_case(self, test_case: TestCase) -> TestResult:
        """Run a single test case."""
        logger.info("Running test: %s", test_case.name)
        start_time = time.time()

        try:
            response = await self.send_message(
                test_case.input_message,
                test_case.conversation_type,
                timeout=aiohttp.ClientTimeout(total=test_case.timeout_seconds),
            )
            actual_response = response.get("text", "")

            # Check if response matches expected patterns
            success = any(
                pattern.lower() in actual_response.lower()
                for pattern in test_case.expected_patterns
            )

            return TestResult(
                test_case=test_case,
                success=success,
                actual_response=actual_response,
                error=(
                    "Response did not match expected patterns" if not success else None
                ),
                response_time=time.time() - start_time,
            )

        except Exception as e:
            return TestResult(
                test_case=test_case,
                success=False,
                actual_response=None,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def run_tests(self, test_cases: list[TestCase]) -> bool:
        """Run all test cases and return overall success status."""
        all_passed = True
        for test_case in test_cases:
            result = await self.run_test_case(test_case)
            self.results.append(result)

            if not result.success:
                all_passed = False
                error_msg = (
                    f"Test '{test_case.name}' failed:\n"
                    f"  Input: {test_case.input_message}\n"
                    f"  Expected: {test_case.expected_patterns}\n"
                    f"  Actual: {result.actual_response}\n"
                    f"  Error: {result.error or 'Pattern mismatch'}\n"
                    f"  Requirements: {test_case.requirements}"
                )
                logger.error(error_msg)
            else:
                logger.info(
                    "Test '%s' passed (%.2fs)",
                    test_case.name,
                    result.response_time,
                )

        return all_passed

    def generate_report(self, output_file: Path | None = None) -> dict:
        """Generate test report."""
        report = {
            "summary": {
                "total_tests": len(self.results),
                "passed_tests": len([r for r in self.results if r.success]),
                "failed_tests": len([r for r in self.results if not r.success]),
                "average_response_time": (
                    sum(r.response_time for r in self.results) / len(self.results)
                    if self.results
                    else 0.0
                ),
            },
            "test_results": [
                {
                    "name": result.test_case.name,
                    "success": result.success,
                    "actual_response": result.actual_response,
                    "error": result.error,
                    "response_time": result.response_time,
                    "requirements": result.test_case.requirements,
                }
                for result in self.results
            ],
        }

        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with output_file.open("w") as f:
                json.dump(report, f, indent=2)
            logger.info("Report saved to %s", output_file)

            # Generate HTML report
            html_file = output_file.with_suffix(".html")
            self.generate_html_report(report, html_file)
            logger.info("HTML report saved to %s", html_file)

        return report

    def generate_html_report(self, report: dict, output_file: Path) -> None:
        """Generate HTML test report."""
        styles = """
            body { font-family: Arial, sans-serif; margin: 20px; }
            .summary { background: #f5f5f5; padding: 20px; margin-bottom: 20px; }
            .test-case { border: 1px solid #ddd; margin: 10px 0; padding: 10px; }
            .test-case.failed { background: #fff0f0; }
            .test-case.passed { background: #f0fff0; }
        """

        test_results = "".join(
            f"""
            <div class="test-case {'passed' if r['success'] else 'failed'}">
                <h3>{r['name']}</h3>
                <p>Success: {r['success']}</p>
                <p>Response Time: {r['response_time']:.2f}s</p>
                {f"<p>Error: {r['error']}</p>" if r.get('error') else ''}
                {f"<p>Requirements: {', '.join(r['requirements'])}</p>" if r.get('requirements') else ''}
            </div>
            """
            for r in report["test_results"]
        )

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
                <p>Total Tests: {report['summary']['total_tests']}</p>
                <p>Passed Tests: {report['summary']['passed_tests']}</p>
                <p>Failed Tests: {report['summary']['failed_tests']}</p>
                <p>Average Response Time: {report['summary']['average_response_time']:.2f}s</p>
            </div>

            <h2>Test Results</h2>
            {test_results}
        </body>
        </html>
        """

        with output_file.open("w") as f:
            f.write(html_content)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run bot tests")
    parser.add_argument("test_file", type=Path, help="Test configuration file")
    parser.add_argument(
        "--endpoint",
        default="http://localhost:3978/api/messages",
        help="Bot endpoint URL",
    )
    args = parser.parse_args()

    if not args.test_file.exists():
        logger.error("Test file not found: %s", args.test_file)
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
