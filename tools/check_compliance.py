# Ontology: meta:ComplianceComponent
# Implements: meta:AutomatedValidator
# Requirement: REQ-VAL-003 Automated compliance checking
# Guidance: guidance:ValidationPatterns#AutomatedChecks
# Description: Automated compliance checking for guidance patterns

import logging
import sys
from pathlib import Path
from typing import Dict, List


def check_file_header(file_path: Path) -> Dict[str, bool]:
    """Check if a file has proper traceability headers."""
    required_headers = [
        "# Ontology:",
        "# Implements:",
        "# Requirement:",
        "# Guidance:",
        "# Description:",
    ]

    try:
        with open(file_path, "r") as f:
            content = f.read()
            return {h: h in content[:500] for h in required_headers}
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return {h: False for h in required_headers}


def scan_files(files: List[Path]) -> Dict[str, List[Dict]]:
    """Scan provided files for compliance issues."""
    results = {"missing_headers": []}

    for file_path in files:
        # Check headers
        header_checks = check_file_header(file_path)
        missing = [h for h, present in header_checks.items() if not present]
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
