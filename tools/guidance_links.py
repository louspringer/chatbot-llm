#!/usr/bin/env python3
"""
# Ontology: tools:GuidanceLinks
# Implements: tools:SymlinkManager
# Requirement: REQ-TOOLS-001 Guidance Link Management
# Guidance: guidance:ToolsPattern#FileManagement
# Description: Manages symbolic links for guidance files and ensures proper file structure
"""

import logging
import re
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_module_paths(ttl_file: Path) -> dict[str, str]:
    """Extract module imports and their paths from a Turtle file.

    Args:
        ttl_file: Path to the Turtle file

    Returns:
        Dictionary mapping module names to file paths

    Raises:
        FileNotFoundError: If ttl_file does not exist
        ValueError: If no module imports found
    """

    if not ttl_file.exists():
        raise FileNotFoundError("Turtle file not found: %s" % ttl_file)

    modules = {}
    with open(ttl_file, encoding="utf-8") as f:
        content = f.read()
        # Match owl:imports declarations with optional whitespace and indentation
        import_pattern = r"owl:imports\s+<\./([^>]+)>"
        matches = re.finditer(import_pattern, content)
        for match in matches:
            path = match.group(1)
            module_name = path.split("/")[-1].replace(".ttl", "")
            modules[module_name] = path

    if not modules:
        raise ValueError("No module imports found in %s" % ttl_file)

    return modules


def ensure_symlink(source: Path, target: Path) -> None:
    """Ensure a symlink exists from source to target."""
    if target.exists():
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        target.unlink()
    target.symlink_to(source)


def create_module_symlinks(
    source_dir: Path,
    target_dir: Path,
    modules: dict[str, str],
) -> None:
    """Create symlinks for guidance module files.

    Args:
        source_dir: Directory containing source module files
        target_dir: Directory where symlinks should be created
        modules: Dictionary mapping module names to file paths

    Raises:
        FileNotFoundError: If source_dir does not exist
    """
    if not source_dir.exists():
        raise FileNotFoundError("Source directory not found: %s" % source_dir)

    logger.info("Available source files:")
    for f in source_dir.glob("**/*.ttl"):
        logger.info("  %s", f.relative_to(source_dir))

    logger.info("Module mappings:")
    for module, file_path in modules.items():
        logger.info("  %s -> %s", module, file_path)

    for module, file_path in modules.items():
        source_file = source_dir / file_path
        target_file = target_dir / file_path

        try:
            ensure_symlink(source_file, target_file)
            logger.info("Created/verified symlink for %s", module)
        except (FileNotFoundError, FileExistsError, OSError) as e:
            logger.error("Error processing module %s: %s", module, e)


def main(project_root: Path | None = None) -> int:
    """Main entry point.

    Args:
        project_root: Optional project root path, defaults to script's parent directory

    Returns:
        0 on success, 1 on error
    """
    try:
        if project_root is None:
            project_root = Path(__file__).parent.parent

        ontology_framework_dir = project_root / "ontology-framework"
        guidance_ttl = project_root / "guidance.ttl"

        if not ontology_framework_dir.exists():
            raise FileNotFoundError(
                "ontology-framework directory not found at %s" % ontology_framework_dir,
            )

        if not guidance_ttl.exists():
            raise FileNotFoundError("guidance.ttl not found at %s" % guidance_ttl)

        modules = extract_module_paths(guidance_ttl)
        create_module_symlinks(ontology_framework_dir, project_root, modules)

        logger.info("Symlink creation complete!")
        logger.info(
            "Note: Make sure to add these symlinks to your version control system's ignore file.",
        )
        return 0

    except Exception as e:
        logger.error("Error: %s", e)
        return 1


if __name__ == "__main__":
    exit(main())
