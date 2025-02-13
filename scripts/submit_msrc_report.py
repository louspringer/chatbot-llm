#!/usr/bin/env python3
"""Submit security report to Microsoft Security Response Center."""

import os
import logging
from pathlib import Path
from typing import Dict, Any

import requests
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Handle optional GitHub dependency
try:
    from github import Github
except ImportError:
    logger.warning("PyGithub not installed, GitHub integration disabled")
    Github = None


# MSRC API endpoints
MSRC_API_BASE = "https://api.msrc.microsoft.com/engage/v2.0"
MSRC_SUBMIT_ENDPOINT = f"{MSRC_API_BASE}/submissions"


def load_report(report_path: Path) -> Dict[str, Any]:
    """Load and parse the markdown report into API format."""
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")

    with open(report_path) as f:
        content = f.read()

    # Parse markdown sections into API format
    return {
        "title": (
            "Security: botbuilder-ai dependency blocks critical "
            "aiohttp security updates"
        ),
        "description": content,
        "product": {
            "name": "Bot Framework",
            "version": "4.16.2",
            "component": "botbuilder-ai",
        },
        "impact": {
            "severity": "Medium to High",
            "scope": ("All Bot Framework applications using botbuilder-ai"),
        },
        "reporter": {
            "name": "Lou Springer",
            "email": "lou@louspringer.com",
            "organization": "Independent Security Researcher",
        },
        "references": [
            {
                "url": "https://github.com/louspringer/chatbot-llm/issues/14",
                "description": "Project tracking issue",
            },
            {
                "url": (
                    "https://github.com/aio-libs/aiohttp/releases/"
                    "tag/v3.10.11"
                ),
                "description": "aiohttp Security Fixes",
            },
        ],
    }


def submit_report(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Submit the report to MSRC."""
    api_key = os.getenv("MSRC_API_KEY")
    if not api_key:
        raise ValueError("MSRC_API_KEY environment variable not set")

    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.post(
        MSRC_SUBMIT_ENDPOINT, headers=headers, json=report_data
    )

    if response.status_code != 201:
        logger.error("Failed to submit report: %s", response.text)
        response.raise_for_status()

    return response.json()


def update_github_issue(submission_id: str, status: str) -> None:
    """Update GitHub issue with submission details."""
    if not os.getenv("GITHUB_TOKEN"):
        logger.warning("GITHUB_TOKEN not set, skipping issue update")
        return

    if not Github:
        logger.warning("PyGithub not installed, skipping issue update")
        return

    g = Github(os.getenv("GITHUB_TOKEN"))
    repo = g.get_repo("louspringer/chatbot-llm")
    issue = repo.get_issue(14)
    issue.create_comment(
        "MSRC Report submitted:\n"
        f"- Submission ID: {submission_id}\n"
        f"- Status: {status}"
    )


def main() -> None:
    """Main entry point."""
    load_dotenv()

    try:
        report_path = Path("docs/security/msrc-report-2024-03.md")
        report_data = load_report(report_path)
        result = submit_report(report_data)

        logger.info("Report submitted successfully!")
        logger.info("Submission ID: %s", result.get("id"))
        logger.info("Status: %s", result.get("status"))

        update_github_issue(
            submission_id=result.get("id", "unknown"),
            status=result.get("status", "unknown"),
        )

    except Exception as e:
        logger.error("Failed to submit report: %s", str(e))
        raise


if __name__ == "__main__":
    main()
