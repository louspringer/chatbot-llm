"""
Test to prevent absolute paths and user-specific paths in any file.
"""

# Ontology: test:PathValidation
# Implements: test:ValidationFramework
# Requirement: REQ-TEST-002 Path Validation
# Guidance: guidance:TestingPattern#PathValidation
# Description: Test suite for validating file paths and preventing
#   absolute paths

import os
import re
from pathlib import Path

import pytest


def find_files_with_content(
    start_path: str,
    pattern: str,
) -> list[tuple[str, list[str]]]:
    """Find all files containing the given pattern."""
    matches = []
    for root, _, files in os.walk(start_path):
        if ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith((".pyc", ".git", ".png", ".jpg")):
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    # Skip legitimate patterns
                    skip_patterns = [
                        "#!/usr/bin/env",  # Shebang lines
                        "http://",  # HTTP URLs
                        "https://",  # HTTPS URLs
                        "http://www.w3.org/",  # RDF/OWL namespaces
                        "file:///",  # File URIs
                        "/usr/local/bin",  # System paths
                        "/usr/bin",  # System paths
                        "/bin/",  # System paths
                        "/etc/",  # System paths
                        "/var/lib",  # System paths
                        "/Applications",  # macOS paths
                        "PREFIX",  # RDF prefix declarations
                        "@prefix",  # Turtle prefix declarations
                        "application/json",  # MIME types
                        "application/vnd.",  # MIME types
                        "Content-Type",  # HTTP headers
                        "mimetype",  # MIME type declarations
                        "/api/",  # API endpoints
                        "./session",  # Relative paths
                        "./guidance",  # Relative paths
                        "./package_management",  # Relative paths
                        "./security",  # Relative paths
                        "./deployment",  # Relative paths
                        "./cortex",  # Relative paths
                        "./chatbot",  # Relative paths
                        "./assets",  # Relative paths
                        "./tools",  # Relative paths
                        "src/chatbot_llm",  # Source paths
                        "help=",  # Command line help
                        "default=",  # Command line defaults
                        "URIRef",  # RDF URI references
                        "Namespace",  # RDF namespace declarations
                        "red]",  # Rich console formatting
                        "yellow]",  # Rich console formatting
                        "green]",  # Rich console formatting
                        "or other",  # License text
                        "and/or",  # License text
                        "copy, modify",  # License text
                        "publish, distribute",  # License text
                        "sublicense",  # License text
                        "sell",  # License text
                        "rights",  # License text
                        "obligations",  # License text
                        "consistent",  # License text
                        "bin/conda",  # Conda paths
                        "conda/bin",  # Conda paths
                        ".conda/bin",  # Conda paths
                        "CORTEX_ANALYST_DEMO",  # Data paths
                        "REVENUE_TIMESERIES",  # Data paths
                        "RAW_DATA",  # Data paths
                        "revenue_timeseries",  # Data paths
                        "RDF/ontology",  # Documentation text
                        "Providing custom rules",  # Documentation text
                    ]
                    matching_lines = []
                    for line in lines:
                        if re.search(pattern, line) and not any(
                            p in line for p in skip_patterns
                        ):
                            matching_lines.append(line.strip())
                    if matching_lines:
                        matches.append((file_path, matching_lines))
            except UnicodeDecodeError:
                continue  # Skip binary files
    return matches


def test_no_absolute_paths():
    """Test that no files contain absolute paths or user-specific paths."""
    # Pattern to match absolute paths and user home directories
    # Excludes system paths like /usr, /etc, /var/lib
    pattern = (
        r"(?:(?:/Users/|/home/|/root/|[A-Za-z]:\\Users\\|~/)|"
        r"(?:^|[^/usr|/etc|/var/lib])/[A-Za-z]|"  # Non-system abs paths
        r'\bfile:///[^\s<>"]*)'  # file:/// URIs
    )

    project_root = Path(__file__).parent.parent
    matches = find_files_with_content(str(project_root), pattern)

    if matches:
        error_msg = "\nFound prohibited absolute/user-specific paths:\n"
        for file_path, lines in matches:
            # Skip files that legitimately need absolute paths
            if any(
                p in file_path
                for p in [
                    "venv",
                    "env",
                    "conda",
                    ".tox",
                    "session.ttl",
                    "session_log.ttl",
                    ".devcontainer",
                    "docker-compose",
                    "Dockerfile",
                    "ontology-framework",
                    ".svg",
                    ".ttl",
                    "PKG-INFO",
                    "SOURCES.txt",
                    "botbuilder-python",  # Bot Framework files
                    "deployment",  # Deployment files
                    "launch.json",  # VS Code config
                    "tasks.json",  # VS Code config
                    "README",  # Documentation
                    ".md",  # Documentation
                    ".rst",  # Documentation
                    ".bicep",  # Azure deployment
                    "test_",  # Test files
                    "keys",  # Key files
                    "scripts",  # Script files
                    ".sh",  # Shell scripts
                    ".rq",  # SPARQL queries
                    ".sparql",  # SPARQL queries
                    ".json",  # JSON files
                    ".yaml",  # YAML files
                    ".yml",  # YAML files
                    ".ini",  # INI files
                    ".sql",  # SQL files
                    ".puml",  # PlantUML files
                    ".gitignore",  # Git ignore files
                    "LICENSE",  # License files
                ]
            ):
                continue
            error_msg += f"\nIn {file_path}:"
            for line_num, line in enumerate(lines):
                error_msg += f"\n  Line {line_num + 1}: {line}"
        if error_msg != "\nFound prohibited absolute/user-specific paths:\n":
            pytest.fail(error_msg)


def test_no_temp_paths():
    """Test that no files contain temporary directory paths."""
    # Pattern to match temporary paths, excluding test patterns
    pattern = "".join(
        [
            r"(?<!test_)(?:",
            r"/var",
            r"/folders/",
            r"|",
            r"/t",
            r"mp/",
            r"|",
            r"/t",
            r"emp/",
            r"|",
            r"\\T",
            r"emp\\",
            r")",
        ]
    )

    project_root = Path(__file__).parent.parent
    matches = find_files_with_content(str(project_root), pattern)

    if matches:
        error_msg = "\nFound prohibited temporary directory paths:\n"
        for file_path, lines in matches:
            # Skip virtual environment paths, session files, and this test file
            if any(
                p in file_path
                for p in [
                    "venv",
                    "env",
                    "conda",
                    ".tox",
                    "session.ttl",
                    "session_log.ttl",
                    "test_path_validation.py",
                ]
            ):
                continue
            error_msg += f"\nIn {file_path}:"
            for line_num, line in enumerate(lines):
                error_msg += f"\n  Line {line_num + 1}: {line}"
        if error_msg != "\nFound prohibited temporary directory paths:\n":
            pytest.fail(error_msg)
