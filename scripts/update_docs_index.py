#!/usr/bin/env python3
"""
Script to automatically update the documentation index by scanning for new
documentation files and updating docs/index.md accordingly.
"""

import argparse
import logging
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)


class TimeoutException(Exception):
    """Exception raised when a timeout occurs."""


@contextmanager
def timeout(seconds: int = 2):
    """Context manager for timing out operations."""

    def timeout_handler(signum: Any, frame: Any) -> None:
        raise TimeoutException()

    # Register the signal handler
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)


def is_readable_file(file_path: Path) -> bool:
    """Check if a file is readable and not a binary file."""
    try:
        with timeout():
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" not in chunk
    except (TimeoutException, Exception):
        return False


def get_file_description(file_path: Path) -> str:
    """Extract a description from a file's contents."""
    try:
        if not is_readable_file(file_path):
            return file_path.stem.replace("_", " ").title()

        with timeout():
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

                # Try to find frontmatter description
                if "---" in content:
                    try:
                        _, frontmatter, _ = content.split("---", 2)
                        if "description:" in frontmatter:
                            desc = frontmatter.split("description:", 1)[1]
                            desc = desc.split("\n", 1)[0].strip()
                            logging.debug(
                                f"Found frontmatter in {file_path}: {desc}"
                            )
                            return desc
                    except Exception:
                        pass

                # Try to find first heading description
                lines = content.split("\n")
                for line in lines[:10]:  # Only check first 10 lines
                    if line.startswith("# "):
                        desc = line[2:].strip()
                        logging.debug(f"Found heading in {file_path}: {desc}")
                        return desc

    except (TimeoutException, Exception) as e:
        logging.debug(f"Error processing {file_path}: {str(e)}")

    return file_path.stem.replace("_", " ").title()


def categorize_file(file_path: Path) -> str:
    """Determine the appropriate category for a file."""
    categories = {
        "getting_started": {"README", "CONTRIBUTING", "LICENSE"},
        "setup_and_config": {"environment", "config", ".env"},
        "development_guides": {"guide", "tutorial", "development"},
        "cortex_framework": {"cortex"},
        "issue_management": {"issue"},
        "pull_requests": {"pr", "pull"},
        "ontology_framework": {".ttl"},
        "deployment_config": {"deployment"},
        "sparql_queries": {".sparql", ".rq"},
        "testing_debug": {"test", "debug"},
        "reports_analysis": {"report", "analysis"},
        "scripts_tools": {"script", "tool"},
    }

    file_name = file_path.name.lower()
    file_stem = file_path.stem.lower()
    file_suffix = file_path.suffix.lower()

    # Check each category's patterns
    for category, patterns in categories.items():
        for pattern in patterns:
            if (
                pattern in file_name
                or pattern in file_stem
                or pattern == file_suffix
            ):
                return category

    return "other"


def generate_index_content(workspace_root: Path) -> str:
    """Generate the documentation index content."""
    docs: List[Tuple[str, Path, str]] = []

    # Scan for documentation files
    for file_path in workspace_root.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip certain directories and files
        if any(part.startswith(".") for part in file_path.parts):
            continue
        if "node_modules" in file_path.parts:
            continue

        # Only include documentation files
        if file_path.suffix.lower() in {".md", ".rst", ".txt", ".ttl"}:
            relative_path = file_path.relative_to(workspace_root)
            category = categorize_file(file_path)
            description = get_file_description(file_path)
            docs.append((category, relative_path, description))

    # Group by category
    grouped = group_by_category(docs)

    # Generate markdown content
    content = ["# Documentation Index\n"]
    content.append("## Table of Contents")

    # Add TOC entries
    for category in sorted(grouped.keys()):
        display_name = category.replace("_", " ").title()
        content.append(f"- [{display_name}](#{category})")

    content.append("\n")

    # Add category sections
    for category in sorted(grouped.keys()):
        display_name = category.replace("_", " ").title()
        content.append(f"\n## {display_name}")

        # Add file entries
        for file_path, description in sorted(grouped[category]):
            link_text = file_path.name
            if file_path.name == "index.md":
                link_text = "#"
            content.append(f"- [{link_text}]({file_path}) - {description}")

    content.append("\n---\n")
    content.append("*Note: This index is automatically maintained*")

    return "\n".join(content)


def group_by_category(
    docs: List[Tuple[str, Path, str]],
) -> Dict[str, List[Tuple[Path, str]]]:
    """Group documentation files by their categories."""
    grouped: Dict[str, List[Tuple[Path, str]]] = {}
    for category, path, description in docs:
        if category not in grouped:
            grouped[category] = []
        grouped[category].append((path, description))
    return grouped


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Update documentation index by scanning files."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    workspace_root = Path.cwd()
    index_path = workspace_root / "docs" / "index.md"

    logger.info(f"Generating documentation index at {index_path}")
    content = generate_index_content(workspace_root)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content)
    logger.info("Documentation index updated successfully")


if __name__ == "__main__":
    main()
