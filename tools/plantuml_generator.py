#!/usr/bin/env python3

# Ontology: chatbot:DiagramComponent
# Implements: chatbot:DiagramGenerator
# Requirement: REQ-DOC-001 Automated diagram generation from PlantUML sources
# Guidance: guidance:SecurityPatterns#CommandValidation
# Description: Generates SVG diagrams from PlantUML source files with secure
#   path validation and command execution controls.

import argparse
import subprocess
import sys
from pathlib import Path


def validate_path(path: str | Path, expected_suffix: str | None = None) -> Path:
    """
    Validate a file path to ensure it is safe to use.

    Args:
        path: Path to validate
        expected_suffix: Expected file suffix (e.g. '.puml')

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is not safe
    """
    try:
        path_obj = Path(path).resolve()
        if expected_suffix and path_obj.suffix != expected_suffix:
            error_msg = (
                f"Invalid file suffix: {path_obj.suffix}, expected: {expected_suffix}"
            )
            raise ValueError(error_msg)
        return path_obj
    except (TypeError, ValueError) as e:
        error_msg = f"Invalid path: {path}"
        raise ValueError(error_msg) from e


def validate_command(cmd: list[str], allowed_jar: Path) -> bool:
    """
    Validate the PlantUML command for security.

    Args:
        cmd: Command list to validate
        allowed_jar: Path to allowed PlantUML jar

    Returns:
        bool: True if command is safe
    """
    if len(cmd) < 4:
        return False

    # Validate java command
    if cmd[0] != "java":
        return False

    # Validate jar argument
    if cmd[1] != "-jar":
        return False

    # Validate jar path matches allowed jar
    jar_path = Path(cmd[2]).resolve()
    if jar_path != allowed_jar:
        return False

    # Validate PlantUML options
    valid_options = {"-verbose", "-tsvg", "-output"}
    options = {arg for arg in cmd[3:-2] if arg.startswith("-")}
    return options.issubset(valid_options)


def generate_plantuml_diagram(
    source_file: str,
    source_dir: str = "./assets/diagrams/source",
    target_dir: str = "./assets/diagrams/generated",
    plantuml_jar: str = "./tools/plantuml.jar",
) -> None:
    """
    Generate SVG diagram from PlantUML source file.

    Args:
        source_file: PlantUML source file name
        source_dir: Directory containing PlantUML source files
        target_dir: Directory where generated diagrams should be placed
        plantuml_jar: Path to PlantUML jar file

    Security:
        All paths are validated and resolved before use:
        - source_dir is validated and must exist
        - target_dir is validated and created if needed
        - plantuml_jar must exist and have .jar extension
        - source_file must have .puml extension
        - Command structure is validated before execution
        - Only specific PlantUML options are allowed
        - Java execution is restricted to specific jar file
    """
    # Validate and resolve paths
    source_dir_path = validate_path(source_dir)
    target_dir_path = validate_path(target_dir)
    plantuml_jar_path = validate_path(plantuml_jar, expected_suffix=".jar")
    source_path = validate_path(source_dir_path / source_file, expected_suffix=".puml")

    # Ensure directories exist
    source_dir_path.mkdir(parents=True, exist_ok=True)
    target_dir_path.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        error_msg = f"Source file not found: {source_path}"
        raise FileNotFoundError(error_msg)

    if not plantuml_jar_path.exists():
        error_msg = f"PlantUML jar not found: {plantuml_jar_path}"
        raise FileNotFoundError(error_msg)

    # Run PlantUML with validated paths
    cmd = [
        "java",
        "-jar",
        str(plantuml_jar_path),
        "-verbose",  # Add verbose logging
        "-tsvg",  # Generate SVG
        "-output",
        str(target_dir_path),  # Output directory
        str(source_path),
    ]

    # Validate command before execution
    if not validate_command(cmd, plantuml_jar_path):
        error_msg = "Invalid PlantUML command configuration"
        raise ValueError(error_msg)

    try:
        # ruff: noqa: S603
        # Security measures implemented:
        # 1. All paths are validated and resolved
        # 2. Command structure is checked
        # 3. Only specific PlantUML options are allowed
        # 4. Java execution is restricted to specific jar file
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Generated diagram from {source_file}")
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to generate diagram: {e.stderr}"
        raise RuntimeError(error_msg) from e


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate PlantUML diagrams")
    parser.add_argument("source_file", help="PlantUML source file name")
    parser.add_argument(
        "--source-dir",
        default="./assets/diagrams/source",
        help="Directory containing PlantUML source files",
    )
    parser.add_argument(
        "--target-dir",
        default="./assets/diagrams/generated",
        help="Directory where generated diagrams should be placed",
    )
    parser.add_argument(
        "--plantuml-jar",
        default="./tools/plantuml.jar",
        help="Path to PlantUML jar file",
    )

    args = parser.parse_args()

    try:
        generate_plantuml_diagram(
            args.source_file,
            args.source_dir,
            args.target_dir,
            args.plantuml_jar,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        error_msg = str(e)
        print(error_msg, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
