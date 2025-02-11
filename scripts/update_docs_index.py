#!/usr/bin/env python3
"""
Script to automatically update the documentation index by scanning for new
documentation files and updating docs/index.md accordingly.
"""

from pathlib import Path
import re
import os
import signal
import argparse
import logging
from typing import Dict, List, Tuple
from contextlib import contextmanager


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(message)s' if not verbose else '%(levelname)s: %(message)s'
    )


class TimeoutException(Exception):
    pass


@contextmanager
def timeout(seconds: int = 2):
    """Context manager for timeout handling."""
    def timeout_handler(signum, frame):
        raise TimeoutException()
    
    # Set the timeout handler
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Restore the original handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)


def is_readable_file(file_path: Path) -> bool:
    """Check if file is readable and not a special file."""
    try:
        return (file_path.is_file() and 
                os.access(file_path, os.R_OK) and
                not file_path.is_symlink() and
                file_path.stat().st_size < 1_000_000)
    except (OSError, IOError):
        return False


def get_file_description(file_path: Path) -> str:
    """Extract description from file's frontmatter or first heading."""
    if not is_readable_file(file_path):
        logging.debug(f"Skipping unreadable file: {file_path}")
        return file_path.stem.replace("_", " ").title()
    
    try:
        with timeout(2):  # 2 second timeout for file operations
            with file_path.open('r', encoding='utf-8') as f:
                # Read first 1000 bytes to check for binary content
                try:
                    start = f.read(1000)
                    if '\0' in start:  # Skip binary files
                        logging.debug(f"Binary file detected: {file_path}")
                        return file_path.stem.replace("_", " ").title()
                    
                    # Reset file pointer
                    f.seek(0)
                    content = f.read(10000)  # Limit content read
                    
                    # Try to find description in frontmatter
                    if content.startswith("---"):
                        frontmatter = content.split("---")[1]
                        match = re.search(r'description:\s*(.+)', frontmatter)
                        if match:
                            desc = match.group(1).strip()
                            logging.debug(
                                f"Found frontmatter in {file_path}: {desc}"
                            )
                            return desc
                    
                    # Try to find first heading description
                    lines = content.split("\n")
                    for line in lines[:10]:  # Only check first 10 lines
                        if line.startswith("# "):
                            desc = line[2:].strip()
                            logging.debug(
                                f"Found heading in {file_path}: {desc}"
                            )
                            return desc
                except (UnicodeDecodeError, IOError) as e:
                    logging.debug(f"Error reading {file_path}: {str(e)}")
                
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
        "scripts_tools": {"script", "tool"}
    }
    
    file_name = file_path.name.lower()
    
    for category, keywords in categories.items():
        if any(keyword in file_name for keyword in keywords):
            logging.debug(f"Categorized {file_path} as {category}")
            return category
    
    logging.debug(f"No specific category found for {file_path}, using 'other'")
    return "other"


def generate_index_content(workspace_root: Path) -> str:
    """Generate the content for the index.md file."""
    docs = []
    excluded = {
        # Version Control
        ".git", ".svn",
        # Package/Environment
        "node_modules", ".venv", "venv", "env",
        "virtualenv", ".tox", ".conda",
        # Cache/Build
        "__pycache__", ".pytest_cache", ".mypy_cache",
        ".coverage", "htmlcov", ".ruff_cache",
        "build", "dist", ".eggs",
        # IDE/Editor
        ".vscode", ".idea", ".vs",
        # Other
        ".ipynb_checkpoints"
    }
    
    # Only include actual documentation files
    doc_extensions = {
        # Documentation
        ".md",    # Markdown documentation
        ".rst",   # ReStructured Text docs
        # Ontology files (since they contain documentation)
        ".ttl",   # Turtle format ontologies
        ".owl"    # Web Ontology Language files
    }
    
    logging.info("Scanning workspace for documentation files...")
    total_files = 0
    processed_files = 0
    skipped_files = 0
    
    for file_path in workspace_root.rglob("*"):
        total_files += 1
        try:
            # Skip excluded directories and non-matching files
            if any(x in file_path.parts for x in excluded):
                skipped_files += 1
                logging.debug(f"Skipping excluded path: {file_path}")
                continue
            
            if file_path.suffix not in doc_extensions:
                skipped_files += 1
                logging.debug(f"Skipping non-doc extension: {file_path}")
                continue
            
            if is_readable_file(file_path):
                rel_path = file_path.relative_to(workspace_root)
                category = categorize_file(file_path)
                description = get_file_description(file_path)
                docs.append((category, rel_path, description))
                processed_files += 1
                logging.debug(f"Processed: {rel_path}")
        except Exception as e:
            skipped_files += 1
            logging.debug(f"Error processing {file_path}: {str(e)}")
            continue
    
    stats = (
        f"{processed_files} docs processed, {skipped_files} skipped, "
        f"{total_files} total files"
    )
    logging.info(f"Scan complete: {stats}")
    
    # Generate the index content
    logging.info("Generating index content...")
    content = ["# Documentation Index\n"]
    
    # Add table of contents
    content.append("## Table of Contents")
    sections = [
        "Getting Started", "Project Documentation", "Bot Development",
        "Technical Documentation", "Testing and Debug Tools",
        "Reports and Analysis", "Scripts and Tools"
    ]
    
    for section in sections:
        link = section.lower().replace(' ', '-')
        content.append(f"- [{section}](#{link})")
    content.append("\n")
    
    # Add categorized documentation
    for category, files in sorted(group_by_category(docs).items()):
        title = category.replace('_', ' ').title()
        content.append(f"## {title}")
        for file_path, description in sorted(files):
            is_index = file_path == Path("docs/index.md")
            path = "#" if is_index else f"../{file_path}"
            content.append(f"- [{file_path.name}]({path}) - {description}")
        content.append("")
    
    content.append("---\n")
    msg = "*Note: This index is automatically maintained*"
    content.append(msg)
    
    return "\n".join(content)


def group_by_category(
    docs: List[Tuple[str, Path, str]]
) -> Dict[str, List[Tuple[Path, str]]]:
    """Group documentation files by their categories."""
    GroupedType = Dict[str, List[Tuple[Path, str]]]
    grouped: GroupedType = {}
    for category, path, description in docs:
        if category not in grouped:
            grouped[category] = []
        grouped[category].append((path, description))
    return grouped


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Update the documentation index by scanning for documentation files."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.verbose)
    
    workspace_root = Path(__file__).parent.parent
    index_path = workspace_root / "docs" / "index.md"
    
    logging.info(f"Starting documentation index update in {workspace_root}")
    
    # Create docs directory if it doesn't exist
    index_path.parent.mkdir(exist_ok=True)
    
    # Generate and write the index content
    content = generate_index_content(workspace_root)
    index_path.write_text(content)
    logging.info(f"Successfully updated {index_path}")


if __name__ == "__main__":
    main() 