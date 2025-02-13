#!/usr/bin/env python3
import subprocess
import argparse
from pathlib import Path


def generate_plantuml_diagram(
    source_file: str,
    source_dir: str = "./assets/diagrams/source",
    target_dir: str = "./assets/diagrams/generated",
    plantuml_jar: str = "./tools/plantuml.jar"
) -> None:
    """
    Generate SVG diagram from PlantUML source file.
    
    Args:
        source_file: PlantUML source file name
        source_dir: Directory containing PlantUML source files
        target_dir: Directory where generated diagrams should be placed
        plantuml_jar: Path to PlantUML jar file
    """
    # Ensure directories exist
    Path(source_dir).mkdir(parents=True, exist_ok=True)
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    
    # Construct full paths
    source_path = Path(source_dir) / source_file
    
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    if not Path(plantuml_jar).exists():
        raise FileNotFoundError(f"PlantUML jar not found: {plantuml_jar}")
    
    # Run PlantUML
    cmd = [
        "java", "-jar", plantuml_jar,
        "-verbose",  # Add verbose logging
        "-tsvg",  # Generate SVG
        "-output", str(Path(target_dir).absolute()),  # Output directory
        str(source_path)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Generated diagram from {source_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating diagram: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Generate diagrams from PlantUML files"
    )
    parser.add_argument(
        "source_file",
        help="PlantUML source file name"
    )
    parser.add_argument(
        "--source-dir",
        default="./assets/diagrams/source",
        help="Directory containing PlantUML source files"
    )
    parser.add_argument(
        "--target-dir",
        default="./assets/diagrams/generated",
        help="Directory where generated diagrams should be placed"
    )
    parser.add_argument(
        "--plantuml-jar",
        default="./tools/plantuml.jar",
        help="Path to PlantUML jar file"
    )
    
    args = parser.parse_args()
    
    generate_plantuml_diagram(
        args.source_file,
        args.source_dir,
        args.target_dir,
        args.plantuml_jar
    )


if __name__ == "__main__":
    main() 