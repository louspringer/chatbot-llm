# Ontology: meta:ComplianceComponent
# Implements: meta:AutomatedValidator
# Requirement: REQ-VAL-003 Automated compliance checking
# Guidance: guidance:ValidationPatterns#AutomatedChecks
# Description: Automated compliance checking for guidance patterns

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


def check_yaml_frontmatter(content: str) -> Optional[Dict[str, bool]]:
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


def check_comment_headers(content: str) -> Dict[str, bool]:
    """Check if a file has proper traceability in comment headers."""
    required_headers = [
        "# Ontology:",
        "# Implements:",
        "# Requirement:",
        "# Guidance:",
        "# Description:",
    ]
    return {h: h in content[:500] for h in required_headers}


def check_file_header(file_path: Path) -> Tuple[Dict[str, bool], str]:
    """Check if a file has proper traceability headers."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

            # For markdown and mdc files, try YAML frontmatter first
            if file_path.suffix.lower() in [".md", ".mdc"]:
                yaml_check = check_yaml_frontmatter(content)
                if yaml_check:
                    return yaml_check, "yaml"

            # Fall back to comment headers
            return check_comment_headers(content), "comment"
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return {
            h: False
            for h in [
                "# " + field.capitalize() + ":"
                for field in [
                    "ontology",
                    "implements",
                    "requirement",
                    "guidance",
                    "description",
                ]
            ]
        }, "error"


def scan_files(files: List[Path]) -> Dict[str, List[Dict]]:
    """Scan provided files for compliance issues."""
    results = {"missing_headers": []}

    for file_path in files:
        # Check headers
        header_checks, format_type = check_file_header(file_path)

        def format_header(h: str) -> str:
            """Format header based on type."""
            if format_type == "comment":
                return h
            return h.replace("# ", "").lower().rstrip(":")

        missing = [
            format_header(h) for h, present in header_checks.items() if not present
        ]
        if missing:
            results["missing_headers"].append(
                {"file": str(file_path), "missing": missing}
            )

    return results


def main():
    """Main entry point for compliance checking."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Get files from command line args or scan current directory
    files = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else []
    results = scan_files(files)

    # Log results
    if results["missing_headers"]:
        logger.warning("Files missing traceability headers:")
        for issue in results["missing_headers"]:
            missing = ", ".join(issue["missing"])
            logger.warning(f"  {issue['file']}: Missing {missing}")
    else:
        logger.info("All files comply with guidance patterns")

    # Exit with status code
    sys.exit(1 if results["missing_headers"] else 0)


if __name__ == "__main__":
    main()
