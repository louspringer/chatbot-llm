#!/usr/bin/env python3
"""Create symlinks for ontology dependencies.

This script creates symlinks for ontology files referenced in chatbot.ttl.
It is idempotent - running it multiple times will produce the same result.
"""
from pathlib import Path
import re


def extract_prefix_paths(ttl_file: Path) -> dict:
    """Extract prefix declarations and their paths from a Turtle file.

    Args:
        ttl_file: Path to the Turtle file

    Returns:
        Dictionary mapping prefix names to file paths
    """
    prefixes = {}
    with open(ttl_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Match prefix declarations like @prefix name: <./path> .
        prefix_pattern = r'@prefix\s+(\w+):\s+<\./([^>]+)>\s*\.'
        matches = re.finditer(prefix_pattern, content)
        for match in matches:
            prefix_name = match.group(1)
            path = match.group(2)
            if path.endswith('#'):
                path = path[:-1]
            prefixes[prefix_name] = path + '.ttl'
    return prefixes


def ensure_symlink(source: Path, target: Path) -> None:
    """Ensure a symlink exists and points to the correct location.

    Args:
        source: Path to the source file
        target: Path where symlink should be created
    """
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return  # Symlink already exists and is correct
        target.unlink()  # Remove incorrect symlink
    elif target.exists():
        raise FileExistsError(f"Target exists and is not a symlink: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source.relative_to(target.parent))


def create_symlinks(source_dir: Path, target_dir: Path, prefixes: dict) -> None:
    """Create symlinks for ontology files.

    Args:
        source_dir: Directory containing source ontology files
        target_dir: Directory where symlinks should be created
        prefixes: Dictionary mapping prefix names to file paths
    """
    print("\nSource files available:")
    for f in source_dir.glob('*.ttl'):
        print(f"  {f.name}")

    print("\nPrefix mappings:")
    for prefix, file_path in prefixes.items():
        print(f"  {prefix} -> {file_path}")

    print(f"\nChecking source directory: {source_dir}")
    print("Found files:", [f.name for f in source_dir.glob('*.ttl')])
    print("\nAttempting to create symlinks for:", list(prefixes.values()))

    for prefix, file_path in prefixes.items():
        source_file = source_dir / file_path
        target_file = target_dir / file_path

        try:
            ensure_symlink(source_file, target_file)
        except FileNotFoundError:
            print(f"Source file not found: {source_file}")
        except FileExistsError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error creating symlink for {prefix}: {e}")


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).parent
    ontology_framework_dir = project_root / 'ontology-framework'

    if not ontology_framework_dir.exists():
        print(f"Error: ontology-framework directory not found at {ontology_framework_dir}")
        return

    chatbot_ttl = project_root / 'chatbot.ttl'
    if not chatbot_ttl.exists():
        print(f"Error: {chatbot_ttl} not found")
        return

    prefixes = extract_prefix_paths(chatbot_ttl)
    create_symlinks(ontology_framework_dir, project_root, prefixes)

    print("\nSymlink creation complete!")
    print("Note: Make sure to add these symlinks to your version control system's ignore file.")


if __name__ == "__main__":
    main()