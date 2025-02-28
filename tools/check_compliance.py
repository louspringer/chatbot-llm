# Ontology: meta:ComplianceComponent
# Implements: meta:AutomatedValidator
# Requirement: REQ-VAL-003 Automated compliance checking
# Guidance: guidance:ValidationPatterns#AutomatedChecks
# Description: Automated compliance checking for guidance patterns

import logging
import re
import sys
from pathlib import Path

import yaml

# Patterns for files to exclude from compliance checking
EXCLUDE_PATTERNS = [
    r".*_log\.ttl$",  # Session and other log files
    r"^tests?/.*/(test_.*|__init__)\.py$",  # Test files
    r"\.pytest_cache/.*",  # Pytest cache
    r"__pycache__/.*",  # Python cache
    r"\.git/.*",  # Git files
    r"\.venv/.*",  # Virtual env
]


def should_exclude(file_path: Path) -> bool:
    """Check if a file should be excluded from compliance checking."""
    str_path = str(file_path)
    return any(re.match(pattern, str_path) for pattern in EXCLUDE_PATTERNS)


def check_yaml_frontmatter(content: str) -> dict[str, bool] | None:
    """Check if a file has proper traceability in YAML frontmatter."""
    required_fields = {
        "ontology": False,
        "implements": False,
        "requirement": False,
        "guidance": False,
        "description": False,
    }

    try:
        # Check for YAML frontmatter between --- markers
        if content.startswith("---"):
            # Find the end of frontmatter
            end_marker = content.find("\n---", 3)
            if end_marker == -1:  # Try without newline
                end_marker = content.find("---", 3)
            if end_marker != -1:
                yaml_content = content[3:end_marker]
                frontmatter = yaml.safe_load(yaml_content)
                if isinstance(frontmatter, dict):
                    result = {}
                    for field in required_fields:
                        result[field] = field in frontmatter
                    return result
    except yaml.YAMLError:
        pass
    return None


def check_docstring_traceability(content: str) -> dict[str, bool] | None:
    """Check for traceability in docstring format.

    Handles format like:
    ```
    Traceability:
        - Ontology: value
        - Class: value
        - Property: value
        - Implements: value
        - Requirement: value
        - Guidance: value
        - Description: value
    ```
    """
    # Look for docstring with Traceability section
    docstring_pattern = r'"""[^"]*?Traceability:\s*(.*?)"""'
    docstring_match = re.search(docstring_pattern, content, re.DOTALL)
    if not docstring_match:
        return None

    traceability_text = docstring_match.group(1)

    # Check for required fields
    fields = {
        "Ontology": False,
        "Implements": False,  # Can be satisfied by Class or Property
        "Requirement": False,
        "Guidance": False,
        "Description": False,
    }

    for field in fields:
        # Match both formats:
        # - Field: value
        # - # Field: value
        pattern = rf"(?:^|\n)\s*(?:-\s*|#\s*)?{field}:\s*\S+"
        if field == "Implements":
            # Also check for Class or Property as alternatives
            class_pat = r"(?:^|\n)\s*(?:-\s*|#\s*)?Class:\s*\S+"
            prop_pat = r"(?:^|\n)\s*(?:-\s*|#\s*)?Property:\s*\S+"
            fields[field] = bool(
                re.search(pattern, traceability_text)
                or re.search(class_pat, traceability_text)
                or re.search(prop_pat, traceability_text),
            )
        else:
            fields[field] = bool(re.search(pattern, traceability_text))

    return {f"# {k}": v for k, v in fields.items()}


def check_comment_headers(content: str) -> dict[str, bool]:
    """Check if a file has proper traceability in comment headers."""
    required_headers = [
        r"# Ontology:\s+\S+",
        r"# Implements:\s+\S+",
        r"# Requirement:\s+\S+",
        r"# Guidance:\s+\S+",
        r"# Description:\s+\S+",
    ]
    header_checks = {
        h.split(":")[0]: bool(re.search(h, content[:500])) for h in required_headers
    }

    # Check for Class or Property as alternatives to Implements
    if not header_checks["# Implements"]:
        class_match = re.search(r"# Class:\s+\S+", content[:500])
        prop_match = re.search(r"# Property:\s+\S+", content[:500])
        header_checks["# Implements"] = bool(class_match or prop_match)

    return header_checks


def check_file_header(file_path: Path) -> tuple[dict[str, bool], str]:
    """Check if a file has proper traceability headers."""
    try:
        with open(file_path) as f:
            content = f.read()

            # Try docstring format first for Python files
            if file_path.suffix.lower() == ".py":
                docstring_check = check_docstring_traceability(content)
                if docstring_check and any(docstring_check.values()):
                    return docstring_check, "docstring"

            # For markdown and mdc files, try YAML frontmatter
            if file_path.suffix.lower() in [".md", ".mdc"]:
                yaml_check = check_yaml_frontmatter(content)
                if yaml_check:
                    return yaml_check, "yaml"

            # Fall back to comment headers
            comment_check = check_comment_headers(content)
            if any(comment_check.values()):
                return comment_check, "comment"

            # If no format matched but we found partial headers, return
            # the most complete result
            if docstring_check:
                # Return docstring format if available since it's more structured
                return docstring_check, "docstring"
            # Otherwise return comment format as fallback
            return comment_check, "comment"

    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return {
            h: False
            for h in [
                "# " + field.capitalize()
                for field in [
                    "Ontology",
                    "Implements",
                    "Requirement",
                    "Guidance",
                    "Description",
                ]
            ]
        }, "error"


def scan_files(files: list[Path]) -> dict[str, list[dict]]:
    """Scan provided files for compliance issues."""
    results = {"missing_headers": []}

    for file_path in files:
        if should_exclude(file_path):
            continue

        # Check headers
        header_checks, format_type = check_file_header(file_path)

        def format_header(h: str) -> str:
            """Format header based on type."""
            if format_type == "comment":
                return h
            return h.replace("# ", "").lower().rstrip(":")

        missing = [h for h, present in header_checks.items() if not present]
        if missing:
            results["missing_headers"].append(
                {
                    "file": str(file_path),
                    "missing": [format_header(h) for h in missing],
                    "format": format_type,
                    "found_headers": [
                        format_header(h)
                        for h, present in header_checks.items()
                        if present
                    ],
                },
            )

    return results


def main():
    """Main entry point for compliance checking."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Get files from command line args or scan current directory
    files = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else []
    results = scan_files(files)

    # Log results with improved messages
    if results["missing_headers"]:
        logger.warning("Files missing traceability headers:")
        for issue in results["missing_headers"]:
            file_path = issue["file"]
            missing = ", ".join(issue["missing"])
            format_type = issue["format"]
            found = (
                ", ".join(issue["found_headers"]) if issue["found_headers"] else "none"
            )

            logger.warning(f"  {file_path}:")
            logger.warning(f"    Format detected: {format_type}")
            logger.warning(f"    Headers found: {found}")
            logger.warning(f"    Headers missing: {missing}")
            logger.warning("")
    else:
        logger.info("All files comply with guidance patterns")

    # Exit with status code
    sys.exit(1 if results["missing_headers"] else 0)


if __name__ == "__main__":
    main()
